from typing import Dict, Set, Optional, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from pathlib import Path
from datetime import datetime
from .models import Asset

@dataclass(frozen=True)
class AssetCache:
    """Immutable cache container for asset data."""
    assets: Mapping[str, Asset] = field(default_factory=dict)
    paths_lower: Mapping[str, str] = field(default_factory=dict)
    categories: Mapping[str, frozenset[str]] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)
    extension_index: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Convert mutable collections to immutable ones after initialization."""
        object.__setattr__(self, 'assets', MappingProxyType(dict(self.assets)))
        object.__setattr__(self, 'paths_lower', MappingProxyType(dict(self.paths_lower)))
        object.__setattr__(self, 'categories', MappingProxyType(dict(self.categories)))
        object.__setattr__(self, 'extension_index', MappingProxyType(dict(self.extension_index)))

    @classmethod
    def create_bulk(cls, assets: Dict[str, Asset]) -> 'AssetCache':
        """Create a new cache instance with bulk data."""
        # Group assets by category
        categories: Dict[str, Set[str]] = {}
        extension_index: Dict[str, Set[str]] = {}
        
        for path, asset in assets.items():
            # Group by source/category
            if asset.source not in categories:
                categories[asset.source] = set()
            categories[asset.source].add(path)
            
            # Group by extension
            ext = asset.path.suffix.lower()
            if ext not in extension_index:
                extension_index[ext] = set()
            extension_index[ext].add(path)

        return cls(
            assets=assets,
            paths_lower={k.lower(): k for k in assets.keys()},
            categories={k: frozenset(v) for k, v in categories.items()},
            extension_index={k: frozenset(v) for k, v in extension_index.items()},
            last_updated=datetime.now()
        )

class AssetCacheManager:
    """Manages caching of scanned assets with thread-safe access."""
    
    def __init__(self, max_size: int = 1_000_000) -> None:
        self._cache: Optional[AssetCache] = None
        self._max_cache_age = 3600  # 1 hour in seconds
        self._max_size = max_size

    def add_assets(self, assets: Dict[str, Asset]) -> None:
        """Bulk add or update assets in cache."""
        if len(assets) > self._max_size:
            raise ValueError(f"Cache size exceeded: {len(assets)} > {self._max_size}")
        self._cache = AssetCache.create_bulk(assets)

    def is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache:
            return False
        return (datetime.now() - self._cache.last_updated).seconds < self._max_cache_age

    def get_asset(self, path: str | Path, case_sensitive: bool = True) -> Optional[Asset]:
        """Get asset by path."""
        if not self._cache:
            return None
            
        path_str = str(path).replace('\\', '/')
        if not case_sensitive:
            path_str = path_str.lower()
            for orig_path, asset in self._cache.assets.items():
                if str(orig_path).replace('\\', '/').lower() == path_str:
                    return asset
            return None
        return self._cache.assets.get(path_str)

    def get_assets_by_source(self, source: str) -> Set[Asset]:
        """Get all assets from a specific source."""
        if not self._cache:
            return set()
            
        # Handle source with or without @ prefix
        clean_source = source.strip('@')
        matching_sources = {
            s for s in self._cache.categories.keys() 
            if s.strip('@') == clean_source
        }
        
        assets = set()
        for s in matching_sources:
            assets.update(self._cache.assets[path] for path in self._cache.categories[s])
        return assets

    def get_assets_by_extension(self, extension: str) -> Set[Asset]:
        """Get assets by extension using indexed lookup."""
        if not self._cache:
            return set()
            
        ext = extension.lower()
        if ext not in self._cache.extension_index:
            return set()
            
        return {self._cache.assets[path] for path in self._cache.extension_index[ext]}

    def find_duplicates(self) -> Dict[str, Set[Asset]]:
        """Find duplicate assets by comparing normalized paths."""
        if not self._cache:
            return {}

        # Group by filename
        by_name: Dict[str, Set[Asset]] = {}
        
        for asset in self._cache.assets.values():
            name = asset.path.name
            if name not in by_name:
                by_name[name] = set()
            by_name[name].add(asset)

        # Return only groups with duplicates
        return {
            name: assets 
            for name, assets in by_name.items() 
            if len(assets) > 1
        }

    def get_all_assets(self) -> Set[Asset]:
        """Get all cached assets."""
        return set(self._cache.assets.values()) if self._cache else set()

    def get_sources(self) -> Set[str]:
        """Get all unique asset sources."""
        return set(self._cache.categories.keys()) if self._cache else set()
