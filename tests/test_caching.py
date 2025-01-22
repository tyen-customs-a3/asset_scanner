"""Cache management and persistence tests"""
import pytest
from pathlib import Path
from asset_scanner import AssetAPI, APIConfig

@pytest.fixture
def api(tmp_path):
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

@pytest.fixture
def mod_structure(tmp_path):
    """Create a test mod structure with multiple addons"""
    base = tmp_path / "mods"
    base.mkdir()
    
    # Create multiple mod folders
    mods = {
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
            "addons/shared.paa",  # Same filename in multiple mods
            "addons/unique3.paa"
        ]
    }
    
    # Create the structure
    for mod, files in mods.items():
        mod_dir = base / mod
        mod_dir.mkdir()
        for file in files:
            file_path = mod_dir / file
            file_path.parent.mkdir(exist_ok=True)
            file_path.write_text(f"content for {file}")
            
    return base

def test_cache_accumulation(mod_structure, tmp_path):
    """Test cache accumulation during scanning"""
    api = AssetAPI(tmp_path / "cache")
    
    # Scan mods one by one
    total_assets = 0
    mod_dirs = [d for d in mod_structure.iterdir() if d.is_dir()]
    
    # Debug: Print test files
    print("\nTest structure contains:")
    for mod_dir in mod_dirs:
        print(f"\n{mod_dir.name}:")
        for f in mod_dir.rglob('*'):
            if f.is_file():
                print(f"  {f.relative_to(mod_dir)}")
    
    for mod_dir in mod_dirs:
        result = api.scan_directory(mod_dir)
        total_assets += len(result.assets)
        
        # Verify cache contains all assets scanned so far
        cached = api.get_all_assets()
        assert len(cached) == total_assets
        
        # Debug: Print cache contents after each scan
        print(f"\nAfter scanning {mod_dir.name}:")
        print(f"Cache contains {len(cached)} assets:")
        for asset in sorted(cached, key=lambda x: str(x.path)):
            print(f"  {asset.path} (source: {asset.source})")
    
    # Verify final total - updated to match actual file count
    assert len(api.get_all_assets()) == 7  # Should match total files from all mods

def test_cache_invalidation(mod_structure, tmp_path):
    """Test cache updates on file changes"""
    api = AssetAPI(tmp_path / "cache")
    
    # Initial scan
    mod_dir = mod_structure / "@mod1"
    api.scan_directory(mod_dir)
    initial_assets = api.get_all_assets()
    
    # Modify a file
    test_file = mod_dir / "addons/texture1.paa"
    test_file.write_text("modified content")
    
    # Force rescan
    api.scan_directory(mod_dir, force_rescan=True)
    updated_assets = api.get_all_assets()
    
    # Cache should maintain same number of assets
    assert len(updated_assets) == len(initial_assets)

def test_multiple_scans_consistency(mod_structure, tmp_path):
    """Test consistency when scanning multiple times"""
    api = AssetAPI(tmp_path / "cache")
    
    # Scan all mods multiple times in different orders
    paths = list(p for p in mod_structure.iterdir() if p.is_dir())
    
    # First order
    api.scan_multiple(paths)
    first_scan = {str(a.path): a.source for a in api.get_all_assets()}
    
    # Clear and scan in reverse order
    api = AssetAPI(tmp_path / "cache")
    api.scan_multiple(reversed(paths))
    second_scan = {str(a.path): a.source for a in api.get_all_assets()}
    
    # Results should be identical regardless of scan order
    assert first_scan == second_scan

def test_game_folder_cache(mod_structure, tmp_path):
    """Test game folder scanning with cache"""
    api = AssetAPI(tmp_path / "cache")
    
    # Register game folder
    api.add_folder("GameRoot", mod_structure)
    
    # Scan game folders
    results = api.scan_game_folders(mod_structure)
    
    # All assets should have GameRoot as source
    for result in results:
        for asset in result.assets:
            assert asset.source == "GameRoot"
    
    # Cache should maintain source attribution
    cached = api.get_all_assets()
    assert all(a.source == "GameRoot" for a in cached)

def test_progress_callback(mod_structure, tmp_path):
    """Test progress callback functionality"""
    api = AssetAPI(tmp_path / "cache")
    progress_updates = []

    def progress_callback(file_path):
        progress_updates.append(file_path)

    api._scanner.progress_callback = progress_callback

    # Scan mods
    api.scan_multiple([p for p in mod_structure.iterdir() if p.is_dir()])

    # Verify progress updates were called
    assert len(progress_updates) > 0, "Progress callback should be called"
    assert all(isinstance(p, str) for p in progress_updates), "Progress updates should be strings"

def test_cache_size_limits(mod_structure, tmp_path):
    """Test cache size enforcement"""
    config = APIConfig(cache_max_size=2)  # Very small limit
    api = AssetAPI(tmp_path / "cache", config=config)
    
    with pytest.raises(ValueError, match=r"Cache size exceeded: \d+ > \d+"):  # Updated to match actual error message
        api.scan_directory(mod_structure)

def test_cache_persistence(api, mod_structure, tmp_path):
    """Test cache export/import"""
    # Initial scan
    api.scan_directory(mod_structure)
    original_assets = api.get_all_assets()
    
    # Export cache
    cache_file = tmp_path / "cache_export"
    api.export_cache(cache_file)
    
    # New API instance
    new_api = AssetAPI(tmp_path / "cache2")
    new_api.import_cache(cache_file)
    
    # Compare assets
    imported_assets = new_api.get_all_assets()
    assert len(imported_assets) == len(original_assets)
    
    # Compare paths
    original_paths = {str(a.path) for a in original_assets}
    imported_paths = {str(a.path) for a in imported_assets}
    assert original_paths == imported_paths

def test_cache_clear(api, mod_structure):
    """Test cache clearing"""
    api.scan_directory(mod_structure)
    assert len(api.get_all_assets()) > 0
    
    api.clear_cache()
    assert len(api.get_all_assets()) == 0
