import logging
from typing import Dict

from ..core.config_value import ConfigValue
from .value_parser import ValueParser

logger = logging.getLogger(__name__)

class PropertyParser:
    def __init__(self) -> None:
        self.value_parser = ValueParser()
        
    def parse_properties(self, body: str) -> Dict[str, ConfigValue]:
        """Parse properties from class body"""
        # Remove outer braces
        body = body.strip()
        if body.startswith('{'): body = body[1:]
        if body.endswith('}'): body = body[:-1]
        body = body.strip()
        
        properties: Dict[str, ConfigValue] = {}
        
        # Split into statements
        depth = 0
        current = []
        in_string = False
        escape_next = False
        
        for char in body:
            if escape_next:
                current.append(char)
                escape_next = False
            elif char == '\\':
                current.append(char)
                escape_next = True
            elif char == '"':
                current.append(char)
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    depth += 1
                    current.append(char)
                elif char == '}':
                    depth -= 1
                    current.append(char)
                elif char == ';' and depth == 0:
                    stmt = ''.join(current).strip()
                    if stmt and not stmt.startswith('class'):
                        self._add_property(stmt, properties)
                    current = []
                    continue
                else:
                    current.append(char)
            else:
                current.append(char)
                
        # Process final statement
        stmt = ''.join(current).strip()
        if stmt and not stmt.startswith('class'):
            self._add_property(stmt, properties)
            
        return properties

    def _add_property(self, stmt: str, properties: Dict[str, ConfigValue]) -> None:
        """Add a single property to the properties dict"""
        if '=' not in stmt:
            return
            
        name, value = stmt.split('=', 1)
        name = name.strip()
        value = value.strip()
        
        if name.endswith('[]'):
            name = name[:-2]
            try:
                properties[name] = self.value_parser.create_array_value(value)
            except Exception:
                logger.warning(f"Failed to parse array value: {value}")
        else:
            try:
                properties[name] = self.value_parser.parse_value(value)
            except Exception:
                logger.warning(f"Failed to parse value: {value}")
