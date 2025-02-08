from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List

from asset_scanner.class_parser.core.config_value import ConfigValue

@dataclass
class RawBlock:
    """Raw class block before parsing"""
    header: str  # The class definition line
    body: str    # Everything between { }
    line_number: int
    children: List['RawBlock'] = field(default_factory=list)

@dataclass
class RawClass:
    """Raw class data before hierarchy resolution"""
    name: str
    parent: Optional[str]
    properties: Dict[str, ConfigValue]
    source_file: Path
    line_number: int
    source_pbo: Optional[Path] = None
    source_mod: Optional[str] = None
