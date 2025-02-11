"""Cache management and direct cache interaction tests"""
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import json
from asset_scanner.cache import AssetCache
from asset_scanner.models import Asset

@pytest.fixture
def sample_assets(tmp_path: Path) -> dict[str, Asset]:
    """Create sample assets for testing"""
    now = datetime.now()
    return {
        "asset1": Asset(
            path=Path("@mod1/addons/weapon1.p3d"),
            source="@mod1",
            last_scan=now
        ),
        "asset2": Asset(
            path=Path("@mod1/addons/texture1.paa"),
            source="@mod1",
            last_scan=now
        ),
        "asset3": Asset(
            path=Path("@mod2/addons/weapon2.p3d"),
            source="@mod2",
            last_scan=now
        )
    }

def test_cache_basic_operations(sample_assets: dict[str, Asset]) -> None:
    """Test basic cache operations"""
    cache = AssetCache()
    
    # Test adding assets
    cache.add_assets({str(a.path): a for a in sample_assets.values()})
    assert len(cache.get_all_assets()) == len(sample_assets)
    
    # Test retrieving specific asset
    asset = cache.get_asset("@mod1/addons/weapon1.p3d")
    assert asset == sample_assets["asset1"]
    
    # Test clearing cache
    cache.clear()
    assert len(cache.get_all_assets()) == 0

def test_cache_persistence(tmp_path: Path, sample_assets: dict[str, Asset]) -> None:
    """Test cache save/load operations"""
    cache_file = tmp_path / "test_cache.json"
    cache = AssetCache()
    
    # Add and save assets
    cache.add_assets({str(a.path): a for a in sample_assets.values()})
    cache.save_to_disk(cache_file)
    
    # Load in new cache instance
    new_cache = AssetCache.load_from_disk(cache_file)
    assert len(new_cache.get_all_assets()) == len(sample_assets)
    
    # Verify loaded assets match original
    for asset in sample_assets.values():
        loaded = new_cache.get_asset(str(asset.path))
        assert loaded == asset

def test_cache_source_isolation(sample_assets: dict[str, Asset]) -> None:
    """Test asset source separation"""
    cache = AssetCache()
    cache.add_assets({str(a.path): a for a in sample_assets.values()})
    
    mod1_assets = cache.get_assets_by_source("@mod1")
    mod2_assets = cache.get_assets_by_source("@mod2")
    
    assert len(mod1_assets) == 2
    assert len(mod2_assets) == 1
    assert not mod1_assets.intersection(mod2_assets)

def test_cache_validity() -> None:
    """Test cache validity timing"""
    cache = AssetCache()
    assert cache.is_valid()
    
    # Force cache to be old
    cache._last_updated = datetime.now() - timedelta(hours=2)
    assert not cache.is_valid()

def test_cache_size_limit() -> None:
    """Test cache size limitations"""
    cache = AssetCache(max_cache_size=2)
    assets = {
        f"asset{i}": Asset(
            path=Path(f"@mod/asset{i}.paa"),
            source="@mod",
            last_scan=datetime.now()
        ) for i in range(3)
    }
    
    with pytest.raises(ValueError, match="Cache size exceeded"):
        cache.add_assets({str(a.path): a for a in assets.values()})

def test_cache_duplicate_detection(sample_assets: dict[str, Asset]) -> None:
    """Test finding duplicate assets"""
    cache = AssetCache()
    
    # Add duplicate asset with different source
    assets = dict(sample_assets)
    assets["duplicate"] = Asset(
        path=Path("@mod3/addons/weapon1.p3d"),  # Same filename as asset1
        source="@mod3",
        last_scan=datetime.now()
    )
    
    cache.add_assets({str(a.path): a for a in assets.values()})
    duplicates = cache.find_duplicates()
    
    assert "weapon1.p3d" in duplicates
    assert len(duplicates["weapon1.p3d"]) == 2

def test_cache_invalid_file(tmp_path: Path) -> None:
    """Test handling of corrupted cache file"""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("invalid json content")
    
    cache = AssetCache.load_from_disk(invalid_file)
    assert len(cache.get_all_assets()) == 0

def test_cache_serialization(sample_assets: dict[str, Asset]) -> None:
    """Test cache serialization format"""
    cache = AssetCache()
    cache.add_assets({str(a.path): a for a in sample_assets.values()})
    
    data = cache.to_serializable()
    
    assert "assets" in data
    assert "last_updated" in data
    assert "max_age_seconds" in data
    assert "max_cache_size" in data
    assert len(data["assets"]) == len(sample_assets)
