import logging
from matplotlib.figure import Figure


plotter_logger = logging.getLogger("specqp.plotter")  # Creating child logger


def plot_region(region, axs, x_data='energy', y_data='final', invert_x=True, log_scale=False, y_offset=0,
                scatter=False, label=None, color=None, title=True, font_size=8,
                legend=True, legend_features=('Temperature',), legend_pos='best'):
    """Plotting spectrum with matplotlib using given axes and a number of optional arguments. legend_features parameter
    allows for adding distinguishing features to each plotted curve taking their values from Region._conditions.
    """
    if x_data in list(region.get_data()):
        x = region.get_data(column=x_data)
    else:
        x = region.get_data(column='energy')
    if y_data in list(region.get_data()):
        y = region.get_data(column=y_data)
    else:
        y = region.get_data(column='counts')

    if not label:
        label = f"{region.get_id()}"
        features = region.get_conditions()
        if legend_features and features:
            for legend_feature in legend_features:
                if legend_feature in features:
                    label = " : ".join([label, features[legend_feature]])
        elif legend_features and not features:
            plotter_logger.info(f"Conditions for region {region.get_id()} are not known.")

    # If we want scatter plot
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


def plot_peak(peak, axs, y_offset=0, label=None, color=None, fill=True, legend=True, legend_pos='best', font_size=8):
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
        label = f"Cen: {peak.get_parameters('center'):.2f}; LorentzFWHM: {peak.get_parameters('fwhm'):.2f}"

    axs.plot(peak.get_data()[0], peak.get_data()[1] + y_offset, color=color, label=label)
    if fill:
        # Fill the peak shape with color that is retrieved from the last plotted line
        axs.fill_between(peak_line[0], peak_line[1].min() + y_offset, peak_line[1] + y_offset,
                        facecolor=axs.get_lines()[-1].get_color(), alpha=0.3)
    if legend:
        axs.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': font_size})


def plot_fit(fitter, axs, y_offset=0, label=None, color='black', legend=True, legend_pos='best',
             addresiduals=True, font_size=8):
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


class SpecqpPlot(Figure):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
