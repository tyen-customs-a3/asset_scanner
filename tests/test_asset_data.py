import pytest
import logging
from pathlib import Path
from pytest import LogCaptureFixture

from asset_scanner import AssetAPI
from .conftest import PBO_FILES, MIRRORFORM_PBO_FILE

logger = logging.getLogger(__name__)

def test_scanning_all_addons(sample_data_path: Path, tmp_path: Path) -> None:
    """Test scanning all sample addons together"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan(sample_data_path)
    
    assert result.assets, "Should find assets"
    assert result.source == sample_data_path.name

    logger.debug("Scan results:")
    logger.debug(f"  Source: {result.source}")
    logger.debug(f"  Assets: {len(result.assets)}")
    logger.debug(f"  Files: {[str(a.path) for a in result.assets]}")


def test_asset_patterns(sample_data_path: Path, tmp_path: Path) -> None:
    """Test pattern-based asset filtering"""
    api = AssetAPI(tmp_path / "cache")
    api.scan(sample_data_path)

    models = api.find_by_extension('.p3d')
    textures = api.find_by_extension('.paa')

    assert len(models) > 0, "Should find model files"
    assert len(textures) > 0, "Should find texture files"

    # Test specific patterns
    mirror = api.find_by_pattern(r".*mirror.*")
    headband = api.find_by_pattern(r".*headband.*")

    assert len(mirror) > 0, "Should find mirror assets"
    assert len(headband) > 0, "Should find headband assets"
