import abc
from pathlib import Path
from typing import Callable, Set, Dict, Optional, List, Tuple
from datetime import datetime

from .asset_models import Asset, ScanResult
from .pbo_extractor import PboExtractor


class ScannerEngine(abc.ABC):
    def __init__(self, progress_callback: Optional[Callable[[str, float], None]] = None) -> None:
        self.progress_callback = progress_callback

    @abc.abstractmethod
    def scan_file(self, file_path: Path) -> Optional[ScanResult]:
        """Scan a single file"""
        if self.progress_callback:
            self.progress_callback(str(file_path), 0.0)
        return None

    @abc.abstractmethod
    def supports_file(self, file_path: Path) -> bool:
        """Check if this engine supports scanning the given file"""
        pass


class PBOScannerEngine(ScannerEngine):
    """Scanner engine for PBO files"""

    def __init__(self, pbo_extractor: 'PboExtractor', progress_callback: Optional[Callable[[str, float], None]] = None) -> None:
        super().__init__(progress_callback)
        self.pbo_extractor = pbo_extractor

    def supports_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.pbo'

    def scan_file(self, pbo_path: Path) -> Optional[ScanResult]:
        """Scan a single PBO file"""
        try:
            if self.progress_callback:
                self.progress_callback(f"Scanning PBO: {pbo_path}", 0.0)
            source = pbo_path.parent.parent.name.strip('@')
            returncode, code_files, normalized_paths = self.pbo_extractor.scan_pbo_contents(pbo_path)
            if returncode != 0:
                return None

            assets = set()
            current_time = datetime.now()

            for path in normalized_paths:
                assets.add(Asset(
                    path=Path(path),
                    source=source,
                    last_scan=current_time,
                    has_prefix=True,
                    pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                ))

            result = ScanResult(assets=assets, scan_time=current_time)
            if self.progress_callback:
                self.progress_callback(f"Completed PBO: {pbo_path}", 1.0)
            return result

        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"Error scanning PBO: {pbo_path} - {e}", 1.0)
            return None


class RegularFileScannerEngine(ScannerEngine):
    """Scanner engine for regular files"""

    def __init__(self, valid_extensions: Set[str], progress_callback: Optional[Callable[[str, float], None]] = None):
        super().__init__(progress_callback)
        self.valid_extensions = valid_extensions

    def supports_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.valid_extensions

    def scan_file(self, file_path: Path) -> Optional[ScanResult]:
        if self.progress_callback:
            self.progress_callback(f"Scanning: {file_path}", 0.0)
        if not self.supports_file(file_path):
            return None

        source_path = file_path
        while source_path.parent != source_path:
            if source_path.parent.name == 'addons':
                source = source_path.parent.parent.name
                break
            source_path = source_path.parent
        else:
            source = file_path.parent.parent.name

        source = source.strip('@')

        try:
            rel_path = file_path.relative_to(file_path.parent.parent)
        except ValueError:
            rel_path = Path(file_path.name)

        clean_path = f"{source}/{str(rel_path)}".replace('\\', '/')

        asset = Asset(
            path=Path(clean_path),
            source=source,
            last_scan=datetime.now(),
            has_prefix=False,
            pbo_path=None
        )

        if self.progress_callback:
            self.progress_callback(f"Completed: {file_path}", 1.0)
        return ScanResult(assets={asset}, scan_time=datetime.now())
