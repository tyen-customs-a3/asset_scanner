class ParsingError(Exception):
    """Base error for parsing failures"""
    pass

class ValueParsingError(ParsingError):
    """Error when parsing values"""
    pass

class SyntaxError(ParsingError):
    """Error for malformed syntax"""
    pass

class BraceError(SyntaxError):
    """Error for mismatched braces"""
    pass

class PropertyError(SyntaxError):
    """Error for malformed properties"""
    pass
