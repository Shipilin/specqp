import numpy as np
import csv
import copy

from matplotlib import pyplot as plt
from matplotlib.widgets import Slider

from lmfit import Parameters, minimize

from specqp.fittingmodels import Models


class GlobalFit:
    def __init__(self, region):
        self.data = data['scans']
        self.ndata = len(data['scans'])
        self.resid = []
        self.models = Models()
        self.fitParams = Parameters()
        self.peaksInfo = None
        self.bgParam = []
        self.result = None
        self.baseValues = {}

    # ----------------------------------------------------------------------
    def getParamValue(self, peakName, paramData, paramName, fitParams, spectraInd):

        if paramData['fitable']:
            if paramData['model'] == 'Flex':
                return 0 + fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)]

            elif paramData['model'] == 'Common':
                if paramData['linkType'] == 'additive':
                    return paramData['value'] + fitParams['{}_{}'.format(peakName, paramName)]
                else:
                    return paramData['value'] * fitParams['{}_{}'.format(peakName, paramName)]

            elif paramData['model'] == 'Dependent':
                if paramData['linkType'] == 'additive':
                    return fitParams['{}_{}_{}'.format(paramData['baseValue'], paramName, spectraInd)] +\
                           fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)]
                else:
                    return fitParams['{}_{}_{}'.format(paramData['baseValue'], paramName, spectraInd)] *\
                           fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)]

            elif paramData['model'] == 'Dependent_on_fixed':
                if paramData['linkType'] == 'additive':
                    return self.baseValues['{}_{}_{}'.format(peakName, paramName, spectraInd)] +\
                           fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)]
                else:
                    return self.baseValues['{}_{}_{}'.format(peakName, paramName, spectraInd)] *\
                           fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)]
            else:
                raise RuntimeError('Unknown model')
        else:
            if paramData['model'] == 'Dependent':
                if paramData['linkType'] == 'additive':
                    return fitParams['{}_{}_{}'.format(paramData['baseValue'], paramName, spectraInd)] +\
                           paramData['value']
                else:
                    return fitParams['{}_{}_{}'.format(paramData['baseValue'], paramName, spectraInd)] *\
                           paramData['value']
            else:
                return paramData['value']

    # ----------------------------------------------------------------------
    def getParamError(self, peakName, paramData, paramName, fitParams, spectraInd):
        try:
            if paramData['fitable']:
                if paramData['model'] == 'Flex':
                    return 0 + fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)].stderr

                elif paramData['model'] == 'Common':
                    if paramData['linkType'] == 'additive':
                        return 0 + fitParams['{}_{}'.format(peakName, paramName)].stderr
                    else:
                        return paramData['value'] * fitParams['{}_{}'.format(peakName, paramName)].stderr

                elif paramData['model'] == 'Dependent':
                       return fitParams['{}_{}_{}'.format(paramData['baseValue'], paramName, spectraInd)].stderr + \
                              fitParams['{}_{}_{}'.format(peakName, paramName, spectraInd)].stderr
                else:
                    raise RuntimeError('Unknown model')
            else:
                if paramData['model'] == 'Dependent':
                    return fitParams['{}_{}_{}'.format(paramData['baseValue'], paramName, spectraInd)].stderr * \
                           paramData['value']
                else:
                    return 0
        except:
            return 0
    # ----------------------------------------------------------------------
    def getBckValues(self, fitParams, spectraInd):

        localBg = copy.deepcopy(self.bgParams)

        if fitParams:
            for type, params in localBg.items():
                if params['fitable']:
                    params['value'] = fitParams['bg_{}_{}'.format(type, spectraInd)]
                if type == 'constant':
                    if params['value'] == 'first':
                        if self.data[spectraInd]['energy'][0] < self.data[spectraInd]['energy'][-1]:
                            params['value'] = self.data[spectraInd]['intensity'][0]
                        else:
                            params['value'] = self.data[spectraInd]['intensity'][-1]
                    elif params['value'] == 'min':
                        params['value'] = np.min(self.data[spectraInd]['intensity'])
        return localBg

    # ----------------------------------------------------------------------
    def simSpectra(self, spectraInd, fitParams):

        # defines the model for the fit (doniachs, voigts, shirley bg, linear bg

        line = np.zeros_like(self.data[spectraInd]['intensity'])
        bg = np.zeros_like(self.data[spectraInd]['intensity'])

        localBg = self.getBckValues(fitParams, spectraInd)

        for peak in copy.deepcopy(self.peaksInfo):
            if fitParams:
                for paramName, paramData in peak['params'].items():
                    paramData['value'] = self.getParamValue(peak['name'], paramData,
                                                            paramName, fitParams, spectraInd)

            line += self.models.getModel(peak['peakType'], self.data[spectraInd]['energy'],
                                         self.data[spectraInd]['intensity'], peak['params'])

        for type, params in localBg.items():
            bg += self.models.getModel(type, self.data[spectraInd]['energy'], line, params)

        line += bg

        return line, bg

    # ----------------------------------------------------------------------
    def errFunc(self, fitParams):
        """ calculate total residual for fits to several data sets held
        in a 2-D array, and modeled by model function"""

        self.resid = []

        for ind in range(self.ndata):

            spectra, _ = self.simSpectra(ind, fitParams)
            self.resid.append(self.data[ind]['intensity'] - spectra)

        return [item for innerlist in self.resid for item in innerlist]

    # ----------------------------------------------------------------------
    def getStartValueBack(self, index, type):
        if type == 'first':
            if self.data[index]['energy'][0] > self.data[index]['energy'][1]:
                return self.data[index]['intensity'][-1]
            else:
                return self.data[index]['intensity'][0]
        elif type == 'min':
            return np.min(self.data[index]['intensity'])

    # ----------------------------------------------------------------------
    def make_params(self, peaksInfo, bgParams):
        # uses the starting values for the first peak to construct
        # free variable voigts and doniachs for peak 0
        # and dependent centers, sigmas and gammas for all other peaks
        # amplitude is only free parameter

        self.bgParams = copy.deepcopy(bgParams)

        for type, params in self.bgParams.items():
            if params['fitable']:
                for ind in range(self.ndata):
                    if type == 'constant':
                        if params['value'] in ['first', 'min']:
                            value = self.getStartValueBack(ind, params['value'])
                        else:
                            value = float(params['value'])

                        if params['min'] in ['first', 'min']:
                            min = self.getStartValueBack(ind, params['value'])
                        else:
                            min = float(params['min'])

                        if params['max'] in ['first', 'min']:
                            max = self.getStartValueBack(ind, params['value'])
                        else:
                            max = float(params['max'])

                    else:
                        value = float(params['value'])
                        min = float(params['min'])
                        max = float(params['max'])

                    self.fitParams.add('bg_{}_{}'.format(type, ind), value=value,
                                       min=min, max=max)

        self.peaksInfo = copy.deepcopy(peaksInfo)

        for peak in self.peaksInfo:
            for paramName, paramData in peak['params'].items():
                if paramData['fitable']:
                    if paramData['model'] in ['Flex', 'Dependent']:
                        for ind in range(self.ndata):
                            if paramData['limModel'] == 'absolute':
                                self.fitParams.add('{}_{}_{}'.format(peak['name'], paramName, ind), value=paramData['value'],
                                                   min=paramData['min'], max=paramData['max'])
                            else:
                                self.fitParams.add('{}_{}_{}'.format(peak['name'], paramName, ind), value=paramData['value'],
                                                   min = paramData['value']-paramData['delta'],
                                                   max = paramData['value'] + paramData['delta'])

                            if paramData['model'] == 'Dependent':
                                for subPeak in self.peaksInfo:
                                    if subPeak['name'] == paramData['baseValue']:
                                        if not subPeak['params'][paramName]['fitable']:
                                            self.baseValues['{}_{}_{}'.format(peak['name'], paramName, ind)] = \
                                                subPeak['params'][paramName]['value']

                                            paramData['model'] = 'Dependent_on_fixed'

                    elif paramData['model'] == 'Common':
                        if paramData['limModel'] == 'absolute':
                            self.fitParams.add('{}_{}'.format(peak['name'], paramName), value=0,
                                               min=paramData['min'] - paramData['value'],
                                               max=paramData['max'] - paramData['value'])
                        else:
                            self.fitParams.add('{}_{}'.format(peak['name'], paramName), value=0,
                                               min=-paramData['delta'], max=paramData['delta'])

                elif paramData['model'] == 'Dependent':
                    for subPeak in self.peaksInfo:
                        if subPeak['name'] == paramData['baseValue']:
                            if not subPeak['params'][paramName]['fitable']:
                                if paramData['linkType'] == 'additive':
                                    paramData['value'] = subPeak['params'][paramName]['value'] + paramData['value']
                                elif paramData['linkType'] == 'multiplication':
                                    paramData['value'] = subPeak['params'][paramName]['value'] * paramData['value']
                                else:
                                    raise RuntimeError('Unknown link type')

                                paramData['model'] = 'fixed'

    # ----------------------------------------------------------------------
    def fit(self):
        # calls minimize from lmfit using the objective function and the parameters

        self.result = minimize(self.errFunc, self.fitParams, method='least_squares')

        return self.result.params

    # ----------------------------------------------------------------------
    def plot_residual_interactive(self, fitResults = None):
        # plots a window of fit, its components and residual
        # contains slider that allows to slide trough spectra

        if not fitResults:
            fitResults = self.fitParams

        fig, ax = plt.subplots(1, 1, sharex='col')
        plt.subplots_adjust(bottom=0.2)
        mng = plt.get_current_fig_manager()
        mng.full_screen_toggle()

        # plt.ylim(self.specs.min(), self.specs.max())
        axidx = plt.axes([0.25, 0.1, 0.65, 0.03])

        # if the returned sidx (slider object) is destroyed the slider
        # loses its functionality!

        self.sidx = Slider(axidx, 'Spec#', 0, self.ndata - 1, valinit=0, valstep=1)

        def update(idx):
            idx = int(idx)
            ax.cla()
            # ax[0].cla()
            # ax[1].cla()
            self.plot_components(idx, fitResults, ax)
            ax.plot(self.data[idx]['energy'], self.data[idx]['intensity'], '.', label='S')
            spec, _ = self.simSpectra(idx, fitResults)
            ax.plot(self.data[idx]['energy'], spec, label='M')
            ax.legend()
            # if self.resid:
            #     ax[1].plot(self.data[idx]['energy'], self.resid[idx])
            high = np.max(self.data[idx]['energy'])
            low = np.min(self.data[idx]['energy'])
            plt.sca(ax)
            plt.xlim(high, low)
            # plt.ylim(self.specs.min(), self.specs.max())

        self.sidx.on_changed(update)
        update(0)

        return plt

    # ----------------------------------------------------------------------
    def plot_components(self, spectraInd, fitParams, ax):

        #plots the component i onto ax using params

        _, bg = self.simSpectra(spectraInd, fitParams)

        ax.plot(self.data[spectraInd]['energy'], bg)

        line = np.zeros_like(self.data[spectraInd]['intensity'])

        for peak in copy.deepcopy(self.peaksInfo):
            if fitParams:
                for paramName, paramData in peak['params'].items():
                    paramData['value'] = self.getParamValue(peak['name'], paramData,
                                                            paramName, fitParams, spectraInd)

            line = bg + self.models.getModel(peak['peakType'], self.data[spectraInd]['energy'],
                                             self.data[spectraInd]['intensity'], peak['params'])

            ax.plot(self.data[spectraInd]['energy'], line)

    # ----------------------------------------------------------------------
    def collect_fit_data(self, fitParams):
        rawFitResult = []
        rawColumns = []

        absoluteFitResult = []
        absoluteColumns =  []

        for spectraInd in range(self.ndata):
            spectraRawRecord = {}
            spectraAbsoluteRecord = {}

            localBg = self.getBckValues(fitParams, spectraInd)
            for type, params in localBg.items():
                if params['value']:
                    spectraRawRecord['bg_{}'.format(type)] = 0 + float(params['value'])
                    spectraAbsoluteRecord['bg_{}'.format(type)] = 0 + float(params['value'])
                    if 'bg_{}'.format(type) not in absoluteColumns: absoluteColumns.append('bg_{}'.format(type))
                    if 'bg_{}'.format(type) not in rawColumns: rawColumns.append('bg_{}'.format(type))

            for peak in copy.deepcopy(self.peaksInfo):
                for paramName, paramData in peak['params'].items():
                    spectraAbsoluteRecord['{}_{}'.format(peak['name'], paramName)]=\
                        self.getParamValue(peak['name'], paramData, paramName, fitParams, spectraInd)
                    spectraAbsoluteRecord['{}_{}_err'.format(peak['name'], paramName)]=\
                        self.getParamError(peak['name'], paramData, paramName, fitParams, spectraInd)

                    if '{}_{}'.format(peak['name'], paramName) not in absoluteColumns:
                        absoluteColumns.append('{}_{}'.format(peak['name'], paramName))
                    if '{}_{}_err'.format(peak['name'], paramName) not in absoluteColumns:
                        absoluteColumns.append('{}_{}_err'.format(peak['name'], paramName))

                    if paramData['fitable']:
                        spectraRawRecord['{}_{}'.format(peak['name'], paramName)] = 0 + \
                            fitParams['{}_{}_{}'.format(peak['name'], paramName, spectraInd)]

                        if '{}_{}'.format(peak['name'], paramName) not in rawColumns:
                            rawColumns.append('{}_{}'.format(peak['name'], paramName))

            absoluteFitResult.append(spectraAbsoluteRecord)
            if spectraRawRecord:
                rawFitResult.append(spectraRawRecord)

        return rawFitResult, rawColumns, absoluteFitResult, absoluteColumns

    # ----------------------------------------------------------------------
    def save_fits(self, fitParams, key):

        rawFitResult, rawColumns, absoluteFitResult, absoluteColumns = self.collect_fit_data(fitParams)

        try:
            with open('./fits/{}_raw.csv'.format(key), 'w', newline='') as outputFile:
                writer = csv.DictWriter(outputFile, delimiter =';', lineterminator='', fieldnames=rawColumns)
                writer.writeheader()
                for record in rawFitResult:
                    writer.writerow(record)
            with open('./fits/{}_absolute.csv'.format(key), 'w', newline='') as outputFile:
                writer = csv.DictWriter(outputFile, delimiter =';', lineterminator='', fieldnames=absoluteColumns)
                writer.writeheader()
                for record in absoluteFitResult:
                    writer.writerow(record)
        except:
            print("I/O error")

    # ----------------------------------------------------------------------
    def print_fits(self, fitParams, fieldsToPrint = None):

        rawFitResult, rawColumns, _, _ = self.collect_fit_data(fitParams)

        if not fieldsToPrint:
            fieldsToPrint = rawColumns

        for record in rawFitResult:
            line = ''
            for field in fieldsToPrint:
                line += field + ': ' + '{:.4f}'.format(record[field]) + ' '
            print(line)


    # ----------------------------------------------------------------------
    def load_fits(self, fileName):

        csvreader = csv.DictReader(open(fileName, 'r'),delimiter=';')

        counter = 0
        finished = False
        while not finished:
            try:
                line = next(csvreader)
                self.updateFitParams(line, counter)
                counter += 1
            except:
                finished = True

    # ----------------------------------------------------------------------
    def updateFitParams(self, params, ind):

        for paramName, value in params.items():
            try:
                self.fitParams['{:s}_{:d}'.format(paramName, ind)].value = float(value)
            except:
                print('Cannot update parameter: {:s}'.format(paramName))

    # ----------------------------------------------------------------------
    def make_fits_file(self, folder, fileName, csv_columns):
        try:
            outputFile = open('{}/{}.csv'.format(folder, fileName), 'w', newline='')
            writer = csv.DictWriter(outputFile, delimiter=';', fieldnames=csv_columns)
            writer.writeheader()
            return outputFile, writer
        except:
            print("I/O error")

    # ----------------------------------------------------------------------
    def save_fits_line(self, writer, fitResult):
        for record in fitResult:
            writer.writerow(record)
