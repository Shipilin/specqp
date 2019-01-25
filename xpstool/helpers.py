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

def calculateLinearBackground(region, y_data="counts", by_min=False, add_column=False):
    """Calculates the linear background using left and right ends of the region
    or using the minimum and the end that is furthest from the minimum
    """
    def calculateLine(min_position):
        """Helper function to calculate the line cross the whole
        spectrum given coordinates of two points and "left" or "right" value
        of min_position to know in which direction the line must be extended
        """
        # School algebra to calculate the line coordinates given two points
        if min_position == "right": # Line from left end to min
            x1 = energy[0]
            x2 = energy[counts_min_index]
            y1 = counts[0]
            y2 = counts_min
            slope = (y1-y2)/(x1-x2)
            b = (x1*y1 - x2*y1)/(x1-x2)
            line_end = slope*energy[-1] + b
            return np.linspace(counts[0], line_end, len(energy))
        elif min_position == "left":
            x1 = energy[counts_min_index]
            x2 = energy[-1]
            y1 = counts_min
            y2 = counts[-1]
            slope = (y1-y2)/(x1-x2)
            b = (x1*y1 - x2*y1)/(x1-x2)
            line_end = slope*energy[0] + b
            return np.linspace(line_end, counts[-1], len(energy))

    # If we want to use other column than "counts" for calculations
    if y_data == "counts":
        counts = region.getData(column="counts").tolist()
    else:
        counts = region.getData(column=y_data).tolist()
    energy = region.getData(column="energy").tolist()

    if by_min:
        counts_min = min(counts)
        counts_min_index = counts.index(counts_min)
        print(counts_min, counts_min_index)
        # If minimum lies closer to the right side of the region
        if counts_min_index > len(energy)//2:
            background = calculateLine("right")
        else:
            background = calculateLine("left")
    else:
        background = np.linspace(counts[0], counts[-1], len(energy))

    if add_column:
        region.addColumn("linear bg corrected", counts - background)
    return background

def calculateShirley(region, y_data="counts", tolerance=1e-5, maxiter=50, add_column=False):
    """Calculates shirley background. Adopted from https://github.com/schachmett/xpl
    Author Simon Fischer <sfischer@ifp.uni-bremen.de>"
    """
    # If we want to use other column than "counts" for calculations
    if y_data == "counts":
        counts = region.getData(column="counts")
    else:
        counts = region.getData(column=y_data)
    energy = region.getData(column="energy")

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
        print(f"{region.getInfo()['File']}: {region.getInfo()['Region Name']} - Background calculation failed due to excessive iterations")

    output = background
    if is_reversed:
        output = background[::-1]

    if add_column:
        region.addColumn("shirley corrected", counts - output)

    return output

def calculateLinearAndShirley(region, by_min=False, tolerance=1e-5, maxiter=50, add_column=False):
    """Calculates the linear background using left and right ends of the region
    or using the minimum and the end that is furthest from the minimum if by_min=True.
    Then calculates shirley background.
    """
    linear_bg = calculateLinearBackground(region, by_min=by_min, add_column=True)
    shirley_bg = calculateShirley(region, y_data="linear bg corrected", tolerance=tolerance, maxiter=maxiter, add_column=add_column)

def normalize(region, y_data="counts", add_column=False):
    """Normalize counts.
    """
    # If we want to use other column than "counts" for calculations
    if y_data == "counts":
        counts = region.getData(column="counts")
    else:
        counts = region.getData(column=y_data)
    energy = region.getData(column="energy")

    output = counts / max(counts)

    if add_column:
        region.addColumn("normalized", output)
    return output
