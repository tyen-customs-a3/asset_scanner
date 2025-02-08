"""Asset search and filtering tests"""
import pytest
from asset_scanner import AssetAPI

@pytest.fixture
def api(tmp_path):
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

@pytest.fixture
def test_assets(tmp_path):
    """Create test assets for searching"""
    base = tmp_path / "test_assets"
    base.mkdir()
    
    # Create test files with various patterns
    files = {
        "models/weapon_ak.p3d": "model1",
        "models/weapon_m4.p3d": "model2",
        "textures/weapon_ak_co.paa": "texture1",
        "textures/weapon_m4_co.paa": "texture2",
        "data/scripts/weapon.sqf": "script",
        "data/common.paa": "common",
    }
    
    # Create the directory structure
    for path, content in files.items():
        full_path = base / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        
    return base

def test_find_by_extension(api, test_assets):
    """Test extension-based search"""
    api.scan_directory(test_assets)
    
    # Test different extensions
    p3d_files = api.find_by_extension('.p3d')
    paa_files = api.find_by_extension('paa')  # Test without dot
    sqf_files = api.find_by_extension('.sqf')
    
    assert len(p3d_files) == 2
    assert len(paa_files) == 3
    assert len(sqf_files) == 1
    
    # Verify extensions are correct
    assert all(a.path.suffix == '.p3d' for a in p3d_files)
    assert all(a.path.suffix == '.paa' for a in paa_files)
    assert all(a.path.suffix == '.sqf' for a in sqf_files)

def test_find_by_pattern(api, test_assets):
    """Test pattern matching"""
    api.scan_directory(test_assets)
    
    # Test different patterns
    ak_files = api.find_by_pattern(r"weapon_ak")
    m4_files = api.find_by_pattern(r"weapon_m4")
    textures = api.find_by_pattern(r"_co\.paa$")
    
    assert len(ak_files) == 2  # Model and texture
    assert len(m4_files) == 2  # Model and texture
    assert len(textures) == 2  # All color textures

def test_find_by_criteria(api, test_assets):
    """Test multi-criteria search"""
    api.scan_directory(test_assets)
    
    # Test combined criteria
    criteria = {
        'extension': '.paa',
        'pattern': r'weapon',
        'source': test_assets.name
    }
    
    results = api.find_by_criteria(criteria)
    
    # Verify results match all criteria
    assert all(a.path.suffix == '.paa' for a in results)
    assert all('weapon' in str(a.path) for a in results)
    assert all(a.source == test_assets.name for a in results)
    assert len(results) == 2  # Should find weapon textures only

def test_case_insensitive_search(api, test_assets):
    """Test case-insensitive pattern matching"""
    api.scan_directory(test_assets)
    
    # Test different case patterns
    upper = api.find_by_pattern(r"WEAPON")
    lower = api.find_by_pattern(r"weapon")
    mixed = api.find_by_pattern(r"WeApOn")
    
    # All should find the same files
    assert len(upper) == len(lower) == len(mixed)
    assert upper == lower == mixed

def test_complex_patterns(api, test_assets):
    """Test more complex search patterns"""
    api.scan_directory(test_assets)
    
    # Debug output
    print("\nDebug: All scanned assets:")
    for asset in api.get_all_assets():
        print(f"  {asset.path}")
    
    # Test regex patterns
    models = api.find_by_pattern(r"models/.*\.p3d$")
    color_maps = api.find_by_pattern(r"_co\.paa$")
    ak_variants = api.find_by_pattern(r"ak.*\.(p3d|paa)$")
    
    # Verify results
    assert len(models) == 2, f"Expected 2 models, found: {[str(a.path) for a in models]}"
    assert len(color_maps) == 2, f"Expected 2 color maps, found: {[str(a.path) for a in color_maps]}"
    assert len(ak_variants) == 2, f"Expected 2 ak variants, found: {[str(a.path) for a in ak_variants]}"
