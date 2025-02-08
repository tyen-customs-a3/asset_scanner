import re

# Core patterns - simplified for preprocessed text
CLASS_PATTERN = re.compile(r'''
    class\s+                    # class keyword
    (\w+)                      # class name
    (?:\s*:\s*(\w+))?         # optional parent class
    \s*                        # whitespace
    (?=[{;])                  # lookahead for brace or semicolon
''', re.VERBOSE)

# Value validation patterns
VALUE_PATTERNS = {
    'quoted_string': re.compile(r'^"([^"]*)"$'),
    'number': re.compile(r'^[-+]?[0-9]*\.?[0-9]+$'),
    'boolean': re.compile(r'^(true|false)$', re.IGNORECASE),
    'path': re.compile(r'^(?:")?[a-zA-Z0-9_\\]+\.(p3d|paa)(?:")?$', re.IGNORECASE)
}
