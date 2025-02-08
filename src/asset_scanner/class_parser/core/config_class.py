from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from .config_value import ConfigValue


@dataclass(frozen=True)
class ConfigClass:
    """Represents a single class definition"""
    name: str
    config_group: str
    parent: Optional[str] = None
    properties: Dict[str, ConfigValue] = field(default_factory=dict)
    source_file: Path = Path("unknown")
    source_pbo: Optional[Path] = None
    source_mod: Optional[str] = None
    line_number: int = 0

    def __post_init__(self) -> None:
        if self.properties is None:
            object.__setattr__(self, 'properties', {})
