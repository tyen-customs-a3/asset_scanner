import logging
import re
from typing import Any, Dict, List, Optional, Set, Pattern
from pathlib import Path
from datetime import datetime
import threading

from .models import Asset, ScanResult
from .cache import AssetCache
from .config import APIConfig
from .pbo_extractor import PboExtractor
from .scanner_parallel import ParallelScanner


class AssetAPI:
    """Main API for asset scanning and caching"""

    def __init__(self, config: Optional[APIConfig] = None):
        self._logger = logging.getLogger(__name__)
        self.config = config or APIConfig()
        self._stats_lock = threading.Lock()
        self._pbo_extractor = PboExtractor()
        self._cache = AssetCache(max_cache_size=self.config.max_cache_size)
        self._scanner = ParallelScanner(
            self._pbo_extractor,
            max_workers=self.config.max_workers
        )

    @property
    def cache_file(self) -> Optional[Path]:
        """Get configured cache file path"""
        return self.config.cache_file

    def save_cache(self, path: Optional[Path] = None) -> None:
        """Manually save cache to disk"""
        save_path = path or self.config.cache_file
        if not save_path:
            self._logger.warning("No cache file configured for save operation")
            return
        try:
            self._cache.save_to_disk(save_path)
        except Exception as e:
            self._handle_error(e, "manual cache save failed")

    def load_cache(self) -> bool:
        """Load cache from configured file"""
        if not self.config.cache_file:
            self._logger.warning("No cache file configured for load operation")
            return False

        try:
            loaded_cache = AssetCache.load_from_disk(self.config.cache_file)
            assets = loaded_cache.get_all_assets()
            if not assets:
                self._logger.warning(f"No assets found in cache file {self.config.cache_file}")
                return False

            self._cache.add_assets({str(a.path): a for a in assets})
            self._logger.debug(f"Loaded {len(assets)} assets from {self.config.cache_file}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to load cache: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear the cache without auto-saving"""
        self._cache.clear()

    def is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        return self._cache.is_valid()

    def _save_cache(self) -> None:
        """Save cache to disk if configured"""
        self.save_cache(self.config.cache_file)

    def scan(self, root_path: Path, patterns: Optional[List[Pattern]] = None) -> ScanResult:
        """Scan for assets without auto-saving"""
        try:
            if not root_path.exists():
                raise FileNotFoundError(f"Directory not found: {root_path}")

            self._logger.info(f"Starting scan of {root_path}")
            source = root_path.name.lstrip('@')  # Normalize source name
            paths_to_scan = self._get_scannable_paths(root_path)

            # Keep track of existing assets from other sources
            other_source_assets = {
                str(a.path): a for a in self._cache.get_all_assets()
                if Asset.normalize_source(a.source) != source
            }

            self._logger.debug(f"Preserved {len(other_source_assets)} existing assets from other sources")
            self._logger.debug(f"Existing asset sources: {set(a.source for a in other_source_assets.values())}")

            # Scan for new assets 
            scan_results = self._scanner.scan_directories(paths_to_scan, source)

            # Collect all new assets from this scan, ensuring proper source prefixing
            new_assets = set()
            for result in scan_results:
                for asset in result.assets:
                    # Ensure asset paths are properly prefixed with source
                    asset_path = str(asset.path)
                    if not asset_path.startswith(f"{source}/"):
                        asset_path = f"{source}/{asset_path}"
                    new_assets.add(Asset(
                        path=Path(asset_path),
                        source=source,
                        last_scan=asset.last_scan,
                        has_prefix=asset.has_prefix,
                        pbo_path=asset.pbo_path
                    ))

            self._logger.debug(f"Added {len(new_assets)} new assets from {source}")

            # Update cache with both existing and new assets
            all_assets = dict(other_source_assets)
            for asset in new_assets:
                all_assets[str(asset.path)] = asset

            self._logger.debug(f"Updating cache with {len(all_assets)} total assets")
            self._cache.add_assets(all_assets)

            return ScanResult(
                assets=new_assets,
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

        paths.append(root)

        return paths

    def _scan_parallel(self, paths: List[Path], source: str,
                       patterns: Optional[List[Pattern]] = None) -> List[ScanResult]:
        """Perform parallel scanning of directories."""
        self._logger.debug(f"Starting parallel scan of {len(paths)} directories for assets from {source}")

        try:
            scanner = ParallelScanner(
                self._scanner.pbo_extractor,
                max_workers=self.config.max_workers or 4
            )

            return scanner.scan_directories(paths, source)

        except Exception as e:
            self._handle_error(e, "parallel scan failed")
            raise

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

    def _handle_error(self, error: Exception, context: str = "") -> None:
        if self.config and self.config.error_handler:
            try:
                self.config.error_handler(error)
            except Exception as e:
                self._logger.error(f"Error handler failed: {e}")
                return

        self._logger.error(f"Error in {context}: {error}")

    def cleanup(self) -> None:
        print("Cleanup")

    def shutdown(self) -> None:
        try:
            self.cleanup()
            self._cache = AssetCache(self.config.max_cache_size)
            self._logger.info("AssetAPI shutdown complete")
        except Exception as e:
            self._handle_error(e, "shutdown")
