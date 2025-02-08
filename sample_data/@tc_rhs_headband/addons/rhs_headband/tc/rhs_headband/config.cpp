////////////////////////////////////////////////////////////////////
//DeRap: config.bin
//Produced from mikero's Dos Tools Dll version 9.93
//https://mikero.bytex.digital/Downloads
//'now' is Sat Feb 01 13:12:48 2025 : 'file' last modified on Thu Jan 16 10:18:46 2025
////////////////////////////////////////////////////////////////////

#define _ARMA_

class CfgPatches
{
	class tc_rhs_headband
	{
		author = "PCA";
		requiredVersion = 1.6;
		requiredAddons[] = {"A3_Characters_F","A3_Weapons_F_Exp","rhs_main","rhs_c_troops"};
		units[] = {};
		weapons[] = {};
	};
};
class CfgWeapons
{
	class ItemCore;
	class H_HelmetB: ItemCore
	{
		class ItemInfo;
	};
	class rhs_headband;
	class tc_rhs_headband: rhs_headband
	{
		displayName = "Headband (I <3 Choccy Milk)";
		hiddenSelectionsTextures[] = {"tc\rhs_headband\data\tex\headband_choccymilk_co.paa"};
	};
};
