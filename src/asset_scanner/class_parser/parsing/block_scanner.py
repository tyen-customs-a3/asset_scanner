from pathlib import Path
from typing import List, Optional
from .raw_class import RawBlock

class BlockScanner:
    """First-pass scanner that extracts raw class blocks"""
    
    def scan_file(self, file_path: Path) -> List[RawBlock]:
        """Extract all class blocks preserving structure"""
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = file_path.read_text(encoding='latin1')
            
        return self.scan_content(content)

    def scan_content(self, content: str) -> List[RawBlock]:
        """Extract class blocks from content"""
        blocks = []
        line_number = 1
        i = 0
        
        while i < len(content):
            # Skip whitespace
            while i < len(content) and content[i].isspace():
                if content[i] == '\n':
                    line_number += 1
                i += 1
            
            # Look for class definitions
            if i + 5 < len(content) and content[i:i+5] == 'class':
                block = self._extract_block(content[i:], line_number)
                if block:
                    blocks.append(block)
                    # Skip past this block
                    i += len(block.header) + len(block.body)
                    line_number += block.header.count('\n') + block.body.count('\n')
                    continue
            i += 1
            
        return blocks

    def _extract_block(self, text: str, line_number: int) -> Optional[RawBlock]:
        """Extract a single class block with nested blocks"""
        # Find class header with better quote handling
        header_end = 0
        in_string = False
        escape_next = False
        
        while header_end < len(text):
            if escape_next:
                escape_next = False
                header_end += 1
                continue
                
            if text[header_end] == '\\':
                escape_next = True
            elif text[header_end] == '"' and not escape_next:
                in_string = not in_string
            elif not in_string and text[header_end] in '{;':
                break
            header_end += 1
            
        if header_end >= len(text):
            return None
            
        header = text[:header_end].strip()
        
        # Skip empty or invalid headers
        if not header.startswith('class '):
            return None
            
        # Handle forward declarations and empty classes
        if text[header_end] == ';':
            return RawBlock(header=header, body="", line_number=line_number, children=[])
            
        # Extract body with proper nesting
        body, children = self._extract_body_with_children(text[header_end:])
        if not body:
            return None
            
        return RawBlock(
            header=header,
            body=body, 
            line_number=line_number,
            children=children
        )

    def _extract_body_with_children(self, text: str) -> tuple[str, List[RawBlock]]:
        """Extract class body handling nested classes"""
        if not text.startswith('{'):
            return "", []
            
        body: List[str] = []
        children: List[RawBlock] = []
        depth = 0
        in_string = False
        i = 0
        
        while i < len(text):
            char = text[i]
            
            if char == '"' and (i == 0 or text[i-1] != '\\'):
                in_string = not in_string
                body.append(char)
            elif not in_string:
                if char == '{':
                    depth += 1
                    if depth == 1:
                        body.append(char)
                    else:
                        body.append(char)
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        body.append(char)
                        break
                    body.append(char)
                else:
                    body.append(char)
            else:
                body.append(char)
            i += 1
            
        body_str = ''.join(body)
        
        # Extract nested classes
        nested = self.scan_content(body_str[1:-1])  # Remove outer braces
        
        return body_str, nested
