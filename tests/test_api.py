import pytest
from pathlib import Path
from asset_scanner import Asset, AssetAPI
from unittest.mock import Mock
from asset_scanner.config import APIConfig
import time
from datetime import datetime, timedelta

from tests.conftest import PBO_FILES


@pytest.fixture
def sample_assets(tmp_path: Path, test_data_dir: Path) -> Path:
    """Create sample asset directory structure using real test data"""
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir(parents=True)

    # Copy real PBO files from test data
    for pbo_name, pbo_data in PBO_FILES.items():
        # Create mod directory structure
        mod_dir = asset_dir / f"@{pbo_data['source']}"
        addon_dir = mod_dir / "addons"
        addon_dir.mkdir(parents=True, exist_ok=True)

        # Copy the actual PBO file
        src_pbo = pbo_data['path']
        dst_pbo = addon_dir / src_pbo.name
        if src_pbo.exists():
            dst_pbo.write_bytes(src_pbo.read_bytes())

    return asset_dir


@pytest.fixture
def api() -> AssetAPI:
    return AssetAPI()


def test_basic_scanning(api: AssetAPI, sample_assets: Path) -> None:
    """Test basic asset scanning functionality"""
    result = api.scan(sample_assets)
    assert result.assets
    assert all(isinstance(asset, Asset) for asset in result.assets)
    assert result.source == sample_assets.name


def test_error_handling(api: AssetAPI) -> None:
    """Test error handler configuration"""
    error_handler = Mock()
    config = APIConfig(error_handler=error_handler)
    api = AssetAPI(config=config)

    with pytest.raises(FileNotFoundError):
        api.scan(Path("nonexistent"))

    error_handler.assert_called_once()
    args = error_handler.call_args[0]
    assert isinstance(args[0], FileNotFoundError)


def test_asset_querying(api: AssetAPI, sample_assets: Path) -> None:
    """Test asset querying methods"""
    api.scan(sample_assets)
    
    # Test get_asset with known files from test data
    mirror_asset = api.get_asset("uniform/mirror.p3d")
    assert mirror_asset is not None
    assert mirror_asset.path.name == "mirror.p3d"
    
    # Test find_by_extension with known extensions
    p3d_assets = api.find_by_extension(".p3d")
    assert len(p3d_assets) > 0
    assert all(a.path.suffix == '.p3d' for a in p3d_assets)
    
    # Test find_by_pattern with real file patterns
    headband_assets = api.find_by_pattern(r"headband.*\.paa$")
    assert len(headband_assets) > 0
    assert all('headband' in str(a.path) for a in headband_assets)


def test_cache_persistence(api: AssetAPI, sample_assets: Path) -> None:
    """Test that cache persists between scans"""
    result1 = api.scan(sample_assets)
    assets1 = api.get_all_assets()
    
    result2 = api.scan(sample_assets)
    assets2 = api.get_all_assets()

    assert len(assets1) == len(assets2)
    assert {str(a.path) for a in assets1} == {str(a.path) for a in assets2}


def test_cleanup(api: AssetAPI, sample_assets: Path) -> None:
    """Test cleanup and shutdown"""
    api.scan(sample_assets)
    initial_assets = len(api.get_all_assets())
    assert initial_assets > 0
    
    api.clear_cache()
    assert len(api.get_all_assets()) == 0
    
    api.shutdown()
    assert len(api.get_all_assets()) == 0


def test_criteria_search(api: AssetAPI, sample_assets: Path) -> None:
    """Test finding assets by multiple criteria"""
    result = api.scan(sample_assets)
    print("\nDebug - All scanned assets:")
    for asset in sorted(api.get_all_assets(), key=lambda x: str(x.path)):
        print(f"  {asset.source}: {asset.path}")
    
    print("\nDebug - Testing p3d files in uniform folder")
    criteria = {
        'extension': '.p3d',
        'pattern': 'uniform/.*'
    }
    
    results = api.find_by_criteria(criteria)
    print(f"Found {len(results)} results matching criteria: {criteria}")
    for asset in sorted(results, key=lambda x: str(x.path)):
        print(f"  {asset.source}: {asset.path}")
    
    assert len(results) > 0, "Should find at least one .p3d file in uniform folder"
    assert all(a.path.suffix == '.p3d' and 'uniform' in str(a.path) for a in results)
    
    print("\nDebug - Testing PAA files in textures folder")
    criteria = {
        'extension': '.paa',
        'pattern': 'textures/.*'
    }
    
    results = api.find_by_criteria(criteria)
    print(f"Found {len(results)} results matching criteria: {criteria}")
    for asset in sorted(results, key=lambda x: str(x.path)):
        print(f"  {asset.source}: {asset.path}")
    
    assert len(results) > 0, "Should find at least one .paa file in textures folder"
    assert all(a.path.suffix == '.paa' and 'textures' in str(a.path) for a in results)
    
    print("\nDebug - Testing by source and extension")
    criteria = {
        'extension': '.p3d',
        'source': 'assets'
    }
    
    results = api.find_by_criteria(criteria)
    print(f"Found {len(results)} results matching criteria: {criteria}")
    for asset in sorted(results, key=lambda x: str(x.path)):
        print(f"  {asset.source}: {asset.path}")
    
    assert len(results) > 0, "Should find at least one .p3d file in assets"
    assert all(a.path.suffix == '.p3d' and a.source == 'assets' for a in results)


def test_api_cache_persistence(tmp_path: Path) -> None:
    """Test API cache save/load operations"""
    cache_file = tmp_path / "api_cache.json"
    config = APIConfig(cache_file=cache_file)
    
    # Create API and scan assets
    api1 = AssetAPI(config=config)
    initial_assets = {
        "@test/file1.paa": Asset(path=Path("@test/file1.paa"), source="@test", last_scan=datetime.now()),
        "@test/file2.paa": Asset(path=Path("@test/file2.paa"), source="@test", last_scan=datetime.now())
    }
    api1._cache.add_assets(initial_assets)
    api1.save_cache()
    
    # Create new API instance and load cache
    api2 = AssetAPI(config=config)
    assert api2.load_cache(), "Cache should load successfully"
    assert len(api2.get_all_assets()) == len(initial_assets)
    
    # Verify loaded assets match original
    for path, asset in initial_assets.items():
        loaded = api2.get_asset(path)
        assert loaded == asset, f"Loaded asset {path} doesn't match original"


def test_api_cache_invalidation(api: AssetAPI, sample_assets: Path) -> None:
    """Test cache invalidation behavior"""
    # Initial scan
    api.scan(sample_assets)
    assert api.is_cache_valid()
    
    # Force cache to be old
    api._cache._last_updated = datetime.now() - timedelta(hours=2)
    assert not api.is_cache_valid()
    
    # Verify rescan updates cache
    api.scan(sample_assets)
    assert api.is_cache_valid()


def test_api_cache_clear(api: AssetAPI, sample_assets: Path) -> None:
    """Test cache clearing through API"""
    api.scan(sample_assets)
    assert len(api.get_all_assets()) > 0
    
    api.clear_cache()
    assert len(api.get_all_assets()) == 0
    assert api.is_cache_valid()


def test_api_cache_source_isolation(api: AssetAPI, sample_assets: Path) -> None:
    """Test source isolation in cache through API"""
    # First scan the mirror mod directory
    mirror_mod_dir = sample_assets / "@tc_mirrorform"
    mirror_result = api.scan(mirror_mod_dir)
    assert len(mirror_result.assets) > 0, "Should find assets in @tc_mirrorform"
    mirror_assets = api.get_assets_by_source("tc_mirrorform")
    assert len(mirror_assets) > 0, "Should have cached mirror assets"
    
    # Verify expected mirror assets are present
    mirror_paths = {str(a.path) for a in mirror_assets}
    print("Debug - Mirror paths found:", mirror_paths)  # Debug output
    
    # Check for PBO-prefixed paths we know exist
    assert any('uniform\\mirror.p3d' in path for path in mirror_paths), \
           f"Missing mirror.p3d file. Found paths: {mirror_paths}"
    assert any('uniform\\black.paa' in path for path in mirror_paths), \
           f"Missing black.paa file. Found paths: {mirror_paths}"
    
    # Then scan the headband mod
    headband_mod_dir = sample_assets / "@tc_rhs_headband"
    headband_result = api.scan(headband_mod_dir)
    headband_assets = api.get_assets_by_source("tc_rhs_headband")
    assert len(headband_assets) > 0, "Should find headband assets"
    
    headband_paths = {str(a.path) for a in headband_assets}
    print("Debug - Headband paths found:", headband_paths)  # Debug output
    
    # Verify source isolation
    assert not mirror_paths.intersection(headband_paths), \
           "Sources should not share assets"
    
    # Verify total assets makes sense
    total_assets = len(api.get_all_assets())
    assert total_assets == len(mirror_assets) + len(headband_assets), \
           "Total assets should equal sum of individual sources"


def test_api_cache_recovery(tmp_path: Path, sample_assets: Path) -> None:
    """Test cache recovery after corruption"""
    cache_file = tmp_path / "corrupt_cache.json"
    cache_file.write_text("invalid json")
    
    api = AssetAPI(config=APIConfig(cache_file=cache_file))
    assert len(api.get_all_assets()) == 0  # Should start empty
    
    # Should still work after cache corruption
    result = api.scan(sample_assets)
    assert len(result.assets) > 0
    assert api.is_cache_valid()
