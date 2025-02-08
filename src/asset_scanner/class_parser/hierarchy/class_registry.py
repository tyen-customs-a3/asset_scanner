from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, Set, Optional
from pathlib import Path

from asset_scanner.class_parser.core.config_class import ConfigClass

@dataclass
class ClassRegistry:
    """Simple storage for parsed classes"""
    classes: Dict[str, ConfigClass] = field(default_factory=dict)
    config_groups: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_class(self, cls: ConfigClass) -> None:
        """Add a class to the registry"""
        # For nested classes, use parent/child format
        if cls.parent:
            path = f"{cls.config_group}/{cls.parent}/{cls.name}"
        else:
            path = f"{cls.config_group}/{cls.name}"
        
        self.classes[path] = cls
        self.config_groups[cls.config_group].add(cls.name)

    def get_class(self, config_group: str, name: str) -> Optional[ConfigClass]:
        """Get a class by its group and name, supporting nested classes"""
        # Try direct path
        key = f"{config_group}/{name}"
        if key in self.classes:
            return self.classes[key]
            
        # Handle nested class paths
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            key = f"{config_group}/{parent}/{child}"
            if key in self.classes:
                return self.classes[key]
                
            # Try full path as class name
            key = f"{config_group}/{name}"
            if key in self.classes:
                return self.classes[key]
        
        # Try as nested class under any parent
        for path, cls in self.classes.items():
            if path.endswith(f"/{name}") and path.startswith(f"{config_group}/"):
                return cls
                
        return None