"""The module contains classes and functions responsible
for loading and storing spectroscopy data. It also provides
general handles for the outside modules and scripts.
The hierarchy of objects is as follows:
1. Class Experiment contains all data for an executed experiment.
Usually it shoul contains one uninterrupted set of measurements
for one sample.
2. Class Set contains a number of spectra measured under the same
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
import tkinter as tk
from tkinter import filedialog
import pandas as pd

class Experiment:
    """Class Experiment contains all data for an executed experiment.
    Usually it shoul contains one uninterrupted set of measurements
    for one sample.
    """
    def __init__(self, path=None):
        if not path:
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename()

        self.Path = path

    def __str__():
        return self.Path

    @staticmethod
    def loadScientaTXT():
        pass

    @staticmethod
    def loadSpecsXY():
        pass
