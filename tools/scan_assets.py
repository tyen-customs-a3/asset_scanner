import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set, DefaultDict
from collections import defaultdict

from asset_scanner.api import AssetAPI
from asset_scanner.config import APIConfig
from modules.report import print_summary, save_report


#
# Configuration & Setup
#

@dataclass
class ScannerConfig:
    """Scanner configuration settings"""
    input_paths: List[Path]
    output_dir: Path
    workers: int = 60
    cache_size: int = 1_000_000
    verbose: bool = False
    report_formats: List[str] = field(default_factory=lambda: ["text", "json"])


def parse_arguments() -> ScannerConfig:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Scan directories for game assets and generate reports"
    )
    parser.add_argument(
        "input_paths",
        nargs="+",
        type=Path,
        help="One or more directories to scan"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "scan_results",
        help="Output directory for reports"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=60,
        help="Number of worker threads"
    )
    parser.add_argument(
        "--cache-size",
        type=int,
        default=1_000_000,
        help="Maximum cache size in bytes"
    )
    parser.add_argument(
        "--format",
        nargs="+",
        choices=["json", "text"],
        default=["json", "text"],
        help="Report output formats (default: all)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()
    return ScannerConfig(
        input_paths=args.input_paths,
        output_dir=args.output,
        workers=args.workers,
        cache_size=args.cache_size,
        verbose=args.verbose,
        report_formats=args.format
    )


def setup_logging(output_dir: Path, verbose: bool) -> logging.Logger:
    """Setup logging"""
    output_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("asset_scanner")
    logger.setLevel(log_level)

    file_handler = logging.FileHandler(output_dir / "scan.log")
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s')
    )
    logger.addHandler(console_handler)

    return logger


#
# Scanning Logic
#

def scan_directories(
    config: ScannerConfig,
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    """Perform asset scanning using AssetAPI"""
    try:
        input_paths = [p.resolve() for p in config.input_paths]

        api_config = APIConfig(
            max_cache_size=config.cache_size,
            max_workers=config.workers
        )
        api = AssetAPI(api_config)

        all_results = []
        total_pbos = 0
        total_assets = 0

        for i, path in enumerate(input_paths, 1):
            logger.info(f"Scanning directory {i}/{len(input_paths)}: {path}")
            result = api.scan(path)

            if not result or not result.assets:
                logger.warning(f"No results found in {path}")
                continue

            # Group assets by PBO
            pbo_contents: DefaultDict[str, List[str]] = defaultdict(list)
            loose_files: List[str] = []

            for asset in result.assets:
                if hasattr(asset, 'pbo_path') and asset.pbo_path:
                    pbo_key = str(asset.pbo_path)
                    pbo_contents[pbo_key].append(str(asset.path))
                else:
                    loose_files.append(str(asset.path))

            folder_results: Dict[str, Any] = {
                "path": str(path),
                "source": result.source,
                "scan_time": result.scan_time.isoformat() if result.scan_time else None,
                "pbos": [{
                    "path": pbo_path,
                    "contents": sorted(contents)
                } for pbo_path, contents in pbo_contents.items()],
                "loose_files": sorted(loose_files),
                "total_assets": len(result.assets)
            }

            total_pbos += len(pbo_contents)
            total_assets += len(result.assets)

            all_results.append(folder_results)

        if not all_results:
            logger.error("No valid results found in any directory")
            return None

        results = {
            "folders": all_results,
            "summary": {
                "total_directories": len(input_paths),
                "total_assets": total_assets,
                "total_pbos": total_pbos,
                "total_loose_files": sum(len(r["loose_files"]) for r in all_results)
            }
        }

        return results

    except Exception as e:
        logger.error(f"Scanning failed: {e}", exc_info=True)
        return None


#
# Main Program Flow
#

def main() -> int:
    """Main entry point"""
    try:
        config = parse_arguments()
        logger = setup_logging(config.output_dir, config.verbose)

        invalid_paths = [p for p in config.input_paths if not p.exists()]
        if invalid_paths:
            logger.error(f"Invalid input paths: {invalid_paths}")
            return 1

        results = scan_directories(config, logger)
        if not results:
            return 1

        if "text" in config.report_formats:
            print_summary(results)

        formats = [f for f in config.report_formats]
        if formats:
            logger.info("Saving report files...")
            save_report(results, config.output_dir, logger, formats=formats)

        logger.info(f"Scan completed successfully. Results saved to {config.output_dir}")
        return 0

    except KeyboardInterrupt:
        print("\nScan interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
