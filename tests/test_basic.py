"""Basic functionality tests"""
import pytest
from pathlib import Path
from asset_scanner import AssetAPI, Asset
from asset_scanner.class_models import ParsedClassData

@pytest.fixture
def api(tmp_path: Path) -> AssetAPI:
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

@pytest.fixture
def sample_assets(tmp_path: Path) -> Path:
    """Create sample asset structure for basic tests"""
    base = tmp_path / "basic_assets"
    base.mkdir()

    files = {
        "models/test.p3d": "model data",
        "textures/color.paa": "texture data",
        "scripts/main.sqf": "script data"
    }

    for path, content in files.items():
        full_path = base / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    return base

def test_basic_scanning(api: AssetAPI, sample_assets: Path) -> None:
    """Test basic asset scanning functionality"""
    result = api.scan_directory(sample_assets)

    assert isinstance(result.assets, set)
    assert len(result.assets) == 3
    assert all(isinstance(asset, Asset) for asset in result.assets)

    extensions = {a.path.suffix for a in result.assets}
    assert extensions == {'.p3d', '.paa', '.sqf'}

    if hasattr(result, 'class_data'):
        assert isinstance(result.class_data, (ParsedClassData, type(None)))
