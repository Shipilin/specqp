"""Provides functions for fitting the data
"""

import scipy as sp
from scipy.optimize import curve_fit
from .region import Region

def fitFermiEdge(region, initial_params):
    """Fits error function to fermi level scan
    """
    # Check if the region is actually Fermi level
    if not region.getFlags()[Region._region_flags[2]]:
        print("The provided region is not Fermi level. No fitting was done.")
        return

    # Parameters and parameters covariance of the fit
    popt, pcov = curve_fit(errorFunc,
                    region.getData()['energy'].values.tolist(),
                    region.getData()['counts'].values.tolist(),
                    p0=initial_params)

    return [popt, pcov]

# f(x) = s/(exp(-1*(x-m)/(8.617*(10^-5)*t)) + 1) + a*x + b
def errorFunc(x, a0, a1, a2, a3):
    """Defines a complementary error function of the form
    (a0/2)*sp.special.erfc((a1-x)/a2) + a3
    """
    return (a0/2)*sp.special.erfc((a1-x)/a2) + a3
