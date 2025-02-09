from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, List, Set, Dict, Optional, Tuple
from datetime import datetime
import logging

from .asset_models import ScanResult, Asset
from .scanner_tasks import ScanTask, TaskManager, TaskStatus, TaskPriority

class ParallelScanner:
    """Unified scanner implementation"""
    ASSET_EXTENSIONS = {'.p3d', '.paa', '.rtm', '.jpg', '.jpeg', '.png', '.tga', '.wrp', '.pac', '.lip'}

    def __init__(self, pbo_extractor: Any, max_workers: int = 3):
        self.pbo_extractor = pbo_extractor
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        self.task_manager = TaskManager(max_workers=self.max_workers)

    def discover_loose_files(self, directories: List[Path]) -> Dict[str, List[Path]]:
        """Stage 1: Discover loose asset files"""
        loose_files: Dict[str, List[Path]] = {'assets': [], 'pbos': []}
        total_dirs = len(directories)
        processed_dirs = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_dir = {
                executor.submit(self._scan_directory, directory): directory
                for directory in directories
            }

            for future in as_completed(future_to_dir):
                directory = future_to_dir[future]
                try:
                    assets, pbos = future.result()
                    loose_files['assets'].extend(assets)
                    loose_files['pbos'].extend(pbos)

                except Exception as e:
                    self.logger.error(f"Error scanning directory {directory}: {e}")

        return loose_files

    def _scan_directory(self, directory: Path) -> Tuple[List[Path], List[Path]]:
        """Scan directory separating assets and PBOs"""
        assets = []
        pbos = []
        try:
            for item in directory.rglob('*'):
                if item.is_file():
                    suffix = item.suffix.lower()
                    if suffix == '.pbo':
                        pbos.append(item)
                    elif suffix in self.ASSET_EXTENSIONS:
                        assets.append(item)
        except Exception as e:
            self.logger.error(f"Error scanning {directory}: {e}")
        return assets, pbos

    def scan_pbo_contents(self, pbo_files: List[Path]) -> Dict[Path, Tuple[str, Set[str]]]:
        """Stage 2: List contents of all PBOs and get their prefixes"""
        pbo_contents: Dict[Path, Tuple[str, Set[str]]] = {}
        total_pbos = len(pbo_files)
        processed_pbos = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_pbo = {
                executor.submit(self.pbo_extractor.list_contents, pbo): pbo
                for pbo in pbo_files
            }

            for future in as_completed(future_to_pbo):
                pbo = future_to_pbo[future]
                try:
                    returncode, stdout, stderr = future.result()
                    if returncode == 0:
                        prefix = self.pbo_extractor.extract_prefix(stdout)
                        prefix_clean = prefix.replace('\\', '/').strip('/') if prefix else ''

                        paths = set()
                        for line in stdout.splitlines():
                            line = line.strip()
                            if line and not line.startswith(('$', 'prefix=', 'Active code page:', 'Opening ', '==')):
                                clean_path = line.replace('\\', '/').strip('/')
                                if clean_path:
                                    paths.add(clean_path)

                        pbo_contents[pbo] = (prefix_clean, paths)

                except Exception as e:
                    self.logger.error(f"Error listing contents of {pbo}: {e}")

        return pbo_contents

    def scan_directories(self, directories: List[Path], source: str = "None") -> List[ScanResult]:
        """Scan directories preserving original source names"""
        try:
            results = []
            self.logger.info("Discovering files...")
            loose_files = self.discover_loose_files(directories)
            
            # Track processed assets to avoid duplicates
            processed_paths = set()
            
            for directory in directories:
                dir_source = directory.name
                dir_files = [
                    f for f in loose_files['assets'] 
                    if directory in f.parents and f not in processed_paths
                ]
                
                if dir_files:
                    for result in self._process_loose_assets(dir_files, dir_source):
                        results.append(result)
                        processed_paths.update(a.path for a in result.assets)

                dir_pbos = [
                    p for p in loose_files['pbos'] 
                    if directory in p.parents and p not in processed_paths
                ]
                if dir_pbos:
                    pbo_contents = self.scan_pbo_contents(dir_pbos)
                    pbo_results = self._process_pbo_results(pbo_contents, dir_source)
                    results.extend(pbo_results)
                    for r in pbo_results:
                        processed_paths.update(a.path for a in r.assets)

            return results

        except Exception as e:
            self.logger.error(f"Error during scanning: {e}")
            return []

    def _process_loose_assets(self, asset_files: List[Path], source: str) -> List[ScanResult]:
        """Process loose asset files in parallel"""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._create_asset_result, path, source)
                for path in asset_files
            ]
            for future in as_completed(futures):
                try:
                    if result := future.result():
                        results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing loose asset: {e}")
        return results

    def _process_pbo_results(
        self,
        pbo_contents: Dict[Path, Tuple[str, Set[str]]],
        source: str
    ) -> List[ScanResult]:
        """Process PBO contents and create final results"""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for pbo, (prefix, paths) in pbo_contents.items():
                future = executor.submit(
                    self._create_pbo_result,
                    pbo,
                    prefix,
                    paths,
                    source
                )
                futures[future] = pbo

            for future in as_completed(futures):
                if result := future.result():
                    results.append(result)

        return results

    def _create_asset_result(self, path: Path, source: str) -> Optional[ScanResult]:
        try:
            if not path.exists():
                return None

            current_time = datetime.now()
            
            # Find the mod root directory and get relative path
            mod_root = None
            for parent in path.parents:
                if parent.name == source:  # Match exact source name
                    mod_root = parent
                    break
            
            if mod_root:
                # Get path relative to mod root, preserve structure
                rel_path = path.relative_to(mod_root)
            else:
                # Fallback to parent.parent if no mod root found
                rel_path = path.relative_to(path.parent.parent)

            # Clean up path but preserve exact source
            clean_path = str(rel_path).replace('\\', '/')

            asset = Asset(
                path=Path(clean_path),
                source=source,  # Keep exact source name
                last_scan=current_time,
                has_prefix=False
            )

            return ScanResult(
                assets={asset},
                scan_time=current_time,
                source=source,
                path=path
            )

        except Exception as e:
            self.logger.error(f"Error processing asset {path}: {e}")
            return None

    def _create_pbo_result(
        self,
        pbo_path: Path,
        prefix: Optional[str],
        file_paths: Set[str],
        source: str
    ) -> Optional[ScanResult]:
        """Create result for a PBO file with parallel processing"""
        try:
            current_time = datetime.now()
            
            pbo_asset = Asset(
                path=pbo_path.relative_to(pbo_path.parent.parent),
                source=source,
                last_scan=current_time,
                has_prefix=bool(prefix)
            )
            
            assets = {pbo_asset}
            
            if prefix:
                prefix = prefix.replace('\\', '/').strip('/')

            for path in file_paths:
                path_lower = path.lower()
                if any(path_lower.endswith(ext) for ext in self.ASSET_EXTENSIONS):
                    clean_path = path.replace('\\', '/').strip('/')
                    assets.add(Asset(
                        path=Path(clean_path),
                        source=source,
                        last_scan=current_time,
                        has_prefix=bool(prefix),
                        pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                    ))

            return ScanResult(
                path=pbo_path,
                prefix=prefix or '',
                assets=assets,
                scan_time=current_time,
                source=source
            )

        except Exception as e:
            self.logger.error(f"Error processing PBO {pbo_path}: {e}")
            raise

    def _process_task(self, task: ScanTask) -> Optional[ScanResult]:
        """Process a single task with proper error handling"""
        try:
            task.status = TaskStatus.PROCESSING
            task.start_time = datetime.now()

            msg = f"Processing {task.path.name}"
            self.logger.debug(msg)

            result = None
            try:
                if task.task_type == 'pbo':
                    result = self._scan_pbo(task)
                else:
                    result = self._scan_asset(task)

                if result:
                    msg = f"Completed {task.path.name}"
                    task.status = TaskStatus.COMPLETED
                else:
                    msg = f"Failed {task.path.name}"
                    task.status = TaskStatus.FAILED
                    task.error = "Failed to process task"

                self.logger.debug(msg)

            except Exception as e:
                error_msg = f"Failed {task.path.name}: {e}"
                self.logger.error(error_msg)

                task.status = TaskStatus.FAILED
                task.error = str(e)
                result = None

            return result

        finally:
            task.end_time = datetime.now()
            self.task_manager.complete_task(
                task.path,
                error=task.error or '',
                failed=task.status == TaskStatus.FAILED
            )

    def _scan_pbo(self, task: ScanTask) -> Optional[ScanResult]:
        """Scan a PBO file for task processing"""
        try:
            current_time = datetime.now()
            assets = set()
            
            returncode, stdout, stderr = self.pbo_extractor.list_contents(task.path)
            if returncode != 0:
                return None
                
            prefix = self.pbo_extractor.extract_prefix(stdout)
            if prefix:
                prefix = prefix.replace('\\', '/').strip('/')
                
            pbo_asset = Asset(
                path=task.path.relative_to(task.path.parent.parent),
                source=task.source,
                last_scan=current_time,
                has_prefix=bool(prefix)
            )
            assets.add(pbo_asset)
            
            return ScanResult(
                path=task.path,
                prefix=prefix or '',
                assets=assets,
                scan_time=current_time,
                source=task.source
            )
            
        except Exception as e:
            self.logger.error(f"Error processing PBO task {task.path}: {e}")
            return None

    def _scan_asset(self, task: ScanTask) -> Optional[ScanResult]:
        """Scan a regular asset file for task processing"""
        try:
            if not task.path.exists():
                return None
                
            # Find mod root directory
            mod_root = None
            for parent in task.path.parents:
                if parent.name == task.source:
                    mod_root = parent
                    break

            # Get relative path preserving structure
            if mod_root:
                rel_path = task.path.relative_to(mod_root)
            else:
                rel_path = task.path.relative_to(task.path.parent.parent)

            clean_path = str(rel_path).replace('\\', '/')
            
            asset = Asset(
                path=Path(clean_path),
                source=task.source,  # Keep exact source name
                last_scan=datetime.now(),
                has_prefix=False
            )
            
            return ScanResult(
                assets={asset},
                scan_time=datetime.now(),
                source=task.source,
                path=task.path
            )
            
        except Exception as e:
            self.logger.error(f"Error processing asset task {task.path}: {e}")
            return None

