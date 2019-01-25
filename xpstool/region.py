import os
from matplotlib import pyplot as plt
import pandas as pd

class Region:
    """Contains and handles a single recorded region together with all information
    about the scan and experimental conditions provided in data file
    """
    _region_flags = (
            "energy_shift_corrected",
            "binding_energy_flag",
            "fermi_level_flag"
            )

    def __init__(self, energy, counts, energy_shift_corrected=False, binding_energy_flag=False,
                 fermi_level_flag=False, info=None):
        """Creates the class using two variables (of type list or similar).
        The first goes for energy (X) axis, the second - for counts (Y) axis.
        The 'energy_shift_corrected' flag shows whether the energy values were
        corrected (using Fermi level, gas peak, etc.)
        The 'binding_energy_flag' defines which energy representation is used
        (binding (True) or kinetic (False)). Fermi_flag should be True if the spectrum
        represents the Fermi level measurement. Experimental conditions can be passed
        as 'info' dictionary {"name": value} and stored in the instance.
        """

        # The main attribute of the class is pandas dataframe
        self._Data = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)
        self._Flags = {
                Region._region_flags[0]: energy_shift_corrected,
                Region._region_flags[1]: binding_energy_flag,
                Region._region_flags[2]: fermi_level_flag
                }
        self._Info = info
        # Special info entry that allows for adding information about measurements
        # conditions in the future. For example {"Temperature": "250 C"}
        self._Info["Conditions"] = {}
        # This is a dataframe identical to _Data at the beginning. It works as as
        # a storage of Raw data, which can be used to restore the initial state of
        # the region data in case of cropping or similar
        self._Raw = pd.DataFrame(data={'energy': energy, 'counts': counts}, dtype=float)

    def __str__(self):
        """Prints the info read from the Scienta file
        Possible to add keys of the Info dictionary to be printed
        """
        output = ""
        if not self._Info:
            output = "No info available"
        else:
            for key, val in self._Info.items():
                output = "\n".join((output, f"{key}: {val}"))
        return output

    def addConditionsEntry(self, entry_name, entry_value):
        """Adding a dictionary entry to the region. For example "Temperature", "250 C"
        """
        self._Info["Conditions"]= {entry_name: entry_value}

    def resetRegion(self):
        """Removes all the changes made to the Region and restores the initial
        "counts" and "energy" columns
        """
        self._Data = self._Raw

    def plotRegion(self, figure=1, ax=None, invert_x=True, x_data="energy", y_data="counts", scatter=False, label=None, color=None):
        """Plotting spectrum with pyplot using given plt.figure and a number of optional arguments
        """
        x = self._Data[x_data].values
        y = self._Data[y_data].values

        plt.figure(figure)
        if not ax:
            ax = plt.gca()

        if not label:
            label=f"{self._Info['Region Name']}: {self._Info['File']} | {self._Info['Conditions']['Temperature']}"
        # If we want scatter plot
        if scatter:
            ax.scatter(x, y, s=7, c=color, label=label)
        else:
            ax.plot(x, y, color=color, label=label)

        ax.legend(loc='best')
        ax.set_title(f"Pass: {self._Info['Pass Energy']}   |   Sweeps: {self._Info['Number of Sweeps']}   |   File: {self._Info['File']}")

        #   Stiling axes
        x_label_prefix = "Binding"
        if self._Info["Energy Scale"] == "Kinetic":
            x_label_prefix = "Kinetic"

        ax.set_xlabel(f"{x_label_prefix} energy (eV)")
        ax.set_ylabel("Counts (a.u.)")

        # Inverting x-axis if desired and not yet inverted
        if invert_x and not ax.xaxis_inverted():
            ax.invert_xaxis()

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
            self._Flags[Region._region_flags[0]] = True

    def getData(self, column=None):
        """Returns pandas DataFrame with two or more columns (first two columns
        were originally retrieved from the data file, other columns could be added
        after some processing of the original data)
        """
        if column:
            return self._Data[column].values
        return self._Data

    def getInfo(self):
        """Returns 'info' dictionary {"name": value}
        """
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
        """Returns the dictionary of flags in the following order
        """
        return self._Flags

    def setFermiFlag(self):
        """Sets the Fermi flag of the region to be True
        """
        self._Flags[Region._region_flags[2]] = True

    def addColumn(self, column_label, array):
        """Adds one column to the data object assigning it the name 'column_label'.
        Choose descriptive labels.
        """
        self._Data[column_label] = array

    def removeColumn(self, column_label):
        """Removes one of the columns of the data object
        """
        if (column_label == 'energy') or (column_label == 'counts'):
            print("Original data columns can't be removed!")
            return
        self._Data = self._Data.drop(column_label, 1)

    def saveCSV(self, filename):
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

    @staticmethod
    def readCSV(filename):
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

        return Region(df['energy'].tolist(), df['counts'].tolist(),
                        energy_shift_corrected=flags[Region._region_flags[0]],
                        binding_energy_flag=flags[Region._region_flags[1]],
                        fermi_level_flag=flags[Region._region_flags[2]], info=info)
