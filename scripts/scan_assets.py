import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from asset_scanner.api import AssetAPI
from asset_scanner.config import APIConfig

@dataclass
class ScannerConfig:
    """Scanner configuration settings"""
    input_paths: List[Path]
    output_dir: Path
    workers: int = 60
    cache_size: int = 1_000_000
    verbose: bool = False
    report_formats: List[str] = field(default_factory=lambda: ["rich", "json", "text"])

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
        choices=["rich", "json", "text"],
        default=["rich", "json", "text"],
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

def setup_logging(output_dir: Path, verbose: bool) -> tuple[logging.Logger, Console]:
    """Setup logging and console output"""
    console = Console()
    
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
    
    return logger, console

def create_progress() -> Progress:
    """Create Rich progress display"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=Console()
    )

def scan_directories(
    config: ScannerConfig, 
    logger: logging.Logger
) -> Optional[dict]:
    """Perform asset scanning using AssetAPI"""
    try:
        # Normalize input paths
        input_paths = [p.resolve() for p in config.input_paths]
        
        api_config = APIConfig(
            cache_max_size=config.cache_size,
            max_workers=config.workers
        )
        api = AssetAPI(config.output_dir, api_config)
        
        with create_progress() as progress:
            scan_task = progress.add_task(
                "[cyan]Scanning directories...",
                total=len(input_paths)
            )
            
            all_results = []
            total_pbos = 0
            total_classes = 0 
            total_assets = 0
            all_classes = []
            
            for path in input_paths:
                logger.info(f"Scanning directory: {path}")
                results = api.parallel_scan_directories([path], path.name)
                
                if not results:
                    logger.warning(f"No results found in {path}")
                    progress.advance(scan_task)
                    continue
                    
                # Store complete results for this directory
                folder_assets = []
                folder_pbos = []
                folder_loose = []
                folder_classes = []
                
                for r in results:
                    if hasattr(r, 'pbo_path'):
                        total_pbos += 1
                        folder_pbos.append(r)
                    else:
                        folder_loose.append(r)
                        
                    folder_assets.extend(r.assets)
                    total_assets += len(r.assets)
                    
                    # Handle class data with proper type checking
                    if hasattr(r, 'classes') and r.classes:
                        for class_name, class_data in r.classes.items():
                            try:
                                class_info = {
                                    "name": class_name,
                                    "source": str(r.source),
                                    "parent": None,  # Default value
                                    "properties": {}  # Default empty dict
                                }

                                # Handle different class_data types
                                if hasattr(class_data, 'parent'):
                                    class_info["parent"] = class_data.parent
                                elif isinstance(class_data, dict):
                                    class_info["parent"] = class_data.get('parent')
                                elif isinstance(class_data, (set, frozenset)):
                                    # Handle set case - no parent info
                                    pass

                                # Handle properties similarly
                                if hasattr(class_data, 'properties'):
                                    props = class_data.properties
                                elif isinstance(class_data, dict):
                                    props = class_data.get('properties', {})
                                else:
                                    props = {}

                                # Convert properties
                                class_info["properties"] = {
                                    name: getattr(prop, 'value', prop)
                                    for name, prop in props.items()
                                }

                                folder_classes.append(class_info)
                                total_classes += 1
                            except Exception as e:
                                logger.debug(f"Skipping class {class_name}: {e}")
                                continue
                
                # Add folder results with accurate counts
                folder_results = {
                    "path": str(path),
                    "pbos": [str(p.pbo_path) for p in folder_pbos],
                    "loose_files": [str(f.path) for f in folder_loose],
                    "total_assets": len(folder_assets),
                    "total_classes": len(folder_classes),
                    "classes": folder_classes
                }
                all_results.append(folder_results)
                progress.advance(scan_task)
            
            if not all_results:
                logger.error("No valid results found in any directory")
                return None
                
            results = {
                "folders": all_results,
                "summary": {
                    "total_directories": len(input_paths),
                    "total_assets": total_assets,
                    "total_pbos": total_pbos,
                    "total_classes": total_classes,
                    "total_loose_files": len([r for r in all_results if not r["pbos"]])
                }
            }
            
            return results
            
    except Exception as e:
        logger.error(f"Scanning failed: {e}", exc_info=True)
        return None

def main() -> int:
    """Main entry point"""
    try:
        config = parse_arguments()
        
        # Validate output directory 
        try:
            config.output_dir.mkdir(parents=True, exist_ok=True)
            if not config.output_dir.is_dir():
                raise ValueError(f"Output path exists but is not a directory: {config.output_dir}")
        except Exception as e:
            print(f"Error creating output directory: {e}")
            return 1
            
        logger, console = setup_logging(config.output_dir, config.verbose)
        
        invalid_paths = [p for p in config.input_paths if not p.exists()]
        if invalid_paths:
            logger.error(f"Invalid input paths: {invalid_paths}")
            return 1
            
        results = scan_directories(config, logger)
        if not results:
            return 1
            
        from modules.report import print_summary, save_report
        
        with create_progress() as progress:
            # Rich console output
            if "rich" in config.report_formats:
                report_task = progress.add_task(
                    "[green]Generating console report...",
                    total=1
                )
                print_summary(results, console)
                progress.advance(report_task)
            
            # File reports
            formats = [f for f in config.report_formats if f != "rich"]
            if formats:
                report_task = progress.add_task(
                    "[green]Saving report files...",
                    total=len(formats)
                )
                for fmt in formats:
                    save_report(results, config.output_dir, logger, formats=[fmt])
                    progress.advance(report_task)
            
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
