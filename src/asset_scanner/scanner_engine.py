import abc
from pathlib import Path
from typing import Set, Dict, Optional, List, Tuple
from datetime import datetime
from .asset_models import Asset, ScanResult
from .class_models import UnprocessedClasses, ClassInfo

class ScannerEngine(abc.ABC):
    """Base class for scanner engines"""
    
    @abc.abstractmethod
    def scan_file(self, file_path: Path) -> Optional[ScanResult]:
        """Scan a single file"""
        pass
        
    @abc.abstractmethod
    def supports_file(self, file_path: Path) -> bool:
        """Check if this engine supports scanning the given file"""
        pass

class PBOScannerEngine(ScannerEngine):
    """Scanner engine for PBO files"""
    
    def __init__(self, extractor, class_parser):
        self.extractor = extractor
        self.class_parser = class_parser
        
    def supports_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.pbo'
        
    def scan_file(self, pbo_path: Path) -> Optional[ScanResult]:
        """Scan a single PBO file"""
        try:
            source = pbo_path.parent.parent.name.strip('@')
            returncode, code_files, normalized_paths = self.extractor.scan_pbo_contents(pbo_path)
            if returncode != 0:
                return None

            # Create assets for all valid paths
            assets = set()
            current_time = datetime.now()
            
            for path in normalized_paths:
                # Path is already normalized with prefix from PboExtractor
                assets.add(Asset(
                    path=Path(path),
                    source=source,
                    last_scan=current_time,
                    has_prefix=True,
                    pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                ))

            result = ScanResult(assets=assets, scan_time=current_time)
            return result
            
        except Exception as e:
            print(f"Error scanning PBO: {e}")
            return None

class RegularFileScannerEngine(ScannerEngine):
    """Scanner engine for regular files"""
    
    def __init__(self, valid_extensions: Set[str]):
        self.valid_extensions = valid_extensions
        
    def supports_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.valid_extensions
        
    def scan_file(self, file_path: Path) -> Optional[ScanResult]:
        if not self.supports_file(file_path):
            return None
            
        # Get source (mod folder name) - look for parent of 'addons' folder or immediate parent
        source_path = file_path
        while source_path.parent != source_path:
            if source_path.parent.name == 'addons':
                source = source_path.parent.parent.name
                break
            source_path = source_path.parent
        else:
            source = file_path.parent.parent.name

        # Strip @ from source if present
        source = source.strip('@')
        
        # Get relative path starting after source or addons folder
        try:
            if 'addons' in str(file_path).lower():
                rel_path = file_path.relative_to(file_path.parent.parent.parent)
            else:
                rel_path = file_path.relative_to(file_path.parent.parent)
        except ValueError:
            # If relative_to fails, use just the filename
            rel_path = Path(file_path.name)

        # Construct clean path with proper source prefix
        clean_path = f"{source}/addons/{str(rel_path)}".replace('\\', '/')
            
        asset = Asset(
            path=Path(clean_path),
            source=source,
            last_scan=datetime.now(),
            has_prefix=False,
            pbo_path=None
        )
        
        return ScanResult(assets={asset}, scan_time=datetime.now())
