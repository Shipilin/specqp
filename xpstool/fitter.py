""" Provides class Fitter with helping functions
"""
import numpy as np
import scipy as sp
from scipy.optimize import curve_fit
from .datahandler import Region

class Peak:
    """Contains information about one peak fitted to a region.
    """
    peak_types = {
        "gaussian": ["amplitude", "center", "sigma"],
        "lorenzian": ["a", "b", "c"], # TODO
        "voigt": ["a", "b", "c"] # TODO
    }

    def __init__(self, x_data, y_data, popt, pcov, peak_type):
        """Creates an instance of Peak object with X and Y data for plotting
        and fitting parameters and parameters coavriance.
        """
        self._X = x_data
        self._Y = y_data
        self._Popt = popt
        self._Pcov = pcov
        self._FittingErrors = np.sqrt(np.diag(self._Pcov))
        self._PeakType = peak_type

    def __str__(self):
        output = self._PeakType
        for i, p in enumerate(self._Popt):
            output = "\n".join((output, f"{self.peak_types[self._PeakType][i]}: {p:.4f} +/- {self._FittingErrors[i]:.4f}"))
        return output

    def getData(self):
        """Returns a list of x and y data
        """
        return [self._X, self._Y]

    def getParameters(self, parameter=None):
        """Returns all fitting parameters or one specified by name from 'peak_types'
        """
        if not parameter:
            return self._Popt
        else:
            for i, par_name in enumerate(self.peak_types[self._PeakType]):
                if parameter == par_name:
                    return self._Popt[i]
        print("No such parameter")

    def getCovariance(self, parameter=None):
        """Returns all fitting parameters covariances or one specified by name 'peak_types'
        """
        if not parameter:
            return self._Pcov
        else:
            for i, par_name in enumerate(self.peak_types[self._PeakType]):
                if parameter == par_name:
                    return self._Pcov[i]
        print("No such parameter")

    def getFittingErrors(self, parameter=None):
        """Returns fitting errors for all parameters or one specified by name 'peak_types'
        """
        if not parameter:
            return self._FittingErrors
        else:
            for i, par_name in enumerate(self.peak_types[self._PeakType]):
                if parameter == par_name:
                    return self._FittingErrors[i]
        print("No such parameter")

    def getPeakType(self):
        return self._PeakType

class Fitter:
    """Provides fitting possibilities for XPS spectra
    """
    def __init__(self, region, y_data='counts'):
        """Creates an object that contains information about fitting of
        a particular XPS region.
        """
        self._X_data = region.getData(column='energy').tolist()
        self._Y_data = region.getData(column=y_data).tolist()
        self._Peaks = []

    def __str__(self):
        output = ""
        for i, peak in enumerate(self._Peaks):
            new_line = "\n"
            if i == 0:
                new_line = ""
            output = new_line.join((output, f"Peak #{i}"))
            output = "\n".join((output, peak.__str__()))
        return output

    def fitGaussian(self, initial_params):
        """Fits one Gaussian function to Region object based on initial values
        of three parameters (amplitude, center, and sigma). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        """
        def _multiGaussian(x, *args):
            cnt = 0
            func = 0
            while cnt < len(args):
                func += args[cnt]*(1/(args[cnt+2]*(np.sqrt(2*np.pi))))*(np.exp(-((x-args[cnt+1])**2)/((2*args[cnt+2])**2)))
                cnt += 3
            return func

        if len(initial_params) % 3 != 0:
            print("Check the number of initial parameters.")
            return

        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_multiGaussian,
                        self._X_data,
                        self._Y_data,
                        p0=initial_params)

        cnt = 0
        while cnt < len(initial_params):
            peak_y = _multiGaussian(self._X_data, popt[cnt], popt[cnt+1], popt[cnt+2])
            self._Peaks.append(Peak(self._X_data,
                                    peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                    "gaussian"))
            cnt += 3

    def getPeaks(self, peak_num=None): # TODO add peak ID
        if not peak_num:
            return self._Peaks
        else:
            return self._Peaks[peak_num]
