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
        "lorentzian": ["amplitude", "center", "width"],
        "voigt": ["wg", "amplitude", "center", "width"] # wg - weight of Gaussian
    }

    def __init__(self, x_data, y_data, popt, pcov, peak_type):
        """Creates an instance of Peak object with X and Y data for plotting
        and fitting parameters and parameters coavriance.
        """
        self._X = x_data
        self._Y = y_data
        self._Popt = popt
        self._Pcov = pcov
        self._Area = np.trapz(self._Y)
        self._PeakType = peak_type
        self._FittingErrors = []
        for i in range(len(self._Popt)):
            try:
              self._FittingErrors.append(np.absolute(self._Pcov[i][i])**0.5)
            except:
              self._FittingErrors.append( 0.00 )

    def __str__(self):
        output = f"Type: {self._PeakType}"
        for i, p in enumerate(self._Popt):
            output = "\n".join((output, f"{self.peak_types[self._PeakType][i]}: {p:.4f} (+/- {self._FittingErrors[i]:.4f})"))
        output = "\n".join((output, f"Area: {self._Area:.4f}"))
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
    def __init__(self, region, y_data='counts', gauss_fwhm=None):
        """Creates an object that contains information about fitting of
        a particular XPS region.
        """
        self._X_data = region.getData(column='energy')
        self._Y_data = region.getData(column=y_data)
        # Following attributes are assigned during the fitting procedure
        self._FitLine = region.getData(column=y_data)*0
        self._Residuals = region.getData(column=y_data)*0
        self._Rsquared = 0
        self._Peaks = []
        # The gauss widening is constant due to the equipment used in the
        # experiment. So, if we know it, we should fix this parameter in
        # fitting.
        self._GaussFWHM = gauss_fwhm

    def __str__(self):
        output = ""
        for i, peak in enumerate(self._Peaks):
            new_line = "\n"
            if i == 0:
                new_line = ""
            output = new_line.join((output, f"--- Peak #{i+1} ---"))
            output = "\n".join((output, peak.__str__()))
        return output

    @staticmethod
    def _multiGaussian(x, *args):# TODO change gamma and fwhm
        cnt = 0
        func = 0
        while cnt < len(args):
            func += args[cnt]*(1/(args[cnt+2]*(np.sqrt(2*np.pi))))*(np.exp(-((x-args[cnt+1])**2)/(2*(args[cnt+2])**2)))
            cnt += 3
        return func

    @staticmethod
    def _multiLorentzian(x, *args):# TODO change gamma and fwhm
        """Creates a single or multiple Lorentzian shape taking amplitude, Center
        and FWHM parameters
        """
        cnt = 0
        func = 0
        while cnt < len(args):
            func += args[cnt]*(1/np.pi*(args[cnt+2]/2))*((args[cnt+2]/2)**2)/(((x-args[cnt+1])**2)+(args[cnt+2]/2)**2)
            #args[cnt]*args[cnt+2]**2/((x-args[cnt+1])**2+args[cnt+2]**2)
            cnt += 3
        return func

    def _multiVoigt(self, x, *args):
        """Creates a single or multiple Voigt shape using
        f = weight*gaussian + (1-weight)*lorentzian
        Takes constant sigma for gaussian contribution.
        """
        def lorentz(x, x0, g):
            return 1. / ( np.pi * g * ( 1 + ( ( x - x0 )/ g )**2 ) )

        def gauss( x, x0, s):
            return 1./ np.sqrt(2 * np.pi * s**2 ) * np.exp( - (x-x0)**2 / ( 2 * s**2 ) )

        cnt = 0
        func = 0
        while cnt < len(args):
            if not self._GaussFWHM:
                sigma = args[cnt+3]/(2*np.sqrt(2*np.log(2)))
            else:
                sigma = self._GaussFWHM/(2*np.sqrt(2*np.log(2)))
            func += args[cnt + 1] * (args[cnt] * gauss(x, args[cnt + 2], sigma)
                                        + (1 - args[cnt]) * lorentz(x, args[cnt + 2], args[cnt + 3] / 2))

            cnt += 4

        return func

    def fitGaussian(self, initial_params):# TODO change gamma and fwhm
        """Fits Gaussian function(s) to Region object based on initial values
        of three parameters (amplitude, center, and sigma). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        """

        if len(initial_params) % 3 != 0:
            print("Check the number of initial parameters.")
            return

        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(Fitter._multiGaussian,
                        self._X_data,
                        self._Y_data,
                        p0=initial_params)

        cnt = 0
        while cnt < len(initial_params):
            peak_y = Fitter._multiGaussian(self._X_data, popt[cnt], popt[cnt+1], popt[cnt+2])
            self._Peaks.append(Peak(self._X_data,
                                    peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                    "gaussian"))
            cnt += 3

        self._makeFit()

    def fitLorentzian(self, initial_params):# TODO change gamma and fwhm
        """Fits one Lorentzian function to Region object based on initial values
        of three parameters (amplitude, center, and width). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        """

        if len(initial_params) % 3 != 0:
            print("Check the number of initial parameters.")
            return

        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(Fitter._multiLorentzian,
                        self._X_data,
                        self._Y_data,
                        p0=initial_params)

        cnt = 0
        while cnt < len(initial_params):
            peak_y = Fitter._multiLorentzian(self._X_data, popt[cnt], popt[cnt+1], popt[cnt+2])
            self._Peaks.append(Peak(self._X_data,
                                    peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                    "lorentzian"))
            cnt += 3
        self._makeFit()

    def fitVoigt(self, initial_params, fix_pars=None):
        """Fits one or more Voigt function(s) to Region object based on initial values
        of three parameters (amplitude, center, and fwhm). The weight of
        gaussian (wg) is also added to parameters to be able to vary
        Gaussian and (1-wg) Lorentzian contributions. If sigma for Gaussian
        is known from experiment, the width parameter changes on;y for Lorentzian.
        If list with more than one set of parameters is given, the function fits
        more than one peak. fix_parameter is a dictionary with names of parameters
        to fix as keys and numbers of peaks for which the parameters should be fixed
        as lists. Ex: {"wg": [0,1,2], "cen": [1,2]}
        """
        if len(initial_params) % 4 != 0:
            print(f"Check the number of initial parameters for peak #{i+1}.")
            return

        bounds_low = []
        bounds_high = []
        for i in range(0, len(initial_params)):
            if i % 4 == 0: # Fixing gaussian weight parameter
                # wg parameter has numbers 0,4,8,...
                if fix_pars and ("wg" in fix_pars):
                    if (i // 4) in fix_pars["wg"]:
                        # For curve_fit method the boundaries should be different
                        # Add 0.0001 difference
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
                bounds_low.append(0)
                bounds_high.append(1)
                continue
            if (i-1) % 4 == 0: # Adjusting amplitude parameter boundaries
                if fix_pars and ("amp" in fix_pars):
                    if ((i-1) // 4) in fix_pars["amp"]:
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
                # Fixing the lower limit for amplitude at 0 and the higher
                # limit at data_y max
                bounds_low.append(0)
                # The upper boundary of amplitude should not be lower than the
                # value of initial guess
                if initial_params[i] < np.amax(self._Y_data):
                    bounds_high.append(np.amax(self._Y_data))
                else:
                    bounds_high.append(initial_params[i])
                continue
            if (i-2) % 4 == 0: # Fixing center parameters if asked
                if fix_pars and ("cen" in fix_pars):
                    if ((i-2) // 4) in fix_pars["cen"]:
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
            if (i-3) % 4 == 0: # Fixing fwhm parameters if asked
                if fix_pars and ("fwhm" in fix_pars):
                    if ((i-3) // 4) in fix_pars["fwhm"]:
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
            bounds_low.append(-np.inf)
            bounds_high.append(np.inf)
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(self._multiVoigt,
                        self._X_data,
                        self._Y_data,
                        p0=initial_params,
                        bounds=(bounds_low, bounds_high))

        cnt = 0
        while cnt < len(initial_params):
            peak_y = self._multiVoigt(self._X_data, popt[cnt], popt[cnt+1], popt[cnt+2], popt[cnt+3])
            self._Peaks.append(Peak(self._X_data,
                                    peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2], popt[cnt+3]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2], pcov[cnt+3]],
                                    "voigt"))
            cnt += 4
        self._makeFit()

    def _makeFit(self):
        """Calculates the total fit line including all peaks and calculates the
        residuals and r-squared.
        """
        # Calculate fit line
        for peak in self._Peaks:
            #for peak_y in peak.getData()[1]:
            self._FitLine += peak.getData()[1]
        # Calculate residuals
        #for i, y in enumerate(self._Y_data):
        self._Residuals = self._Y_data - self._FitLine
        # Calculate R-squared
        ss_res = np.sum(self._Residuals**2)
        ss_tot = np.sum((self._Y_data - np.mean(self._Y_data))**2)
        self._Rsquared = 1 - (ss_res / ss_tot)

    def getFitLine(self):
        """Returns x and y coordinates for the fit line based on all fitted peaks
        """
        if not self._FitLine.size == 0:
            return self._FitLine
        print("Do fit first")

    def getResiduals(self):
        if not self._Residuals.size == 0:
            return self._Residuals
        print("Do fit first")

    def getRsquared(self):
        if not self._Rsquared == 0:
            return self._Rsquared
        print("Do fit first")

    def getPeaks(self, peak_num=None): # TODO add peak ID
        if not self._Peaks:
            print("Do fit first")
            return
        if not peak_num:
            return self._Peaks
        else:
            return self._Peaks[peak_num]

    def getData(self):
        return [self._X_data, self._Y_data]
