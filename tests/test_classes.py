import pytest
from pathlib import Path
from asset_scanner import Asset, AssetAPI, APIConfig
from datetime import datetime

@pytest.fixture
def api(tmp_path):
    """Create API instance for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return AssetAPI(cache_dir)

@pytest.fixture
def complex_class_code():
    """Create complex test cases for class searches"""
    # The previous test output shows truncated test data
    # We need to ensure the full class definition is included
    return """
    class ObjectBase {
        scope = 0;
        model = "";
    };

    class ItemBase: ObjectBase {
        scope = 2;
        class ItemInfo {
            type = 0;
        };
    };

    class WeaponBase: ItemBase {
        scope = 1;
        class WeaponSlotsInfo {
            mass = 100;
            class MuzzleSlot {
                linkProxy = "muzzle";
            };
        };
    };

    class Magazine: ItemBase {
        type = "Magazine";
        count = 30;
        mass = 10;
    };

    // Circular inheritance test
    class CircularA: CircularB {};
    class CircularB: CircularC {};
    class CircularC: CircularA {};

    // Multiple parent references
    class BaseVehicle {
        crew = "Soldier";
    };

    class BaseTank: BaseVehicle {
        armor = 1000;
    };

    class ModernTank: BaseTank {
        crew = "Modern_Crew";  // Override base property
        thermals = 1;
    };

    // Enum with values
    enum DamageType {
        KINETIC = 1,
        EXPLOSIVE = 2,
        THERMAL = 3
    };

    // Class with array properties
    class AmmoBox {
        magazines[] = {
            "Mag1",
            "Mag2"
        };
        weapons[] = {"Gun1"};
    };
    """

def test_property_inheritance(api, complex_class_code):
    """Test complex property inheritance scenarios"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    # Test basic inheritance
    weapon = hierarchy.classes["WeaponBase"]
    assert weapon.get_all_properties()["scope"] == "1"  # Local override
    assert weapon.get_all_properties()["model"] == ""  # Inherited from ObjectBase

    # Test nested class inheritance - use direct properties
    assert "WeaponSlotsInfo" in weapon.properties
    weapon_slots = weapon.properties["WeaponSlotsInfo"]
    assert isinstance(weapon_slots, dict)  # Make sure it's a dictionary
    assert "mass" in weapon_slots  # Local property
    assert weapon_slots["mass"] == "100"  # Verify exact value

def test_find_classes_with_property(api, complex_class_code):
    """Test finding classes with specific properties"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    # Test direct properties
    mass_classes = hierarchy.find_classes_with_property("mass")
    assert "Magazine" in mass_classes
    assert "WeaponSlotsInfo" not in mass_classes  # Nested class shouldn't be in root

    # Test inherited properties
    scope_classes = hierarchy.find_classes_with_property("scope")
    assert "ItemBase" in scope_classes
    assert "WeaponBase" in scope_classes
    assert "Magazine" in scope_classes  # Inherits from ItemBase

def test_circular_inheritance_detection(api, complex_class_code):
    """Test detection and handling of circular inheritance"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    # All classes in cycle should be marked invalid
    assert "CircularA" in hierarchy.invalid_classes
    assert "CircularB" in hierarchy.invalid_classes
    assert "CircularC" in hierarchy.invalid_classes

    # Invalid classes should not be in main hierarchy
    assert "CircularA" not in hierarchy.classes
    assert "CircularB" not in hierarchy.classes
    assert "CircularC" not in hierarchy.classes

def test_enum_handling(api, complex_class_code):
    """Test handling of enum definitions"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    damage_type = hierarchy.classes["DamageType"]
    assert damage_type.type == "enum"
    assert damage_type.properties["KINETIC"] == "1"
    assert damage_type.properties["EXPLOSIVE"] == "2"
    assert damage_type.properties["THERMAL"] == "3"

def test_array_properties(api, complex_class_code):
    """Test handling of array properties"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    ammo_box = hierarchy.classes["AmmoBox"]
    assert "magazines" in ammo_box.properties
    assert "weapons" in ammo_box.properties
    # Array values should be preserved
    assert "Mag1" in ammo_box.properties["magazines"]
    assert "Mag2" in ammo_box.properties["magazines"]

def test_inheritance_chain(api, complex_class_code):
    """Test inheritance chain building"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    # Test bottom-up chain
    weapon_chain = hierarchy.get_inheritance_chain("WeaponBase", bottom_up=True)
    assert weapon_chain == ["WeaponBase", "ItemBase", "ObjectBase"]

    # Test top-down chain
    tank_chain = hierarchy.get_inheritance_chain("ModernTank")
    assert tank_chain == ["BaseVehicle", "BaseTank", "ModernTank"]

def test_child_class_lookup(api, complex_class_code):
    """Test finding child classes"""
    raw_classes = api._scanner.class_scanner.scan_classes("test", {"test.cpp": complex_class_code})
    hierarchy = raw_classes.build_hierarchy()

    # Test direct children
    item_children = hierarchy.get_all_children("ItemBase", include_indirect=False)
    assert "WeaponBase" in item_children
    assert "Magazine" in item_children
    assert "ModernTank" not in item_children  # Not a direct child

    # Test all descendants
    object_descendants = hierarchy.get_all_children("ObjectBase")
    assert "ItemBase" in object_descendants
    assert "WeaponBase" in object_descendants
    assert "Magazine" in object_descendants
