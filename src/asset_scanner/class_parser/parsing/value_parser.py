from typing import List, Any, Optional

from asset_scanner.class_parser.core.config_value import ConfigValue, ValueType
from asset_scanner.class_parser.parsing.patterns import VALUE_PATTERNS

class ValueParser:
    @staticmethod
    def parse_value(raw_value: str) -> ConfigValue:
        """Parse a single value with type detection"""
        raw_value = raw_value.strip()
        
        # Handle arrays
        if raw_value.startswith('{'):
            return ValueParser.create_array_value(raw_value)
            
        # Handle quoted strings
        if VALUE_PATTERNS['quoted_string'].match(raw_value):
            value = raw_value[1:-1]
            if VALUE_PATTERNS['path'].match(value):
                return ConfigValue(raw_value, ValueType.PATH, value)
            return ConfigValue(raw_value, ValueType.STRING, value)
            
        # Handle numbers
        if VALUE_PATTERNS['number'].match(raw_value):
            return ConfigValue(raw_value, ValueType.NUMBER, float(raw_value))
            
        # Handle booleans
        if VALUE_PATTERNS['boolean'].match(raw_value):
            return ConfigValue(raw_value, ValueType.BOOLEAN, raw_value.lower() == 'true')
            
        return ConfigValue(raw_value, ValueType.STRING, raw_value)

    @staticmethod
    def create_array_value(raw_str: str) -> ConfigValue:
        """Create array type ConfigValue"""
        # Remove outer braces
        content = raw_str.strip()
        if not content.startswith('{') or not content.endswith('}'):
            return ConfigValue(raw_str, ValueType.ARRAY, [])
            
        content = content[1:-1].strip()
        if not content:
            return ConfigValue(raw_str, ValueType.ARRAY, [])
            
        items = ValueParser._parse_array_items(content)
        return ConfigValue(raw_str, ValueType.ARRAY, items)

    @staticmethod
    def _parse_array_items(content: str) -> List[Any]:
        """Parse array items with proper nesting support"""
        items = []
        current = []
        depth = 0
        in_string = False
        escape_next = False
        
        for char in content:
            if escape_next:
                current.append(char)
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                current.append(char)
            elif char == '"' and not escape_next:
                in_string = not in_string
                current.append(char)
            elif not in_string:
                if char == '{':
                    depth += 1
                    current.append(char)
                elif char == '}':
                    depth -= 1
                    current.append(char)
                elif char == ',' and depth == 0:
                    item = ''.join(current).strip()
                    if item:
                        parsed = ValueParser.parse_value(item)
                        items.append(parsed)
                    current = []
                    continue
                else:
                    current.append(char)
            else:
                current.append(char)
                
        # Add final item
        item = ''.join(current).strip()
        if item:
            parsed = ValueParser.parse_value(item)
            items.append(parsed)
            
        return items
