""" Provides class Fitter with helping functions
"""
import logging
import numpy as np
from scipy.optimize import curve_fit

fitter_logger = logging.getLogger("specqp.fitter")  # Creating child logger


class Peak:
    """Contains information about one peak fitted to a region.
    """
    peak_types = {
        "gaussian": ["amplitude", "center", "fwhm"],
        "lorentzian": ["amplitude", "center", "fwhm"],
        "voigt": ["amplitude", "center", "fwhm"]
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

    def get_data(self):
        """Returns a list of x and y data
        """
        return [self._X, self._Y]

    def get_parameters(self, parameter=None):
        """Returns all fitting parameters or one specified by name from 'peak_types'
        """
        if not parameter:
            return self._Popt
        else:
            for i, par_name in enumerate(self.peak_types[self._PeakType]):
                if parameter == par_name:
                    return self._Popt[i]
        fitter_logger.error(f"Couldn't get fitting parameters from a Peak instance")

    def get_covariance(self, parameter=None):
        """Returns all fitting parameters covariances or one specified by name 'peak_types'
        """
        if not parameter:
            return self._Pcov
        else:
            for i, par_name in enumerate(self.peak_types[self._PeakType]):
                if parameter == par_name:
                    return self._Pcov[i]
        fitter_logger.error(f"Couldn't get covariance from a Peak instance")

    def get_fitting_errors(self, parameter=None):
        """Returns fitting errors for all parameters or one specified by name 'peak_types'
        """
        if not parameter:
            return self._FittingErrors
        else:
            for i, par_name in enumerate(self.peak_types[self._PeakType]):
                if parameter == par_name:
                    return self._FittingErrors[i]
        fitter_logger.error(f"Couldn't get fitting errors from a Peak instance")

    def get_peak_type(self):
        return self._PeakType


class Fitter:
    """Provides fitting possibilities for XPS regions
    """
    def __init__(self, region, y_data='final', gauss_fwhm=None):
        """Creates an object that contains information about fitting of
        a particular XPS region.
        """
        self._X_data = region.get_data(column='energy')
        self._Y_data = region.get_data(column=y_data)
        # Following attributes are assigned during the fitting procedure
        self._FitLine = region.get_data(column=y_data) * 0
        self._Residuals = region.get_data(column=y_data) * 0
        self._Rsquared = 0
        self._Chisquared = 0
        self._RMS = 0
        self._Peaks = []
        # The gauss widening is constant due to the equipment used in the
        # experiment. So, if we know it, we should fix this parameter in
        # fitting.
        self._GaussFWHM = gauss_fwhm*1.0
        self._ID = region.get_id()

    def __str__(self):
        output = ""
        for i, peak in enumerate(self._Peaks):
            new_line = "\n"
            if i == 0:
                new_line = ""
            output = new_line.join((output, f"--- Peak #{i+1} ---"))
            output = "\n".join((output, peak.__str__()))
        return output

    # TODO change gamma and fwhm
    def fit_gaussian(self, initial_params):
        """Fits Gaussian function(s) to Region object based on initial values
        of three parameters (amplitude, center, and sigma). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        """

        def _multi_gaussian(x, *args):
            cnt = 0
            func = 0
            while cnt < len(args):
                func += args[cnt] * (1 / (args[cnt + 2] * (np.sqrt(2 * np.pi)))) * (
                    np.exp(-((x - args[cnt + 1]) ** 2) / (2 * (args[cnt + 2]) ** 2)))
                cnt += 3
            return func

        if len(initial_params) % 3 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fitter.fit_gaussian method.")
            return

        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_multi_gaussian, self._X_data, self._Y_data, p0=initial_params)

        cnt = 0
        while cnt < len(initial_params):
            peak_y = _multi_gaussian(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2])
            self._Peaks.append(Peak(self._X_data, peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                    "gaussian"))
            cnt += 3

        self._make_fit()

    # TODO change gamma and fwhm
    def fit_lorentzian(self, initial_params):
        """Fits one Lorentzian function to Region object based on initial values
        of three parameters (amplitude, center, and width). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        """
        def _multi_lorentzian(x, *args):
            """Creates a single or multiple Lorentzian shape taking amplitude, Center
            and FWHM parameters
            """
            cnt = 0
            func = 0
            while cnt < len(args):
                func += args[cnt] * (1 / np.pi * (args[cnt + 2] / 2)) * ((args[cnt + 2] / 2) ** 2) / (
                            ((x - args[cnt + 1]) ** 2) + (args[cnt + 2] / 2) ** 2)
                cnt += 3
            return func

        if len(initial_params) % 3 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fitter.fit_lorentzian method.")
            return

        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_multi_lorentzian, self._X_data, self._Y_data, p0=initial_params)

        cnt = 0
        while cnt < len(initial_params):
            peak_y = _multi_lorentzian(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2])
            self._Peaks.append(Peak(self._X_data, peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                    "lorentzian"))
            cnt += 3
        self._make_fit()

    def _multi_voigt(self, x, *args):
        """Creates a single or multiple pseudo Voigt shape.
        Takes constant sigma for gaussian contribution if known.
        """
        def lorentz(x, x0, FWHM):
            gamma = FWHM/2
            l_func = 1. / ( np.pi * gamma * ( 1 + ( ( x - x0 )/ gamma )**2 ) )
            return l_func #/ np.amax(l_func) # Normalizing to 1

        def gauss( x, x0, FWHM):
            sigma = FWHM / ( 2 * np.sqrt( 2 * np.log(2) ) )
            g_func = 1./ np.sqrt(2 * np.pi * sigma**2 ) * np.exp( - (x-x0)**2 / ( 2 * sigma**2 ) )
            return g_func #/ np.amax(g_func) # Normalizing to 1

        def pseudo_voigt( x, cen, gFWHM, lFWHM, amp ):
            f = ( gFWHM**5 +  2.69269 * gFWHM**4 * lFWHM + 2.42843 * gFWHM**3 * lFWHM**2 + 4.47163 * gFWHM**2 * lFWHM**3 + 0.07842 * gFWHM * lFWHM**4 + lFWHM**5)**(1./5.)
            eta = 1.36603 * ( lFWHM / f ) - 0.47719 * ( lFWHM / f )**2 + 0.11116 * ( lFWHM / f )**3
            pv_func = ( eta * lorentz( x, cen, f) + ( 1 - eta ) * gauss( x, cen, f ) )
            return amp * pv_func / np.amax(pv_func) # Normalizing to 1

        # To avoid faulty mathematical operations in pseudo_voigt calculation
        for arg in args:
            if arg < 0:
                return 0

        cnt = 0
        func = 0
        while cnt < len(args):
            amp = args[cnt]
            cen = args[cnt+1]
            lFWHM = args[cnt+2]
            if not self._GaussFWHM:
                gFWHM = lFWHM
            else:
                gFWHM = self._GaussFWHM
            func += pseudo_voigt(x, cen, gFWHM, lFWHM, amp)

            cnt += 3
        return func

    def fit_voigt(self, initial_params, fix_pars=None, boundaries=None):
        """Fits one or more Voigt function(s) to Region object based on initial values
        of three parameters (amplitude, center, and fwhm). If sigma for Gaussian
        is known from experiment, the fwhm parameter changes only for Lorentzian.
        If list with more than one set of parameters is given, the function fits
        more than one peak.
        fix_parameter is a dictionary with names of parameters to fix as keys
        and numbers of peaks for which the parameters should be fixed
        as lists. Ex: {"cen": [1,2], "amp": [0,1,2]}
        boundaries is a dictionary with names of parameters as keys and a
        dictionary containing lower and upper boundaries for the corresponding
        peak. Ex: {"cen": {1: [34,35], 2: [35,36]}}
        """
        if len(initial_params) % 3 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fitter.fit_voigt method.")
            return

        bounds_low = []
        bounds_high = []
        for i in range(0, len(initial_params)):
            if i % 3 == 0: # Adjusting amplitude parameter boundaries
                peak_number = (i) // 3
                if fix_pars and ("amp" in fix_pars):
                    if peak_number in fix_pars["amp"]:
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
                if boundaries and ("amp" in boundaries):
                    if peak_number in boundaries["amp"]:
                        if len(boundaries["amp"][peak_number]) == 2:
                            bounds_low.append(min(boundaries["amp"][peak_number]))
                            bounds_high.append(max(boundaries["amp"][peak_number]))
                            continue
                # Fixing the lower limit for amplitude at 0 and the higher limit at data_y max
                bounds_low.append(0)
                # The upper boundary of amplitude should not be lower than the value of initial guess
                if initial_params[i] < np.amax(self._Y_data):
                    bounds_high.append(np.amax(self._Y_data))
                else:
                    bounds_high.append(initial_params[i])
                continue
            if (i-1) % 3 == 0: # Adjusting center parameters boundaries
                peak_number = (i - 1) // 3
                if fix_pars and ("cen" in fix_pars):
                    if peak_number in fix_pars["cen"]:
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
                if boundaries and ("cen" in boundaries):
                    if peak_number in boundaries["cen"]:
                        if len(boundaries["cen"][peak_number]) == 2:
                            bounds_low.append(min(boundaries["cen"][peak_number]))
                            bounds_high.append(max(boundaries["cen"][peak_number]))
                            continue
            if (i-2) % 3 == 0: # Adjusting fwhm parameters boundaries
                peak_number = (i - 2) // 3
                if fix_pars and ("fwhm" in fix_pars):
                    if peak_number in fix_pars["fwhm"]:
                        bounds_low.append(initial_params[i] - 0.0001)
                        bounds_high.append(initial_params[i] + 0.0001)
                        continue
                if boundaries and ("fwhm" in boundaries):
                    if peak_number in boundaries["fwhm"]:
                        if len(boundaries["fwhm"][peak_number]) == 2:
                            bounds_low.append(min(boundaries["fwhm"][peak_number]))
                            bounds_high.append(max(boundaries["fwhm"][peak_number]))
                            continue
            bounds_low.append(-np.inf)
            bounds_high.append(np.inf)
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(self._multi_voigt, self._X_data, self._Y_data, p0=initial_params,
                               bounds=(bounds_low, bounds_high))

        cnt = 0
        while cnt < len(initial_params):
            peak_y = self._multi_voigt(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2])
            self._Peaks.append(Peak(self._X_data, peak_y,
                                    [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                    [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                    "voigt"))
            cnt += 3
        self._make_fit()

    def _make_fit(self):
        """Calculates the total fit line including all peaks and calculates the
        residuals and r-squared.
        """
        # Calculate fit line
        for peak in self._Peaks:
            self._FitLine += peak.get_data()[1]
        # Calculate residuals
        self._Residuals = self._Y_data - self._FitLine
        # Calculate R-squared
        ss_res = np.sum(self._Residuals**2)
        ss_tot = np.sum((self._Y_data - np.mean(self._Y_data))**2)
        self._Rsquared = 1 - (ss_res / ss_tot)
        # Individual standard deviation of original data
        std_d = np.sqrt((self._Y_data - np.mean(self._Y_data))**2)
        self._Chisquared = np.sum(((self._Y_data - self._FitLine)/std_d)**2)
        self._RMS = np.sum((self._Y_data - self._FitLine)**2)

    def get_fit_line(self):
        """Returns x and y coordinates for the fit line based on all fitted peaks
        """
        if not self._FitLine.size == 0:
            return self._FitLine
        fitter_logger.warning("Can't get Fit Line from a Fitter instance. Do fit first.")

    def get_residuals(self):
        if not self._Residuals.size == 0:
            return self._Residuals
        fitter_logger.warning("Can't get residuals from a Fitter instance. Do fit first.")

    def get_rsquared(self):
        if not self._Rsquared == 0:
            return self._Rsquared
        fitter_logger.warning("Can't get R Squared from a Fitter instance. Do fit first.")

    def get_chi_squared(self):
        if not self._Chisquared == 0:
            return self._Chisquared
        fitter_logger.warning("Can't get Chi Squared from a Fitter instance. Do fit first.")

    def get_rms(self):
        if not self._RMS == 0:
            return self._RMS
        fitter_logger.warning("Can't get RMS from a Fitter instance. Do fit first.")

    # TODO add peak ID
    def get_peaks(self, peak_num=None):
        if not self._Peaks:
            fitter_logger.warning("Can't get peaks from a Fitter instance. Do fit first.")
            return
        if not peak_num:
            return self._Peaks
        else:
            return self._Peaks[peak_num]

    def get_data(self):
        return [self._X_data, self._Y_data]

    def get_id(self):
        return self._ID

    def get_gauss_fwhm(self):
        return self._GaussFWHM
