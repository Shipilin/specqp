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
