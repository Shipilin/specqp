=========================================
SPECQP stands for SPECtroscopy Quick Peak
=========================================

Default GUI mode
________________

To run the default GUI mode run the specqp.launcher module of the package:

    $ python -m specqp.launcher

It will automatically call the specqp.service module to create startup files and variables
if they don't yet exist. After that it will call the main() method of the specqp.gui module,
which shows the default GUI window where all the functions can be realized by pressing
corresponding buttons or calling corresponding menu options.


Main window
____________


*OPENING FILES*


Files can be loaded in a batch mode (see specqp_installation_launching.rst file for details) or manually. To load a
scienta (.txt) or a specs (.xy) file (examples can be found in the *test* folder of the project) manually one
can use either *load SCIENTA* or *load SPECS* buttons of the main window. It is possible to load both single and
multiple files. The same functionality is available in the *File* menu.

In the *File* menu one can find the option *Load other file type*, which one can use to load just tabular data from
file to plot it (NOTE: in this case no info about the experiment is available and therefore some corrections can
fail to work, just disable corrections if it happens).

From the *Open pressure calibration file* menu option one can also open a file (example in *test* folder of the
project), which is more specific to POLARIS setup at P22 beamline of Petra III synchrotron at DESY. Such a file has
the '.dat' extension and contains a header and tabular data received from several sensors of POLARIS. The menu option
allows to open and plot the data in such a file (works for multiple files of the same type as well).

The *Open file as text* menu option allows to open any text containing file for view (like in a text editor).


*PLOT MENU*


Here one can set some properties to change the appearance of the plots. Will be extended over time.


*HELP MENU*


Here one can check the information about the program choosing the option *About*. The option *Help...* redirects the
user to the GitHub repository, where the latest versions of the source python files, manuals and test data files
can be viewed.

The *Export log* option allows to save the program log to a chosen location for reading or sending to the developer.


*CHOOSING DATA*


The left vertical panel of the main window contains the list of regions loaded in the current session.

NOTE: The data lines correspond to XPS regions and not to files. In case a file contains several regions, its name
will be shown as a label, below which all the regions will be listed. The further work will be performed with the
regions.

*Check all* check box that allows to enable and disable all regions.

The regions with enabled checkboxes will be used for the further processing.

NOTE: Good news! The originally loaded regions are never changed and all further corrections and adjustments are done to
the original data. Every time one changes the desired corrections the whole process is repeated from the start.
Therefore no residual data changes are transferred to the new iterations.


*DATA CORRECTIONS*


In the middle section of the main widow one can set different values and preferences for the data corrections.

*Photon energy* will be used to convert the data Kinetic energy scale to Binding energy scale and back if necessary.
The value can be given as a single number or as a sequence of numbers separated by semicolon. In the former case,
the value will be used for all chosen regions. In the latter case the number of entries should be equal to the number of
chosen regions, then every region will receive its own value. If the number of entries is not equal to the number of
regions, the first value will be used for all regions.

*Energy shift(s)* follows the same rules as *Photon energy* and shifts the data by the given amount. This value can be
found by, e.g. fitting a Fermi level with Error function (available in the fitting part of the main window).

*Normilize by sweeps* checkbox divides the intensity data by the number of sweeps and by the dwell time, thus,
normalizing the data. For add-dimension data works properly for separate measurements.

*Normalize by const* normalizes by a number that one can give, e.g. based on the background height. Follows the same
rules as *Photon energy*

*Crop from:to* crops the data on the X (energy) axis. Same values are taken for all chosen regions. Does not care
about the sequential order of left and right boundaries. Needs both numbers to be entered.

*Subtract constant background* removes the constant background based on the average of 10 lowest data points.

*Subtract Shirley bg* iteratively calculates the shirley background and removes it.


*PLOTTING DATA*


Here one can change the visual representation of the corrected data. The options are self explanatory and are
applied on pressing the *Plot* button.


*SAVING DATA*


Buttons *Save* and *Save as...* allows to save the data in the chosen location. Both options save two files. One '.dat'
with two columns energy (left) and corrected intensity (right). Second is '.sqr' file with the list of all corrections
and tabular data containing energy, and intensity columns with original numbers of the region, intermediate and final
numbers obtained after all corrections. The difference between *Save* and *Save as...* is that the *Save* asks only for
the directory and takes the name of the region as the name of the file while *Save as...* allows to choose the file
name.


*FITTING DATA*


To do the fitting, one needs to press either *Fit* button for a "quick" fit or "Advanced fit" button for more extensive
fitting capabilities.

NOTE: The *Fit* buttons makes separate fit window for every chosen region, while *Advanced fit* options work with all
chosen regions as a connected set and treats them together.

NOTE: The current look of the data shown in the plot panel of the main window is the one that will be fitted in the
fit windows. So, if you want to have/not have them in the fit, remove or add corrections in the main window.

NOTE: Fit window will use the fit function that is predefined in the main window next to the button. It won't
be possible to change the fit type in the Fit window. Advanced fit option will start with the predefined fit function
but it is possible to freely choose other fit functions for different peaks later in teh Advanced fit window.

NOTE: For fitting the Fermi edge data with Error function use Fit option, Advanced Fit doesn't work with Error function.

For more details see the following sections.


Fit window
____________


Here one can do a quick fit of a spectrum with one or more peaks of the same line shape predefined in the main window.
Also, some basic plotting options are added to make visualization more flexible.

Peaks can be added and removed by '+' and '-' buttons in the top right corner of the peak field in the left panel of
the fit window. Peaks can also be disabled without removing by unchecking the checkbox in the top left corner.

The parameter values should be filled with numbers. Bounds values can stay empty or can be filled with two numbers
separated by semicolon. If no bounds values provided (-infinity, +infinity) are taken for the fitting procedure.

By checking the 'Fit' checkbox on the right side of the parameter line, one can disable the variation of that parameter
in the fitting procedure.

*Replot* replots the spectrum and the fit (if already done) with various plotting options chosen.

*Do Fit* does the fit.

*Save Fit* saves a '.fit' file where all the relevant fit parameters as well as tabular data for energy, intensity and
fitline are stored.

The fitting results are displayed in the bottom horizontal panel of the Fit window.


Advanced Fit window
____________


This window looks and works in a similar way with the regular fit window except with more functionality. It can
treat single or multiple regions as a set of connected data.

Firstly, the peaks can be fitted simultaneously together with single or multiple backgrounds. To add a background, one
needs to check the box on the left side of the corresponding background line. The 'Fix' checkbox on the right side
should be unchecked if the background parameter needs to be varied in the fitting procedure.

Secondly, the line shape of every peak can be separately varied.

Thirdly, the peaks can be fitted dependently through multiple spectra set with *Dependent **, *Dependent +* and
*Common* options. The first two options link the corresponding parameters of a peak to another peak that is
indicated in the *Base #* field. The fitting process in such a case does depending fitting of the linked peaks.

    Example: Peak 0 has position at 600 eV binding energy and 100 arbitrary units intensity. Peak 1 can be fitted
    in such a way that it has position 0.5 eV higher in energy than Peak 0 (or between 0.3 and 0.5 eV higher) and
    intensity that is 0.8 of the intensity of Peak 0. To do that one needs to choose 'values: 0.5, bounds: 0.3; 0.5,
    Dependent + Base #0' options for center and 'value: 0.8 Dependent * Base #0' for amplitude.

*Common* option when chosen makes sure that the parameter value will be kept the same for different spectra with the
resulting value that gives the best fit over all spectra. The chosen "fix" parameter makes the *Common* option useless,
while the "Base #" value is meaningless in this case and is ignored.

Buttons available in Advanced fit windows allow for plotting trends (area of the same peak through spectra), switch
between different spectra in the set using *Previous* and *Next* buttons.

One can also save the fitting parameters and tabular data like in regular Fit window by pressing *Save Fit*

Buttons *Save Figures* and *Save Movie* saves the visual data as separate .png figures and as .mp4 video with
spectra and their fit as video frames.


Batch GUI mode
______________


To be able to load multiple files in a convenient way, one can create a txt file with instructions.
The general form of the file is shown below. Lines starting with ## are not necessary to include.
NOTE: All data corresponding to one file have to be on the same line starting with *FP*

| ## Instructions file for SpecQP GUI.
| ## [name], [/name] - the beginning and the ending of a section
| ## # Comments for a section
| ## FP - Full (or relative to the current bash folder) data file path
| ## FT - File type (scienta or specs)
| ## PE - Photon energy used for the measurements
| ## ES - Energy shift (Fermi level position or otherwise determined energy shift of the spectra)
| ## NC - Normalizatin constant (e.g. mean counts rate at the lowest measured binding energy)
| ## CO - Conditions of the measurements (will be used for the comments and plot legends)
| ## CROP - Cropping (e.g. 715:703)
| ## CBG - remove/preserve Constant background (True/False)
| ## SBG - remove/preserve Shirley background (True/False)
|
| [C1s]
| # 4 H2 + 1 CO2 at 75 mbar
| FP=/Users/Data/Fe_0073.txt; FT=scienta; PE=4600; ES=3.64; NC=76; CROP=; CBG=True; SBG=; CO=150C
| FP=/Users/Data/Fe_0059.txt; FT=scienta; PE=4600; ES=3.67; NC=37; CROP=; CBG=True; SBG=; CO=200C
| FP=/Users/Data/Fe_0065.txt; FT=scienta; PE=4600; ES=3.64; NC=87; CROP=; CBG=True; SBG=; CO=250C
| FP=/Users/Data/Fe_0052.txt; FT=scienta; PE=4600; ES=3.68; NC=85; CROP=; CBG=True; SBG=; CO=300C
| [/C1s]
|
| [O1s]
| # 4 H2 + 1 CO2 at 75 mbar
| FP=/Users/Data/Fe_0074.txt; FT=scienta; PE=4600; ES=3.64; NC=76; CROP=; CBG=True; SBG=; CO=150C
| FP=/Users/Data/Fe_0058.txt; FT=scienta; PE=4600; ES=3.67; NC=37; CROP=; CBG=True; SBG=; CO=200C
| FP=/Users/Data/Fe_0066.txt; FT=scienta; PE=4600; ES=3.64; NC=87; CROP=; CBG=True; SBG=; CO=250C
| FP=/Users/Data/Fe_0053.txt; FT=scienta; PE=4600; ES=3.68; NC=85; CROP=; CBG=True; SBG=; CO=300C
| [/O1s]
|
| [Fe2p]
| # 4 H2 + 1 CO2 at 75 mbar
| FP=/Users/Data/Fe_0075.txt; FT=scienta; PE=4600; ES=3.64; NC=76; CROP=715:703; CBG=True; SBG=True; CO=150C
| FP=/Users/Data/Fe_0061.txt; FT=scienta; PE=4600; ES=3.67; NC=37; CROP=715:703; CBG=True; SBG=True; CO=200C
| FP=/Users/Data/Fe_0068.txt; FT=scienta; PE=4600; ES=3.64; NC=87; CROP=715:703; CBG=True; SBG=True; CO=250C
| FP=/Users/Data/Fe_0054.txt; FT=scienta; PE=4600; ES=3.68; NC=85; CROP=715:703; CBG=True; SBG=True; CO=300C
| [/Fe2p]
|
To load all or part of the files specified in the instructions txt file together with predefined conditions type in Terminal
one of the following lines

To load all data files specified in the txt file use *filenames* parameter:

    $ python -m specqp.launcher -gui filenames="/full/path/to/instructions.txt"

To load one section of the txt file use *filenames* and *sections* parameters:

    $ python -m specqp.launcher -gui filenames="/full/path/to/instructions.txt" sections=Fe2p

The parameters *filenames* and *sections* can be used together in different combinations:

    $ python -m specqp.launcher -gui filenames="/full/path/to/instructions.txt" sections="Fe2p;O1s"
    $ python -m specqp.launcher -gui filenames="/full/path/to/instructions.txt;/full/path/to/instructions2.txt"
    $ python -m specqp.launcher -gui filenames="/full/path/to/instructions.txt;/full/path/to/instructions2.txt" sections="Fe2p;O1s"

Every time the program meets the specified section(s) name(s) in each txt file, it loads everything within the section(s).
If the section name is not found, it is ignored.

NOTE: You can type all above mentioned commands in a text file and run it in Terminal by

    $ source /full/or/relative/path/to/file.txt

In such a way you avoid manually typing long commands in Terminal. You can store different command lines in the txt file
hiding it from Terminal interpreter by placing the '#' sign at the beginning of the line you don't want to use.