import os, sys
import copy
import math
import matplotlib.pyplot as plt
from colorama import Fore

import numpy as np
import pandas as pd
import scipy as sp

import helpers
from datahandler import Experiment, Spectrum, Region
from fitter import Fitter, Peak

def run():
    """Defines the behavior of the app if run as a script
    """
    print("Running as a script")

if __name__ == "__main__":
    gui.main()
