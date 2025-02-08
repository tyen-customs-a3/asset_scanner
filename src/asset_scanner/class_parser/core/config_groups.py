from typing import Set

class ConfigGroups:
    """Helper for managing config groups"""
    KNOWN_GROUPS = {
        'CfgPatches',
        'CfgVehicles',
        'CfgWeapons',
        'CfgAmmo',
        'CfgMagazines'
    }

    @staticmethod
    def is_valid_group(group: str) -> bool:
        """Check if a config group name is valid"""
        return group.startswith('Cfg') and (
            group in ConfigGroups.KNOWN_GROUPS or 
            group.replace('Cfg', '').isalpha()
        )

    @staticmethod
    def normalize_group(group: str) -> str:
        """Normalize a config group name"""
        if not group.startswith('Cfg'):
            return f"Cfg{group}"
        return group