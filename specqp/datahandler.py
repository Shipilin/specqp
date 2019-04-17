"""The module contains classes and functions responsible
for loading and storing spectroscopy data. It also provides
general handles for the outside modules and scripts.

The hierarchy of objects is as follows:
1. Class Experiment contains all data for an executed experiment.
Usually it should contain one uninterrupted set of measurements
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
"""
import os
import copy
import pandas as pd


class DataFile(file_abspath, fileID=None):
    """The class that knows the loaded file and knows how to read it properly
    """
    def __init__(self):
        self.filepath = file_abspath
        if fileID:
            self.ID = fileID
        else:
            self.ID = file_abspath





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
        # Not all info entries are important for data analysis,
        # Choose only important ones
        info_lines_revised = {}
        info_lines_revised[Region._info_entries[0]] = info_lines["Region Name"]
        info_lines_revised[Region._info_entries[1]] = info_lines["Pass Energy"]
        info_lines_revised[Region._info_entries[2]] = info_lines["Number of Sweeps"]
        info_lines_revised[Region._info_entries[3]] = info_lines["Excitation Energy"]
        info_lines_revised[Region._info_entries[4]] = info_lines["Energy Scale"]
        info_lines_revised[Region._info_entries[5]] = info_lines["Energy Step"]
        info_lines_revised[Region._info_entries[6]] = info_lines["Step Time"]
        info_lines_revised[Region._info_entries[7]] = info_lines["File"]
        info_lines_revised[Region._info_entries[8]] = f"{info_lines['Date']} {info_lines['Time']}"

        # Create a Region object for the current region
        regions.append(Region(energy, counts, info=info_lines_revised))

    return regions


def _loadSpecsXY(filename):
    """Opens and parses provided SPECS file returning the data and info for recorded
    region as a list of Region objects in order to be consistent with the Scienta
    loading routine.
    """
    def parseSpecFileInfo(lines):
        """Parses the list of lines read from SPEC.xy file info block
        and returns 'info' dictionary
        """
        info = {}
        for line in lines:
            line = line.strip().lstrip('#').strip()
            if ':' in line:
                line_content = line.split(':', 1)
                info[line_content[0].strip()] = line_content[1].strip()

        return info

    with open(filename) as f:
        lines = f.read().splitlines()

    # Basic parsing based on the appearance of SPECS files
    energy, counts = [], []
    info_lines = []
    for line in lines:
        if not line.strip():
            continue # Scip empty lines
        elif line.strip().startswith('#'):
            info_lines.append(line) # Save info lines
        else:
            xy = line.split()
            x = float(xy[0].strip())
            y = float(xy[1].strip())
            if y > 0:
                energy.append(x)
                counts.append(y)

    regions = []
    # The file might be empty, then we ignore it
    if energy:
        # Switch from list to dictionary
        info_lines = parseSpecFileInfo(info_lines)

        # Check which energy scale is used:
        if info_lines["Energy Axis"] == "Kinetic Energy":
            info_lines["Energy Axis"] = "Kinetic" # To make it consistent with scienta
        else:
            info_lines["Energy Axis"] = "Binding"

        # Not all info entries are important for data analysis,
        # Choose only important ones
        info_lines_revised = {}
        info_lines_revised[Region._info_entries[0]] = info_lines["Region"]
        info_lines_revised[Region._info_entries[1]] = info_lines["Pass Energy"]
        info_lines_revised[Region._info_entries[2]] = info_lines["Number of Scans"]
        info_lines_revised[Region._info_entries[3]] = info_lines["Excitation Energy"]
        info_lines_revised[Region._info_entries[4]] = info_lines["Energy Axis"]
        info_lines_revised[Region._info_entries[5]] = str(abs(energy[-1] - energy[0])/int(info_lines["Values/Curve"]))
        info_lines_revised[Region._info_entries[6]] = info_lines["Dwell Time"]
        info_lines_revised[Region._info_entries[7]] = filename.rpartition('.')[0].rpartition('/')[2]
        info_lines_revised[Region._info_entries[8]] = info_lines["Acquisition Date"]

        # Create a Region object for the current region
        regions.append(Region(energy, counts, info=info_lines_revised))
    return regions


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
                    binding_energy_flag=flags[Region._region_flags[1]],
                    info=info)

    return region


class Experiment:
    """Class contains a number of spectra that were taken as one set of measurements.
    Usually for one sample and one reaction with changing conditions.
    The main attribute is Spectra dictionary {"spectrumID": spectrum}
    It is empty upon object instance initialization and has to be populated using
    addSpectrum method.
    """
    def __init__(self):
        self._Spectra = {}
        self._EnergyShifts = {}
        self._GaussFWHMs = {}

    def __str__(self):
        output = ""
        if not self._Spectra:
            output = "No spectra were loaded"
        else:
            for i, key in enumerate(self._Spectra.keys()):
                if i == 0:
                    output = "".join((output, self._Spectra[key].__str__()))
                else:
                    output = "\n".join((output, self._Spectra[key].__str__()))
        return output

    def addSpectrum(self, spectrum):
        """Adds spectrum to the Experiment object
        """
        self._Spectra[spectrum.getID()] = spectrum

    def addEnergyShift(self, energy_shift, spectrumID):
        """Adds energy shift to the spectrum with specified ID within
        Experiment object
        """
        self._EnergyShifts[spectrumID] = energy_shift

    def addEnergyShift(self, gauss_fwhm, spectrumID):
        """Adds gaussian widening to the spectrum with specified ID within
        Experiment object
        """
        self._GaussFWHMs[spectrumID] = gauss_fwhm

    def getSpectrum(self, spectrumID):
        if not spectrumID in self._Spectra:
            print(f"Spectrum {spectrumID} is not loaded in the experiment.")
            return
        return self._Spectra[spectrumID]

    def getEnergyShift(self, spectrumID):
        if not spectrumID in self._Spectra:
            print(f"Spectrum {spectrumID} is not loaded in the experiment.")
            return
        return self._EnergyShifts[spectrumID]

    def getGaussFWHM(self, spectrumID):
        if not spectrumID in self._Spectra:
            print(f"Spectrum {spectrumID} is not loaded in the experiment.")
            return
        return self._GaussFWHMs[spectrumID]

    def getSpectraID(self):
        return self._Spectra.keys()


class Spectrum:
    """Class Spectrum contains a single spectrum with possibly several
    regions. It knows also how to parse data files since each file normally
    contains one spectrum.
    """
    def __init__(self, path=None, conditions=None, ID=None, excitation_energy=None, file_type="scienta"):
        if not path:
            path = _askPath(folder_flag=False, multiple_files_flag=False)

        self._Path = path
        if file_type == "scienta":
            self._Regions = _loadScientaTXT(self._Path)
        elif file_type == "specs":
            self._Regions = _loadSpecsXY(self._Path)
            if not excitation_energy and self._Regions:
                excitation_energy = float(self.getRegion().getInfo("Excitation Energy"))
        self._setConditions(conditions)
        self._setExcitationEnergy(excitation_energy)

        if not ID:
            # Set name of the file without extention as ID
            ID = path.rpartition("/")[2].split(".", 1)[0]
        self._setID(ID)

    def __str__(self):
        output = ""
        if not self._Regions:
            output = f"No regions in {self._ID} spectrum"
        else:
            output = "".join((output, f"Spectrum: #{self._ID}"))
            if self._Conditions:
                for key, val in self._Conditions.items():
                    output = "\n".join((output, f"{key}: {val}"))
            for region in self._Regions:
                output = "\n--->".join((output, region.getID()))
        return output

    def _setID(self, spectrumID):
        self._ID = spectrumID

    def _setConditions(self, conditions):
        """Set spectrum's experimental conditions to a dictionary
        {"Property": Value}. Also transfers them to every Region object within
        the Spectrum object
        """
        self._Conditions = conditions
        for region in self._Regions:
            region._setConditions(conditions)

    def _setExcitationEnergy(self, excitation_energy):
        """Set spectrum's excitation energy. Also transfers the value to
        every Region object within the Spectrum object
        """
        self._ExcitationEnergy = excitation_energy
        for region in self._Regions:
            region._setExcitationEnergy(excitation_energy, overwrite=True)

    def isEmpty(self):
        """Returns True if there are no regions in spectrum objects.
        False otherwise.
        """
        if self._Regions:
            return False
        return True

    def setFermiFlag(self, regionID):
        """Sets True for Fermi flag of the region specified by regionID
        """
        for region in self._Regions:
            if region.getID() == regionID:
                region.setFermiFlag()

    def getID(self):
        return self._ID

    def getConditions(self, property=None):
        """Returns experimental conditions as a dictionary {"Property": Value} or
        the value of the specified property.
        """
        if property:
            return self._Conditions[property]
        return self._Conditions

    def getExcitationEnergy(self):
        return self._ExcitationEnergy

    def getRegions(self):
        """Returns a list of regions
        """
        return self._Regions

    def getRegion(self, regionID=None):
        """If there is only one region in the spectrum, which is often the case,
        returns this region as a single object.
        """
        if regionID:
            for region in self._Regions:
                if region.getID() == regionID:
                    return region
                else:
                    print(f"Spectrum {self.getID()} doesn't contain {regionID} region")
        else:
            if len(self._Regions) == 1:
                return self._Regions[0]
            else:
                if self.isEmpty():
                    print(f"The spetrum {self.getID()} is empty")
                else:
                    print(f"The spetrum {self.getID()} contains more than one region")

    def getFilePath(self):
        """Returns the path to the original file with the data
        """
        return self._Path


class AddDimensionSpectrum(Spectrum): # TODO finish writing the class
    """Class AddDimensionSpectrum is on the same hierarchical level with
    the class Spectrum, but is dedicated to "add dimension" measurements
    where the same spectrum is taken a number of times in a row under
    changing conditions.
    """
    pass


class Region:
    """Class Region contains the data for one region.
    """
    _info_entries = (
        "Region Name",          # 0
        "Pass Energy",          # 1
        "Sweeps Number",        # 2
        "Excitation Energy",    # 3
        "Energy Scale",         # 4
        "Energy Step",          # 5
        "Dwell Time",           # 6
        "File Name",            # 7
        "Date",                 # 8
        "Conditions"            # 9
    )

    _region_flags = (
        "energy_shift_corrected",
        "binding_energy_flag",
        "fermi_flag",
        "sweeps_normalized"
    )

    def __init__(self,
                 energy,
                 counts,
                 info=None,
                 excitation_energy=None,
                 conditions=None,
                 ID=None,
                 fermiFlag=False):
        """Creates an object using two variables (of type list or similar).
        The first goes for energy (X) axis, the second - for counts (Y) axis.
        Info about the region is stored as a dictionary {property: value}.
        The same goes for experimental conditions.
        """
        # The main attribute of the class is pandas dataframe
        self._Data = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        # This is a dataframe identical to _Data at the beginning. It works as as
        # a backup, which can be used to restore the initial state of
        # the region data in case of cropping or similar.
        self._Raw = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        if not info:
            info = {}
        self._Info = info
        self._RawInfo = info
        # Experimental conditions
        self._setConditions(conditions)
        # Excitation energy
        self._setExcitationEnergy(excitation_energy)
        # Default values for flags
        self._Flags = {
                Region._region_flags[0]: False,
                Region._region_flags[1]: None,
                Region._region_flags[2]: fermiFlag,
                Region._region_flags[3]: False
                }
        # Check which energy scale is used:
        if self._Info: # Info can be None
            if self._Info[Region._info_entries[4]] == "Binding":
                self._Flags[Region._region_flags[1]] = True
            else:
                self._Flags[Region._region_flags[1]] = False
            # If info is available for the region and the ID is not assigned,
            # take string 'FileNumber:RegionName' as ID
            if not ID:
                ID = f"{self._Info[Region._info_entries[7]]}:{self._Info[Region._info_entries[0]]}"
        self._setID(ID)

        self._Fitter = None # After fitting of the region we want to save the
                            # results and the Region object should know about it

        self.addColumn('final', self._Data["counts"])

    def __str__(self):
        """Prints the info read from the Scienta file
        Possible to add keys of the Info dictionary to be printed
        """
        return self.getInfoString()

    def __sub__(self, other_region): # TODO
        """Returns the difference of the "final" column of two instances
        """
        return self._Data["final"] - other_region.getData("final")

    def _setID(self, regionID):
        self._ID = regionID

    def _setConditions(self, conditions):
        """Set experimental conditions as a dictionary {"Property": Value}
        """
        self._Conditions = conditions

    def _setExcitationEnergy(self, excitation_energy, overwrite=False):
        """Set regions's excitation energy.
        """
        self._ExcitationEnergy = excitation_energy
        if overwrite:
            self._Info[Region._info_entries[3]] = str(excitation_energy)

    def setFermiFlag(self):
        self._Flags[Region._region_flags[2]] = True

    def getConditions(self, property=None):
        """Returns experimental conditions as a dictionary {"Property": Value} or
        th evalue of the specified property.
        """
        if property:
            return self._Conditions[property]
        return self._Conditions

    def getExcitationEnergy(self):
        return self._ExcitationEnergy

    def getID(self):
        return self._ID

    def resetRegion(self):
        """Removes all the changes made to the Region and restores the initial
        "counts" and "energy" columns together with the _Info
        """
        self._Data = self._Raw
        self._Info = self._RawInfo

    def invertToBinding(self):
        """Changes the energy scale of the region from kinetic to binding energy.
        """
        if not self._Flags[Region._region_flags[1]]:
            self.invertEnergyScale()

    def invertToKinetic(self):
        """Changes the energy scale of the region from binding to kinetic energy.
        """
        if self._Flags[Region._region_flags[1]]:
            self.invertEnergyScale()

    def invertEnergyScale(self):
        """Changes the energy scale of the region from the currently defined to
        the alternative one. From kinetic to binding energy
        or from binding to kinetic energy.
        """
        self._Data['energy'] = [(self._ExcitationEnergy - value) for value in self._Data['energy']]
        self._Flags[Region._region_flags[1]] = not self._Flags[Region._region_flags[1]]

        # We need to change "Energy Scale" info entry also
        if self._Flags[Region._region_flags[1]]:
            self._Info[Region._info_entries[4]] = "Binding"
        else:
            self._Info[Region._info_entries[4]] = "Kinetic"

    def correctEnergyShift(self, shift):
        if not self._Flags[Region._region_flags[0]]:
            self._Data['energy'] += shift
            self._Flags[Region._region_flags[0]] = True
        else:
            print(f"The region {self.getID()} has already been energy corrected.")

    def normalizeBySweeps(self):
        # If not yet normalized
        if not self._Flags[self._region_flags[3]]:
            if self._Info and (Region._info_entries[2] in self._Info):
                self._Data['counts'] = self._Data['counts'] / float(self._Info[Region._info_entries[2]])
                self._Flags[self._region_flags[3]] = True

    def cropRegion(self, start=None, stop=None, changesource=False):
        """Returns a copy of the region with the data within [start, stop] interval
        on 'energy' axis. Interval is given in real units of the data. If start or
        stop or both are not specified the method takes first (or/and last) values.
        If changesource flag is True, the original region is cropped, if False -
        the copy of original region is cropped and returned.
        """
        s = self._Data['energy']
        first_index = 0
        last_index = self._Data.index.values[-1]
        if start:
            for i in s.index:
                if i > 0:
                    if ((s[i - 1] <= start and s[i] >= start) or
                        (s[i - 1] >= start and s[i] <= start)):
                        first_index = i
        if stop:
            for i in s.index:
                if i > 0:
                    if ((s[i - 1] <= stop and s[i] >= stop) or
                        (s[i - 1] >= stop and s[i] <= stop)):
                        last_index = i

        if changesource:
            self._Data = self._Data.truncate(before=first_index, after=last_index)
            # Reset indexing after truncation so that it starts again with 0
            self._Data.reset_index(drop=True, inplace=True)
            return

        tmp_region = copy.deepcopy(self)
        tmp_region._Data = tmp_region._Data.truncate(before=first_index, after=last_index)
        tmp_region._Data.reset_index(drop=True, inplace=True)
        return tmp_region

    def getData(self, column=None):
        """Returns pandas DataFrame with data columns. If column name is
        provided, returns 1D numpy.ndarray of specified column.
        """
        if column:
            return self._Data[column].values
        return self._Data

    def getInfo(self, parameter=None):
        """Returns 'info' dictionary {"name": value} or the value of specified
        parameter.
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
            output = f"No info available for region {self.getID()}"
        else:
            # If no specific arguments provided, add everything to the output
            if len(args) == 0:
                for key, val in self._Info.items():
                    output = "\n".join((output, f"{key}: {val}"))
            else:
                # Add only specified parameters
                for arg in args:
                    output = "\n".join((output, f"{arg}: {self._Info[arg]}"))
        return output

    def getFlags(self):
        """Returns the dictionary of flags
        """
        return self._Flags

    def isEnergyCorrected(self):
        return self._Flags[self._region_flags[0]]

    def isSweepsNormalized(self):
        return self._Flags[self._region_flags[3]]

    def isBinding(self):
        return self._Flags[1]

    def addColumn(self, column_label, array, overwrite=False):
        """Adds one column to the data object assigning it the name 'column_label'.
        Choose descriptive labels. If label already exists but 'overwrite' flag
        is set to True, the method overwrites the data in the column.
        """
        if column_label in self._Data.columns:
            if not overwrite:
                print(f"Column '{column_label}' already exists in {self.getID()}")
                print("Pass overwrite=True to overwrite the existing values.")
        self._Data[column_label] = array

    def addFitter(self, fitter, overwrite=False):
        if self._Fitter and (not overwrite):
            print(f"Region {self.getID()} already has a fitter. Add overwrite=True parameter to overwrite.")
            return
        self._Fitter = fitter

    def getFitter(self):
        if not self._Fitter:
            print(f"Region {self.getID()} doesn't have a fitter.")
            return
        return self._Fitter

    def makeFinalColumn(self, parent_column, overwrite=False):
        """Adds a column with name "final" and populates it with the values
        from the column "parent_column", which is supposed to contain original
        data values corrected by background, normalized etc. It is used then for
        data analysis later on.
        """
        self.addColumn('final', self._Data[parent_column], overwrite)

    def removeColumn(self, column_label):
        """Removes one of the columns of the data object except two main ones:
        'energy' and 'counts'.
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
