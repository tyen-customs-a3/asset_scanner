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
def em_config() -> str:
    path = Path('sample_data/@em/addons/babe_em/babe/babe_em/config.cpp')
    with open(path) as f:
        return f.read()

def test_em_config_structure(parser: ClassParser, em_config: str) -> None:
    """Test parsing produces correct data structures"""
    result = parser.parse(em_config)
    
    assert isinstance(result, ParsedClassData)
    assert 'CfgPatches' in result.classes
    assert 'CfgModSettings' in result.classes
    assert 'CfgVehicles' in result.classes

def test_em_patches_class(parser: ClassParser, em_config: str) -> None:
    """Test CfgPatches class structure"""
    result = parser.parse(em_config)
    patches = result.classes['CfgPatches']

    babe_em = patches.properties.get('BaBe_EM')
    assert isinstance(babe_em, ClassData)
    
    props = babe_em.properties
    assert props['units'].value == ['babe_helper']
    assert props['weapons'].value == []
    assert props['requiredVersion'].value == 0.1
    assert props['requiredAddons'].value == ['babe_core', 'A3_characters_F']

def test_em_mod_settings(parser: ClassParser, em_config: str) -> None:
    """Test CfgModSettings structure"""
    result = parser.parse(em_config)
    settings = result.classes['CfgModSettings']
    
    babe_em = settings.properties.get('babe_EM')
    assert isinstance(babe_em, ClassData)
    assert babe_em.properties['displayname'].value == 'Enhanced Movement'

    # Test key bindings section
    keys = babe_em.properties['Keys']
    assert isinstance(keys, ClassData)
    for key_action in ['jumpclimb', 'Use', 'Selfint', 'jump', 'climb']:
        assert key_action in keys.properties

def test_em_settings_options(parser: ClassParser, em_config: str) -> None:
    """Test settings options structure"""
    result = parser.parse(em_config)
    settings = result.classes['CfgModSettings']
    
    babe_em = settings.properties['babe_EM']
    settings_section = babe_em.properties['Settings']
    
    # Test stamina settings
    stamina = settings_section.properties['Stamina']
    assert stamina.properties['defaultvalue'].value == 'On'
    assert 'On' in stamina.properties
    assert 'Off' in stamina.properties

    # Test walkonstuff settings
    walkonstuff = settings_section.properties['walkonstuff']
    assert walkonstuff.properties['defaultvalue'].value == 'On'
    assert 'On' in walkonstuff.properties
    assert 'Off' in walkonstuff.properties

def test_em_vehicles_inheritance(parser: ClassParser, em_config: str) -> None:
    """Test CfgVehicles inheritance structure"""
    result = parser.parse(em_config)
    vehicles = result.classes['CfgVehicles']

    helper = vehicles.properties['babe_helper']
    assert isinstance(helper, ClassData)
    assert helper.parent == 'TargetGrenade'
    
    props = helper.properties
    assert props['model'].value == '\\babe\\babe_em\\models\\helper.p3d'
    assert props['armor'].value == 20000
    assert props['scope'].value == 2
    assert props['displayName'].value == 'helper'
    assert props['hiddenSelections'].value == ['camo']

def test_em_inheritance_map(parser: ClassParser, em_config: str) -> None:
    """Test complete inheritance relationships"""
    result = parser.parse(em_config)
    
    expected_inheritance = {
        'Static': 'All',
        'Building': 'Static',
        'NonStrategic': 'Building',
        'TargetTraining': 'NonStrategic',
        'TargetGrenade': 'TargetTraining',
        'babe_helper': 'TargetGrenade'
    }

    assert all(child in result.inheritance for child in expected_inheritance)
    assert all(result.inheritance[child] == parent 
               for child, parent in expected_inheritance.items())
