"""Cache management and persistence tests"""
import pytest
from asset_scanner import AssetAPI
from asset_scanner.config import APIConfig


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
            "addons/shared.paa",
            "addons/unique3.paa"
        ]
    }

    for mod, files in mods.items():
        mod_dir = base / mod
        mod_dir.mkdir()
        for file in files:
            file_path = mod_dir / file
            file_path.parent.mkdir(exist_ok=True)
            file_path.write_text(f"content for {file}")

    return base


def test_cache_accumulation(mod_structure, tmp_path) -> None:
    """Test cache accumulation during scanning"""
    api = AssetAPI(tmp_path / "cache")

    total_assets = 0
    mod_dirs = [d for d in mod_structure.iterdir() if d.is_dir()]

    print("\nTest structure contains:")
    for mod_dir in mod_dirs:
        print(f"\n{mod_dir.name}:")
        for f in mod_dir.rglob('*'):
            if f.is_file():
                print(f"  {f.relative_to(mod_dir)}")

    for mod_dir in mod_dirs:
        result = api.scan_directory(mod_dir)
        total_assets += len(result.assets)

        cached = api.get_all_assets()
        assert len(cached) == total_assets

        print(f"\nAfter scanning {mod_dir.name}:")
        print(f"Cache contains {len(cached)} assets:")
        for asset in sorted(cached, key=lambda x: str(x.path)):
            print(f"  {asset.path} (source: {asset.source})")

    assert len(api.get_all_assets()) == 7


def test_cache_invalidation(mod_structure, tmp_path) -> None:
    """Test cache updates on file changes"""
    api = AssetAPI(tmp_path / "cache")

    mod_dir = mod_structure / "@mod1"
    api.scan_directory(mod_dir)
    initial_assets = api.get_all_assets()

    test_file = mod_dir / "addons/texture1.paa"
    test_file.write_text("modified content")

    api.scan_directory(mod_dir, force_rescan=True)
    updated_assets = api.get_all_assets()

    assert len(updated_assets) == len(initial_assets)


def test_multiple_scans_consistency(mod_structure, tmp_path) -> None:
    """Test consistency when scanning multiple times"""
    api = AssetAPI(tmp_path / "cache")

    paths = list(p for p in mod_structure.iterdir() if p.is_dir())

    api.scan_multiple(paths)
    first_scan = {str(a.path): a.source for a in api.get_all_assets()}

    api = AssetAPI(tmp_path / "cache")
    api.scan_multiple(reversed(paths))
    second_scan = {str(a.path): a.source for a in api.get_all_assets()}

    assert first_scan == second_scan


def test_game_folder_cache(mod_structure, tmp_path) -> None:
    """Test game folder scanning with cache"""
    api = AssetAPI(tmp_path / "cache")

    api.add_folder("GameRoot", mod_structure)

    results = api.scan_game_folders(mod_structure)

    for result in results:
        for asset in result.assets:
            assert asset.source == "GameRoot"

    cached = api.get_all_assets()
    assert all(a.source == "GameRoot" for a in cached)


def test_cache_size_limits(mod_structure, tmp_path) -> None:
    """Test cache size enforcement"""
    config = APIConfig(cache_max_size=2)
    api = AssetAPI(tmp_path / "cache", config=config)

    with pytest.raises(ValueError, match=r"Cache size exceeded: \d+ > \d+"):
        api.scan_directory(mod_structure)


def test_cache_persistence(api, mod_structure, tmp_path) -> None:
    """Test cache export/import"""
    api.scan_directory(mod_structure)
    original_assets = api.get_all_assets()

    cache_file = tmp_path / "cache_export"
    api.export_cache(cache_file)

    new_api = AssetAPI(tmp_path / "cache2")
    new_api.import_cache(cache_file)

    imported_assets = new_api.get_all_assets()
    assert len(imported_assets) == len(original_assets)

    original_paths = {str(a.path) for a in original_assets}
    imported_paths = {str(a.path) for a in imported_assets}
    assert original_paths == imported_paths


def test_cache_clear(api, mod_structure) -> None:
    """Test cache clearing"""
    api.scan_directory(mod_structure)
    assert len(api.get_all_assets()) > 0

    api.clear_cache()
    assert len(api.get_all_assets()) == 0
