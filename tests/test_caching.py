"""Cache management and in-memory cache tests"""
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import time
from asset_scanner import AssetAPI
from asset_scanner.config import APIConfig
from asset_scanner.models import Asset


@pytest.fixture
def mod_structure(tmp_path: Path) -> Path:
    base = tmp_path / "mods"
    base.mkdir()

    mods: dict[str, list[str]] = {
        "@mod1": [
            "addons/weapon1.p3d",
            "addons/texture1.paa",
            "addons/script1.sqf"
        ],
        "@mod2": [
            "addons/weapon2.p3d",
            "addons/texture2.paa"
        ],
        "@mod3": [
            "addons/shared.paa",
            "addons/unique3.paa"
        ]
    }

    for mod, files in mods.items():
        mod_dir = base / mod
        mod_dir.mkdir()
        for file in files:
            file_path = mod_dir / file
            file_path.parent.mkdir(exist_ok=True)
            file_path.write_text(f"content for {file}")

    return base


def test_cache_memory_storage(mod_structure: Path, tmp_path: Path) -> None:
    """Test in-memory cache storage"""
    api = AssetAPI()
    
    result1 = api.scan(mod_structure)
    assets1 = {str(a.path) for a in result1.assets}
    
    # Create new API instance (should have empty cache)
    api2 = AssetAPI()
    assert len(api2.get_all_assets()) == 0, "New API instance should have empty cache"

def test_cache_max_age(mod_structure: Path) -> None:
    """Test cache invalidation by age"""
    api = AssetAPI()
    result = api.scan(mod_structure)
    
    # Force cache to be old by modifying last_updated
    api._cache._last_updated = datetime.now() - timedelta(hours=2)
    
    assert not api._cache.is_valid(), "Cache should be invalid after max age"

def test_cache_update(mod_structure: Path) -> None:
    """Test cache updates when adding new assets"""
    api = AssetAPI()
    
    # Initial scan
    result1 = api.scan(mod_structure)
    initial_count = len(result1.assets)
    
    # Add new file
    new_file = mod_structure / "@mod1" / "addons" / "new_asset.paa"
    new_file.parent.mkdir(exist_ok=True)
    new_file.write_text("new content")
    
    # Rescan
    result2 = api.scan(mod_structure)
    assert len(result2.assets) == initial_count + 1, "Cache should include new asset"

def test_cache_source_isolation(mod_structure: Path) -> None:
    """Test that assets from different sources don't interfere"""
    api = AssetAPI()
    
    # Scan first mod
    mod1_path = mod_structure / "@mod1"
    result1 = api.scan(mod1_path)
    mod1_assets = len(result1.assets)
    
    # Scan second mod
    mod2_path = mod_structure / "@mod2"
    result2 = api.scan(mod2_path)
    
    # Check that assets from both mods are preserved
    assert len(api.get_assets_by_source("@mod1")) == mod1_assets
    assert len(api.get_assets_by_source("@mod2")) > 0

def test_cache_clear(mod_structure: Path) -> None:
    """Test cache clearing"""
    api = AssetAPI()
    
    api.scan(mod_structure)
    assert len(api.get_all_assets()) > 0
    
    api.clear_cache()
    assert len(api.get_all_assets()) == 0
    
    # Verify new scans work after clearing
    result = api.scan(mod_structure)
    assert len(result.assets) > 0

def test_cache_size_limit(mod_structure: Path) -> None:
    """Test cache size limits"""
    small_cache_size = 2
    api = AssetAPI(config=APIConfig(max_cache_size=small_cache_size))
    
    with pytest.raises(ValueError, match="Cache size exceeded"):
        api.scan(mod_structure)
