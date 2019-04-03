import sys

import helpers
from datahandler import Experiment, Spectrum, Region
from fitter import Fitter, Peak
from gui import main as callGUI

def main(*args, **kwargs):
    """Defines the behavior of the app if run in batch mode
    """
    print("Running in batch mode")
    if args is not None:
        for arg in args:
            print(arg)
    if kwargs is not None:
        for key, value in kwargs.items():
            print(f"{key}={value}")

if __name__ == "__main__":

    # Enable the case below to force the user to provide arguments
    # if len(sys.argv) < 2:
    #     raise SyntaxError("Insufficient arguments.")

    if len(sys.argv) == 1:
        # If only script name is specified call GUI for interacive work
        callGUI()
    if len(sys.argv) > 1:
        # If there are additional arguments run in batch mode
        args = []
        kwargs = []
        for arg in sys.argv[1:]:
            if "=" in arg:
                # If key word arguments are provided
                kwargs.append(arg)
            else:
                args.append(arg)
        main(*args, *kwargs)
