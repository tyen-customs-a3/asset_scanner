import logging
from pathlib import Path
import pytest
from asset_scanner.pbo_extractor import PboExtractor
from tests.conftest import PBO_FILES

# Configure logging to output directly to console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s',  # Simplified format for readability
    force=True  # Override any existing logging configuration
)

logger = logging.getLogger(__name__)


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
