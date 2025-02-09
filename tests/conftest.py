import pytest
import logging
from pathlib import Path
from unittest.mock import Mock
from typing import Dict, Set, Tuple, Any, List, TypedDict

class PboFileData(TypedDict):
    path: Path
    prefix: str
    source: str
    expected: Set[str]

# Test Data Constants
SAMPLE_DATA_ROOT = Path(__file__).parent.parent / "sample_data"
PBO_FILES: Dict[str, PboFileData] = {
    'mirror': {
        'path': SAMPLE_DATA_ROOT / '@tc_mirrorform/addons/mirrorform.pbo',
        'prefix': 'tc/mirrorform',
        'source': 'tc_mirrorform',
        'expected': {
            "config.bin",
            "texHeaders.bin",
            "logo.paa",
            "logo_small.paa",
            "uniform/mirror.p3d",
            "uniform/black.paa",
            "uniform/mirror.rvmat",
        }
    },
    'headband': {
        'path': SAMPLE_DATA_ROOT / '@tc_rhs_headband/addons/rhs_headband.pbo',
        'prefix': 'tc/rhs_headband',
        'source': 'tc_rhs_headband',
        'expected': {
            "config.bin",
            "texHeaders.bin",
            "data/tex/headband_choccymilk_co.paa",
            "logo.paa",
            "logo_small.paa"
        }
    },
    'em_babe': {
        'path': SAMPLE_DATA_ROOT / '@em/addons/babe_em.pbo',
        'prefix': 'babe/babe_em',
        'source': 'em',
        'expected': {
            'c_anm_EM/config.bin',
            'c_gst/config.bin',
            'c_ui/config.bin',
            'config.bin',
            'func/config.bin',
            'texHeaders.bin',
            'models/helper.p3d',
            'data/nope_ca.paa',
            'textures/EM_ca.paa',
            'textures/ui/fatigue_ca.paa',
            'animations/climbOnHer_pst.rtm',
            'animations/climbOnHer_rfl.rtm',
            'animations/climbOnHer_ua.rtm',
            'animations/climbOnH_pst.rtm',
            'animations/climbOnH_rfl.rtm',
            'animations/climbOnH_ua.rtm',
            'animations/climbOn_pst.rtm',
            'animations/climbOn_rfl.rtm',
            'animations/climbOn_ua.rtm',
            'animations/climbOverHer_pst.rtm',
            'animations/climbOverHer_rfl.rtm',
            'animations/climbOverHer_ua.rtm',
            'animations/climbOverH_pst.rtm',
            'animations/climbOverH_rfl.rtm',
            'animations/climbOverH_ua.rtm',
            'animations/climbOver_pst.rtm',
            'animations/climbOver_rfl.rtm',
            'animations/climbOver_ua.rtm',
            'animations/drop_pst.rtm',
            'animations/drop_rfl.rtm',
            'animations/drop_ua.rtm',
            'animations/jump_pst.rtm',
            'animations/jump_rfl.rtm',
            'animations/jump_ua.rtm',
            'animations/pull.rtm',
            'animations/push.rtm',
            'animations/stepOn_pst.rtm',
            'animations/stepOn_rfl.rtm',
            'animations/stepOn_ua.rtm',
            'animations/vaultover_pst.rtm',
            'animations/vaultover_rfl.rtm',
            'animations/vaultover_ua.rtm',
            'func/EH/fn_AnimDone.sqf',
            'func/EH/fn_handledamage_nofd.sqf',
            'func/core/fn_init.sqf',
            'func/mov/fn_detect.sqf',
            'func/mov/fn_detect_cl_only.sqf',
            'func/mov/fn_em.sqf',
            'func/mov/fn_exec_drop.sqf',
            'func/mov/fn_exec_em.sqf',
            'func/mov/fn_finish_drop.sqf',
            'func/mov/fn_finish_em.sqf',
            'func/mov/fn_jump.sqf',
            'func/mov/fn_jump_only.sqf',
            'func/mov/fn_walkonstuff.sqf',
        }
    }
}

# Fix PBO name mappings
PBO_NAME_MAP = {
    'babe_em.pbo': 'em_babe',
    'mirrorform.pbo': 'mirror',
    'rhs_headband.pbo': 'headband'
}

# Update compatibility mappings
PBO_PATHS = {k: PBO_FILES[PBO_NAME_MAP[k]]['path'] for k in PBO_NAME_MAP}
EXPECTED_PATHS = {k: PBO_FILES[PBO_NAME_MAP[k]]['expected'] for k in PBO_NAME_MAP}
SOURCE_MAPPING = {k: PBO_FILES[PBO_NAME_MAP[k]]['source'] for k in PBO_NAME_MAP}

# Individual PBO files for backward compatibility
MIRRORFORM_PBO_FILE = PBO_FILES['mirror']['path']
BABE_EM_PBO_FILE = PBO_FILES['em_babe']['path']
HEADBAND_PBO_FILE = PBO_FILES['headband']['path']

# Expected content sets for backward compatibility
MIRROR_EXPECTED = PBO_FILES['mirror']['expected']
EM_BABE_EXPECTED = PBO_FILES['em_babe']['expected']
HEADBAND_EXPECTED = PBO_FILES['headband']['expected']

# Basic Test Configuration
@pytest.fixture(autouse=True)
def setup_logging() -> None:
    """Configure logging for tests"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler('test_debug.log')]
    )

# Sample Data Fixtures
@pytest.fixture
def sample_pbos() -> Dict[str, Tuple[Path, Set[str]]]:
    """Collection of sample PBO files with expected contents"""
    return {
        str(name): (Path(data['path']), data['expected'])
        for name, data in PBO_FILES.items()
    }

@pytest.fixture
def test_structure(tmp_path: Path) -> Path:
    """Create a test directory structure for all test types"""
    mod_dir = tmp_path / "@test_mod"
    mod_dir.mkdir()
    addons_dir = mod_dir / "addons"
    addons_dir.mkdir()

    # Create test files
    test_files = {
        "addons/config.pbo": "dummy",
        "addons/data1.pbo": "dummy",
        "addons/data2.pbo": "dummy",
        "logo.paa": "dummy"
    }
    
    for path, content in test_files.items():
        full_path = mod_dir / path
        full_path.parent.mkdir(exist_ok=True)
        full_path.write_text(content)

    # Create performance test structure
    for i in range(100):
        perf_dir = tmp_path / f"@mod_{i}"
        perf_dir.mkdir()
        for j in range(10):
            (perf_dir / f"file_{j}.p3d").write_text("test")

    return tmp_path

@pytest.fixture
def mirror_addon_path(tmp_path: Path) -> Path:
    """Create mirror addon structure"""
    addon_path = tmp_path / "@tc_mirrorform"
    addon_path.mkdir(parents=True, exist_ok=True)
    addons_dir = addon_path / "addons"
    addons_dir.mkdir(exist_ok=True)
    
    for path_str in PBO_FILES['mirror']['expected']:
        full_path = addons_dir / str(PBO_FILES['mirror']['prefix']) / str(path_str)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(b"test data")
    
    return addon_path

@pytest.fixture
def sample_data_path(tmp_path: Path) -> Path:
    """Create complete sample data structure"""
    sample_path = tmp_path / "sample_data"
    sample_path.mkdir(exist_ok=True)
    
    for name, data in PBO_FILES.items():
        # Create addon structure
        addon_name = f"@{data['source']}"  # Fix: use source instead of prefix split
        addon_path = sample_path / addon_name
        addon_path.mkdir(parents=True, exist_ok=True)
        addons_dir = addon_path / "addons"
        addons_dir.mkdir(exist_ok=True)
        
        # Create sample files
        for filepath in data['expected']:
            full_path = addons_dir / str(data['prefix']) / str(filepath)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(b"test data")
            
    return sample_path

# Mock Fixtures
@pytest.fixture
def mock_extractor() -> Mock:
    """Mock PBO extractor with proper test responses"""
    extractor = Mock()
    
    def mock_list_contents(path: Path) -> Tuple[int, str, str]:
        """Mock list_contents with valid results"""
        # Return consistent response regardless of path
        return (
            0,  # Return code
            "prefix=test_prefix\nconfig.cpp\nmodel.p3d\ntexture.paa",  # stdout
            ""  # stderr
        )
    
    def mock_scan_contents(path: Path) -> Tuple[int, Dict[str, str], Set[str]]:
        """Mock scan_pbo_contents with valid results"""
        # Return consistent response regardless of path
        return (
            0,  # Return code
            {"config.cpp": "class TestClass { weapon = 'rifle'; };"},  # Code files
            {"config.cpp", "model.p3d", "texture.paa"}  # All paths
        )
    
    # Set up mock methods
    extractor.list_contents.side_effect = mock_list_contents
    extractor.scan_pbo_contents.side_effect = mock_scan_contents
    extractor.extract_prefix.return_value = "test_prefix"
    
    return extractor

@pytest.fixture
def mock_class_parser() -> Mock:
    """Mock class parser with appropriate class data"""
    parser = Mock()
    
    def mock_parse_code(code: str) -> Tuple[List[str], Dict[str, Any], Dict[str, Dict[str, str]]]:
        """Mock code parsing with valid class data"""
        return (
            ["TestClass"],  # classes
            {"TestClass": None},  # inheritance
            {"TestClass": {"weapon": "rifle"}}  # properties
        )
    
    parser.parse_code.side_effect = mock_parse_code
    return parser