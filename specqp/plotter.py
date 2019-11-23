import logging
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable

from specqp import helpers
from specqp.datahandler import Region
# import helpers

plotter_logger = logging.getLogger("specqp.plotter")  # Creating child logger


def _get_arrays(region, x_data='energy', y_data='final'):
    """
    :param region: Region object
    :param x_data: region's column name
    :param y_data: region's column name
    :return: ndarrays of specified columns' values
    """
    if x_data in list(region.get_data()):
        x = region.get_data(column=x_data)
    else:
        x = region.get_data(column='energy')
    if y_data in list(region.get_data()):
        y = region.get_data(column=y_data)
    else:
        y = region.get_data(column='final')

    return x, y


def _make_label(region, legend_features=None):
    def _add_to_label(lbl: str, new_lbl_entry: str):
        if not bool(lbl):  # If label is empty
            lbl = "".join([lbl, new_lbl_entry])
        else:
            lbl = " : ".join([lbl, new_lbl_entry])
        return lbl

    label = ""
    if 'ID' in legend_features:
        label = _add_to_label(label, f"{region.get_id()}")
    for entry in legend_features:
        if entry in Region.info_entries:
            label = _add_to_label(label, f"{region.get_info(entry)}")
    features = region.get_conditions()
    if "Conditions" in legend_features and features:
        label = _add_to_label(label, f"{region.get_conditions(as_string=True)}")
    elif legend_features and features:
        for legend_feature in legend_features:
            if legend_feature in features:
                label = _add_to_label(label, features[legend_feature])
    elif legend_features and not features:
        plotter_logger.info(f"Conditions for region {region.get_id()} are not known.")
    return label


def plot_add_dimension(region, axs, x_data='energy', y_data='final', invert_x=True, log_scale=False, y_offset=0.0,
                       global_y_offset=0.0, scatter=False, label=None, color=None, title=False, font_size=12,
                       legend=True, legend_features=None, legend_pos='best', plot2D=False, colormap=None):
    """

    :param region: region object
    :param axs: Matplotlib axis object
    :param x_data: type string. Name of the region's data column to plot on X-axis
    :param y_data: type string. Name of the region's data column to plot on Y-axis
    :param invert_x: True/False for the X-axis (Binding/Kinetic energy representation)
    :param log_scale: True/False for the Y-axis
    :param y_offset: offset for each next curve along the Y-axis
    :param global_y_offset: common offset for all curves along the Y-axis
    :param scatter: scatter or solid line-shape
    :param label: label of curves. Can be list of labels for all add-dimension curves.
    :param color: color of curves. Can be list of colors for all add-dimension curves.
    :param title: General title of the plot
    :param font_size:
    :param legend: True/Flase
    :param legend_features: What info to add to the labels from the region's infp section.
    For example, legend_features=('Temperature',)
    :param legend_pos: Legend position according to matplotlib rules. For example, 'best'
    :param plot2D: 2D plot
    :return: None
    """
    if not region.is_add_dimension():
        # plot_region(region, axs, x_data=x_data, y_data=y_data, invert_x=invert_x, log_scale=log_scale, y_offset=y_offset,
        #             scatter=scatter, label=label, color=color, title=title, font_size=font_size,
        #             legend=legend, legend_features=legend_features, legend_pos=legend_pos)
        plotter_logger.warning(f"Region {region.get_id()} was not plotted because it is not add-dimension.")
        return

    n_curves = region.get_add_dimension_counter()

    if plot2D:
        x, _ = _get_arrays(region, x_data=f'{x_data}')
        y = list(range(1, n_curves + 1))
        z = [_get_arrays(region, y_data=f'{y_data}{i}')[1] for i in range(n_curves)]
        cs = axs.contourf(x, y, z, cmap=colormap)
        # divider = make_axes_locatable(axs)
        # cax = divider.append_axes("right", size="5%", pad=0.05)
        # axs.get_figure().colorbar(cs, cax=cax, fraction=0.15)
        cbar = axs.get_figure().colorbar(cs, fraction=0.15)
        axs.tick_params(axis='both', which='both', labelsize=font_size)
        if title:
            if region.is_sweeps_normalized():
                title_str = f"Pass: {region.get_info('Pass Energy')} | File: {region.get_info('File Name')}"
            else:
                if region.is_add_dimension():
                    title_str = f"Pass: {region.get_info('Pass Energy')} " \
                                f" | Sweeps: {int(region.get_info('Sweeps Number')) * region.get_add_dimension_counter()}" \
                                f" | File: {region.get_info('File Name')}"
                else:
                    title_str = f"Pass: {region.get_info('Pass Energy')} | Sweeps: {region.get_info('Sweeps Number')}" \
                                f" | File: {region.get_info('File Name')}"
            axs.set_title(title_str, fontsize=font_size)
        #   Stiling axes
        x_label_prefix = "Binding"
        if region.get_info("Energy Scale") == "Kinetic":
            x_label_prefix = "Kinetic"
        axs.set_xlabel(f"{x_label_prefix} energy (eV)", fontsize=font_size)
        axs.set_ylabel("Scan number", fontsize=font_size)
        # Inverting x-axis if desired and not yet inverted
        if invert_x and not axs.xaxis_inverted():
            axs.invert_xaxis()
        return

    if label and not helpers.is_iterable(label):
        label = [f'{label} : sweep {i}' for i in range(1, n_curves + 1)]
    elif (label and len(label) != n_curves) or not label:
        #plotter_logger.info(f"Labels for region {region.get_id()} plotting were set to defaults.")
        label = _make_label(region, legend_features=legend_features)
        label = [f'{label} : sweep {i}' for i in range(1, n_curves + 1)]

    if color and not helpers.is_iterable(color):
        color = [color for _ in range(1, n_curves + 1)]
    elif (color and len(color) != n_curves) or not color:
        color = [None for _ in range(1, n_curves + 1)]

    for i in range(n_curves):
        x, y = _get_arrays(region, x_data=f'{x_data}{i}', y_data=f'{y_data}{i}')
        if global_y_offset:
            y += global_y_offset
        _plot_curve(x, y, region, axs, invert_x=invert_x, log_scale=log_scale, y_offset=i*y_offset,
                    scatter=scatter, label=label[i], color=color[i], title=title, font_size=font_size,
                    legend=legend, legend_features=legend_features, legend_pos=legend_pos)


def plot_region(region, axs, x_data='energy', y_data='final', invert_x=True, log_scale=False, y_offset=0,
                scatter=False, label=None, color=None, title=True, font_size=12,
                legend=True, legend_features=None, legend_pos='best'):
    """Plotting spectrum with matplotlib using given axes and a number of optional arguments. legend_features parameter
    allows for adding distinguishing features to each plotted curve taking their values from Region._conditions.
    Example: legend_features=('Temperature',)
    """
    x, y = _get_arrays(region, x_data, y_data)
    _plot_curve(x, y, region, axs, invert_x=invert_x, log_scale=log_scale, y_offset=y_offset,
                scatter=scatter, label=label, color=color, title=title, font_size=font_size,
                legend=legend, legend_features=legend_features, legend_pos=legend_pos)


def _plot_curve(x, y, region, axs, invert_x=True, log_scale=False, y_offset=0.0,
                scatter=False, label=None, color=None, title=True, font_size=12,
                legend=True, legend_features=None, legend_pos='best'):

    if label is None:
        label = _make_label(region, legend_features=legend_features)
    # If we want scatter plot
    if not bool(label):
        label = " "
    if scatter:
        axs.scatter(x, y + y_offset, s=7, c=color, label=label)
    else:
        axs.plot(x, y + y_offset, color=color, label=label)
    axs.tick_params(axis='both', which='both', labelsize=font_size)
    if legend:
        if legend_pos == 'lower center':
            axs.set_ylim(ymin=-1 * max(y.tolist()))
            axs.tick_params(
                axis='y',  # changes apply to the y-axis
                which='both',  # both major and minor ticks are affected
                left=False,  # ticks along the left edge are off
                right=False)  # ticks along the right edge are off
        axs.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': font_size})
    if title:
        if region.is_sweeps_normalized():
            title_str = f"Pass: {region.get_info('Pass Energy')} | File: {region.get_info('File Name')}"
        else:
            if region.is_add_dimension():
                title_str = f"Pass: {region.get_info('Pass Energy')} " \
                    f" | Sweeps: {int(region.get_info('Sweeps Number'))*region.get_add_dimension_counter()}" \
                    f" | File: {region.get_info('File Name')}"
            else:
                title_str = f"Pass: {region.get_info('Pass Energy')} | Sweeps: {region.get_info('Sweeps Number')}" \
                    f" | File: {region.get_info('File Name')}"
        axs.set_title(title_str, fontsize=font_size)

    #   Stiling axes
    x_label_prefix = "Binding"
    if region.get_info("Energy Scale") == "Kinetic":
        x_label_prefix = "Kinetic"

    axs.set_xlabel(f"{x_label_prefix} energy (eV)", fontsize=font_size)
    axs.set_ylabel("Counts (a.u.)", fontsize=font_size)

    # Inverting x-axis if desired and not yet inverted
    if invert_x and not axs.xaxis_inverted():
        axs.invert_xaxis()

    if log_scale:
        axs.set_yscale('log')

    # Switch to scientific notation when y-axis numbers get bigger than 4 digits
    if max(y) > 9999:
        axs.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))


def plot_peak(peak, axs, y_offset=0.0, label=None, color=None, fill=True, legend=True, legend_pos='best', font_size=12):
    """
    Plotting one peak from Fitter object
    :param peak: Peak object
    :param axs: matplotlib.figure.axes object
    :param y_offset: vertical offset of the plot
    :param label: legend entry
    :param color: color
    :param fill: fills the peak area with half-transparent color (same as the color of the curve)
    :param legend: Enable/disable legend
    :param legend_pos: legend position
    :param font_size: font_size for all text within the axes object
    :return: None
    """
    peak_line = peak.get_data()
    if not label:
        label = f"Cen: {peak.get_parameters('center'):.2f}; LorentzFWHM: {peak.get_parameters('l_fwhm'):.2f}"

    plot_peak_xy(peak_line[0], peak_line[1], axs, y_offset=y_offset, label=label, color=color,
                 fill=fill, legend=legend, legend_pos=legend_pos, font_size=font_size)


def plot_peak_xy(x, y, axs, y_offset=0.0, label=None, baseline=None,
                 color=None, fill=True, legend=True, legend_pos='best', font_size=12):
    """Plotting one peak by given (x, y) points
    :param x: x coordinates
    :param y: y coordinates
    :param axs: matplotlib.figure.axes object
    :param y_offset: vertical offset of the plot
    :param label: legend entry
    :param color: color
    :param fill: fills the peak area with half-transparent color (same as the color of the curve)
    :param legend: Enable/disable legend
    :param legend_pos: legend position
    :param font_size: font_size for all text within the axes object
    :return: None
    """
    axs.plot(x, y + y_offset, color=color, label=label)
    if fill:
        # Fill the peak shape with color that is retrieved from the last plotted line
        if baseline is not None:
            axs.fill_between(x, baseline + y_offset, y + y_offset, facecolor=axs.get_lines()[-1].get_color(), alpha=0.3)
        else:
            axs.fill_between(x, y.min() + y_offset, y + y_offset, facecolor=axs.get_lines()[-1].get_color(), alpha=0.3)
    if legend:
        axs.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': font_size})


def plot_fit(fitter, axs, y_offset=0, label=None, color='black', legend=True, legend_pos='best',
             addresiduals=True, font_size=12):
    """Plotting fit line with pyplot using given plt.figure and a number of optional arguments
    """
    if not label:
        label = f"fit {fitter.get_id()}"
    axs.plot(fitter.get_data()[0], fitter.get_fit_line() + y_offset, linestyle='--', color=color, label=label)
    # Add residuals if specified
    if addresiduals:
        axs.plot(fitter.get_data()[0], fitter.get_residuals() + y_offset, linestyle=':', alpha=1, color='black',
                label=f"Chi^2 = {fitter.get_chi_squared():.2f}\nRMS = {fitter.get_rms():.2f}")
    if legend:
        axs.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': font_size})


def stylize_axes(ax):
    ax.set_aspect('auto')
    ax.set_facecolor('None')
    ax.grid(which='both', axis='both', color='grey', linestyle=':')
    ax.spines['bottom'].set_color('black')
    ax.spines['left'].set_color('black')
    ax.tick_params(axis='x', colors='black')
    ax.tick_params(axis='y', colors='black')
    ax.yaxis.label.set_color('black')
    ax.xaxis.label.set_color('black')


class SpecqpPlot(Figure):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
