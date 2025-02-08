from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, List, Set, Dict, Optional, Callable, Tuple
from datetime import datetime
import logging
import os

from asset_scanner.pbo_extractor import PboExtractor
from .scanner_base import BaseScanner
from .asset_models import ScanResult, Asset
from .scanner_tasks import ScanTask, TaskManager, TaskStatus
from asset_scanner.types.progress_callback import ProgressCallbackType


class ParallelScanner(BaseScanner):
    """Parallel scanner with distinct processing stages"""

    def __init__(self,
                 pbo_extractor: Any,
                 class_parser: Any,
                 max_workers: int = 3,
                 progress_callback: Optional[ProgressCallbackType] = None) -> None:
        super().__init__(pbo_extractor, class_parser, progress_callback)
        self.max_workers = max_workers
        self.progress_callback = progress_callback
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
                    if self.progress_callback:
                        processed_dirs += 1
                        self.progress_callback(
                            f"Found {len(assets)} assets and {len(pbos)} PBOs in {directory}",
                            processed_dirs / total_dirs
                        )
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
                    if item.suffix.lower() == '.pbo':
                        pbos.append(item)
                    elif item.suffix.lower() in self.ASSET_EXTENSIONS:
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
                        if self.progress_callback:
                            processed_pbos += 1
                            self.progress_callback(
                                f"Listed {len(paths)} files in {pbo.name}",
                                processed_pbos / total_pbos
                            )
                except Exception as e:
                    self.logger.error(f"Error listing contents of {pbo}: {e}")

        return pbo_contents

    def extract_code_files(self, pbo_contents: Dict[Path, Tuple[str, Set[str]]]) -> Dict[Path, Dict[str, str]]:
        """Stage 3: Extract and parse code files"""
        code_files = {}

        code_pbos = {}
        for pbo, (_, paths) in pbo_contents.items():
            if any(str(p).lower().endswith(('.cpp', '.hpp', '.bin', 'config.bin'))
                   for p in paths):
                code_pbos[pbo] = paths

        self.logger.debug(f"Found {len(code_pbos)} PBOs with potential code files")

        total_files = len(code_pbos)
        processed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_pbo = {
                executor.submit(
                    self.pbo_extractor.extract_code_files,
                    pbo,
                    {'.cpp', '.hpp'}
                ): pbo
                for pbo in code_pbos.keys()
            }

            for future in as_completed(future_to_pbo):
                pbo = future_to_pbo[future]
                try:
                    extracted_files = future.result()
                    if extracted_files:
                        self.logger.debug(f"Got {len(extracted_files)} files from {pbo.name}")
                        code_files[pbo] = extracted_files
                        if self.progress_callback:
                            processed += 1
                            self.progress_callback(
                                f"Extracted {len(extracted_files)} files from {pbo.name}",
                                processed / total_files
                            )
                except Exception as e:
                    self.logger.error(f"Failed to extract from {pbo}: {e}")

        return code_files

    def scan_class_files(self, code_files: Dict[Path, Dict[str, str]]) -> Any:
        """Stage 4: Parse and process class files"""
        self.logger.debug(f"Starting class file scanning for {len(code_files)} PBOs")
        class_results = {}

        total_files = len(code_files)
        processed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for pbo_path, files in code_files.items():
                self.logger.debug(f"Submitting {len(files)} files from {pbo_path.name} for class parsing")
                future = executor.submit(self._process_class_files, files, pbo_path)
                futures[future] = pbo_path

            for future in as_completed(futures):
                pbo_path = futures[future]
                try:
                    if result := future.result():
                        self.logger.debug(f"Got {len(result.classes)} classes from {pbo_path.name}")
                        class_results[pbo_path] = result
                        if self.progress_callback:
                            processed += 1
                            self.progress_callback(
                                f"Processed {len(result.classes)} classes from {pbo_path.name}",
                                processed / total_files
                            )
                except Exception as e:
                    self.logger.error(f"Error processing classes from {pbo_path}: {e}")

        self.logger.debug(f"Completed class scanning. Found classes in {len(class_results)} PBOs")
        return class_results

    def _process_class_files(
        self,
        files: Dict[str, str],
        pbo_path: Optional[Path] = None,
        mod_name: Optional[str] = None
    ) -> Any:
        # TODO 
        return None

    def scan_directories(self, directories: List[Path], source: str = "None") -> List[ScanResult]:
        """Main scanning method with expanded stages"""
        try:
            results = []
            stage = 1
            total_stages = 5

            self.logger.info("Stage 1: Discovering loose files...")
            if self.progress_callback:
                self.progress_callback("Starting asset scan", 0.0)

            loose_files = self.discover_loose_files(directories)
            self.logger.info(
                f"Found {len(loose_files['assets'])} loose assets and "
                f"{len(loose_files['pbos'])} PBOs"
            )

            if loose_files['assets']:
                asset_results = self._process_loose_assets(loose_files['assets'], source)
                results.extend(asset_results)

            if not loose_files['pbos']:
                return results

            self.logger.info("Stage 2: Scanning PBO contents...")
            pbo_contents = self.scan_pbo_contents(loose_files['pbos'])

            self.logger.info("Stage 3: Processing code files...")
            code_files = self.extract_code_files(pbo_contents)

            self.logger.info("Stage 4: Processing class files...")
            class_results = self.scan_class_files(code_files)

            self.logger.info("Stage 5: Creating final results...")
            pbo_results = self._process_pbo_results(pbo_contents, class_results, source)
            results.extend(pbo_results)

            if self.progress_callback:
                self.progress_callback("Scan completed", 1.0)

            return results

        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"Error during scanning: {e}", 1.0)
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

        task_sources = {
            task.path: task
            for task in self.task_manager.tasks.values()
        }

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for pbo, (prefix, paths) in pbo_contents.items():
                task = task_sources.get(pbo)
                if task:
                    task.status = TaskStatus.PROCESSING
                    task.start_time = datetime.now()

                future = executor.submit(
                    self._create_pbo_result,
                    pbo,
                    prefix,
                    paths,
                    task.source if task else source
                )
                futures[future] = (pbo, task)

            for future in as_completed(futures):
                pbo, task = futures[future]
                try:
                    if result := future.result():
                        results.append(result)
                        if task:
                            task.status = TaskStatus.COMPLETED
                            task.end_time = datetime.now()
                    else:
                        if task:
                            task.status = TaskStatus.FAILED
                            task.error = "Failed to create result"
                except Exception as e:
                    self.logger.error(f"Error creating PBO result: {e}")
                    if task:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        task.end_time = datetime.now()

        return results

    def _create_asset_result(self, path: Path, source: str) -> Optional[ScanResult]:
        """Create result for a loose asset file"""
        try:
            if not path.exists():
                return None

            current_time = datetime.now()
            asset = Asset(
                path=path,
                source=source,
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
            self.logger.debug(f"Creating PBO result for {pbo_path.name}")

            assets = set()
            asset_extensions = {ext.lower() for ext in self.ASSET_EXTENSIONS}

            if prefix:
                prefix = prefix.replace('\\', '/').strip('/')

            for path in file_paths:
                path_lower = path.lower()
                if any(path_lower.endswith(ext) for ext in asset_extensions):
                    clean_path = path.replace('\\', '/').strip('/')
                    # Remove the source prefix if present
                    if source and clean_path.startswith(source + '/'):
                        clean_path = clean_path[len(source)+1:].strip('/')
                    
                    assets.add(Asset(
                        path=Path(clean_path),
                        source=source,
                        last_scan=current_time,
                        has_prefix=bool(prefix),
                        pbo_path=pbo_path.relative_to(pbo_path.parent.parent)
                    ))

            result = ScanResult(
                path=pbo_path,
                prefix=prefix or '',
                assets=assets,
                scan_time=current_time,
                source=source
            )

            self.logger.debug(
                f"Final PBO result for {pbo_path.name}: "
                f"{len(assets)} assets, "
            )
            return result

        except Exception as e:
            self.logger.error(f"Error processing PBO {pbo_path}: {e}")
            raise

    def _parse_code_file(self, file_path: str, content: str, pbo_path: Optional[Path] = None, mod_name: Optional[str] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        """Parse a single code file in parallel"""
        try:
            parsed_classes, inheritance, properties = self.class_parser.parse(str(content))
            result: Dict[str, Dict[str, Any]] = {}
            
            for class_name, props in parsed_classes.items():
                str_class_name = str(class_name)
                result[str_class_name] = {
                    'properties': {str(k): str(v) for k, v in props.items()} if props else {},
                    'parent': str(inheritance.get(class_name, '')),
                    'source_pbo': str(pbo_path) if pbo_path else '',
                    'source_mod': str(mod_name) if mod_name else ''
                }
            return result
        except Exception as e:
            self.logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def _process_task(self, task: ScanTask) -> Optional[ScanResult]:
        """Process a single task with proper error handling"""
        try:
            task.status = TaskStatus.PROCESSING
            task.start_time = datetime.now()

            msg = f"Processing {task.path.name}"
            self.logger.debug(msg)
            if self.progress_callback:
                self.progress_callback(msg, 0.0)

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
                if self.progress_callback:
                    self.progress_callback(msg, 1.0)

            except Exception as e:
                error_msg = f"Failed {task.path.name}: {e}"
                self.logger.error(error_msg)
                if self.progress_callback:
                    self.progress_callback(error_msg, 1.0)
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

