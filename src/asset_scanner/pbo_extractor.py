import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set, List
import shutil
import tempfile
import threading
import uuid

logger = logging.getLogger(__name__)

class PboExtractor:
    """Helper class for PBO file operations using extractpbo tool"""
    
    CODE_EXTENSIONS = {'.cpp', '.hpp', '.sqf'}
    BIN_FILE_TYPES = {
        'config.bin': 'config.cpp',
        'texHeaders.bin': 'texHeaders.hpp',
        'stringtable.bin': 'stringtable.xml',
        'model.bin': 'model.cfg'
    }
    
    def __init__(self, timeout: int = 30):
        """Initialize PBO extractor with timeout
        
        Args:
            timeout: Maximum time in seconds to wait for extractpbo operations
        """
        self.timeout = timeout
        self._temp_dirs: Dict[str, Path] = {}
        self._lock = threading.Lock()

    def __del__(self) -> None:
        """Cleanup temporary resources"""
        self.cleanup()

    def cleanup(self) -> None:
        """Remove all temporary directories"""
        with self._lock:
            for temp_dir in self._temp_dirs.values():
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._temp_dirs.clear()

    def _get_temp_dir(self, operation_id: str = "") -> Path:
        """Get or create temporary directory for an operation
        
        Args:
            operation_id: Unique identifier for this operation
        """
        if operation_id is "":
            operation_id = str(uuid.uuid4())
            
        with self._lock:
            if operation_id not in self._temp_dirs:
                temp_dir = Path(tempfile.mkdtemp(prefix=f'pbo_extractor_{operation_id}_'))
                self._temp_dirs[operation_id] = temp_dir
            return self._temp_dirs[operation_id]

    def _cleanup_temp_dir(self, operation_id: str) -> None:
        """Clean up temporary directory for a specific operation"""
        with self._lock:
            if operation_id in self._temp_dirs:
                shutil.rmtree(self._temp_dirs[operation_id], ignore_errors=True)
                del self._temp_dirs[operation_id]

    def list_pbo_contents(self, pbo_path: Path) -> tuple[int, str, str]:
        """Alias for list_contents to maintain backwards compatibility"""
        return self.list_contents(pbo_path)

    def list_contents(self, pbo_path: Path) -> tuple[int, str, str]:
        """List contents of PBO file
        
        Args:
            pbo_path: Path to PBO file
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        result = subprocess.run(
            ['extractpbo', '-LB', '-P', str(pbo_path)],
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        
        if result.stdout:
            logger.debug(f"Raw PBO listing for {pbo_path.name}:")
            for line in result.stdout.splitlines():
                logger.debug(f"  {line}")
                
        return result.returncode, result.stdout, result.stderr

    def _detect_bin_type(self, file_path: str) -> Optional[str]:
        """Detect the type of a .bin file and return appropriate extension
        
        Args:
            file_path: Path to bin file
            
        Returns:
            New filename with correct extension, or None if unknown
        """
        basename = Path(file_path).name.lower()
        
        if basename in self.BIN_FILE_TYPES:
            return self.BIN_FILE_TYPES[basename]
            
        if basename.endswith('.bin'):
            parts = basename.rsplit('.', 1)[0]
            if '.' in parts:
                return parts
                
        return None

    def extract_files(self, pbo_path: Path, output_dir: Path, file_filter: Optional[str] = None) -> tuple[int, str, str]:
        """Extract files from PBO with bin file handling"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = ['extractpbo', '-S', '-P', '-Y']
        if file_filter:
            cmd.append(f'-F={file_filter}')
        cmd.extend([str(pbo_path), str(output_dir)])
        
        logger.debug(f"Running extractpbo command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        
        if result.returncode == 0:
            self._process_extracted_bins(output_dir)
            
        return result.returncode, result.stdout, result.stderr

    def _process_extracted_bins(self, output_dir: Path) -> None:
        """Process extracted bin files and rename them appropriately"""
        for bin_file in output_dir.rglob('*.bin'):
            try:
                if new_name := self._detect_bin_type(bin_file.name):
                    new_path = bin_file.with_name(new_name)
                    logger.debug(f"Renaming {bin_file.name} to {new_name}")
                    bin_file.replace(new_path)
            except Exception as e:
                logger.warning(f"Failed to process bin file {bin_file}: {e}")

    def extract_prefix(self, stdout: str) -> Optional[str]:
        """Extract the prefix= line from extractpbo output
        
        Args:
            stdout: Output from extractpbo command
            
        Returns:
            Prefix string if found, None otherwise
        """
        for line in stdout.splitlines():
            if line.startswith('prefix='):
                prefix = line.split('=', 1)[1].strip().strip(';')
                return prefix.replace('\\', '/')
            elif line.startswith('PboPrefix'):
                prefix = line.split(':', 1)[1].strip().strip(';')
                return prefix.replace('\\', '/')
        return None

    def _read_file_with_fallback(self, file_path: Path) -> Optional[str]:
        """Try to read file with different encodings
        
        Args:
            file_path: Path to file to read
            
        Returns:
            File contents as string, or None if file cannot be read
            
        The function tries different encodings in this order:
        1. utf-8-sig (UTF-8 with BOM)
        2. utf-8
        3. cp1252 (Windows-1252)
        4. latin1 (ISO-8859-1)
        """
        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin1']
        errors = []
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                return content
            except UnicodeDecodeError as e:
                errors.append(f"{encoding}: {str(e)}")
                continue
                
        error_details = "\n  ".join(errors)
        logger.warning(
            f"Failed to read {file_path} with all encodings:\n"
            f"  {error_details}\n"
            f"File size: {file_path.stat().st_size} bytes"
        )
        return None

    def _normalize_pbo_path(self, path: str, prefix: Optional[str] = None) -> str:
        """Normalize PBO path to consistent format with prefix"""
        clean_path = path.strip().replace('\\', '/').strip('/')
        
        if clean_path in {'$PBOPREFIX$', '$PREFIX$'} or \
           clean_path.startswith(('$', '__', '.')):
            return ''
            
        if ':' in clean_path:
            clean_path = clean_path.split(':')[-1].lstrip('\\/')
        clean_path = '/'.join(p for p in clean_path.split('/') if p and not p.startswith('..'))
            
        if prefix:
            prefix = prefix.replace('\\', '/').strip('/')
            if not clean_path.startswith(prefix):
                while clean_path.startswith(f"{prefix}/{prefix}"):
                    clean_path = clean_path[len(prefix)+1:]
                clean_path = f"{prefix}/{clean_path}"
                
        return clean_path

    def scan_pbo_contents(self, pbo_path: Path) -> tuple[int, Dict[str, str], Set[str]]:
        """Thread-safe scan of PBO contents"""
        operation_id = str(uuid.uuid4())
        code_files: Dict[str, str] = {}
        all_paths: Set[str] = set()
        prefix = None
        
        try:
            returncode, stdout, stderr = self.list_contents(pbo_path)
            if returncode != 0:
                logger.error(f"Failed to list PBO contents: {stderr}")
                return returncode, code_files, all_paths
                
            prefix = self.extract_prefix(stdout)
            logger.debug(f"Found PBO prefix: {prefix}")
            logger.debug(f"Processing PBO: {pbo_path}")
                
            logger.debug("Found files:")
            for line in stdout.splitlines():
                line = line.strip()
                if not line or line.startswith(('Active code page:', 'Opening ', '==')):
                    continue
                    
                if line.startswith(('prefix=', 'Prefix=', '$')):
                    continue

                logger.debug(f"  Raw path: {line}")                
                clean_path = self._normalize_pbo_path(line, prefix)
                if clean_path:
                    all_paths.add(clean_path)
                
            logger.debug(f"\nScan Results for {pbo_path.name}:")
            logger.debug(f"  Prefix: {prefix}")
            logger.debug(f"  Total paths found: {len(all_paths)}")
            logger.debug(f"  Code files found: {len(code_files)}")
            logger.debug("  Asset paths:")
            for path in sorted(all_paths):
                logger.debug(f"    {path}")
                        
            return returncode, code_files, all_paths
        finally:
            self._cleanup_temp_dir(operation_id)
