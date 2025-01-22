from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Set, Optional

@dataclass(frozen=True)
class Asset:
    """Represents a scanned asset file"""
    path: Path
    source: str
    last_scan: datetime
    has_prefix: bool = True
    pbo_path: Optional[Path] = None

    def __post_init__(self):
        """Ensure path is normalized on creation"""
        if self.path:
            normalized = str(self.path).replace('\\', '/').strip('/')
            object.__setattr__(self, 'path', Path(normalized))
        if self.pbo_path:
            normalized = str(self.pbo_path).replace('\\', '/').strip('/')
            object.__setattr__(self, 'pbo_path', Path(normalized))
        # Strip @ prefix from source
        if self.source.startswith('@'):
            object.__setattr__(self, 'source', self.source.strip('@'))

    @property
    def normalized_path(self) -> str:
        """Get consistently normalized path string"""
        return str(self.path).replace('\\', '/')

    @property
    def filename(self) -> str:
        """Get just the filename without directories"""
        return self.path.name

@dataclass
class ScanResult:
    """Contains results of an asset scan"""
    assets: Set[Asset]
    scan_time: datetime
    
    def __iter__(self):
        """Make ScanResult iterable, yielding assets"""
        return iter(self.assets)
