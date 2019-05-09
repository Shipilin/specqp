"""The module contains classes and functions responsible
for loading and storing spectroscopy data. It also provides
general handles for the outside modules and scripts.

The hierarchy of objects is as follows:
1. Class Experiment contains all data for an executed experiment.
Usually it should contain one uninterrupted set of measurements
for one sample.
2. Class SetOfSpectra contains a number of regions measured under the same
conditions. Usually a few regions including Fermi edge measurement.
3. Class Spectrum contains a single spectrum with possibly several
regions.
4. Class AddDimensionSpectrum is on the same hierarchical level with
the class Spectrum, but is dedicated to "add dimension" measurements
where the same spectrum is taken a number of times in a row under
changing conditions or such.
5. Class Region contains the data for one region.
"""
import os
import logging
import copy
import pandas as pd


datahandler_logger = logging.getLogger("specqp.datahandler")  # Creating child logger

DATA_FILE_TYPES = (
    "scienta",
    "specs"
)


def ask_path(folder_flag=True, multiple_files_flag=False):
    """Makes a tkinter dialog for choosing the folder if folder_flag=True
    or file(s) otherwise. For multiple files the multiple_files_flag should
    be True.
    """
    # This method is almost never used, so the required imports are locally called
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    path = os.getcwd()
    if folder_flag: # Open folder
        path = filedialog.askdirectory(parent=root, initialdir=path, title='Please select experiment directory')
    else: # Open file
        if multiple_files_flag:
            path = filedialog.askopenfilenames(parent=root, initialdir=path, title='Please select data files')
            path = root.tk.splitlist(path)
        else:
            path = filedialog.askopenfilename(parent=root, initialdir=path, title='Please select data file')
    root.destroy()
    return path


# TODO: Add error raising for the case when a file with a wrong type is passed
def load_scienta_txt(filename, regions_number_line=1):
    """Opens and parses provided scienta file returning the data and info for all regions
    as a list of Region objects. Variable 'regions_number_line' gives the
    number of the line in the scienta file where the number of regions is given
    (the line numbering starts with 0 and by default it is the line number 1 that
    contains the information).
    """
    # Info block parsing routine
    def parse_scienta_file_info(lines):
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

    # Dictionary that contains the map of the file, where the name of the section (specific region) is
    # the key and the lists of first and last indices of Region, Info and Data subsections are the values
    # Example: {"Region 1": [[0, 2], [3, 78], [81, 180]]}
    #                        Region    Info      Data
    file_map = {}

    # The number of regions is given in the second line of the file
    regions_number = int(lines[regions_number_line].split("=")[1])
    # We make a list of scan objects even for just one region
    regions = []

    # Temporary counter to know the currently treated region number in the
    # for-loop below
    cnt = 1
    # Temporary list variables to store the first and the last indices of the
    # region, the info and the data blocks for every region
    region_indices = []
    info_indices = []
    data_indices = []

    # Parsing algorithm below assumes that the file structure is constant and
    # the blocks follow the sequence:
    # [Region N] - may contain info about add-dimension mode
    # [Info N] - important info
    # [Data N] - data
    for i, line in enumerate(lines):
        if f"[Region {cnt}]" in line:
            # If it is not the first region, than the data section of the previous
            # region ends on the previous line
            region_indices.append(i+1)
            if cnt > 1:
                data_indices.append(i-1)
            continue
        if f"[Info {cnt}]" in line:
            region_indices.append(i-1)
            info_indices.append(i+1)
            continue
        if f"[Data {cnt}]" in line:
            info_indices.append(i-1)
            data_indices.append(i+1)
            if cnt == regions_number:
                data_indices.append(len(lines)-1)
                break
            else:
                cnt += 1

    # Resetting region number counter to 1 to start again from the first region
    # and do the mapping procedure
    cnt = 1
    for j in range(1, len(region_indices), 2):
        file_map[f"Region {cnt}"] = [[region_indices[j-1], region_indices[j]],
                                     [info_indices[j-1], info_indices[j]],
                                     [data_indices[j-1], data_indices[j]]]
        cnt += 1

    # Iterating through regions
    for val in file_map.values():

        # Variables which are necessary for the case of add-dimension region
        add_dimension_flag = False
        add_dimension_data = None

        # Region block of the current region
        region_block = lines[val[0][0]:val[0][1] + 1]
        for line in region_block:
            # If the region is measured in add-dimension mode
            if "Dimension 2 size" in line:
                add_dimension_flag = True
                add_dimension_data = []

        # Info block of the current region
        info_lines = parse_scienta_file_info(lines[val[1][0]:val[1][1]+1])
        # Not all info entries are important for data analysis,
        # Choose only important ones
        info_lines_revised = {Region.info_entries[0]: info_lines["Region Name"],
                              Region.info_entries[1]: info_lines["Pass Energy"],
                              Region.info_entries[2]: info_lines["Number of Sweeps"],
                              Region.info_entries[3]: info_lines["Excitation Energy"],
                              Region.info_entries[4]: info_lines["Energy Scale"],
                              Region.info_entries[5]: info_lines["Energy Step"],
                              Region.info_entries[6]: info_lines["Step Time"],
                              Region.info_entries[7]: info_lines["File"],
                              Region.info_entries[8]: f"{info_lines['Date']} {info_lines['Time']}"}

        # Data block of the current region
        data_block = lines[val[2][0]:val[2][1]+1]
        energy, counts = [], []
        for i, line in enumerate(data_block):
            if not line.strip():
                continue  # Skip empty lines
            else:
                xy = list(map(float, line.split()))
                energy.append(xy[0])
                if not add_dimension_flag:
                    counts.append(xy[1])
                # If add-dimension mode
                else:
                    row_counts_values = []
                    for ncol in range(1, len(xy)):
                        row_counts_values.append(xy[ncol])
                    counts.append(sum(row_counts_values))
                    add_dimension_data.append(row_counts_values)

        if add_dimension_data:
            add_dimension_data = list(map(list, zip(*add_dimension_data)))
        # Create a Region object for the current region
        regions.append(Region(energy, counts, add_dimension_flag=add_dimension_flag,
                              add_dimension_data=add_dimension_data, info=info_lines_revised))

    return regions


# TODO: Add error raising for the case when a file with a wrong type is passed
def load_specs_xy(filename):
    """Opens and parses provided SPECS file returning the data and info for recorded
    region as a list of Region objects in order to be consistent with the Scienta
    loading routine.
    """
    def parse_spec_file_info(lines):
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
        info_lines = parse_spec_file_info(info_lines)

        # Check which energy scale is used:
        if info_lines["Energy Axis"] == "Kinetic Energy":
            info_lines["Energy Axis"] = "Kinetic" # To make it consistent with scienta
        else:
            info_lines["Energy Axis"] = "Binding"

        # Not all info entries are important for data analysis,
        # Choose only important ones
        info_lines_revised = {Region.info_entries[0]: info_lines["Region"],
                              Region.info_entries[1]: info_lines["Pass Energy"],
                              Region.info_entries[2]: info_lines["Number of Scans"],
                              Region.info_entries[3]: info_lines["Excitation Energy"],
                              Region.info_entries[4]: info_lines["Energy Axis"],
                              Region.info_entries[5]: str(abs(energy[-1] - energy[0]) / int(info_lines["Values/Curve"])),
                              Region.info_entries[6]: info_lines["Dwell Time"],
                              Region.info_entries[7]: filename.rpartition('.')[0].rpartition('/')[2],
                              Region.info_entries[8]: info_lines["Acquisition Date"]}

        # Create a Region object for the current region
        regions.append(Region(energy, counts, info=info_lines_revised))
    return regions


# TODO change the structure of file
def save_csv(region, filename):
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
        region.get_data().to_csv(file, index=False)


# TODO rewrite
def read_csv(filename):
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
            for flag in Region.region_flags:
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
                    energy_shift_corrected=flags[Region.region_flags[0]],
                    binding_energy_flag=flags[Region.region_flags[1]],
                    info=info)

    return region


class Region:
    """Class Region contains the data and info for one measured region, e.g. C1s
    """
    info_entries = (
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

    region_flags = (
        "energy_shift_corrected",  # 0
        "binding_energy_flag",     # 1
        "fermi_flag",              # 2
        "sweeps_normalized",       # 3
        "add_dimension_flag"       # 4
    )

    def __init__(self, energy, counts, id=None, fermi_flag=False, add_dimension_flag=False, add_dimension_data=None,
                 info=None, conditions=None, excitation_energy=None, flags=None):
        """
        :param energy: goes for energy (X) axis
        :param counts: goes for counts (Y) axis
        :param id: ID of the region (usually the string "filename:regionname")
        :param fermi_flag: True if the region stores the measurement of the Fermi level
        :param add_dimension_flag: True if the region stores two-dimensional data (in such case, the values in the
        'counts' column are obtained by integration aver the second dimension and separate columns 'counts1', 'counts2'
        etc. are added to the region object and contain separate information for sweeps)
        :param add_dimension_data: list of iterables containing separate data for sweeps in the second dimension
        :param info: Info about the region is stored as a dictionary {property: value} based on info_entries tuple
        :param conditions: Experimental conditions are stored as a dictionary {property: value}
        :param excitation_energy: Photon energy used in the experiment
        :param flags: dictionary of flags if already processed data is to be imported to a new Region object
        """

        # The main attribute of the class is pandas dataframe
        self._data = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        self._add_dimension_scans_number = 1
        self._info = info
        self._id = id
        # Experimental conditions
        self._conditions = conditions
        # Excitation energy
        self._excitation_energy = excitation_energy
        if flags and len(flags) == len(Region.region_flags):
            self._flags = flags
        else:
            if flags:
                datahandler_logger.warning("Incorrect dictionary of flags when creating a region object")
            # Default values for flags
            self._flags = {
                    Region.region_flags[0]: False,
                    Region.region_flags[1]: None,
                    Region.region_flags[2]: fermi_flag,
                    Region.region_flags[3]: False,
                    Region.region_flags[4]: add_dimension_flag
                    }
        # Check which energy scale is used:
        if self._info:  # Info can be None
            if self._info[Region.info_entries[4]] == "Binding":
                self._flags[Region.region_flags[1]] = True
            else:
                self._flags[Region.region_flags[1]] = False
            # If info is available for the region and the ID is not assigned,
            # take string 'FileName:RegionName' as ID
            if not self._id:
                self.set_id(f"{self._info[Region.info_entries[7]]} : {self._info[Region.info_entries[0]]}")
        if Region.region_flags[4] and add_dimension_data:
            self._add_dimension_scans_number = len(add_dimension_data)
            for i, data_set in enumerate(add_dimension_data):
                self.add_column(f'counts{i}', data_set)
        # 'final' column is the main y-data column for plotting. At the beginning it is identical with the raw counts
        self.add_column('final', self._data["counts"])

        # A backup, which can be used to restore the initial state of the region object.
        self._data_backup = self._data
        self._info_backup = self._info
        self._flags_backup = self._flags

    def __str__(self):
        """Prints the info read from the data file
        Possible to add keys of the Info dictionary to be printed
        """
        return self.get_info_string()

    # TODO: write region subtraction routine
    def __sub__(self, other_region):
        """Returns the difference of the "final" column of two instances
        """
        return self._data["final"] - other_region.get_data("final")

    def add_column(self, column_label, array, overwrite=False):
        """Adds one column to the data object assigning it the name 'column_label'.
        Choose descriptive labels. If label already exists but 'overwrite' flag
        is set to True, the method overwrites the data in the column.
        """
        if column_label in self._data.columns:
            if not overwrite:
                datahandler_logger.warning(f"Column '{column_label}' already exists in {self.get_id()}"
                                           "Pass overwrite=True to overwrite the existing values.")
                return
        self._data[column_label] = array

    def correct_energy_shift(self, shift):
        if not self._flags[Region.region_flags[0]]:
            self._data['energy'] += shift
            self._flags[Region.region_flags[0]] = True
        else:
            datahandler_logger.info(f"The region {self.get_id()} has already been energy corrected.")

    def crop_region(self, start=None, stop=None, changesource=False):
        """Returns a copy of the region with the data within [start, stop] interval
        on 'energy' x-axis. Interval is given in real units of the data. If start or
        stop or both are not specified the method takes first (or/and last) values.
        If changesource flag is True, the original region is cropped, if False -
        the copy of original region is cropped and returned.
        """
        x_values = self._data['energy']
        first_index = 0
        last_index = self._data.index.values[-1]
        if start:
            for i in x_values.index:
                if i > 0:
                    if (x_values[i - 1] <= start <= x_values[i]) or (x_values[i - 1] >= start >= x_values[i]):
                        first_index = i
        if stop:
            for i in x_values.index:
                if i > 0:
                    if (x_values[i - 1] <= stop <= x_values[i]) or (x_values[i - 1] >= stop >= x_values[i]):
                        last_index = i

        if changesource:
            self._data = self._data.truncate(before=first_index, after=last_index)
            # Reset indexing after truncation so that it starts again with 0
            self._data.reset_index(drop=True, inplace=True)
            return

        tmp_region = copy.deepcopy(self)
        tmp_region._data = tmp_region._data.truncate(before=first_index, after=last_index)
        tmp_region._data.reset_index(drop=True, inplace=True)
        return tmp_region

    def get_add_dimension_counter(self):
        """
        :return: Number of separate scans in add-dimension region
        """
        return self._add_dimension_scans_number

    def get_conditions(self, entry=None):
        """Returns experimental conditions as a dictionary {"entry": value} or
        the value of the specified entry.
        """
        if entry:
            return self._conditions[entry]
        return self._conditions

    def get_data(self, column=None):
        """Returns pandas DataFrame with data columns. If column name is
        provided, returns 1D numpy.ndarray of specified column.
        """
        if column:
            return self._data[column].to_numpy()
        return self._data

    def get_excitation_energy(self):
        return self._excitation_energy

    def get_flags(self):
        """Returns the dictionary of flags
        """
        return self._flags

    def get_id(self):
        return self._id

    def get_info(self, parameter=None):
        """Returns 'info' dictionary {"name": value} or the value of specified
        parameter.
        """
        if parameter:
            return self._info[parameter]
        return self._info

    def get_info_string(self, *args):
        """Returns info string with the information about the region
        Possible to add keys of the Info dictionary to be printed
        """
        output = ""
        if not self._info:
            output = f"No info available for region {self.get_id()}"
        else:
            # If no specific arguments provided, add everything to the output
            if len(args) == 0:
                for key, val in self._info.items():
                    output = "\n".join((output, f"{key}: {val}"))
            else:
                # Add only specified parameters
                for arg in args:
                    if arg in self._info:
                        output = "\n".join((output, f"{arg}: {self._info[arg]}"))
                    else:
                        datahandler_logger.warning(f"Parameter {arg} is not known for region {self._id}")
        return output

    def invert_energy_scale(self):
        """Changes the energy scale of the region from the currently defined to
        the alternative one. From kinetic to binding energy
        or from binding to kinetic energy.
        """
        self._data['energy'] = [(self._excitation_energy - value) for value in self._data['energy']]
        self._flags[Region.region_flags[1]] = not self._flags[Region.region_flags[1]]

        # We need to change "Energy Scale" info entry also
        if self._flags[Region.region_flags[1]]:
            self._info[Region.info_entries[4]] = "Binding"
        else:
            self._info[Region.info_entries[4]] = "Kinetic"

    def invert_to_binding(self):
        """Changes the energy scale of the region from kinetic to binding energy.
        """
        if not self._flags[Region.region_flags[1]]:
            self.invert_energy_scale()

    def invert_to_kinetic(self):
        """Changes the energy scale of the region from binding to kinetic energy.
        """
        if self._flags[Region.region_flags[1]]:
            self.invert_energy_scale()

    def is_add_dimension(self):
        return self._flags[self.region_flags[4]]

    def is_energy_corrected(self):
        return self._flags[self.region_flags[0]]

    def is_sweeps_normalized(self):
        return self._flags[self.region_flags[3]]

    def is_binding(self):
        return self._flags[1]

    def make_final_column(self, parent_column, overwrite=False):
        """Populates the 'final' column with the values from the column "parent_column", which contains processed data.
        """
        self.add_column('final', self._data[parent_column], overwrite)

    def normalize_by_sweeps(self):
        # If not yet normalized
        if not self._flags[self.region_flags[3]]:
            if self._info and (Region.info_entries[2] in self._info):
                if not self._flags[self.region_flags[4]]:
                    self._data['counts'] = self._data['counts'] / float(self._info[Region.info_entries[2]])
                else:
                    cnt = 0
                    n_sweeps = self._info[Region.info_entries[2]]
                    while True:
                        column_label = f'counts{cnt}'
                        if column_label in self._data.columns:
                            self._data[column_label] = self._data[column_label] / float(n_sweeps)
                            cnt += 1
                        else:
                            break
                    self._data['counts'] = self._data['counts'] / float(n_sweeps * cnt)
                self._flags[self.region_flags[3]] = True

    def remove_column(self, column_label):
        """Removes one of the columns of the data object except two main ones:
        'energy' and 'counts'.
        """
        # We don't want to remove basic data columns, which are 'energy', 'counts' and 'final'
        # For add dimension regions we also don't want to remove separate sweeps 'counts1', 'counts2' etc.
        if (column_label == 'energy') or ('counts' in column_label) or (column_label == 'final'):
            datahandler_logger.warning("Basic data columns can't be removed!")
            return
        self._data = self._data.drop(column_label, 1)

    def reset_region(self):
        """Removes all the changes made to the Region and restores the initial
        "counts" and "energy" columns together with the _info, _flags
        """
        self._data = self._data_backup
        self._info = self._info_backup
        self._flags = self._flags_backup

    def set_conditions(self, conditions):
        """Set experimental conditions as a dictionary {"Property": Value}
        """
        self._conditions = conditions

    def set_excitation_energy(self, excitation_energy):
        """Set regions's excitation energy.
        """
        self._excitation_energy = excitation_energy
        self._info[Region.info_entries[3]] = str(excitation_energy)

    def set_id(self, region_id):
        self._id = region_id

    def set_fermi_flag(self):
        self._flags[Region.region_flags[2]] = True


class RegionsCollection:
    """Keeps track of the list of regions being in work simultaneously in the GUI or the batch mode
    """
    def __init__(self):
        self.regions = {}

    def add_regions(self, list_of_new_regions):
        """Adds region objects. Checks for duplicates and rejects adding if already exists.
        :param list_of_new_regions: List of region objects (can be also single object in the list form, e.g. [obj,])
        :return: list of IDs for regions that were added
        """
        ids = []
        duplicate_ids = []  # For information purposes
        for i, new_region in enumerate(list_of_new_regions):
            new_id = new_region.get_id()
            if self.is_duplicate(new_id):
                duplicate_ids.append(new_id)
                continue
            else:
                ids.append(new_id)
                self.regions[ids[i]] = new_region
        if duplicate_ids:
            datahandler_logger.warning(f"Regions already loaded to the collection in work: {duplicate_ids}")
        if ids:
            return ids

        return None

    def add_regions_from_file(self, file_path, file_type=DATA_FILE_TYPES[0]):
        """Adds region objects after extracting them from the file.
        Checks for duplicates and rejects adding if already exists.
        :param file_path: Absolute path to the data file from which the regions shall be extracted
        :param file_type: File type to be processed
        :return: list of IDs for regions loaded from the file
        """
        ids = []
        try:
            if file_type == DATA_FILE_TYPES[0]:
                ids = self.add_regions(load_scienta_txt(file_path))
            elif file_type == DATA_FILE_TYPES[1]:
                ids = self.add_regions(load_specs_xy(file_path))
        except OSError:
            datahandler_logger.error(f"Couldn't access the file {file_path}", exc_info=True)
            return None
        except UnicodeDecodeError:
            datahandler_logger.error(f"Couldn't decode the file {file_path}", exc_info=True)
            return None
        except ValueError:
            datahandler_logger.error(f"The file {file_path} has unexpected characters", exc_info=True)
            return None
        except Exception:
            datahandler_logger.error(f"The file {file_path} is corrupted", exc_info=True)
            return None

        return ids

    def get_ids(self):
        """Returns the list of IDs for regions in RegionCollection object
        :return: list of IDs
        """
        return list(self.regions.keys())

    def get_by_id(self, region_id):
        if region_id in self.regions:
            return self.regions[region_id]

    def is_duplicate(self, id):
        if id in self.regions:
            return True
        else:
            return False