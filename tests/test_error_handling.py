"""Error handling and recovery tests"""
import pytest
from pathlib import Path
from asset_scanner import AssetAPI
from unittest.mock import Mock
from asset_scanner.config import APIConfig


@pytest.fixture
def api(tmp_path: Path) -> AssetAPI:
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)


@pytest.fixture
def edge_case_structure(tmp_path) -> Path:
    """Create error-triggering file structure"""
    base = tmp_path / "error_test"
    base.mkdir()

    (base / "bad.p3d").write_bytes(b'\x00\xFF' * 1000)
    (base / ".invalid").write_text("invalid content")

    return base


def test_error_handler() -> None:
    """Test error handler configuration"""
    error_handler = Mock()
    config = APIConfig(error_handler=error_handler)
    api = AssetAPI(Path("test"), config=config)

    try:
        api.scan_directory(Path("nonexistent"))
    except FileNotFoundError:
        pass

    assert error_handler.called
    assert isinstance(error_handler.call_args[0][0], Exception)

