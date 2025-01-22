import os
import sys
import json
from pathlib import Path
import tempfile
from datetime import datetime
from typing import Dict, Any
import logging
from tqdm import tqdm

# Add the src directory to Python path
src_path = str(Path(__file__).parent.parent / 'src')
if (src_path not in sys.path):
    sys.path.insert(0, src_path)

from asset_scanner import AssetAPI

DEFAULT_ARMA3_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Arma 3")
DEFAULT_PCA_PATH = Path(r"D:\pca\pcanext")
PROJECT_ROOT = Path(__file__).parent.parent

def ensure_temp_dir() -> Path:
    """Create and return temp directory in project root"""
    temp_dir = PROJECT_ROOT / 'temp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

def generate_report(api: AssetAPI, output_path: Path) -> None:
    """Generate a detailed report focusing on PBO contents"""
    stats = api.get_stats()
    sources = api.get_sources()
    
    # Initialize advanced statistics
    advanced_stats = {
        'total_size': 0,
        'largest_files': [],
        'deepest_paths': [],
        'source_breakdown': {},
        'extension_details': {}
    }
    
    # Group assets by PBO source and path
    pbo_hierarchy = {}
    for source in sources:
        assets = api.get_assets_by_source(source)
        source_pbos = {}
        source_stats = {'total_size': 0, 'file_count': 0, 'avg_file_depth': 0}
        
        for asset in assets:
            # Track source statistics
            source_stats['file_count'] += 1
            file_size = asset.path.stat().st_size if asset.path.exists() else 0
            source_stats['total_size'] += file_size
            path_depth = len(str(asset.path).split('/'))
            source_stats['avg_file_depth'] += path_depth
            
            # Track largest files
            advanced_stats['largest_files'].append((str(asset.path), file_size))
            advanced_stats['total_size'] += file_size
            
            # Track deepest paths
            advanced_stats['deepest_paths'].append((str(asset.path), path_depth))
            
            # Track extension details
            ext = asset.path.suffix.lower()
            if ext not in advanced_stats['extension_details']:
                advanced_stats['extension_details'][ext] = {
                    'count': 0,
                    'total_size': 0,
                    'avg_size': 0,
                    'largest_file': ('', 0)
                }
            ext_stats = advanced_stats['extension_details'][ext]
            ext_stats['count'] += 1
            ext_stats['total_size'] += file_size
            if file_size > ext_stats['largest_file'][1]:
                ext_stats['largest_file'] = (str(asset.path), file_size)
            
            # Continue with existing PBO grouping logic
            if not asset.pbo_path:
                continue
                
            pbo_key = str(asset.pbo_path)
            if pbo_key not in source_pbos:
                source_pbos[pbo_key] = {
                    'source': source,
                    'path': str(asset.pbo_path),
                    'files': [],
                    'extensions': {},
                    'file_count': 0
                }
            
            # Add file info with proper path handling
            if str(asset.path) != pbo_key:  # Don't include PBO itself
                rel_path = str(asset.path).split('/', 1)[1] if '/' in str(asset.path) else str(asset.path)
                source_pbos[pbo_key]['files'].append(rel_path)
                
                # Track extensions
                ext = asset.path.suffix.lower()
                source_pbos[pbo_key]['extensions'][ext] = source_pbos[pbo_key]['extensions'].get(ext, 0) + 1
                source_pbos[pbo_key]['file_count'] += 1
        
        if source_pbos:
            pbo_hierarchy[source] = source_pbos
        
        # Finalize source statistics
        source_stats['avg_file_depth'] /= source_stats['file_count'] if source_stats['file_count'] > 0 else 1
        advanced_stats['source_breakdown'][source] = source_stats
    
    # Finalize advanced statistics
    advanced_stats['largest_files'] = sorted(advanced_stats['largest_files'], key=lambda x: x[1], reverse=True)[:10]
    advanced_stats['deepest_paths'] = sorted(advanced_stats['deepest_paths'], key=lambda x: x[1], reverse=True)[:10]
    
    # Calculate averages for extension details
    for ext_stats in advanced_stats['extension_details'].values():
        ext_stats['avg_size'] = ext_stats['total_size'] / ext_stats['count']

    report = {
        "scan_time": datetime.now().isoformat(),
        "summary": {
            "total_assets": stats['total_assets'],
            "total_sources": len(sources),
            "total_size_bytes": advanced_stats['total_size'],
            "extensions": stats['by_extension']
        },
        "advanced_stats": advanced_stats,
        "sources": pbo_hierarchy
    }
    
    # Write detailed report
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, sort_keys=True)
    
    # Print enhanced summary
    print("\nAdvanced Scan Summary:")
    print(f"Total Assets: {stats['total_assets']}")
    print(f"Total Size: {advanced_stats['total_size'] / (1024*1024):.2f} MB")
    print(f"Total Sources: {len(sources)}")
    
    print("\nTop 5 Largest Files:")
    for path, size in advanced_stats['largest_files'][:5]:
        print(f"  {path}: {size / (1024*1024):.2f} MB")
    
    print("\nExtension Overview:")
    for ext, details in advanced_stats['extension_details'].items():
        print(f"  {ext}:")
        print(f"    Count: {details['count']}")
        print(f"    Average Size: {details['avg_size'] / 1024:.2f} KB")
    
    print(f"\nDetailed report written to: {output_path}")

def scan_locations(api: AssetAPI, arma_path: Path, pca_path: Path, logger: logging.Logger) -> None:
    """Scan both Arma 3 and PCA directories using core API"""
    # Add game directories
    if arma_path.exists():
        logger.info(f"Scanning Arma 3 directory: {arma_path}")
        api.add_folder("Arma3", arma_path)
        results = api.scan_game_folders(arma_path)
        logger.info(f"Found {sum(len(r.assets) for r in results)} assets in Arma 3")
        
    # if pca_path.exists():
    #     logger.info(f"Scanning PCA directory: {pca_path}")
    #     api.add_folder("PCA", pca_path)
    #     results = api.scan_game_folders(pca_path)
    #     logger.info(f"Found {sum(len(r.assets) for r in results)} assets in PCA")

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Scan Arma 3 and PCA directories for assets')
    parser.add_argument('--arma', type=Path, default=DEFAULT_ARMA3_PATH, help='Path to Arma 3 directory')
    parser.add_argument('--pca', type=Path, default=DEFAULT_PCA_PATH, help='Path to PCA directory')
    args = parser.parse_args()

    # Setup directories and logging
    temp_dir = ensure_temp_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = temp_dir / f"asset_scan_{timestamp}.json"
    log_file = temp_dir / f"scan_{timestamp}.log"

    # Setup logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(console_handler)

    try:
        # Initialize API
        api = AssetAPI(temp_dir)
        logger.info(f"Output will be saved to: {temp_dir}")
        
        pbar = tqdm(desc="Scanning", unit=" files")
        
        def progress_callback(asset_path: str):
            pbar.update(1)
            pbar.set_description(f"Scanning: {Path(asset_path).name[:30]}")
            if pbar.n % 100 == 0:
                logger.debug(f"Processed {pbar.n} files...")

        # Connect progress callback
        api._scanner.progress_callback = progress_callback

        # Perform scans
        scan_locations(api, args.arma, args.pca, logger)
        pbar.close()
            
        # Generate and save report
        generate_report(api, output_file)
        
    except KeyboardInterrupt:
        logger.error("\nScan interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"\nError during scan: {e}")
        sys.exit(1)
    finally:
        api.cleanup()
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

if __name__ == "__main__":
    main()
