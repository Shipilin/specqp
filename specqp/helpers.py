"""Provides functions for handling and fitting the data
"""
import os
import logging
import scipy as sp
import numpy as np
from scipy.optimize import curve_fit


helpers_logger = logging.getLogger("specqp.helpers")  # Creating child logger


def is_iterable(obj):
    try:
        _ = (e for e in obj)
        return True
    except TypeError:
        return False


def fit_fermi_edge(region, initial_params, column="final", add_column=True, overwrite=True):
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
        helpers_logger.warning(f"Can't fit the error func to non-Fermi region {region.get_id()}")
        return

    # Parameters and parameters covariance of the fit
    popt, pcov = curve_fit(error_func,
                           region.get_data(column='energy'),
                           region.get_data(column=column),
                           p0=initial_params)

    if add_column:
        region.add_column("fitFermi", error_func(region.get_data(column='energy'),
                                                popt[0],
                                                popt[1],
                                                popt[2],
                                                popt[3]),
                          overwrite=overwrite)
    # Return parameters and their uncertainties
    return [popt, np.sqrt(np.diag(pcov))]


def subtract_linear_bg(region, y_data='final', manual_bg=None, by_min=False, add_column=True, overwrite=True):
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
        region.add_column("no_lin_bg", counts - background, overwrite=overwrite)

    return background


def subtract_shirley(region, y_data='final', tolerance=1e-5, maxiter=50, add_column=True, overwrite=True):
    """Calculates shirley background. Adopted from https://github.com/schachmett/xpl
    Author Simon Fischer <sfischer@ifp.uni-bremen.de>"
    """
    def get_shirley_bg(energy, counts, tolerance=1e-5, maxiter=50):
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
            integral[i] = spacing * (ysum[i] - 0.5 * (subtracted[i] + subtracted[-1]))
        iteration = 0
        while iteration < maxiter:
            subtracted = counts - background
            integral = spacing * (subtracted.sum() - np.cumsum(subtracted))
            bnew = ((counts[0] - counts[-1]) * integral / integral[0] + counts[-1])
            if np.linalg.norm((bnew - background) / counts[0]) < tolerance:
                background = bnew.copy()
                break
            else:
                background = bnew.copy()
            iteration += 1
        if iteration >= maxiter:
            return None
        output = background
        if is_reversed:
            output = background[::-1]
        return output

    energy = region.get_data(column="energy")
    counts = region.get_data(column=y_data)
    bg = get_shirley_bg(energy, counts, tolerance, maxiter)
    if bg is None:
        helpers_logger.warning(f"{region.get_id()} - Shirley background calculation failed due to excessive iterations")
        bg = counts * 0
    if add_column:
        corrected = counts - bg
        if np.amin(corrected) < 0:
            corrected += np.absolute(np.amin(corrected))
        region.add_column("no_shirley", corrected, overwrite=overwrite)
    if region.is_add_dimension():
        main_output = bg
        add_dimension_output = []
        for i in range(region.get_add_dimension_counter()):
            if f'{y_data}{i}' in region.get_data().columns:
                counts = region.get_data(column=f'{y_data}{i}')
                bg = get_shirley_bg(energy, counts, tolerance, maxiter)
                if bg is None:
                    helpers_logger.warning(f"{region.get_id()} : Add-dimension line {i} - "
                                           f"Shirley background calculation failed due to excessive iterations")
                    bg = counts * 0
                add_dimension_output.append(bg)
                if add_column:
                    corrected = counts - bg
                    if np.amin(corrected) < 0:
                        corrected += np.absolute(np.amin(corrected))
                    region.add_column(f"no_shirley{i}", corrected, overwrite=True)
        return main_output, add_dimension_output
    return bg


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
        shirley_bg = subtract_shirley(region, tolerance=tolerance, maxiter=maxiter, add_column=add_column)
        linear_bg = subtract_linear_bg(region, y_data='no_shirley', by_min=by_min, add_column=add_column)
    else:
        linear_bg = subtract_linear_bg(region, by_min=by_min, add_column=add_column)
        shirley_bg = subtract_shirley(region, y_data="no_lin_bg", tolerance=tolerance, maxiter=maxiter,
                                      add_column=add_column)
    background = linear_bg + shirley_bg
    if add_column:
        region.add_column("no_lin_no_shirley", counts - background, overwrite=overwrite)

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


def normalize(region, y_data='final', const=None, add_column=True):
    """Normalize counts by maximum. If const is given, normalizes by this number. If add_dimension region is received
    normalizes the main (integrated) columns 'counts', 'final' etc. as usual. Other columns are normalized as well in
    the case const is None (takes max of every add_dimesion column) or normalize by a constant if a list of
    corresponding constants is provided. In case single constant is provided, add_dimension columns 'final0', 'final1'
    etc. are not normalized.
    """
    # If we want to use other column than "final" for calculations
    if not region.is_add_dimension():
        if is_iterable(const):
            return False
        else:
            y = region.get_data(column=y_data)
            if const:
                output = y / float(const)
            else:
                output = y / float(max(y))
            if add_column:
                region.add_column("normalized", output, overwrite=True)
                return True
            else:
                return output
    else:
        if not const:
            for i in range(region.get_add_dimension_counter()):
                if f'{y_data}{i}' in list(region.get_data()):
                    y = region.get_data(column=f'{y_data}{i}')
                    region.add_column(f"normalized{i}", y / float(np.amax(y)), overwrite=True)
                    y = region.get_data(column=f'{y_data}')
                    region.add_column(f"normalized", y / float(np.amax(y)), overwrite=True)
        # If const is provided it should be iterable containing values for every corresponding add-dimension column
        # elif isinstance(const, Iterable):
        else:
            output = []
            if is_iterable(const):
                if len(const) == region.get_add_dimension_counter():
                    main_res = region.get_data(column=y_data) / float(np.mean(const))
                    for i, constant in enumerate(const):
                        res = region.get_data(column=f'{y_data}{i}') / float(constant)
                        if add_column:
                            region.add_column("normalized", main_res, overwrite=True)
                            region.add_column(f"normalized{i}", res, overwrite=True)
                        else:
                            output.append(res)
                    if add_column:
                        return True
                    else:
                        return main_res, output
                else:
                    helpers_logger.warning(f"Add-dimension data in region {region.get_id()} was not normalized.")
                    return False
            else:
                main_res = region.get_data(column=y_data) / float(const)
                for i in range(region.get_add_dimension_counter()):
                    res = region.get_data(column=f'{y_data}{i}') / float(const)
                    if add_column:
                        region.add_column("normalized", main_res, overwrite=True)
                        region.add_column(f"normalized{i}", res, overwrite=True)
                    else:
                        output.append(res)
                if add_column:
                    return True
                else:
                    return main_res, output


def normalize_by_background(region, start, stop, y_data='counts', add_column=True):
    """Correct counts by the average background level given by the interval [start, stop]
    """
    # If we want to use other column than "counts" for calculations
    counts = region.get_data(column=y_data)
    energy = region.get_data(column='energy')

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


def normalize_group(regionscollection, y_data: str = 'final',
                    const: float = None, add_column: bool = True) -> bool:
    """Normalize y-axis of all regions in the RegionsCollection by the maximum y-value of all included regions.
       If const is given, normalizes by this number. If add_dimension region is received
       normalizes the main (integrated) columns 'counts', 'final' etc. only.
    """
    # If we want to use other column than "counts" for calculations
    regions = regionscollection.get_regions()
    if const:
        if is_iterable(const) and len(const) == len(regions):
            for i, region in enumerate(regions):
                output = normalize(region, y_data=y_data, const=const[i], add_column=False)
                if region.is_add_dimension():
                    output = output[0]
                if add_column:
                    region.add_column("groupnormalized", output, overwrite=True)
            return True
        elif is_iterable(const) and len(const) != len(regions):
            helpers_logger.warning(f"Regions collection was not normalized because number of normalization"
                                   f"constants was not equal to number of regions.")
            return False
        elif not is_iterable(const):
            for region in regions:
                output = normalize(region, y_data=y_data, const=const, add_column=False)
                if region.is_add_dimension():
                    output = output[0]
                if add_column:
                    region.add_column("groupnormalized", output, overwrite=True)
            return True

    # Normalization coefficient for all regions (max y-value of all regions from y_data column)
    allmax = max([np.max(region.get_data(column=y_data)) for region in regions if len(region.get_data(column=y_data)) > 0])
    for region in regions:
        output = normalize(region, y_data=y_data, const=allmax, add_column=False)
        if region.is_add_dimension():
            output = output[0]
        if add_column:
            region.add_column("groupnormalized", output, overwrite=True)
    return True


def shift_by_background(region, interval, y_data='final', add_column=True):
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

    main_output = counts - float(np.mean(counts[first_index:last_index]))
    add_dimension_outputs = []
    if add_column:
        region.add_column("bgshifted", main_output, overwrite=True)
    if region.is_add_dimension():
        for i in range(region.get_add_dimension_counter()):
            if f'{y_data}{i}' in region.get_data().columns:
                counts = region.get_data(column=f'{y_data}{i}')
                output = counts - float(np.mean(counts[first_index:last_index]))
                add_dimension_outputs.append(output)
                if add_column:
                    region.add_column(f"bgshifted{i}", output, overwrite=True)
    if add_dimension_outputs:
        return main_output, add_dimension_outputs
    else:
        return main_output


def ask_path(folder_flag=True, multiple_files_flag=False):
    """Makes a tkinter dialog for choosing the folder if folder_flag=True
    or file(s) otherwise. For multiple files the multiple_files_flag should
    be True.
    """
    # This method is almost never used, so the required imports are locally called
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    path = os.getcwd()
    if folder_flag:  # Open folder
        path = filedialog.askdirectory(parent=root, initialdir=path, title='Please select directory')
    else:  # Open file
        if multiple_files_flag:
            path = filedialog.askopenfilenames(parent=root, initialdir=path, title='Please select data files')
            path = root.tk.splitlist(path)
        else:
            path = filedialog.askopenfilename(parent=root, initialdir=path, title='Please select data file')
    root.destroy()
    return path
