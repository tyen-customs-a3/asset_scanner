import pytest
from pathlib import Path
from asset_scanner.class_parser.class_parser import ClassParser, ParsingError
from asset_scanner.class_parser.core.config_value import ValueType

@pytest.fixture
def test_config(tmp_path: Path) -> Path:
    """Create a test config file with various class definitions"""
    config_content = """
    class CfgPatches {
        class TestMod {
            units[] = {"Vehicle1"};
            weapons[] = {"Weapon1"};
            requiredVersion = 1.0;
            requiredAddons[] = {"A3_Data_F"};
        };
    };
    
    class CfgVehicles {
        class ParentVehicle {
            scope = 1;
            model = "base.p3d";
        };
        
        class Vehicle1: ParentVehicle {
            scope = 2;
            displayName = "Test Vehicle";
            model = "test.p3d";
            
            class Turret {
                gunnerName = "Gunner";
                weapons[] = {"Weapon1"};
            };
        };
    };
    """
    config_file = tmp_path / "config.cpp"
    config_file.write_text(config_content)
    return config_file

def test_basic_parsing(test_config: Path) -> None:
    """Test basic class parsing functionality"""
    parser = ClassParser()
    parser.parse_file(test_config)
    registry = parser.get_registry()
    
    # Test CfgPatches class
    mod_class = registry.get_class("CfgPatches", "TestMod")
    assert mod_class is not None
    assert mod_class.name == "TestMod"
    assert mod_class.config_group == "CfgPatches"
    assert mod_class.properties["requiredVersion"].value == 1.0
    
    # Test array values
    units = mod_class.properties["units"]
    assert units.type == ValueType.ARRAY
    assert units.value == ["Vehicle1"]

def test_inheritance(test_config: Path) -> None:
    """Test class inheritance resolution"""
    parser = ClassParser()
    parser.parse_file(test_config)
    registry = parser.get_registry()
    
    vehicle = registry.get_class("CfgVehicles", "Vehicle1")
    assert vehicle is not None
    assert vehicle.parent == "ParentVehicle"
    assert vehicle.properties["scope"].value == 2
    assert vehicle.properties["model"].value == "test.p3d"

def test_nested_classes(test_config: Path) -> None:
    """Test nested class handling"""
    parser = ClassParser()
    parser.parse_file(test_config)
    registry = parser.get_registry()
    
    # Test accessing nested class
    turret = registry.get_class("CfgVehicles", "Vehicle1.Turret")
    assert turret is not None
    assert turret.name == "Turret"
    assert turret.parent == "Vehicle1"
    assert turret.properties["gunnerName"].value == "Gunner"

def test_error_handling(tmp_path: Path) -> None:
    """Test error handling for malformed configs"""
    config = tmp_path / "invalid.cpp"
    
    # Test unclosed class
    config.write_text("class Unclosed {")
    parser = ClassParser()
    with pytest.raises(ParsingError):
        parser.parse_file(config)
    
    # Test invalid inheritance
    config.write_text("class Child: NonexistentParent {};")
    parser = ClassParser()
    parser.parse_file(config)  # Should parse but log warning
    
    # Test invalid property
    config.write_text("class Test { invalid; };")
    parser = ClassParser()
    parser.parse_file(config)  # Should skip invalid property
    registry = parser.get_registry()
    test_class = registry.get_class("CfgPatches", "Test")
    assert test_class is not None
    assert len(test_class.properties) == 0

def test_config_groups(tmp_path: Path) -> None:
    """Test config group handling"""
    config = tmp_path / "groups.cpp"
    config.write_text("""
    class CfgVehicles {
        class TestVehicle {};
    };
    class InvalidGroup {
        class Test {};
    };
    """)
    
    parser = ClassParser()
    parser.parse_file(config)
    registry = parser.get_registry()
    
    # Valid group
    vehicle = registry.get_class("CfgVehicles", "TestVehicle")
    assert vehicle is not None
    assert vehicle.config_group == "CfgVehicles"
    
    # Invalid group defaults to CfgPatches
    test = registry.get_class("CfgPatches", "Test")
    assert test is not None

def test_source_tracking(tmp_path: Path) -> None:
    """Test source file and location tracking"""
    config = tmp_path / "source.cpp"
    config.write_text("class Test {};")
    
    parser = ClassParser()
    parser.parse_file(config, Path("test.pbo"), "TestMod")
    registry = parser.get_registry()
    
    test = registry.get_class("CfgPatches", "Test")
    assert test is not None
    assert test.source_file == config
    assert test.source_pbo == Path("test.pbo")
    assert test.source_mod == "TestMod"
    assert test.line_number > 0
