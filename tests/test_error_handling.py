"""Error handling and recovery tests"""
import pytest
from pathlib import Path
from asset_scanner import AssetAPI, APIConfig
from unittest.mock import Mock

@pytest.fixture
def api(tmp_path):
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

@pytest.fixture
def edge_case_structure(tmp_path):
    """Create error-triggering file structure"""
    base = tmp_path / "error_test"
    base.mkdir()
    
    # Create problematic files
    (base / "bad.p3d").write_bytes(b'\x00\xFF' * 1000)  # Invalid binary content
    (base / ".invalid").write_text("invalid content")
    
    return base

def test_error_handler():
    """Test error handler configuration"""
    error_handler = Mock()
    config = APIConfig(error_handler=error_handler)
    api = AssetAPI(Path("test"), config=config)

    # Trigger error with nonexistent path
    try:
        api.scan_directory(Path("nonexistent"))
    except FileNotFoundError:
        pass

    assert error_handler.called
    assert isinstance(error_handler.call_args[0][0], Exception)

def test_error_recovery(api, edge_case_structure):
    """Test recovery from scan errors"""
    errors = []
    
    def error_handler(e: Exception):
        print(f"Debug: Error caught: {e}")  # Debug output
        errors.append(e)
    
    # Update existing API with error handler
    api.config = APIConfig(
        error_handler=error_handler,
        cache_max_size=api.config.cache_max_size,
        scan_timeout=1  # Short timeout to trigger errors
    )
    
    try:
        api.scan_directory(edge_case_structure)
    except Exception as e:
        print(f"Debug: Expected exception: {type(e).__name__}: {e}")
    
    print(f"Debug: Error count: {len(errors)}")
    print(f"Debug: Errors: {errors}")
    
    assert len(errors) > 0, "Error handler should have been called"
