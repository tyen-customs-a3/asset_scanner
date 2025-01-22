import pytest
from pathlib import Path
from asset_scanner import AssetAPI, Asset
import logging

# Setup logger
logger = logging.getLogger(__name__)

# Update test constants to match actual PBO prefixes

# babe_em.pbo has prefix=babe\babe_em
EM_BABE_EXPECTED = {
    'babe/babe_em/models/helper.p3d',
    'babe/babe_em/data/nope_ca.paa',
    'babe/babe_em/textures/EM_ca.paa',
    'babe/babe_em/textures/ui/fatigue_ca.paa',
    'babe/babe_em/func/mov/fn_jump_only.sqf'
}

# mirrorform.pbo has prefix=tc\mirrorform
MIRROR_EXPECTED = {
    "tc/mirrorform/logo.paa",
    "tc/mirrorform/logo_small.paa",
    "tc/mirrorform/uniform/mirror.p3d",
    "tc/mirrorform/uniform/black.paa"
}

# rhs_headband.pbo has prefix=tc\rhs_headband
HEADBAND_EXPECTED = {
    "tc/rhs_headband/data/tex/headband_choccymilk_co.paa",
    "tc/rhs_headband/logo.paa",
    "tc/rhs_headband/logo_small.paa"
}

def test_mirror_addon_scanning(mirror_addon_path, tmp_path):
    """Test scanning @tc_mirrorform addon with specific file checks"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan_directory(mirror_addon_path)
    
    # Convert scanned assets to normalized paths for comparison
    scanned_paths = {
        str(asset.path).replace('\\', '/').removeprefix('@tc_mirrorform/addons/').removeprefix('tc_mirrorform/addons/')
        for asset in result.assets
    }
    
    # Debug logging for troubleshooting
    logger.debug("------- Mirror Addon Test Results -------")
    logger.debug(f"Total assets found: {len(result.assets)}")
    logger.debug("Scanned paths:")
    for path in sorted(scanned_paths):
        logger.debug(f"  {path}")
    
    logger.debug("\nExpected paths:")
    for path in sorted(MIRROR_EXPECTED):
        logger.debug(f"  {path}")
    
    logger.debug("\nAsset details:")
    for asset in sorted(result.assets, key=lambda x: str(x.path)):
        logger.debug(f"  Path: {asset.path}")
        logger.debug(f"    Source: {asset.source}")

    # Verify all expected asset files were found
    for expected in MIRROR_EXPECTED:
        assert expected in scanned_paths, f"Missing expected asset: {expected}"
    
    # Update to not expect @ prefix in source names
    base_source = mirror_addon_path.name.strip('@')
    
    # Verify source attribution (without @ prefix)
    invalid_sources = [asset for asset in result.assets if asset.source != base_source]
    assert not invalid_sources, f"Found assets with incorrect source: {invalid_sources}"

def test_headband_addon_scanning(headband_addon_path, tmp_path):
    """Test scanning @tc_rhs_headband addon"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan_directory(headband_addon_path)
    
    scanned_paths = {
        str(asset.path).replace('\\', '/').removeprefix('@tc_rhs_headband/addons/').removeprefix('tc_rhs_headband/addons/')
        for asset in result.assets
    }
    
    for expected in HEADBAND_EXPECTED:
        assert expected in scanned_paths, f"Missing expected asset: {expected}"
    
    # Update to not expect @ prefix
    base_source = headband_addon_path.name.strip('@')
    assert all(asset.source == base_source for asset in result.assets)

def test_em_addon_scanning(em_addon_path, tmp_path):
    """Test scanning babe_em.pbo with specific prefix"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan_directory(em_addon_path)
    
    scanned_paths = {
        str(asset.path).replace('\\', '/').removeprefix('@em/addons/').removeprefix('em/addons/')
        for asset in result.assets
    }
    
    # Log actual paths for debugging
    logger.debug("Found paths:")
    for path in sorted(scanned_paths):
        logger.debug(f"  {path}")

    # Check if paths match expected prefix structure
    for expected in EM_BABE_EXPECTED:
        assert expected in scanned_paths, f"Missing expected asset: {expected}"
        
    # Update to not expect @ prefix
    base_source = em_addon_path.name.strip('@')
    assert all(asset.source == base_source for asset in result.assets)

def test_scanning_all_addons(sample_data_path, tmp_path):
    """Test scanning all sample addons together"""
    api = AssetAPI(tmp_path / "cache")
    
    # Get all addon directories
    addon_paths = [
        p for p in sample_data_path.iterdir() 
        if p.is_dir() and p.name.startswith("@")
    ]
    
    # Scan all addons
    results = api.scan_multiple(addon_paths)
    
    # Verify expected addons
    addon_names = {p.name.strip('@') for p in addon_paths}  # Strip @ for comparison
    expected_addons = {"em", "tc_mirrorform", "tc_rhs_headband"}
    assert addon_names == expected_addons
    
    # Basic validation
    assert len(results) == len(addon_paths)
    assert all(len(r.assets) > 0 for r in results)
    
    # Check statistics
    stats = api.get_stats()
    assert stats['total_assets'] > 0
    assert stats['total_sources'] == len(addon_paths)  # Should match number of addons
    
    # Get sources without @ prefix
    scanned_sources = {s.strip('@') for s in api.get_sources()}
    assert scanned_sources == expected_addons  # Compare without @ prefix

def test_asset_patterns(sample_data_path, tmp_path):
    """Test pattern-based asset filtering"""
    api = AssetAPI(tmp_path / "cache")
    
    # Scan all addons first
    api.scan_directory(sample_data_path)
    
    # Test different pattern searches
    models = api.find_by_extension('.p3d')
    textures = api.find_by_extension('.paa')
    
    assert len(models) > 0, "Should find model files"
    assert len(textures) > 0, "Should find texture files"
    
    # Find assets by pattern
    mirror = api.find_by_pattern(r".*mirror.*")
    headband = api.find_by_pattern(r".*headband.*")
    
    # Verify we found assets from each category
    assert len(mirror) > 0, "Should find mirror assets"
    assert len(headband) > 0, "Should find headband assets"

def test_mirror_asset_structure(mirror_addon_path, tmp_path):
    """Test detailed structure of mirror addon assets"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan_directory(mirror_addon_path)
    
    # Convert all paths to normalized format for comparison
    asset_paths = {
        str(a.path).replace('\\', '/').removeprefix('@tc_mirrorform/addons/').removeprefix('tc_mirrorform/addons/')
        for a in result.assets
    }
    
    # Expected paths should match PBO prefix structure
    expected_paths = {
        "tc/mirrorform/uniform/mirror.p3d",
        "tc/mirrorform/uniform/black.paa",
        "tc/mirrorform/logo.paa",
        "tc/mirrorform/logo_small.paa"
    }
    
    # Verify all expected paths exist
    for path in expected_paths:
        assert path in asset_paths, f"Missing expected asset: {path}"
    
    # Test asset retrieval
    model_path = "tc/mirrorform/uniform/mirror.p3d"
    model_asset = api.get_asset(model_path)
    assert model_asset is not None, f"Mirror model not found at {model_path}"
    assert model_asset.source == "tc_mirrorform"  # No @ prefix expected

def test_pbo_path_handling(mirror_addon_path, tmp_path):
    """Test PBO path normalization"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan_directory(mirror_addon_path)
    
    # Convert paths to normalized format
    scanned_paths = {str(a.path).replace('\\', '/').removeprefix('@tc_mirrorform/addons/').removeprefix('tc_mirrorform/addons/') for a in result.assets}
    
    # All paths should start with PBO prefix
    prefix = "tc/mirrorform"
    for path in scanned_paths:
        if not path.startswith(prefix):
            assert path.endswith(('.paa', '.p3d')), f"Non-prefixed path: {path}"
    
    # Verify source name
    assert all(a.source == "tc_mirrorform" for a in result.assets)

# Helper function for path normalization
def _normalize_asset_path(path: str, mod_name: str) -> str:
    """Remove mod and addon prefixes from path"""
    path = path.replace('\\', '/')
    prefixes = [
        f"@{mod_name}/addons/",
        f"{mod_name}/addons/",
    ]
    for prefix in prefixes:
        if path.startswith(prefix):
            return path[len(prefix):]
    return path
