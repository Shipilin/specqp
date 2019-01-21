import os
import pandas as pd

class Region:
    """Contains and handles a single recorded region together with all information
    about the scan and experimental conditions provided in data file
    """
    
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
        self._EnergyShiftCorrectedFlag = energy_shift_corrected
        self._BindingEnergyFlag = binding_energy_flag
        self._FermiLevelFlag = fermi_level_flag
        self._Info = info
                    
    def __str__(self):
        """Prints the info read from the Scienta file
        """
        output = ""
        if not self._Info:
            output = "No info available"
        else:
            for key, val in self._Info.items():
                output = "\n".join((output, f"{key}: {val}"))
        return output 
    
    def invertEnergyScale(self, excitation_energy):
        """Changes the energy scale of the region from the currently defined to 
        the alternative one. From kinetic to binding energy 
        or from binding to kinetic energy. The photon energy used for excitation 
        is required.
        """
        self._Data['energy'] = [(excitation_energy - value) for value in self._Data['energy']]
        self._BindingEnergyFlag = not self._BindingEnergyFlag
        
        # We need to change some info entries also
        self._Info["Excitation Energy"] = str(excitation_energy)
        for key in ["Energy Scale", "Energy Unit", "Energy Axis"]:
            # Depending on whether it was SPECS or Scienta file loaded, the info 
            # dictionaries may have different keys. So, we scroll through all
            # possible values and change the existing ones 
            if key in self._Info.keys():
                if self._BindingEnergyFlag:
                    self._Info[key] = "Binding"
                else:
                    self._Info[key] = "Kinetic"
        for key in ["Center Energy", "Low Energy", "High Energy"]:
            if key in self._Info.keys():
                self._Info[key] = str(excitation_energy - float(self._Info[key]))
    
    def getData(self):
        """Returns pandas DataFrame with two or more columns (first two columns
        were originally retrieved from the data file, other columns could be added
        after some processing of the original data) 
        """
        return self._Data

    def getInfo(self):
        """Returns 'info' dictionary {"name": value}
        """
        return self._Info
    
    def getFlags(self):
        """Returns the list of flags in the following order 
        [energy_shift_corrected_flag, binding_energy_flag, fermi_level_flag]
        """
        return [self._EnergyShiftCorrectedFlag, self._BindingEnergyFlag, self._FermiLevelFlag]
        
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
            for flag in [self._EnergyShiftCorrectedFlag, self._BindingEnergyFlag, self._FermiLevelFlag]:
                file.write(f"# {flag}\n")
            for key, value in self._Info.items():
                file.write(f"# {key}: {value}\n")                
            self._Data.to_csv(file, index=False)
                       
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
        # Reading the flags from the first three lines
        energy_shift_corrected=lines[0].strip('#').strip() 
        binding_energy_flag=lines[1].strip('#').strip()
        fermi_level_flag=lines[2].strip('#').strip()
                           
        # Reading info part of the file (lines starting with '#')
        info_lines = []
        # Start reading after the flags lines
        for i in range(3, len(lines)):
            if lines[i].strip().startswith('#'):
                info_lines.append(lines[i].strip('\n')) # Save info lines   
              
        info = {} 
        for line in info_lines:
            line = line.strip().lstrip('#').strip()
            line_content = line.split(':', 1)
            info[line_content[0].strip()] = line_content[1].strip()   
    
        return Region(df['energy'].tolist(), df['counts'].tolist(), 
                        energy_shift_corrected=energy_shift_corrected, 
                        binding_energy_flag=binding_energy_flag,
                        fermi_level_flag=fermi_level_flag, info=info)
                                                        