from venv import logger
import pytest
from pathlib import Path
from asset_scanner import AssetAPI


@pytest.fixture
def complex_structure(tmp_path: Path) -> Path:
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


def test_strict_accumulation(complex_structure: Path, tmp_path: Path) -> None:
    """Test strict accumulation of assets across multiple scans"""
    api = AssetAPI()

    # Track what we expect to find
    expected_assets = {}
    
    # Scan each mod directory individually
    for mod_dir in sorted(complex_structure.iterdir()):
        result = api.scan(mod_dir)
        
        logger.debug(f"Scanned {mod_dir.name}, found {len(result.assets)} assets")
        
        # Store expected assets for this mod
        mod_name = mod_dir.name
        expected_assets[mod_name] = {
            str(asset.path): asset for asset in result.assets
        }
        
        # Verify all previously scanned assets are still present
        cached = api.get_all_assets()
        
        logger.debug(f"Total cached assets after scanning {mod_name}: {len(cached)}")
        logger.debug(f"Asset sources in cache: {set(a.source for a in cached)}")
        
        cached_paths = {str(asset.path) for asset in cached}
        
        for prev_mod, prev_assets in expected_assets.items():
            for path, expected_asset in prev_assets.items():
                assert path in cached_paths, f"Lost asset {path} from {prev_mod}"
                cached_asset = next(a for a in cached if str(a.path) == path)
                assert cached_asset.source == expected_asset.source, (
                    f"Wrong source for {path}: expected {expected_asset.source}, "
                    f"got {cached_asset.source}"
                )
                logger.debug(f"Verified {path} from {cached_asset.source}")


def test_path_resolution(complex_structure: Path, tmp_path: Path) -> None:
    """Test asset resolution with different path formats"""
    api = AssetAPI()
    api.scan(complex_structure)

    # Test various path formats for the same asset
    rifle_paths = [
        "weapons/rifle.p3d",
        "./weapons/rifle.p3d",
        "@mod_a/addons/weapons/rifle.p3d",
        "rifle.p3d",  # Just filename
    ]

    for path in rifle_paths:
        asset = api.get_asset(path)
        assert asset is not None, f"Failed to resolve path: {path}"
        assert "rifle.p3d" in str(asset.path), f"Wrong asset found for {path}"


def test_incremental_updates(complex_structure: Path, tmp_path: Path) -> None:
    """Test scanning with file modifications"""
    api = AssetAPI()
    
    # Initial scan
    api.scan(complex_structure)
    initial_count = len(api.get_all_assets())
    
    # Modify an existing file
    test_file = next(complex_structure.rglob("*.p3d"))
    test_file.write_text("modified content")
    
    # Rescan
    api.scan(complex_structure)
    
    # Count should remain the same
    assert len(api.get_all_assets()) == initial_count
