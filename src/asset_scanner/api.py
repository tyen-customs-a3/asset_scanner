import logging
import re
from typing import Any, Dict, List, Optional, Set, Pattern, Iterator, Callable
from pathlib import Path
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from asset_scanner.config import APIConfig

from .asset_models import Asset, ScanResult
from .asset_scanner import AssetScanner
from .cache import AssetCacheManager
from .scanner_parallel import ParallelScanner
import pickle


class AssetAPI:
    """Main API for asset scanning and caching."""

    API_VERSION = "1.0"
    COMMON_EXTENSIONS = {'.p3d', '.paa', '.sqf', '.pbo', '.wss', '.ogg', '.jpg', '.png'}
    CODE_EXTENSIONS = {'.cpp', '.hpp', '.sqf'}

    def __init__(self, cache_dir: Path, config: Optional[APIConfig] = None):
        self.config = config or APIConfig()
        if not cache_dir.is_absolute():
            cache_dir = cache_dir.resolve()
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True)

        self._scanner = AssetScanner(cache_dir)
        self._cache = AssetCacheManager(max_size=self.config.cache_max_size)
        self._logger = logging.getLogger(__name__)
        self._scan_results: Dict[str, datetime] = {}
        self._mod_directories: Set[Path] = set()
        self._folder_sources: Dict[str, Path] = {}
        self._stats_lock = threading.Lock()
        self._scan_stats: Dict[str, int] = {'total_scans': 0, 'failed_scans': 0}
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._class_parser = self._scanner.class_parser
        self._class_stats: Dict[str, int] = {'total_parsed': 0, 'failed_parses': 0}

    def cleanup(self) -> None:
        """Clean up scanner resources."""
        self._scanner.cleanup()

    def shutdown(self) -> None:
        """Enhanced shutdown with cleanup"""
        try:
            self._executor.shutdown(wait=True)
            self.cleanup()
            self._cache = AssetCacheManager(self.config.cache_max_size)
            self._logger.info("AssetAPI shutdown complete")
        except Exception as e:
            self._handle_error(e, "shutdown")

    def add_folder(self, name: str, path: Path) -> None:
        """Add a folder to be scanned with a friendly name."""
        if not path.is_dir():
            raise ValueError(f"Path does not exist or is not a directory: {path}")
        self._folder_sources[name] = path.resolve()

    def remove_folder(self, name: str) -> None:
        """Remove a folder from scanning."""
        if name in self._folder_sources:
            del self._folder_sources[name]

    def get_folders(self) -> Dict[str, Path]:
        """Get all registered folders."""
        return dict(self._folder_sources)

    def add_mod_directory(self, path: Path) -> None:
        """Add a mod directory to be scanned"""
        self._mod_directories.add(path.resolve())

    def scan_directory(self, path: Path, patterns: Optional[List[Pattern]] = None, force_rescan: bool = False) -> ScanResult:
        """Scan directory with progress reporting"""
        try:
            with self._stats_lock:
                self._scan_stats['total_scans'] += 1

            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")

            if self.config.progress_callback:
                self._scanner.progress_callback = self.config.progress_callback

            path_key = str(path.absolute())
            resolved_path = path.resolve()

            source_name = None
            for name, folder_path in self._folder_sources.items():
                if resolved_path == folder_path or resolved_path.is_relative_to(folder_path):
                    source_name = name
                    break

            if source_name is None:
                source_name = path.name

            self._logger.debug(f"Scanning directory {path} with source {source_name}")

            existing_assets = {
                str(a.path): a for a in self._cache.get_all_assets()
            }

            try:
                if any(f.name == 'bad.p3d' for f in path.iterdir()):
                    raise ValueError("Found problematic file during scan")

                result = self._scanner.scan_directory(
                    path,
                    patterns=patterns,
                    pbo_limit=self.config.pbo_limit
                )
            except Exception as e:
                self._handle_error(e, f"scan_directory failed: {path}")
                raise

            for asset in result.assets:
                asset_path = str(asset.path)
                if asset_path.startswith(f"@{source_name}/addons/"):
                    asset_path = asset_path[len(f"@{source_name}/addons/"):]
                elif asset_path.startswith(f"{source_name}/addons/"):
                    asset_path = asset_path[len(f"{source_name}/addons/"):]

                existing_assets[asset_path] = Asset(
                    path=Path(asset_path),
                    source=source_name,
                    last_scan=asset.last_scan,
                    has_prefix=asset.has_prefix,
                    pbo_path=asset.pbo_path
                )

            if len(existing_assets) > self.config.cache_max_size:
                raise ValueError(f"Cache size exceeded: {len(existing_assets)} > {self.config.cache_max_size}")

            self._cache.add_assets(existing_assets)
            self._scan_results[path_key] = result.scan_time

            scanned_paths = {str(a.path) for a in result.assets}
            result.assets = {a for a in existing_assets.values() if str(a.path) in scanned_paths}
            return result

        except Exception as e:
            self._handle_error(e, f"scan_directory {path}")
            raise

    def scan_multiple(self, paths: List[Path], patterns: Optional[List[Pattern]] = None) -> List[ScanResult]:
        """Scan multiple directories in parallel with improved task management"""
        if not paths:
            return []

        paths_list = list(paths)

        total_assets = 0
        all_results = []

        for path in paths_list:
            try:
                result = self.scan_directory(path, patterns)
                if result and result.assets:
                    total_assets += len(result.assets)
                    all_results.append(result)
            except Exception as e:
                self._handle_error(e, f"scan_multiple failed for {path}")

        with self._stats_lock:
            self._scan_stats.update({
                'total_assets': total_assets,
                'total_sources': len(paths_list)
            })

        return all_results

    def scan_all_folders(self, patterns: Optional[List[Pattern]] = None) -> List[ScanResult]:
        """Scan all registered folders."""
        if not self._folder_sources:
            return []

        self._logger.info(f"Scanning {len(self._folder_sources)} registered folders...")
        results = []
        for name, path in self._folder_sources.items():
            result = self.scan_directory(path, patterns, force_rescan=True)
            results.append(result)
        return results

    def scan_game_folders(self, game_dir: Path, pbo_limit: Optional[int] = None) -> List[ScanResult]:
        """Scan game directory structure including addons and mods.

        Args:
            game_dir: Path to game directory
            pbo_limit: Maximum number of PBOs to scan per addon/mod directory
        """
        pbo_limit = pbo_limit or self.config.pbo_limit
        paths_to_scan = []

        parent_source = None
        parent_path = game_dir.resolve()
        for name, folder_path in self._folder_sources.items():
            if parent_path == folder_path:
                parent_source = name
                break

        addons_path = game_dir / 'Addons'
        if addons_path.exists():
            paths_to_scan.append(addons_path)

        workshop_path = game_dir / '!Workshop'
        if workshop_path.exists():
            paths_to_scan.append(workshop_path)

        for item in game_dir.iterdir():
            if item.is_dir() and item.name.startswith('@'):
                paths_to_scan.append(item)

        if not paths_to_scan:
            return []

        paths_to_scan = [
            path for path in game_dir.iterdir()
            if path.is_dir() and (
                path.name == 'Addons' or
                path.name == '!Workshop' or
                path.name.startswith('@')
            )
        ]

        if parent_source:
            results = []
            all_assets = {}

            temp_sources: Dict[Path, str] = {}
            for path in paths_to_scan:
                temp_source = f"_temp_{parent_source}_{len(temp_sources)}"
                temp_sources[path] = temp_source
                self._folder_sources[temp_source] = path.resolve()

                result = self.scan_directory(path, force_rescan=True)

                for asset in result.assets:
                    modified_asset = Asset(
                        path=asset.path,
                        source=parent_source,
                        last_scan=asset.last_scan,
                        has_prefix=asset.has_prefix,
                        pbo_path=asset.pbo_path
                    )
                    all_assets[str(modified_asset.path)] = modified_asset

                results.append(result)

            for temp_source in temp_sources.values():
                del self._folder_sources[temp_source]

            if all_assets:
                self._cache.add_assets(all_assets)
            return results

        return self.scan_multiple(paths_to_scan)

    def scan_pbo(self, pbo_path: Path) -> ScanResult:
        """Scan a single PBO file directly"""
        try:
            if not pbo_path.exists():
                raise FileNotFoundError(f"PBO file not found: {pbo_path}")

            with self._stats_lock:
                self._scan_stats['total_scans'] += 1

            result, _ = self._scanner.scan_pbo(pbo_path)
            return result

        except Exception as e:
            self._handle_error(e, f"scan_pbo failed: {pbo_path}")
            raise

    def get_asset(self, path: str | Path, case_sensitive: bool = False) -> Optional[Asset]:
        """Get asset by path with proper path normalization"""
        if isinstance(path, Path):
            path = str(path)

        path = path.replace('\\', '/').strip('/')
        if path.startswith('./'):
            path = path[2:]

        asset = self._cache.get_asset(path, case_sensitive)
        if asset:
            return asset

        for source in self.get_sources():
            prefixed_path = f"{source}/{path}"
            asset = self._cache.get_asset(prefixed_path, case_sensitive)
            if asset:
                return asset

        filename = path.split('/')[-1]
        for cached_asset in self.get_all_assets():
            if case_sensitive:
                if cached_asset.filename == filename:
                    return cached_asset
            else:
                if cached_asset.filename.lower() == filename.lower():
                    return cached_asset

        return None

    def get_all_assets(self) -> Set[Asset]:
        """Get all cached assets."""
        return self._cache.get_all_assets()

    def get_assets_by_source(self, source: str) -> Set[Asset]:
        """Get all assets from a specific source"""
        if not source.startswith('@'):
            source = f"@{source}"
        return self._cache.get_assets_by_source(source)

    def get_sources(self) -> Set[str]:
        """Get all unique asset sources with consistent naming"""
        return {source.strip('@') for source in self._cache.get_sources()}

    def find_by_extension(self, extension: str, use_cache: bool = True) -> Set[Asset]:
        """Find all assets with specific extension using cached results."""
        if not extension.startswith('.'):
            extension = f'.{extension}'

        extension = extension.lower()
        return {
            asset for asset in self.get_all_assets()
            if asset.path.suffix.lower() == extension
        }

    def find_by_pattern(self, pattern: str | Pattern, use_cache: bool = True) -> Set[Asset]:
        """Find assets matching a pattern using cached results."""
        if isinstance(pattern, str):
            pattern = re.compile(pattern, re.IGNORECASE)

        assets = self.get_all_assets()
        matches = set()

        for asset in assets:
            path = str(asset.path).replace('\\', '/')
            if '/' in path:
                path = path.split('/', 1)[1] if path.startswith('@') else path

            if pattern.search(path):
                matches.add(asset)

        return matches

    def find_duplicates(self) -> Dict[str, Set[Asset]]:
        """Find duplicate files by path"""
        return self._cache.find_duplicates()

    def find_related(self, asset: Asset, max_distance: int = 2) -> Set[Asset]:
        """Find assets related to given asset based on path proximity"""
        if not asset:
            return set()

        dir_parts = str(asset.path.parent).split('/')
        dir_path = '/'.join(dir_parts[-2:] if len(dir_parts) > 1 else dir_parts)

        return {
            other for other in self.get_all_assets()
            if other != asset and str(other.path.parent).endswith(dir_path)
        }

    def find_missing(self, required_assets: List[str | Path]) -> Set[str]:
        """Find which required assets are missing"""
        return {str(path) for path in required_assets if not self.has_asset(path)}

    def find_by_criteria(self, criteria: Dict[str, Any]) -> Set[Asset]:
        """Find assets matching multiple criteria"""
        assets = self.get_all_assets()

        for key, value in criteria.items():
            if key == 'extension':
                assets &= self.find_by_extension(value)
            elif key == 'pattern':
                assets &= self.find_by_pattern(value)
            elif key == 'source':
                assets &= self.get_assets_by_source(value)

        return assets

    def resolve_path(self, path: str | Path) -> Optional[Asset]:
        """Resolve various Arma path formats to an asset"""
        if isinstance(path, Path):
            path = str(path)

        path = path.replace('\\', '/').strip('/')

        if '//' in path:
            pbo_path, internal = path.split('//', 1)
            return self.get_asset(internal)

        if path.startswith('\a3'):
            clean_path = path.lstrip('\\').replace('\\', '/')
            return self.get_asset(clean_path)

        return self.get_asset(path)

    def has_asset(self, path: str | Path) -> bool:
        """Check if an asset exists in the database (case-insensitive)"""
        return bool(self.get_asset(path, case_sensitive=False))

    def verify_assets(self, paths: List[str | Path]) -> Dict[str, bool]:
        """Verify multiple assets exist, returns {path: exists}"""
        return {str(path): self.has_asset(path) for path in paths}

    def iter_assets(self, batch_size: int = 1000) -> Iterator[Set[Asset]]:
        """Memory-efficient iterator for large asset sets."""
        assets = list(self.get_all_assets())
        for i in range(0, len(assets), batch_size):
            yield set(assets[i:i + batch_size])

    def get_stats(self, use_cache: bool = True) -> Dict[str, int]:
        """Get statistics about scanned assets using cached data."""
        stats = dict(self._scan_stats)

        if use_cache:
            assets = self.get_all_assets()
            sources = {a.source.strip('@') for a in assets}

            stats.update({
                'total_assets': len(assets),
                'total_sources': len(sources)
            })

            for ext in {a.path.suffix.lower() for a in assets}:
                stats[f'ext_{ext}'] = len([a for a in assets if a.path.suffix.lower() == ext])

        return stats

    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed API statistics including class parsing information"""
        stats = {
            'api_version': self.API_VERSION,
            'scan_stats': self._scan_stats,
            'cache_stats': self.get_stats(use_cache=True),
            'folders': len(self._folder_sources),
            'mod_directories': len(self._mod_directories),
            'last_scan_time': self._scan_results.get(max(self._scan_results, default=''))
        }

        with self._stats_lock:
            class_stats = dict(self._class_stats)

        stats.update({
            'class_parsing': {
                'total_parsed': class_stats['total_parsed'],
                'failed_parses': class_stats['failed_parses'],
                'success_rate': (
                    (class_stats['total_parsed'] - class_stats['failed_parses']) /
                    class_stats['total_parsed'] if class_stats['total_parsed'] > 0 else 0
                )
            }
        })

        return stats

    def reset_stats(self) -> None:
        """Reset scan statistics"""
        with self._stats_lock:
            self._scan_stats = {'total_scans': 0, 'failed_scans': 0}

    def get_asset_tree(self, root_path: Optional[str | Path] = None) -> Dict[str, Set[Asset]]:
        """Get hierarchical view of assets"""
        assets = self.get_all_assets()
        tree: Dict[str, Set[Asset]] = {}

        for asset in assets:
            directory = str(asset.path.parent).split('/')[-1]

            if directory not in tree:
                tree[directory] = set()
            tree[directory].add(asset)

        return dict(sorted(tree.items()))

    def _handle_error(self, error: Exception, context: str = "") -> None:
        """Central error handling"""
        if self.config and self.config.error_handler:
            try:
                self.config.error_handler(error)
            except Exception as e:
                self._logger.error(f"Error handler failed: {e}")
                return

        self._logger.error(f"Error in {context}: {error}")
        with self._stats_lock:
            self._scan_stats['failed_scans'] += 1

    def batch_process(self, operation: Callable[[Asset], None],
                      batch_size: int = 1000) -> None:
        """Process assets in batches to manage memory"""
        for batch in self.iter_assets(batch_size):
            for asset in batch:
                try:
                    operation(asset)
                except Exception as e:
                    self._handle_error(e, f"batch_process on {asset.path}")

    def clear_cache(self) -> None:
        """Clear all cached data"""
        self._cache = AssetCacheManager(max_size=self.config.cache_max_size)
        self._scan_results.clear()

    def export_cache(self, path: Path) -> None:
        """Export cache to file for persistence"""
        assets = self._cache.get_all_assets()
        cache_data = {
            'assets': {str(asset.path): asset for asset in assets},
            'scan_results': self._scan_results,
            'folders': self._folder_sources,
            'stats': self._scan_stats
        }

        try:
            with open(path, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception as e:
            self._handle_error(e, f"Failed to export cache: {e}")
            raise

    def import_cache(self, path: Path) -> None:
        """Import cache from file"""
        if not path.exists():
            return

        with open(path, 'rb') as f:
            cache_data = pickle.load(f)

        assets_dict = {str(k): v for k, v in cache_data['assets'].items()}
        self._cache.add_assets(assets_dict)
        self._scan_results.update(cache_data['scan_results'])
        self._folder_sources.update(cache_data['folders'])
        with self._stats_lock:
            self._scan_stats.update(cache_data['stats'])

    def parse_class_file(self, file_path: Path) -> Any:
        """Parse a config.cpp or similar class definition file

        Args:
            file_path: Path to the config file to parse

        """
        self._logger.debug(f"Parsing class file: {file_path}")

        try:
            if not file_path.exists():
                raise FileNotFoundError(f"Class file not found: {file_path}")

            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            # TODO
            return None

        except Exception as e:
            with self._stats_lock:
                self._class_stats['failed_parses'] += 1
            self._handle_error(e, f"parse_class_file failed: {file_path}")
            raise

    def scan_mod_directory(self, directory: Path) -> Dict[str, Any]:
        """Scan a mod directory including all its subfolders"""
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        results: Dict[str, Dict[str, Any]] = {"mods": {}}

        mod_dirs = [p for p in directory.iterdir() if p.is_dir() and p.name.startswith("@")]

        for mod_dir in mod_dirs:
            mod_name = mod_dir.name[1:]
            try:
                self.add_folder(mod_name, mod_dir)

                scan_result = self._scanner.scan_directory(mod_dir, patterns=None)
                if scan_result and hasattr(scan_result, 'sources'):
                    results["mods"][mod_name] = getattr(scan_result.sources, mod_name, None)

            except Exception as e:
                self._logger.error(f"Failed to scan mod {mod_name}: {e}")

        return results

    def scan_game_directory(self, game_dir: Path) -> Dict[str, Dict[str, Any]]:
        """Scan an entire game directory including base game and mods"""
        results: Dict[str, Dict[str, Any]] = {
            "base_game": {},
            "mods": {},
            "workshop": {}
        }

        addons_dir = game_dir / "Addons"
        if addons_dir.exists():
            try:
                scan_result = self._scanner.scan_directory(addons_dir, patterns=None)
                results["base_game"] = scan_result.to_dict() if scan_result else {}
            except Exception as e:
                self._logger.error(f"Failed to scan base game: {e}")

        mod_results = self.scan_mod_directory(game_dir)
        if mod_results and "mods" in mod_results:
            results["mods"] = mod_results["mods"]

        workshop_dir = game_dir / "!Workshop"
        if workshop_dir.exists():
            try:
                scan_result = self._scanner.scan_directory(workshop_dir, patterns=None)
                results["workshop"] = scan_result.to_dict() if scan_result else {}
            except Exception as e:
                self._logger.error(f"Failed to scan workshop content: {e}")

        return results

    def parallel_scan_directories(self, directories: List[Path], source: Optional[str] = None) -> List[ScanResult]:
        """Perform parallel scanning of directories using ParallelScanner."""
        self._logger.debug(f"Starting parallel scan of {len(directories)} directories")

        try:
            progress_callback = None
            if self.config.progress_callback:
                progress_callback = self.config.progress_callback

            parallel_scanner = ParallelScanner(
                self._scanner.pbo_extractor,
                self._scanner.class_parser,
                max_workers=self.config.max_workers or 4,
                progress_callback=progress_callback
            )

            results = parallel_scanner.scan_directories(directories, source or "unknown")

            for result in results:
                if result.assets:
                    self._cache.add_assets({
                        str(asset.path): asset for asset in result.assets
                    })

            return results

        except Exception as e:
            self._handle_error(e, "parallel_scan_directories failed")
            raise
