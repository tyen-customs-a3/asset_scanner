import pytest
from pathlib import Path
from asset_scanner import AssetAPI, Asset
from datetime import datetime

@pytest.fixture
def complex_structure(tmp_path):
    """Create a complex nested mod structure"""
    root = tmp_path / "complex_mods"
    root.mkdir()
    
    # Structure with overlapping and unique files
    structure = {
        "@mod_a": {
            "addons/weapons/rifle.p3d": "rifle data",
            "addons/weapons/rifle.paa": "rifle texture",
            "addons/shared/common.paa": "shared texture 1",
        },
        "@mod_b": {
            "addons/weapons/pistol.p3d": "pistol data",
            "addons/shared/common.paa": "shared texture 2",  # Same name, different content
        },
        "@mod_c": {
            "addons/weapons/rifle.paa": "different rifle texture",  # Same name as mod_a
            "addons/unique/special.p3d": "unique model",
        }
    }
    
    # Create files
    for mod, files in structure.items():
        mod_dir = root / mod
        for path, content in files.items():
            full_path = mod_dir / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            
    return root

def test_strict_accumulation(complex_structure, tmp_path):
    """Test strict accumulation of assets across multiple scans"""
    api = AssetAPI(tmp_path / "cache")
    
    # Track expected assets
    expected_by_mod = {}
    total_unique_paths = set()
    
    # Scan each mod and verify
    for mod_dir in sorted(complex_structure.iterdir()):
        result = api.scan_directory(mod_dir)
        mod_name = mod_dir.name
        
        # Store results for this mod
        expected_by_mod[mod_name] = {
            str(asset.path): asset for asset in result.assets
        }
        
        # Update total unique paths
        total_unique_paths.update(str(asset.path) for asset in result.assets)
        
        # Verify current state
        cached = api.get_all_assets()
        cached_paths = {str(asset.path) for asset in cached}
        
        # All previously scanned assets should still be present
        for prev_mod, prev_assets in expected_by_mod.items():
            for path, asset in prev_assets.items():
                assert path in cached_paths, f"Lost asset {path} from {prev_mod}"
                cached_asset = next(a for a in cached if str(a.path) == path)
                assert cached_asset.source == asset.source, f"Source changed for {path}"
        
        # Cache should contain exactly the expected number of assets
        assert len(cached) == len(total_unique_paths), \
            f"Cache has {len(cached)} assets, expected {len(total_unique_paths)}"

def test_source_integrity(complex_structure, tmp_path):
    """Test that source attribution remains correct during accumulation"""
    api = AssetAPI(tmp_path / "cache")
    
    # Register each mod as a source
    sources = {}
    for mod_dir in complex_structure.iterdir():
        source_name = mod_dir.name
        api.add_folder(source_name, mod_dir)
        sources[source_name.strip('@')] = mod_dir  # Store without @ prefix
    
    # Scan all mods
    results = api.scan_multiple([p for p in complex_structure.iterdir()])
    
    # Debug: Print all assets and their sources
    print("\nDebug: All assets and their sources:")
    for asset in api.get_all_assets():
        print(f"Asset: {asset.path} -> Source: {asset.source}")
    
    # Verify each asset's source
    all_assets = api.get_all_assets()
    for asset in all_assets:
        # Get the asset's full path for debugging
        full_path = str(asset.path).replace('\\', '/')
        
        # Find matching source (comparing without @ prefix)
        matching_source = None
        for source_name, source_path in sources.items():
            source_prefix = source_name.replace('\\', '/')
            if full_path.startswith(f"@{source_prefix}/") or full_path.startswith(f"{source_prefix}/"):
                matching_source = source_name
                break
        
        assert matching_source is not None, \
            f"No matching source found for asset {full_path}"
        assert asset.source == matching_source, \
            f"Asset {full_path} has source {asset.source}, expected {matching_source}"

def test_duplicate_handling(complex_structure, tmp_path):
    """Test handling of files with same name but different paths"""
    api = AssetAPI(tmp_path / "cache")
    
    # Scan all at once
    api.scan_multiple([p for p in complex_structure.iterdir()])
    
    # Check specific cases
    rifle_textures = api.find_by_pattern("rifle.paa$")
    assert len(rifle_textures) == 2, "Should find both rifle textures"
    
    # Verify different sources
    sources = {asset.source for asset in rifle_textures}
    assert len(sources) == 2, "Textures should have different sources"
    
    # Check content preservation
    common_textures = api.find_by_pattern("common.paa$")
    assert len(common_textures) == 2, "Should preserve both common textures"

def test_incremental_scanning(complex_structure, tmp_path):
    """Test scanning with updates and modifications"""
    api = AssetAPI(tmp_path / "cache")
    
    # Initial scan
    initial_paths = [p for p in complex_structure.iterdir()][:2]
    api.scan_multiple(initial_paths)
    initial_count = len(api.get_all_assets())
    
    # Add new mod
    remaining_path = next(p for p in complex_structure.iterdir() if p not in initial_paths)
    api.scan_directory(remaining_path)
    
    # Verify accumulation
    final_assets = api.get_all_assets()
    assert len(final_assets) > initial_count, "Should add new assets"
    
    # Modify an existing file
    test_file = next(p for p in complex_structure.rglob("*.p3d"))
    original_content = test_file.read_text()
    test_file.write_text("modified content")
    
    # Rescan and verify
    api.scan_directory(test_file.parent.parent.parent, force_rescan=True)
    assert len(api.get_all_assets()) == len(final_assets), \
        "Asset count should remain stable after modification"

def test_parallel_scanning(complex_structure, tmp_path):
    """Test scanning multiple mods in parallel"""
    api = AssetAPI(tmp_path / "cache")
    
    # Get all mod paths
    mod_paths = [p for p in complex_structure.iterdir() if p.is_dir()]
    
    # Scan all at once
    results = api.scan_multiple(mod_paths)
    
    # Verify all assets were cached
    cached = api.get_all_assets()
    total_assets = sum(len(r.assets) for r in results)
    assert len(cached) == total_assets

def test_cross_source_resolution(complex_structure, tmp_path):
    """Test asset resolution across multiple sources"""
    api = AssetAPI(tmp_path / "cache")
    
    # Scan everything
    api.scan_multiple([p for p in complex_structure.iterdir()])
    
    # Test various path formats
    test_cases = [
        "rifle.p3d",                    # Simple filename
        "weapons/rifle.p3d",            # Partial path
        "@mod_a/addons/weapons/rifle.p3d",  # Full path
        "RIFLE.P3D",                    # Case variation
    ]
    
    # All should resolve to the same asset
    results = [api.get_asset(path) for path in test_cases]
    assert all(r is not None for r in results), "All paths should resolve"
    assert len({str(r.path) for r in results}) == 1, "All should resolve to same asset"
