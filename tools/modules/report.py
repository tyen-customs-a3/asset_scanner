from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, DefaultDict
from collections import defaultdict
import json
import logging
from rich.console import Console
from rich.table import Table
from rich.tree import Tree


#
# Data Structures
#

@dataclass
class AssetResult:
    """Represents a single asset scan result"""
    source: str
    path: Path
    pbo_name: Optional[str]
    type: Optional[str]


#
# Report Generation
#

def generate_report(results: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """Generate a structured report from parallel scan results"""
    if "folders" not in results or not results["folders"]:
        logger.warning("No folders found in scan results")
        return {
            "summary": {
                "total_folders": 0,
                "total_pbos": 0,
                "total_assets": 0,
                "total_loose_files": 0,
                "scan_time": None
            },
            "folders": []
        }
        
    try:
        folder = results["folders"][0]
        
        summary = {
            "total_folders": 1,
            "total_pbos": len(folder.get("pbos", [])),
            "total_assets": folder.get("total_assets", 0),
            "total_loose_files": len(folder.get("loose_files", []))
        }
        
        return {
            "summary": summary,
            "folders": results["folders"]
        }
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise

def _convert_to_serializable(obj: Any) -> Any:
    """Convert objects to JSON serializable formats"""
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_serializable(v) for v in obj]
    return obj


#
# Report Output
#

def save_text_report(report: Dict[str, Any], output_dir: Path) -> Path:
    """Save report in plain text format"""
    output_file = output_dir / "scan_report.txt"
    with open(output_file, 'w') as f:
        f.write("Asset Scanner Report\n")
        f.write("===================\n\n")
        
        # Write summary
        f.write("Summary\n-------\n")
        for key, value in report["summary"].items():
            f.write(f"{key.replace('_', ' ').title()}: {value}\n")
        
        # Write folder details
        f.write("\nFolder Details\n--------------\n")
        for folder in report["folders"]:
            f.write(f"\nPath: {folder['path']}\n")
            f.write(f"PBOs: {len(folder['pbos'])}\n")
            f.write(f"Loose Files: {len(folder['loose_files'])}\n")
            f.write(f"Total Assets: {folder['total_assets']}\n")
    
    return output_file

def save_json_report(report: Dict[str, Any], output_dir: Path) -> Path:
    """Save report in JSON format"""
    output_file = output_dir / "scan_report.json"
    serializable_report = _convert_to_serializable(report)
    with open(output_file, 'w') as f:
        json.dump(serializable_report, f, indent=2)
    return output_file

def save_report(report: Dict[str, Any], output_dir: Path, logger: logging.Logger, formats: List[str] = ["rich", "json", "text"]) -> None:
    """Save report in specified formats"""
    try:
        saved_files = []
        
        if "json" in formats:
            json_file = save_json_report(report, output_dir)
            saved_files.append(f"JSON: {json_file}")
            
        if "text" in formats:
            text_file = save_text_report(report, output_dir)
            saved_files.append(f"Text: {text_file}")
        
        if saved_files:
            logger.info("Reports saved to:")
            for file in saved_files:
                logger.info(f"- {file}")
                
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        raise


#
# Display & Visualization
#

def print_summary(report: Dict[str, Any], console: Console) -> None:
    """Print enhanced summary of parallel scan results"""
    summary = Table(title="Scan Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", justify="right", style="green")
    summary.add_column("Details", style="dim")
    
    # Add core metrics with details
    for key, value in report["summary"].items():
        if key == "total_pbos":
            summary.add_row("PBO Files", str(value), 
                          f"Contains {report['summary']['total_assets']} assets")
        elif key != "scan_time":
            summary.add_row(key.replace('_', ' ').title(), str(value), "")
    
    console.print(summary)

def generate_asset_tree(results: List[Dict[str, Any]], console: Console) -> None:
    """Generate hierarchical tree view of assets"""
    root = Tree("📁 Asset Hierarchy")
    
    # Type annotations for dictionaries
    addon_groups: DefaultDict[str, List[AssetResult]] = defaultdict(list)
    pbo_groups: DefaultDict[str, List[AssetResult]] = defaultdict(list)
    
    for result in results:
        source_name = result.get("source", "unknown")
        source_tree = root.add(f"[blue]{source_name}")
        
        # Group by addon folders
        for asset in result.get("assets", []):
            asset_obj = AssetResult(
                source=source_name,
                path=Path(asset["path"]),
                pbo_name=asset.get("pbo"),
                type=asset.get("type")
            )
            addon = asset_obj.path.parts[1] if len(asset_obj.path.parts) > 1 else "root"
            addon_groups[addon].append(asset_obj)
        
        # Add addon folders and their PBOs
        for addon, assets in addon_groups.items():
            addon_tree = source_tree.add(f"[cyan]{addon}")
            
            # Group by PBO
            for asset in assets:
                pbo = asset.pbo_name or "loose_files"
                pbo_groups[pbo].append(asset)
            
            # Add PBOs and their assets
            for pbo, pbo_assets in pbo_groups.items():
                pbo_tree = addon_tree.add(f"[green]{pbo}")
                for asset in pbo_assets:
                    pbo_tree.add(f"[yellow]{asset.path.name}")
            
            # Clear PBO groups for next addon
            pbo_groups.clear()
        
        # Clear addon groups for next source
        addon_groups.clear()
    
    console.print(root)
