=========================================
SPECQP stands for SPECtroscopy Quick Peak
=========================================

Installation
____________

NOTE: Python 3.x.x version and pip library are required for installing and running the specqp software.

NOTE: One certain tkinter (python gui tool) version and one certain MacOS version have a poor compatibility which
results in rebooting the system upon running the program. This chance is slim but, just in case you are "lucky",
save your work in other applications before doing the following actions.

NOTE: for some python installations the *python* and *pip* commands can refer to Python 2.x.x version, while *python3*
and *pip3* commands correspond to Python 3.x.x version. If that is the case for you, use *python3* and *pip3* in all
steps described below

Check *python* and *pip* versions by typing in Terminal (for MacOS):

    $ which python

and

    $ python -V

The first command shows the path to active python environment, the second shows the version (should be 3.x.x).

To check pip, type

    $ pip --version

If this command shows some version of pip, you're good to go.
Otherwise install pip (should be easy, check Google for instructions)

After you've done the check, put the .whl file from the dist subdirectory in any place on your hard drive,
and, being in this directory in Terminal, type

    $ pip install *name of the .whl file*

NOTE: If you already had it installed type first

    $ pip uninstall specqp

Finally you should see similar to the following message in the Terminal

    $ Successfully installed specqp-1.1

Default GUI mode
________________

To run the default GUI mode run the specqp.launcher module of the package:

    $ python -m specqp.launcher

It will automatically call the specqp.service module to create startup files and variables
if they don't yet exist. After that it will call the main() method of the specqp.gui module,
which shows the default GUI window where all the functions can be realized by pressing
corresponding buttons or calling corresponding menu options.

Batch GUI mode
______________

To be able to load multiple files in a convenient way, one can create a txt file with instructions.
The general form of the file is shown below. Lines starting with ## are not necessary to include.

    ## Instructions file for SpecQP GUI.
    ## [name], [/name] - the beginning and the ending of a section
    ## # Comments for a section
    ## FP - Full (or relative to the current bash folder) data file path
    ## FT - File type (scienta or specs)
    ## PE - Photon energy used for the measurements
    ## ES - Energy shift (Fermi level position or otherwise determined energy shift of the spectra)
    ## NC - Normalizatin constant (e.g. mean counts rate at the lowest measured binding energy)
    ## CO - Conditions of the measurements (will be used for the comments and plot legends)
    ## CROP - Cropping (e.g. 715:703)
    ## CBG - remove/preserve Constant background (True/False)
    ## SBG - remove/preserve Shirley background (True/False)

    [C1s]
    # 4 H2 + 1 CO2 at 75 mbar
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0073.txt; FT=scienta; PE=4600; ES=3.64; NC=76; CROP=; CBG=True; SBG=; CO=150C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0059.txt; FT=scienta; PE=4600; ES=3.67; NC=37; CROP=; CBG=True; SBG=; CO=200C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0065.txt; FT=scienta; PE=4600; ES=3.64; NC=87; CROP=; CBG=True; SBG=; CO=250C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0052.txt; FT=scienta; PE=4600; ES=3.68; NC=85; CROP=; CBG=True; SBG=; CO=300C
    [/C1s]

    [O1s]
    # 4 H2 + 1 CO2 at 75 mbar
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0074.txt; FT=scienta; PE=4600; ES=3.64; NC=76; CROP=; CBG=True; SBG=; CO=150C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0058.txt; FT=scienta; PE=4600; ES=3.67; NC=37; CROP=; CBG=True; SBG=; CO=200C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0066.txt; FT=scienta; PE=4600; ES=3.64; NC=87; CROP=; CBG=True; SBG=; CO=250C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0053.txt; FT=scienta; PE=4600; ES=3.68; NC=85; CROP=; CBG=True; SBG=; CO=300C
    [/O1s]

    [Fe2p]
    # 4 H2 + 1 CO2 at 75 mbar
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0075.txt; FT=scienta; PE=4600; ES=3.64; NC=76; CROP=715:703; CBG=True; SBG=True; CO=150C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0061.txt; FT=scienta; PE=4600; ES=3.67; NC=37; CROP=715:703; CBG=True; SBG=True; CO=200C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0068.txt; FT=scienta; PE=4600; ES=3.64; NC=87; CROP=715:703; CBG=True; SBG=True; CO=250C
    FP=/Users/Shipilin/Documents/07_DataAnalysis/2019-03-Fe110/Data/Fe_0054.txt; FT=scienta; PE=4600; ES=3.68; NC=85; CROP=715:703; CBG=True; SBG=True; CO=300C
    [/Fe2p]

To load all or part of the files specified in the instructions txt file together with predefined conditions type in Terminal
one of the following lines

To load all data files specified:

    $ python -m specqp.launcher -gui filename="/full/path/to/instructions.txt"

To load one section of the txt file:

    $ python -m specqp.launcher -gui filename="/full/path/to/instructions.txt" section=Fe2p

To load several sections of the txt file:

    $ python -m specqp.launcher -gui filename="/full/path/to/instructions.txt" section="Fe2p;O1s"

To load several txt files:

    $ python -m specqp.launcher -gui filenames="/full/path/to/instructions.txt;/full/path/to/instructions2.txt"

The last option can be combined with *section* and *sections* flags in the same way as shown higher above.
Every time the program meets the specified section(s) name(s) in each txt file, it loads everything within the section(s).
If the section name is not found, it is ignored.
