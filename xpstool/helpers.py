"""Provides functions for handling and fitting the data
"""
import scipy as sp
import numpy as np
from scipy.optimize import curve_fit
from .region import Region

def fitFermiEdge(region, initial_params, add_column=False):
    """Fits error function to fermi level scan. If add_column flag
    is True, adds the fitting results as a column to the region object
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

    if add_column:
        region.addColumn("fit", errorFunc(region.getData()["energy"],
                             popt[0],
                             popt[1],
                             popt[2],
                             popt[3]))

    return [popt, pcov]

# f(x) = s/(exp(-1*(x-m)/(8.617*(10^-5)*t)) + 1) + a*x + b
def errorFunc(x, a0, a1, a2, a3):
    """Defines a complementary error function of the form
    (a0/2)*sp.special.erfc((a1-x)/a2) + a3
    """
    return (a0/2)*sp.special.erfc((a1-x)/a2) + a3

def calculateShirley(region, tolerance=1e-5, maxiter=50, add_column=False):
    """Calculates shirley background. Adopted from https://github.com/schachmett/xpl
    Author Simon Fischer <sfischer@ifp.uni-bremen.de>"
    """
    energy = region.getData(column="energy")
    counts = region.getData(column="counts")
    if energy[0] < energy[-1]:
        is_reversed = True
        energy = energy[::-1]
        counts = counts[::-1]
    else:
        is_reversed = False

    background = np.ones(energy.shape) * counts[-1]
    integral = np.zeros(energy.shape)
    spacing = (energy[-1] - energy[0]) / (len(energy) - 1)

    subtracted = counts - background
    ysum = subtracted.sum() - np.cumsum(subtracted)
    for i in range(len(energy)):
        integral[i] = spacing * (ysum[i] - 0.5
                                 * (subtracted[i] + subtracted[-1]))

    iteration = 0
    while iteration < maxiter:
        subtracted = counts - background
        integral = spacing * (subtracted.sum() - np.cumsum(subtracted))
        bnew = ((counts[0] - counts[-1])
                * integral / integral[0] + counts[-1])
        if np.linalg.norm((bnew - background) / counts[0]) < tolerance:
            background = bnew.copy()
            break
        else:
            background = bnew.copy()
        iteration += 1
    if iteration >= maxiter:
        print("Background calculation failed due to excessive iterations")

    output = background
    if is_reversed:
        output = background[::-1]

    if add_column:
        region.addColumn("no background", counts - output)

    return output
