"""Provides functions for handling and fitting the data
"""
import logging
import scipy as sp
import numpy as np
from scipy.optimize import curve_fit
#from specqp.fitter import Peak
from matplotlib import pyplot as plt


helpers_logger = logging.getLogger("specqp.helpers")  # Creating child logger


def fit_fermi_edge(region, initial_params, add_column=True, overwrite=True):
    """Fits error function to fermi level scan. If add_column flag
    is True, adds the fitting results as a column to the Region object.
    NOTE: Overwrites the 'fitFermi' column if already present.
    Returns a list [shift, fittingError]
    """

    # f(x) = s/(exp(-1*(x-m)/(8.617*(10^-5)*t)) + 1) + a*x + b
    def error_func(x, a0, a1, a2, a3):
        """Defines a complementary error function of the form
        (a0/2)*sp.special.erfc((a1-x)/a2) + a3
        """
        return (a0 / 2) * sp.special.erfc((a1 - x) / a2) + a3

    if not region.get_flags()["fermi_flag"]:
        helpers_logger.error(f"Can't fit the error func to non-Fermi region {region.get_id()}")
        return

    # Parameters and parameters covariance of the fit
    popt, pcov = curve_fit(error_func,
                           region.get_data(column='energy'),
                           region.get_data(column='counts'),
                           p0=initial_params)

    if add_column:
        region.add_column("fitFermi", error_func(region.get_data(column='energy'),
                                                popt[0],
                                                popt[1],
                                                popt[2],
                                                popt[3]),
                          overwrite=overwrite)

    return [popt, np.sqrt(np.diag(pcov))]


def calculate_linear_background(region, y_data='counts', manual_bg=None, by_min=False, add_column=True, overwrite=True):
    """Calculates the linear background using left and right ends of the region
    or using the minimum on Y-axis and the end that is furthest from the minimum
    on the X-axis. Manual background can be provided by passing approximate intervals
    like [[730, 740], [760,770]]; In that case the average values within these
    intervals will be calculated and assigned to the end points of the line
    describing the background.
    """

    def calculate_line(min_position):
        """Helper function to calculate the line cross the whole
        spectrum given coordinates of two points and "left" or "right" value
        of min_position to know in which direction the line must be extended
        """
        # School algebra to calculate the line coordinates given two points
        if min_position == "right":  # Line from left end to min
            x1 = energy[0]
            x2 = energy[counts_min_index]
            y1 = counts[0]
            y2 = counts_min
            slope = (y1 - y2) / (x1 - x2)
            b = (x1 * y1 - x2 * y1) / (x1 - x2)
            line_end = slope * energy[-1] + b
            return np.linspace(counts[0], line_end, len(energy))
        elif min_position == "left":
            x1 = energy[counts_min_index]
            x2 = energy[-1]
            y1 = counts_min
            y2 = counts[-1]
            slope = (y1 - y2) / (x1 - x2)
            b = (x1 * y1 - x2 * y1) / (x1 - x2)
            line_end = slope * energy[0] + b
            return np.linspace(line_end, counts[-1], len(energy))

    def calculate_manual_bg(x, y, x_intervals):
        left_interval = x_intervals[0]
        right_interval = x_intervals[1]
        # Checking that left is left and right is right. Swop otherwise.
        if x[0] > x[-1]:
            if left_interval[0] < right_interval[0]:
                left_interval = x_intervals[1]
                right_interval = x_intervals[0]

        left_bg_values = []
        right_bg_values = []

        first_left_index = 0
        last_left_index = len(x) - 1
        first_right_index = 0
        last_right_index = len(x) - 1
        for i in range(1, len(x)):
            if (x[i - 1] >= left_interval[0] >= x[i]) or (x[i - 1] <= left_interval[0] <= x[i]):
                first_left_index = i
            if (x[i - 1] >= left_interval[1] >= x[i]) or (x[i - 1] <= left_interval[1] <= x[i]):
                last_left_index = i
            if (x[i - 1] >= right_interval[0] >= x[i]) or (x[i - 1] <= right_interval[0] <= x[i]):
                first_right_index = i
            if (x[i - 1] >= right_interval[1] >= x[i]) or (x[i - 1] <= right_interval[1] <= x[i]):
                last_right_index = i

        left_background = y[first_left_index:last_left_index + 1]
        left_average = np.mean(left_background)
        # sum(left_background)/float(len(left_background))
        right_background = y[first_right_index:last_right_index + 1]
        right_average = np.mean(right_background)
        # sum(right_background)/float(len(right_background))

        return [left_average, right_average]

    counts = region.get_data(column=y_data).tolist()
    energy = region.get_data(column="energy").tolist()

    if by_min:
        counts_min = min(counts)
        counts_min_index = counts.index(counts_min)
        # If minimum lies closer to the right side of the region
        if counts_min_index > len(energy) // 2:
            background = calculate_line("right")
        else:
            background = calculate_line("left")
    else:
        if manual_bg:
            line_end_values = calculate_manual_bg(energy, counts, manual_bg)
            background = np.linspace(line_end_values[0], line_end_values[1], len(energy))
        else:
            background = np.linspace(counts[0], counts[-1], len(energy))

    if add_column:
        region.add_column("linearBG", counts - background, overwrite=overwrite)

    return background


def calculate_shirley(region, y_data='counts', tolerance=1e-5, maxiter=50, add_column=True, overwrite=True):
    """Calculates shirley background. Adopted from https://github.com/schachmett/xpl
    Author Simon Fischer <sfischer@ifp.uni-bremen.de>"
    """
    counts = region.get_data(column=y_data)
    energy = region.get_data(column="energy")

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
        helpers_logger.warning(f"{region.get_id()} - Background calculation failed due to excessive iterations")

    output = background
    if is_reversed:
        output = background[::-1]

    if add_column:
        corrected = counts - output
        if np.amin(corrected) < 0:
            corrected += np.absolute(np.amin(corrected))
        region.add_column("shirleyBG", corrected, overwrite=overwrite)

    return output


def calculate_linear_and_shirley(region, y_data='counts', shirleyfirst=True, by_min=False, tolerance=1e-5, maxiter=50,
                                 add_column=True, overwrite=True):
    """If shirleyfirst=False, calculates the linear background using left and
    right ends of the region or using the minimum and the end that is furthest
    from the minimum if by_min=True. Then calculates shirley background.
    If shirleyfirst=True, does shirley first and linear second.
    """
    if y_data in list(region.get_data()):
        counts = region.get_data(column=y_data)
    else:
        counts = region.get_data(column='counts')

    if shirleyfirst:
        shirley_bg = calculate_shirley(region, tolerance=tolerance, maxiter=maxiter, add_column=add_column)
        linear_bg = calculate_linear_background(region, y_data='shirleyBG', by_min=by_min, add_column=add_column)
    else:
        linear_bg = calculate_linear_background(region, by_min=by_min, add_column=add_column)
        shirley_bg = calculate_shirley(region, y_data="linearBG", tolerance=tolerance, maxiter=maxiter,
                                       add_column=add_column)
    background = linear_bg + shirley_bg
    if add_column:
        region.add_column("linear+shirleyBG", counts - background, overwrite=overwrite)

    return background


def smoothen(region, y_data='counts', interval=3, add_column=True):
    """Smoothes intensity averaging the data within the given interval"""
    intensity = region.get_data(column=y_data)
    odd = int(interval / 2) * 2 + 1
    even = int(interval / 2) * 2
    cumsum = np.cumsum(np.insert(intensity, 0, 0))
    avged = (cumsum[odd:] - cumsum[:-odd]) / odd
    for _ in range(int(even / 2)):
        avged = np.insert(avged, 0, avged[0])
        avged = np.insert(avged, -1, avged[-1])

    if add_column:
        region.add_column("averaged", avged, overwrite=True)

    return avged


def normalize(region, y_data='counts', const=None, add_column=True):
    """Normalize counts by maximum. If const is given, normalizes by this number
    """
    # If we want to use other column than "counts" for calculations
    counts = region.get_data(column=y_data)
    if const:
        output = counts / float(const)
    else:
        output = counts / float(max(counts))

    if add_column:
        region.add_column("normalized", output, overwrite=True)
    return output


def normalize_by_background(region, start, stop, y_data='counts', add_column=True):
    """Correct counts by the average background level given by the interval [start, stop]
    """
    # If we want to use other column than "counts" for calculations
    counts = region.get_data(column=y_data)
    energy = region.get_data(column="energy")

    first_index = 0
    last_index = len(counts) - 1

    for i in range(0, len(energy)):
        if i > 0:
            if (energy[i - 1] <= start <= energy[i]) or (energy[i - 1] >= start >= energy[i]):
                first_index = i
            if (energy[i - 1] <= stop <= energy[i]) or (energy[i - 1] >= stop >= energy[i]):
                last_index = i

    output = counts / float(np.mean(counts[first_index:last_index]))

    if add_column:
        region.add_column("bgnormalized", output, overwrite=True)
    return output


def shift_by_background(region, interval, y_data='counts', add_column=True):
    """Correct counts by the average background level given by the interval [start, stop]
    """
    # If we want to use other column than "counts" for calculations
    counts = region.get_data(column=y_data)
    energy = region.get_data(column="energy")

    first_index = 0
    last_index = len(counts) - 1

    for i in range(0, len(energy)):
        if i > 0:
            if (energy[i - 1] <= interval[0] <= energy[i]) or (energy[i - 1] >= interval[0] >= energy[i]):
                first_index = i
            if (energy[i - 1] <= interval[1] <= energy[i]) or (energy[i - 1] >= interval[1] >= energy[i]):
                last_index = i

    output = counts - float(np.mean(counts[first_index:last_index]))

    if add_column:
        region.add_column("bgshifted", output, overwrite=True)
    return output


def plot_region(region, figure=1, ax=None, invert_x=True, log_scale=False, y_offset=0, x_data='energy', y_data='final',
                scatter=False, label=None, color=None, title=True, legend=True, legend_pos='best'):
    """Plotting spectrum with pyplot using given plt.figure and a number of optional arguments
    """
    if x_data in list(region.get_data()):
        x = region.get_data(column=x_data)
    else:
        x = region.get_data(column='energy')
    if y_data in list(region.get_data()):
        y = region.get_data(column=y_data)
    else:
        y = region.get_data(column='counts')

    plt.figure(figure)
    if not ax:
        ax = plt.gca()
    if not label:
        label = f"{region.get_id()} ({region.get_conditions()['Temperature']})"
    # If we want scatter plot
    if scatter:
        ax.scatter(x, y + y_offset, s=7, c=color, label=label)
    else:
        ax.plot(x, y + y_offset, color=color, label=label)
    if legend:
        if legend_pos == 'lower center':
            ax.set_ylim(ymin=-1 * np.amax(y))
            plt.tick_params(
                axis='y',  # changes apply to the y-axis
                which='both',  # both major and minor ticks are affected
                left=False,  # ticks along the left edge are off
                right=False)  # ticks along the right edge are off
        ax.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': 8})
    if title:
        title_str = ""
        if region.is_sweeps_normalized():
            title_str = f"Pass: {region.get_info('Pass Energy')}   |   File: {region.get_info('File Name')}"
        else:
            title_str = f"Pass: {region.get_info('Pass Energy')}   |   Sweeps: {region.get_info('Sweeps Number')}" \
                f"   |   File: {region.get_info('File Name')}"
        ax.set_title(title_str)

    #   Stiling axes
    x_label_prefix = "Binding"
    if region.get_info("Energy Scale") == "Kinetic":
        x_label_prefix = "Kinetic"

    ax.set_xlabel(f"{x_label_prefix} energy (eV)")
    ax.set_ylabel("Counts (a.u.)")

    # Inverting x-axis if desired and not yet inverted
    if invert_x and not ax.xaxis_inverted():
        ax.invert_xaxis()

    if log_scale:
        ax.set_yscale('log')


def plot_peak(peak, y_offset=0, figure=1, ax=None, label=None, color=None, fill=True, legend=True, legend_pos='best'):
    """Plotting fit peak with pyplot using given plt.figure and a number of optional arguments
    """
    peak_line = peak.get_data()
    plt.figure(figure)
    if not ax:
        ax = plt.gca()
    if not label:
        label = f"Cen: {peak.get_parameters('center'):.2f}; LorentzFWHM: {peak.get_parameters('fwhm'):.2f}"

    ax.plot(peak.get_data()[0], peak.get_data()[1] + y_offset, color=color, label=label)
    if fill:
        # Fill the peak shape with color that is retrieved from the last plotted line
        ax.fill_between(peak_line[0], peak_line[1].min() + y_offset, peak_line[1] + y_offset,
                        facecolor=ax.get_lines()[-1].get_color(), alpha=0.3)
    if legend:
        ax.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': 8})


def plot_fit(fitter, y_offset=0, figure=1, ax=None, label=None, color='black', legend=True, legend_pos='best',
             addresiduals=True):
    """Plotting fit line with pyplot using given plt.figure and a number of optional arguments
    """
    plt.figure(figure)
    if not ax:
        ax = plt.gca()
    if not label:
        label = "fit"
    fit_x = fitter.get_data()[0].tolist()
    fit_y = (fitter.get_fit_line() + y_offset).tolist()
    ax.plot(fit_x, fit_y, linestyle='--', color=color, label=label)
    # Add residuals if specified
    if addresiduals:
        ax.plot(fit_x, fit_y, linestyle=':', alpha=1, color='black',
                label=f"Chi^2 = {fitter.get_chi_squared():.2f}\nRMS = {fitter.get_rms():.2f}")
    if legend:
        ax.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': 8})
