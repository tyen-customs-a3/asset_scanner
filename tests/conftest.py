from asset_scanner import AssetScanner, Asset, ScanResult
import pytest
from pathlib import Path
import logging

@pytest.fixture(autouse=True)
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_debug.log')
        ]
    )

@pytest.fixture
def sample_data_path(tmp_path) -> Path:
    """Create sample data structure for testing"""
    sample_path = tmp_path / "sample_data"
    sample_path.mkdir()
    
    # Create mock addon paths
    em_path = sample_path / "@em"
    mirror_path = sample_path / "@tc_mirrorform"
    headband_path = sample_path / "@tc_rhs_headband"
    
    # Create addon structures with PBO-like content
    _create_em_addon(em_path)
    _create_mirror_addon(mirror_path)
    _create_headband_addon(headband_path)
    
    return sample_path

@pytest.fixture
def mirror_addon_path(sample_data_path) -> Path:
    """Get mirror addon path"""
    return sample_data_path / "@tc_mirrorform"

@pytest.fixture
def headband_addon_path(sample_data_path) -> Path:
    """Get headband addon path"""
    return sample_data_path / "@tc_rhs_headband"

@pytest.fixture
def em_addon_path(sample_data_path) -> Path:
    """Get EM addon path"""
    return sample_data_path / "@em"

def _create_em_addon(path: Path) -> None:
    """Create EM addon structure"""
    path.mkdir(parents=True)
    addons = path / "addons"
    addons.mkdir()
    
    files = {
        "babe/babe_em/models/helper.p3d": b"model data",
        "babe/babe_em/data/nope_ca.paa": b"texture data",
        "babe/babe_em/textures/EM_ca.paa": b"texture data",
        "babe/babe_em/textures/ui/fatigue_ca.paa": b"texture data",
        "babe/babe_em/func/mov/fn_jump_only.sqf": b"script data"
    }
    
    for file_path, content in files.items():
        full_path = addons / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

def _create_mirror_addon(path: Path) -> None:
    """Create mirror addon structure"""
    path.mkdir(parents=True)
    addons = path / "addons"
    addons.mkdir()
    
    files = {
        "tc/mirrorform/logo.paa": b"logo data",
        "tc/mirrorform/logo_small.paa": b"small logo data",
        "tc/mirrorform/uniform/mirror.p3d": b"model data",
        "tc/mirrorform/uniform/black.paa": b"texture data"
    }
    
    for file_path, content in files.items():
        full_path = addons / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

def _create_headband_addon(path: Path) -> None:
    """Create headband addon structure"""
    path.mkdir(parents=True)
    addons = path / "addons"
    addons.mkdir()
    
    files = {
        "tc/rhs_headband/data/tex/headband_choccymilk_co.paa": b"texture data",
        "tc/rhs_headband/logo.paa": b"logo data",
        "tc/rhs_headband/logo_small.paa": b"small logo data"
    }
    
    for file_path, content in files.items():
        full_path = addons / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)