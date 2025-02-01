import os
from pathlib import Path
import shutil
import tempfile
from typing import Set, Dict, Optional, List, Pattern
from datetime import datetime
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .asset_models import Asset, ScanResult
from .class_models import UnprocessedClasses
from .pbo_extractor import PboExtractor
from .scanner_engine import ScannerEngine, PBOScannerEngine, RegularFileScannerEngine
from .class_parser import ClassParser

logger = logging.getLogger(__name__)

class AssetScanner:
    """Asset scanner for game content"""
    
    VALID_EXTENSIONS = {'.p3d', '.paa', '.sqf', '.pbo', '.wss', '.ogg', '.jpg', '.png', '.cpp', '.hpp'}
    CODE_EXTENSIONS = {'.cpp', '.hpp', '.sqf'}  # Add this line
    
    def __init__(self, cache_dir: Path, pbo_timeout: int = 30):
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True)
        self.cache_dir = cache_dir
        self.pbo_timeout = pbo_timeout
        self._executor = None
        self._executor_lock = threading.Lock()
        self._file_count = 0
        self._max_workers = max(1, (os.cpu_count() or 2) - 1)
        self.progress_callback = None  # Add this line
        self._temp_dir = None
        
        # Initialize components in correct order
        self.pbo_extractor = PboExtractor(timeout=pbo_timeout)
        self.class_parser = ClassParser()  # Add this line
        
        # Initialize scanner engines
        self.engines: List[ScannerEngine] = [
            PBOScannerEngine(self.pbo_extractor, self.class_parser),
            RegularFileScannerEngine(self.VALID_EXTENSIONS)
        ]

    def __del__(self):
        self.cleanup()

    def cleanup(self):
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
        return self._temp_dir

    def scan_directory(self, path: Path, patterns: Optional[List[Pattern]] = None, max_files: Optional[int] = None) -> ScanResult:
        """Scan directory for assets with proper cleanup"""
        try:
            with self._executor_lock:
                if not self._executor:
                    self._executor = ThreadPoolExecutor(
                        max_workers=self._max_workers,
                        thread_name_prefix="scanner"
                    )
                    
            self._file_count = 0
            assets = set()
            futures = []

            # Collect all files first
            for file_path in path.rglob('*'):
                if not file_path.is_file():
                    continue
                
                if self.progress_callback:
                    self.progress_callback(str(file_path))
                    
                if max_files and self._file_count >= max_files:
                    break

                # Skip files that don't match patterns
                if patterns and not any(p.match(str(file_path)) for p in patterns):
                    continue

                # Use engines for scanning
                result = self._scan_file(file_path)
                if result:
                    assets.update(result.assets)
                
                self._file_count += 1

            # Process results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        if isinstance(result, set):
                            assets.update(result)
                        else:
                            assets.add(result)
                except Exception as e:
                    logger.error(f"Error processing file: {e}")

            return ScanResult(
                assets=assets,
                scan_time=datetime.now()
            )

        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.cleanup()
            raise

    def _normalize_path(self, path: str | Path, prefix: Optional[str] = None, source: Optional[str] = None) -> Optional[Path]:
        """Normalize any path to consistent format."""
        try:
            clean_path = str(path).strip().replace('\\', '/').strip('/')
            
            # Skip invalid paths
            if not clean_path or clean_path in {'texHeaders.bin', 'config.bin', 'userkeys.hpp'}:
                return None

            parts = []
            
            # Handle prefix/source
            if prefix:
                parts.append(prefix.strip().replace('\\', '/').strip('/'))
            elif source:
                parts.append(source.strip('@'))
                
            # Add remaining path
            if clean_path:
                # Remove addons/ prefix if present
                if clean_path.startswith('addons/'):
                    clean_path = clean_path[7:]
                parts.append(clean_path)
                
            # Join and normalize
            final_path = '/'.join(p for p in parts if p)
            return Path(final_path)
            
        except Exception as e:
            logger.debug(f"Path normalization failed: {path} ({e})")
            return None

    def _scan_regular_file(self, file_path: Path, base_path: Path) -> Optional[Asset]:
        """Process a regular file"""
        try:
            # Get relative path from base directory
            relative_path = file_path.relative_to(base_path)
            source = base_path.name
            
            # Include source in path for non-PBO files
            clean_path = str(relative_path).replace('\\', '/')
            
            # Ensure path includes source name
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

    def scan_pbo(self, pbo_path: Path, extract_classes: bool = True) -> ScanResult:
        """Extract information from a PBO file."""
        try:
            if self.progress_callback:
                self.progress_callback(str(pbo_path))
                
            source = pbo_path.parent.parent.name.strip('@')
            logger.debug(f"Scanning PBO {pbo_path.name} from source {source}")
            
            # Get prefix first
            _, stdout, _ = self.pbo_extractor.list_contents(pbo_path)
            prefix = self.pbo_extractor.extract_prefix(stdout)
            logger.debug(f"Found prefix: {prefix}")
            
            # Then scan contents with known prefix
            returncode, code_files, all_paths = self.pbo_extractor.scan_pbo_contents(pbo_path)
            if returncode != 0:
                logger.error(f"PBO scan failed with code {returncode}")
                return ScanResult(assets=set(), scan_time=datetime.now(), prefix=prefix, source=source)

            # Process assets - only include asset files, not code files
            assets = set()
            current_time = datetime.now()
            asset_extensions = {'.p3d', '.paa', '.jpg', '.png', '.wss', '.ogg', '.rtm'}  # Added .rtm

            logger.debug(f"\nProcessing {len(all_paths)} paths from PBO:")
            logger.debug(f"Looking for extensions: {sorted(asset_extensions)}")

            for path in all_paths:
                path_lower = path.lower()
                
                # Skip non-asset files
                if not any(path_lower.endswith(ext) for ext in asset_extensions):
                    logger.debug(f"Skipping non-asset file: {path}")
                    continue
                    
                # Skip empty or invalid paths
                if not path:
                    logger.debug("Skipping empty path")
                    continue
                    
                # Create asset
                logger.debug(f"Adding asset: {path}")
                assets.add(Asset(
                    path=Path(path),
                    source=source,
                    last_scan=current_time,
                    has_prefix=True,
                    pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                ))

            logger.debug(f"\nFound {len(assets)} assets:")
            for asset in sorted(assets, key=lambda x: str(x.path)):
                logger.debug(f"  {asset.path}")

            return ScanResult(
                assets=assets, 
                scan_time=current_time,
                prefix=prefix,
                source=source
            )
            
        except Exception as e:
            logger.error(f"PBO scanning error: {pbo_path} - {e}")
            return ScanResult(assets=set(), scan_time=datetime.now(), prefix=None, source=source)

    def _scan_pbo(self, pbo_path: Path) -> Set[Asset]:
        """Internal PBO scanning implementation"""
        return self.scan_pbo(pbo_path).assets

    def read_pbo_code(self, pbo_path: Path) -> Dict[str, str]:
        """Extract and read code files from PBO"""
        return self.pbo_extractor.extract_code_files(pbo_path, self.CODE_EXTENSIONS)
    
    def _scan_file(self, file_path: Path) -> Optional[ScanResult]:
        """Scan a single file using appropriate engine"""
        for engine in self.engines:
            if engine.supports_file(file_path):
                return engine.scan_file(file_path)
        return None
