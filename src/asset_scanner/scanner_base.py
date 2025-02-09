from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Set, Callable, Dict, Tuple, Any
from datetime import datetime
import logging

from .asset_models import Asset, ScanResult
from .progress_callback import ProgressCallbackType
from .scanner_tasks import ScanTask, TaskManager, TaskPriority


class BaseScanner(ABC):
    """Base class for asset scanners"""

    ASSET_EXTENSIONS = {'.p3d', '.paa', '.rtm', '.jpg', '.jpeg', '.png', '.tga', '.wrp', '.pac', '.lip', '.rvmat', '.bin' }

    def __init__(
        self,
        pbo_extractor: Any,
        class_parser: Any,
        progress_callback: Optional[ProgressCallbackType] = None
    ) -> None:
        self.pbo_extractor = pbo_extractor
        self.class_parser = class_parser
        self.progress_callback = progress_callback
        self.task_manager = TaskManager()
        self.logger = logging.getLogger(__name__)
        self.pbo_contents_cache: Dict[str, Tuple[int, Dict[str, str], Set[str]]] = {}

    @abstractmethod
    def scan_directories(self, directories: List[Path], source: str) -> List[ScanResult]:
        """Scan directories and return results"""
        pass

    def _report_progress(self, message: str, progress: float = 0.0) -> None:
        """Report progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(message, progress)

    def preprocess_directory(self, path: Path, source: str) -> None:
        """Create tasks for directory contents - optimized version"""
        if not path.exists():
            return

        pbo_batch_size = 50
        pbo_batch = []

        asset_ext_set = set(self.ASSET_EXTENSIONS)

        all_files = list(path.rglob('*'))

        for item in all_files:
            if not item.is_file():
                continue

            if item.suffix == '.pbo':
                pbo_batch.append(item)
                if len(pbo_batch) >= pbo_batch_size:
                    self._process_pbo_batch(pbo_batch, source)
                    pbo_batch = []
            elif item.suffix.lower() in asset_ext_set:
                self.task_manager.add_task(ScanTask(
                    path=item,
                    priority=TaskPriority.LOW,
                    task_type='asset',
                    source=source
                ))

        if pbo_batch:
            self._process_pbo_batch(pbo_batch, source)

    def _process_pbo_batch(self, pbo_files: List[Path], source: str) -> None:
        """Process a batch of PBO files in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def check_pbo(pbo_path: Path) -> Optional[Tuple[Path, TaskPriority]]:
            try:
                if str(pbo_path) in self.pbo_contents_cache:
                    _, _, paths = self.pbo_contents_cache[str(pbo_path)]
                    has_configs = any(str(p).endswith('.cpp') for p in paths)
                    priority = TaskPriority.HIGH if has_configs else TaskPriority.MEDIUM
                    return (pbo_path, priority)

                returncode, stdout, paths = self.pbo_extractor.list_pbo_contents(pbo_path)
                if returncode == 0:
                    self.pbo_contents_cache[str(pbo_path)] = (returncode, stdout, paths)
                    has_configs = any(str(p).endswith('.cpp') for p in paths)
                    priority = TaskPriority.HIGH if has_configs else TaskPriority.MEDIUM
                    return (pbo_path, priority)
                return None
            except Exception as e:
                self.logger.warning(f"Failed to preprocess PBO {pbo_path}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(check_pbo, pbo) for pbo in pbo_files]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    pbo_path, priority = result
                    self.task_manager.add_task(ScanTask(
                        path=pbo_path,
                        priority=priority,
                        task_type='pbo',
                        source=source
                    ))

    def _process_task(self, task: ScanTask) -> Optional[ScanResult]:
        """Process a single task"""
        try:
            self._report_progress(str(task.path))

            result = None
            if task.task_type == 'pbo':
                result = self._scan_pbo(task)
            else:
                result = self._scan_asset(task)

            if result is None:
                self.task_manager.complete_task(task.path, "Task failed to produce results", failed=True)
            else:
                self.task_manager.complete_task(task.path)
            return result

        except Exception as e:
            self.logger.error(f"Error processing {task.path}: {e}")
            self.task_manager.complete_task(task.path, str(e), failed=True)
            return None

    def _scan_pbo(self, task: ScanTask) -> Optional[ScanResult]:
        """Scan a PBO file"""
        try:
            if not task.path.exists():
                self.task_manager.complete_task(task.path, "File not found", failed=True)
                return None

            returncode, stdout, _ = self.pbo_extractor.list_contents(task.path)
            if returncode != 0:
                self.task_manager.complete_task(task.path, "Failed to list PBO contents", failed=True)
                return None

            prefix = self.pbo_extractor.extract_prefix(stdout)
            if prefix:
                prefix = prefix.replace('\\', '/').strip('/')

            pbo_key = str(task.path)
            if pbo_key in self.pbo_contents_cache:
                returncode, code_files, asset_paths = self.pbo_contents_cache[pbo_key]
            else:
                returncode, code_files, asset_paths = self.pbo_extractor.scan_pbo_contents(task.path)
                self.pbo_contents_cache[pbo_key] = (returncode, code_files, asset_paths)

            if returncode != 0:
                self.task_manager.complete_task(task.path, f"PBO scan failed with return code {returncode}", failed=True)
                return None

            if not asset_paths:
                self.task_manager.complete_task(task.path, "No valid assets found in PBO", failed=True)
                return None

            # Filter out .pbo files from assets list
            asset_paths = {p for p in asset_paths if not str(p).lower().endswith('.pbo')}

            assets = set()
            current_time = datetime.now()

            for path in asset_paths:
                try:
                    path_str = str(path).replace('\\', '/').strip('/')

                    if prefix and path_str.startswith(prefix):
                        path_str = path_str[len(prefix)+1:].strip('/')

                    # Normalize source to strip @ prefix
                    source = task.source.lstrip('@')

                    assets.add(Asset(
                        path=Path(path_str),
                        source=source,
                        last_scan=current_time,
                        has_prefix=bool(prefix),
                        pbo_path=task.path.relative_to(task.path.parent.parent)
                    ))
                except Exception as e:
                    self.logger.warning(f"Failed to create asset: {e}")

            self.task_manager.complete_task(task.path)
            return ScanResult(
                assets=assets,
                scan_time=current_time,
                prefix=prefix or '',
                source=task.source
            )

        except Exception as e:
            self.logger.error(f"Error scanning PBO {task.path}: {e}")
            self.task_manager.complete_task(task.path, str(e), failed=True)
            return None

    def _scan_asset(self, task: ScanTask) -> Optional[ScanResult]:
        """Scan a regular asset file"""
        if not task.path.exists():
            self.task_manager.complete_task(task.path, "File not found", failed=True)
            return None

        # Find mod root by source name
        mod_root = None
        for parent in task.path.parents:
            if parent.name == task.source:  # Look for exact match
                mod_root = parent
                break
                
        if mod_root:
            rel_path = task.path.relative_to(mod_root)
        else:
            rel_path = task.path.relative_to(task.path.parent.parent)
            

        clean_path = str(rel_path).replace('\\', '/')

        asset = Asset(
            path=Path(clean_path),
            source=task.source,  # Preserve exact source name
            last_scan=datetime.now(),
            has_prefix=False,
            pbo_path=None
        )

        self.task_manager.complete_task(task.path)
        return ScanResult(
            assets={asset}, 
            scan_time=datetime.now(),
            source=task.source
        )

    def _find_pbos(self, path: Path) -> List[Path]:
        """Find all PBO files in directory recursively"""
        if not path.exists():
            return []

        pbo_files = []
        for item in path.rglob("*.pbo"):
            if item.is_file():
                pbo_files.append(item)
        return pbo_files
