import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from ..core import ConfigValue
from .text_preprocessor import ConfigPreprocessor
from .value_parser import ValueParser
from .patterns import CLASS_PATTERN
from ..errors import ParsingError

logger = logging.getLogger(__name__)

@dataclass
class ClassBlock:
    """Represents a raw class block before parsing"""
    header: str
    body: str
    start_line: int
    nested_blocks: List['ClassBlock']

class ClassScanner:
    """Scans raw text for class definitions"""
    
    def __init__(self) -> None:
        self.preprocessor = ConfigPreprocessor()
        self.value_parser = ValueParser()

    def scan_file(self, file_path: Path) -> List[ClassBlock]:
        """Extract raw class blocks from file"""
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = file_path.read_text(encoding='latin1')
            
        clean_content = self.preprocessor.preprocess(content)
        return self._extract_class_blocks(clean_content)

    def _extract_class_blocks(self, content: str) -> List[ClassBlock]:
        """Extract class blocks with proper nesting support"""
        blocks = []
        i = 0
        line_num = 1
        
        while i < len(content):
            # Skip whitespace
            while i < len(content) and content[i].isspace():
                if content[i] == '\n':
                    line_num += 1
                i += 1
                
            # Look for class definitions
            if i + 5 < len(content) and content[i:i+5] == 'class':
                block, consumed = self._capture_class_block(content[i:], line_num)
                if block:
                    blocks.append(block)
                    i += consumed
                    line_num += content[i-consumed:i].count('\n')
                    continue
            i += 1
            
        return blocks

    def _capture_class_block(self, text: str, line_num: int) -> Tuple[Optional[ClassBlock], int]:
        """Capture a complete class block with nested blocks"""
        # Find class header
        header_end = 0
        in_string = False
        
        while header_end < len(text):
            if text[header_end] == '"':
                in_string = not in_string
            elif not in_string and text[header_end] in '{;':
                break
            header_end += 1
            
        if header_end >= len(text):
            return None, 0
            
        header = text[:header_end].strip()
        
        # Handle forward declarations
        if text[header_end] == ';':
            return ClassBlock(header, "", line_num, []), header_end + 1
            
        # Extract body with nested blocks
        body, nested, consumed = self._extract_body(text[header_end:], line_num + text[:header_end].count('\n'))
        
        if body is None:
            return None, 0
            
        return ClassBlock(header, body, line_num, nested), header_end + consumed

    def _extract_body(self, text: str, line_num: int) -> Tuple[Optional[str], List[ClassBlock], int]:
        """Extract class body handling nested classes"""
        if not text.startswith('{'):
            return None, [], 0
            
        body = []
        nested = []
        depth = 0
        in_string = False
        escape_next = False
        i = 0
        current_line = line_num
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                body.append(char)
                escape_next = False
            elif char == '\\':
                body.append(char)
                escape_next = True
            elif char == '"' and not escape_next:
                body.append(char)
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    depth += 1
                    body.append(char)
                elif char == '}':
                    depth -= 1
                    body.append(char)
                    if depth == 0:
                        break
                elif char == '\n':
                    current_line += 1
                    body.append(char)
                elif text[i:i+5] == 'class' and depth == 1:
                    # Found nested class
                    nested_block, consumed = self._capture_class_block(text[i:], current_line)
                    if nested_block:
                        nested.append(nested_block)
                        body.extend(text[i:i+consumed])
                        i += consumed - 1
                else:
                    body.append(char)
            else:
                body.append(char)
            i += 1
            
        if depth > 0:
            return None, [], 0
            
        return ''.join(body), nested, i + 1

    def _process_block(self, raw_block: str) -> Dict[str, str]:
        """Process a raw class block into header and body"""
        # Find class header end
        header_end = raw_block.find('{')
        if header_end == -1:
            header_end = raw_block.find(';')
            if header_end == -1:
                raise ParsingError(f"Invalid class block: {raw_block}")
                
        header = raw_block[:header_end].strip()
        body = raw_block[header_end:].strip()
        
        return {
            'header': header,
            'body': body
        }
