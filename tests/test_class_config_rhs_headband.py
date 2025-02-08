import logging
import pytest
from pathlib import Path
from asset_scanner.class_models import (
    ValueType, ClassData, ParsedClassData, ConfigValue
)
from asset_scanner.parser.class_parser import ClassParser

logger = logging.getLogger(__name__)

@pytest.fixture
def parser() -> ClassParser:
    return ClassParser()

@pytest.fixture
def headband_config() -> str:
    path = Path('sample_data/@tc_rhs_headband/addons/rhs_headband/tc/rhs_headband/config.cpp')
    with open(path) as f:
        return f.read()

def test_headband_config_structure(parser: ClassParser, headband_config: str) -> None:
    """Test parsing produces correct data structures"""
    result = parser.parse(headband_config)
    
    assert isinstance(result, ParsedClassData)
    assert 'CfgPatches' in result.classes
    assert 'CfgWeapons' in result.classes

def test_headband_patches_class(parser: ClassParser, headband_config: str) -> None:
    """Test CfgPatches class structure"""
    result = parser.parse(headband_config)
    patches = result.classes['CfgPatches']

    tc_headband = patches.properties.get('tc_rhs_headband')
    assert isinstance(tc_headband, ClassData)
    
    props = tc_headband.properties
    assert props['author'].value == 'PCA'
    assert props['requiredVersion'].value == 1.6
    assert props['requiredAddons'].value == ['A3_Characters_F', 'A3_Weapons_F_Exp', 'rhs_main', 'rhs_c_troops']
    assert props['units'].value == []
    assert props['weapons'].value == []

def test_headband_weapons_inheritance(parser: ClassParser, headband_config: str) -> None:
    """Test CfgWeapons inheritance structure"""
    result = parser.parse(headband_config)
    weapons = result.classes['CfgWeapons']

    # Test base class references
    assert 'ItemCore' in weapons.properties
    assert 'H_HelmetB' in weapons.properties
    assert 'rhs_headband' in weapons.properties

    # Test custom headband
    tc_headband = weapons.properties['tc_rhs_headband']
    assert isinstance(tc_headband, ClassData)
    assert tc_headband.parent == 'rhs_headband'
    
    props = tc_headband.properties
    assert props['displayName'].value == 'Headband (I <3 Choccy Milk)'
    assert props['hiddenSelectionsTextures'].value == ['tc\\rhs_headband\\data\\tex\\headband_choccymilk_co.paa']

def test_headband_inheritance_map(parser: ClassParser, headband_config: str) -> None:
    """Test complete inheritance relationships"""
    result = parser.parse(headband_config)
    
    expected_inheritance = {
        'H_HelmetB': 'ItemCore',
        'tc_rhs_headband': 'rhs_headband'
    }

    assert all(child in result.inheritance for child in expected_inheritance)
    assert all(result.inheritance[child] == parent 
               for child, parent in expected_inheritance.items())
