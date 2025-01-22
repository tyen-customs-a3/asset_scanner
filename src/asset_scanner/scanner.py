import os
from pathlib import Path
from typing import Set, Dict, Optional, List, Pattern
from datetime import datetime
import hashlib
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from .models import Asset, ScanResult

logger = logging.getLogger(__name__)

class AssetScanner:
    """Asset scanner for game content"""
    
    VALID_EXTENSIONS = {'.p3d', '.paa', '.sqf', '.pbo', '.wss', '.ogg', '.jpg', '.png'}
    
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

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        """Clean up thread pool resources"""
        with self._executor_lock:
            if self._executor:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None

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

                # Handle PBOs separately
                if file_path.suffix.lower() == '.pbo':
                    future = self._executor.submit(self._scan_pbo, file_path)
                else:
                    # Only process files with valid extensions
                    if file_path.suffix.lower() not in self.VALID_EXTENSIONS:
                        continue
                    future = self._executor.submit(self._scan_regular_file, file_path, path)
                
                futures.append(future)
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

    def _extract_prefix_from_pbo(self, stdout: str) -> Optional[str]:
        """Extract the prefix line from PBO output"""
        for line in stdout.splitlines():
            if line.startswith('prefix='):
                return line.split('=')[1].strip().replace('\\', '/').strip(';')
        return None

    def _scan_pbo(self, pbo_path: Path) -> Set[Asset]:
        """Extract asset information from PBO."""
        try:
            if self.progress_callback:
                self.progress_callback(str(pbo_path))
                
            source = pbo_path.parent.parent.name.strip('@')
            
            result = subprocess.run(
                ['extractpbo', '-LBP', str(pbo_path)], 
                capture_output=True, 
                text=True, 
                timeout=self.pbo_timeout  # Use configurable timeout
            )
            
            if result.returncode != 0:
                logger.error(f"PBO extraction failed: {pbo_path}")
                return set()

            # Extract and validate prefix
            prefix = self._extract_prefix_from_pbo(result.stdout)
            if not prefix:
                logger.warning(f"No prefix found in PBO: {pbo_path}")
                return set()

            assets = set()
            seen_paths = set()
            current_time = datetime.now()

            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith(('Active code page:', 'Opening ', 'prefix=', '==', '$')):
                    continue
                        
                if not any(line.endswith(ext) for ext in self.VALID_EXTENSIONS):
                    continue

                # Use consolidated path normalization
                normalized_path = self._normalize_path(line, prefix=prefix)
                if not normalized_path:
                    continue
                    
                path_key = str(normalized_path)
                if path_key in seen_paths:
                    continue

                seen_paths.add(path_key)
                assets.add(Asset(
                    path=normalized_path,
                    source=source,
                    last_scan=current_time,
                    has_prefix=bool(prefix and path_key.startswith(prefix)),
                    pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                ))

            return assets

        except subprocess.TimeoutExpired:
            logger.warning(f"PBO scanning timeout: {pbo_path}")
        except Exception as e:
            logger.error(f"PBO scanning error: {pbo_path} - {e}")
        
        return set()
