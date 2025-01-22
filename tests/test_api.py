import pytest
from pathlib import Path
import re
from datetime import datetime, timedelta
from asset_scanner import Asset, AssetAPI, APIConfig
import logging
from unittest.mock import Mock

@pytest.fixture
def sample_assets(tmp_path):
    """Create sample asset directory structure"""
    # Create sample directory structure
    asset_dir = tmp_path / "assets"
    (asset_dir / "models").mkdir(parents=True)
    (asset_dir / "textures").mkdir()
    
    # Create test files
    files = [
        ("models/vehicle.p3d", "content1"),
        ("models/vehicle_copy.p3d", "content1"),  # Duplicate content
        ("textures/vehicle_co.paa", "texture1"),
        ("models/weapon.p3d", "content2"),
    ]
    
    for fname, content in files:
        path = asset_dir / fname
        path.write_text(content)
        
    return asset_dir

@pytest.fixture
def api(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

def test_api_configuration():
    """Test API configuration handling"""
    custom_config = APIConfig(
        cache_max_age=1800,
        cache_max_size=500000,
        scan_timeout=60,
        max_workers=4
    )
    
    api = AssetAPI(Path("test"), config=custom_config)
    assert api.config.cache_max_age == 1800
    assert api.config.cache_max_size == 500000

def test_error_handling():
    """Test error handler configuration"""
    error_handler = Mock()
    config = APIConfig(error_handler=error_handler)
    api = AssetAPI(Path("test"), config=config)

    # Trigger an error
    try:
        api.scan_directory(Path("nonexistent"))
    except FileNotFoundError:
        pass  # Expected exception

    # Verify error handler was called
    error_handler.assert_called_once()
    args = error_handler.call_args[0]
    assert isinstance(args[0], FileNotFoundError)

def test_progress_callback():
    """Test progress reporting"""
    progress_updates = []
    
    def progress_handler(path: str, progress: float):
        progress_updates.append((path, progress))
        
    config = APIConfig(progress_callback=progress_handler)
    api = AssetAPI(Path("test"), config=config)
    
    # Scan should trigger progress updates
    api.scan_directory(Path("."))
    assert len(progress_updates) > 0

def test_detailed_stats(api, sample_assets):
    """Test detailed statistics collection"""
    api.scan_directory(sample_assets)
    stats = api.get_detailed_stats()
    
    assert 'api_version' in stats
    assert 'scan_stats' in stats
    assert 'cache_stats' in stats
    assert stats['scan_stats']['total_scans'] > 0

def test_batch_processing(api, sample_assets):
    """Test batch processing capabilities"""
    api.scan_directory(sample_assets)
    
    processed = []
    def test_operation(asset: Asset):
        processed.append(asset)
        
    api.batch_process(test_operation, batch_size=2)
    assert len(processed) == len(api.get_all_assets())

# Basic API functionality
def test_basic_scanning(api, sample_assets):
    """Test basic asset scanning functionality"""
    result = api.scan_directory(sample_assets)
    assert len(result.assets) > 0
    assert all(isinstance(asset, Asset) for asset in result.assets)

def test_source_filtering(api, sample_assets):
    """Test filtering assets by source"""
    api.scan_directory(sample_assets)
    assets = api.get_assets_by_source(sample_assets.name)
    assert len(assets) > 0
    assert all(asset.source == sample_assets.name for asset in assets)

def test_cache_persistence(api, sample_assets):
    """Test that cache persists between scans"""
    # First scan
    result1 = api.scan_directory(sample_assets)
    first_assets = api.get_all_assets()

    # Second scan should use cache
    result2 = api.scan_directory(sample_assets)
    second_assets = api.get_all_assets()

    # Results should be identical
    assert {str(a.path) for a in first_assets} == {str(a.path) for a in second_assets}
    assert {a.source for a in first_assets} == {a.source for a in second_assets}

def test_scan_multiple(api, tmp_path):
    """Test scanning multiple directories"""
    # Create test directories
    dirs = []
    for i in range(3):
        path = tmp_path / f"dir{i}"
        path.mkdir()
        (path / "test.p3d").write_text(f"content{i}")
        dirs.append(path)
    
    results = api.scan_multiple([Path(d) for d in dirs])
    assert len(results) == 3
    assert all(len(r.assets) > 0 for r in results)

def test_find_by_extension(api, sample_assets):
    """Test finding assets by extension"""
    api.scan_directory(sample_assets)
    p3d_assets = api.find_by_extension('.p3d')
    assert all(a.path.suffix == '.p3d' for a in p3d_assets)
    assert len(p3d_assets) == 3  # vehicle.p3d, vehicle_copy.p3d, weapon.p3d

def test_find_by_pattern(api, sample_assets):
    """Test finding assets by pattern"""
    api.scan_directory(sample_assets)
    vehicle_assets = api.find_by_pattern(r"vehicle.*\.p3d$")
    assert len(vehicle_assets) == 2  # vehicle.p3d and vehicle_copy.p3d

def test_source_handling(api, sample_assets):
    """Test comprehensive source name handling"""
    api.scan_directory(sample_assets)
    
    # Test with and without @ prefix
    source_name = sample_assets.name
    assets1 = api.get_assets_by_source(source_name)
    assets2 = api.get_assets_by_source(f"@{source_name}")
    
    assert assets1 == assets2
    assert all(a.source == source_name for a in assets1)
    
    # Add source filtering tests
    filtered = api.get_assets_by_source(source_name)
    assert len(filtered) > 0
    assert all(asset.source == source_name for asset in filtered)

def test_folder_registration(api, tmp_path):
    """Test folder registration and scanning"""
    # Create test structure
    folder = tmp_path / "test_folder"
    folder.mkdir()
    (folder / "test.p3d").write_text("content")
    
    # Register folder with friendly name
    api.add_folder("TestMod", folder)
    
    # Verify registration
    assert api.get_folders()["TestMod"] == folder.resolve()
    
    # Scan and verify source attribution
    results = api.scan_all_folders()
    assert len(results) == 1
    assert all(asset.source == "TestMod" for asset in results[0].assets)

def test_game_folder_scanning(api, tmp_path):
    """Test game directory structure scanning"""
    # Create mock game structure
    game_dir = tmp_path / "Game"
    game_dir.mkdir()
    
    # Create addons directory
    addons = game_dir / "Addons"
    addons.mkdir()
    (addons / "test.paa").write_text("content")
    
    # Create mod directory
    mod = game_dir / "@TestMod"
    mod.mkdir()
    (mod / "test.p3d").write_text("content")
    
    # Register game directory
    api.add_folder("GameBase", game_dir)
    
    # Scan game folders
    results = api.scan_game_folders(game_dir)
    
    # Verify results
    assert len(results) == 2  # Addons and @TestMod
    all_assets = [asset for result in results for asset in result.assets]
    assert all(asset.source == "GameBase" for asset in all_assets)

def test_asset_tree(api, sample_assets):
    """Test hierarchical asset view"""
    api.scan_directory(sample_assets)
    tree = api.get_asset_tree()
    
    # Find directories in normalized form
    directory_keys = {str(Path(k)).replace('\\', '/') for k in tree.keys()}
    
    # Check for directory presence using normalized paths
    assert any('models' in key for key in directory_keys)
    assert any('textures' in key for key in directory_keys)
    
    # Verify structure
    for assets in tree.values():
        assert isinstance(assets, set)
        assert all(isinstance(a, Asset) for a in assets)
        
    # Verify asset grouping
    for key, assets in tree.items():
        normalized_key = str(Path(key)).replace('\\', '/')
        for asset in assets:
            assert normalized_key in str(asset.path).replace('\\', '/')

def test_find_related(api, sample_assets):
    """Test finding related assets"""
    api.scan_directory(sample_assets)
    
    # Get a test asset
    asset = next(iter(api.get_all_assets()))
    related = api.find_related(asset)
    
    # Should find assets in same directory
    assert all(str(a.path.parent) == str(asset.path.parent) for a in related)
    assert asset not in related  # Shouldn't include self

def test_path_resolution(api, sample_assets):
    """Test Arma path format resolution"""
    api.scan_directory(sample_assets)
    
    # Test different path formats
    paths = [
        r"\a3\data_f\test.paa",
        "@Mod/addons/test.pbo//file.paa",
        "models/vehicle.p3d",
        "textures/vehicle_co.paa"
    ]
    
    for path in paths:
        result = api.resolve_path(path)
        # We don't expect all paths to exist in sample data
        if result:
            assert isinstance(result, Asset)

def test_verification(api, sample_assets):
    """Test asset verification methods"""
    api.scan_directory(sample_assets)
    
    # Debug: Print scanned assets
    print("\nDebug: Scanned assets:")
    for asset in api.get_all_assets():
        print(f"  {asset.path} (source: {asset.source})")
    
    source_name = sample_assets.name
    paths = [
        f"{source_name}/models/vehicle.p3d",  # Full path with source
        "models/vehicle.p3d",                  # Path without source
        "vehicle.p3d",                         # Just filename
        "nonexistent.paa"                      # Missing file
    ]
    
    # Test has_asset with various path formats
    for path in paths[:-1]:  # Test all except nonexistent
        assert api.has_asset(path), f"Failed to find asset: {path}"
    
    # Test nonexistent file
    assert not api.has_asset(paths[-1])
    
    # Test verify_assets
    results = api.verify_assets(paths)
    assert all(results[p] for p in paths[:-1])
    assert not results[paths[-1]]
    
    # Test find_missing
    missing = api.find_missing(paths)
    assert len(missing) == 1
    assert paths[-1] in missing

def test_asset_iteration(api, sample_assets):
    """Test memory-efficient asset iteration"""
    api.scan_directory(sample_assets)
    
    # Test with different batch sizes
    batch_sizes = [1, 2, 5]
    for size in batch_sizes:
        total_assets = 0
        for batch in api.iter_assets(batch_size=size):
            assert len(batch) <= size
            total_assets += len(batch)
        
        assert total_assets == len(api.get_all_assets())
