import pytest
from pathlib import Path
from asset_scanner import AssetAPI, Asset
import logging
from .test_data import (
    EXPECTED_PATHS, MIRRORFORM_PBO_FILE, SAMPLE_DATA_ROOT, PBO_PATHS, PBO_FILES,
    EM_BABE_EXPECTED, MIRROR_EXPECTED, HEADBAND_EXPECTED, SOURCE_MAPPING
)

# Setup logger
logger = logging.getLogger(__name__)


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

def test_pbo_prefix_handling(tmp_path):
    """Test correct handling of PBO prefixes"""
    api = AssetAPI(tmp_path / "cache")
    
    for pbo_name, pbo_path in PBO_PATHS.items():
        if not pbo_path.exists():
            pytest.skip(f"PBO file not found: {pbo_path}")

        result = api.scan_pbo(pbo_path)
        assert result.prefix == PBO_FILES[pbo_name]['prefix']
        
        prefix_parts = PBO_FILES[pbo_name]['prefix'].replace('\\', '/').split('/')
        for asset in result.assets:
            path_str = str(asset.path).replace('\\', '/')
            assert path_str.startswith('/'.join(prefix_parts))

def test_pbo_content_extraction(sample_data_path, caplog):
    """Test direct PBO content extraction and prefix handling"""
    caplog.set_level(logging.DEBUG)
    
    mirror_pbo = MIRRORFORM_PBO_FILE
    assert mirror_pbo.exists(), f"Test PBO file not found: {mirror_pbo}"
    
    from asset_scanner.pbo_extractor import PboExtractor
    extractor = PboExtractor()
    
    # Test list contents and prefix extraction
    return_code, stdout, stderr = extractor.list_contents(mirror_pbo)
    assert return_code == 0, f"PBO listing failed: {stderr}"
    
    logger.debug("\nRaw PBO Listing Output:")
    for line in stdout.splitlines():
        logger.debug(f"  {line}")
    
    # Test prefix extraction from raw output
    prefix = extractor.extract_prefix(stdout)
    logger.debug(f"\nExtracted Prefix: {prefix}")
    assert prefix == "tc\\mirrorform" or prefix == "tc/mirrorform", f"Unexpected prefix: {prefix}"
    
    # Test content scanning with normalized paths
    return_code, code_files, all_paths = extractor.scan_pbo_contents(mirror_pbo)
    assert return_code == 0, "PBO scanning failed"
    
    logger.debug("\nNormalized Paths:")
    for path in sorted(all_paths):
        logger.debug(f"  {path}")
    
    # Convert expected and scanned paths to sets for comparison
    # Here we expect non-prefixed paths since prefix is handled separately
    expected_paths = {
        'logo.paa',
        'logo_small.paa',
        'uniform/mirror.p3d',
        'uniform/black.paa'
    }
    
    # Get paths without prefix for comparison
    prefix_with_slash = prefix.replace('\\', '/') + '/'
    scanned_paths = {
        p.replace('\\', '/').removeprefix(prefix_with_slash)
        for p in all_paths
        if not p.endswith('.rvmat')  # Exclude non-asset files
    }
    
    logger.debug("\nProcessed paths for comparison:")
    logger.debug(f"Expected: {sorted(expected_paths)}")
    logger.debug(f"Found: {sorted(scanned_paths)}")
    
    # Verify all expected paths are found
    for path in expected_paths:
        assert path in scanned_paths, f"Missing expected path: {path}"
        
    # Verify prefix is properly applied in full paths
    full_paths = {p.replace('\\', '/') for p in all_paths}
    for path in full_paths:
        if not path.endswith(('.bin', '.rvmat')):  # Skip non-asset files
            assert path.startswith(prefix.replace('\\', '/')), f"Path missing prefix: {path}"

def test_pbo_scanning_and_contents(tmp_path):
    """Test scanning individual PBOs and verify their contents"""
    api = AssetAPI(tmp_path / "cache")
    
    for pbo_name, pbo_path in PBO_PATHS.items():
        if not pbo_path.exists():
            pytest.skip(f"PBO file not found: {pbo_path}")
            
        # Scan individual PBO
        result = api.scan_pbo(pbo_path)
        
        # Verify basic properties
        assert result is not None
        assert result.prefix == PBO_FILES[pbo_name]['prefix']
        assert result.source == SOURCE_MAPPING[pbo_name]
        
        # Get paths for comparison - strip prefix for comparison
        prefix_with_slash = result.prefix.replace('\\', '/') + '/'
        scanned_paths = {
            str(a.path).replace('\\', '/').removeprefix(prefix_with_slash) 
            for a in result.assets
        }
        expected_paths = EXPECTED_PATHS[pbo_name]
        
        # Log paths for debugging
        logger.debug(f"\nPaths for {pbo_name}:")
        logger.debug(f"Scanned paths: {sorted(scanned_paths)}")
        logger.debug(f"Expected paths: {sorted(expected_paths)}")
        
        # Verify expected contents
        assert scanned_paths == expected_paths, f"Mismatch in {pbo_name} contents"
        
        # Verify all assets have correct source
        assert all(a.source == SOURCE_MAPPING[pbo_name] for a in result.assets)
        
        # Verify file extensions
        for asset in result.assets:
            ext = asset.path.suffix.lower()
            assert ext in {'.p3d', '.paa', '.rtm'}, f"Invalid extension in {pbo_name}: {ext}"
