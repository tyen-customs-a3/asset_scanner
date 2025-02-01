import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set, List
import shutil
import tempfile

logger = logging.getLogger(__name__)

class PboExtractor:
    """Helper class for PBO file operations using extractpbo tool"""
    
    # Add CODE_EXTENSIONS to class attributes
    CODE_EXTENSIONS = {'.cpp', '.hpp', '.sqf'}
    # Add mapping for known bin file types
    BIN_FILE_TYPES = {
        'config.bin': 'config.cpp',
        'model.bin': 'model.cfg',
        'stringtable.bin': 'stringtable.xml',
        'texHeaders.bin': 'texHeaders.h'
    }
    
    def __init__(self, timeout: int = 30):
        """Initialize PBO extractor with timeout
        
        Args:
            timeout: Maximum time in seconds to wait for extractpbo operations
        """
        self.timeout = timeout
        self._temp_dir = None

    def __del__(self):
        """Cleanup temporary resources"""
        self.cleanup()

    def cleanup(self):
        """Remove temporary directory if it exists"""
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def _get_temp_dir(self) -> Path:
        """Get or create temporary directory"""
        if not self._temp_dir:
            self._temp_dir = Path(tempfile.mkdtemp(prefix='pbo_extractor_'))
        return self._temp_dir

    def list_contents(self, pbo_path: Path) -> tuple[int, str, str]:
        """List contents of PBO file
        
        Args:
            pbo_path: Path to PBO file
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        # Use -LB for brief directory style output, -P to prevent pausing
        result = subprocess.run(
            ['extractpbo', '-LB', '-P', str(pbo_path)],
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        
        # Log the raw output for debugging
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
        
        # Check known bin types
        if basename in self.BIN_FILE_TYPES:
            return self.BIN_FILE_TYPES[basename]
            
        # Handle other bin files based on content or path
        if basename.endswith('.bin'):
            parts = basename.rsplit('.', 1)[0]
            if '.' in parts:  # Has another extension before .bin
                return parts  # Remove .bin extension
                
        return None

    def extract_files(self, pbo_path: Path, output_dir: Path, file_filter: Optional[str] = None) -> tuple[int, str, str]:
        """Extract files from PBO with bin file handling"""
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = ['extractpbo', '-S', '-P', '-Y']
        if file_filter:
            # Fix: -F requires equals sign syntax
            cmd.append(f'-F={file_filter}')
        cmd.extend([str(pbo_path), str(output_dir)])
        
        logger.debug(f"Running extractpbo command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        
        # Handle bin file renaming after extraction
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
                    # Use replace() to handle existing files
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
            # Match prefix line, both with and without semicolon
            if line.startswith('prefix='):
                # Extract prefix and normalize
                prefix = line.split('=', 1)[1].strip().strip(';')
                return prefix.replace('\\', '/')
            # Also check for PBO prefix format in list output
            elif line.startswith('PboPrefix'):
                prefix = line.split(':', 1)[1].strip().strip(';')
                return prefix.replace('\\', '/')
        return None

    def extract_code_files(self, pbo_path: Path, extensions: Set[str]) -> Dict[str, str]:
        """Extract and read code files from PBO"""
        try:
            # Add .bin to extensions we're looking for
            search_extensions = extensions | {'.bin'}
            logger.info(f"Extracting code files from {pbo_path}")
            logger.debug(f"Looking for extensions: {', '.join(search_extensions)}")
            
            temp_dir = self._get_temp_dir() / pbo_path.stem
            temp_dir.mkdir(parents=True, exist_ok=True)

            # First check if PBO contains any matching files
            returncode, stdout, stderr = self.list_contents(pbo_path)
            if returncode != 0:
                logger.error(f"Failed to list PBO contents: {pbo_path}")
                if stderr:
                    logger.error(f"ExtractPBO error: {stderr}")
                return {}

            # Check for matching files
            matching_files = [
                line.strip() for line in stdout.splitlines()
                if any(line.strip().endswith(ext) for ext in search_extensions)
            ]
            
            if not matching_files:
                logger.info("No matching files found in PBO")
                return {}

            logger.info(f"Found {len(matching_files)} matching files:")
            for file in matching_files:
                logger.debug(f"  {file}")

            # Extract only matching files using correct filter format
            file_filter = ','.join(f'*{ext}' for ext in search_extensions)
            returncode, stdout, stderr = self.extract_files(pbo_path, temp_dir, file_filter)
            if returncode != 0:
                logger.error(f"Failed to extract files from PBO: {pbo_path}")
                if stderr:
                    logger.error(f"ExtractPBO error: {stderr}")
                return {}

            # Read extracted files (bin files will have been renamed by extract_files)
            code_files = {}
            for ext in extensions:
                for file_path in temp_dir.rglob(f'*{ext}'):
                    try:
                        relative_path = file_path.relative_to(temp_dir)
                        code_files[str(relative_path)] = file_path.read_text(encoding='utf-8-sig')
                        logger.info(f"Successfully read {relative_path}")
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {e}")

            # Also check for converted bin files that match our target extensions
            for bin_type in self.BIN_FILE_TYPES.values():
                if any(bin_type.endswith(ext) for ext in extensions):
                    for file_path in temp_dir.rglob(bin_type):
                        try:
                            relative_path = file_path.relative_to(temp_dir)
                            code_files[str(relative_path)] = file_path.read_text(encoding='utf-8-sig')
                            logger.info(f"Successfully read converted bin file {relative_path}")
                        except Exception as e:
                            logger.warning(f"Failed to read converted bin file {file_path}: {e}")

            logger.info(f"Successfully extracted {len(code_files)} code files")
            return code_files

        except Exception as e:
            logger.error(f"Error extracting code files from {pbo_path}: {e}")
            return {}

    def _normalize_pbo_path(self, path: str, prefix: Optional[str] = None) -> str:
        """Normalize PBO path to consistent format with prefix"""
        # Clean up path separators
        clean_path = path.strip().replace('\\', '/').strip('/')
        
        # Skip special files
        if clean_path in {'$PBOPREFIX$', '$PREFIX$'} or \
           clean_path.startswith(('$', '__', '.')):
            return ''
            
        # Remove any absolute path components
        if ':' in clean_path:  # Windows path
            clean_path = clean_path.split(':')[-1].lstrip('\\/')
        clean_path = '/'.join(p for p in clean_path.split('/') if p and not p.startswith('..'))
            
        # Add prefix if provided and path doesn't already start with it
        if prefix:
            prefix = prefix.replace('\\', '/').strip('/')
            # Check if path already has prefix to avoid duplication
            if not clean_path.startswith(prefix):
                # Remove any duplicate prefixes that might exist
                while clean_path.startswith(f"{prefix}/{prefix}"):
                    clean_path = clean_path[len(prefix)+1:]
                clean_path = f"{prefix}/{clean_path}"
                
        return clean_path

    def scan_pbo_contents(self, pbo_path: Path) -> tuple[int, Dict[str, str], Set[str]]:
        """Scan PBO contents and extract code files in one operation"""
        code_files = {}
        all_paths = set()
        prefix = None
        
        # First list contents
        returncode, stdout, stderr = self.list_contents(pbo_path)
        if returncode != 0:
            logger.error(f"Failed to list PBO contents: {stderr}")
            return returncode, code_files, all_paths
            
        # Extract prefix first
        prefix = self.extract_prefix(stdout)
        logger.debug(f"Found PBO prefix: {prefix}")
        logger.debug(f"Processing PBO: {pbo_path}")
            
        # Process file listings
        logger.debug("Found files:")
        for line in stdout.splitlines():
            line = line.strip()
            # Ignore headers and empty lines
            if not line or line.startswith(('Active code page:', 'Opening ', '==')):
                continue
                
            # Skip prefix line
            if line.startswith(('prefix=', 'Prefix=', '$')):
                continue

            logger.debug(f"  Raw path: {line}")                
            # Normalize path with prefix
            clean_path = self._normalize_pbo_path(line, prefix)
            if clean_path:
                all_paths.add(clean_path)
                logger.debug(f"  -> Normalized: {clean_path}")
            else:
                logger.debug("  -> Skipped (invalid path)")
            
            # Extract code files if needed
            if any(line.endswith(ext) for ext in self.CODE_EXTENSIONS) or line.endswith('.bin'):
                if not code_files:  # Only extract if we find code files
                    code_files = self.extract_code_files(pbo_path, self.CODE_EXTENSIONS)

        # Log summary
        logger.debug(f"\nScan Results for {pbo_path.name}:")
        logger.debug(f"  Prefix: {prefix}")
        logger.debug(f"  Total paths found: {len(all_paths)}")
        logger.debug(f"  Code files found: {len(code_files)}")
        logger.debug("  Asset paths:")
        for path in sorted(all_paths):
            logger.debug(f"    {path}")
                    
        return returncode, code_files, all_paths
