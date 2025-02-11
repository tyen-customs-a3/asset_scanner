from typing import Optional, Callable
from pathlib import Path

from asset_scanner.progress_callback import ProgressCallbackType

class APIConfig:
    def __init__(
        self,
        max_cache_size: int = 10000000,
        max_workers: int = 4,
        pbo_limit: Optional[int] = None,
        progress_callback: Optional[ProgressCallbackType] = None,
        error_handler: Optional[Callable[[Exception], None]] = None,
        cache_file: Optional[Path] = None
    ):
        self.max_cache_size = max_cache_size
        self.max_workers = max_workers
        self.pbo_limit = pbo_limit
        self.progress_callback = progress_callback
        self.error_handler = error_handler
        self.cache_file = cache_file