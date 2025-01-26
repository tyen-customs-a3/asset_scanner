import logging
from pathlib import Path
from typing import Dict, Set, Optional, List
import re
from .class_models import ClassHierarchy, ClassInfo, UnprocessedClasses, RawClassDef

logger = logging.getLogger(__name__)

class ClassScanner:
    """Scanner for class definitions and hierarchies"""
    
    CODE_EXTENSIONS = {'.sqf', '.cpp', '.hpp'}
    
    def __init__(self, asset_scanner):
        """Initialize with reference to AssetScanner for PBO handling"""
        self.asset_scanner = asset_scanner
        
    def scan_classes(self, source: str, code_files: Dict[str, str]) -> UnprocessedClasses:
        """Scan code files and return unprocessed class definitions"""
        raw_classes: Dict[str, RawClassDef] = {}
        
        for file_path, content in code_files.items():
            try:
                class_defs = self.parse_class_definitions(content)
                for name, info in class_defs.items():
                    if name in raw_classes:
                        # Keep more detailed definition
                        if len(info['properties']) > len(raw_classes[name].properties):
                            raw_classes[name] = RawClassDef(
                                name=name,
                                parent=info['parent'],
                                properties=info['properties'],
                                file_path=Path(file_path),
                                source=source,
                                type=info.get('type', 'class')
                            )
                    else:
                        raw_classes[name] = RawClassDef(
                            name=name,
                            parent=info['parent'],
                            properties=info['properties'],
                            file_path=Path(file_path),
                            source=source,
                            type=info.get('type', 'class')
                        )
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                
        return UnprocessedClasses(
            classes=raw_classes,
            source=source
        )

    def parse_class_definitions(self, code: str) -> Dict[str, Dict]:
        """Parse class definitions with improved property handling"""
        classes = {}
        # Clean up code
        text = re.sub(r'//.*?(?:\n|$)', '\n', code, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        def extract_class_content(text: str, start: int) -> tuple[int, str]:
            """Extract content between balanced braces"""
            level = 0
            i = start
            content_start = None
            
            while i < len(text):
                if text[i] == '{':
                    level += 1
                    if level == 1:
                        content_start = i + 1
                elif text[i] == '}':
                    level -= 1
                    if level == 0 and content_start is not None:
                        return i, text[content_start:i]
                i += 1
            return -1, ""

        def parse_class(text: str, pos: int = 0) -> Dict[str, Dict]:
            """Parse single class and its nested classes"""
            result = {}
            class_pattern = r'(?:class|enum)\s+(\w+)(?:\s*:\s*(?:public\s+)?([^\s{]+))?\s*{'
            
            while True:
                match = re.search(class_pattern, text[pos:], re.MULTILINE)
                if not match:
                    break
                    
                start_pos = pos + match.start()
                class_pos = pos + match.end()
                end_pos, content = extract_class_content(text, class_pos - 1)
                if end_pos == -1:
                    break

                name = match.group(1)
                parent = match.group(2)
                is_enum = match.group(0).lstrip().startswith('enum')
                
                # Parse properties first (including nested class properties)
                properties = {}
                if is_enum:
                    # Special handling for enum values
                    enum_pattern = r'(\w+)\s*=\s*([^,\s}]+)'
                    for enum_match in re.finditer(enum_pattern, content):
                        properties[enum_match.group(1)] = enum_match.group(2).strip()
                else:
                    # Parse regular properties
                    properties = self.parse_properties(content)
                    
                    # Parse nested classes separately but store their direct properties
                    nested = parse_class(content)
                    for nested_name, nested_info in nested.items():
                        # Store nested class properties directly in parent's properties
                        if 'properties' in nested_info:
                            properties[nested_name] = nested_info['properties']

                result[name] = {
                    'parent': parent.strip() if parent else None,
                    'properties': properties,
                    'type': 'enum' if is_enum else 'class'
                }
                
                pos = end_pos + 1

            return result

        return parse_class(text)

    def parse_properties(self, content: str) -> Dict[str, str]:
        """Parse properties with improved array handling"""
        properties = {}
        # Handle regular properties and arrays
        prop_pattern = r'''
            (\w+)               # Property name
            (?:\[\])?          # Optional array marker
            \s*=\s*            # Equals with whitespace
            (?:
                \{             # Array start
                ([^}]+)        # Array contents
                \}             # Array end
                |              # OR
                ([^;]+)        # Regular value
            )
            \s*;              # End with semicolon
        '''
        
        for match in re.finditer(prop_pattern, content, re.VERBOSE | re.MULTILINE | re.DOTALL):
            name = match.group(1)
            array_value = match.group(2)
            single_value = match.group(3)
            
            if array_value is not None:
                # Handle array values
                items = [v.strip(' "\'') for v in array_value.split(',')]
                value = ','.join(v for v in items if v)
            else:
                value = single_value.strip(' "\'')
                
            # Always include the property, even if value is empty
            properties[name.strip()] = value

        return properties

    def build_class_hierarchy(self, source: str, code_files: Dict[str, str]) -> ClassHierarchy:
        """Build class hierarchy with proper inheritance"""
        all_classes: Dict[str, ClassInfo] = {}
        invalid_classes: Set[str] = set()
        
        # First pass: collect all classes
        for file_path, content in code_files.items():
            try:
                for name, info in self.parse_class_definitions(content).items():
                    # Keep more detailed definition if duplicate
                    if name in all_classes:
                        if len(info['properties']) > len(all_classes[name].properties):
                            all_classes[name] = ClassInfo(
                                name=name,
                                parent=info['parent'],
                                properties=info['properties'],
                                file_path=Path(file_path),
                                source=source,
                                type=info.get('type', 'class')
                            )
                    else:
                        all_classes[name] = ClassInfo(
                            name=name,
                            parent=info['parent'],
                            properties=info['properties'],
                            file_path=Path(file_path),
                            source=source,
                            type=info.get('type', 'class')
                        )
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")

        # Find cycles in inheritance graph
        def detect_cycle(name: str, path: Set[str]) -> bool:
            if name in path:
                invalid_classes.update(path | {name})
                return True
            if name not in all_classes:
                return False
                
            path.add(name)
            if all_classes[name].parent:
                if detect_cycle(all_classes[name].parent, path):
                    return True
            path.remove(name)
            return False

        # Check all classes for cycles
        for name in list(all_classes.keys()):
            detect_cycle(name, set())

        def build_inheritance_chain(name: str) -> List[str]:
            """Build inheritance chain from parent to child"""
            chain = []
            current = name
            while current and current not in invalid_classes:
                chain.append(current)
                if info := all_classes.get(current):
                    current = info.parent
                else:
                    break
            return list(reversed(chain))

        # Process valid classes
        processed_classes: Dict[str, ClassInfo] = {}
        root_classes = set()

        for name in all_classes:
            if name in invalid_classes:
                continue

            chain = build_inheritance_chain(name)
            if not chain:
                continue

            # Build merged properties through inheritance chain
            merged = {}
            for class_name in chain:
                info = all_classes[class_name]
                props = dict(info.properties)
                
                # Handle nested classes separately
                if "__nested_classes" in props:
                    nested = props.pop("__nested_classes")
                    # Merge regular properties
                    curr_props = {**merged, **props}
                    # Add nested classes back
                    props = dict(props)
                    props["__nested_classes"] = nested
                else:
                    curr_props = {**merged, **props}

                children = {
                    c for c, i in all_classes.items()
                    if i.parent == class_name and c not in invalid_classes
                }

                processed_classes[class_name] = ClassInfo(
                    name=class_name,
                    parent=info.parent,
                    properties=props,
                    inherited_properties=merged.copy(),
                    file_path=info.file_path,
                    source=source,
                    children=children,
                    type=info.type
                )

                if not info.parent:
                    root_classes.add(class_name)

                merged = curr_props

        return ClassHierarchy(
            classes=processed_classes,
            root_classes=root_classes,
            source=source,
            invalid_classes=invalid_classes
        )

    def find_code_references(self, search_term: str, code: str) -> List[tuple]:
        """Find references to a term in code content"""
        references = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            if search_term in line:
                references.append((line_num, line.strip()))
                
        return references

    def read_code_file(self, file_path: Path) -> Optional[str]:
        """Read a code file with proper encoding detection"""
        try:
            # Try UTF-8 first
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                # Fallback to Windows-1252
                return file_path.read_text(encoding='windows-1252')
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return None
