import numpy as np
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
    
    def getFalgs(self):
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
        self._Data = self.Data.drop(column_label, 1)