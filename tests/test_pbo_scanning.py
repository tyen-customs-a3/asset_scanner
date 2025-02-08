from pathlib import Path
import pytest
from asset_scanner import AssetAPI
from tests.conftest import BABE_EM_PBO_FILE, EM_BABE_EXPECTED, HEADBAND_EXPECTED, HEADBAND_PBO_FILE, MIRROR_EXPECTED, MIRRORFORM_PBO_FILE, PBO_FILES


@pytest.fixture
def sample_pbos() -> dict:
    """Collection of sample PBO files"""
    return {
        'mirror': (MIRRORFORM_PBO_FILE, MIRROR_EXPECTED),
        'headband': (HEADBAND_PBO_FILE, HEADBAND_EXPECTED),
        'em_babe': (BABE_EM_PBO_FILE, EM_BABE_EXPECTED)
    }


def test_pbo_class_extraction(sample_pbos : dict, tmp_path : Path) -> None:
    """Test extraction of class definitions from PBOs"""
    api = AssetAPI(tmp_path / "cache")
    
    for name, (pbo_path, _) in sample_pbos.items():
        if not pbo_path.exists():
            continue
            
        result, classes = api.scan_pbo_with_classes(pbo_path)
        assert result is not None
        assert len(result.assets) > 0
        
        if classes:
            hierarchy = classes.build_hierarchy()
            assert not hierarchy.invalid_classes
            
            for class_name, info in hierarchy.classes.items():
                assert info.name == class_name
                assert info.source == result.source
                assert info.file_path is not None
