from dataclasses import dataclass, field, asdict
import json
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
            
        # Normalize source by stripping @ prefix
        normalized_source = self.source.lstrip('@')
        if normalized_source != self.source:
            object.__setattr__(self, 'source', normalized_source)

    @property
    def normalized_path(self) -> str:
        return str(self.path).replace('\\', '/')

    @property 
    def filename(self) -> str:
        return self.path.name

    @staticmethod
    def normalize_source(source: str) -> str:
        """Remove @ prefix from source name"""
        return source.lstrip('@')

    def to_dict(self) -> dict:
        """Convert asset to dictionary for serialization"""
        return {
            'path': str(self.path),
            'source': self.source,
            'last_scan': self.last_scan.isoformat(),
            'has_prefix': self.has_prefix,
            'pbo_path': str(self.pbo_path) if self.pbo_path else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Asset':
        """Create asset from dictionary"""
        return cls(
            path=Path(data['path']),
            source=data['source'],
            last_scan=datetime.fromisoformat(data['last_scan']),
            has_prefix=data['has_prefix'],
            pbo_path=Path(data['pbo_path']) if data['pbo_path'] else None
        )

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