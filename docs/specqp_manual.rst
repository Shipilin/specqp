=========================================
SPECQP stands for SPECtroscopy Quick Peak
=========================================

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
For more details see the following sections.
NOTE: The *Fit* buttons makes separate fit window for every chosen region, while *Advanced fit* options work with all
chosen regions as a connected set and treats them together.
NOTE: The current look of the data shown in the plot panel of the main window is the one that will be fitted in the
fit windows. So, if you want to have/not have them in the fit, remove or add corrections in the main window.


Fit window
____________




Advanced Fit window
____________

This window shows up when the "Advanced Fit" button of the main window has been pressed.

In the right pannel the same plot that was earlier obtained in the main window is presented (note that
if you changed some settings in the "Settings" or "Plotting" panels of teh main windows and pressed the "Advanced Fit"
button without pressing "Plot" button of the main window, the advanced fit window may show a differently looking plot).





...

*Common* option when chosen makes sure that the parameter value will be kept the same for different
spectra with the resulting value that gives the best fit over all spectra. The chosen "fix" parameter makes the *Common*
option useless, while the "Base #" value is meaningless in this case and is ignored.