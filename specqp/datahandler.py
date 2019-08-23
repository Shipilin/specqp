"""The module provides classes and functions responsible for loading and storing spectroscopy data.
Class Region contains the data for one region.
Class RegionCollection stores a number of Region objects
"""
import os
import ntpath
import logging
import copy
import csv
import pandas as pd
import numpy as np

from specqp import helpers

datahandler_logger = logging.getLogger("specqp.datahandler")  # Creating child logger

DATA_FILE_TYPES = (
    "scienta",
    "specs"
)


def load_scienta_txt(filename, regions_number_line=1, first_region_number=1):
    """Opens and parses provided scienta.txt file returning the data and info for all regions
    as a list of Region objects. Variable 'regions_number_line' gives the
    number of the line in the scienta file where the number of regions is given
    (the line numbering starts with 0 and by default it is the line number 1 that
    contains the information).
    The functions doesn't do any internal checks for file format, file access, file errors etc. and, therefore,
    should be wrapped with error handler when in use.
    """

    def parse_scienta_file_info(lines_):
        """Helper function that parses the list of lines acquired from Scienta.txt
        file info block and returns 'info' dictionary {property: value}
        """
        info = {}
        for line_ in lines_:
            if '=' in line_:
                line_content = line_.strip().split('=', 1)
                # Modify the file name
                if line_content[0].strip() == "File":
                    line_content[1] = ntpath.basename(line_content[1]).split('.', 1)[0]
                info[line_content[0].strip()] = line_content[1].strip()
        return info

    with open(filename) as f:
        lines = f.read().splitlines()

    # Dictionary that contains the map of the file, where the name of the section (specific region) is
    # the key and the lists of first and last indices of Region, Info and Data subsections are the values
    # Example: {"Region 1": [[0, 2], [3, 78], [81, 180]]}
    #                        Region    Info      Data
    file_map = {}
    # Reading the number of regions from the specified line of the file
    regions_number = int(lines[regions_number_line].split("=", 1)[1])
    # We make a list of region objects even for just one region
    regions = []
    # Temporary counter to know the currently treated region number in the for-loop below
    cnt = first_region_number  # (=1 by default)
    # Temporary list variables to store the first and the last indices of the
    # region, the info and the data blocks for every region
    region_indices = []
    info_indices = []
    data_indices = []

    # Parsing algorithm below assumes that the file structure is constant and the blocks follow the sequence:
    # [Region N] - may contain info about add-dimension mode
    # [Info N] - important info
    # [Data N] - data
    for i, line in enumerate(lines):
        if f"[Region {cnt}]" in line:
            region_indices.append(i + 1)
            # If it is not the first region, than the data section of the previous
            # region ends on the previous line
            if cnt > 1:
                data_indices.append(i - 1)
            continue
        if f"[Info {cnt}]" in line:
            info_indices.append(i + 1)
            region_indices.append(i - 1)  # Region section ends on the previous line
            continue
        if f"[Data {cnt}]" in line:
            data_indices.append(i + 1)
            info_indices.append(i - 1)  # Info section ends on the previous line
            # If it is the last region, the current Data section is the last. The last line of the file is the last
            # line of the current Data section. Else, we go to the next region.
            if cnt == regions_number:
                data_indices.append(len(lines) - 1)
                break
            else:
                cnt += 1

    # Resetting region number counter to 1 to start again from the first region and do the mapping procedure
    cnt = first_region_number  # (=1 by default)
    # Iterate through every pair [begin, end] of Region, Info and Data indices to populate the mapping dictionary
    for j in range(1, len(region_indices), 2):
        file_map[f"Region {cnt}"] = [[region_indices[j-1], region_indices[j]],
                                     [info_indices[j-1], info_indices[j]],
                                     [data_indices[j-1], data_indices[j]]]
        cnt += 1

    # Iterating through the mapping dictionary
    for val in file_map.values():
        # Variables which are necessary for the case of add-dimension region
        add_dimension_flag = False
        add_dimension_data = None

        # Region block of the current region
        region_block = lines[val[0][0]:val[0][1] + 1]  # List of lines within [begin, end] indices including end-values
        for line in region_block:
            # If the region is measured in add-dimension mode
            if "Dimension 2 size" in line:
                add_dimension_flag = True
                add_dimension_data = []
                break

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

        region_conditions = {"Comments": info_lines["Comments"]}

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
                # If add-dimension mode is one, there will be a number of columns instead of just two
                # We read them row by row and then transpose the whole thing to get columns
                else:
                    row_counts_values = []
                    # We skip the first value every time because it contains energy which is the same for all columns
                    for ncol in range(1, len(xy)):
                        row_counts_values.append(xy[ncol])
                    counts.append(sum(row_counts_values))  # 'counts' list value contains integrated rows
                    add_dimension_data.append(row_counts_values)

        if add_dimension_data:
            add_dimension_data = list(map(list, zip(*add_dimension_data)))  # Transpose
        # Create a Region object for the current region
        region_id = f"{info_lines_revised[Region.info_entries[7]]} : {info_lines_revised[Region.info_entries[0]]}"
        regions.append(Region(energy, counts, id_=region_id,
                              add_dimension_flag=add_dimension_flag, add_dimension_data=add_dimension_data,
                              info=info_lines_revised, conditions=region_conditions))

    return regions


# TODO: Add possibility to read add_dimension files
def load_specs_xy(filename):
    """Opens and parses provided SPECS file returning the data and info for recorded
    region as a list of Region objects in order to be consistent with the Scienta
    loading routine.
    """
    def parse_spec_file_info(lines_):
        """Parses the list of lines read from SPEC.xy file info block
        and returns 'info' dictionary
        """
        info = {}
        for line_ in lines_:
            if ':' in line_:
                line_ = line_.strip(' #')
                line_content = line_.split(':', 1)
                info[line_content[0].strip()] = line_content[1].strip()

        return info

    with open(filename) as f:
        lines = f.read().splitlines()

    # Basic parsing based on the appearance of SPECS files
    energy, counts = [], []
    info_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue  # Scip empty lines
        elif line.startswith('#'):
            if line.strip(' #'):  # Scip empty info lines
                info_lines.append(line)  # Save info lines
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
            info_lines["Energy Axis"] = "Kinetic"  # To make it consistent with Scienta routine
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

        region_conditions = {"Comments": info_lines["Comment"]}
        # Create a Region object for the current region
        regions.append(Region(energy, counts, info=info_lines_revised, conditions=region_conditions))
    return regions


def load_calibration_curves(filenames):
    """Reads file or files using provided name(s). Checks for file existance etc.
    :param filenames: str or sequence: filepath(s)
    :return:
    """
    calibration_data = {}
    if not type(filenames) == str and not helpers.is_iterable(filenames):
        filenames = [filenames]
    for filename in filenames:
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as f:
                    df = pd.read_csv(f, sep='\t')
                    calibration_data[os.path.basename(filename).rpartition(',')[2]] = \
                        (df['Press_03_value'].to_numpy(), df['Press_05_value'].to_numpy())
            except (IOError, OSError):
                datahandler_logger.error(f"Couldn't access the file: {filename}", exc_info=True)
                continue
    return calibration_data


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
        "Date"                  # 8
    )

    region_flags = (
        "energy_shift_corrected",  # 0
        "binding_energy_flag",     # 1
        "fermi_flag",              # 2
        "sweeps_normalized",       # 3
        "add_dimension_flag"       # 4
    )

    def __init__(self, energy, counts,
                 add_dimension_flag=False, add_dimension_data=None,
                 info=None, conditions=None, excitation_energy=None,
                 id_=None, fermi_flag=False, flags=None):
        """
        :param energy: goes for energy (X) axis
        :param counts: goes for counts (Y) axis
        :param id_: ID of the region (usually the string "filename : regionname")
        :param fermi_flag: True if the region stores the measurement of the Fermi level
        :param add_dimension_flag: True if the region stores two-dimensional data (in this case, the values in the
        'counts' and 'final' columns are obtained by integration over the second dimension. At the same time
        separate columns 'counts0', 'counts1'... and 'final0', 'final1'... are added
        to the region object and contain information for time-distributed scans)
        :param add_dimension_data: list of lists containing separate data for time-distributed scans
        :param info: Info about the region is stored as a dictionary {property: value} based on info_entries tuple
        :param conditions: Experimental conditions are stored as a dictionary {property: value}
        :param excitation_energy: Photon energy used in the experiment
        :param flags: dictionary of flags if already processed data is to be imported to a new Region object
        """
        # The main attribute of the class is pandas dataframe
        self._data = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        self._applied_corrections = []
        self._info = info
        self._id = id_
        # Experimental conditions
        self._conditions = conditions
        # Excitation energy
        if excitation_energy:
            self._excitation_energy = float(excitation_energy)
            self._info[Region.info_entries[3]] = str(float(excitation_energy))
        else:
            self._excitation_energy = None
        if flags and (len(flags) == len(Region.region_flags)):
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
            # take string "FileName : RegionName" as ID
            if not self._id:
                self.set_id(f"{self._info[Region.info_entries[7]]} : {self._info[Region.info_entries[0]]}")
        if Region.region_flags[4] and add_dimension_data:
            self._add_dimension_scans_number = len(add_dimension_data)
            for i, data_set in enumerate(add_dimension_data):
                self.add_column(f'counts{i}', data_set)
                self.add_column(f'final{i}', data_set)
        else:
            self._add_dimension_scans_number = 1

        # 'final' column is the main y-data column for plotting. At the beginning it is identical to the 'counts' values
        self.add_column('final', self._data["counts"])

        # A backup, which can be used to restore the initial state of the region object.
        # If the region is a dummy region that doesn't contain any data, the .copy() action is not available
        try:
            self._data_backup = self._data.copy()
            self._info_backup = self._info.copy()
            self._flags_backup = self._flags.copy()
        except AttributeError:
            datahandler_logger.info(f"A dummy region has been created", exc_info=True)

    def __str__(self):
        """Prints the info read from the data file. Possible to add keys of the Info dictionary to be printed
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
        if column_label in self._data.columns and not overwrite:
            datahandler_logger.warning(f"Column '{column_label}' already exists in {self.get_id()}"
                                       "Pass overwrite=True to overwrite the existing values.")
            return
        self._data[column_label] = array

    def add_correction(self, correction: str):
        self._applied_corrections.append(correction)

    @staticmethod
    def addup_regions(regions, truncate=True):
        """
        Takes two or more non-adddimension regions and combines them in a single region adding up sweeps and results.
        The method checks for regions' energy spans and truncates to the overlapping interval if truncate=True. Skips
        non-matching regions if truncate=False
        NOTE: The method doesn't check for regions compatibility, i.e. conditions, photon energy, etc.
        NOTE: Neither does the method accounts for previously made corrections. Therefore, should be used with
        freshly loaded regions in order to avoid mistakes.
        :param regions: iterable through a number of regions
        :param truncate=True: if regions of different length are combined and truncate == True, the method
        adds them up only in the overlapping region and returns truncated regions as the result
        :return: Region object
        """

        def _find_overlap(a, b):
            ab_intersect = np.in1d(a, b).nonzero()[0]
            ba_intersect = np.in1d(b, a).nonzero()[0]
            if len(ab_intersect) == 0 or len(ba_intersect) == 0:
                return None, None
            return [ab_intersect[0], ab_intersect[-1]], [ba_intersect[0], ba_intersect[-1]]

        if not helpers.is_iterable(regions):
            datahandler_logger.warning(f"Regions should be in an iterable object to be concatenated")
            return None
        region = copy.deepcopy(regions[0])
        for i in range(1, len(regions)):
            energy1 = region.get_data('energy')
            energy2 = regions[i].get_data('energy')
            # Check that the regions can be concatenated, i.e. if they have full/partial overlap
            indxs1, indxs2 = _find_overlap(energy1, energy2)
            if (not indxs1) or (not indxs2):
                continue
            if indxs1 == indxs2 and len(energy1) == len(energy2):  # If regions fully overlap
                region._data['counts'] += regions[i].get_data('counts')
                region._data['final'] += regions[i].get_data('final')
            elif indxs1 != indxs2 and truncate:
                if not (indxs1[0] == 0 and indxs1[1] == len(energy1) + 1):
                    region.crop_region(start=energy1[indxs1[0]], stop=energy1[indxs1[1]], changesource=True)
                region._data['counts'] += regions[i].get_data('counts')[indxs2[0]:indxs2[1]]
                region._data['final'] += regions[i].get_data('final')[indxs2[0]:indxs2[1]]
            else:
                datahandler_logger.warning(f"Regions {region.getid()} and {regions[i].get_id()} have different length")
                continue
            region._info[Region.info_entries[2]] = str(int(region.get_info(Region.info_entries[2])) +
                                                       int(regions[i].get_info(Region.info_entries[2])))
        return region

    def correct_energy_shift(self, shift):
        if not self._flags[Region.region_flags[0]]:  # If not already corrected
            self._data['energy'] += shift
            self._flags[Region.region_flags[0]] = True
            self._applied_corrections.append("Energy shift corrected")
        else:
            datahandler_logger.info(f"The region {self._id} has already been energy corrected.")

    def crop_region(self, start=None, stop=None, changesource=False):
        """Returns a copy of the region with the data within [start, stop] interval
        on 'energy' x-axis. Interval is given in real units of the data. If start or
        stop or both are not specified the method takes first (or/and last) values.
        If changesource flag is True, the original region is cropped, if False -
        the copy of original region is cropped and returned.
        """
        if start is None and stop is None:
            return

        x_values = self._data['energy']
        if start is not None and stop is not None:
            if (x_values.iloc[0] > x_values.iloc[-1] and start < stop) or (x_values.iloc[-0] < x_values.iloc[-1] and start > stop):
                start, stop = stop, start

        first_index = 0
        last_index = self._data.index.values[-1]
        if start is not None:
            for i in x_values.index:
                if i > 0:
                    if (x_values[i - 1] <= start <= x_values[i]) or (x_values[i - 1] >= start >= x_values[i]):
                        first_index = i
        if stop is not None:
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
        if self._conditions:
            if entry:
                return self._conditions[entry]
            return self._conditions
        else:
            datahandler_logger.warning(f"The region {self._id} doesn't contain information about conditions.")

    def get_corrections(self, as_string=False):
        """Returns either the list or the string (if as_string=True) of corrections that has been applied to the region
        """
        if not as_string:
            return self._applied_corrections
        else:
            if not self._applied_corrections:
                return "Not corrected"
            else:
                output = ""
                for cor in self._applied_corrections:
                    if not output:
                        output = "".join([output, cor])
                    else:
                        output = "; ".join([output, cor])
                return output

    def get_data(self, column=None):
        """Returns pandas DataFrame with data columns. If column name is
        provided, returns 1D numpy.ndarray of specified column.
        """
        if column:
            return self._data[column].to_numpy()
        return self._data

    def get_data_columns(self, add_dimension=True) -> list:
        # If we want to get all add_dimension columns or the region is not add_dimension, return all columns
        if add_dimension or not self._flags[self.region_flags[4]]:
            return self._data.columns.to_list()
        else:
            # Return only main columns, the ones that don't contain digits
            cols = [col for col in self._data.columns if not any([char.isdigit() for char in col])]
            return cols

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

    def get_info_string(self, include_conditions=True, *args):
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
                if include_conditions:
                    for key, val in self._conditions.items():
                        output = "\n".join((output, f"{key}: {val}"))
            else:
                # Add only specified parameters
                for arg in args:
                    if arg in self._info:
                        output = "\n".join((output, f"{arg}: {self._info[arg]}"))
                    elif include_conditions and arg in self._conditions:
                        output = "\n".join((output, f"{arg}: {self._conditions[arg]}"))
                    else:
                        datahandler_logger.warning(f"Parameter {arg} is not known for region {self._id}")
        return output

    def invert_energy_scale(self):
        """Changes the energy scale of the region from the currently defined to
        the alternative one. From kinetic to binding energy or from binding to kinetic energy.
        """
        self._data['energy'] = -1 * self._data['energy'] + self._excitation_energy
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

    def is_dummy(self):
        if len(self._data['energy']) == 0:
            return True
        return False

    def is_energy_corrected(self):
        return self._flags[self.region_flags[0]]

    def is_sweeps_normalized(self):
        return self._flags[self.region_flags[3]]

    def is_binding(self):
        return self._flags[self.region_flags[1]]

    def make_final_column(self, parent_column, overwrite=False):
        """Populates the 'final' column with the values from the column "parent_column", which contains processed data.
        Populates all 'finalN' columns with values from 'parent_columnN' for add_dimension regions.
        """
        self.add_column('final', self._data[parent_column], overwrite)
        if self.is_add_dimension():
            for i in range(self._add_dimension_scans_number):
                if f'{parent_column}{i}' in list(self._data):
                    self.add_column(f'final{i}', self._data[f'{parent_column}{i}'], overwrite)

    def normalize_by_sweeps(self, column='final'):
        """
        Normalizes 'column' column by sweeps and stores the result in the new column 'sweepsNormalized'.
        For add_dimension regions normalizes all columns 'columnN' and creates new columns 'sweepsNormalizedN'
        NOTE: The routine also takes into account the dwell time per point
        :return:
        """
        # If not yet normalized by sweeps
        if not self._flags[self.region_flags[3]]:
            if self._info and (Region.info_entries[2] in self._info):
                if not self._flags[self.region_flags[4]]:
                    self._data['sweepsNormalized'] = self._data[column] / (float(self._info[Region.info_entries[2]]) *
                                                                           float(self._info[Region.info_entries[6]]))
                else:
                    # This many sweeps in each add_dimension measurement
                    sweeps_per_set = self._info[Region.info_entries[2]]
                    for i in range(self._add_dimension_scans_number):
                        if f'{column}{i}' in self._data.columns:
                            self._data[f'sweepsNormalized{i}'] = (self._data[f'{column}{i}'] /
                                                                  (float(sweeps_per_set) *
                                                                   float(self._info[Region.info_entries[6]])))
                    self._data['sweepsNormalized'] = (self._data[column] /
                                                      (float(int(sweeps_per_set) * self._add_dimension_scans_number) *
                                                       float(self._info[Region.info_entries[6]])))
                self._flags[self.region_flags[3]] = True
                return True
        return False

    @staticmethod
    def read_csv(filename):
        """Reads csv file and returns Region object. Values of flags and info
        is retrieved from the comment lines marked with '#' simbol at the beginning
        of the file.
        """
        try:
            with open(filename, 'r') as region_file:
                data_start = False
                flags = {}
                info = {}
                conditions = {}
                _id = None
                _scans_cnt = 1
                applied_c = []
                while not data_start:
                    line = region_file.readline()
                    if line.strip() == "[DATA]":
                        data_start = True
                        continue
                    elif '#ID' in line:
                        _id = line.replace("#ID", "").strip()
                    elif '#AD' in line:
                        _scans_cnt = int(line.replace("#AD", "").strip())
                    elif '#F' in line:
                        key, _, val = line.replace("#F", "").strip().partition("=")
                        flags[key] = val
                    elif '#I' in line:
                        key, _, val = line.replace("#I", "").strip().partition("=")
                        info[key] = val
                    elif '#C' in line:
                        key, _, val = line.replace("#C", "").strip().partition("=")
                        conditions[key] = val
                    elif "#AC":
                        applied_c = line.replace("#AC", "").strip().split(';')
                        applied_c = [ac.strip() for ac in applied_c]
                data = pd.read_csv(region_file, sep='\t')

                region = Region([], [], info=info, excitation_energy=float(info[Region.info_entries[3]]), conditions=conditions, id_=_id, flags=flags)
                region._data = data
                region._add_dimension_scans_number = _scans_cnt
                region._applied_corrections = applied_c
                region._data_backup = data.copy()
                region._info_backup = info.copy()
                region._flags_backup = flags.copy()
                return region
        except (IOError, OSError):
            datahandler_logger.warning(f"Can't access the file {filename}", exc_info=True)
            return False

    def reset_region(self):
        """Removes all the changes made to the Region and restores the initial
        "counts" and "energy" columns together with the _info, _flags
        """
        if self._data_backup and self._info_backup and self._flags_backup:
            self._data = self._data_backup.copy()
            self._info = self._info_backup.copy()
            self._flags = self._flags_backup.copy()
            self._applied_corrections = []
        else:
            datahandler_logger.warning("Attempt to reset a dummy region. Option is not available for dummy regions.")

    def save_xy(self, file, cols='final', add_dimension=True, headers=True):
        """Saves Region object as csv file with 'energy' and other specified columns. If add_dimension region
        is provided and 'add_dimension' variable is True, saves 'energy' column and specified columns for all sweeps.
        :param cols: Sequence, String, 'all'. Which columns of the Region dataframe to save along with the energy column
        :param add_dimension: Saves all relevant columns for all sweeps of add_dimension region
        :param file: File handle
        :param headers: Include the columns headers in the file
        :return: True if successful, False otherwise
        """
        if cols == 'all':
            cols = self.get_data_columns(add_dimension)
        else:
            if not (type(cols) != str and helpers.is_iterable(cols)):
                cols = [cols]
            else:
                cols = list(cols)  # Convert possible sequences to list
            # Check if columns exist in self._data and report the missing columns
            missing_cols = cols.copy()
            cols = [c for c in cols if c in self._data.columns]
            missing_cols = list(set(missing_cols) - set(cols))
            for mc in missing_cols:
                datahandler_logger.warning(f"Can't save column '{mc}' in region {self._id}.")
            # If the region is add-dimension and we want to save it as add_dimension -> save all relevant columns
            if self._flags[self.region_flags[4]] and add_dimension:
                add_dimension_cols = []
                for col in cols:
                    add_dimension_cols += [c for c in self._data.columns if col in c]
                cols = add_dimension_cols
            if 'energy' not in cols:
                cols = ['energy'] + cols

        try:
            self._data[cols].round(2).to_csv(file, header=headers, index=False, sep='\t')
        except (OSError, IOError):
            datahandler_logger.error(f"Can't write the file {file.name}", exc_info=True)
            return False
        print(f"Created: {file.name}")
        return True

    def save_as_file(self, file, cols='all', add_dimension=True, details=True, headers=True):
        """Saves Region object as csv file with all columns. If details==True, saves also info, conditions and
        :param details: Bool
        :param file: File handle
        :param cols: Which columns to write to file
        :param add_dimension: If True, saves data for all sweeps, if False, saves only main columns
        :param headers: Include the columns headers in the file
        :return: True if successful, False otherwise
        """
        if not details:
            if not self.save_xy(file, cols=cols, add_dimension=add_dimension, headers=headers):
                return False
        else:
            try:
                file.write(f"#ID {self._id}\n")
                if self.is_add_dimension():
                    file.write(f"#AD {self._add_dimension_scans_number}\n")
                for key, value in self._flags.items():
                    file.write(f"#F {key}={value}\n")
                for key, value in self._info.items():
                    file.write(f"#I {key}={value}\n")
                for key, value in self._conditions.items():
                    file.write(f"#C {key}={value}\n")
                file.write(f"#AC {self.get_corrections(as_string=True)}\n")
                file.write("[DATA]\n")
            except (OSError, IOError):
                datahandler_logger.error(f"Can't write the file {file.name}", exc_info=True, sep='\t')
                return False
            if not self.save_xy(file, cols=cols, add_dimension=add_dimension, headers=headers):
                return False
        return True

    def set_conditions(self, conditions, overwrite=False):
        """Set experimental conditions as a dictionary {"Property": Value}. If conditions with the same names
        already exist will skip/overwrite depending on the overwrite value.
        """
        # If some conditions already exist
        if self._conditions:
            for key, val in conditions.items():
                if key in self._conditions and not overwrite:
                    continue
                self._conditions[key] = val
        else:
            self._conditions = conditions

    def set_excitation_energy(self, excitation_energy):
        """Set regions's excitation energy.
        """
        self._excitation_energy = float(excitation_energy)
        self._info[Region.info_entries[3]] = str(float(excitation_energy))

    def set_id(self, region_id):
        self._id = region_id

    def set_fermi_flag(self):
        self._flags[Region.region_flags[2]] = True


class RegionsCollection:
    """Keeps track of the list of regions being in work simultaneously in the GUI or the batch mode
    """
    def __init__(self, regions=None):
        """
        :param regions: List of region objects (can be also single object in the list form, e.g. [obj,])
        """
        self.regions = {}
        if regions:
            for region in regions:
                self.regions[region.get_id()] = region

    def add_regions(self, new_regions):
        """Adds region objects. Checks for duplicates and rejects adding if already exists.
        :param new_regions: List of region objects (can be also single object in the list form, e.g. [obj,])
        :return: list of IDs for regions that were added
        """
        ids = []
        duplicate_ids = []  # For information purposes
        for new_region in new_regions:
            new_id = new_region.get_id()
            if self.is_duplicate(new_id):
                duplicate_ids.append(new_id)
                continue
            else:
                ids.append(new_id)
                self.regions[new_id] = new_region
        if duplicate_ids:
            datahandler_logger.warning(f"Regions are already loaded: {duplicate_ids}")
        if ids:
            return ids

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
        if not type(region_id) == str and helpers.is_iterable(region_id):  # Return multiple regions
            return [self.regions[reg_id] for reg_id in region_id if reg_id in self.regions]
        else:
            if region_id in self.regions:
                return self.regions[region_id]

    def get_regions(self):
        return self.regions.values()

    def is_duplicate(self, id_):
        if id_ in self.regions:
            return True
        else:
            return False
