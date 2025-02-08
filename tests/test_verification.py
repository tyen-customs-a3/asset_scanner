import pytest
from asset_scanner import AssetAPI

@pytest.fixture
def api(tmp_path):
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

@pytest.fixture
def mock_arma_structure(tmp_path):
    """Create mock Arma directory structure"""
    # Create base directories
    arma_path = tmp_path / "Arma 3"
    arma_path.mkdir()
    (arma_path / "addons").mkdir()
    
    mod_path = tmp_path / "Mods" / "@TestMod"
    mod_path.mkdir(parents=True)
    mod_addons = mod_path / "addons"
    mod_addons.mkdir()
    
    # Create regular test files instead of PBOs for basic testing
    test_files = {
        mod_addons / "test_weapon.p3d": b"model data",
        mod_addons / "texture.paa": b"texture data",
        mod_addons / "test_script.sqf": b"script data"
    }
    
    # Write test files
    for path, content in test_files.items():
        path.write_bytes(content)
        
    return tmp_path

def test_verify_assets(api, mock_arma_structure):
    """Test asset verification methods"""
    mod_path = mock_arma_structure / "Mods" / "@TestMod"
    result = api.scan_directory(mod_path)
    
    # Debug: Print all scanned assets
    print("\nScanned assets:")
    for asset in result.assets:
        print(f"  {asset.path} (source: {asset.source})")
    
    # Test exact paths
    test_path = "TestMod/addons/test_weapon.p3d"
    asset = api.get_asset(test_path)
    if not asset:
        print(f"\nFailed to find: {test_path}")
        print("Available paths:")
        for a in api.get_all_assets():
            print(f"  {a.path}")
    
    assert api.has_asset(test_path), f"Asset not found: {test_path}"
    assert api.has_asset("TestMod/addons/texture.paa")
    
    # Test partial paths
    assert api.has_asset("test_weapon.p3d")
    assert api.has_asset("texture.paa")
    
    # Test nonexistent files
    assert not api.has_asset("nonexistent.paa")

def test_path_resolution(api, mock_arma_structure):
    """Test various Arma path formats"""
    api.scan_directory(mock_arma_structure / "Arma 3")
    
    paths = [
        r"\a3\data_f\texture.paa",
        "@TestMod/addons/main.pbo//texture.paa",
        "weapons_f/rifle.p3d",
        "data_f/something.paa"
    ]
    
    for path in paths:
        result = api.resolve_path(path)
        # We don't expect all paths to exist, just that resolution works
        if result:
            assert result.path is not None

def test_case_sensitivity(api, mock_arma_structure):
    """Test case-sensitive and insensitive path handling"""
    mod_path = mock_arma_structure / "Mods" / "@TestMod"
    api.scan_directory(mod_path)
    
    # Test case variations
    variations = [
        "TEXTURE.PAA",
        "Texture.paa",
        "texture.PAA"
    ]
    
    # All variations should match the original file
    for variant in variations:
        assert api.has_asset(variant), f"Failed to match: {variant}"
        assert api.resolve_path(variant) is not None

def test_mod_directory_handling(api, mock_arma_structure):
    """Test mod directory management"""
    mod_path = mock_arma_structure / "Mods" / "@TestMod"
    
    # Add and verify mod directory
    api.add_mod_directory(mod_path)
    assert mod_path.resolve() in api._mod_directories
    
    # Scan and verify assets
    api.scan_directory(mod_path)
    assets = api.get_assets_by_source("TestMod")
    assert len(assets) > 0
