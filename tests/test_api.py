import pytest
from pathlib import Path
from asset_scanner import Asset, AssetAPI
from unittest.mock import Mock
from asset_scanner.config import APIConfig


@pytest.fixture
def sample_assets(tmp_path: Path) -> Path:
    """Create sample asset directory structure"""
    asset_dir = tmp_path / "assets"
    (asset_dir / "models").mkdir(parents=True)
    (asset_dir / "textures").mkdir()
    (asset_dir / "addons").mkdir()

    # Create sample mod structure
    mod_dir = asset_dir / "@TestMod"
    mod_dir.mkdir()
    (mod_dir / "addons").mkdir()

    files = [
        ("models/vehicle.p3d", "content1"),
        ("models/vehicle_copy.p3d", "content1"),
        ("textures/vehicle_co.paa", "texture1"),
        ("models/weapon.p3d", "content2"),
        ("@TestMod/addons/test.pbo", b"pbo_content"),
        ("addons/base.pbo", b"base_content")
    ]

    for fname, content in files:
        path = asset_dir / fname
        if isinstance(content, str):
            path.write_text(content)
        else:
            path.write_bytes(content)

    return asset_dir


@pytest.fixture
def api(tmp_path: Path) -> AssetAPI:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)


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
    api = AssetAPI(Path("test"), config=config)

    with pytest.raises(FileNotFoundError):
        api.scan(Path("nonexistent"))

    error_handler.assert_called_once()
    args = error_handler.call_args[0]
    assert isinstance(args[0], FileNotFoundError)


def test_asset_querying(api: AssetAPI, sample_assets: Path) -> None:
    """Test asset querying methods"""
    api.scan(sample_assets)
    
    # Test get_asset
    asset = api.get_asset("vehicle.p3d")
    assert asset is not None
    assert asset.path.name == "vehicle.p3d"
    
    # Test find_by_extension
    p3d_assets = api.find_by_extension(".p3d")
    assert len(p3d_assets) == 3
    
    # Test find_by_pattern
    vehicle_assets = api.find_by_pattern(r"vehicle.*\.p3d$")
    assert len(vehicle_assets) == 2


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
    api.scan(sample_assets)
    
    criteria = {
        'extension': '.p3d',
        'pattern': 'vehicle'
    }
    
    results = api.find_by_criteria(criteria)
    assert len(results) > 0
    assert all(a.path.suffix == '.p3d' and 'vehicle' in str(a.path) for a in results)
