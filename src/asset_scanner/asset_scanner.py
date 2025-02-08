import os
from pathlib import Path
import shutil
import tempfile
from typing import Set, Dict, Optional, List, Pattern, Callable, Any, Tuple
from datetime import datetime
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import concurrent

from asset_scanner.class_parser.class_parser import ClassParser

from .asset_models import Asset, ScanResult
from .pbo_extractor import PboExtractor
from .scanner_engine import ScannerEngine, PBOScannerEngine, RegularFileScannerEngine

logger = logging.getLogger(__name__)


class AssetScanner:
    """Asset scanner for game content"""

    VALID_EXTENSIONS = {'.p3d', '.paa', '.sqf', '.pbo', '.wss', '.ogg', '.jpg', '.png', '.cpp', '.hpp'}
    CODE_EXTENSIONS = {'.cpp', '.hpp', '.sqf'}

    def __init__(self, cache_dir: Path, pbo_timeout: int = 30):
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True)
        self.cache_dir = cache_dir
        self.pbo_timeout = pbo_timeout
        self._executor: Optional[ThreadPoolExecutor] = None
        self._executor_lock = threading.Lock()
        self._file_count = 0
        self._max_workers = max(1, (os.cpu_count() or 2) - 1)
        self._progress_callback: Optional[Callable[[str, float], None]] = None
        self._temp_dir: Optional[Path] = None

        self.pbo_extractor = PboExtractor(timeout=pbo_timeout)

        self.engines: List[ScannerEngine] = [
            PBOScannerEngine(self.pbo_extractor),
            RegularFileScannerEngine(self.VALID_EXTENSIONS)
        ]

    @property
    def progress_callback(self) -> Optional[Callable[[str, float], None]]:
        return self._progress_callback

    @progress_callback.setter
    def progress_callback(self, callback: Optional[Callable[[str, float], None]]) -> None:
        self._progress_callback = callback
        for engine in self.engines:
            engine.progress_callback = callback

    def __del__(self) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Clean up thread pool and temporary resources"""
        with self._executor_lock:
            if self._executor:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
        self.pbo_extractor.cleanup()

    def _get_temp_dir(self) -> Path:
        """Get or create temporary directory"""
        if not self._temp_dir:
            self._temp_dir = Path(tempfile.mkdtemp(prefix='asset_scanner_'))
        if not self._temp_dir:
            raise RuntimeError("Failed to create temporary directory")
        return self._temp_dir

    def scan_directory(self, path: Path, patterns: Optional[List[Pattern]] = None, max_files: Optional[int] = None, pbo_limit: Optional[int] = None) -> ScanResult:
        """Scan directory for assets with proper cleanup

        Args:
            path: Directory to scan
            patterns: Optional list of patterns to match
            max_files: Maximum number of files to scan
            pbo_limit: Maximum number of PBO files to scan
        """
        try:
            total_files = sum(1 for _ in path.rglob('*') if _.is_file())
            processed = 0

            if self.progress_callback:
                self.progress_callback(f"Scanning directory: {path}", 0.0)

            with self._executor_lock:
                if not self._executor:
                    self._executor = ThreadPoolExecutor(
                        max_workers=self._max_workers,
                        thread_name_prefix="scanner"
                    )

            self._file_count = 0
            assets = set()
            futures: List[concurrent.futures.Future] = []
            pbo_count = 0

            for file_path in path.rglob('*'):
                if not file_path.is_file():
                    continue

                if self.progress_callback:
                    processed += 1
                    self.progress_callback(str(file_path), processed / total_files)

                if file_path.suffix.lower() == '.pbo':
                    if pbo_limit and pbo_count >= pbo_limit:
                        continue
                    pbo_count += 1

                if max_files and self._file_count >= max_files:
                    break

                if patterns and not any(p.match(str(file_path)) for p in patterns):
                    continue

                self._file_count += 1
                future = self._executor.submit(self._scan_file, file_path)
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        if result.assets:
                            assets.update(result.assets)
                except Exception as e:
                    logger.error(f"Error processing file: {e}")

            return ScanResult(
                assets=assets,
                scan_time=datetime.now()
            )

        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"Error scanning directory: {path} - {e}", 1.0)
            logger.error(f"Scan error: {e}")
            self.cleanup()
            raise

    def _normalize_path(self, path: str | Path, prefix: Optional[str] = None, source: Optional[str] = None) -> Optional[Path]:
        """Normalize any path to consistent format."""
        try:
            clean_path = str(path).strip().replace('\\', '/').strip('/')

            if not clean_path or clean_path in {'texHeaders.bin', 'config.bin', 'userkeys.hpp'}:
                return None

            parts = []

            if prefix:
                parts.append(prefix.strip().replace('\\', '/').strip('/'))
            elif source:
                parts.append(source.strip('@'))

            if clean_path:
                if clean_path.startswith('addons/'):
                    clean_path = clean_path[7:]
                parts.append(clean_path)

            final_path = '/'.join(p for p in parts if p)
            return Path(final_path)

        except Exception as e:
            logger.debug(f"Path normalization failed: {path} ({e})")
            return None

    def _scan_regular_file(self, file_path: Path, base_path: Path) -> Optional[Asset]:
        """Process a regular file"""
        try:
            relative_path = file_path.relative_to(base_path)
            source = base_path.name

            clean_path = str(relative_path).replace('\\', '/')

            if not clean_path.startswith(f"{source}/"):
                clean_path = f"{source}/{clean_path}"

            return Asset(
                path=Path(clean_path),
                source=source,
                last_scan=datetime.now(),
                has_prefix=False,
                pbo_path=None
            )

        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            return None

    def scan_pbo(self, pbo_path: Path, extract_classes: bool = True, file_limit: Optional[int] = None) -> Tuple[ScanResult, Optional[Dict[str, str]]]:
        """Extract information from a PBO file."""
        try:
            if self.progress_callback:
                self.progress_callback(f"Scanning PBO: {pbo_path}", 0.0)

            source = pbo_path.parent.parent.name.strip('@')
            logger.debug(f"Scanning PBO {pbo_path.name} from source {source}")

            _, stdout, _ = self.pbo_extractor.list_contents(pbo_path)
            prefix = self.pbo_extractor.extract_prefix(stdout)
            logger.debug(f"Found prefix: {prefix}")

            returncode, code_files, all_paths = self.pbo_extractor.scan_pbo_contents(pbo_path)
            if returncode != 0:
                logger.error(f"PBO scan failed with code {returncode}")
                return (ScanResult(assets=set(), scan_time=datetime.now(), prefix=prefix or "", source=source), None)

            class_definitions = None
            if extract_classes and code_files:
                try:
                    # TODO
                    print (code_files)
                except Exception as e:
                    logger.error(f"Class extraction failed: {e}")

            assets = set()
            current_time = datetime.now()
            asset_extensions = {'.p3d', '.paa', '.jpg', '.png', '.wss', '.ogg', '.rtm'}

            processed_paths = 0
            for path in all_paths:
                if file_limit and processed_paths >= file_limit:
                    break

                path_lower = path.lower()

                if not any(path_lower.endswith(ext) for ext in asset_extensions):
                    continue

                if not path:
                    continue

                path_parts = []

                if prefix:
                    path_parts.append(prefix.strip().replace('\\', '/').strip('/'))

                clean_path = str(path).replace('\\', '/').strip('/')
                if clean_path:
                    if prefix and clean_path.startswith(prefix):
                        clean_path = clean_path[len(prefix):].strip('/')
                    path_parts.append(clean_path)

                final_path = '/'.join(p for p in path_parts if p)

                assets.add(Asset(
                    path=Path(final_path),
                    source=source,
                    last_scan=current_time,
                    has_prefix=True,
                    pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                ))
                processed_paths += 1

            result = ScanResult(
                assets=assets,
                scan_time=current_time,
                prefix=prefix or "",
                source=source
            )

            return (result, class_definitions)

        except Exception as e:
            logger.error(f"PBO scanning error: {pbo_path} - {e}")
            return (ScanResult(assets=set(), scan_time=datetime.now(), prefix="", source=source), None)

    def _scan_pbo(self, pbo_path: Path) -> Set[Asset]:
        """Internal PBO scanning implementation"""
        return self.scan_pbo(pbo_path)[0].assets

    def read_pbo_code(self, pbo_path: Path) -> Dict[str, str]:
        """Extract and read code files from PBO"""
        return self.pbo_extractor.extract_code_files(pbo_path, self.CODE_EXTENSIONS)

    def _scan_file(self, file_path: Path) -> Optional[ScanResult]:
        """Scan a single file using appropriate engine"""
        for engine in self.engines:
            if engine.supports_file(file_path):
                return engine.scan_file(file_path)
        return None
