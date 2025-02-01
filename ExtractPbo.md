ExtractPbo
Jump to navigation
Jump to search
ExtractPbo (Gui) and ExtractPboDos version 2.xx by mikero.
WIN VISTA and beyond. This exe is not compatible with winxp.
See readmeGeneral and fixes
ExtractPboDos is a dos console only application for spread freaks.
ExtractPbo is the gui version which contains ExtractPboDos inside
ExtractPbo works in an identical manner to ExtractPboDos in console mode.
ExtractPbo does what it is name suggests.
ExtractPbo covers the nuances of all Bis 'pbo' files from the very first cwc demo to Arma3. This includes (but is not limited to):
    Cold war crisis
    Resistance
    Xbox Elite
    Arma1,2,3
    Arrowhead
    Ifa (ifa files)
    vbs2lite (xbo files)
Extractpbo will specifically not extract vbs2 'ebo' files.
In the following documentation a 'pbo' is considered to be: .pbo, .ifa, ,ebo, .xbo
This is a powerful dos console extractor that extracts ANY pbo from CWR thru to VBS2 LITE (xbo files)
ExtractPbo uses a heuristic approach to output the best possible results to the best-possible output folder. While you can over-ride the default options the general scenario is that the extractor will
    Derapify binarised content (mission.sqm, config.bin. *rvmat ,etc)
    Decompress a pbo (ofp only)
    Decrypt Elite and VBS2 Lite pbo's
    Autodetect the type of pbo / xbo / ebo
    Verify valid compression for p3d and paa content (eg)
In the specific case of non-ofp pbo's , the prefix is accounted for by writing the file pboPrext.txt to the output.
An erroneous pboPrext.txt file if detected in the pbo itself, is never extracted.
usage
extractpbo [-options...] NameOfPbo[.pbo|.xbo|.ebo]/aFolder/AnExtractionList [SomeFolder]
.extensions are not required. a 'pbo' is considered to be ANY *.xbo,*.ebo,*pbo
options (optional, case insensitive)
-L list only
-LB brief dir style output
-P do not pause (allow the controlling program to handle the return status)
-S silent (default)
-N Noisy
-D Derapify file(s) where relevant (default)
-R Dont Derapify file(s)
-Y Don't prompt if overwriting a folder
-A deprecated
-T used spaced (not tabbed) derap output
-W Warnings are errors
-V1 force extraction of vbs2 lite uk
-V2 ditto us
normally, the dll will detect which type it is. In extreme circumstances the heuristic model might fail, and you can force it to one, or the other.
Note missions (pbo) and addons (xbo) are equivalent.
-F filelist[,...] name(s) of file(s) to extract
extracted file(s) will appear in their 'correct' position in the relevent output folder tree
thus, multiple instances of config.cpp (eg) can be extracted.
a minor form of wildcard the aster dot sequence can indicate 'all' extensions of that type
-K ignore prefix
Contents
    1 OUTPUT FOLDER
        1.1 =================
        1.2 =================
    2 Other examples
OUTPUT FOLDER
Distinctions exist between folder output for OFP vs non OFP (ARMA)
    in OFP the NameOfPbo is sacrosanct. It must form part of the output to have any meaning to the engine.
    in ARMA the prefix inside the pbo is sacrosanct. It will form part of the output.
The dll detects the difference.
Thus:
For OFP:
extractppo thing.pbo >> contents to thing\
extractpbo thing.pbo anywhere >> contents to anywhere\thing\
For ARMA:
extractppo thing.pbo >> contents to thing\'prefix'\
extractpbo thing.pbo drive:\anywhere >> contents to contents to anywhere\'prefix'\
the anywhere clause for arma allows creation of a p:\ca by specifying
extractpbo thing P:\
Note that the -K option ignores the prefix and writes to output as per ofp
this can be a convenience when decoding very long paths
Be WARNED
Normally, extractPBO does two important things
1) it checks before over-writing a folder
2) it erases all output folder content in an 'all bets are off' approach before extracting the pbo
using the anywhere option causes these 2 features to be disabled.
if you have crap in the output folder(s). the crap will remain in the output folder(s)
if you specify an 'interesting' destination. you will get, 'interesting' results.
extraction behaviour
        Fundamentally, a folder is created of the same name as the pbo in the same
folder as the pbo.
        Arma pbo's will, in addition, create subfolders based on the detected
prefix. Thus:
ExtractPbo Thing
OFP: pbo thing.pbo -> thing\.....
ARMA: pbo thing.pbo -> thing\Prefix\......
Option -K is used to force OFP behaviour
ExtractPbo -k Thing //Arma prefix subfolders are NOT created (but the $PREFIX% is still supplied correctly)
thing.pbo -> thing\..... (prefix is ignored)
        ============================
        Specifying a destination
        ============================
ExtractPbo thing P:\
thing.pbo ->P:\prefix\.... will create a perfect namespace based on the prefix.
ExtractPbo thing -k P:\
thing.pbo ->P:\thing\prefix\....
ExtractPbo thing P:\SomeWhere
thing.pbo ->P:\Somewhere\prefix\...
ExtractPbo -K thing P:\SomeWhere
thing.pbo ->P:\Somewhere\thing\.........
=================
Specifying a relative destination address
=================
you can't. drive: MUST be specified
Other examples
extractpbo thing
will extract thing.pbo to thing\ folder and derapify any content (such as mission.sqm) that has been binarised
extractpbo -f -r mission.sqm thing.pbo
will extract a single file (and NOT derapify)
extractpbo -L thing
does a dir listing of pbo content along with added info
extractpbo -f *.p3d nameofpbo
will extract ONLY p3d files
extractpbo ExtractionList.any [toSomewhere]
will extract files contained in extraction list. Nameof extraction list can be anything other than .pbo, or foldername
line syntax for each line is identical to command line.
global parameters FROM the command line operate as defaults if not respecified in the list
extractpbo Folder [toSomewhere]
will recurse subfolders of above searching for pbo files.
==warning messages====
"1st/last entry has non-zero real_size, reserved, or BlockLength field"
"reserved field non zero anywhere in entry bodies (except xbo)"
Normally an attempt to prevent extraction and should present no issues. But, users should suspect something wonky in the author's implementation
"no shakey on arma";
early pbo makers did not create the appended 21 byte sha. This causes issues only if attempting to sign the pbo for MP play
"residual bytes in file" // throws an error anyway
something has been either misinterpreted, or the pbo maker is at fault
"arma pbo is missing a prefix (probably a mission)";
missions do not require prefix entries. But, as a matter of de-riguer, they normally have them.
ExtractPbo,exe is ExtractPboDos.exe with Window dressing (pun intended).
Major Features:
    Dual Dos-Console or Windows Mode.
    Drag n Drop Interface fully exploited.
        Drop (and open) pbo's onto the dialog
        Drag or drop single files or entire folders INTO or OUT OF the pbo
        Double Click Automated viewing of (almost) any pbo file in it is relevant application (texview,visitor, rvmat, ogg)
        Renaming/Deleting/Adding/Moving any part of the pbo tree
This application implements a consistent user interface. To whit:
    All files extracted from a pbo are unconditionally:
        DeCrypted if encrypted.
        DeCompressed if compressed.
        Unparsed to humanly readable text (config.bin, rvmat, bisurf eg)
    All Saved As pbo's are unconditionally:
        Encrypted if vbs2lite
        Uncompressed
        Parsed (Rapified)
To keep the interface noise free and simple to use, there is no facility for selective Parsing/Compression/Encryption. All of these 'features' use tried and proven algorithms inside the dll including which types of files require modification.
Dos Mode:
It will operate, just like before, in dos (console) mode, allowing batch file processing, drag n drop, and dos console operations. It will behave as nature intended, and as described, in the ExtractPbo readme. A more versatile and extensive range of -options exist in this mode for the connoisseur (or insane). The very popular Arma2P extractor for instance uses Dos Mode.
Windows Mode:
Windows mode is how most (new) users will prefer to use it.
Switching between Dos and Windows Mode:
ANY parameters supplied on the command line invoke Dos Mode. This occurs as a natural result of simply using it in a dos console to begin with and specifying a pbo to extract, or, dropping a file onto the exe icon. On the other hand, simply invoking this exe from a dos console with NO parameters, invokes the gui.
Windows mode uses previously recorded 'session' data of which files, what targets, to start with (including window positioning and size).
Forcing Windows Mode:
-w on the command line, or, by checkbox.
Be wary of using this option. Dos batch files expecting dos results, will fail.
ExtractPboGui will extract the content of any 'pbo' except encrypted vbs2. (yes, it does extract vbs2lite)
The over-riding philosophy of all MikeroTools (not just this one) is to maintain backward compatibility. To this end, the same 'behaviour' can be expected from files emanating from the very first cwc demo, Resistance, Xbox Elite, Arrowhead, TOH, Arma3, IFA extensions, Vbs2lite. There are nuances to each type which the underlying dll takes care of. They are hidden from the user (and hidden from developers using the dll who only want to 'see' a uniform API). ExtractPboGui utilises over a decade of lessons learned in the dll about things-pbo. Underneath the covers it is exceptionally powerful and above all, robust.
Options available in this gui are intentionally bare minimal. The intent being, 'just extract the damn thing'.
Installation:
Self installer: sit back and watch the pretty lights.
Manual Install:
Anywhere that gives you a thrill, but take note that dePbodll is also required for this gui. (of course)
'pbo'
    In this documentation 'pbo' is meant to infer SomeFile.pbo
    To avoid the risk of tediousness everywhere else, a 'pbo' can actually be an .xbo .ebo, .ifa, or, indeed, a .pbo. If a .toh ever gets introduced (or any other 'pbo' extension) you can be sure the underlying dll will 'understand' it is a Packed Binary Object.
Gui options:
PboName
Use the browse button (...) to select any 'pbo' from anywhere, including net drives.
Output Path
Use the browse button (...) to select the beginning of the extraction point or simply type or paste it in. The Browse button allows you to create new folder(s) for the beginning should you wish to.
Note most carefully. This is the beginning path of all extracted content. From this point on, the nature of the pbo determines how that path will be filled (by prefix, by pboname)
If you wanted to re-create the bis engine's view of 'files', you would set the Output Path to "P:\"
Destination Folder
ExtractPboGui autogenerates this path based on the OutputPath above, catenated with the internal prefix of the selected pbo (if any), or it is pboname (if none). There is no facility to change this catenated prefix.
    Allow Overwrite
        If the Destination Folder already exists, you will normally be asked before extracting. Allow Overwrite removes this sometimes annoying safety feature.
        Be aware this is the Destination Folder being over-written, not, the entire Output Path.
        Remove Folder Before Extraction.
            In a fair and reasonable world, you wouldn't want 'stale' paa's remaining via some previously extracted content. Or any other 'file' you might have placed there. Unfortunately the nature of Arma prefixed pbo's is such that nost of the pbo's live inside the file space of some other pbo. If you extracted Air3.pbo and THEN extracted Air.pbo (it's root). Air3 content would be inadvertently removed.
BUTTONS
EXTRACT
Should speak for itself. The main purpose of this application!
SAVEAS

