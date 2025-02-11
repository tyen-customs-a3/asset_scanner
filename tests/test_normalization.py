from pathlib import Path
from asset_scanner import Asset, AssetAPI
from datetime import datetime

def test_asset_path_normalization() -> None:
    """Test that Asset enforces path normalization"""
    paths = [
        r"test\path\file.paa",
        "test/path/file.paa",
        "/test/path/file.paa",
        "test/path/file.paa/",
        "//test//path//file.paa"
    ]
    
    expected = "test/path/file.paa"
    
    for path in paths:
        asset = Asset(
            path=Path(path),
            source="test",
            last_scan=datetime.now()
        )
        assert asset.normalized_path == expected

def test_source_normalization() -> None:
    """Test that @ prefix is stripped from source"""
    sources = ["test", "@test", "@@test"]
    
    for source in sources:
        asset = Asset(
            path=Path("test.paa"),
            source=source,
            last_scan=datetime.now()
        )
        assert asset.source == "test"

def test_pbo_path_normalization() -> None:
    """Test PBO path normalization"""
    asset = Asset(
        path=Path("test.paa"),
        source="test",
        last_scan=datetime.now(),
        pbo_path=Path("test\\addon.pbo")
    )
    assert str(asset.pbo_path).replace('\\', '/') == "test/addon.pbo"

def test_api_path_handling(tmp_path) -> None:
    """Test API handles different path formats consistently"""
    api = AssetAPI()
    
    # Create test structure
    mod_dir = tmp_path / "test_mod"
    mod_dir.mkdir()
    (mod_dir / "test.paa").write_text("content")
    
    api.scan(mod_dir)
    
    # Different ways to reference the same file
    paths = [
        "test.paa",                    # Just filename
        "./test.paa",                  # Current directory
        "test_mod/test.paa",          # With source
        "test_mod\\test.paa",         # Windows path
        "/test_mod/test.paa",         # Absolute-style
        ".\\test.paa",                # Windows current dir
    ]
    
    # Debug output
    print("\nDebug: Scanned assets:")
    for asset in api.get_all_assets():
        print(f"  {asset.path} (source: {asset.source})")
    
    # Get reference asset
    first_result = api.get_asset(paths[0])
    assert first_result is not None, "Failed to find reference asset"
    
    # Test each path variant
    for path in paths[1:]:
        result = api.get_asset(path)
        assert result is not None, f"Failed to find asset with path: {path}"
        assert result == first_result, f"Mismatch for path: {path}"
        assert str(result.path).replace('\\', '/') == str(first_result.path).replace('\\', '/')
