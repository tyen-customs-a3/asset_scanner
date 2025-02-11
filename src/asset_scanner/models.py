from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Set, Optional

@dataclass(frozen=True)
class Asset:
    """Represents a scanned asset file"""
    path: Path
    source: str
    last_scan: datetime
    has_prefix: bool = True
    pbo_path: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.path:
            normalized = str(self.path).replace('\\', '/').strip('/')
            object.__setattr__(self, 'path', Path(normalized))
        if self.pbo_path:
            normalized = str(self.pbo_path).replace('\\', '/').strip('/')
            object.__setattr__(self, 'pbo_path', Path(normalized))
        if not self.source:
            raise ValueError("Source cannot be empty")

    @property
    def normalized_path(self) -> str:
        return str(self.path).replace('\\', '/')

    @property 
    def filename(self) -> str:
        return self.path.name

@dataclass(frozen=True)
class ScanResult:
    """Contains results of an asset scan"""
    assets: Set[Asset] = field(default_factory=set)
    scan_time: datetime = field(default_factory=datetime.now)
    source: str = ''
    prefix: str = ''
    path: Optional[Path] = None

    def __post_init__(self) -> None:
        if not self.assets:
            object.__setattr__(self, 'assets', set())

    def __iter__(self) -> Iterator[Asset]:
        return iter(self.assets)

    def to_dict(self) -> dict:
        return {
            'assets': [str(asset.path) for asset in self.assets],
            'scan_time': self.scan_time.isoformat()
        }