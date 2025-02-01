import re
from pathlib import Path
from typing import Dict, Optional, Set
from .class_models import UnprocessedClasses, RawClassDef

class ClassParser:
    """Parser for class definitions in code files"""
    
    def __init__(self):
        self._class_pattern = r'(?:class|enum)\s+(\w+)(?:\s*:\s*(?:public\s+)?([^\s{]+))?\s*{'
        
    def parse_code(self, code: str, pbo_prefix: Optional[str] = None) -> Dict[str, Dict]:
        """Parse class definitions from code content"""
        # Clean up code first
        text = self._clean_code(code)
        
        # Get root prefix if present
        root_prefix = self._extract_root_prefix(text) or pbo_prefix
        
        # Parse all class definitions
        return self._parse_classes(text, root_prefix)
        
    def _clean_code(self, code: str) -> str:
        """Clean up code by removing comments"""
        text = re.sub(r'//.*?(?:\n|$)', '\n', code, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return re.sub(r'\n\s*\n', '\n', text)
        
    def _extract_root_prefix(self, text: str) -> Optional[str]:
        """Extract root prefix definition if present"""
        match = re.search(r'^\s*prefix\s*=\\s*"([^"]+)"\s*;', text, re.MULTILINE)
        if match:
            return match.group(1).replace('\\', '/')
        return None
        
    def _parse_classes(self, text: str, parent_prefix: Optional[str] = None) -> Dict[str, Dict]:
        """Parse class definitions recursively"""
        # Implementation moved from ClassScanner
        # ...existing parsing logic...
