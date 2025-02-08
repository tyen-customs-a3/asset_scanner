from typing import Dict, Set, List
from collections import defaultdict

from asset_scanner.class_parser.core.config_class import ConfigClass
from asset_scanner.class_parser.hierarchy.class_registry import ClassRegistry
from asset_scanner.class_parser.parsing.raw_class import RawClass

class HierarchyBuilder:
    def __init__(self) -> None:
        """Initialize the hierarchy builder"""
        self.inheritance_graph: Dict[str, Set[str]] = defaultdict(set)
        self.config_groups: Dict[str, Set[str]] = defaultdict(set)
        
    def build_hierarchy(self, raw_classes: List[RawClass]) -> ClassRegistry:
        """Build complete class hierarchy from raw classes"""
        registry = ClassRegistry()
        
        # First pass - register all classes
        for raw in raw_classes:
            config_class = self._create_config_class(raw)
            registry.add_class(config_class)
            
            # Track inheritance
            if raw.parent:
                # Use config group from raw class if available, otherwise use default
                config_group = getattr(raw, 'config_group', 'CfgPatches')
                full_name = f"{config_group}/{raw.name}"
                parent_name = f"{config_group}/{raw.parent}"
                self.inheritance_graph[full_name].add(parent_name)
            
        # Second pass - resolve inheritance
        self._resolve_inheritance(registry)
        
        return registry
        
    def _resolve_inheritance(self, registry: ClassRegistry) -> None:
        """Resolve inherited properties"""
        for path, parents in self.inheritance_graph.items():
            child = registry.classes.get(path)
            if not child:
                continue
                
            # Build complete property set from inheritance chain
            inherited_props = {}
            for parent_path in self._get_inheritance_chain(path):
                parent = registry.classes.get(parent_path)
                if parent:
                    inherited_props.update(parent.properties)
                    
            # Override with child's own properties
            inherited_props.update(child.properties)
            # Create new config class with resolved properties
            registry.classes[path] = ConfigClass(
                name=child.name,
                config_group=child.config_group,
                parent=child.parent,
                properties=inherited_props,
                source_file=child.source_file,
                source_pbo=child.source_pbo,
                source_mod=child.source_mod,
                line_number=child.line_number
            )
            
    def _get_inheritance_chain(self, class_path: str) -> List[str]:
        """Get ordered list of parent classes"""
        chain = []
        current = class_path
        visited = set()
        
        while current in self.inheritance_graph and current not in visited:
            visited.add(current)
            parents = self.inheritance_graph[current]
            if parents:
                parent = next(iter(parents))
                chain.append(parent)
                current = parent
            else:
                break
                
        return chain

    def _create_config_class(self, raw: RawClass) -> ConfigClass:
        """Create a ConfigClass instance from a RawClass"""
        config_group = getattr(raw, 'config_group', 'CfgPatches')
        return ConfigClass(
            name=raw.name,
            config_group=config_group,
            parent=raw.parent,
            properties=raw.properties,
            source_file=raw.source_file,
            source_pbo=getattr(raw, 'source_pbo', None),
            source_mod=getattr(raw, 'source_mod', None),
            line_number=raw.line_number
        )
