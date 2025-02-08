import pytest
from asset_scanner import AssetAPI


@pytest.fixture
def complex_structure(tmp_path) -> str:
    """Create a complex nested mod structure"""
    root = tmp_path / "complex_mods"
    root.mkdir()

    structure = {
        "@mod_a": {
            "addons/weapons/rifle.p3d": "rifle data",
            "addons/weapons/rifle.paa": "rifle texture",
            "addons/shared/common.paa": "shared texture 1",
        },
        "@mod_b": {
            "addons/weapons/pistol.p3d": "pistol data",
            "addons/shared/common.paa": "shared texture 2",
        },
        "@mod_c": {
            "addons/weapons/rifle.paa": "different rifle texture",
            "addons/unique/special.p3d": "unique model",
        }
    }

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

    expected_by_mod = {}
    total_unique_paths = set()

    for mod_dir in sorted(complex_structure.iterdir()):
        result = api.scan_directory(mod_dir)
        mod_name = mod_dir.name

        expected_by_mod[mod_name] = {
            str(asset.path): asset for asset in result.assets
        }

        total_unique_paths.update(str(asset.path) for asset in result.assets)

        cached = api.get_all_assets()
        cached_paths = {str(asset.path) for asset in cached}

        for prev_mod, prev_assets in expected_by_mod.items():
            for path, asset in prev_assets.items():
                assert path in cached_paths, f"Lost asset {path} from {prev_mod}"
                cached_asset = next(a for a in cached if str(a.path) == path)
                assert cached_asset.source == asset.source, f"Source changed for {path}"

        assert len(cached) == len(total_unique_paths), \
            f"Cache has {len(cached)} assets, expected {len(total_unique_paths)}"


def test_source_integrity(complex_structure, tmp_path):
    """Test that source attribution remains correct during accumulation"""
    api = AssetAPI(tmp_path / "cache")

    sources = {}
    for mod_dir in complex_structure.iterdir():
        source_name = mod_dir.name.strip('@')
        api.add_folder(source_name, mod_dir)
        sources[source_name] = mod_dir

    results = api.scan_multiple([p for p in complex_structure.iterdir()])

    print("\nDebug: All assets and their sources:")
    for asset in api.get_all_assets():
        print(f"Asset: {asset.path} -> Source: {asset.source}")

    for asset in api.get_all_assets():
        path_parts = str(asset.path).replace('\\', '/').split('/')

        found_source = False
        source_name = asset.source

        for part in path_parts:
            if part.strip('@') == source_name:
                found_source = True
                break

        assert found_source, \
            f"Asset path {asset.path} does not contain its source {source_name}"

        assert source_name in sources, \
            f"Asset {asset.path} has unknown source {source_name}"


def test_duplicate_handling(complex_structure, tmp_path):
    """Test handling of files with same name but different paths"""
    api = AssetAPI(tmp_path / "cache")

    api.scan_multiple([p for p in complex_structure.iterdir()])

    rifle_textures = api.find_by_pattern("rifle.paa$")
    assert len(rifle_textures) == 2, "Should find both rifle textures"

    sources = {asset.source for asset in rifle_textures}
    assert len(sources) == 2, "Textures should have different sources"

    common_textures = api.find_by_pattern("common.paa$")
    assert len(common_textures) == 2, "Should preserve both common textures"


def test_incremental_scanning(complex_structure, tmp_path):
    """Test scanning with updates and modifications"""
    api = AssetAPI(tmp_path / "cache")

    initial_paths = [p for p in complex_structure.iterdir()][:2]
    api.scan_multiple(initial_paths)
    initial_count = len(api.get_all_assets())

    remaining_path = next(p for p in complex_structure.iterdir() if p not in initial_paths)
    api.scan_directory(remaining_path)

    final_assets = api.get_all_assets()
    assert len(final_assets) > initial_count, "Should add new assets"

    test_file = next(p for p in complex_structure.rglob("*.p3d"))
    original_content = test_file.read_text()
    test_file.write_text("modified content")

    api.scan_directory(test_file.parent.parent.parent, force_rescan=True)
    assert len(api.get_all_assets()) == len(final_assets), \
        "Asset count should remain stable after modification"


def test_parallel_scanning(complex_structure, tmp_path):
    """Test scanning multiple mods in parallel"""
    api = AssetAPI(tmp_path / "cache")

    mod_paths = [p for p in complex_structure.iterdir() if p.is_dir()]

    results = api.scan_multiple(mod_paths)

    cached = api.get_all_assets()
    total_assets = sum(len(r.assets) for r in results)
    assert len(cached) == total_assets


def test_cross_source_resolution(complex_structure, tmp_path):
    """Test asset resolution across multiple sources"""
    api = AssetAPI(tmp_path / "cache")

    api.scan_multiple([p for p in complex_structure.iterdir()])

    test_cases = [
        "rifle.p3d",
        "weapons/rifle.p3d",
        "@mod_a/addons/weapons/rifle.p3d",
        "RIFLE.P3D",
    ]

    results = [api.get_asset(path) for path in test_cases]
    assert all(r is not None for r in results), "All paths should resolve"
    assert len({str(r.path) for r in results}) == 1, "All should resolve to same asset"
