"""Cache management and persistence tests"""
import pytest
from pathlib import Path
from asset_scanner import AssetAPI
from asset_scanner.config import APIConfig


@pytest.fixture
def mod_structure(tmp_path) -> Path:
    base = tmp_path / "mods"
    base.mkdir()

    mods: dict[str, list[str]] = {
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


def test_cache_persistence(mod_structure: Path, tmp_path: Path) -> None:
    """Test cache persists between scans"""
    api = AssetAPI(tmp_path / "cache")
    
    result1 = api.scan(mod_structure)
    assets1 = {str(a.path) for a in result1.assets}
    
    result2 = api.scan(mod_structure)
    assets2 = {str(a.path) for a in result2.assets}
    
    assert assets1 == assets2, "Cached assets should match between scans"


def test_cache_invalidation(mod_structure: Path, tmp_path: Path) -> None:
    """Test cache updates when files change"""
    api = AssetAPI(tmp_path / "cache")
    
    result = api.scan(mod_structure)
    initial_count = len(result.assets)
    
    # Modify a file
    test_file = next(mod_structure.rglob("*.p3d"))
    test_file.write_text("modified content")
    
    # Rescan
    new_result = api.scan(mod_structure)
    assert len(new_result.assets) == initial_count, "Asset count should remain same"


def test_cache_size_limits(mod_structure: Path, tmp_path: Path) -> None:
    """Test cache size enforcement"""
    config = APIConfig(cache_max_size=2)
    api = AssetAPI(tmp_path / "cache", config=config)

    with pytest.raises(ValueError, match=r"Cache size exceeded"):
        api.scan(mod_structure)


def test_cache_clearing(mod_structure: Path, tmp_path: Path) -> None:
    """Test cache clearing operations"""
    api = AssetAPI(tmp_path / "cache")
    
    result = api.scan(mod_structure)
    assert len(result.assets) > 0
    
    api.clear_cache()
    assert len(api.get_all_assets()) == 0
    
    api.shutdown()
    assert len(api.get_all_assets()) == 0
