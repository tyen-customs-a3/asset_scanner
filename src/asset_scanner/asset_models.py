from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Set, Optional, Dict, List
from types import MappingProxyType


@dataclass(frozen=True)
class Asset:
    """Represents a scanned asset file"""
    path: Path
    source: str
    last_scan: datetime
    has_prefix: bool = True
    pbo_path: Optional[Path] = None

    def __post_init__(self) -> None:
        """Ensure path is normalized on creation"""
        if self.path:
            normalized = str(self.path).replace('\\', '/').strip('/')
            object.__setattr__(self, 'path', Path(normalized))
        if self.pbo_path:
            normalized = str(self.pbo_path).replace('\\', '/').strip('/')
            object.__setattr__(self, 'pbo_path', Path(normalized))
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
    assets: Set[Asset] = field(default_factory=set)
    scan_time: datetime = field(default_factory=datetime.now)
    source: str = ''
    prefix: str = ''
    path: Optional[Path] = None
    mod_pack: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.scan_time:
            self.scan_time = datetime.now()
        if not self.assets:
            self.assets = set()

    def __iter__(self) -> Iterator[Asset]:
        """Make ScanResult iterable, yielding assets"""
        return iter(self.assets)

    def to_dict(self) -> dict:
        """Convert the scan result to a dictionary representation."""
        return {
            'assets': [str(asset.path) for asset in self.assets],
            'scan_time': self.scan_time.isoformat()
        }