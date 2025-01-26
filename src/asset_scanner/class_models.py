from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Set, Optional, Dict, List
from types import MappingProxyType

@dataclass(frozen=True)
class CodeReference:
    """Represents a code reference result"""
    file_path: Path
    line_number: int
    line_content: str
    source: str

@dataclass(frozen=True)
class ClassDefinition:
    """Represents a class definition found in code"""
    name: str
    parent: Optional[str]
    properties: Dict[str, str]
    file_path: Path
    source: str

@dataclass(frozen=True)
class ClassInfo:
    """Represents a class with its properties and inheritance info"""
    name: str
    parent: Optional[str]
    properties: Dict[str, str]
    file_path: Path
    source: str
    children: Set[str] = field(default_factory=frozenset)
    inherited_properties: Dict[str, str] = field(default_factory=dict)
    type: str = 'class'  # 'class' or 'enum'

    def __post_init__(self):
        """Convert mutable collections to immutable"""
        if not isinstance(self.children, frozenset):
            object.__setattr__(self, 'children', frozenset(self.children))
        if isinstance(self.properties, dict):
            object.__setattr__(self, 'properties', MappingProxyType(dict(self.properties)))
        if isinstance(self.inherited_properties, dict):
            object.__setattr__(self, 'inherited_properties', MappingProxyType(dict(self.inherited_properties)))

    def get_all_properties(self) -> Dict[str, str]:
        """Get all properties including inherited ones"""
        return {**self.inherited_properties, **self.properties}

    def has_property(self, name: str) -> bool:
        """Check if property exists (including inherited)"""
        return name in self.properties or name in self.inherited_properties

@dataclass(frozen=True)
class ClassHierarchy:
    """Represents the entire class hierarchy for a mod"""
    classes: Dict[str, ClassInfo]
    root_classes: Set[str]
    source: str
    invalid_classes: Set[str] = field(default_factory=set)
    last_updated: datetime = field(default_factory=datetime.now)

    def get_all_children(self, class_name: str, include_indirect: bool = True) -> Set[str]:
        """Get all descendant classes recursively"""
        if (class_name not in self.classes):
            return set()
        
        if not include_indirect:
            return self.classes[class_name].children
            
        result = set()
        to_process = {class_name}
        
        while to_process:
            current = to_process.pop()
            if current in self.classes:
                children = self.classes[current].children
                result.update(children)
                to_process.update(children)
                
        return result

    def get_inheritance_chain(self, class_name: str, bottom_up: bool = False) -> List[str]:
        """Get the full inheritance chain for a class
        
        Args:
            class_name: Name of the class to get chain for
            bottom_up: If True, returns chain from child to parent, else parent to child
        """
        if class_name not in self.classes:
            return []
            
        chain = [class_name]
        current = self.classes[class_name]
        
        while current.parent:
            if current.parent in self.classes:
                chain.append(current.parent)
                current = self.classes[current.parent]
            else:
                break
                
        return chain if bottom_up else list(reversed(chain))

    def find_classes_with_property(self, property_name: str) -> Set[str]:
        """Find all classes that have a specific property"""
        return {
            name for name, info in self.classes.items()
            if info.has_property(property_name)
        }

@dataclass(frozen=True)
class RawClassDef:
    """Raw class definition before hierarchy processing"""
    name: str
    parent: Optional[str]
    properties: Dict[str, str]
    file_path: Path
    source: str
    type: str = 'class'

@dataclass(frozen=True)
class UnprocessedClasses:
    """Container for unprocessed class definitions"""
    classes: Dict[str, RawClassDef]
    source: str
    last_updated: datetime = field(default_factory=datetime.now)

    def build_hierarchy(self) -> ClassHierarchy:
        """Process raw classes into a complete hierarchy"""
        invalid_classes: Set[str] = set()
        
        def detect_cycles(name: str, visited: Set[str], path: Set[str]) -> None:
            if name in path:
                cycle = {n for n in path if n in self.classes}
                cycle.add(name)
                invalid_classes.update(cycle)
                return
                
            if name in visited or name not in self.classes:
                return
                
            visited.add(name)
            path.add(name)
            
            raw = self.classes.get(name)
            if raw and raw.parent:
                detect_cycles(raw.parent, visited, path)
                    
            path.remove(name)

        # Find all circular inheritance
        visited: Set[str] = set()
        for name in self.classes:
            if name not in visited:
                detect_cycles(name, visited, set())

        # Process valid classes
        processed: Dict[str, ClassInfo] = {}
        root_classes: Set[str] = set()

        def get_inherited_properties(class_name: str, processed_chain: Set[str]) -> Dict[str, str]:
            """Get inherited properties by walking up the inheritance chain"""
            if class_name in processed_chain or class_name not in self.classes:
                return {}

            raw = self.classes[class_name]
            if not raw.parent:
                return {}  # Base class has no inherited properties

            processed_chain.add(class_name)
            parent_props = get_inherited_properties(raw.parent, processed_chain)
            processed_chain.remove(class_name)

            # Get properties from parent class itself
            if parent := self.classes.get(raw.parent):
                # Include ALL properties from parent, including empty strings
                all_props = dict(parent.properties)
                # Add recursively inherited properties from further up the chain
                all_props.update(parent_props)
                return all_props

            return parent_props

        # Build class hierarchy
        for name, raw in self.classes.items():
            if name in invalid_classes:
                continue

            # Get all inherited properties
            inherited = get_inherited_properties(name, set())
            
            # Get direct children
            children = {
                c for c, r in self.classes.items()
                if r.parent == name and c not in invalid_classes
            }

            processed[name] = ClassInfo(
                name=name,
                parent=raw.parent,
                properties=dict(raw.properties),  # Make a copy to ensure all properties are included
                inherited_properties=inherited,
                file_path=raw.file_path,
                source=raw.source,
                children=children,
                type=raw.type
            )

            if not raw.parent:
                root_classes.add(name)

        return ClassHierarchy(
            classes=processed,
            root_classes=root_classes,
            source=self.source,
            invalid_classes=invalid_classes
        )
