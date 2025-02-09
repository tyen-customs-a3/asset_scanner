from typing import Callable, Protocol

class ProgressCallback(Protocol):
    """Protocol for progress callback functions"""
    def __call__(self, message: str, progress: float) -> None: ...

# Type alias for backward compatibility
ProgressCallbackType = Callable[[str, float], None]