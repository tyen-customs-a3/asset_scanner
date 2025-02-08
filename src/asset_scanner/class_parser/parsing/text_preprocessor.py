import re

class ConfigPreprocessor:
    """Preprocesses config files for easier parsing"""
    
    def preprocess(self, content: str) -> str:
        """Clean and normalize config content"""
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        result = []
        in_string = False
        in_comment = False
        in_multiline = False
        escape_next = False  # Add escape handling
        i = 0
        
        while i < len(content):
            if escape_next:
                result.append(content[i])
                escape_next = False
                i += 1
                continue

            if content[i] == '\\':
                escape_next = True 
                result.append(content[i])
                i += 1
                continue

            # Handle comments with proper nesting
            if content[i:i+2] == '/*' and not in_string:
                in_multiline = True
                i += 2
                continue
            elif content[i:i+2] == '*/' and not in_string and in_multiline:
                in_multiline = False
                i += 2
                continue
            elif content[i:i+2] == '//' and not in_string and not in_multiline:
                in_comment = True
                i += 2
                continue
            elif content[i] == '\n':
                if in_comment:
                    in_comment = False
                result.append('\n')
                i += 1
                continue
            elif content[i] == '"' and not escape_next:
                in_string = not in_string
            
            if not in_comment and not in_multiline:
                if content[i].isspace() and not in_string:
                    if result and not result[-1].isspace():
                        result.append(' ')
                else:
                    result.append(content[i])
            i += 1
            
        return ''.join(result).strip()

    def split_into_declarations(self, content: str) -> list[str]:
        """Split with improved nested handling"""
        declarations = []
        current = []
        depth = 0
        in_string = False
        in_class = False
        
        i = 0
        while i < len(content):
            char = content[i]
            current.append(char)
            
            if content[i:].startswith('class '):
                in_class = True
                
            if char == '"' and (i == 0 or content[i-1] != '\\'):
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0 and in_class:
                        declarations.append(''.join(current).strip())
                        current = []
                        in_class = False
                elif char == ';' and depth == 0 and in_class:
                    declarations.append(''.join(current).strip())
                    current = []
                    in_class = False
            i += 1
            
        if current and in_class:
            declarations.append(''.join(current).strip())
            
        return [d for d in declarations if d and d.startswith('class')]
