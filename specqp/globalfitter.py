import copy
import logging

import numpy as np
from lmfit import Parameters, minimize

from specqp import helpers
from specqp.fitter import Fitter, Peak

globalfitter_logger = logging.getLogger("specqp.globalfitter")  # Creating child logger


class GlobalFit:
    def __init__(self, regions, peaks_info, bg_params, y_data='final'):
        if not helpers.is_iterable(regions):
            self._Regions = [regions]
        else:
            self._Regions = regions
        self._Data = []
        self._Fitters = []
        for region in self._Regions:
            basic_data = {
                'scan': region.get_id(),
                'energy': region.get_data('energy'),
                'intensity': region.get_data(y_data)
            }
            self._Data.append(basic_data)
            self._Fitters.append(Fitter(region, y_data=y_data))
        self._FitParams = Parameters()
        self._PeaksInfo = copy.deepcopy(peaks_info)
        self._BgParams = copy.deepcopy(bg_params)
        for bgpar in self._BgParams.values():
            if bgpar['min'] is None or bgpar['min'] == "":
                bgpar['min'] = -np.inf
            if bgpar['max'] is None or bgpar['max'] == "":
                bgpar['max'] = np.inf
        self._BaseValues = {}

        self.bindingscale = True
        if not self._Regions[0].is_binding():
            self.bindingscale = False

        self.make_initial_params()

    @staticmethod
    def get_param_error(peak_name, param_data, param_name, fit_params, spectra_ind):
        if param_data['dependencetype'] == 'Dependent +':
            return (fit_params[f"{param_data['dependencebase']}_{param_name}_{spectra_ind}"].stderr ** 2 +
                    fit_params[f'{peak_name}_{param_name}_{spectra_ind}'].stderr ** 2) ** 0.5
        elif param_data['dependencetype'] == 'Dependent *':
            return ((fit_params[f"{param_data['dependencebase']}_{param_name}_{spectra_ind}"].stderr /
                     fit_params[f"{param_data['dependencebase']}_{param_name}_{spectra_ind}"].value) ** 2 +
                    (fit_params[f'{peak_name}_{param_name}_{spectra_ind}'].stderr /
                     fit_params[f'{peak_name}_{param_name}_{spectra_ind}'].value) ** 2) ** 0.5
        else:
            return fit_params[f'{peak_name}_{param_name}_{spectra_ind}'].stderr

    def get_bg_values(self, fit_params, spectra_ind):
        local_bg = copy.deepcopy(self._BgParams)
        if fit_params:
            for bg_type, params in local_bg.items():
                params['value'] = fit_params[f'bg_{bg_type}_{spectra_ind}']
        return local_bg

    def sim_spectra(self, fit_params, spectra_ind):
        """Defines the model for the fit (doniach, voigt, shirley bg, linear bg
        """
        line = np.zeros_like(self._Data[spectra_ind]['intensity'])
        bg = np.zeros_like(self._Data[spectra_ind]['intensity'])
        local_bg = self.get_bg_values(fit_params, spectra_ind)
        peaks = copy.deepcopy(self._PeaksInfo)
        for peak in peaks:
            if fit_params:
                for param_name, param_data in peak['parameters'].items():
                    param_data['value'] = fit_params[f"{peak['peakname']}_{param_name}_{spectra_ind}"]
            line += Fitter.get_model(peak['fittype'], self._Data[spectra_ind]['energy'],
                                     self._Data[spectra_ind]['intensity'], peak['parameters'],
                                     bindingscale=self.bindingscale)
        for fittype, params in local_bg.items():
            bg += Fitter.get_model(fittype, self._Data[spectra_ind]['energy'], line, params)
        line += bg
        return line, bg

    def err_func(self, fit_params):
        """ calculate total residual for fits to several data sets held
        in a 2-D array, and modeled by model function"""
        residuals = []
        for ind in range(len(self._Regions)):
            spectra, _ = self.sim_spectra(fit_params, ind)
            residuals.append(self._Data[ind]['intensity'] - spectra)
        return [item for innerlist in residuals for item in innerlist]

    def make_initial_params(self):
        """
        Creates a dictionary of parameters based on initially provided values
        :return: Dictionary of parameters for lmfit.minimize method
        """
        def get_min_first(region, pos):
            if pos == 'first':
                if region['energy'][0] > region['energy'][1]:
                    return region['intensity'][-1]
                else:
                    return region['intensity'][0]
            elif pos == 'min':
                return np.min(region['intensity'])

        # Adding background parameters to the dictionary
        try:
            for bgtype, bg_params in self._BgParams.items():
                vary = True
                if bg_params['fix']:
                    vary = False
                for ind in range(len(self._Regions)):
                    if bgtype == 'constant':
                        if bg_params['value'] in ['first', 'min']:
                            value = get_min_first(self._Data[ind], bg_params['value'])
                        else:
                            value = float(bg_params['value'])
                        if bg_params['min'] in ['first', 'min']:
                            min_ = get_min_first(self._Data[ind], bg_params['value'])
                        else:
                            min_ = float(bg_params['min'])
                        if bg_params['max'] in ['first', 'min']:
                            max_ = get_min_first(self._Data[ind], bg_params['value'])
                        else:
                            max_ = float(bg_params['max'])
                    else:
                        value = float(bg_params['value'])
                        min_ = float(bg_params['min'])
                        max_ = float(bg_params['max'])
                    self._FitParams.add(f'bg_{bgtype}_{ind}', value=value, min=min_, max=max_, vary=vary)
        except ValueError:
            self._FitParams.add(f'bg_{bgtype}_{ind}', value=0.0, min=0.0, max=0.0, vary=False)
            globalfitter_logger.warning("Check background values.")

        # Adding peak parameters to the dictionary
        common = {}
        for peak in self._PeaksInfo:
            for param_name, param_data in peak['parameters'].items():
                if param_data['min'] is None or param_data['min'] == "":
                    param_data['min'] = -np.inf
                if param_data['max'] is None or param_data['max'] == "":
                    param_data['max'] = np.inf
                vary = True
                if param_data['fix']:
                    vary = False
                for ind in range(len(self._Regions)):
                    if param_data['dependencetype'] == 'Independent':
                        self._FitParams.add(f"{peak['peakname']}_{param_name}_{ind}", value=param_data['value'],
                                            min=param_data['min'], max=param_data['max'], vary=vary)
                    elif param_data['dependencetype'] == 'Dependent +':
                        self._FitParams.add(f"{peak['peakname']}_{param_name}_{ind}_base", value=param_data['value'],
                                            min=param_data['min'],
                                            max=param_data['max'],
                                            vary=vary)
                        self._FitParams.add(f"{peak['peakname']}_{param_name}_{ind}",
                                            value=self._FitParams[f"Peak{param_data['dependencebase']}_{param_name}_{ind}"].value + param_data['value'],
                                            min=self._FitParams[f"Peak{param_data['dependencebase']}_{param_name}_{ind}"].min + param_data['min'],
                                            max=self._FitParams[f"Peak{param_data['dependencebase']}_{param_name}_{ind}"].max + param_data['max'],
                                            vary=vary,
                                            expr=f"Peak{param_data['dependencebase']}_{param_name}_{ind} + {peak['peakname']}_{param_name}_{ind}_base")
                    elif param_data['dependencetype'] == 'Dependent *':
                        self._FitParams.add(f"{peak['peakname']}_{param_name}_{ind}_base", value=param_data['value'],
                                            min=param_data['min'],
                                            max=param_data['max'],
                                            vary=vary)
                        self._FitParams.add(f"{peak['peakname']}_{param_name}_{ind}",
                                            value=self._FitParams[f"Peak{param_data['dependencebase']}_{param_name}_{ind}"].value * param_data['value'],
                                            min=self._FitParams[f"Peak{param_data['dependencebase']}_{param_name}_{ind}"].min * param_data['min'],
                                            max=self._FitParams[f"Peak{param_data['dependencebase']}_{param_name}_{ind}"].max * param_data['max'],
                                            vary=vary,
                                            expr=f"Peak{param_data['dependencebase']}_{param_name}_{ind} * {peak['peakname']}_{param_name}_{ind}_base")
                    elif param_data['dependencetype'] == 'Common':
                        if not ind == 0:
                            common[f"{peak['peakname']}_{param_name}_{ind}"] = f"{peak['peakname']}_{param_name}_{0}"
                        self._FitParams.add(f"{peak['peakname']}_{param_name}_{ind}", value=param_data['value'],
                                            min=param_data['min'], max=param_data['max'], vary=vary)

        if len(common) > 0:
            for key, val in common.items():
                self._FitParams[key].expr = val

    def fit(self):
        """Calls minimize from lmfit using the objective function and the parameters
        """
        result = minimize(self.err_func, self._FitParams, method='least_squares')
        for i, fitterobj in enumerate(self._Fitters):
            for peak in self._PeaksInfo:
                peak_pars = {}
                peak_errs = {}
                for key, val in peak['parameters'].items():
                    peak_pars[key] = result.params[f"{peak['peakname']}_{key}_{i}"].value
                    peak_errs[key] = result.params[f"{peak['peakname']}_{key}_{i}"].stderr
                asymmetry = 'higher'
                if not self.bindingscale:
                    asymmetry = 'lower'
                peak_y = Fitter.get_model_func(peak['fittype'])(fitterobj.get_data()[0], *peak_pars.values(),
                                                                asymmetry=asymmetry)
                peak = Peak(fitterobj.get_data()[0], peak_y, [*peak_pars.values()], [*peak_errs.values()],
                            peak_func=Fitter.get_model_func(peak['fittype']),
                            peak_id=peak['peakname'], peak_type=peak['fittype'],
                            bindingscale=self.bindingscale,
                            lmfit=True)
                fitterobj.add_peak(peak)
            if len(self._BgParams) > 0:
                fitterobj._Bg = self.get_bg_values(result.params, i)
                fitterobj.make_fitline(usebg=True)
            else:
                fitterobj.make_fitline(usebg=False)
        return self._Fitters
