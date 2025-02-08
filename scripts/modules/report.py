from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, DefaultDict
from collections import defaultdict
import json
import csv
import logging
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

@dataclass
class AssetResult:
    source: str
    path: Path
    pbo_name: Optional[str]
    type: Optional[str]

@dataclass
class ClassResult:
    name: str
    parent: Optional[str]
    properties: Dict[str, Any]
    source: str

def generate_report(results: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    """Generate a structured report from parallel scan results"""
    if "folders" not in results or not results["folders"]:
        logger.warning("No folders found in scan results")
        return {
            "summary": {
                "total_folders": 0,
                "total_pbos": 0,
                "total_assets": 0,
                "total_classes": 0,
                "total_loose_files": 0,
                "scan_time": None
            },
            "folders": []
        }
        
    try:
        # Use the totals already calculated in the scanner
        folder = results["folders"][0]  # We're using consolidated results
        
        summary = {
            "total_folders": 1,
            "total_pbos": len(folder.get("pbos", [])),
            "total_assets": folder.get("total_assets", 0),
            "total_classes": folder.get("total_classes", 0),
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
    elif isinstance(obj, dict):
        return {k: _convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_serializable(v) for v in obj]
    return obj

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
            f.write(f"Total Classes: {folder['total_classes']}\n")
    
    return output_file

def save_json_report(report: Dict[str, Any], output_dir: Path) -> Path:
    """Save report in JSON format"""
    output_file = output_dir / "scan_report.json"
    serializable_report = _convert_to_serializable(report)
    with open(output_file, 'w') as f:
        json.dump(serializable_report, f, indent=2)
    return output_file

def save_class_tree(report: Dict[str, Any], output_dir: Path) -> Path:
    """Save class hierarchy as text tree with flattened structure"""
    output_file = output_dir / "class_tree.txt"
    
    def format_class(cls: Dict[str, Any], indent: int = 0) -> str:
        lines = []
        prefix = "  " * indent
        name = cls["name"]
        parent = cls.get("parent", "")
        lines.append(f"{prefix}{name}" + (f" <- {parent}" if parent else ""))
        
        if cls.get("properties"):
            for key, value in sorted(cls["properties"].items()):
                if isinstance(value, dict) and "value" in value:
                    lines.append(f"{prefix}  ├─ {key}: {value['value']}")
                else:
                    lines.append(f"{prefix}  ├─ {key}: {value}")
        
        return "\n".join(lines)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Class Hierarchy\n")
        f.write("==============\n\n")
        
        for folder in report["folders"]:
            if folder.get("classes"):
                f.write(f"\n[{folder['path']}]\n")
                classes = folder["classes"]
                
                # Group by class type
                class_groups: Dict[str, List[Dict[str, Any]]] = {}
                for cls in classes:
                    prefix = cls["name"].split("_")[0] if "_" in cls["name"] else "Other"
                    if prefix not in class_groups:
                        class_groups[prefix] = []
                    class_groups[prefix].append(cls)
                
                # Print each group
                for prefix, group_classes in sorted(class_groups.items()):
                    f.write(f"\n{prefix}\n")
                    for cls in sorted(group_classes, key=lambda x: x["name"]):
                        f.write("\n" + format_class(cls))
                    f.write("\n")

    return output_file

def save_class_graph(report: Dict[str, Any], output_dir: Path) -> Path:
    """Save class inheritance as DOT graph"""
    output_file = output_dir / "class_graph.dot"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('digraph Classes {\n')
        f.write('  rankdir=LR;\n')  # Left to right layout
        f.write('  node [shape=box, style=rounded];\n')
        f.write('  edge [arrowhead=empty];\n\n')
        
        # Track processed classes to avoid duplicates
        processed = set()
        
        for folder in report["folders"]:
            if folder.get("classes"):
                f.write(f'  subgraph "cluster_{folder["path"]}" {{\n')
                f.write(f'    label="{folder["path"]}";\n')
                
                classes = folder["classes"]
                
                # Add nodes
                for cls in classes:
                    if cls["name"] not in processed:
                        escaped_name = cls["name"].replace('"', '\\"')
                        f.write(f'    "{escaped_name}";\n')
                        processed.add(cls["name"])
                
                # Add inheritance edges
                for cls in classes:
                    if cls.get("parent"):
                        escaped_name = cls["name"].replace('"', '\\"')
                        escaped_parent = cls["parent"].replace('"', '\\"')
                        f.write(f'    "{escaped_parent}" -> "{escaped_name}";\n')
                
                f.write('  }\n\n')
        
        f.write('}\n')
    
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
            
            # Generate additional class analysis files with text format
            tree_file = save_class_tree(report, output_dir)
            saved_files.append(f"Class Tree: {tree_file}")
            
            graph_file = save_class_graph(report, output_dir)
            saved_files.append(f"Class Graph: {graph_file}")
        
        if saved_files:
            logger.info("Reports saved to:")
            for file in saved_files:
                logger.info(f"- {file}")
                
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        raise

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
        elif key == "total_classes":
            summary.add_row("Classes", str(value),
                          f"Across {report['summary']['total_pbos']} PBOs")
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

def generate_class_tree(results: List[Dict[str, Any]], console: Console) -> None:
    """Generate hierarchical tree view of classes with flattened properties"""
    root = Tree("📚 Class Hierarchy")
    
    for result in results:
        source_name = result.get("source", "unknown")
        classes = result.get("classes", [])
        
        if not classes:
            continue
            
        source_tree = root.add(f"[blue]{source_name}")
        
        # Group by class type
        class_groups = {}
        for class_data in classes:
            prefix = class_data["name"].split("_")[0] if "_" in class_data["name"] else "Other"
            if prefix not in class_groups:
                class_groups[prefix] = []
            class_groups[prefix].append(class_data)
        
        # Add class groups
        for prefix, group_classes in sorted(class_groups.items()):
            group_tree = source_tree.add(f"[cyan]{prefix}")
            for class_data in sorted(group_classes, key=lambda x: x["name"]):
                class_node = group_tree.add(f"[green]{class_data['name']}")
                if class_data.get("parent"):
                    class_node.add(f"[yellow]Parent: {class_data['parent']}")
                if class_data.get("properties"):
                    props_node = class_node.add("[magenta]Properties")
                    for prop_name, prop_value in class_data["properties"].items():
                        if isinstance(prop_value, dict) and "value" in prop_value:
                            props_node.add(f"[white]{prop_name}: {prop_value['value']}")
                        else:
                            props_node.add(f"[white]{prop_name}: {prop_value}")
    
    console.print(root)

def generate_inheritance_graph(results: List[Dict[str, Any]], output_dir: Path) -> None:
    """Generate Cosmograph compatible CSV of class inheritance"""
    graph_file = output_dir / "class_inheritance.csv"
    
    with open(graph_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "type"])
        
        for result in results:
            classes = result.get("classes", [])
            source_name = result.get("source", "unknown")
            
            for class_data in classes:
                if class_data.get("parent"):
                    writer.writerow([
                        class_data["parent"],
                        class_data["name"],
                        source_name
                    ])

def save_detailed_report(results: Dict[str, Any], output_dir: Path) -> None:
    """Save detailed JSON report with all scan data"""
    report_file = output_dir / "detailed_report.json"
    
    # Convert results to serializable format
    serializable = {
        "summary": results["summary"],
        "stats": results["stats"],
        "assets": [
            {
                "source": r.source,
                "path": str(r.path),
                "type": r.type if hasattr(r, 'type') else None,
                "pbo": r.pbo_name if hasattr(r, 'pbo_name') else None
            }
            for result in results["results"]
            for r in result.assets
        ],
        "classes": [
            {
                "name": c.name,
                "parent": c.parent,
                "properties": c.properties,
                "source": c.source
            }
            for result in results["results"]
            if hasattr(result, 'classes')
            for c in result.classes.values()
        ]
    }
    
    with open(report_file, 'w') as f:
        json.dump(serializable, f, indent=2)
