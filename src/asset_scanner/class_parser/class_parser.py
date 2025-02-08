import logging
from pathlib import Path
from typing import Optional

from asset_scanner.class_parser.parsing.patterns import CLASS_PATTERN
from asset_scanner.class_parser.parsing.raw_class import RawBlock, RawClass

from .core.config_class import ConfigClass 
from .hierarchy.class_registry import ClassRegistry
from .hierarchy.hierarchy_builder import HierarchyBuilder
from .parsing.block_scanner import BlockScanner
from .parsing.property_parser import PropertyParser
from .parsing.text_preprocessor import ConfigPreprocessor
from .errors import ParsingError

logger = logging.getLogger(__name__)

class ClassParser:
    def __init__(self) -> None:
        self.preprocessor = ConfigPreprocessor()
        self.block_scanner = BlockScanner()
        self.property_parser = PropertyParser()
        self.hierarchy_builder = HierarchyBuilder()
        self.registry = ClassRegistry()

    def parse(self, content: str, file_path: Optional[Path] = None) -> ClassRegistry:
        """Parse config content into class registry"""
        try:
            # Preprocess content
            clean_content = self.preprocessor.preprocess(content)
            if not clean_content:
                logger.warning("Empty content after preprocessing")
                return ClassRegistry()

            # Extract blocks
            blocks = self.block_scanner.scan_content(clean_content)
            if not blocks:
                logger.warning("No class blocks found")
                
            # Convert to raw classes
            raw_classes = []
            for block in blocks:
                raw_class = self._convert_to_raw_class(block, file_path or Path())
                if raw_class:
                    raw_classes.append(raw_class)

            # Build hierarchy
            self.registry = self.hierarchy_builder.build_hierarchy(raw_classes)
            return self.registry

        except Exception as e:
            logger.error(f"Failed to parse content: {str(e)}")
            raise ParsingError(f"Failed to parse content: {str(e)}")

    def parse_file(self, file_path: Path, pbo_path: Optional[Path] = None, 
                   mod_name: Optional[str] = None) -> None:
        """Parse config file with error handling"""
        try:
            logger.debug(f"Parsing file: {file_path}")
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            logger.debug(f"Retrying with latin1 encoding: {file_path}")
            content = file_path.read_text(encoding='latin1')
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {str(e)}")
            raise ParsingError(f"Failed to read file {file_path}: {str(e)}")

        try:
            self.registry = self.parse(content, file_path)
            self._update_metadata(pbo_path, mod_name)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {str(e)}")
            raise ParsingError(f"Failed to parse {file_path}: {str(e)}")

    def get_registry(self) -> ClassRegistry:
        return self.registry

    def _convert_blocks_to_classes(self, blocks: list[RawBlock], source_file: Path) -> list[RawClass]:
        """Convert raw blocks to classes"""
        raw_classes = []
        for block in blocks:
            raw_class = self._convert_to_raw_class(block, source_file)
            if raw_class:
                raw_classes.append(raw_class)
        return raw_classes

    def _convert_to_raw_class(self, block: RawBlock, source_file: Path) -> Optional[RawClass]:
        """Convert block to raw class"""
        match = CLASS_PATTERN.match(block.header)
        if not match:
            return None
            
        return RawClass(
            name=match.group(1),
            parent=match.group(2),
            properties=self.property_parser.parse_properties(block.body),
            source_file=source_file,
            line_number=block.line_number
        )

    def _update_metadata(self, pbo_path: Optional[Path], mod_name: Optional[str]) -> None:
        """Update PBO and mod metadata"""
        for cls in self.registry.classes.values():
            if pbo_path:
                object.__setattr__(cls, 'source_pbo', pbo_path)
            if mod_name:
                object.__setattr__(cls, 'source_mod', mod_name)
