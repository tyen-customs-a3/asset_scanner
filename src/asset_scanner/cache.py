import logging
from typing import Dict, Set, Optional
from pathlib import Path
from datetime import datetime, timedelta

from .models import Asset

class AssetCache:
    """Simple in-memory cache for asset data"""
    
    def __init__(self, max_cache_size: int = 1_000_000):
        self._assets: Dict[str, Asset] = {}
        self.max_cache_size = max_cache_size
        self._last_updated = datetime.now()
        self._max_age = timedelta(hours=1)
        self._logger = logging.getLogger(__name__)

    def add_assets(self, assets: Dict[str, Asset]) -> None:
        """Add or update assets in cache"""
        if len(assets) > self.max_cache_size:
            raise ValueError(f"Cache size exceeded: {len(assets)} > {self.max_cache_size}")
            
        # Update existing assets or add new ones
        for path, asset in assets.items():
            normalized_path = str(path).replace('\\', '/')
            self._assets[normalized_path] = asset
            
        self._last_updated = datetime.now()
        self._logger.debug(f"Cache updated with {len(assets)} assets")

    def get_asset(self, path: str | Path, case_sensitive: bool = True) -> Optional[Asset]:
        """Get asset by path"""
        path_str = str(path).replace('\\', '/')
        
        if case_sensitive:
            return self._assets.get(path_str)
        
        path_lower = path_str.lower()
        for stored_path, asset in self._assets.items():
            if stored_path.lower() == path_lower:
                return asset
        return None

    def get_assets_by_source(self, source: str) -> Set[Asset]:
        """Get all assets from a specific source"""
        clean_source = source.strip('@')
        return {
            asset for asset in self._assets.values()
            if asset.source.strip('@') == clean_source
        }

    def get_assets_by_extension(self, extension: str) -> Set[Asset]:
        """Get assets by file extension"""
        ext = extension.lower()
        if not ext.startswith('.'):
            ext = f'.{ext}'
            
        return {
            asset for asset in self._assets.values()
            if asset.path.suffix.lower() == ext
        }

    def find_duplicates(self) -> Dict[str, Set[Asset]]:
        """Find assets with duplicate filenames"""
        by_name: Dict[str, Set[Asset]] = {}
        
        for asset in self._assets.values():
            name = asset.path.name
            if name not in by_name:
                by_name[name] = set()
            by_name[name].add(asset)

        return {
            name: assets 
            for name, assets in by_name.items() 
            if len(assets) > 1
        }

    def get_all_assets(self) -> Set[Asset]:
        """Get all cached assets"""
        return set(self._assets.values())

    def get_sources(self) -> Set[str]:
        """Get all unique asset sources"""
        return {asset.source for asset in self._assets.values()}

    def is_valid(self) -> bool:
        """Check if cache is still valid"""
        return datetime.now() - self._last_updated < self._max_age

    def clear(self) -> None:
        """Clear the cache"""
        self._assets.clear()
        self._last_updated = datetime.now()
