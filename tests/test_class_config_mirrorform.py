import logging
import pytest
from pathlib import Path
from asset_scanner.class_models import (
    ValueType, ClassData, ParsedClassData, ConfigValue,
)
from asset_scanner.parser.class_parser import ClassParser


logger = logging.getLogger(__name__)

@pytest.fixture
def parser() -> ClassParser:
    return ClassParser()


@pytest.fixture
def mirror_config() -> str:
    path = Path('sample_data/@tc_mirrorform/addons/mirrorform/tc/mirrorform/config.cpp')
    with open(path) as f:
        return f.read()


def test_mirror_config_structure(parser: ClassParser, mirror_config: str) -> None:
    """Test parsing produces correct data structures"""
    result = parser.parse(mirror_config)

    assert isinstance(result, ParsedClassData)
    assert all(isinstance(cls, ClassData) for cls in result.classes.values())


def test_mirror_patches_class(parser: ClassParser, mirror_config: str) -> None:
    """Test CfgPatches class structure"""
    result = parser.parse(mirror_config)
    patches = result.classes['CfgPatches']

    tc_mirror = patches.properties.get('TC_MIRROR')
    assert isinstance(tc_mirror, ClassData)
    assert tc_mirror.parent is None

    props = tc_mirror.properties
    
    logger.debug(props)
    
    assert isinstance(props['units'], ConfigValue)
    assert props['units'].type == ValueType.ARRAY
    assert props['units'].value == ['TC_B_Mirror_1']
    assert props['weapons'].value == ['TC_U_Mirror_1']
    assert props['requiredVersion'].type == ValueType.NUMBER
    assert props['requiredVersion'].value == 0.1
    assert props['requiredAddons'].value == ['A3_Characters_F']


def test_mirror_weapons_inheritance(parser: ClassParser, mirror_config: str) -> None:
    """Test CfgWeapons inheritance structure"""
    result = parser.parse(mirror_config)
    weapons = result.classes['CfgWeapons']

    base = weapons.properties['TC_U_Mirror_Base']
    assert isinstance(base, ClassData)
    assert base.parent == 'Uniform_Base'

    base_props = base.properties
    assert base_props['author'].value == 'Tyen'
    assert base_props['scope'].value == 0
    assert base_props['displayName'].value == 'Mirrorform'
    assert base_props['model'].value == '\\tc\\mirrorform\\uniform\\mirror.p3d'

    item_info = base_props['ItemInfo']
    assert isinstance(item_info, ClassData)
    assert item_info.parent == 'UniformItem'
    assert item_info.properties['uniformClass'].value == 'TC_B_Mirror_Base'
    assert item_info.properties['uniformModel'].value == '-'
    assert item_info.properties['containerClass'].value == 'Supply40'
    assert item_info.properties['mass'].value == 40

    derived = weapons.properties['TC_U_Mirror_1']
    assert isinstance(derived, ClassData)
    assert derived.parent == 'TC_U_Mirror_Base'
    assert derived.properties['scope'].value == 2
    assert derived.properties['displayName'].value == 'Mirrorform'

    derived_item_info = derived.properties['ItemInfo']
    assert isinstance(derived_item_info, ClassData)
    assert derived_item_info.parent == 'UniformItem'
    assert derived_item_info.properties['uniformClass'].value == 'TC_B_Mirror_1'
    assert derived_item_info.properties['uniformModel'].value == '-'
    assert derived_item_info.properties['containerClass'].value == 'Supply40'
    assert derived_item_info.properties['mass'].value == 40


def test_mirror_vehicles_inheritance(parser: ClassParser, mirror_config: str) -> None:
    """Test CfgVehicles inheritance structure"""
    result = parser.parse(mirror_config)
    vehicles = result.classes['CfgVehicles']

    base = vehicles.properties['TC_B_Mirror_Base']
    assert isinstance(base, ClassData)
    assert base.parent == 'B_Soldier_base_F'
    assert base.properties['author'].value == 'Tyen'
    assert base.properties['scope'].value == 0
    assert base.properties['displayName'].value == 'Mirrorform'
    assert base.properties['model'].value == '\\tc\\mirrorform\\uniform\\mirror.p3d'
    assert base.properties['uniformClass'].value == 'TC_U_Mirror_Base'

    derived = vehicles.properties['TC_B_Mirror_1']
    assert isinstance(derived, ClassData)
    assert derived.parent == 'TC_B_Mirror_Base'
    assert derived.properties['scope'].value == 2
    assert derived.properties['displayName'].value == 'Mirrorform'
    assert derived.properties['uniformClass'].value == 'TC_U_Mirror_1'
    assert derived.properties['hiddenSelections'].type == ValueType.ARRAY
    assert derived.properties['hiddenSelections'].value == ['hs_shirt']
    assert derived.properties['hiddenSelectionsTextures'].type == ValueType.ARRAY
    assert derived.properties['hiddenSelectionsTextures'].value == ['\\tc\\mirrorform\\uniform\\black.paa']


def test_mirror_inheritance_map(parser: ClassParser, mirror_config: str) -> None:
    """Test complete inheritance relationships"""
    result = parser.parse(mirror_config)

    logger.debug("Full inheritance map:")
    for child, parent in result.inheritance.items():
        logger.debug(f"  {child} inherits from {parent}")

    expected_inheritance = {
        'TC_U_Mirror_Base': 'Uniform_Base',
        'TC_U_Mirror_1': 'TC_U_Mirror_Base',
        'TC_B_Mirror_Base': 'B_Soldier_base_F', 
        'TC_B_Mirror_1': 'TC_B_Mirror_Base'
    }

    logger.debug("Expected inheritance:")
    for child, parent in expected_inheritance.items():
        logger.debug(f"  {child} inherits from {parent}")
        logger.debug(f"  Actual parent: {result.inheritance.get(child)}")

    assert all(child in result.inheritance for child in expected_inheritance)
    assert all(result.inheritance[child] == parent 
               for child, parent in expected_inheritance.items())
