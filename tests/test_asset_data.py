import pytest
from asset_scanner import AssetAPI
import logging
from pathlib import Path
from typing import Any, Set
from pytest import LogCaptureFixture

from asset_scanner.pbo_extractor import PboExtractor

from .conftest import EXPECTED_PATHS, MIRRORFORM_PBO_FILE, PBO_FILES, PBO_NAME_MAP, PBO_PATHS, SOURCE_MAPPING

logger = logging.getLogger(__name__)


def test_scanning_all_addons(sample_data_path: Path, tmp_path: Path) -> None:
    """Test scanning all sample addons together"""
    api = AssetAPI(tmp_path / "cache")

    addon_paths = sorted([
        p for p in sample_data_path.iterdir()
        if p.is_dir() and p.name.startswith("@")
    ])

    logger.debug("Found addon directories:")
    for p in addon_paths:
        logger.debug(f"  {p.name}")

    results = api.scan_multiple(addon_paths)

    logger.debug("Scan results:")
    for result in results:
        logger.debug(f"  Source: {result.source}")
        logger.debug(f"  Assets: {len(result.assets)}")
        logger.debug(f"  Files: {[str(a.path) for a in result.assets]}")

    addon_names = {p.name.strip('@') for p in addon_paths}

    expected_addons = {"tc_rhs_headband", "tc_mirrorform", "em"}

    logger.debug(f"Found addon names: {addon_names}")
    logger.debug(f"Expected addon names: {expected_addons}")
    assert addon_names == expected_addons


def test_asset_patterns(sample_data_path: Path, tmp_path: Path) -> None:
    """Test pattern-based asset filtering"""
    api = AssetAPI(tmp_path / "cache")

    api.scan_directory(sample_data_path)

    models = api.find_by_extension('.p3d')
    textures = api.find_by_extension('.paa')

    assert len(models) > 0, "Should find model files"
    assert len(textures) > 0, "Should find texture files"

    mirror = api.find_by_pattern(r".*mirror.*")
    headband = api.find_by_pattern(r".*headband.*")

    assert len(mirror) > 0, "Should find mirror assets"
    assert len(headband) > 0, "Should find headband assets"


def test_pbo_path_handling(mirror_addon_path: Path, tmp_path: Path) -> None:
    """Test PBO path normalization"""
    api = AssetAPI(tmp_path / "cache")
    result = api.scan_directory(mirror_addon_path)

    scanned_paths = {str(a.path).replace('\\', '/').removeprefix('@tc_mirrorform/addons/').removeprefix('tc_mirrorform/addons/') for a in result.assets}

    prefix = "tc/mirrorform"
    for path in scanned_paths:
        if not path.startswith(prefix):
            assert path.endswith(('.paa', '.p3d')), f"Non-prefixed path: {path}"

    assert all(a.source == "tc_mirrorform" for a in result.assets)


def test_pbo_prefix_handling(tmp_path: Path) -> None:
    """Test correct handling of PBO prefixes"""
    api = AssetAPI(tmp_path / "cache")

    for pbo_name, pbo_path in PBO_PATHS.items():
        if not pbo_path.exists():
            pytest.skip(f"PBO file not found: {pbo_path}")

        result = api.scan_pbo(pbo_path)
        mapped_name = PBO_NAME_MAP[pbo_name]
        assert result.prefix == PBO_FILES[mapped_name]['prefix']

        prefix_parts = PBO_FILES[mapped_name]['prefix'].replace('\\', '/').split('/')
        for asset in result.assets:
            path_str = str(asset.path).replace('\\', '/')
            assert path_str.startswith('/'.join(prefix_parts))


def test_pbo_content_extraction(sample_data_path: Path, caplog: LogCaptureFixture) -> None:
    """Test direct PBO content extraction and prefix handling"""
    caplog.set_level(logging.DEBUG)

    mirror_pbo = MIRRORFORM_PBO_FILE
    assert mirror_pbo.exists(), f"Test PBO file not found: {mirror_pbo}"

    from asset_scanner.pbo_extractor import PboExtractor
    extractor = PboExtractor()

    return_code, stdout, stderr = extractor.list_contents(mirror_pbo)
    assert return_code == 0, f"PBO listing failed: {stderr}"

    logger.debug("\nRaw PBO Listing Output:")
    for line in stdout.splitlines():
        logger.debug(f"  {line}")

    prefix = extractor.extract_prefix(stdout)
    logger.debug(f"\nExtracted Prefix: {prefix}")
    assert prefix == "tc\\mirrorform" or prefix == "tc/mirrorform", f"Unexpected prefix: {prefix}"

    return_code, code_files, all_paths = extractor.scan_pbo_contents(mirror_pbo)
    assert return_code == 0, "PBO scanning failed"

    logger.debug("\nNormalized Paths:")
    for path in sorted(all_paths):
        logger.debug(f"  {path}")

    expected_paths = {
        'logo.paa',
        'logo_small.paa',
        'uniform/mirror.p3d',
        'uniform/black.paa'
    }

    prefix_with_slash = prefix.replace('\\', '/') + '/'
    scanned_paths = {
        p.replace('\\', '/').removeprefix(prefix_with_slash)
        for p in all_paths
        if not p.endswith('.rvmat')
    }

    logger.debug("\nProcessed paths for comparison:")
    logger.debug(f"Expected: {sorted(expected_paths)}")
    logger.debug(f"Found: {sorted(scanned_paths)}")

    for path in expected_paths:
        assert path in scanned_paths, f"Missing expected path: {path}"

    full_paths = {p.replace('\\', '/') for p in all_paths}
    for path in full_paths:
        if not path.endswith(('.bin', '.rvmat')):
            assert path.startswith(prefix.replace('\\', '/')), f"Path missing prefix: {path}"


def test_dump_pbo_contents(capfd: pytest.CaptureFixture) -> None:
    """Dump the contents of each test PBO to console"""
    extractor = PboExtractor()

    for name, info in PBO_FILES.items():
        pbo_path = info['path']
        if not pbo_path.exists():
            print(f"\nSkipping missing PBO: {pbo_path}")
            continue

        print(f"\n{'='*80}")
        print(f"Scanning PBO: {name}")
        print(f"Path: {pbo_path}")
        print(f"Expected prefix: {info['prefix']}")
        print(f"Source: {info['source']}")
        print(f"{'='*80}\n")

        # Get PBO contents
        returncode, stdout, stderr = extractor.list_contents(pbo_path)
        if returncode != 0:
            print(f"Failed to list contents: {stderr}")
            continue

        # Extract and show prefix
        prefix = extractor.extract_prefix(stdout)
        print(f"Detected prefix: {prefix}")

        # Get detailed contents
        returncode, code_files, all_paths = extractor.scan_pbo_contents(pbo_path)
        if returncode != 0:
            print("Failed to scan PBO contents")
            continue

        # Show all paths
        print("\nAll files:")
        for path in sorted(all_paths):
            print(f"  {path}")

        # # Show code files
        # if code_files:
        #     print("\nCode files found:")
        #     for path, content in code_files.items():
        #         print(f"\n  {path}:")
        #         print(f"  {'-'*40}")
        #         for line in content.splitlines()[:10]:  # Show first 10 lines
        #             print(f"  {line}")
        #         if len(content.splitlines()) > 10:
        #             print("  ... (truncated)")
        #         print(f"  {'-'*40}")

        # Compare with expected paths
        print("\nPath comparison:")
        expected = info['expected']
        if prefix is None:
            prefix = ""

        # Process paths:
        # 1. Remove prefix from each path
        # 2. Remove leading slash if present
        # 3. Exclude .bin, .cpp, and .hpp files
        found = set()
        for path in all_paths:
            if path.endswith(('.bin', '.cpp', '.hpp')):
                continue
            # Remove prefix and ensure no leading slash
            relative_path = path[len(prefix):].lstrip('/')
            found.add(relative_path)

        extra = found - expected
        missing = expected - found

        if extra:
            print("\nExtra files found:")
            for path in sorted(extra):
                print(f"  + {path}")

        if missing:
            print("\nMissing expected files:")
            for path in sorted(missing):
                print(f"  - {path}")

        # Force output to be displayed
        captured = capfd.readouterr()
        print(captured.out)
