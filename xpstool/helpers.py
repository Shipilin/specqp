"""Provides functions for handling and fitting the data
"""
from matplotlib import pyplot as plt
import scipy as sp
import numpy as np
from scipy.optimize import curve_fit

def fitFermiEdge(region, initial_params, add_column=True):
    """Fits error function to fermi level scan. If add_column flag
    is True, adds the fitting results as a column to the Region object.
    NOTE: Overwrites the 'fitFermi' column if already present in the instance
    unless add_column is set to False explicitly.
    Returns a list [shift, fittingError]
    """
    # f(x) = s/(exp(-1*(x-m)/(8.617*(10^-5)*t)) + 1) + a*x + b
    def errorFunc(x, a0, a1, a2, a3):
        """Defines a complementary error function of the form
        (a0/2)*sp.special.erfc((a1-x)/a2) + a3
        """
        return (a0/2)*sp.special.erfc((a1-x)/a2) + a3

    if not region.getFlags()["fermi_flag"]:
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

    return [popt[1], np.sqrt(np.diag(pcov))[1]]

def calculateLinearBackground(region, y_data='counts', by_min=False, add_column=True):
    """Calculates the linear background using left and right ends of the region
    or using the minimum on Y-axis and the end that is furthest from the minimum
    on the X-axis.
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

    counts = region.getData(column=y_data).tolist()
    energy = region.getData(column='energy').tolist()

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
        region.addColumn("linearBG", counts - background, overwrite=True)

    return background

def calculateShirley(region, y_data='counts', tolerance=1e-5, maxiter=50, add_column=True):
    """Calculates shirley background. Adopted from https://github.com/schachmett/xpl
    Author Simon Fischer <sfischer@ifp.uni-bremen.de>"
    """
    counts = region.getData(column=y_data)
    energy = region.getData(column='energy')

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
        print(f"{region.getID()} - Background calculation failed due to excessive iterations")

    output = background
    if is_reversed:
        output = background[::-1]

    if add_column:
        region.addColumn("shirleyBG", counts - output, overwrite=True)

    return output

def calculateLinearAndShirley(region, by_min=False, tolerance=1e-5, maxiter=50, add_column=True):
    """Calculates the linear background using left and right ends of the region
    or using the minimum and the end that is furthest from the minimum if by_min=True.
    Then calculates shirley background.
    """
    linear_bg = calculateLinearBackground(region, by_min=by_min, add_column=add_column)
    shirley_bg = calculateShirley(region, y_data="linearBG", tolerance=tolerance, maxiter=maxiter, add_column=add_column)
    background = linear_bg + shirley_bg
    if add_column:
        region.addColumn("linear+shirleyBG", counts - background, overwrite=True)

    return background

def normalize(region, y_data='counts', add_column=True):
    """Normalize counts.
    """
    # If we want to use other column than "counts" for calculations
    counts = region.getData(column=y_data)
    energy = region.getData(column='energy')

    output = counts / max(counts)

    if add_column:
        region.addColumn("normalized", output, overwrite=True)
    return output

def plotRegion(region,
            figure=1,
            ax=None,
            invert_x=True,
            x_data='energy',
            y_data='counts',
            scatter=False,
            label=None,
            color=None,
            title=True,
            legend=True):
    """Plotting spectrum with pyplot using given plt.figure and a number of optional arguments
    """
    x = region.getData(column=x_data)
    y = region.getData(column=y_data)

    plt.figure(figure)
    if not ax:
        ax = plt.gca()

    if not label:
        label=f"{region.getID()}"
    # If we want scatter plot
    if scatter:
        ax.scatter(x, y, s=7, c=color, label=label)
    else:
        ax.plot(x, y, color=color, label=label)
    if legend:
        ax.legend(fancybox=True, framealpha=0, loc='best')
    if title:
        ax.set_title(f"Pass: {region.getInfo('Pass Energy')}   |   Sweeps: {region.getInfo('Number of Sweeps')}   |   File: {region.getInfo('File')}")

    #   Stiling axes
    x_label_prefix = "Binding"
    if region.getInfo("Energy Scale") == "Kinetic":
        x_label_prefix = "Kinetic"

    ax.set_xlabel(f"{x_label_prefix} energy (eV)")
    ax.set_ylabel("Counts (a.u.)")

    # Inverting x-axis if desired and not yet inverted
    if invert_x and not ax.xaxis_inverted():
        ax.invert_xaxis()
