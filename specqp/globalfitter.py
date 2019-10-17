## Module globalfitter.py originally written by
# Yury Matveev yury.matveev@desy.de
# Patrick Loemker patrick.loemker@desy.de
# Adopted by
# Mikhail Shipilin mikhail.shipilin@fysik.su.se

import numpy as np
import copy
from matplotlib import pyplot as plt
from matplotlib.widgets import Slider
from lmfit import Parameters, minimize
from specqp import helpers
from specqp.fitter import Fitter, Peak


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
        self._BaseValues = {}

        self.make_params()

    def get_param_value(self, peak_name, param_data, param_name, fit_params, spectra_ind):
        if not param_data['fix']:
            if param_data['dependencetype'] == 'Independent':
                return 0 + fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)]
            elif param_data['dependencetype'] == 'Common +':
                return param_data['value'] + fit_params['{}_{}'.format(peak_name, param_name)]
            elif param_data['dependencetype'] == 'Common *':
                return param_data['value'] * fit_params['{}_{}'.format(peak_name, param_name)]
            elif param_data['dependencetype'] == 'Dependent +':
                return fit_params['Peak{}_{}_{}'.format(param_data['dependencebase'], param_name, spectra_ind)] + \
                       fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)]
            elif param_data['dependencetype'] == 'Dependent *':
                return fit_params['Peak{}_{}_{}'.format(param_data['dependencebase'], param_name, spectra_ind)] * \
                       fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)]
            elif param_data['dependencetype'] == 'Dependent on fixed +':
                return self._BaseValues['{}_{}_{}'.format(peak_name, param_name, spectra_ind)] + \
                       fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)]
            elif param_data['dependencetype'] == 'Dependent on fixed *':
                return self._BaseValues['{}_{}_{}'.format(peak_name, param_name, spectra_ind)] * \
                       fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)]
            else:
                raise RuntimeError('Unknown model')
        else:
            if param_data['dependencetype'] == 'Dependent +':
                return fit_params['Peak{}_{}_{}'.format(param_data['dependencebase'], param_name, spectra_ind)] + \
                       param_data['value']
            elif param_data['dependencetype'] == 'Dependent *':
                return fit_params['Peak{}_{}_{}'.format(param_data['dependencebase'], param_name, spectra_ind)] * \
                       param_data['value']
            else:
                return param_data['value']

    def get_param_error(self, peak_name, param_data, param_name, fit_params, spectra_ind):
        try:
            if not param_data['fix']:
                if param_data['dependencetype'] == 'Independent':
                    return 0 + fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)].stderr
                elif param_data['dependencetype'] == 'Common +':
                    return 0 + fit_params['{}_{}'.format(peak_name, param_name)].stderr
                elif param_data['dependencetype'] == 'Common *':
                    return param_data['value'] * fit_params['{}_{}'.format(peak_name, param_name)].stderr
                elif param_data['dependencetype'] in ('Dependent +', 'Dependent *'):
                    return fit_params['Peak{}_{}_{}'.format(param_data['dependencebase'], param_name, spectra_ind)].stderr + \
                           fit_params['{}_{}_{}'.format(peak_name, param_name, spectra_ind)].stderr
                else:
                    raise RuntimeError('Unknown model')
            else:
                if param_data['dependencetype'] in ('Dependent +', 'Dependent *'):
                    return fit_params['Peak{}_{}_{}'.format(param_data['dependencebase'], param_name, spectra_ind)].stderr * \
                           param_data['value']
                else:
                    return 0
        except:
            return 0

    def get_bg_values(self, fit_params, spectra_ind):

        local_bg = copy.deepcopy(self._BgParams)

        if fit_params:
            for bg_type, params in local_bg.items():
                if not params['fix']:
                    params['value'] = fit_params['bg_{}_{}'.format(bg_type, spectra_ind)]
                if bg_type == 'constant':
                    if params['value'] == 'first':
                        if self._Data[spectra_ind]['energy'][0] < self._Data[spectra_ind]['energy'][-1]:
                            params['value'] = self._Data[spectra_ind]['intensity'][0]
                        else:
                            params['value'] = self._Data[spectra_ind]['intensity'][-1]
                    elif params['value'] == 'min':
                        params['value'] = np.min(self._Data[spectra_ind]['intensity'])
        return local_bg

    def sim_spectra(self, spectra_ind, fit_params):
        """Defines the model for the fit (doniachs, voigts, shirley bg, linear bg
        """
        line = np.zeros_like(self._Data[spectra_ind]['intensity'])
        bg = np.zeros_like(self._Data[spectra_ind]['intensity'])
        local_bg = self.get_bg_values(fit_params, spectra_ind)
        peaks = copy.deepcopy(self._PeaksInfo)
        for peak in peaks:
            if fit_params:
                for param_name, param_data in peak['parameters'].items():
                    param_data['value'] = self.get_param_value(peak['peakname'], param_data,
                                                            param_name, fit_params, spectra_ind)
            line += Fitter.get_model(peak['fittype'], self._Data[spectra_ind]['energy'],
                                     self._Data[spectra_ind]['intensity'], peak['parameters'])
        for fittype, params in local_bg.items():
            bg += Fitter.get_model(fittype, self._Data[spectra_ind]['energy'], line, params)
        line += bg
        return line, bg

    def err_func(self, fit_params):
        """ calculate total residual for fits to several data sets held
        in a 2-D array, and modeled by model function"""
        self._Residuals = []
        for ind in range(len(self._Regions)):
            spectra, _ = self.sim_spectra(ind, fit_params)
            self._Residuals.append(self._Data[ind]['intensity'] - spectra)
        return [item for innerlist in self._Residuals for item in innerlist]

    def get_start_value_back(self, index, fittype):
        if fittype == 'first':
            if self._Data[index]['energy'][0] > self._Data[index]['energy'][1]:
                return self._Data[index]['intensity'][-1]
            else:
                return self._Data[index]['intensity'][0]
        elif fittype == 'min':
            return np.min(self._Data[index]['intensity'])

    def make_params(self):
        """Uses the starting values for the first peak to construct
        free variable voigts and doniachs for peak 0
        and dependent centers, sigmas and gammas for all other peaks
        amplitude is only free parameter
        """
        for fittype, params in self._BgParams.items():
            if not params['fix']:
                for ind in range(len(self._Regions)):
                    if fittype == 'constant':
                        if params['value'] in ['first', 'min']:
                            value = self.get_start_value_back(ind, params['value'])
                        else:
                            value = float(params['value'])
                        if params['min'] in ['first', 'min']:
                            min_ = self.get_start_value_back(ind, params['value'])
                        else:
                            min_ = float(params['min'])
                        if params['max'] in ['first', 'min']:
                            max_ = self.get_start_value_back(ind, params['value'])
                        else:
                            max_ = float(params['max'])
                    else:
                        value = float(params['value'])
                        min_ = float(params['min'])
                        max_ = float(params['max'])
                    self._FitParams.add('bg_{}_{}'.format(fittype, ind), value=value, min=min_, max=max_)

        for peak_info in self._PeaksInfo:
            for param_name, param_data in peak_info['parameters'].items():
                if not param_data['fix']:
                    if param_data['dependencetype'] in ['Independent', 'Dependent +', 'Dependent *']:
                        for ind in range(len(self._Regions)):
                            self._FitParams.add('{}_{}_{}'.format(peak_info['peakname'], param_name, ind),
                                                value=param_data['value'], min=param_data['min'], max=param_data['max'])
                            if param_data['dependencetype'] in ('Dependent +', 'Dependent *'):
                                for sub_peak in self._PeaksInfo:
                                    if sub_peak['peakname'] == param_data['dependencebase']:
                                        if sub_peak['parameters'][param_name]['fix']:
                                            self._BaseValues['{}_{}_{}'.format(peak_info['peakname'], param_name, ind)] = \
                                                sub_peak['parameters'][param_name]['value']
                                            #TODO: make sure that the line below is correct
                                            param_data['dependencetype'] = 'Dependent_on_fixed *'
                    elif param_data['dependencetype'] in ('Common +', 'Common *'):
                        self._FitParams.add('{}_{}'.format(peak_info['name'], param_name),
                                            value=0,
                                            min=param_data['min'] - param_data['value'],
                                            max=param_data['max'] - param_data['value'])
                elif param_data['dependencetype'] in ('Dependent +', 'Dependent *'):
                    for sub_peak in self._PeaksInfo:
                        if sub_peak['peakname'] == param_data['dependencebase']:
                            if sub_peak['parameters'][param_name]['fix']:
                                if param_data['dependencetype'] == 'Dependent +':
                                    param_data['value'] = sub_peak['parameters'][param_name]['value'] + param_data['value']
                                elif param_data['dependencetype'] == 'Dependent *':
                                    param_data['value'] = sub_peak['parameters'][param_name]['value'] * param_data['value']
                                else:
                                    raise RuntimeError('Unknown link type')
                                #TODO: check the line below
                                param_data['dependencetype'] = 'Fixed'

    def fit(self):
        """Calls minimize from lmfit using the objective function and the parameters
        """
        result = minimize(self.err_func, self._FitParams, method='least_squares')
        for i, fitterobj in enumerate(self._Fitters):
            for peak_info in self._PeaksInfo:
                peak_pars = {}
                peak_errs = {}
                for key, val in peak_info['parameters'].items():
                    if val['fix']:
                        if val['dependencetype'] == "Independent":
                            peak_pars[key] = val['value']
                        if val['dependencetype'] in ("Dependent *", "Dependent +"):
                            for pi in self._PeaksInfo:
                                if pi['peakname'] == f"Peak{val['dependencebase']}":
                                    if val['dependencetype'] == "Dependent *":
                                        peak_pars[key] = val['value'] * pi['parameters'][key]['value']
                                    else:
                                        peak_pars[key] = val['value'] + pi['parameters'][key]['value']
                                    break
                        peak_errs[key] = 0.0
                    else:
                        peak_pars[key] = result.params[f"{peak_info['peakname']}_{key}_{i}"].value
                        peak_errs[key] = result.params[f"{peak_info['peakname']}_{key}_{i}"].stderr
                peak_y = Fitter.get_model_func(peak_info['fittype'])(fitterobj._X_data, *peak_pars.values())
                peak = Peak(fitterobj._X_data, peak_y, [*peak_pars.values()], [*peak_errs.values()],
                            peak_func=Fitter.get_model_func(peak_info['fittype']),
                            peak_id=peak_info['peakname'], peak_type=peak_info['fittype'], lmfit=True)
                fitterobj._Peaks.append(peak)
            if len(self._BgParams) > 0:
                fitterobj._Bg = self.get_bg_values(result.params, i)
                fitterobj._make_fit(usebg=True)
            else:
                fitterobj._make_fit(usebg=False)
        return self._Fitters
