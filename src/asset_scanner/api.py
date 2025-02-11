import logging
import re
from typing import Any, Dict, List, Optional, Set, Pattern
from pathlib import Path
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from .models import Asset, ScanResult
from .cache import AssetCacheManager
from .config import APIConfig
from .pbo_extractor import PboExtractor
from .scanner_parallel import ParallelScanner

class AssetAPI:
    """Simplified main API"""
    
    def __init__(self, cache_dir: Path, config: Optional[APIConfig] = None):
        self.config = config or APIConfig()
        self._cache = AssetCacheManager(max_size=self.config.cache_max_size)
        self._logger = logging.getLogger(__name__)
        self._stats_lock = threading.Lock()
        self._pbo_extractor = PboExtractor()
        self._scanner = ParallelScanner(
            self._pbo_extractor,
            max_workers=self.config.max_workers
        )

    def scan(self, root_path: Path, patterns: Optional[List[Pattern]] = None) -> ScanResult:
        """Simplified scanning method"""
        try:
            if not root_path.exists():
                raise FileNotFoundError(f"Directory not found: {root_path}")

            self._logger.info(f"Starting scan of {root_path}")
            source = root_path.name
            paths_to_scan = self._get_scannable_paths(root_path)
            
            # Get existing assets, but separate current source assets
            existing_assets = {
                str(a.path): a for a in self._cache.get_all_assets()
                if a.source != source  # Only keep assets from other sources
            }
            
            self._logger.debug(f"Preserved {len(existing_assets)} existing assets from other sources")
            self._logger.debug(f"Existing asset sources: {set(a.source for a in existing_assets.values())}")
            
            # Perform scan
            scan_results = self._scanner.scan_directories(paths_to_scan, source)
            
            # Add new assets while preserving existing ones from other sources
            all_assets = dict(existing_assets)  # Start with existing assets from other sources
            
            # Add newly scanned assets
            new_asset_count = 0
            for result in scan_results:
                for asset in result.assets:
                    asset_key = str(asset.path)
                    # Only update if from current source or not present
                    if asset_key not in all_assets:
                        all_assets[asset_key] = asset
                        new_asset_count += 1
                    elif all_assets[asset_key].source != asset.source:
                        self._logger.warning(
                            f"Asset collision: {asset_key} from {asset.source} "
                            f"conflicts with existing from {all_assets[asset_key].source}"
                        )
            
            self._logger.debug(f"Added {new_asset_count} new assets from {source}")
            
            # Update cache with complete set
            self._logger.debug(f"Updating cache with {len(all_assets)} total assets")
            self._cache.add_assets(all_assets)
            
            # Return only new/updated assets for this source
            current_assets = {
                asset for asset in all_assets.values() 
                if asset.source == source
            }
            
            self._logger.debug(f"Returning {len(current_assets)} assets for source {source}")
            
            return ScanResult(
                assets=current_assets,
                scan_time=datetime.now(),
                source=source,
                path=root_path
            )

        except Exception as e:
            self._handle_error(e, f"scan failed for {root_path}")
            raise

    def get_sources(self) -> Set[str]:
        """Get all unique asset sources."""
        return self._cache.get_sources()

    def _get_scannable_paths(self, root: Path) -> List[Path]:
        """Get all paths that should be scanned under root."""
        paths = []
        
        # Always include root for regular files
        paths.append(root)
            
        return paths

    def _scan_parallel(self, paths: List[Path], source: str, 
                      patterns: Optional[List[Pattern]] = None) -> List[ScanResult]:
        """Perform parallel scanning of directories."""
        self._logger.debug(f"Starting parallel scan of {len(paths)} directories")

        try:
            scanner = ParallelScanner(
                self._scanner.pbo_extractor,
                max_workers=self.config.max_workers or 4
            )

            return scanner.scan_directories(paths, source)

        except Exception as e:
            self._handle_error(e, "parallel scan failed")
            raise

    # Keep asset query methods public
    def get_asset(self, path: str | Path, case_sensitive: bool = False) -> Optional[Asset]:
        if isinstance(path, Path):
            path = str(path)

        path = path.replace('\\', '/').strip('/')
        if path.startswith('./'):
            path = path[2:]

        asset = self._cache.get_asset(path, case_sensitive)
        if asset:
            return asset

        for source in self.get_sources():
            prefixed_path = f"{source}/{path}"
            asset = self._cache.get_asset(prefixed_path, case_sensitive)
            if asset:
                return asset

        filename = path.split('/')[-1]
        for cached_asset in self.get_all_assets():
            if case_sensitive:
                if cached_asset.filename == filename:
                    return cached_asset
            else:
                if cached_asset.filename.lower() == filename.lower():
                    return cached_asset

        return None

    def get_all_assets(self) -> Set[Asset]:
        return self._cache.get_all_assets()

    def get_assets_by_source(self, source: str) -> Set[Asset]:
        if not source.startswith('@'):
            source = f"@{source}"
        return self._cache.get_assets_by_source(source)

    # Keep asset finding methods public
    def find_by_extension(self, extension: str) -> Set[Asset]:
        if not extension.startswith('.'):
            extension = f'.{extension}'

        extension = extension.lower()
        return {
            asset for asset in self.get_all_assets()
            if asset.path.suffix.lower() == extension
        }

    def find_by_pattern(self, pattern: str | Pattern) -> Set[Asset]:
        if isinstance(pattern, str):
            pattern = re.compile(pattern, re.IGNORECASE)

        assets = self.get_all_assets()
        matches = set()

        for asset in assets:
            path = str(asset.path).replace('\\', '/')
            if '/' in path:
                path = path.split('/', 1)[1] if path.startswith('@') else path

            if pattern.search(path):
                matches.add(asset)

        return matches

    def find_duplicates(self) -> Dict[str, Set[Asset]]:
        return self._cache.find_duplicates()

    def find_by_criteria(self, criteria: Dict[str, Any]) -> Set[Asset]:
        assets = self.get_all_assets()

        for key, value in criteria.items():
            if key == 'extension':
                assets &= self.find_by_extension(value)
            elif key == 'pattern':
                assets &= self.find_by_pattern(value)
            elif key == 'source':
                assets &= self.get_assets_by_source(value)

        return assets

    # Make cache management private
    def _handle_error(self, error: Exception, context: str = "") -> None:
        if self.config and self.config.error_handler:
            try:
                self.config.error_handler(error)
            except Exception as e:
                self._logger.error(f"Error handler failed: {e}")
                return

        self._logger.error(f"Error in {context}: {error}")

    def clear_cache(self) -> None:
        self._cache = AssetCacheManager(max_size=self.config.cache_max_size)

    def cleanup(self) -> None:
        print ("Cleanup")

    def shutdown(self) -> None:
        try:
            self.cleanup()
            self._cache = AssetCacheManager(self.config.cache_max_size)
            self._logger.info("AssetAPI shutdown complete")
        except Exception as e:
            self._handle_error(e, "shutdown")
