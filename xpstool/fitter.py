""" Provides class Fitter with helping functions
"""
import numpy as np
import scipy as sp
from scipy.optimize import curve_fit
from .region import Region

class Fitter:
    """Provides fitting possibilities for XPS spectra
    """
    def __init__(self, region):
        self._Region = region

    @staticmethod
    def fitFermiEdge(region, initial_params, add_column=True):
        """Fits error function to fermi level scan. If add_column flag
        is True, adds the fitting results as a column to the Region object.
        NOTE: Overwrites the 'fitFermi' column if already present in the instance.
        Returns a list [shift, fittingError]
        """
        # f(x) = s/(exp(-1*(x-m)/(8.617*(10^-5)*t)) + 1) + a*x + b
        def errorFunc(x, a0, a1, a2, a3):
            """Defines a complementary error function of the form
            (a0/2)*sp.special.erfc((a1-x)/a2) + a3
            """
            return (a0/2)*sp.special.erfc((a1-x)/a2) + a3

        if not region.getFlags()[2]:
            print(f"Can't fit the error func to non-Fermi region {region.getID()}")
            return

        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(errorFunc,
                        region.getData(column='energy').tolist(),
                        region.getData(column='counts').tolist(),
                        p0=initial_params)

        if add_column:
            region.addColumn("fitFermi", errorFunc(region.getData(column='energy'),
                                 popt[0],
                                 popt[1],
                                 popt[2],
                                 popt[3]),
                                 overwrite=True)

        return [popt[1], np.sqrt(np.diag(pcov_gauss))[1]]

    @staticmethod
    def fitSingleGaussian(region, initial_params, add_column=False):
        """Fits single Gaussian function to Region object. If add_column flag
        is True, adds the fitting results as a column to the Region object
        """
        # Parameters and parameters covariance of the fit
        popt, pcov = curve_fit(_single_gaussian,
                        region.getData('energy').tolist(),
                        region.getData('counts').tolist(),
                        p0=initial_params)

        if add_column:
            region.addColumn("fit", errorFunc(region.getData('energy'),
                                 popt[0],
                                 popt[1],
                                 popt[2],
                                 popt[3]))

        return [popt, pcov]


    def _single_gaussian(x, amp, cen, sigma):
        return amp*(1/(sigma*(np.sqrt(2*np.pi))))*(np.exp(-((x-cen)**2)/((2*sigma)**2)))








def fitSingleGaussian(region, initial_params, y_data='counts', add_column=False):
    """Fits single Gaussian function to Region object based on initial values
    of three parameters (amplitude, center, and sigma). If add_column flag
    is True, adds the fitting results as a column to the Region object
    """
    # Parameters and parameters covariance of the fit
    popt, pcov = curve_fit(_multiGaussian,
                    region.getData('energy').tolist(),
                    region.getData(y_data).tolist(),
                    p0=initial_params)

    if add_column:
        region.addColumn("onegauss", _multiGaussian(region.getData('energy'),
                             popt[0],
                             popt[1],
                             popt[2]))
        region.addColumn("twogauss", _multiGaussian(region.getData('energy'),
                          popt[3],
                          popt[4],
                          popt[5]))

    return [popt, pcov, np.sqrt(np.diag(pcov))]

def _singleGaussian(x, amp, cen, sigma):
    return amp*(1/(sigma*(np.sqrt(2*np.pi))))*(np.exp(-((x-cen)**2)/((2*sigma)**2)))

def _multiGaussian(x, *args):
    cnt = 0
    func = 0
    while cnt < len(args):
        func += args[cnt]*(1/(args[cnt+2]*(np.sqrt(2*np.pi))))*(np.exp(-((x-args[cnt+1])**2)/((2*args[cnt+2])**2)))
        cnt += 3
    return func
