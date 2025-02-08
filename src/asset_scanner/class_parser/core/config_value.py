from enum import Enum
from dataclasses import dataclass
from typing import Union, List, Any

class ValueType(Enum):
    STRING = "string"
    NUMBER = "number"
    PATH = "path"
    ARRAY = "array"
    BOOLEAN = "boolean"
    UNDEFINED = "undefined"

@dataclass(frozen=True)
class ConfigValue:
    """Represents a parsed configuration value"""
    raw: str
    type: ValueType
    value: Union[str, float, bool, List[Any], None]