from typing import Optional, Callable

from asset_scanner.progress_callback import ProgressCallbackType

class APIConfig:
    def __init__(
        self,
        cache_max_size: int = 100000,
        max_workers: int = 4,
        pbo_limit: Optional[int] = None,
        progress_callback: Optional[ProgressCallbackType] = None,
        error_handler: Optional[Callable[[Exception], None]] = None
    ):
        self.cache_max_size = cache_max_size
        self.max_workers = max_workers
        self.pbo_limit = pbo_limit
        self.progress_callback = progress_callback
        self.error_handler = error_handler