"""Basic functionality tests"""
import pytest
from pathlib import Path
from asset_scanner import AssetAPI, Asset

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
