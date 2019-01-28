"""The module contains classes and functions responsible
for loading and storing spectroscopy data. It also provides
general handles for the outside modules and scripts.
The hierarchy of objects is as follows:
1. Class Experiment contains all data for an executed experiment.
Usually it shoul contains one uninterrupted set of measurements
for one sample.
2. Class SetOfSpectra contains a number of spectra measured under the same
conditions. Usually a few spectra including Fermi edge measurement.
3. Class Spectrum contains a single spectrum with possibly several
regions.
4. Class AddDimensionSpectrum is on the same hierarchical level with
the class Spectrum, but is dedicated to "add dimension" measurements
where the same spectrum is taken a number of times in a row under
changing conditions or such.
5. Class Region contains the data for one region.
6. Class FermiRegion inherits from Region and contains the data
for one Fermi Region
"""
import os
import tkinter as tk
from tkinter import filedialog
import numpy as np
import pandas as pd

def _loadScientaTXT(filename, regions_number_line=1):
    """Opens and parses provided scienta file returning the data and info for all regions
    as a list of Region objects. Variable 'regions_number_line' gives the
    number of the line in the scienta file where the number of regions is given
    (the line numbering starts with 0 and by default it is the line number 1 that
    contains the information).
    """
    # Info block parsing routine
    def parseScientaFileInfo(lines):
        """Helper function that parses the list of lines read from Scienta.txt
        file info block and returns 'info' dictionary {property: value}
        """
        info = {}
        for line in lines:
            line = line.strip()
            if '=' in line:
                line_content = line.split('=', 1)
                # Modify the file name
                if line_content[0].strip() == "File":
                    line_content[1] = line_content[1].rpartition("\\")[2].split(".", 1)[0]
                info[line_content[0]] = line_content[1]

        return info

    with open(filename) as f:
        lines = f.read().splitlines()

    # Dictionary that contains the map of the file, where the name of the section is
    # the key and the list of first and last indices of Info and Data sections is the value
    # Example: {"Region 1": [[3, 78], [81, 180]]}
    #                         Info      Data
    file_map = {}

    # The number of regions is given in the second line of the file
    regions_number = int(lines[regions_number_line].split("=")[1])
    # If number of regions higher than one, we'll need to make a list of scan objects
    regions = []

    # Temporary counter to know the currently treated region number in the
    # for-loop below
    cnt = 1
    # Temporary list variables to store the first and the last indices of the
    # info and the data file blocks for every region
    info_indices = []
    data_indices = []

    # Parsing algorithm below assumes that the file structure is constant and
    # the blocks follow the sequence:
    # [Region N] - not important info
    # [Info N] - important info
    # [Data N] - data
    for i, line in enumerate(lines):
        if ("[Region %d]" % cnt) in line:
            # If it is not the first region, than the data section of the previous
            # region ends on the previous line
            if cnt > 1:
                data_indices.append(i-1)
            continue
        if ("[Info %d]" % cnt) in line:
            info_indices.append(i+1)
            continue
        if ("[Data %d]" % cnt) in line:
            info_indices.append(i-1)
            data_indices.append(i+1)
            if cnt == regions_number:
                data_indices.append(len(lines)-1)
                break
            else:
                cnt += 1

    # Reseting region number counter to 1 to start again from the first region
    # and do the mapping procedure
    cnt = 1
    for j in range(1, len(info_indices), 2):
        file_map[f"Region {cnt}"] = [[info_indices[j-1], info_indices[j]], [data_indices[j-1], data_indices[j]]]
        cnt += 1

    # Iterating through regions
    for val in file_map.values():
        energy, counts = [], []
        # Parsing Data block of the current region
        data_block = lines[val[1][0]:val[1][1]+1]
        for line in data_block:
            if not line.strip():
                continue # Scip empty lines
            else:
                xy = line.split()
                x = float(xy[0].strip())
                y = float(xy[1].strip())
                if y > 0:
                    energy.append(x)
                    counts.append(y)

        # Info block of the current region
        info_lines = parseScientaFileInfo(lines[val[0][0]:val[0][1]+1])

        # Create a Region object for the current region with corresponding values
        # of flags
        regions.append(Region(energy, counts, info=info_lines))

    return regions

def _loadSpecsXY():
    pass

def _askPath(folder_flag=True, multiple_files_flag=False):
    """Makes a tkinter dialog for choosing the folder if folder_flag=True
    or file(s) otherwise. For multiple files the multiple_files_flag should
    be True.
    """
    root = tk.Tk()
    root.withdraw()
    path = os.getcwd()
    if folder_flag: # Open folder
        path = filedialog.askdirectory(parent=root, initialdir=path,
                                    title='Please select experiment directory')
    else: # Open file
        if multiple_files_flag:
            path = filedialog.askopenfilenames(parent=root, initialdir=path,
                                    title='Please select data files')
            path = root.tk.splitlist(path)
        else:
            path = filedialog.askopenfilename(parent=root, initialdir=path,
                                    title='Please select data file')
    root.destroy()
    return path

def readCSV(filename): # TODO rewrite for new classes
    """Reads csv file and returns Region object. Values of flags and info
    is retrieved from the comment lines marked with '#' simbol at the beginning
    of the file.
    """
    # Reading the data part of the file
    df = pd.read_csv(filename, comment='#')

    info = {}
    with open(filename, mode='r') as file:
        lines = file.readlines()

    # Reading info part of the file (lines starting with '#')
    info_lines = []
    flags = {}
    for line in lines:
        # Reading the flags
        if line.strip().startswith('#F'):
            for flag in Region._region_flags:
                if flag in line:
                    flags[flag] = line.lstrip('#F').strip().split("=")[1]
            continue

        if line.strip().startswith('#'):
            info_lines.append(line.strip('\n')) # Save info lines

    info = {}
    for line in info_lines:
        line = line.strip().lstrip('#').strip()
        line_content = line.split(':', 1)
        info[line_content[0].strip()] = line_content[1].strip()

    region = Region(df['energy'].values, df['counts'].values,
                    energy_shift_corrected=flags[Region._region_flags[0]],
                    binding_energy_flag=flags[Region._region_flags[1]], info=info)

    return region

class Experiment:
    """Class Experiment contains all data for an executed experiment.
    Usually it shoul contains one uninterrupted set of measurements
    for one sample.
    """
    def __init__(self, path=None):
        if not path:
            path = _askPath(folder_flag=True, multiple_files_flag=False)
        self.Path = path

    def __str__(self):
        return self.Path

class SetOfSpectra:
    """Class SetOfSpectra contains a number of spectra measured under the same
    conditions. Usually a few spectra including Fermi edge measurement.
    """
    def __init__(self, path=None, conditions=None):
        if not path:
            path = _askPath(folder_flag=False, multiple_files_flag=True)
        for single_file in path:
            self._Spectra.append(_loadScientaTXT(path[single_file]))

        self._Conditions = None

class Spectrum:
    """Class Spectrum contains a single spectrum with possibly several
    regions. It knows also how to parse data files since each file normally
    contains one spectrum.
    """
    def __init__(self, path=None):
        if not path:
            path = _askPath(folder_flag=False, multiple_files_flag=False)
        self._Regions = _loadScientaTXT(path)

    def setConditions(self, conditions):
        """Set conditions
        """
        self._Conditions = conditions

class AddDimensionSpectrum(Spectrum):
    """Class AddDimensionSpectrum is on the same hierarchical level with
    the class Spectrum, but is dedicated to "add dimension" measurements
    where the same spectrum is taken a number of times in a row under
    changing conditions or such.
    """
    pass

class Region:
    """Class Region contains the data for one region.
    """
    _region_flags = (
        "energy_shift_corrected",
        "binding_energy_flag"
    )

    def __init__(self, energy, counts, info=None):
        """Creates an object using two variables (of type list or similar).
        The first goes for energy (X) axis, the second - for counts (Y) axis.
        Info about the region is stored as a dictionary {property: value}.
        """
        # The main attribute of the class is pandas dataframe
        self._Data = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        # This is a dataframe identical to _Data at the beginning. It works as as
        # a backup, which can be used to restore the initial state of
        # the region data in case of cropping or similar.
        self._Raw = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        # If the region is a part of a larger object like spectrum or experiment
        # it needs to have an ID for easier access. Single region doesn't have any ID,
        # but it can be added by using internal class method.
        self._ID = None
        # Default values for flags
        self._Flags = {
                Region._region_flags[0]: False,
                Region._region_flags[1]: None
                }
        self._Info = info
        # Check which energy scale is used:
        if self._info["Energy Scale"] == "Binding":
            self._Flags[Region._region_flags[1]] = True
        else:
            self._Flags[Region._region_flags[1]] = False

    def __str__(self):
        """Prints the info read from the Scienta file
        Possible to add keys of the Info dictionary to be printed
        """
        return self.getInfoString()

    def _setID(self, regionID):
        self._ID = regionID

    def getID(self):
        return self._ID

    def resetRegion(self):
        """Removes all the changes made to the Region and restores the initial
        "counts" and "energy" columns
        """
        self._Data = self._Raw

    def invertToBinding(self, excitation_energy):
        """Changes the energy scale of the region from kinetic to binding energy
        """
        if not self._Flags[Region._region_flags[1]]:
            self.invertEnergyScale(excitation_energy)

    def invertToKinetic(self, excitation_energy):
        """Changes the energy scale of the region from binding to kinetic energy
        """
        if self._Flags[Region._region_flags[1]]:
            self.invertEnergyScale(excitation_energy)

    def invertEnergyScale(self, excitation_energy):
        """Changes the energy scale of the region from the currently defined to
        the alternative one. From kinetic to binding energy
        or from binding to kinetic energy. The photon energy used for excitation
        is required.
        """
        self._Data['energy'] = [(excitation_energy - value) for value in self._Data['energy']]
        self._Flags[Region._region_flags[1]] = not self._Flags[Region._region_flags[1]]

        # We need to change some info entries also
        self._Info["Excitation Energy"] = str(excitation_energy)
        for key in ["Energy Scale", "Energy Unit", "Energy Axis"]:
            # Depending on whether it was SPECS or Scienta file loaded, the info
            # dictionaries may have different keys. So, we scroll through all
            # possible values and change the existing ones
            if key in self._Info.keys():
                if self._Flags[Region._region_flags[1]]:
                    self._Info[key] = "Binding"
                else:
                    self._Info[key] = "Kinetic"
        for key in ["Center Energy", "Low Energy", "High Energy"]:
            if key in self._Info.keys():
                self._Info[key] = str(excitation_energy - float(self._Info[key]))

    def correctEnergyShift(self, shift):
        if not self._Flags[Region._region_flags[0]]:
            self._Data["energy"] += shift
            # We also need to change some info due to change in energy values
            for key in ["Center Energy", "Low Energy", "High Energy"]:
                self._Info[key] = str(float(self._Info[key]) + shift)
            self._Flags[Region._region_flags[0]] = True
        else:
            print(f"The region {self._Info['File']}: {self._Info['Region Name']} has already been energy corrected.")

    def cropRegion(self, start=None, stop=None):
        """Delete the data outside of the [start, stop] interval
        on "energy" axis
        """
        # Since the values of start and stop are given "by eye", we have to
        # loop through the "energy" serie to find the closest value
        if start:
            first_index = start
        else:
            first_index = 0
        if stop:
            last_index = stop
        else:
            last_index = self._Data.index.values[-1]
        self._Data = self._Data.truncate(before=first_index, after=last_index)

    def getData(self, column=None):
        """Returns pandas DataFrame with two or more columns (first two columns
        were originally retrieved from the data file, other columns could be added
        after some processing of the original data)
        """
        if column:
            return self._Data[column].values
        return self._Data

    def getInfo(self, parameter=None):
        """Returns 'info' dictionary {"name": value}
        """
        if parameter:
            return self._Info[parameter]
        return self._Info

    def getInfoString(self, *args):
        """Returns info string with the information about the region
        Possible to add keys of the Info dictionary to be printed
        """
        output = ""
        if not self._Info:
            output = "No info available"
        else:
            if len(args) == 0:
                for key, val in self._Info.items():
                    output = "\n".join((output, f"{key}: {val}"))
            else:
                for arg in args:
                    output = "\n".join((output, f"{arg}: {self._Info[arg]}"))
        return output

    def getFlags(self):
        """Returns the dictionary of flags
        """
        return self._Flags

    def isEnergyCorrected(self):
        return self._Flags[0]

    def isBinding(self):
        return self._Flags[1]

    def addColumn(self, column_label, array, overwrite=False):
        """Adds one column to the data object assigning it the name 'column_label'.
        Choose descriptive labels. If label already exists but 'overwrite' flag
        is set to True, the method overwrites the data in the column.
        """
        if column_label in self._Data.columns:
            if not overwrite:
                print(f"Column '{column_label}' already exists in {self._Info['File']}: {self._Info['Region Name']}")

        self._Data[column_label] = array

    def removeColumn(self, column_label):
        """Removes one of the columns of the data object
        """
        if (column_label == 'energy') or (column_label == 'counts'):
            print("Basic data columns can't be removed!")
            return
        self._Data = self._Data.drop(column_label, 1)

    def saveCSV(self, filename): # TODO change the struture of file
        """Saves Region object in the csv file with given name. Flags and info are
        stored in the comment lines marked with '#' simbol at the beginning of
        the file.
        """
        # If the file exists, saving data to the file with alternative name
        if os.path.isfile(filename):
            name_and_extension = filename.split(".")
            for i in range(1, 100):
                filename = ".".join(["".join([name_and_extension[0], f"_{i}"]), name_and_extension[1]])
                if not os.path.isfile(filename):
                    break

        with open(filename, mode='a+') as file:
            for key, value in self._Flags.items():
                file.write(f"#F {key}={value}\n")
            for key, value in self._Info.items():
                file.write(f"# {key}: {value}\n")
            self._Data.to_csv(file, index=False)

class FermiRegion(Region):
    """Class FermiRegion contains the data for one Fermi region.
    """
    def setShift(shift):
        self._Shift = shift

    def getShift(self):
        if self._Shift:
            return self._Shift
        else:
            print(f"The region {self._Info['File']}: {self._Info['Region Name']} has not been fitted yet.")
