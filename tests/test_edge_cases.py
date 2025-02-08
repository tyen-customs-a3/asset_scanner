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
def edge_case_structure(tmp_path):
    """Create structure with edge case filenames and paths"""
    mod_path = tmp_path / "@Test Mod With Spaces"
    mod_path.mkdir(parents=True)
    addon_path = mod_path / "addons"
    addon_path.mkdir()

    test_files = {
        addon_path / "file with spaces.p3d": b"data",
        addon_path / "über_weapon.p3d": b"data",
        addon_path / "mixed~!@#$%^&()_+.paa": b"data",
        addon_path / "UPPERCASE.PAA": b"data",
        addon_path / "lowercase.paa": b"data",
        addon_path / "MixedCase.Paa": b"data",
        addon_path / "deep/nested/folder/structure/file.p3d": b"data",
        addon_path / "empty.sqf": b"",
        addon_path / ".hidden.paa": b"data",
        addon_path / "multiple.texture.paa": b"data",
        addon_path / "regular.paa": b"original content"
    }

    for path, content in test_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    try:
        (addon_path / "symlink.paa").symlink_to(addon_path / "regular.paa")
    except:
        pass

    return tmp_path


def test_special_characters(api, edge_case_structure):
    """Test handling of special characters in filenames"""
    mod_path = edge_case_structure / "@Test Mod With Spaces"
    result = api.scan_directory(mod_path)

    assert api.has_asset("file with spaces.p3d")

    assert api.has_asset("über_weapon.p3d")

    assert api.has_asset("mixed~!@#$%^&()_+.paa")


def test_case_sensitivity_edge_cases(api, edge_case_structure):
    """Test various case sensitivity scenarios"""
    mod_path = edge_case_structure / "@Test Mod With Spaces"
    api.scan_directory(mod_path)

    assert api.has_asset("UPPERCASE.PAA")
    assert api.has_asset("uppercase.paa")
    assert api.has_asset("LOWERCASE.PAA")

    assert api.get_asset("UPPERCASE.PAA", case_sensitive=True) is not None
    assert api.get_asset("uppercase.paa", case_sensitive=True) is None


def test_path_depth_handling(api, edge_case_structure):
    """Test handling of deeply nested paths"""
    mod_path = edge_case_structure / "@Test Mod With Spaces"
    api.scan_directory(mod_path)

    deep_path = "deep/nested/folder/structure/file.p3d"

    assert api.has_asset(deep_path)

    assert api.has_asset("structure/file.p3d")
    assert api.has_asset("file.p3d")


def test_empty_and_special_files(api, edge_case_structure):
    """Test handling of empty and special files"""
    mod_path = edge_case_structure / "@Test Mod With Spaces"
    api.scan_directory(mod_path)

    assert api.has_asset("empty.sqf")

    assert api.has_asset(".hidden.paa")

    assert api.has_asset("multiple.texture.paa")

    assert not api.has_asset("multiple.texture")
    assert not api.has_asset("multiple")


def test_invalid_inputs(api, edge_case_structure):
    """Test handling of invalid inputs"""
    mod_path = edge_case_structure / "@Test Mod With Spaces"
    api.scan_directory(mod_path)

    assert not api.has_asset("")
    assert not api.has_asset("////")
    assert not api.has_asset("../outside.paa")
    assert not api.has_asset("C:/absolute/path.paa")

    assert not api.has_asset("\0null.paa")
    assert not api.has_asset("*.paa")

    very_long_name = "a" * 255 + ".paa"
    assert not api.has_asset(very_long_name)


def test_symlink_handling(api, edge_case_structure):
    """Test handling of symbolic links"""
    mod_path = edge_case_structure / "@Test Mod With Spaces"
    api.scan_directory(mod_path)

    assert api.has_asset("regular.paa")

    assets = {str(a.path) for a in api.get_all_assets()}
    if "symlink.paa" in assets:
        assert len({a for a in assets if str(a).endswith("regular.paa")}) == 2


def test_concurrent_access(api, edge_case_structure):
    """Test concurrent access to assets"""
    import threading
    import random

    mod_path = edge_case_structure / "@Test Mod With Spaces"
    api.scan_directory(mod_path)

    test_files = ["file with spaces.p3d", "regular.paa", "UPPERCASE.PAA"]
    errors = []

    def worker():
        try:
            for _ in range(100):
                file = random.choice(test_files)
                assert api.has_asset(file)
                asset = api.get_asset(file)
                assert asset is not None
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent access errors: {errors}"


def test_error_recovery(api, edge_case_structure):
    """Test error recovery during scanning"""
    errors = []

    def error_handler(e: Exception):
        print(f"Debug: Error caught: {e}")
        errors.append(e)

    api.config = APIConfig(error_handler=error_handler)

    bad_file = edge_case_structure / "addons" / "bad.p3d"
    bad_file.parent.mkdir(exist_ok=True)
    bad_file.write_bytes(b'\x00\xFF' * 1000000)

    try:
        api.scan_directory(bad_file.parent)
    except Exception as e:
        print(f"Debug: Expected exception: {type(e).__name__}: {e}")

    print(f"Debug: Errors caught: {len(errors)}")
    for err in errors:
        print(f"Debug: Error type: {type(err).__name__}: {err}")

    assert len(errors) > 0, "Error handler should have been called"
    assert isinstance(errors[0], Exception), "Should have caught an exception"


def test_criteria_search(api, edge_case_structure):
    """Test multi-criteria search"""
    api.scan_directory(edge_case_structure)

    criteria = {
        'extension': '.paa',
        'pattern': r'texture|model',
        'source': edge_case_structure.name
    }

    results = api.find_by_criteria(criteria)
    assert all(a.path.suffix.lower() == '.paa' for a in results)
    assert all(('texture' in str(a.path) or 'model' in str(a.path))
               for a in results)
