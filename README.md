## SPECQP stands for SPECtroscopy Quick Peak

### What for

The package can be used for quick and more advanced plotting and fitting of spectroscopy
data. In version 1.1 it provides functionality for working with X-ray photoelectron spectroscopy
data. Plotting, normalization, background subtraction, fitting possibilities are included for 
single and series of curves.
 
GUI interface is also realized providing full interactive functionality for handling single
and series of curves. In versions 1.1 only *.xy* files from SPECS instruments and *.txt* files
from SCIENTA instruments are handled within GUI.

NOTE: The package was developed for Mac OS, but it works on Windows as well, although some GUI features may become
less pretty.

## Installation MacOS

**Remember to always save your current work before experimenting with new applications**

Python 3 version and pip library are required for installing and running the specqp software.
For some python installations the *python* and *pip* commands can refer to Python 2 version, while *python3*
and *pip3* commands correspond to Python 3 version. If that is the case for you, use *python3* and *pip3* in all
steps described above and below.

### Installation from PyPI

Just write in Terminal

    $ pip install specqp

### Installation from .whl file

Put the .whl file to any place on your hard drive, and type in Terminal

    $ pip install full/or/relative/path/to/file.whl

NOTE: If you already had it installed type first

    $ pip uninstall specqp

Finally you should see similar to the following message in the Terminal

    $ Successfully installed specqp-1.1

### Default GUI mode

To run the default GUI mode run the specqp.launcher module of the package:

    $ python -m specqp.launcher

It will automatically call the specqp.service module to create startup files and variables
if they don't yet exist. After that it will call the main() method of the specqp.gui module,
which shows the default GUI window where all the functions can be realized by pressing
corresponding buttons or calling corresponding menu options.

### Manual

More information on how to use the GUI and batch modes of the application can be found in *docs/specqp_manual.rst* 
file of the github repository accessible at *https://github.com/Shipilin/specqp* 
or via Help... menu of the installed application.