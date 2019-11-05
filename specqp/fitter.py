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
        "Gauss": ["amplitude", "center", "fwhm"],
        "Lorentz": ["amplitude", "center", "fwhm"],
        "Pseudo Voigt": ["amplitude", "center", "g_fwhm", "l_fwhm"],
        "Doniach-Sunjic": ["amplitude", "center", "g_fwhm", "l_fwhm"]
    }

    def __init__(self, x_data, y_data, popt, pcov, peak_func, peak_id, peak_type, bindingscale=True, lmfit=False):
        """Creates an instance of Peak object with X and Y data for plotting
        and fitting parameters and parameters coavriance.
        """
        self._X = x_data
        self._Y = y_data
        self._Popt = popt
        self._function = peak_func
        self._bindingscale = bindingscale
        self._id = peak_id
        self._Area = np.trapz(self._Y)
        self._PeakType = peak_type
        self._Pcov = pcov
        self._FittingErrors = []
        if not lmfit:
            for i in range(len(self._Popt)):
                try:
                    self._FittingErrors.append(np.absolute(self._Pcov[i][i])**0.5)
                except RuntimeWarning:
                    self._FittingErrors.append(0.00)
        else:
            self._FittingErrors = pcov

    def __str__(self):
        output = f"Type: {self._PeakType}"
        for i, p in enumerate(self._Popt):
            output = "\n".join((output, f"{self.peak_types[self._PeakType][i]}: {p:.4f} (+/- {self._FittingErrors[i]:.4f})"))
        output = "\n".join((output, f"Area: {self._Area:.4f}"))
        return output

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

    def get_data(self):
        """Returns a list of x and y data
        """
        return [self._X, self._Y]

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

    def get_peak_area(self):
        return self._Area

    def get_peak_id(self):
        return self._id

    def get_peak_type(self):
        return self._PeakType

    def get_virtual_data(self, num=10, multiply=True):
        """Returns more (or less) data points. If multiply==False, value of 'num' is taken as desired number of ponts.
        If multiply==True, multiplies the existing number of points by value of 'num'. For plotting a smoother curve,
        for example.
        :param num: Number of desired points or multiplicator
        :param multiply: True if num is multiplicator, False if num is absolute number of points
        :return (ndarray, ndarray) x and y data with desired number of points
        """
        assert num > 0
        if multiply:
            peak_virtual_x = np.linspace(self._X[0], self._X[-1], len(self._X) * num, endpoint=True)
        else:
            peak_virtual_x = np.linspace(self._X[0], self._X[-1], num, endpoint=True)

        if self._function.__name__ == "doniach_sunjic":
            asymmetry = 'higher'
            if not self._bindingscale:
                asymmetry = 'lower'
            peak_virtual_y = self._function(peak_virtual_x, *self._Popt, asymmetry=asymmetry)
        else:
            peak_virtual_y = self._function(peak_virtual_x, *self._Popt)
        return peak_virtual_x, peak_virtual_y

    def set_peak_id(self, new_id):
        self._id = new_id


class Fitter:
    """Provides fitting possibilities for XPS regions
    """

    bg_types = (
        'constant',
        'linear',
        'square',
        'shirley'
    )

    def __init__(self, region, y_data='final', gauss_fwhm=None, bg=None):
        """Creates an object that contains information about fitting of
        a particular XPS region.
        """
        self.region = region
        self._X_data = region.get_data(column='energy')
        self._Y_data = region.get_data(column=y_data)
        # Following attributes are assigned during the fitting procedure
        self._FitLine = region.get_data(column=y_data) * 0
        self._Residuals = region.get_data(column=y_data) * 0
        self._Rsquared = 0
        self._Chisquared = 0
        self._RMS = 0
        self._Peaks = {}
        self._Bg = bg
        # The gauss widening is constant due to the equipment used in the experiment. So, if we know it,
        # we should fix this parameter in fitting.
        if gauss_fwhm:
            self._global_gauss_fwhm = gauss_fwhm * 1.0
        self._ID = region.get_id()

    def __str__(self):
        output = ""
        for i, peak in enumerate(self._Peaks.values()):
            new_line = "\n"
            if i == 0:
                new_line = ""
            output = new_line.join((output, f"--- Peak #{i+1} ---"))
            output = "\n".join((output, peak.__str__()))
        return output

    def add_peak(self, peak):
        peak_id = peak.get_peak_id()
        if peak_id not in self._Peaks:
            self._Peaks[peak_id] = peak
            return True
        else:
            fitter_logger.warning(f"Peak '{peak_id}' already exists in fitter object {self._ID}.")
            return False

    def delete_peak(self, peak_id):
        if peak_id in self._Peaks:
            del self._Peaks[peak_id]

    @staticmethod
    def get_model(model, energy, intensity, params, bindingscale=True):
        """Returns the function model according to name
        :param model: str one of specqp.Peak.peak_types
        :param energy: x axis
        :param intensity: y axis (optionally used by some models)
        :param params: parameters dictionary, e.g.
        {'amplitude': {'value': 200, 'fix': False, 'dependencetype': 'Independent',
                  'min': 10, 'max': 100000},
         'center': {'value': 22.35, 'fix': False, 'dependencetype': 'Dependent *',
                    'min': 10, 'max': 30},
         'g_fwhm': {'value': 1.15, 'fix': True, 'dependencetype': 'Independent',
                    'min': 1.1, 'max': 1.2},
         'l_fwhm': {'value': 0.5, 'fix': True, 'dependencetype': 'Independent',
                    'min': 0.4, 'max': 0.6}}
        :return: array
        """
        if model in Peak.peak_types:
            if model == "Gauss":
                return Fitter.gauss(energy, params[Peak.peak_types[model][0]]['value'],
                                    params[Peak.peak_types[model][1]]['value'],
                                    params[Peak.peak_types[model][2]]['value'])
            if model == "Lorentz":
                return Fitter.lorentz(energy, params[Peak.peak_types[model][0]]['value'],
                                      params[Peak.peak_types[model][1]]['value'],
                                      params[Peak.peak_types[model][2]]['value'])
            if model == "Pseudo Voigt":
                return Fitter.pseudo_voigt(energy, params[Peak.peak_types[model][0]]['value'],
                                           params[Peak.peak_types[model][1]]['value'],
                                           params[Peak.peak_types[model][2]]['value'],
                                           params[Peak.peak_types[model][3]]['value'])
            if model == "Doniach-Sunjic":
                asymmetry = 'higher'
                if not bindingscale:
                    asymmetry = 'lower'
                return Fitter.doniach_sunjic(energy, params[Peak.peak_types[model][0]]['value'],
                                             params[Peak.peak_types[model][1]]['value'],
                                             params[Peak.peak_types[model][2]]['value'],
                                             params[Peak.peak_types[model][3]]['value'],
                                             asymmetry=asymmetry)
        elif model in Fitter.bg_types:
            if model == 'shirley':
                return getattr(Fitter, model)(energy, intensity, params['value'])
            else:
                return getattr(Fitter, model)(energy, params['value'])
        else:
            raise KeyError(f"'{model}' is not a valid fitting model")

    @staticmethod
    def get_model_func(model):
        if model in Peak.peak_types:
            if model == "Gauss":
                return Fitter.gauss
            if model == "Lorentz":
                return Fitter.lorentz
            if model == "Pseudo Voigt":
                return Fitter.pseudo_voigt
            if model == "Doniach-Sunjic":
                return Fitter.doniach_sunjic
        elif model in Fitter.bg_types:
            if model == 'shirley':
                return Fitter.shirley
            else:
                return getattr(Fitter, model)
        else:
            raise KeyError(f"'{model}' is not a valid fitting model")

    @staticmethod
    def constant(energy, value: float, asymmetry=None):
        """Calculates constant background for simulated spectrum
        """
        return np.ones_like(energy) * value

    @staticmethod
    def linear(energy, value: float, asymmetry=None):
        """Calculates linear background for simulated spectrum
        """
        bg = np.zeros_like(energy)
        if energy[0] < energy[-1]:
            need_to_reversed = False
        else:
            need_to_reversed = True
            energy = energy[::-1]
        bg = bg + (energy - energy[0]) * value
        if need_to_reversed:
            return bg[::-1]
        else:
            return bg

    @staticmethod
    def square(energy, value: float, asymmetry=None):
        """Calculates square background for simulated spectrum
        """
        bg = np.zeros_like(energy)
        if energy[0] < energy[-1]:
            need_to_reversed = False
        else:
            need_to_reversed = True
            energy = energy[::-1]
        bg = bg + np.square((energy - energy[0])) * value
        if need_to_reversed:
            return bg[::-1]
        else:
            return bg

    @staticmethod
    def shirley(energy, intensity, value: float, asymmetry=None):
        """Calculates Shirley background for simulated spectrum
        """
        if energy[0] < energy[-1]:
            is_reversed = True
            energy = energy[::-1]
            intensity = intensity[::-1]
        else:
            is_reversed = False
        spacing = (energy[-1] - energy[0]) / (len(energy) - 1)
        output = value * spacing * (np.cumsum(intensity) - intensity.sum())
        if is_reversed:
            return output[::-1]
        return output

        # bg = np.zeros_like(energy)
        # if energy[0] < energy[-1]:
        #     need_to_reversed = False
        # else:
        #     need_to_reversed = True
        #     intensity = intensity[::-1]
        # bg = bg + (np.cumsum(intensity) - intensity) * value
        # if need_to_reversed:
        #     return bg[::-1]
        # else:
        #     return bg

    @staticmethod
    def lorentz(x, amp, cen, l_fwhm, asymmetry=None):
        gamma = l_fwhm / 2
        return amp * 1. / (np.pi * gamma * (1 + ((x - cen) / gamma) ** 2))

    @staticmethod
    def gauss(x, amp, cen, g_fwhm, asymmetry=None):
        sigma = g_fwhm / (2 * np.sqrt(2 * np.log(2)))
        return amp * 1. / np.sqrt(2 * np.pi * sigma ** 2) * np.exp(-(x - cen) ** 2 / (2 * sigma ** 2))

    @staticmethod
    def pseudo_voigt(x, amp, cen, g_fwhm, l_fwhm, asymmetry=None):
        """Returns a pseudo Voigt lineshape, used for photo-emission.
        :param x: X data
        :param amp: amplitude
        :param cen: center
        :param g_fwhm: Gauss FWHM
        :param l_fwhm: Lorentz FWHM
        :return: Pseudo Voigt line shape
        """
        f = (g_fwhm ** 5 + 2.69269 * g_fwhm ** 4 * l_fwhm + 2.42843 * g_fwhm ** 3 * l_fwhm ** 2 +
             4.47163 * g_fwhm ** 2 * l_fwhm ** 3 + 0.07842 * g_fwhm * l_fwhm ** 4 + l_fwhm ** 5) ** (1. / 5.)
        eta = 1.36603 * (l_fwhm / f) - 0.47719 * (l_fwhm / f) ** 2 + 0.11116 * (l_fwhm / f) ** 3
        pv_func = (eta * Fitter.lorentz(x, 1.0, cen, f) + (1 - eta) * Fitter.gauss(x, 1.0, cen, f))
        return amp * pv_func / np.amax(pv_func)  # Normalizing to 1

    @staticmethod
    def doniach_sunjic(x, amp, cen, g_fwhm, l_fwhm, asymmetry='higher'):
        """Returns a Doniach Sunjic asymmetric lineshape, used for photo-emission.
        Formula taken from https://lmfit.github.io/lmfit-py/builtin_models.html
        :param x: X data
        :param amp: amplitude
        :param cen: center
        :param g_fwhm: Gauss FWHM
        :param l_fwhm: Lorentz FWHM
        :param asymmetry: one of ('higher', 'lower') defines whether the secondary electrons background shall be added
        towards higher energy values (the case of binding energy representation) or lower energy values (the case
        of kinetic energy representation)
        :return: Doniach-Sunjic assimetric line shape
        """
        assert asymmetry in ('higher', 'lower')
        if x[0] > x[1]:
            reverse = True
        else:
            reverse = False
        if reverse:
            x = x[::-1]
        if asymmetry == 'higher':
            asymmetry = cen - x
        elif asymmetry == 'lower':
            asymmetry = x - cen
        else:
            fitter_logger.warning("Only 'higher' or 'lower' values are possible for asymmetry parameter.")

        sigma = g_fwhm / (2 * np.sqrt(2 * np.log(2)))
        gamma = l_fwhm / 2
        func_numerator = np.cos(np.pi * gamma / 2 + (1.0 - gamma) * np.arctan((asymmetry) / sigma))
        func_denominator = (1 + ((asymmetry) / sigma) ** 2) ** ((1.0 - gamma) / 2)
        ds_func = (amp / sigma ** (1.0 - gamma)) * func_numerator / func_denominator

        if reverse:
            return ds_func[::-1]
        return ds_func

    def _get_fitting_restrains(self, initial_params, fix_pars=None, tolerance=0.0001, boundaries=None):
        """Parses fitting restrains for multiple peaks
        :param initial_params: initial values of multiple of three (or four) parameters:
        amplitude, center, (g_fwhm - optional), and l_fwhm
        :param fix_pars: dictionary with names of parameters to fix as keys and numbers of peaks for which
        the parameters should be fixed as lists. Ex: {"cen": [1,2], "amp": [0,1,2]}
        :param tolerance: when fixing parameters some small tolerance is necessary for fitting
        :param boundaries: dictionary with names of parameters as keys and a dictionary containing lower and upper
        boundaries for the corresponding peak. Ex: {"cen": {1: [34,35], 2: [35,36]}}
        :return: Two lists: lower boundaries and upper boundaries (same order as in initial_params)
        """
        peak_pars_cnt = 0
        if len(initial_params) % 3 == 0:
            peak_pars_cnt = 3  # Fitting three-parameter function
        if len(initial_params) % 4 == 0:
            peak_pars_cnt = 4  # Fitting four-parameter function

        bounds_low = []
        bounds_high = []
        for i in range(0, len(initial_params)):
            if i % peak_pars_cnt == 0:  # Adjusting amplitude parameter boundaries
                peak_number = i // peak_pars_cnt
                if fix_pars and ("amplitude" in fix_pars):
                    if peak_number in fix_pars["amplitude"]:
                        bounds_low.append(initial_params[i] - tolerance)
                        bounds_high.append(initial_params[i] + tolerance)
                        continue
                if boundaries and ("amplitude" in boundaries):
                    if peak_number in boundaries["amplitude"]:
                        if len(boundaries["amplitude"][peak_number]) == 2 and None not in boundaries["amplitude"][peak_number]:
                            bounds_low.append(min(boundaries["amplitude"][peak_number]))
                            bounds_high.append(max(boundaries["amplitude"][peak_number]))
                            continue
                # If amplitude is not fixed and not restrained,
                # fix the lower limit at 0 and the upper limit at data_y max
                bounds_low.append(0)
                # The upper boundary of amplitude should not be lower than the value of initial guess
                if initial_params[i] < np.amax(self._Y_data):
                    bounds_high.append(np.amax(self._Y_data))
                else:
                    bounds_high.append(initial_params[i])
                continue
            if (i - 1) % peak_pars_cnt == 0:  # Adjusting center parameters boundaries
                peak_number = (i - 1) // peak_pars_cnt
                if fix_pars and ("center" in fix_pars):
                    if peak_number in fix_pars["center"]:
                        bounds_low.append(initial_params[i] - tolerance)
                        bounds_high.append(initial_params[i] + tolerance)
                        continue
                if boundaries and ("center" in boundaries):
                    if peak_number in boundaries["center"]:
                        if len(boundaries["center"][peak_number]) == 2 and None not in boundaries["center"][peak_number]:
                            bounds_low.append(min(boundaries["center"][peak_number]))
                            bounds_high.append(max(boundaries["center"][peak_number]))
                            continue
            if (i - 2) % peak_pars_cnt == 0:  # Adjusting single (or first) fwhm parameters boundaries
                peak_number = (i - 2) // peak_pars_cnt
                if fix_pars and ("g_fwhm" in fix_pars):
                    if peak_number in fix_pars["g_fwhm"]:
                        bounds_low.append(initial_params[i] - tolerance)
                        bounds_high.append(initial_params[i] + tolerance)
                        continue
                elif fix_pars and ("l_fwhm" in fix_pars):
                    if peak_number in fix_pars["l_fwhm"]:
                        bounds_low.append(initial_params[i] - tolerance)
                        bounds_high.append(initial_params[i] + tolerance)
                        continue
                if boundaries and ("g_fwhm" in boundaries):
                    if peak_number in boundaries["g_fwhm"]:
                        if len(boundaries["g_fwhm"][peak_number]) == 2 and None not in boundaries["g_fwhm"][peak_number]:
                            bounds_low.append(min(boundaries["g_fwhm"][peak_number]))
                            bounds_high.append(max(boundaries["g_fwhm"][peak_number]))
                            continue
                elif boundaries and ("l_fwhm" in boundaries):
                    if peak_number in boundaries["l_fwhm"]:
                        if len(boundaries["l_fwhm"][peak_number]) == 2 and None not in boundaries["l_fwhm"][peak_number]:
                            bounds_low.append(min(boundaries["l_fwhm"][peak_number]))
                            bounds_high.append(max(boundaries["l_fwhm"][peak_number]))
                            continue
            if peak_pars_cnt == 4:  # Adjusting second fwhm parameters boundaries
                if (i - 3) % peak_pars_cnt == 0:  # Adjusting fwhm parameters boundaries
                    peak_number = (i - 3) // peak_pars_cnt
                    if fix_pars and ("l_fwhm" in fix_pars):
                        if peak_number in fix_pars["l_fwhm"]:
                            bounds_low.append(initial_params[i] - tolerance)
                            bounds_high.append(initial_params[i] + tolerance)
                            continue
                    if boundaries and ("l_fwhm" in boundaries):
                        if peak_number in boundaries["l_fwhm"]:
                            if len(boundaries["l_fwhm"][peak_number]) == 2 and None not in boundaries["l_fwhm"][peak_number]:
                                bounds_low.append(min(boundaries["l_fwhm"][peak_number]))
                                bounds_high.append(max(boundaries["l_fwhm"][peak_number]))
                                continue
            bounds_low.append(-np.inf)
            bounds_high.append(np.inf)

        return bounds_low, bounds_high

    def fit_gaussian(self, initial_params, fix_pars=None, tolerance=0.0001, boundaries=None):
        """Fits Gaussian function to Region object based on initial values
        of three parameters (amplitude, center, and fwhm). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        :param initial_params: list of initial values of parameters: amplitude, center, g_fwhm. Must contain a multiple
        of 3 values.
        :param fix_pars: dictionary with names of parameters to fix as keys and numbers of peaks for which
        the parameters should be fixed as lists. Ex: {"cen": [1,2], "amp": [0,1,2]}
        :param tolerance: when fixing parameters some small tolerance is necessary for fitting
        :param boundaries: dictionary with names of parameters as keys and a dictionary containing lower and upper
        boundaries for the corresponding peak. Ex: {"cen": {1: [34,35], 2: [35,36]}}
        """
        def _multi_gaussian(x, *args):
            cnt = 0
            func = 0
            while cnt < len(args):
                amp = args[cnt]
                cen = args[cnt + 1]
                g_fwhm = args[cnt + 2]
                func += Fitter.gauss(x, amp, cen, g_fwhm)
                cnt += 3
            return func

        if len(initial_params) % 3 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fit_gaussian method. "
                                f"Should be multiple of 3.")
            return
        bounds_low, bounds_high = self._get_fitting_restrains(initial_params, fix_pars, tolerance, boundaries)
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_multi_gaussian, self._X_data, self._Y_data, p0=initial_params,
                               bounds=(bounds_low, bounds_high))

        cnt = 0
        while cnt < len(initial_params):
            peak_y = _multi_gaussian(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2])
            if type(peak_y) == int:
                self._Peaks[cnt // 3] = None
            else:
                self._Peaks[cnt // 3] = Peak(self._X_data, peak_y,
                                           [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                           [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                           peak_func=_multi_gaussian,
                                           peak_id=cnt // 3, peak_type=list(Peak.peak_types.keys())[0])
            cnt += 3

        self.make_fitline()

    def fit_lorentzian(self, initial_params, fix_pars=None, tolerance=0.0001, boundaries=None):
        """Fits Lorentzian (Cauchy) function to Region object based on initial values
        of three parameters (amplitude, center, and fwhm). If list with more than
        one set of three parameters is given, the function fits more than one peak.
        :param initial_params: list of initial values of parameters: amplitude, center, l_fwhm. Must contain a multiple
        of 3 values.
        :param fix_pars: dictionary with names of parameters to fix as keys and numbers of peaks for which
        the parameters should be fixed as lists. Ex: {"cen": [1,2], "amp": [0,1,2]}
        :param tolerance: when fixing parameters some small tolerance is necessary for fitting
        :param boundaries: dictionary with names of parameters as keys and a dictionary containing lower and upper
        boundaries for the corresponding peak. Ex: {"cen": {1: [34,35], 2: [35,36]}}
        """
        def _multi_lorentzian(x, *args):
            """Creates a single or multiple Lorentzian shape taking amplitude, Center
            and FWHM parameters
            """
            cnt = 0
            func = 0
            while cnt < len(args):
                amp = args[cnt]
                cen = args[cnt + 1]
                l_fwhm = args[cnt + 2]
                func += Fitter.lorentz(x, amp, cen, l_fwhm)
                cnt += 3
            return func

        if len(initial_params) % 3 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fit_lorentzian method. "
                                f"Should be multiple of 3.")
            return
        bounds_low, bounds_high = self._get_fitting_restrains(initial_params, fix_pars, tolerance, boundaries)
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_multi_lorentzian, self._X_data, self._Y_data, p0=initial_params,
                               bounds=(bounds_low, bounds_high))
        cnt = 0
        while cnt < len(initial_params):
            peak_y = _multi_lorentzian(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2])
            if type(peak_y) == int:
                self._Peaks[cnt // 3] = None
            else:
                self._Peaks[cnt // 3] = Peak(self._X_data, peak_y,
                                             [popt[cnt], popt[cnt+1], popt[cnt+2]],
                                             [pcov[cnt], pcov[cnt+1], pcov[cnt+2]],
                                             peak_func=_multi_lorentzian,
                                             peak_id=cnt // 3, peak_type=list(Peak.peak_types.keys())[1])
            cnt += 3
        self.make_fitline()

    def fit_pseudo_voigt(self, initial_params, fix_pars=None, tolerance=0.0001, boundaries=None):
        """Fits Pseudo-Voigt function to Region object based on initial values
        of four parameters (amplitude, center, gauss_fwhm, lorentz_fwhm). If list with more than
        one set of four parameters is given, the function fits more than one peak.
        :param initial_params: list of initial values of parameters: amplitude, center, g_fwhm, l_fwhm. Must contain a
        multiple of 4 values.
        :param fix_pars: dictionary with names of parameters to fix as keys and numbers of peaks for which
        the parameters should be fixed as lists. Ex: {"cen": [1,2], "amp": [0,1,2]}
        :param tolerance: when fixing parameters some small tolerance is necessary for fitting
        :param boundaries: dictionary with names of parameters as keys and a dictionary containing lower and upper
        boundaries for the corresponding peak. Ex: {"cen": {1: [34,35], 2: [35,36]}}
        """
        def _multi_voigt(x, *args):
            """Creates a single or multiple Voigt shape taking amplitude, Center, g_FWHM and l_FWHM parameters
            """
            cnt = 0
            func = 0
            while cnt < len(args):
                amp = args[cnt]
                cen = args[cnt + 1]
                g_fwhm = args[cnt + 2]
                l_fwhm = args[cnt + 3]
                func += Fitter.pseudo_voigt(x, amp, cen, g_fwhm, l_fwhm)
                cnt += 4
            return func

        if len(initial_params) % 4 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fit_pseudo_voigt method."
                                f"Should be multiple of 4.")
            return
        bounds_low, bounds_high = self._get_fitting_restrains(initial_params, fix_pars, tolerance, boundaries)
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_multi_voigt, self._X_data, self._Y_data, p0=initial_params,
                               bounds=(bounds_low, bounds_high))

        cnt = 0
        while cnt < len(initial_params):
            peak_y = _multi_voigt(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2], popt[cnt + 3])
            if type(peak_y) == int:
                self._Peaks[cnt // 4] = None
            else:
                self._Peaks[cnt // 4] = Peak(self._X_data, peak_y,
                                             [popt[cnt], popt[cnt+1], popt[cnt+2], popt[cnt+3]],
                                             [pcov[cnt], pcov[cnt+1], pcov[cnt+2], pcov[cnt+3]],
                                             peak_func=_multi_voigt,
                                             peak_id=cnt // 4, peak_type=list(Peak.peak_types.keys())[2])
            cnt += 4
        self.make_fitline()

    def fit_doniach_sunjic(self, initial_params, fix_pars=None, tolerance=0.0001, boundaries=None):
        """Fits Doniach-Sunjic assimetric function (Formula taken from https://lmfit.github.io/lmfit- py/builtin_models.html)
        to Region object based on initial values of four parameters (amplitude, center, gauss_fwhm, lorentz_fwhm).
        If list with more than one set of four parameters is given, the function fits more than one peak.
        :param initial_params: list of initial values of parameters: amplitude, center, g_fwhm, l_fwhm. Must contain a
        multiple of 4 values.
        :param fix_pars: dictionary with names of parameters to fix as keys and numbers of peaks for which
        the parameters should be fixed as lists. Ex: {"cen": [1,2], "amp": [0,1,2]}
        :param tolerance: when fixing parameters some small tolerance is necessary for fitting
        :param boundaries: dictionary with names of parameters as keys and a dictionary containing lower and upper
        boundaries for the corresponding peak. Ex: {"cen": {1: [34,35], 2: [35,36]}}
        """

        def _multi_doniach_sunjic_higher(x, *args):
            """Creates a single or multiple Voigt shape taking amplitude, Center, g_FWHM and l_FWHM parameters
            """
            cnt = 0
            func = 0
            while cnt < len(args):
                amp = args[cnt]
                cen = args[cnt + 1]
                g_fwhm = args[cnt + 2]
                l_fwhm = args[cnt + 3]
                func += Fitter.doniach_sunjic(x, amp, cen, g_fwhm, l_fwhm, asymmetry='higher')
                cnt += 4
            return func

        def _multi_doniach_sunjic_lower(x, *args):
            """Creates a single or multiple Voigt shape taking amplitude, Center, g_FWHM and l_FWHM parameters
            """
            cnt = 0
            func = 0
            while cnt < len(args):
                amp = args[cnt]
                cen = args[cnt + 1]
                g_fwhm = args[cnt + 2]
                l_fwhm = args[cnt + 3]
                func += Fitter.doniach_sunjic(x, amp, cen, g_fwhm, l_fwhm, asymmetry='lower')
                cnt += 4
            return func

        fitfunc = _multi_doniach_sunjic_higher
        if not self.region.is_binding():
            fitfunc = _multi_doniach_sunjic_lower

        if len(initial_params) % 4 != 0:
            fitter_logger.debug(f"Check the number of initial parameters in fit_doniach_sunjic method."
                                f"Should be multiple of 4.")
            return
        bounds_low, bounds_high = self._get_fitting_restrains(initial_params, fix_pars, tolerance, boundaries)
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(fitfunc, self._X_data, self._Y_data, p0=initial_params,
                               bounds=(bounds_low, bounds_high))

        cnt = 0
        while cnt < len(initial_params):
            peak_y = fitfunc(self._X_data, popt[cnt], popt[cnt + 1], popt[cnt + 2], popt[cnt + 3])
            if type(peak_y) == int:
                self._Peaks[cnt // 4] = None
            else:
                self._Peaks[cnt // 4] = Peak(self._X_data, peak_y,
                                             [popt[cnt], popt[cnt+1], popt[cnt+2], popt[cnt+3]],
                                             [pcov[cnt], pcov[cnt+1], pcov[cnt+2], pcov[cnt+3]],
                                             peak_func=fitfunc,
                                             peak_id=cnt // 4, peak_type=list(Peak.peak_types.keys())[3])
            cnt += 4
        self.make_fitline()

    def make_fitline(self, usebg=False):
        """Calculates the total fit line including all peaks and calculates the
        residuals and r-squared.
        """
        # Calculate fit line
        for peak in self._Peaks.values():
            if peak:
                self._FitLine += peak.get_data()[1]
        if usebg and self._Bg is not None:
            for key, val in self._Bg.items():
                self._FitLine += self.get_model(key, self._X_data, self._Y_data, val)
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

    def get_bg(self):
        if self._Bg is None:
            return None
        bg_dict = {}
        for key, val in self._Bg.items():
            if type(val['value']) == float:
                bg_dict[key] = [val['value'], 0.0]
            else:
                bg_dict[key] = [val['value'].value, val['value'].stderr]
        return bg_dict

    def get_fit_line(self):
        """Returns x and y coordinates for the fit line based on all fitted peaks
        """
        if not self._FitLine.size == 0:
            return self._FitLine
        fitter_logger.warning("Can't get Fit Line from a Fitter instance. Do fit first.")

    def get_virtual_bg(self, num=10, multiply=True):
        """Returns the bg (x,y) with more (or less) data points.
        If multiply==False, value of 'num' is taken as desired number of ponts.
        If multiply==True, multiplies the existing number of points by value of 'num'. For plotting a smoother curve,
        for example.
        :param num: Number of desired points or multiplicator
        :param multiply: True if num is multiplicator, False if num is absolute number of points
        :return (ndarray, ndarray) x and y data with desired number of points
        """
        if multiply:
            bg_virtual_x = np.linspace(self._X_data[0], self._X_data[-1], len(self._X_data) * num, endpoint=True)
        else:
            bg_virtual_x = np.linspace(self._X_data[0], self._X_data[-1], num, endpoint=True)
        bg_virtual_y = np.zeros_like(bg_virtual_x)

        if self._Bg is not None:
            total_bg_y = np.zeros_like(self._Y_data)
            for key, val in self._Bg.items():
                total_bg_y += self.get_model(key, self._X_data, self._Y_data, val)

            x = list(range(len(self._X_data)))
            new_x = np.linspace(0, max(x), len(bg_virtual_x), endpoint=True)
            bg_virtual_y = np.interp(new_x, x, total_bg_y)

        return bg_virtual_x, bg_virtual_y

    def get_virtual_fitline(self, num=10, multiply=True, usebg=False):
        """Returns the fitline (x,y) with more (or less) data points.
        If multiply==False, value of 'num' is taken as desired number of ponts.
        If multiply==True, multiplies the existing number of points by value of 'num'. For plotting a smoother curve,
        for example.
        :param num: Number of desired points or multiplicator
        :param multiply: True if num is multiplicator, False if num is absolute number of points
        :return (ndarray, ndarray) x and y data with desired number of points
        """
        fitline_x, fitline_y = None, None
        for i, peak in enumerate(self._Peaks.values()):
            if peak:
                peak_data = peak.get_virtual_data(num=num, multiply=multiply)
                if i == 0:
                    fitline_x, fitline_y = peak_data
                else:
                    _, fy = peak_data
                    fitline_y += fy
        if usebg:
            _, bg_y = self.get_virtual_bg(num=num, multiply=multiply)
            fitline_y += bg_y
        return fitline_x, fitline_y

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
    def get_peaks(self, peak_id=None):
        if len(self._Peaks) == 0:
            fitter_logger.warning("Can't get peaks from a Fitter instance. Do fit first.")
            return
        if peak_id is None:
            return list(self._Peaks.values())
        else:
            if peak_id in self._Peaks:
                return self._Peaks[peak_id]
            else:
                fitter_logger.warning(f"Fitter {self._ID} does not contain peak {peak_id}.")
                return

    def get_data(self):
        return [self._X_data, self._Y_data]

    def get_id(self):
        return self._ID

    def get_global_gauss_fwhm(self):
        return self._global_gauss_fwhm


