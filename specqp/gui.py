import os
import copy
from shutil import copyfile
import re
import datetime
import ntpath
import logging
import webbrowser

import pandas as pd
import numpy as np

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, simpledialog, messagebox

import matplotlib
from matplotlib import pyplot as plt
from matplotlib import cm
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
import matplotlib.image as mpimg
import matplotlib.animation as animation

from specqp import service
from specqp import datahandler
from specqp import plotter
from specqp import helpers
from specqp import fitter
from specqp.globalfitter import GlobalFit

# Default font for the GUI
LARGE_FONT = ("Verdana", "12")

COLORS = ['gray', 'navy', 'blue', 'turquoise', 'cyan', 'aquamarine', 'green', 'khaki', 'yellow', 'gold',
          'goldenrod', 'salmon', 'orange', 'coral', 'tomato', 'red', 'pink', 'maroon', 'purple', 'thistle']

gui_logger = logging.getLogger("specqp.gui")  # Creating child logger
matplotlib.use('TkAgg')  # Configuring matplotlib interaction with tkinter
style.use('ggplot')  # Configuring matplotlib style

logo_img_file = os.path.dirname(os.path.abspath(__file__)) + "/assets/specqp_icon.png"
BG = "#ececec"


class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create a proxy for the underlying widget
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, *args):
        # Let the actual widget perform the requested action
        cmd = (self._orig,) + args
        result = self.tk.call(cmd)

        # Generate an event if scrolling wheel was used or scroll slider dragged
        if (args[0:2] == ("yview", "scroll") or
            args[0:2] == ("yview", "moveto")):
            self.event_generate("<<Change>>", when="tail")

        # Return what the actual widget returned
        return result


class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget

    def redraw(self, *args):
        """Redraws line numbers
        """
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True:
            dline= self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(1, y, anchor="nw", text=linenum, font=LARGE_FONT,
                            fill="gray55")
            i = self.textwidget.index("%s+1line" % i)


class FileViewerWindow(ttk.Frame):
    """Frame with a text widget for displaying the data files
    """
    def __init__(self, parent, filepath, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.text = CustomText(self, highlightthickness=0, font=LARGE_FONT, background="lightgrey", borderwidth=0)
        self.vsb = tk.Scrollbar(self, highlightthickness=0, borderwidth=0, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=self.vsb.set)
        self.linenumbers = TextLineNumbers(self, highlightthickness=0, borderwidth=0, background="lightgrey", width=30)
        self.linenumbers.attach(self.text)

        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.linenumbers.pack(side=tk.LEFT, fill=tk.Y)

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

        try:
            with open(filepath, "r") as file:
                self.text.insert(0.0, file.read())
                self.text.config(state=tk.DISABLED)
        except OSError:
            gui_logger.warning(f"Can't open the file {filepath}", exc_info=True)
            self.winfo_toplevel().display_message(f"Can't open the file {filepath}")
            self.text.insert(0.0, f"Can't open the file: {filepath}")
            self.text.config(state=tk.DISABLED)
            pass
        except ValueError:
            gui_logger.warning(f"Can't decode the file {filepath}", exc_info=True)
            self.winfo_toplevel().display_message(f"Can't decode the file {filepath}")
            self.text.insert(0.0, f"The file can't be decoded': {filepath}")
            self.text.config(state=tk.DISABLED)
            pass

    def _on_change(self, event):
        self.linenumbers.redraw()


class BrowserTreeView(ttk.Frame):
    def __init__(self, parent, default_items=None, label='main', *args, **kwargs):
        """Creates a check list with loaded file names as sections and corresponding regions IDs as checkable items
        :param default_items: dictionary {"file_name1": ("ID1, ID2,..."), "file_name2": ("ID1", "ID2", ...)}
        :param args:
        :param kwargs:
        """
        super().__init__(parent, *args, **kwargs)
        if label and label == 'main':
            self.winfo_toplevel().gui_widgets["BrowserTreeView"] = self

            self.check_all_frame = ttk.Frame(self)
            self.check_all_frame.pack(side=tk.TOP, fill=tk.X, expand=False)

        self.scrollable_canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scrollable_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.scrollable_canvas.yview)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollable_canvas.configure(yscrollcommand=self.vsb.set)

        self.treeview = ttk.Frame(self.scrollable_canvas)
        self.treeview.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.interior_id = self.scrollable_canvas.create_window((0, 0), window=self.treeview, anchor='nw')
        self.treeview.bind("<Configure>", self._configure_treeview)
        self.scrollable_canvas.bind('<Enter>', self._bound_to_mousewheel)
        self.scrollable_canvas.bind('<Leave>', self._unbound_to_mousewheel)
        self.treeview.bind('<Enter>', self._bound_to_mousewheel)
        self.treeview.bind('<Leave>', self._unbound_to_mousewheel)
        self.vsb.bind('<Enter>', self._bound_to_mousewheel)
        self.vsb.bind('<Leave>', self._unbound_to_mousewheel)

        if label and label == 'main':
            # When the check list items will be created, the "Check all" item should appear and rule them all.
            self.check_all_item = None
            self.check_all_box = None
            self.check_list_items = []
            self.check_boxes = []
            if default_items:
                for key, val in default_items.items():
                    self.add_items_to_check_list(key, val)

    def _bound_to_mousewheel(self, event):
        self.scrollable_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _change_check_all(self):
        for item in self.check_list_items:
            if not item.get():
                self.check_all_box.deselect()
                return
        self.check_all_box.select()

    def _configure_treeview(self, event):
        # Update the scrollbars to match the size of the inner frame
        self.scrollable_canvas.config(scrollregion=f"0 0 {self.treeview.winfo_reqwidth()} {self.treeview.winfo_reqheight()}")
        if self.treeview.winfo_reqwidth() != self.scrollable_canvas.winfo_width():
            # Update the canvas's width to fit the inner frame
            self.scrollable_canvas.config(width=self.treeview.winfo_reqwidth())

    def _on_mousewheel(self, event):
        # For OSX use event.delta
        # For Wondows use (event.delta / 120)
        # For X11 systems use (event.delta / number), number depends on the desired speed of scrolling. Also the binding
        # should be done for <Button-4> and <Button-5>
        if self.treeview.winfo_height() > self.winfo_height():
            self.scrollable_canvas.yview_scroll(int(-1 * event.delta), "units")

    def _toggle_all(self):
        for cb in self.check_boxes:
            if self.check_all_item.get():
                cb.select()
            else:
                cb.deselect()
        self.update()

    def _unbound_to_mousewheel(self, event):
        self.scrollable_canvas.unbind_all("<MouseWheel>")

    def add_items_to_check_list(self, section_name, items):
        """A call to the function dinamically adds a section with loaded regions IDs to the checkbox list
        :param section_name: the name of the file that was loaded
        :param items: the IDs of regions loaded from the file
        :return: None
        """
        if type(items) is str or not helpers.is_iterable(items):
            items = [items]
        # When the first item(s) are added, add the "Check all" button on top.
        if not self.check_list_items:
            if items:
                self.check_all_item = tk.StringVar(value="Check all")
                self.check_all_box = tk.Checkbutton(self.check_all_frame, var=self.check_all_item, text="Check all",
                                                    onvalue="Check all", offvalue="", background=BG,
                                                    anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                    command=self._toggle_all
                                                    )
                self.check_all_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
                sep = ttk.Separator(self.check_all_frame, orient=tk.HORIZONTAL)
                sep.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)

        file_name_label = ttk.Label(self.treeview, text=section_name, anchor=tk.W)
        file_name_label.pack(side=tk.TOP, fill=tk.X)
        for item in items:
            var = tk.StringVar(value=item)
            self.check_list_items.append(var)
            cb = tk.Checkbutton(self.treeview, var=var, text=item,
                                onvalue=item, offvalue="", background=BG,
                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                command=self._change_check_all
                                )
            cb.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
            self.check_boxes.append(cb)

    def get_checked_items(self):
        values = []
        for item in self.check_list_items:
            value = item.get()
            if value:
                values.append(value)
        return values


class BrowserPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["BrowserPanel"] = self
        # Action buttons panel
        self.buttons_panel = ttk.Frame(self, borderwidth=1, relief="groove")
        # Action buttons
        self.load_label = ttk.Label(self.buttons_panel,
                                    text="Load File", anchor=tk.W)
        self.load_label.pack(side=tk.TOP, fill=tk.X)
        self.add_sc_file_button = ttk.Button(self.buttons_panel,
                                             text='Load SCIENTA', command=self._ask_load_scienta_file)
        self.add_sc_file_button.pack(side=tk.TOP, fill=tk.X)
        self.add_sp_file_button = ttk.Button(self.buttons_panel,
                                             text='Load SPECS', command=self._ask_load_specs_file)
        self.add_sp_file_button.pack(side=tk.TOP, fill=tk.X)
        self.blank_label = ttk.Label(self.buttons_panel,
                                     text="", anchor=tk.W)
        self.blank_label.pack(side=tk.TOP, fill=tk.X)
        self.app_quit_button = ttk.Button(self.buttons_panel,
                                          text='Quit', command=self._quit)
        self.app_quit_button.pack(side=tk.TOP, fill=tk.X)
        self.buttons_panel.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Files tree panel
        self.spectra_tree_panel = BrowserTreeView(self, label='main', borderwidth=1, relief="groove")
        self.spectra_tree_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _ask_load_scienta_file(self):
        self.winfo_toplevel().load_file(file_type=datahandler.DATA_FILE_TYPES[0])

    def _ask_load_specs_file(self):
        self.winfo_toplevel().load_file(file_type=datahandler.DATA_FILE_TYPES[1])

    def _quit(self):
        self.winfo_toplevel().quit()  # stops mainloop


class PlotPanel(ttk.Frame):
    def __init__(self, parent, label=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.figure = plotter.SpecqpPlot(dpi=100)
        self.figure_axes = self.figure.add_subplot(111)
        if label and label == 'main':  # The main-window plot frame is being created
            self.winfo_toplevel().gui_widgets["PlotPanel"] = self
            self.start_page_img = mpimg.imread(logo_img_file)
            self.figure_axes.set_axis_off()
            self.figure_axes.imshow(self.start_page_img)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self) #CustomToolbar(self.canvas, self)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        # self.canvas.mpl_connect("key_press_event", self._on_key_press)
        # self.canvas.mpl_connect("button_press_event", self._on_mouse_click)

    # def _on_key_press(self, event):
    #     gui_logger.debug(f"{event.key} pressed on plot canvas")
    #     key_press_handler(event, self.canvas, self.toolbar)

    # def _on_mouse_click(self, event):
    #     gui_logger.debug(f"{event.button} pressed on plot canvas")
    #     key_press_handler(event, self.canvas, self.toolbar)

    def plot_fit(self, reg, fobj, ymin=None, ymax=None, region_color=None, colors=None, fill=True, residuals=None,
                 fitline="True", bg="", ax=None, legend_feature=("ID",), legend_pos='best', title=False, font_size=12):
        """Plots region data with fit line, fitted peaks and residuals
        :param reg: region object
        :param fobj: fitter object
        :return: None
        """
        if not ax:
            ax = self.figure_axes
        ax.clear()

        peaks = fobj.get_peaks()
        if helpers.is_iterable(fill):
            assert len(fill) == len(peaks)
        else:
            fill = [fill]
            for _ in range(len(peaks)):
                fill.append(fill[0])

        for i, peak in enumerate(peaks):
            if peak:
                peak_data = peak.get_virtual_data()
                baseline = None
                _, bg_y = fobj.get_virtual_bg()
                if np.max(bg_y) > 0:
                    baseline=bg_y
                if colors is not None and colors[i] != "Default color":
                    plotter.plot_peak_xy(peak_data[0], peak_data[1] + bg_y, ax, baseline=baseline,
                                         legend_pos=legend_pos, font_size=font_size, fill=fill[i],
                                         label=f"{peak.get_parameters('center'):.2f}", color=colors[i])
                else:
                    plotter.plot_peak_xy(peak_data[0], peak_data[1] + bg_y, ax, baseline=baseline,
                                         legend_pos=legend_pos, font_size=font_size, fill=fill[i],
                                         label=f"{peak.get_parameters('center'):.2f}")

        if region_color is None:
            region_color = 'red'
        invert_x = True
        if not reg.is_binding():
            invert_x = False
        plotter.plot_region(reg, ax, color=region_color, scatter=True, font_size=font_size, invert_x=invert_x,
                            legend_features=legend_feature, legend_pos=legend_pos, title=title)

        if bg is not None and bg != "":
            bg_x, bg_y = fobj.get_virtual_bg()
            ax.plot(bg_x, bg_y, linestyle='-', color='black', label=None, alpha=0.5)
        if fitline is not None and fitline != "":
            fitline_x, fitline_y = fobj.get_virtual_fitline(usebg=True)
            ax.plot(fitline_x, fitline_y, linestyle='--', color='black', label=None)
        # Add residuals
        if residuals is not None and residuals != "":
            ax.plot(fobj.get_data()[0], fobj.get_residuals(), linestyle=':', alpha=1, color='black', label=None)
            plotter.stylize_axes(ax)
        ax.set_ylim([ymin, ymax])
        ax.set_aspect(float(service.get_service_parameter("PLOT_ASPECT_RATIO"))/ax.get_data_ratio())
        self.canvas.draw()
        self.toolbar.update()

    def plot_regions(self, regions, ax=None, x_data='energy', y_data='final', ymin=None, ymax=None, log_scale=False,
                     y_offset=0.0, scatter=False, plot2D=False, label=None, color=None, title=True, font_size=12,
                     legend=True, legend_features=("ID", ), legend_pos='best', add_dimension=False, colormap=None):
        if regions:
            if not helpers.is_iterable(regions):
                regions = [regions]
            if not ax:
                ax = self.figure_axes
            ax.clear()
            if colormap:  # Calculate number of colors needed to plot all curves
                num_colors = 0
                for region in regions:
                    if add_dimension and region.is_add_dimension():
                        num_colors += region.get_add_dimension_counter()
                    else:
                        num_colors += 1
                cmap = cm.get_cmap(colormap)
                ax.set_prop_cycle('color', [cmap(1. * i / num_colors) for i in range(num_colors)])

            offset = 0
            invert_x = True
            if not regions[0].is_binding():
                invert_x = False
            for region in regions:
                if not add_dimension or not region.is_add_dimension():
                    plotter.plot_region(region, ax, x_data=x_data, y_data=y_data, invert_x=invert_x, log_scale=log_scale,
                                        y_offset=offset, scatter=scatter, label=label, color=color, title=title,
                                        font_size=font_size, legend=legend, legend_features=legend_features,
                                        legend_pos=legend_pos)
                    offset += y_offset
                else:
                    plotter.plot_add_dimension(region, ax, x_data=x_data, y_data=y_data, invert_x=invert_x, log_scale=log_scale,
                                               y_offset=y_offset, global_y_offset=offset, scatter=scatter, label=label,
                                               color=color, title=title, font_size=font_size, legend=legend,
                                               legend_features=legend_features, legend_pos=legend_pos, plot2D=plot2D,
                                               colormap=cm.get_cmap(colormap))
                    offset += y_offset * region.get_add_dimension_counter()
            if len(regions) > 1:
                ax.set_title(None)
            plotter.stylize_axes(ax)
            ax.set_ylim([ymin, ymax])
            ax.set_aspect(float(service.get_service_parameter("PLOT_ASPECT_RATIO"))/ax.get_data_ratio())
            self.canvas.draw()
            self.toolbar.update()

    def plot_trends(self, x, areas, ax=None, ymin=None, ymax=None, log_scale=False, y_offset=0.0, scatter=False,
                    labels=None, colors=None, font_size=12, legend=True, legend_pos='best'):
        if not ax:
            ax = self.figure_axes
        ax.clear()
        if not labels is None or len(labels) == 0:
            labels = list(range(len(areas)))
        offset = 0
        for i, trend in enumerate(areas):
            if scatter:
                ax.scatter(x, areas[i] + y_offset, s=7, c=colors[i], label=labels[i])
            else:
                ax.plot(x, areas[i] + y_offset, 'o-', color=colors[i], label=labels[i])
            offset += y_offset
        ax.set_xlabel(f"Scan number", fontsize=font_size)
        ax.set_ylabel("Peak area (a.u.)", fontsize=font_size)
        ax.set_title("Peak areas trends")
        plotter.stylize_axes(ax)
        ax.tick_params(axis='both', which='both', labelsize=font_size)
        ax.set_ylim([ymin, ymax])
        if legend:
            ax.legend(fancybox=True, framealpha=0, loc=legend_pos, prop={'size': font_size})
        if log_scale:
            ax.set_yscale('log')
        # Switch to scientific notation when y-axis numbers get bigger than 4 digits
        if np.max(areas) > 9999:
            ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
        ax.set_aspect(float(service.get_service_parameter("PLOT_ASPECT_RATIO")) / ax.get_data_ratio())
        self.canvas.draw()
        self.toolbar.update()

    def clear_figure(self):
        self.figure.clf()
        self.figure_axes = self.figure.add_subplot(111)


class CorrectionsPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["CorrectionsPanel"] = self
        self.regions_in_work = None
        # Adding widgets to settings two-columns section
        self._make_settings_subframe()
        # Blank label
        blank_label = ttk.Label(self, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        # Adding widgets to plotting settings two-columns section
        self._make_plotting_settings_subframe()
        # Blank label
        blank_label = ttk.Label(self, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        # Plot button
        self.plot = ttk.Button(self, text='Plot', command=self._plot)
        self.plot.pack(side=tk.TOP, fill=tk.X)
        # Show regions info
        self.show_info = ttk.Button(self, text='Show Regions Info', command=self._show_info)
        self.show_info.pack(side=tk.TOP, fill=tk.X)
        # Save buttons
        self.save = ttk.Button(self, text='Save', command=self._save)
        self.save.pack(side=tk.TOP, fill=tk.X)
        self.saveas = ttk.Button(self, text='Save as...', command=self._saveas)
        self.saveas.pack(side=tk.TOP, fill=tk.X)
        # Blank label
        blank_label = ttk.Label(self, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        # Fit
        self.fit_subframe = ttk.Frame(self)
        self.fit = ttk.Button(self.fit_subframe, text='Fit', command=self._fit)
        self.fit.pack(side=tk.LEFT, fill=tk.X, expand=False)
        self.select_fit_type = tk.StringVar()
        self.select_fit_type.set("Pseudo Voigt")
        options = list(fitter.Peak.peak_types.keys()) + ['Error Func']
        self.opmenu_fit_type = ttk.OptionMenu(self.fit_subframe, self.select_fit_type, self.select_fit_type.get(), *options)
        self.opmenu_fit_type.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.fit_subframe.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.advanced_fit = ttk.Button(self, text='Advanced Fit', command=self._do_advanced_fit)
        self.advanced_fit.pack(side=tk.TOP, fill=tk.X, expand=False)

    def _do_advanced_fit(self):
        regions_in_work = self._get_regions_in_work(checkbg=True)
        regions_to_fit = []
        if not self.regions_in_work:
            return
        if self.select_fit_type.get() not in fitter.Peak.peak_types.keys():
            self.winfo_toplevel().display_message("There is no advanced fitting routine available for Error Function.")
            return
        cmap = None if self.select_colormap.get() == "Default colormap" else self.select_colormap.get()
        plot_options = {
                        'scatter': bool(self.scatter_var.get()),
                        'legend': bool(self.plot_legend_var.get()),
                        'legend_features': tuple(self._get_legend_features()),
                        'title': bool(self.plot_title_var.get()),
                        'colormap': cmap
                        }
        if self.plot_add_dim_var.get():
            for region in regions_in_work:
                if region.is_add_dimension():
                    regions_to_fit += region.separate_add_dimension(region)
                else:
                    regions_to_fit.append(region)
        else:
            regions_to_fit = regions_in_work
        global_fit_window = AdvancedFitWindow(self.winfo_toplevel(), regions_to_fit,
                                              fittype=self.select_fit_type.get(), plot_options=plot_options)
        self.winfo_toplevel().update()  # Update to be able to request fit_window parameters
        global_fit_window.wm_minsize(width=global_fit_window.winfo_width(), height=global_fit_window.winfo_height())
        self.winfo_toplevel().fit_windows.append(global_fit_window)

    def _fit(self):
        fit_type = self.select_fit_type.get()
        self.regions_in_work = self._get_regions_in_work()
        if not self.regions_in_work:
            return
        es = self.energy_shift.get()
        if es:
            try:
                es = [float(es_str.strip()) for es_str in es.split(';')]
            except ValueError:
                return
        for i, region in enumerate(self.regions_in_work):
            if fit_type == 'Error Func':
                region.set_fermi_flag()
                # Special case: we didn't know that the region was Fermi before and might have corrected by the specified
                # energy shift. Here we can correct it back. Ambiguous result otherwise
                if region.is_energy_corrected():
                    region._flags["energy_shift_corrected"] = False
                    try:
                        if len(self.regions_in_work) != len(es):
                            region.correct_energy_shift(es[0])
                        else:
                            region.correct_energy_shift(es[i])
                    except ValueError:
                        return
                    region._flags["energy_shift_corrected"] = False
            # Transfer plotting options to the new fitting window
            plot_options = {'scatter': bool(self.scatter_var.get()),
                            'legend': bool(self.plot_legend_var.get()),
                            'legend_features': tuple(self._get_legend_features()),
                            'title': bool(self.plot_title_var.get()),
            }
            fit_window = FitWindow(self.winfo_toplevel(), region, fit_type, plot_options)
            self.winfo_toplevel().update()  # Update to be able to request fit_window parameters
            fit_window.wm_minsize(width=fit_window.winfo_width(), height=fit_window.winfo_height())
            self.winfo_toplevel().fit_windows.append(fit_window)

    def _get_legend_features(self):
        lfs = []
        if bool(self.plot_legend_fn_var.get()):
            lfs.append("File Name")
        if bool(self.plot_legend_rn_var.get()):
            lfs.append("Region Name")
        if bool(self.plot_legend_con_var.get()):
            lfs.append("Conditions")
        return lfs

    def _get_regions_in_work(self, checkbg=True):
        reg_ids = self.winfo_toplevel().gui_widgets["BrowserPanel"].spectra_tree_panel.get_checked_items()
        # We will work with copies of regions, so that the temporary changes are not stored
        regions_in_work = copy.deepcopy(self.winfo_toplevel().loaded_regions.get_by_id(reg_ids))
        if regions_in_work:
            pe = self.photon_energy.get()
            es = self.energy_shift.get()
            nc = self.const_norm_var.get()
            if pe:
                try:
                    pe = [float(pe_str.strip()) for pe_str in pe.split(';')]
                except ValueError:
                    gui_logger.warning("Check 'Photon Energy' values. Must be a number or a sequence separated by ';'.")
                    self.winfo_toplevel().display_message("Check 'Photon Energy' values. Must be a number or a sequence separated by ';'.")
                    return
            if es:
                try:
                    es = [float(es_str.strip()) for es_str in es.split(';')]
                except ValueError:
                    gui_logger.warning("Check 'Energy Shift' values. Must be a number or a sequence separated by ';'.")
                    self.winfo_toplevel().display_message("Check 'Energy Shifts' value. Must be a number or a sequence separated by ';'.")
                    return
            if nc:
                try:
                    nc = [float(nc_str.strip()) for nc_str in nc.split(';')]
                except ValueError:
                    gui_logger.warning("Check 'Normalize by const(s)' values. Must be a number or a sequence separated by ';'.")
                    self.winfo_toplevel().display_message("Check 'Normalize by const(s)' value. Must be a number or a sequence separated by ';'.")
                    return

            if self.plot_use_settings_var.get():
                service.set_init_parameters(["PHOTON_ENERGY", "ENERGY_SHIFT"],
                                            ["; ".join([str(s) for s in pe]), "; ".join([str(s) for s in es])])
                service.set_init_parameters("NORMALIZATION_CONSTANT", "; ".join([str(s) for s in nc]))
                # Check that the number of parameters is equal to the number of regions
                if len(pe) > 1 and len(pe) != len(regions_in_work):
                    msg = "Check the number of 'Photon Energy' values. Must be equal to the number of regions. " \
                          "First valid value was used for all regions."
                    gui_logger.warning(msg)
                    self.winfo_toplevel().display_message(msg)
                if len(es) > 1 and len(es) != len(regions_in_work):
                    msg = "Check the number of 'Energy Shift' values. Must be equal to the number of regions. " \
                          "First valid value was used for all regions."
                    gui_logger.warning(msg)
                    self.winfo_toplevel().display_message(msg)
                if len(nc) > 1 and len(nc) != len(regions_in_work):
                    msg = "Check the number of 'Normalize by const(s)' values. Must be equal to the number of regions. " \
                          "First valid value was used for all regions."
                    gui_logger.warning(msg)
                    self.winfo_toplevel().display_message(msg)

                for i, region in enumerate(regions_in_work):
                    if self.bin_add_dim_var.get():
                        if region.is_add_dimension() and int(self.bins_number_entry.get()) < region.get_add_dimension_counter():
                            drop_last_bin = False
                            if self.drop_last_bin_var.get():
                                drop_last_bin = True
                            try:
                                region = datahandler.Region.bin_add_dimension(region,
                                                                              nbins=int(self.bins_number_entry.get()),
                                                                              drop_remainder=drop_last_bin)
                            except ValueError:
                                self.winfo_toplevel().display_message("Check the number of bins. Must be integer.\n"
                                                                      "No binning done.")
                        elif not region.is_add_dimension():
                            self.winfo_toplevel().display_message(f"Not possible to bin non add-dimension region {region.get_id()}")
                        elif int(self.bins_number_entry.get()) > region.get_add_dimension_counter():
                            self.winfo_toplevel().display_message(f"Too many bins required for {region.get_id()}")

                    # Read Photon Energy value from the GUI and set it for the region
                    if len(pe) == 1:
                        region.set_excitation_energy(pe[0])
                    elif len(pe) == len(regions_in_work):
                        if pe[i]:
                            region.set_excitation_energy(pe[i])
                    elif len(pe) > 0:
                        for val in pe:
                            if bool(val):
                                region.set_excitation_energy(val)
                                break
                    # Read Energy Shift value from the GUI and set it for the region
                    if len(es) == 1 and not region.get_flags()["fermi_flag"]:
                        region.correct_energy_shift(es[0])
                        region.add_correction(f"Energy shift corrected by {round(es[0], int(service.service_vars['ROUND_PRECISION']))} eV")
                    elif len(es) == len(regions_in_work) and not region.get_flags()["fermi_flag"]:
                        if es[i]:
                            region.correct_energy_shift(es[i])
                            region.add_correction(f"Energy shift corrected by {round(es[i], int(service.service_vars['ROUND_PRECISION']))} eV")
                    elif len(es) > 0 and not region.get_flags()["fermi_flag"]:
                        for val in es:
                            if bool(val):
                                region.correct_energy_shift(val)
                                region.add_correction(f"Energy shift corrected by {round(val, int(service.service_vars['ROUND_PRECISION']))} eV")
                                break
                    if self.plot_binding_var.get():
                        region.invert_to_binding()
                    if self.plot_kinetic_var.get():
                        region.invert_to_kinetic()
                    if self.normalize_sweeps_var.get():
                        region.normalize_by_sweeps()
                        region.make_final_column("sweepsNormalized", overwrite=True)
                        region.add_correction(f"Normalized by {region.get_info('Sweeps Number')} sweeps")
                    if self.normalize_dwell_var.get():
                        region.normalize_by_dwell_time()
                        region.make_final_column("dwellNormalized", overwrite=True)
                        region.add_correction(f"Normalized by {region.get_info('Dwell Time')} dwell time")
                    if self.do_const_norm_var.get():
                        if len(nc) == 1:
                            helpers.normalize(region, y_data='final', const=nc[0], add_column=True)
                            region.make_final_column("normalized", overwrite=True)
                            region.add_correction(
                                f"Normalized by {round(nc[0], int(service.service_vars['ROUND_PRECISION']))}")
                        elif len(nc) == len(regions_in_work):
                            if nc[i]:
                                helpers.normalize(region, y_data='final', const=nc[i], add_column=True)
                                region.make_final_column("normalized", overwrite=True)
                                region.add_correction(
                                    f"Normalized by {round(nc[i], int(service.service_vars['ROUND_PRECISION']))}")
                        elif len(nc) > 0:
                            for val in nc:
                                if bool(nc):
                                    helpers.normalize(region, y_data='final', const=val, add_column=True)
                                    region.make_final_column("normalized", overwrite=True)
                                    region.add_correction(
                                        f"Normalized by {round(val, int(service.service_vars['ROUND_PRECISION']))}")
                                    break

                    if self.do_crop_var.get():
                        crop_left, crop_right = self.crop_left_var.get(), self.crop_right_var.get()
                        if crop_left and crop_right:
                            try:
                                region.crop_region(start=float(crop_left), stop=float(crop_right), changesource=True)
                                service.set_init_parameters("CROP", ';'.join([crop_left, crop_right]))
                            except ValueError:
                                gui_logger.warning("Check Crop values. Must be numbers.")
                                self.winfo_toplevel().display_message("Check crop values. Must be numbers.")
                    if checkbg:  # If we want to take background options into consideration
                        if self.subtract_const_var.get():
                            e = region.get_data('energy')
                            c = region.get_data('counts')
                            if np.mean(c[-10:-1]) < np.mean(c[0:10]):
                                helpers.shift_by_background(region, [e[-10], e[-1]])
                            else:
                                helpers.shift_by_background(region, [e[0], e[10]])
                            region.make_final_column("bgshifted", overwrite=True)
                            region.add_correction("Constant background subtracted")
                        if self.subtract_shirley_var.get():
                            helpers.subtract_shirley(region)
                            region.make_final_column("no_shirley", overwrite=True)
                            region.add_correction("Shirley background subtracted")

                        # If we were working on the copy of the region (e.g. after binning),
                        # we want to make it the member of regions_in_work list
                        if region is not regions_in_work[i]:
                            regions_in_work[i] = region
        #Rearange the sequence if chosen
        if regions_in_work and self.reorder_plots_var.get():
            try:
                new_order = [int(po.strip()) for po in self.plots_order_var.get().split(';')]
                if len(new_order) != len(regions_in_work):
                    self.winfo_toplevel().display_message("Check the plotting order sequence. "
                                                          "Must be as many numbers as regions plotted.")
                    return regions_in_work
                to_sort = {}
                for i, region in enumerate(regions_in_work):
                    to_sort[region] = new_order[i]
                rev = False
                if self.reverse_order_var.get():
                    rev = True
                sorted_regions = sorted(to_sort.items(), key=lambda kv: kv[1], reverse=rev)
                return list(zip(*sorted_regions))[0]
            except ValueError:
                self.winfo_toplevel().display_message("Check the plotting order sequence. "
                                                      "Must be numbers separated by ';'.")
        return regions_in_work

    def _make_plotting_settings_subframe(self):
        # Plot name label
        self.plotting_label = ttk.Label(self, text="Plotting", anchor=tk.W)
        self.plotting_label.pack(side=tk.TOP, fill=tk.X)
        # Initializing two-columns section
        self.plotting_two_columns = ttk.Frame(self)
        self.plotting_left_column = ttk.Frame(self.plotting_two_columns, width=self.settings_left_column.winfo_width())
        self.plotting_right_column = ttk.Frame(self.plotting_two_columns, width=self.settings_right_column.winfo_width())
        # Reorder plots
        reorder_plots_label = ttk.Label(self.plotting_left_column, text="Reorder plots", anchor=tk.W)
        reorder_plots_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        reorder_panel = ttk.Frame(self.plotting_right_column)
        self.reorder_plots_var = tk.StringVar(value="")
        self.reorder_plots_box = tk.Checkbutton(reorder_panel, var=self.reorder_plots_var,
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                )
        self.reorder_plots_box.pack(side=tk.LEFT, anchor=tk.W)
        self.plots_order_var = tk.StringVar(self, value=None)
        self.plots_order_entry = ttk.Entry(reorder_panel, textvariable=self.plots_order_var, width=10)
        self.plots_order_entry.pack(side=tk.LEFT, anchor=tk.W, expand=False)
        reverse_order = ttk.Label(reorder_panel, text="Reverse", anchor=tk.W)
        reverse_order.pack(side=tk.LEFT, anchor=tk.W, expand=False)
        self.reverse_order_var = tk.StringVar(value="")
        self.reverse_box = tk.Checkbutton(reorder_panel, var=self.reverse_order_var,
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.E, relief=tk.FLAT, highlightthickness=0
                                                )
        self.reverse_box.pack(side=tk.LEFT, anchor=tk.W)
        reorder_panel.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, expand=True)
        # Plot in new window checkbox
        self.plot_separate_label = ttk.Label(self.plotting_left_column, text="Plot in new window", anchor=tk.W)
        self.plot_separate_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_separate_var = tk.StringVar(value="")
        self.plot_separate_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_separate_var,
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                )
        self.plot_separate_box.pack(side=tk.TOP, anchor=tk.W)
        # Plot add-dimension if possible checkbox
        self.plot_add_dim_label = ttk.Label(self.plotting_left_column, text="Plot add-dimension", anchor=tk.W)
        self.plot_add_dim_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        add_dim_panel = ttk.Frame(self.plotting_right_column)
        self.plot_add_dim_var = tk.StringVar(value="")
        self.plot_add_dim_box = tk.Checkbutton(add_dim_panel, var=self.plot_add_dim_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                               )
        self.plot_add_dim_box.pack(side=tk.LEFT, anchor=tk.W)
        plot2D_label = ttk.Label(add_dim_panel, text="Plot 2D", anchor=tk.W)
        plot2D_label.pack(side=tk.LEFT, anchor=tk.W, expand=False)
        self.plot_2D_var = tk.StringVar(value="")
        self.plot_2D_box = tk.Checkbutton(add_dim_panel, var=self.plot_2D_var,
                                          onvalue="True", offvalue="", background=BG,
                                          anchor=tk.E, relief=tk.FLAT, highlightthickness=0
                                          )
        self.plot_2D_box.pack(side=tk.LEFT, anchor=tk.W)
        add_dim_panel.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, expand=True)
        # Bin add-dimension if possible checkbox
        bin_add_dim_label = ttk.Label(self.plotting_left_column, text="Bin add-dimension", anchor=tk.W)
        bin_add_dim_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        bins_panel = ttk.Frame(self.plotting_right_column)
        self.bin_add_dim_var = tk.StringVar(value="")
        self.bin_add_dim_box = tk.Checkbutton(bins_panel, var=self.bin_add_dim_var,
                                              onvalue="True", offvalue="", background=BG,
                                              anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                              )
        self.bin_add_dim_box.pack(side=tk.LEFT, anchor=tk.W)
        bins_number_label = ttk.Label(bins_panel, text="to N bins", anchor=tk.W)
        bins_number_label.pack(side=tk.LEFT, anchor=tk.W, expand=False)
        self.bins_number = tk.StringVar(self, value=1)
        self.bins_number_entry = ttk.Entry(bins_panel, textvariable=self.bins_number, width=3)
        self.bins_number_entry.pack(side=tk.LEFT, anchor=tk.W, expand=False)
        drop_last_label = ttk.Label(bins_panel, text="Drop tail", anchor=tk.W)
        drop_last_label.pack(side=tk.LEFT, anchor=tk.W, expand=False)
        self.drop_last_bin_var = tk.StringVar(value="True")
        self.drop_last_bin_box = tk.Checkbutton(bins_panel, var=self.drop_last_bin_var,
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.E, relief=tk.FLAT, highlightthickness=0
                                                )
        self.drop_last_bin_box.pack(side=tk.LEFT, anchor=tk.W)
        bins_panel.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, expand=True)
        # Use settings
        self.plot_use_settings_label = ttk.Label(self.plotting_left_column, text="Use settings", anchor=tk.W)
        self.plot_use_settings_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_use_settings_var = tk.StringVar(value="True")
        self.plot_use_settings_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_use_settings_var,
                                                    onvalue="True", offvalue="", background=BG,
                                                    anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                    command=self._toggle_settings)
        self.plot_use_settings_box.pack(side=tk.TOP, anchor=tk.W)
        # Binding energy axis
        self.energy_axis_label = ttk.Label(self.plotting_left_column, text="Energy axis", anchor=tk.W)
        self.energy_axis_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        if self.photon_energy.get():
            self.plot_binding_var = tk.StringVar(value="True")
        else:
            self.plot_binding_var = tk.StringVar(value="")
        self.plot_kinetic_var = tk.StringVar(value="")
        energy_axis_frame = ttk.Frame(self.plotting_right_column)
        binding_label = ttk.Label(energy_axis_frame, text="Binding", anchor=tk.W)
        binding_label.pack(side=tk.LEFT, expand=False)
        self.plot_binding_box = tk.Checkbutton(energy_axis_frame, var=self.plot_binding_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                               command=lambda: self._toggle_energy_axis('binding')
                                               )
        self.plot_binding_box.pack(side=tk.LEFT, anchor=tk.W)
        kinetic_label = ttk.Label(energy_axis_frame, text="Kinetic", anchor=tk.W)
        kinetic_label.pack(side=tk.LEFT, expand=False)
        self.plot_kinetic_box = tk.Checkbutton(energy_axis_frame, var=self.plot_kinetic_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                               command=lambda: self._toggle_energy_axis('kinetic')
                                               )
        self.plot_kinetic_box.pack(side=tk.LEFT, anchor=tk.W)
        energy_axis_frame.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, expand=True)
        # Offset
        self.offset_label = ttk.Label(self.plotting_left_column, text="Offset (% of max)", anchor=tk.W)
        self.offset_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.offset_subframe = ttk.Frame(self.plotting_right_column)
        self.offset_value_var = tk.IntVar(self, value=0)
        self.offset_value_entry = ttk.Entry(self.offset_subframe, textvariable=self.offset_value_var,
                                            width=3, state=tk.DISABLED, style='default.TEntry')
        self.offset_slider = ttk.Scale(self.offset_subframe, from_=0, to=100, orient=tk.HORIZONTAL,
                                       command=lambda x: self.offset_value_var.set(int(float(x))))
        self.offset_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.offset_value_entry.pack(side=tk.LEFT, expand=False)
        self.offset_subframe.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Scatter
        self.scatter_label = ttk.Label(self.plotting_left_column, text="Plot scatter", anchor=tk.W)
        self.scatter_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.scatter_var = tk.StringVar(value="")
        self.scatter_box = tk.Checkbutton(self.plotting_right_column, var=self.scatter_var,
                                          onvalue="True", offvalue="", background=BG,
                                          anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                          )
        self.scatter_box.pack(side=tk.TOP, anchor=tk.W)
        # Legend
        self.plot_legend_label = ttk.Label(self.plotting_left_column, text="Add legend", anchor=tk.W)
        self.plot_legend_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        legend_boxes = ttk.Frame(self.plotting_right_column)
        self.plot_legend_var = tk.StringVar(value="True")
        self.plot_legend_box = tk.Checkbutton(legend_boxes, var=self.plot_legend_var,
                                              onvalue="True", offvalue="", background=BG,
                                              anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                              command=self._toggle_legend_settings
                                              )
        self.plot_legend_box.pack(side=tk.LEFT, anchor=tk.W)
        init_legend_settings = service.get_service_parameter("LEGEND").split(';')
        # File name in the legend
        fn_label = ttk.Label(legend_boxes, text="FN", anchor=tk.W)
        fn_label.pack(side=tk.LEFT, fill=tk.X, anchor=tk.W)
        self.plot_legend_fn_var = tk.StringVar(value=init_legend_settings[0].strip())
        self.plot_legend_fn_box = tk.Checkbutton(legend_boxes, var=self.plot_legend_fn_var,
                                              onvalue="True", offvalue="", background=BG,
                                              anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                              )
        self.plot_legend_fn_box.pack(side=tk.LEFT, anchor=tk.W)
            # Region name in the legend
        rn_label = ttk.Label(legend_boxes, text="RN", anchor=tk.W)
        rn_label.pack(side=tk.LEFT, fill=tk.X, anchor=tk.W)
        self.plot_legend_rn_var = tk.StringVar(value=init_legend_settings[1].strip())
        self.plot_legend_rn_box = tk.Checkbutton(legend_boxes, var=self.plot_legend_rn_var,
                                              onvalue="True", offvalue="", background=BG,
                                              anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                              )
        self.plot_legend_rn_box.pack(side=tk.LEFT, anchor=tk.W)
            # Conditions in the legend
        con_label = ttk.Label(legend_boxes, text="CON", anchor=tk.W)
        con_label.pack(side=tk.LEFT, fill=tk.X, anchor=tk.W)
        self.plot_legend_con_var = tk.StringVar(value=init_legend_settings[2].strip())
        self.plot_legend_con_box = tk.Checkbutton(legend_boxes, var=self.plot_legend_con_var,
                                              onvalue="True", offvalue="", background=BG,
                                              anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                              )
        self.plot_legend_con_box.pack(side=tk.LEFT, anchor=tk.W)
        legend_boxes.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Title
        self.plot_title_label = ttk.Label(self.plotting_left_column, text="Add title", anchor=tk.W)
        self.plot_title_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_title_var = tk.StringVar(value="True")
        self.plot_title_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_title_var,
                                             onvalue="True", offvalue="", background=BG,
                                             anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                             )
        self.plot_title_box.pack(side=tk.TOP, anchor=tk.W)
        #Pack plotting setting
        self.plotting_left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.plotting_right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.plotting_two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Choose color style for plotting
        self.select_colormap = tk.StringVar()
        self.select_colormap.set("Default colormap")
        # Some colormaps suitable for plotting
        options = ['Default colormap', 'Default colormap', 'jet', 'brg', 'viridis', 'plasma', 'inferno', 'magma', 'cividis', 'spring',
                   'summer', 'autumn', 'winter', 'cool', 'Wistia', 'copper', 'twilight', 'twilight_shifted',
                   'hsv', 'gnuplot', 'gist_rainbow', 'rainbow']
        self.opmenu_colormap = ttk.OptionMenu(self, self.select_colormap, *options)
        self.opmenu_colormap.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)

    def _make_settings_subframe(self):
        # Settings name label
        self.settings_label = ttk.Label(self, text="Settings", anchor=tk.W)
        self.settings_label.pack(side=tk.TOP, fill=tk.X)
        # Initializing two-columns section
        self.settings_two_columns = ttk.Frame(self)
        self.settings_left_column = ttk.Frame(self.settings_two_columns)
        self.settings_right_column = ttk.Frame(self.settings_two_columns)
        # Photon energy
        self.pe_label = ttk.Label(self.settings_left_column, text="Photon Energy (eV)", anchor=tk.W)
        self.pe_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        # Read photon energy from init file if available
        val = service.get_service_parameter("PHOTON_ENERGY").split(';')[0]
        self.photon_energy = tk.StringVar(self, value=val)
        self.pe_entry = ttk.Entry(self.settings_right_column, textvariable=self.photon_energy, width=20)
        self.pe_entry.pack(side=tk.TOP, anchor=tk.W, expand=False)
        # Energy shift
        val = service.get_service_parameter("ENERGY_SHIFT").split(';')[0]
        self.eshift_label = ttk.Label(self.settings_left_column, text="Energy Shift(s) (eV)", anchor=tk.W)
        self.eshift_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.energy_shift = tk.StringVar(self, value=val)
        self.eshift_entry = ttk.Entry(self.settings_right_column, textvariable=self.energy_shift, width=20)
        self.eshift_entry.pack(side=tk.TOP, anchor=tk.W, expand=False)
        # Normalize by sweeps
        self.normalize_sweeps_label = ttk.Label(self.settings_left_column, text="Normalize by sweeps", anchor=tk.W)
        self.normalize_sweeps_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        normalize_frame = ttk.Frame(self.settings_right_column)
        self.normalize_sweeps_var = tk.StringVar(value="True")
        self.normalize_sweeps_box = tk.Checkbutton(normalize_frame, var=self.normalize_sweeps_var,
                                                   onvalue="True", offvalue="", background=BG,
                                                   anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                   command=self._toggle_normalize_sweeps
                                                   )
        self.normalize_sweeps_box.pack(side=tk.LEFT, anchor=tk.W)
        self.normalize_dwell_label = ttk.Label(normalize_frame, text="by dwell time", anchor=tk.W)
        self.normalize_dwell_label.pack(side=tk.LEFT, expand=False)
        self.normalize_dwell_var = tk.StringVar(value="True")
        self.normalize_dwell_box = tk.Checkbutton(normalize_frame, var=self.normalize_dwell_var,
                                                   onvalue="True", offvalue="", background=BG,
                                                   anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                   command=self._toggle_normalize_dwell
                                                   )
        self.normalize_dwell_box.pack(side=tk.LEFT, anchor=tk.W)
        normalize_frame.pack(side=tk.TOP, expand=False, anchor=tk.W)
        # Normalize by a constant
        self.const_norm_label = ttk.Label(self.settings_left_column, text="Normalize by const(s)", anchor=tk.W)
        self.const_norm_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        norm_entrie_frame = ttk.Frame(self.settings_right_column)
        self.do_const_norm_var = tk.StringVar(value="")
        self.do_const_norm_box = tk.Checkbutton(norm_entrie_frame, var=self.do_const_norm_var,
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                command=self._toggle_const_norm
                                                )
        self.do_const_norm_box.pack(side=tk.LEFT, anchor=tk.W)
        self.const_norm_var = tk.StringVar(self, value="")
        self.const_norm_entry = ttk.Entry(norm_entrie_frame, textvariable=self.const_norm_var, width=17)
        self.const_norm_entry.pack(side=tk.LEFT, expand=False)
        norm_entrie_frame.pack(side=tk.TOP, expand=False, anchor=tk.W)
        # Crop
        self.crop_label = ttk.Label(self.settings_left_column, text="Crop from:to (eV)", anchor=tk.W)
        self.crop_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        crop_entries_frame = ttk.Frame(self.settings_right_column)
        self.do_crop_var = tk.StringVar(value="")
        self.do_crop_box = tk.Checkbutton(crop_entries_frame, var=self.do_crop_var,
                                          onvalue="True", offvalue="", background=BG,
                                          anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                          command=self._toggle_crop
                                          )
        self.do_crop_box.pack(side=tk.LEFT, anchor=tk.W)
        self.crop_left_var = tk.StringVar(self, value="")
        self.crop_right_var = tk.StringVar(self, value="")
        self.crop_left_entry = ttk.Entry(crop_entries_frame, textvariable=self.crop_left_var, width=8)
        self.crop_left_entry.pack(side=tk.LEFT, expand=False)
        self.crop_right_entry = ttk.Entry(crop_entries_frame, textvariable=self.crop_right_var, width=8)
        self.crop_right_entry.pack(side=tk.RIGHT, expand=False)
        crop_entries_frame.pack(side=tk.TOP, expand=False, anchor=tk.W)
        # Subtract constant background
        self.subtract_const_label = ttk.Label(self.settings_left_column, text="Subtract constant bg", anchor=tk.W)
        self.subtract_const_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.subtract_const_var = tk.StringVar(value="")
        self.subtract_const_box = tk.Checkbutton(self.settings_right_column, var=self.subtract_const_var,
                                                 onvalue="True", offvalue="", background=BG,
                                                 anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                 command=self._toggle_subtract_bg
                                                 )
        self.subtract_const_box.pack(side=tk.TOP, anchor=tk.W)
        # Subtract Shirley background
        self.subtract_shirley_label = ttk.Label(self.settings_left_column, text="Subtract Shirley bg", anchor=tk.W)
        self.subtract_shirley_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.subtract_shirley_var = tk.StringVar(value="")
        self.subtract_shirley_box = tk.Checkbutton(self.settings_right_column, var=self.subtract_shirley_var,
                                                   onvalue="True", offvalue="", background=BG,
                                                   anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                   command=self._toggle_shirley
                                                   )
        self.subtract_shirley_box.pack(side=tk.TOP, anchor=tk.W)
        # Pack two-columns section
        self.settings_left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.settings_right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.settings_two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)

    def _plot(self):
        self.regions_in_work = self._get_regions_in_work()
        if not self.regions_in_work:
            return
        legend_options = ";".join([self.plot_legend_fn_var.get(), self.plot_legend_rn_var.get(), self.plot_legend_con_var.get()])
        service.set_init_parameters("LEGEND", legend_options)
        offset = (self.offset_slider.get() / 100) * max([np.max(region.get_data(column='final'))
                                                         for region in self.regions_in_work if
                                                         len(region.get_data(column='final')) > 0])
        cmap = None if self.select_colormap.get() == "Default colormap" else self.select_colormap.get()
        legend_features = self._get_legend_features()

        plot_add_dim = bool(self.plot_add_dim_var.get())
        plot_2D = bool(self.plot_2D_var.get())
        plot_scatter = bool(self.scatter_var.get())
        if plot_scatter and plot_2D and plot_add_dim and len(self.regions_in_work) == 1:
            self.winfo_toplevel().display_message("Choose either 'scatter' or '2D plot' mode.")
            return
        elif plot_scatter and plot_2D and (not plot_add_dim or len(self.regions_in_work) > 1):
            plot_2D = False
        elif plot_add_dim and plot_2D and len(self.regions_in_work) > 1:
            self.winfo_toplevel().display_message("Can't make 2D plot for more than 1 scan at the same time.")
            plot_2D = False
        elif not plot_add_dim:
            plot_2D = False
        if bool(self.plot_separate_var.get()):
            new_plot_window = tk.Toplevel(self.winfo_toplevel())
            new_plot_window.wm_title("Raw data")
            new_plot_panel = PlotPanel(new_plot_window, label=None, borderwidth=1, relief="groove")
            new_plot_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            new_plot_panel.plot_regions(self.regions_in_work,
                                        add_dimension=plot_add_dim,
                                        scatter=plot_scatter,
                                        plot2D=plot_2D,
                                        legend=bool(self.plot_legend_var.get()),
                                        legend_features=tuple(legend_features),
                                        title=bool(self.plot_title_var.get()),
                                        y_offset=offset, colormap=cmap,
                                        font_size=int(service.get_service_parameter("FONT_SIZE")))
        else:
            self.winfo_toplevel().gui_widgets["PlotPanel"].clear_figure()
            self.winfo_toplevel().gui_widgets["PlotPanel"].plot_regions(self.regions_in_work,
                                                                        add_dimension=plot_add_dim,
                                                                        scatter=plot_scatter,
                                                                        plot2D=plot_2D,
                                                                        legend=bool(self.plot_legend_var.get()),
                                                                        legend_features=tuple(legend_features),
                                                                        title=bool(self.plot_title_var.get()),
                                                                        y_offset=offset, colormap=cmap,
                                                                        font_size=int(service.get_service_parameter("FONT_SIZE")))

    def _save(self):
        if self.regions_in_work:
            output_dir = filedialog.askdirectory(title="Choose directory for saving",
                                                 initialdir=service.get_service_parameter("DEFAULT_OUTPUT_FOLDER"))
            if output_dir:
                service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)
                for region in self.regions_in_work:
                    name_dat = output_dir + "/" + region.get_info("File Name") + ".dat"
                    name_sqr = output_dir + "/" + region.get_info("File Name") + ".sqr"
                    save_add_dimension = bool(self.plot_add_dim_var.get())
                    try:
                        with open(name_dat, 'w') as f:
                            region.save_xy(f, add_dimension=save_add_dimension, headers=False)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {name_dat}", exc_info=True)
                        self.winfo_toplevel().display_message(f"Couldn't save file {name_dat}")
                    try:
                        with open(name_sqr, 'w') as f:
                            region.save_as_file(f, details=True, add_dimension=save_add_dimension, headers=True)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {name_sqr}", exc_info=True)
                        self.winfo_toplevel().display_message(f"Couldn't save file {name_sqr}")

    def _saveas(self):
        if self.regions_in_work:
            output_dir = service.get_service_parameter("DEFAULT_OUTPUT_FOLDER")
            for region in self.regions_in_work:
                dat_file_path = filedialog.asksaveasfilename(initialdir=output_dir,
                                                             initialfile=region.get_info("File Name") + ".dat",
                                                             title="Save as...",
                                                             filetypes=(("dat files", "*.dat"), ("all files", "*.*")))
                if dat_file_path:
                    save_add_dimension = bool(self.plot_add_dim_var.get())
                    try:
                        with open(dat_file_path, 'w') as f:
                            region.save_xy(f, add_dimension=save_add_dimension, headers=False)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {dat_file_path}", exc_info=True)
                        self.winfo_toplevel().display_message(f"Couldn't save file {dat_file_path}")
                    sqr_file_path = dat_file_path.rpartition('.')[0] + '.sqr'
                    try:
                        with open(sqr_file_path, 'w') as f:
                            region.save_as_file(f, details=True, add_dimension=save_add_dimension, headers=True)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {sqr_file_path}", exc_info=True)
                        self.winfo_toplevel().display_message(f"Couldn't save file {sqr_file_path}")

                output_dir = os.path.dirname(dat_file_path)
            service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)

    def _show_info(self):
        if self.regions_in_work:
            info_message = ""
            for i, region in enumerate(self.regions_in_work):
                if i > 0:
                    info_message += "-" * 10 + "\n"
                info_message += f"{region.get_id()}\n\n"
                info_message += "Info:\n" + region.get_info_string() + "\n"
                info_message += f"Add-dimension mode: {region.is_add_dimension()}\n"
                if region.is_add_dimension():
                    info_message += f"Add-dimension scans number : {region.get_add_dimension_counter()}"
                info_message += "\n\n"
                info_message += "Conditions:\n" + region.get_conditions(as_string=True) + "\n\n"
                info_message += "Corrections:\n"
                corrections_entries = [cor.strip() + '\n' for cor in region.get_corrections(as_string=True).split(';')]
                for cor_entry in corrections_entries:
                    info_message += cor_entry
            text_view = tk.Toplevel(self)
            text_view.wm_title("Regions info")
            output_panel = ttk.Frame(text_view, borderwidth=1, relief="groove")
            info_panel = BrowserTreeView(output_panel, label=None, borderwidth=1, relief="groove")
            msg = tk.Message(info_panel.treeview, text=info_message, anchor=tk.W, bg=BG)
            msg.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
            info_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            output_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _toggle_const_norm(self):
        if not bool(self.do_const_norm_var.get()):
            service.set_init_parameters("NORMALIZE_BY_CONSTANT", "")
        else:
            service.set_init_parameters("NORMALIZE_BY_CONSTANT", "True")
        if self.const_norm_var.get():
            return
        nc = service.get_service_parameter("NORMALIZATION_CONSTANT").split(';')[0]
        if nc:
            self.const_norm_var.set(nc)

    def _toggle_crop(self):
        if not bool(self.do_crop_var.get()):
            service.set_init_parameters("DO_CROP", "")
        else:
            service.set_init_parameters("DO_CROP", "True")
        if self.crop_left_var.get() or self.crop_right_var.get():
            return
        if service.get_service_parameter("CROP"):
            crop_vals = service.get_service_parameter("CROP").split(';')
            self.crop_left_var.set(crop_vals[0])
            self.crop_right_var.set(crop_vals[1])

    def _toggle_energy_axis(self, mode):
        assert mode in ('kinetic', 'binding')
        if self.plot_binding_var.get() and mode == 'binding':
            self.plot_kinetic_var.set("")
        elif self.plot_kinetic_var.get() and mode == 'kinetic':
            self.plot_binding_var.set("")

    def _toggle_legend_settings(self):
        legend_sub_widgets = (
            self.plot_legend_fn_var,
            self.plot_legend_rn_var,
            self.plot_legend_con_var,
            self.plot_legend_fn_box,
            self.plot_legend_rn_box,
            self.plot_legend_con_box
        )
        if not bool(self.plot_legend_var.get()):
            legend_sub_widgets_values = [w.get() for w in legend_sub_widgets[0:3]]
            service.set_init_parameters("LEGEND", ";".join(legend_sub_widgets_values))
            for obj in legend_sub_widgets[0:3]:
                obj.set("")
            for obj in legend_sub_widgets[3:]:
                obj.config(state=tk.DISABLED)
        else:
            legend_sub_widgets_values = service.get_service_parameter("LEGEND").split(";")
            for i, obj in enumerate(legend_sub_widgets[0:3]):
                obj.set(legend_sub_widgets_values[i].strip())
            for obj in legend_sub_widgets[3:]:
                    obj.config(state=tk.NORMAL)

    def _toggle_normalize_sweeps(self):
        if not bool(self.normalize_sweeps_var.get()):
            service.set_init_parameters("NORMALIZE_SWEEPS", "")
        else:
            service.set_init_parameters("NORMALIZE_SWEEPS", "True")

    def _toggle_normalize_dwell(self):
        if not bool(self.normalize_dwell_var.get()):
            service.set_init_parameters("NORMALIZE_DWELL", "")
        else:
            service.set_init_parameters("NORMALIZE_DWELL", "True")

    def _toggle_subtract_bg(self):
        if not bool(self.subtract_const_var.get()):
            service.set_init_parameters("SUBTRACT_CONSTANT", "")
        else:
            service.set_init_parameters("SUBTRACT_CONSTANT", "True")

    def _toggle_settings(self):
        if self.plot_use_settings_var.get():
            self.photon_energy.set(service.get_service_parameter("PHOTON_ENERGY"))
            self.energy_shift.set(service.get_service_parameter("ENERGY_SHIFT"))
            if bool(service.get_service_parameter("NORMALIZE_BY_CONSTANT")):
                self.do_const_norm_var.set("True")
                norm_const = service.get_service_parameter("NORMALIZATION_CONSTANT")
                self.const_norm_var.set(norm_const)
            else:
                self.do_const_norm_var.set("")
            if bool(service.get_service_parameter("NORMALIZE_SWEEPS")):
                self.normalize_sweeps_var.set("True")
            else:
                self.normalize_sweeps_var.set("")
            if bool(service.get_service_parameter("NORMALIZE_DWELL")):
                self.normalize_dwell_var.set("True")
            else:
                self.normalize_dwell_var.set("")
            if bool(service.get_service_parameter("SUBTRACT_CONSTANT")):
                self.subtract_const_var.set("True")
            else:
                self.subtract_const_var.set("")
            self.plot_binding_var.set("True")
            if bool(service.get_service_parameter("SUBTRACT_SHIRLEY")):
                self.subtract_shirley_var.set("True")
            else:
                self.subtract_shirley_var.set("")
            if bool(service.get_service_parameter("DO_CROP")):
                self.do_crop_var.set("True")
                try:
                    crop_vals = service.get_service_parameter("CROP").split(';')
                except (IndexError, IOError):
                    crop_vals = ['', '']
                if bool(crop_vals[0]) and bool(crop_vals[1]):
                    self.do_crop_var.set("True")
                else:
                    self.do_crop_var.set("")
                self.crop_left_var.set(crop_vals[0])
                self.crop_right_var.set(crop_vals[1])
            else:
                self.do_crop_var.set("")
            for obj in (self.subtract_const_box,
                        self.subtract_shirley_box,
                        self.do_const_norm_box,
                        self.const_norm_entry,
                        self.do_crop_box,
                        self.crop_left_entry,
                        self.crop_right_entry,
                        self.normalize_sweeps_box,
                        self.normalize_dwell_box,
                        self.plot_binding_box,
                        self.plot_kinetic_box,
                        self.pe_entry,
                        self.eshift_entry):
                obj.config(state=tk.NORMAL)
        else:
            # Setting vars to ""
            for obj in (self.subtract_const_var,
                        self.subtract_shirley_var,
                        self.do_crop_var,
                        self.crop_left_var,
                        self.crop_right_var,
                        self.do_const_norm_var,
                        self.const_norm_var,
                        self.normalize_sweeps_var,
                        self.normalize_dwell_var,
                        self.plot_binding_var,
                        self.plot_kinetic_var,
                        self.photon_energy,
                        self.energy_shift
                        ):
                obj.set("")
            # Setting boxes and entries to DISABLED
            for obj in (self.subtract_const_box,
                        self.subtract_shirley_box,
                        self.do_const_norm_box,
                        self.const_norm_entry,
                        self.do_crop_box,
                        self.crop_left_entry,
                        self.crop_right_entry,
                        self.normalize_sweeps_box,
                        self.normalize_dwell_box,
                        self.plot_binding_box,
                        self.plot_kinetic_box,
                        self.pe_entry,
                        self.eshift_entry
                        ):
                obj.config(state=tk.DISABLED)

    def _toggle_shirley(self):
        if not bool(self.subtract_shirley_var.get()):
            service.set_init_parameters("SUBTRACT_SHIRLEY", "")
        else:
            service.set_init_parameters("SUBTRACT_SHIRLEY", "True")


class PeakLine(ttk.Frame):
    def __init__(self, parent, fit_type, remove_func, add_func, id_, data_max=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._id = id_
        self.fit_type = fit_type
        self.parameter_vals = {}
        self.parameter_bounds = {}
        self.parameter_fix_vals = {}
        self.parameter_fix_boxes = {}
        self.data_max = data_max

        title_frame = ttk.Frame(self)
        self.remove_peak_button = ttk.Button(title_frame, text='-', command=lambda: remove_func(self._id), width=1)
        self.remove_peak_button.pack(side=tk.RIGHT, expand=False)
        self.add_peak_button = ttk.Button(title_frame, text='+', command=lambda: add_func(), width=1)
        self.add_peak_button.pack(side=tk.RIGHT, expand=False)
        # Choose peak color
        self.peak_color = tk.StringVar()
        self.peak_color.set("Default color")
        # Some colormaps suitable for plotting
        options = ['Default color'] + COLORS
        self.opmenu_color = ttk.OptionMenu(title_frame, self.peak_color, self.peak_color.get(), *options)
        self.opmenu_color.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.id_var = tk.StringVar(value=f"Peak {id_}:")
        self.use_peak_var = tk.StringVar(value="True")
        use_peak_box = tk.Checkbutton(title_frame, var=self.use_peak_var,
                                      onvalue="True", offvalue="", background=BG,
                                      anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                      )
        use_peak_box.pack(side=tk.LEFT, anchor=tk.W)
        self.peak_label = ttk.Label(title_frame, textvariable=self.id_var, anchor=tk.W)
        self.peak_label.pack(side=tk.LEFT, expand=False)
        title_frame.pack(side=tk.TOP, fill=tk.X, expand=False)
        self._add_parameter_fields(fit_type)

    def _add_parameter_fields(self, fittype):
        two_columns = ttk.Frame(self)
        left_column = ttk.Frame(two_columns)
        right_column = ttk.Frame(two_columns)
        # Loop goes over the list of parameters of the current fit type
        for par_name in fitter.Peak.peak_types[fittype]:
            name_label = ttk.Label(left_column, text=f"{par_name} / bounds", anchor=tk.E)
            name_label.pack(side=tk.TOP, expand=True)
            parameter_entry_frame = ttk.Frame(right_column)
            if par_name == 'amplitude' and self.data_max is not None:
                _val = str(round(self.data_max, int(service.service_vars['ROUND_PRECISION'])))
                _val_bounds = '; '.join(['0', _val])
            elif par_name == 'l_fwhm':
                _val = '0.5'
                _val_bounds = "0; 2"
            elif par_name == 'g_fwhm':
                _val = '0.5'
                _val_bounds = "0; 2"
            elif par_name == 'fwhm':
                _val = '0.5'
                _val_bounds = "0; 2"
            else:
                _val = ''
                _val_bounds = ';'
            self.parameter_vals[par_name] = tk.StringVar(self, value=_val)
            parameter_entry = ttk.Entry(parameter_entry_frame, textvariable=self.parameter_vals[par_name], width=8)
            parameter_entry.pack(side=tk.LEFT, expand=False)
            slash_label = ttk.Label(parameter_entry_frame, text="/")
            slash_label.pack(side=tk.LEFT, expand=False)
            self.parameter_bounds[par_name] = tk.StringVar(self, value=_val_bounds)
            parameter_bounds_entry = ttk.Entry(parameter_entry_frame, textvariable=self.parameter_bounds[par_name], width=8)
            parameter_bounds_entry.pack(side=tk.LEFT, expand=False)
            fix_label = ttk.Label(parameter_entry_frame, text="Fix", anchor=tk.W)
            fix_label.pack(side=tk.LEFT, expand=False)
            self.parameter_fix_vals[par_name] = tk.StringVar(value="")
            self.parameter_fix_boxes[par_name] = tk.Checkbutton(parameter_entry_frame,
                                                                var=self.parameter_fix_vals[par_name],
                                                                onvalue="True", offvalue="", background=BG,
                                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                                )
            self.parameter_fix_boxes[par_name].pack(side=tk.LEFT, anchor=tk.W, expand=False)
            parameter_entry_frame.pack(side=tk.TOP, fill=tk.X, expand=True)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)

    def get_id(self):
        return self._id

    def get_parameter(self, par_name: str, string_output=False):
        """Returns parameter str value, bounds and whether or not to fix it for the specified parameter
        :param par_name: str
        :param string_output: True if type string output required
        :return: (float, list of floats, bool) or (str, str, str) if string_output=True
        """
        if par_name in self.parameter_vals.keys():
            if string_output:
                return (self.parameter_vals[par_name].get(),
                        self.parameter_bounds[par_name].get(),
                        self.parameter_fix_vals[par_name].get())
            else:
                try:
                    if self.parameter_vals[par_name].get():
                        val = round(float(self.parameter_vals[par_name].get()), int(service.service_vars['ROUND_PRECISION']))
                    else:
                        val = None
                    if self.parameter_bounds[par_name].get():
                        bounds = [round(float(s.strip()), int(service.service_vars['ROUND_PRECISION']))
                                  for s in re.findall(r"[+-]? *(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
                                                      self.parameter_bounds[par_name].get())]
                        if len(bounds) != 2:
                            #gui_logger.warning(f"Check parameters bounds entries for Peak {self._id}. Must be two numbers.")
                            bounds = [None, None]
                    else:
                        bounds = [None, None]
                    if self.parameter_fix_vals[par_name].get():
                        fix_choise = True
                    else:
                        fix_choise = False
                    return val, bounds, fix_choise
                except ValueError:
                    gui_logger.warning(f"Check parameter entries for Peak {self._id}. Must be numbers.")
                    self.winfo_toplevel().display_message(f"Check parameter entries for Peak {self._id}. Must be numbers.")
                    return None

    def get_all_parameters(self, string_output=False):
        """Returns parameter names, values, bounds and whether to fix them for all parameters
        :return: (list of str,
                  list of floats,
                  list of lists (of two floats),
                  list of bools)
                  or
                  (list of str,
                  list of str,
                  list of str,
                  list of str) if string_output == True
        """
        if string_output:
            vals = [self.parameter_vals[key].get() for key in self.parameter_vals.keys()]
            bounds = [self.parameter_bounds[key].get() for key in self.parameter_bounds.keys()]
            fix_choises = [self.parameter_fix_vals[key].get() for key in self.parameter_fix_vals.keys()]
            return self.parameter_vals.keys(), vals, bounds, fix_choises
        else:
            vals, bounds, fix_choises = [], [], []
            for key in self.parameter_vals.keys():
                par = self.get_parameter(key, string_output=False)
                if par is None:
                    vals.append(None)
                    bounds.append([None, None])
                    fix_choises.append(False)
                else:
                    vals.append(par[0])
                    bounds.append(par[1])
                    fix_choises.append(par[2])
        return self.parameter_vals.keys(), vals, bounds, fix_choises

    def set_id(self, new_id):
        self._id = new_id
        self.id_var.set(f"Peak {new_id}:")

    def set_parameter(self, par_name, par_value, par_bounds, par_fix):
        """Sets parameter value and bounds for the specified parameter
        :param par_name: str
        :param par_value: float or str representing a float
        :param par_bounds: list of two floats or string representing two floats separated with ';'
        :param par_fix: bool or str representing a bool
        """
        assert par_fix in ('True', 'False', '', True, False, 0, 1)
        if type(par_value) is str and type(par_bounds) is str:
            if par_name in self.parameter_vals.keys():
                self.parameter_vals[par_name].set(par_value)
                self.parameter_bounds[par_name].set(par_bounds)
                if par_fix in ('False', '', False):
                    self.parameter_fix_vals[par_name].set('')
                else:
                    self.parameter_fix_vals[par_name].set('True')
                return True
        else:
            assert len(par_bounds) == 2
            if par_name in self.parameter_vals.keys():
                self.parameter_vals[par_name].set(round(par_value, int(service.service_vars['ROUND_PRECISION'])))
                self.parameter_bounds[par_name].set(f"{round(par_bounds[0], int(service.service_vars['ROUND_PRECISION']))};"
                                                    f"{round(par_bounds[1], int(service.service_vars['ROUND_PRECISION']))}")
                self.parameter_fix_vals[par_name].set(bool(par_fix))
                return True

    def set_all_parameters(self, par_names: list, par_values: list, par_bounds: list, par_fixes: list):
        """Sets parameter values and bounds for all parameters
        :param par_names: list of str
        :param par_values: list of str or list of floats
        :param par_bounds: list of str or list of lists (of two floats)
        :param par_fixes: list of str or list of bools
        """
        assert len(par_values) == len(par_bounds) == len(par_names) == len(par_fixes)
        for i, pn in enumerate(par_names):
            self.set_parameter(pn, par_values[i], par_bounds[i], par_fixes[i])


class FitWindow(tk.Toplevel):
    def __init__(self, parent, region, fit_type, plot_options, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.wm_title(f"Fitting {fit_type} to {region.get_id()}")
        self.fittype = fit_type
        self.plot_options = plot_options
        self.region = region
        self.peak_lines = {}
        self.peaks = {}
        self.fitter_obj = None
        self.results_txt = None

        toppanel = ttk.Frame(self, borderwidth=1, relief="groove")
        # Right panel for plotting
        self.plot_panel = PlotPanel(toppanel, label=None, borderwidth=1, relief="groove")
        self.plot_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        # Left panel for fitting settings
        self.fit_settings_panel = ttk.Frame(toppanel, borderwidth=1, relief="groove")
        self.settings = ttk.Frame(self.fit_settings_panel, borderwidth=1, relief="groove")
        # Choose spectrum color
        spectrum_color_frame = ttk.Frame(self.settings)
        spectrum_color_label = ttk.Label(spectrum_color_frame, text="Spectrum color", anchor=tk.W)
        spectrum_color_label.pack(side=tk.LEFT, expand=False)
        self.spectrum_color = tk.StringVar()
        self.spectrum_color.set("Default color")
        # Some colormaps suitable for plotting
        options = ['Default color'] + COLORS
        self.opmenu_spectrum_color = ttk.OptionMenu(spectrum_color_frame, self.spectrum_color,
                                                    self.spectrum_color.get(), *options)
        self.opmenu_spectrum_color.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        spectrum_color_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        if fit_type == 'Error Func':
            self.settings.pack(side=tk.TOP, fill=tk.X, expand=False)
            self.fit_panel = ttk.Frame(self.fit_settings_panel, borderwidth=1, relief="groove")
            self._add_error_func_section()
            self.fit_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.fit_settings_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            toppanel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self._plot()
            return
        # Draw residuals and fit line
        residuals_frame = ttk.Frame(self.settings)
        residuals_label = ttk.Label(residuals_frame, text="Plot residuals", anchor=tk.W)
        residuals_label.pack(side=tk.LEFT, expand=False)
        self.plot_residuals_var = tk.StringVar(value="")
        self.plot_residuals_box = tk.Checkbutton(residuals_frame, var=self.plot_residuals_var,
                                                 onvalue="True", offvalue="", background=BG,
                                                 anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
        self.plot_residuals_box.pack(side=tk.LEFT, anchor=tk.W)
        fitline_label = ttk.Label(residuals_frame, text="Plot fit line", anchor=tk.W)
        fitline_label.pack(side=tk.LEFT, expand=False)
        self.plot_fitline_var = tk.StringVar(value="True")
        self.plot_fitline_box = tk.Checkbutton(residuals_frame, var=self.plot_fitline_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
        self.plot_fitline_box.pack(side=tk.LEFT, anchor=tk.W)
        residuals_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        self.settings.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.fit_panel = BrowserTreeView(self.fit_settings_panel, label=None, borderwidth=1, relief="groove")
        self.fit_tree = self.fit_panel.treeview
        self._add_peak_line()
        self.fit_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Action buttons
        self.buttons_panel = ttk.Frame(self.fit_settings_panel, borderwidth=1, relief="groove")
        replot_button = ttk.Button( self.buttons_panel, text='Replot', command=self._plot, width=8)
        replot_button.pack(side=tk.TOP, fill=tk.X)
        fit_button = ttk.Button(self.buttons_panel, text='Do Fit', command=self._do_fit_peaks)
        fit_button.pack(side=tk.TOP, fill=tk.X)
        save_button = ttk.Button(self.buttons_panel, text='Save Fit', command=self._save_peaks)
        save_button.pack(side=tk.TOP, fill=tk.X)
        close_window_button = ttk.Button(self.buttons_panel, text='Close Window', command=self.destroy)
        close_window_button.pack(side=tk.TOP, fill=tk.X)
        self.buttons_panel.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.fit_settings_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        toppanel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Bottom panel for output
        output_panel = ttk.Frame(self, borderwidth=1, relief="groove", height=50)
        fit_results_frame = BrowserTreeView(output_panel, label=None, borderwidth=1, relief="groove")
        self.fit_results_tree = fit_results_frame.treeview
        fit_results_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        output_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False)

        self._plot()

    def _add_error_func_section(self):
        def _make_parameter_line(parent_obj, par_name, value, input=True):
            if input:
                label = ttk.Label(parent_obj.input_left_column, text=par_name, anchor=tk.E)
                label.pack(side=tk.TOP, fill=tk.X, expand=True)
                parent_obj.error_func_pars_input.append(tk.StringVar(parent_obj, value=value))
                entry = ttk.Entry(parent_obj.input_right_column,
                                  textvariable=parent_obj.error_func_pars_input[-1],
                                  width=8)
            else:
                label = ttk.Label(parent_obj.output_left_column, text=par_name, anchor=tk.E)
                label.pack(side=tk.TOP, fill=tk.X, expand=True)
                parent_obj.error_func_pars_output.append(tk.StringVar(parent_obj, value=value))
                entry = ttk.Label(parent_obj.output_right_column,
                                  textvariable=parent_obj.error_func_pars_output[-1],
                                  width=25)
            entry.pack(side=tk.TOP, anchor=tk.W, expand=False)

        self.error_func_pars_input = []
        self.error_func_pars_output = []
        self.shift = tk.StringVar(self, value="")
        self.gauss_fwhm = tk.StringVar(self, value="")
        error_func_label = ttk.Label(self.fit_panel, text="Error function", anchor=tk.W)
        error_func_label.pack(side=tk.TOP, fill=tk.X, expand=False)
        blank_label = ttk.Label(self.fit_panel, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        parameters_label = ttk.Label(self.fit_panel, text="Parameters:", anchor=tk.W)
        parameters_label.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.input_two_columns = ttk.Frame(self.fit_panel)
        self.input_left_column = ttk.Frame(self.input_two_columns)
        self.input_right_column = ttk.Frame(self.input_two_columns)
        # Read default parameters from init.file
        try:
            par_str = service.get_service_parameter("FERMI_FIT_PARAMETERS")
            par_vals = [float(v) for v in par_str.split(';')]
        except (IndexError, TypeError, ValueError, IOError):
            par_vals = [1.00, 0.00, 0.10, 0.00]
        if len(par_vals) != 4:
            par_vals = [1.00, 0.00, 0.10, 0.00]
        for i, par_name in enumerate(("top", "center", "width", "bottom")):
            _make_parameter_line(self, par_name, par_vals[i])
        # Pack two-columns section
        self.input_left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.input_right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.input_two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)
        blank_label = ttk.Label(self.fit_panel, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        fit_button = ttk.Button(self.fit_panel, text='Do Fit', command=self._do_fit_error_func)
        fit_button.pack(side=tk.TOP, fill=tk.X)
        blank_label = ttk.Label(self.fit_panel, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        results_label = ttk.Label(self.fit_panel, text="Fit results:", anchor=tk.W)
        results_label.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.output_two_columns = ttk.Frame(self.fit_panel)
        self.output_left_column = ttk.Frame(self.output_two_columns)
        self.output_right_column = ttk.Frame(self.output_two_columns)
        for i, par_name in enumerate(("top", "center", "width", "bottom")):
            _make_parameter_line(self, par_name, par_vals[i], input=False)
        self.output_left_column.pack(side=tk.LEFT, fill=tk.X, expand=False)
        self.output_right_column.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.output_two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)
        blank_label = ttk.Label(self.fit_panel, text="", anchor=tk.W)
        blank_label.pack(side=tk.TOP, fill=tk.X)
        shift_label = ttk.Label(self.fit_panel, textvariable=self.shift, anchor=tk.W)
        shift_label.pack(side=tk.TOP, fill=tk.X)
        gauss_fwhm_label = ttk.Label(self.fit_panel, textvariable=self.gauss_fwhm, anchor=tk.W)
        gauss_fwhm_label.pack(side=tk.TOP, fill=tk.X)

    def _add_peak_line(self):
        peak_num = len(self.peak_lines.keys())
        self.peak_lines[peak_num] = PeakLine(self.fit_tree, self.fittype, self._remove_peak_line,
                                             self._add_peak_line, peak_num, data_max=np.max(self.region.get_data('final')))
        self.peak_lines[peak_num].pack(side=tk.TOP, fill=tk.X, expand=False)
        self._redraw_add_remove_buttons()
        if peak_num > 0:
            self.peak_lines[peak_num].set_all_parameters(*self.peak_lines[peak_num - 1].get_all_parameters(string_output=True))

    def _display_message(self, msg, timestamp=True):
        # Clearing the previously existing text
        for widget in self.fit_results_tree.winfo_children():
            widget.destroy()
        if timestamp:
            msg = f"{datetime.datetime.now().strftime('%H:%M:%S')} " + msg
        results_msg = tk.Message(self.fit_results_tree, width=self.winfo_toplevel().winfo_width(), text=msg, anchor=tk.W, bg=BG)
        results_msg.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

    def _do_fit_error_func(self):
        fit_parameters = [float(par_str_var.get()) for par_str_var in self.error_func_pars_input]
        fit_res = helpers.fit_fermi_edge(self.region, fit_parameters)
        fit_res_str = ""
        for i, fr in enumerate(fit_res[0]):
            self.error_func_pars_output[i].set(f"{round(fr, int(service.service_vars['ROUND_PRECISION']))} +/- "
                                               f"{round(fit_res[1][i], int(service.service_vars['ROUND_PRECISION']))}")
            if i == 0:
                fit_res_str += str(round(fr, int(service.service_vars['ROUND_PRECISION'])))
            else:
                fit_res_str = ';'.join([fit_res_str, str(round(fr, int(service.service_vars['ROUND_PRECISION'])))])
        service.set_init_parameters("FERMI_FIT_PARAMETERS", fit_res_str)
        shift = [fit_res[0][1], fit_res[1][1]]  # Energy shifts for Fermi edge
        self.shift.set(f"Energy shift: {round(shift[0], int(service.service_vars['ROUND_PRECISION']))} +/- "
                       f"{round(shift[1], int(service.service_vars['ROUND_PRECISION']))}")
        # a2 parameter of the complementary error function is related to the
        # sigma parameter of the gaussian that can be constructed to describe
        # the widening of ideal step function.
        # FWHM_gauss = 2*sqrt(ln2)*a2
        # FWHM_gauss = 2*sqrt(2ln2)*sigma
        gauss_fwhm = [2 * (np.log(2.0) ** (.5)) * np.absolute(fit_res[0][2]), fit_res[1][2]]
        self.gauss_fwhm.set(f"Gauss contribution: {round(gauss_fwhm[0], int(service.service_vars['ROUND_PRECISION']))} +/- "
                            f"{round(gauss_fwhm[1], int(service.service_vars['ROUND_PRECISION']))}")
        self._plot_error_func_fit(f"fit: {round(shift[0], int(service.service_vars['ROUND_PRECISION']))} +/- "
                                  f"{round(shift[1], int(service.service_vars['ROUND_PRECISION']))}")

    def _do_fit_peaks(self):
        # In this method we need to be extra cotious with the peak numbering because, if the user disables one or more peaks,
        # their actual numbers must be preserved but for the fitting routine they should be consequential.
        # 0, 1, 2, 3,... for fitting
        # 0, 2, 5, 7 (for example) for gui

        # Collecting parameter initial values, boundaries and eventual fix values, and peak colors
        initial_guess = []
        parameter_bounds, fix_parameters = {}, {}
        peak_colors = []
        for pn in fitter.Peak.peak_types[self.fittype]:
            parameter_bounds[pn] = {}
            fix_parameters[pn] = []
        # Here we need to dance withe the numbering described in the comment at the beginning of the method
        cnt = 0
        for i, (_, peak_line) in enumerate(self.peak_lines.items()):
            if not peak_line.use_peak_var.get():
                continue
            par_names, par_initial_vals, par_bounds, par_fixes = peak_line.get_all_parameters(string_output=False)
            initial_guess += par_initial_vals
            for j, par_name in enumerate(par_names):
                if par_fixes[j]:  # If the parameter is fixed, we ignore its boundaries
                    fix_parameters[par_name].append(cnt)
                    parameter_bounds[par_name][cnt] = [None, None]
                else:
                    parameter_bounds[par_name][cnt] = par_bounds[j]
            peak_colors.append(peak_line.peak_color.get())
            cnt += 1
        if None in initial_guess:
            gui_logger.warning("Please fill in initial values for all parameters. Bounds can stay empty.")
            self._display_message("Please fill in initial values for all parameters. Bounds can stay empty.")
            return False
        # Fitting
        self.fitter_obj = fitter.Fitter(self.region)
        if self.fittype == 'Gauss':  # Gauss
            self.fitter_obj.fit_gaussian(initial_guess, fix_parameters, boundaries=parameter_bounds)
        if self.fittype == 'Lorentz':  # Lorentz
            self.fitter_obj.fit_lorentzian(initial_guess, fix_parameters, boundaries=parameter_bounds)
        if self.fittype == 'Pseudo Voigt':  # Pseudo Voigt
            self.fitter_obj.fit_pseudo_voigt(initial_guess, fix_parameters, boundaries=parameter_bounds)
        if self.fittype == 'Doniach-Sunjic':  # Doniach-Sunjik
            self.fitter_obj.fit_doniach_sunjic(initial_guess, fix_parameters, boundaries=parameter_bounds)
        if self.spectrum_color.get() != "Default color":
            region_color = self.spectrum_color.get()
        else:
            region_color = None
        self.plot_panel.plot_fit(self.region, self.fitter_obj, region_color=region_color, colors=peak_colors,
                                 residuals=self.plot_residuals_var.get(), fitline=self.plot_fitline_var.get(),
                                 legend_feature=self.plot_options['legend_features'],
                                 title=self.plot_options['title'],
                                 font_size=int(service.get_service_parameter("FONT_SIZE")))

        # Showing results
        round_precision = int(service.get_service_parameter('ROUND_PRECISION'))
        self.results_txt = f"Goodness:\nChi^2 = {self.fitter_obj.get_chi_squared():.2f}\nRMS = {self.fitter_obj.get_rms():.2f}\n\n"
        # Here we also fix the numbering for the proper vizualization in GUI
        pls = list(self.peak_lines.values())
        cnt = 0
        for i, peak in enumerate(self.fitter_obj.get_peaks()):
            while not pls[cnt].use_peak_var.get():
                cnt += 1
            if peak:
                self.results_txt += f"Peak {cnt}\n"
                peak_area = round(peak.get_peak_area(), round_precision)
                self.results_txt = "  ".join([self.results_txt, f"Area {peak_area}\n"])
                peak_pars = [round(par, round_precision) for par in peak.get_parameters()]
                peak_errors = [round(err, round_precision) for err in peak.get_fitting_errors()]
                for i in range(len(peak_pars)):
                    par_names = fitter.Peak.peak_types[peak.get_peak_type()]
                    self.results_txt = "  ".join([self.results_txt, f"{par_names[i]}: {peak_pars[i]} +/- {peak_errors[i]}\n"])
                self.results_txt += '\n'
            cnt += 1
        # Clearing the previously existing text
        for widget in self.fit_results_tree.winfo_children():
            widget.destroy()
        results_msg = tk.Message(self.fit_results_tree, text=self.results_txt, anchor=tk.W, bg=BG)
        results_msg.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        return True

    def _get_peak_lines_ids(self):
        return [k for k, v in self.peak_lines.items() if v]

    def _make_fit_dataframe(self):
        if self.fitter_obj is not None:
            data_cols = {}
            x, fitline = self.fitter_obj.get_virtual_fitline()
            data_cols["energy"] = x
            data_cols["fitline"] = fitline
            for peak in self.fitter_obj.get_peaks():
                if peak:
                    _, data_cols[f"Peak{peak.get_peak_id()}"] = peak.get_virtual_data()
            return pd.DataFrame(data_cols)

    def _plot(self):
        if self.spectrum_color.get() != "Default color":
            region_color = self.spectrum_color.get()
        else:
            region_color = None
        self.plot_panel.plot_regions(self.region,
                                     color=region_color,
                                     title=self.plot_options['title'],
                                     legend=self.plot_options['legend'],
                                     legend_features=self.plot_options['legend_features'],
                                     scatter=self.plot_options['scatter'],
                                     font_size=int(service.get_service_parameter("FONT_SIZE")))
        if self.fitter_obj is not None:
            peak_colors = []
            for peak_line in self.peak_lines.values():
                if not peak_line.use_peak_var.get():
                    continue
                peak_colors.append(peak_line.peak_color.get())
            if self.spectrum_color.get() != "Default color":
                region_color = self.spectrum_color.get()
            else:
                region_color = None
            self.plot_panel.plot_fit(self.region, self.fitter_obj, region_color=region_color, colors=peak_colors,
                                     residuals=self.plot_residuals_var.get(), fitline=self.plot_fitline_var.get(),
                                     legend_feature=self.plot_options['legend_features'],
                                     title=self.plot_options['title'],
                                     font_size=int(service.get_service_parameter("FONT_SIZE")))

    def _plot_error_func_fit(self, fit_label):
        if self.spectrum_color.get() != "Default color":
            region_color = self.spectrum_color.get()
        else:
            region_color = None
        ax = self.plot_panel.figure_axes
        ax.clear()
        plotter.plot_region(self.region, ax, y_data="final", scatter=True, color=region_color,
                            title=False, legend_features=("ID", "Conditions"),
                            font_size=int(service.get_service_parameter("FONT_SIZE")))
        plotter.plot_region(self.region, ax, y_data="fitFermi", title=False, label=fit_label,
                            font_size=int(service.get_service_parameter("FONT_SIZE")))
        plotter.stylize_axes(ax)
        ax.set_aspect(float(service.get_service_parameter("PLOT_ASPECT_RATIO"))/ax.get_data_ratio())
        self.plot_panel.canvas.draw()
        self.plot_panel.toolbar.update()

    def _remove_peak_line(self, peak_id):
        self.peak_lines[peak_id].pack_forget()
        self.peak_lines[peak_id].destroy()
        self.peak_lines[peak_id] = None
        # If we remove a peak_line we need to renumber the remaining
        peak_line_copy = {}
        cnt = 0
        for val in self.peak_lines.values():
            if val:
                val.set_id(cnt)
                peak_line_copy[cnt] = val
                cnt += 1
        self.peak_lines = peak_line_copy
        self._redraw_add_remove_buttons()

    def _redraw_add_remove_buttons(self):
        line_ids = self._get_peak_lines_ids()
        if len(line_ids) == 1:
            self.peak_lines[line_ids[0]].remove_peak_button.config(state=tk.DISABLED)
            self.peak_lines[line_ids[0]].add_peak_button.config(state=tk.NORMAL)
        else:
            for i, line_id in enumerate(line_ids):
                if i < len(line_ids) - 1:
                    self.peak_lines[line_id].add_peak_button.config(state=tk.DISABLED)
                elif i == len(line_ids) - 1:
                    self.peak_lines[line_id].add_peak_button.config(state=tk.NORMAL)
                self.peak_lines[line_id].remove_peak_button.config(state=tk.NORMAL)

    def _save_peaks(self):
        if self.results_txt is not None:
            output_dir = service.get_service_parameter("DEFAULT_OUTPUT_FOLDER")
            dat_file_path = filedialog.asksaveasfilename(initialdir=output_dir,
                                                         initialfile=self.region.get_info("File Name") + ".fit",
                                                         title="Save as...",
                                                         filetypes=(("fit files", "*.fit"), ("all files", "*.*")))
            if dat_file_path:
                df = self._make_fit_dataframe()
                try:
                    with open(dat_file_path, 'w') as f:
                        f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Fitting {self.region.get_id()} with {len(self.peak_lines)} {self.fittype} peaks\n\n")
                        f.write(self.results_txt)
                        f.write("\n[Data]\n")
                        df.to_csv(f, header=True, index=False, sep='\t')
                except (IOError, OSError):
                    gui_logger.error(f"Couldn't save file {dat_file_path}", exc_info=True)
                    self.winfo_toplevel().display_message(f"Couldn't save file {dat_file_path}")

                output_dir = os.path.dirname(dat_file_path)
                service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)


class AdvancedPeakLine(ttk.Frame):
    def __init__(self, parent, fit_type, remove_func, add_func, toggle_func, id_, data_max=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._id = id_
        self.fit_type = fit_type
        self.parameter_vals = {}
        self.parameter_bounds = {}
        self.parameter_fix_vals = {}
        self.parameter_fix_boxes = {}
        self.parameter_dependence_type = {}
        self.parameter_dependence_base = {}
        self.dependence_types = ['Independent', 'Dependent *', 'Dependent +', 'Common']
        self.data_max = data_max

        title_frame = ttk.Frame(self)
        self.remove_peak_button = ttk.Button(title_frame, text='-', command=lambda: remove_func(self._id), width=1)
        self.remove_peak_button.pack(side=tk.RIGHT, expand=False)
        self.add_peak_button = ttk.Button(title_frame, text='+', command=lambda: add_func(), width=1)
        self.add_peak_button.pack(side=tk.RIGHT, expand=False)
        # Fill with color
        self.fill_color_var = tk.StringVar(value="True")
        fill_color_box = tk.Checkbutton(title_frame, var=self.fill_color_var,
                                        onvalue="True", offvalue="", background=BG,
                                        anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                        )
        fill_color_box.pack(side=tk.RIGHT, anchor=tk.W)
        fill_label = ttk.Label(title_frame, text=f"Fill", anchor=tk.W)
        fill_label.pack(side=tk.RIGHT, expand=False)
        # Choose peak color
        self.peak_color = tk.StringVar()
        self.peak_color.set("Default color")
        # Some colormaps suitable for plotting
        options = ['Default color'] + COLORS
        self.opmenu_color = ttk.OptionMenu(title_frame, self.peak_color, self.peak_color.get(), *options)
        self.opmenu_color.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        # Choose peak type
        self.peak_type = tk.StringVar(self, fit_type)
        options = list(fitter.Peak.peak_types.keys())
        self.typemenu = ttk.OptionMenu(title_frame, self.peak_type, self.peak_type.get(), *options,
                                       command=lambda x: toggle_func(self._id, self.peak_type.get()))
        self.typemenu.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.id_var = tk.StringVar(value=f"Peak {id_}:")
        self.use_peak_var = tk.StringVar(value="True")
        use_peak_box = tk.Checkbutton(title_frame, var=self.use_peak_var,
                                      onvalue="True", offvalue="", background=BG,
                                      anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                      )
        use_peak_box.pack(side=tk.LEFT, anchor=tk.W)
        self.peak_label = ttk.Label(title_frame, textvariable=self.id_var, anchor=tk.W)
        self.peak_label.pack(side=tk.LEFT, expand=False)
        title_frame.pack(side=tk.TOP, fill=tk.X, expand=False)
        self._add_parameter_fields(fit_type)

    def _add_parameter_fields(self, fittype):
        two_columns = ttk.Frame(self)
        left_column = ttk.Frame(two_columns)
        right_column = ttk.Frame(two_columns)
        # Loop goes over the list of parameters of the current fit type
        for par_name in fitter.Peak.peak_types[fittype]:
            name_label = ttk.Label(left_column, text=f"{par_name} / bounds", anchor=tk.E)
            name_label.pack(side=tk.TOP, expand=True)
            parameter_entry_frame = ttk.Frame(right_column)
            if par_name == 'amplitude' and self.data_max is not None:
                _val = str(round(self.data_max, int(service.service_vars['ROUND_PRECISION'])))
                _val_bounds = '; '.join(['0', _val])
            elif par_name == 'l_fwhm':
                _val = '0.5'
                _val_bounds = "0; 2"
            elif par_name == 'g_fwhm':
                _val = '0.5'
                _val_bounds = "0; 2"
            elif par_name == 'fwhm':
                _val = '0.5'
                _val_bounds = "0; 2"
            else:
                _val = ''
                _val_bounds = ';'
            self.parameter_vals[par_name] = tk.StringVar(self, value=_val)
            parameter_entry = ttk.Entry(parameter_entry_frame, textvariable=self.parameter_vals[par_name], width=8)
            parameter_entry.pack(side=tk.LEFT, expand=False)
            slash_label = ttk.Label(parameter_entry_frame, text="/")
            slash_label.pack(side=tk.LEFT, expand=False)
            self.parameter_bounds[par_name] = tk.StringVar(self, value=_val_bounds)
            parameter_bounds_entry = ttk.Entry(parameter_entry_frame, textvariable=self.parameter_bounds[par_name],
                                               width=8)
            parameter_bounds_entry.pack(side=tk.LEFT, expand=False)
            fix_label = ttk.Label(parameter_entry_frame, text="Fix", anchor=tk.W)
            fix_label.pack(side=tk.LEFT, expand=False)
            self.parameter_fix_vals[par_name] = tk.StringVar(value="")
            self.parameter_fix_boxes[par_name] = tk.Checkbutton(parameter_entry_frame,
                                                                var=self.parameter_fix_vals[par_name],
                                                                onvalue="True", offvalue="", background=BG,
                                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                                )
            self.parameter_fix_boxes[par_name].pack(side=tk.LEFT, anchor=tk.W, expand=False)
            # Dependent fit
            self.parameter_dependence_type[par_name] = tk.StringVar(self, value="Independent")
            options = self.dependence_types
            self.opmenu_dependence = ttk.OptionMenu(parameter_entry_frame, self.parameter_dependence_type[par_name],
                                                    self.parameter_dependence_type[par_name].get(), *options)
            self.opmenu_dependence.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.base_peak_label = ttk.Label(parameter_entry_frame, text="Base #", anchor=tk.W)
            self.base_peak_label.pack(side=tk.LEFT, expand=False)
            self.parameter_dependence_base[par_name] = tk.StringVar("")
            self.base_peak_entry = ttk.Entry(parameter_entry_frame,
                                             textvariable=self.parameter_dependence_base[par_name],
                                             width=2)
            self.base_peak_entry.pack(side=tk.LEFT, expand=False)
            parameter_entry_frame.pack(side=tk.TOP, fill=tk.X, expand=True)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)

    def get_id(self):
        return self._id

    def get_parameter(self, par_name: str, string_output=False):
        """Returns parameter str value, bounds and whether or not to fix it for the specified parameter
        :param par_name: str
        :param string_output: True if type string output required
        :return: (float, list of floats, bool, str, float) or (str, str, str, str, str) if string_output=True
        """
        if par_name in self.parameter_vals.keys():
            if string_output:
                return (self.parameter_vals[par_name].get(),
                        self.parameter_bounds[par_name].get(),
                        self.parameter_fix_vals[par_name].get(),
                        self.parameter_dependence_type[par_name].get(),
                        self.parameter_dependence_base[par_name].get())
            else:
                try:
                    if self.parameter_vals[par_name].get():
                        val = round(float(self.parameter_vals[par_name].get()), int(service.service_vars['ROUND_PRECISION']))
                    else:
                        val = None
                    if self.parameter_bounds[par_name].get():
                        bounds = [round(float(s.strip()), int(service.service_vars['ROUND_PRECISION']))
                                  for s in re.findall(r"[+-]? *(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
                                                      self.parameter_bounds[par_name].get())]
                        if len(bounds) != 2:
                            #gui_logger.warning(f"Check parameters bounds entries for Peak {self._id}. Must be two numbers.")
                            bounds = [None, None]
                    else:
                        bounds = [None, None]
                    if self.parameter_fix_vals[par_name].get():
                        fix_choise = True
                    else:
                        fix_choise = False
                    if self.parameter_dependence_base[par_name].get():
                        base = int(self.parameter_dependence_base[par_name].get())
                    else:
                        base = None
                    return val, bounds, fix_choise, self.parameter_dependence_type[par_name].get(), base
                except ValueError:
                    gui_logger.warning(f"Check parameter entries for Peak {self._id}. Must be numbers.")
                    self.winfo_toplevel()._display_message(f"Check parameter entries for Peak {self._id}. Must be numbers.")
                    return None

    def get_all_parameters(self, string_output=False):
        """Returns parameter names, values, bounds and whether to fix them for all parameters
        :return: (list of str,
                  list of floats,
                  list of lists (of two floats),
                  list of bools,
                  list of str,
                  list of int)
                  or
                  (list of str,
                  list of str,
                  list of str,
                  list of str,
                  list of str,
                  list of str) if string_output == True
        """
        if string_output:
            vals = [self.parameter_vals[key].get() for key in self.parameter_vals.keys()]
            bounds = [self.parameter_bounds[key].get() for key in self.parameter_bounds.keys()]
            fix_choises = [self.parameter_fix_vals[key].get() for key in self.parameter_fix_vals.keys()]
            dependence_types = [self.parameter_dependence_type[key].get() for key in self.parameter_dependence_type.keys()]
            dependence_bases = [self.parameter_dependence_base[key].get() for key in self.parameter_dependence_base.keys()]
            return self.parameter_vals.keys(), vals, bounds, fix_choises, dependence_types, dependence_bases
        else:
            vals, bounds, fix_choises, dependence_types, dependence_bases = [], [], [], [], []
            for key in self.parameter_vals.keys():
                par = self.get_parameter(key, string_output=False)
                if par is None:
                    vals.append(None)
                    bounds.append([None, None])
                    fix_choises.append(False)
                    dependence_types.append('Independent')
                    dependence_bases.append(None)
                else:
                    vals.append(par[0])
                    bounds.append(par[1])
                    fix_choises.append(par[2])
                    dependence_types.append(par[3])
                    dependence_bases.append(par[4])
        return list(self.parameter_vals.keys()), vals, bounds, fix_choises, dependence_types, dependence_bases

    def make_global_fit_dictionary(self):
        all_parameters = self.get_all_parameters(string_output=False)
        global_fit_dict = {}
        for i in range(len(all_parameters[0])):
            global_fit_dict[all_parameters[0][i]] = {}

            global_fit_dict[all_parameters[0][i]]['value'] = all_parameters[1][i]
            global_fit_dict[all_parameters[0][i]]['min'] = all_parameters[2][i][0]
            global_fit_dict[all_parameters[0][i]]['max'] = all_parameters[2][i][1]
            global_fit_dict[all_parameters[0][i]]['fix'] = all_parameters[3][i]
            global_fit_dict[all_parameters[0][i]]['dependencetype'] = all_parameters[4][i]
            if all_parameters[5][i] is not None:
                global_fit_dict[all_parameters[0][i]]['dependencebase'] = all_parameters[5][i]
            else:
                global_fit_dict[all_parameters[0][i]]['dependencebase'] = None

        return global_fit_dict

    def set_id(self, new_id):
        self._id = new_id
        self.id_var.set(f"Peak {new_id}:")

    def set_parameter(self, par_name, par_value, par_bounds, par_fix, par_dependence_type, par_dependence_base):
        """Sets parameter value and bounds for the specified parameter
        :param par_name: str
        :param par_value: float or str representing a float
        :param par_bounds: list of two floats or string representing two floats separated with ';'
        :param par_fix: bool or str representing a bool
        :param par_dependence_type: str representing the dependence type
        :param par_dependence_base: int or str representing an int
        """
        assert par_fix in ('True', 'False', '', True, False, 0, 1)
        assert par_dependence_type in self.dependence_types
        for obj in (par_value, par_bounds, par_dependence_base):
            if obj is None:
                obj = ''
        if type(par_value) is str and type(par_bounds) is str and type(par_dependence_base) is str:
            if par_name in self.parameter_vals.keys():
                self.parameter_vals[par_name].set(par_value)
                self.parameter_bounds[par_name].set(par_bounds)
                if par_fix in ('False', '', False):
                    self.parameter_fix_vals[par_name].set('')
                else:
                    self.parameter_fix_vals[par_name].set('True')
        else:
            assert len(par_bounds) == 2
            if par_name in self.parameter_vals.keys():
                if par_value:
                    self.parameter_vals[par_name].set(round(par_value, int(service.service_vars['ROUND_PRECISION'])))
                if par_bounds[0] and par_bounds[1]:
                    self.parameter_bounds[par_name].set(f"{round(par_bounds[0], int(service.service_vars['ROUND_PRECISION']))};"
                                                        f"{round(par_bounds[1], int(service.service_vars['ROUND_PRECISION']))}")
                self.parameter_fix_vals[par_name].set(bool(par_fix))

        self.parameter_dependence_base[par_name].set(par_dependence_base)
        self.parameter_dependence_type[par_name].set(par_dependence_type)
        return True

    def set_all_parameters(self, par_names: list, par_values: list, par_bounds: list, par_fixes: list,
                           par_dependence_types: list, par_dependence_bases: list):
        """Sets parameter values and bounds for all parameters
        :param par_names: list of str
        :param par_values: list of str or list of floats
        :param par_bounds: list of str or list of lists (of two floats)
        :param par_fixes: list of str or list of bools
        :param par_dependence_types: list of str
        :param par_dependence_bases: list of str or list of int
        """
        assert len(par_values) == len(par_bounds) == len(par_names) == len(par_fixes) == \
               len(par_dependence_types) == len(par_dependence_bases)
        for i, pn in enumerate(par_names):
            self.set_parameter(pn, par_values[i], par_bounds[i], par_fixes[i], par_dependence_types[i], par_dependence_bases[i])


class AdvancedFitWindow(tk.Toplevel):
    def __init__(self, parent, regions, plot_options, fittype, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.currently_plotted = None
        self.wm_title("Advanced fitting")
        self.plot_options = plot_options
        if helpers.is_iterable(regions):
            self.regions = regions
        else:
            self.regions = [regions]
        self.peak_lines = {}
        self.peaks = {}
        self.fitter_objs = None
        self.fittype = fittype
        self.results_txt = None

        toppanel = ttk.Frame(self, borderwidth=1, relief="groove")
        # Right panel for plotting
        self.plot_panel = PlotPanel(toppanel, label=None, borderwidth=1, relief="groove")
        self.plot_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.plot_panel.plot_regions(regions,
                                     title=plot_options['title'],
                                     legend=plot_options['legend'],
                                     legend_features=plot_options['legend_features'],
                                     scatter=plot_options['scatter'],
                                     colormap=plot_options['colormap'],
                                     font_size=int(service.get_service_parameter("FONT_SIZE")))
        # Left panel for fitting settings
        self.fit_settings_panel = ttk.Frame(toppanel, borderwidth=1, relief="groove")
        fit_button = ttk.Button(self.fit_settings_panel, text='Do Fit', command=self._do_fit)
        fit_button.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        self.settings = ttk.Frame(self.fit_settings_panel, borderwidth=1, relief="groove")
        # Choose spectrum color
        spectrum_color_frame = ttk.Frame(self.settings)
        spectrum_color_label = ttk.Label(spectrum_color_frame, text="Spectrum color", anchor=tk.W)
        spectrum_color_label.pack(side=tk.LEFT, expand=False)
        self.spectrum_color = tk.StringVar()
        self.spectrum_color.set("Default color")
        # Some colormaps suitable for plotting
        options = ['Default color'] + COLORS
        self.opmenu_spectrum_color = ttk.OptionMenu(spectrum_color_frame, self.spectrum_color,
                                                    self.spectrum_color.get(), *options)
        self.opmenu_spectrum_color.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        spectrum_color_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        # Draw residuals and fit line
        residuals_frame = ttk.Frame(self.settings)
        residuals_label = ttk.Label(residuals_frame, text="Plot residuals", anchor=tk.W)
        residuals_label.pack(side=tk.LEFT, expand=False)
        self.plot_residuals_var = tk.StringVar(value="")
        self.plot_residuals_box = tk.Checkbutton(residuals_frame, var=self.plot_residuals_var,
                                                 onvalue="True", offvalue="", background=BG,
                                                 anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
        self.plot_residuals_box.pack(side=tk.LEFT, anchor=tk.W)
        fitline_label = ttk.Label(residuals_frame, text="Plot fit line", anchor=tk.W)
        fitline_label.pack(side=tk.LEFT, expand=False)
        self.plot_fitline_var = tk.StringVar(value="True")
        self.plot_fitline_box = tk.Checkbutton(residuals_frame, var=self.plot_fitline_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
        self.plot_fitline_box.pack(side=tk.LEFT, anchor=tk.W)
        bg_label = ttk.Label(residuals_frame, text="Plot background", anchor=tk.W)
        bg_label.pack(side=tk.LEFT, expand=False)
        self.plot_bg_var = tk.StringVar(value="True")
        self.plot_bg_box = tk.Checkbutton(residuals_frame, var=self.plot_bg_var,
                                          onvalue="True", offvalue="", background=BG,
                                          anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
        self.plot_bg_box.pack(side=tk.LEFT, anchor=tk.W)
        residuals_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        same_scale_label = ttk.Label(residuals_frame, text="Same Y-scale", anchor=tk.W)
        same_scale_label.pack(side=tk.LEFT, expand=False)
        self.same_scale_var = tk.StringVar(value="True")
        self.same_scale_box = tk.Checkbutton(residuals_frame, var=self.same_scale_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
        self.same_scale_box.pack(side=tk.LEFT, anchor=tk.W)
        self.settings.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Choose background settings
        self.bg_panel = ttk.Frame(self.fit_settings_panel, borderwidth=1, relief="groove")
        self._populate_bg_panel()
        self.bg_panel.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Panel with fit lines specifications
        self.fit_panel = BrowserTreeView(self.fit_settings_panel, label=None, borderwidth=1, relief="groove")
        self.fit_tree = self.fit_panel.treeview
        self._populate_fit_tree()
        self.fit_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Action buttons
        self.buttons_panel = ttk.Frame(self.fit_settings_panel, borderwidth=1, relief="groove")

        after_fit_frame = ttk.Frame(self.buttons_panel)
        plot_subframe = ttk.Frame(after_fit_frame)
        plot_trends_button = ttk.Button(plot_subframe, text='Plot trends', command=self._plot_peak_areas)
        plot_trends_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        replot_button = ttk.Button(plot_subframe, text='Replot', command=self._plot)
        replot_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        plot_subframe.pack(side=tk.LEFT, fill=tk.X, expand=True)
        slider_subframe = ttk.Frame(after_fit_frame)
        previous_button = ttk.Button(slider_subframe, text='Previous', command=self._previous)
        previous_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        next_button = ttk.Button(slider_subframe, text='Next', command=self._next)
        next_button.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        slider_subframe.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        after_fit_frame.pack(side=tk.TOP, fill=tk.X)

        save_frame = ttk.Frame(self.buttons_panel)
        save_fit_button = ttk.Button(save_frame, text='Save Fit', command=self._save_fit)
        save_fit_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        save_fig_button = ttk.Button(save_frame, text='Save Figures', command=self._save_figures)
        save_fig_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        save_movie_button = ttk.Button(save_frame, text='Save Movie', command=lambda: self._save_figures(movie=True))
        save_movie_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        save_frame.pack(side=tk.TOP, fill=tk.X)

        close_window_button = ttk.Button(self.buttons_panel, text='Close Window', command=self.destroy)
        close_window_button.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.buttons_panel.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.fit_settings_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        toppanel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Bottom panel for output
        output_panel = ttk.Frame(self, borderwidth=1, relief="groove", height=50)
        fit_results_frame = BrowserTreeView(output_panel, label=None, borderwidth=1, relief="groove")
        self.fit_results_tree = fit_results_frame.treeview
        fit_results_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        output_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False)

    def _add_peak_line(self):
        peak_num = len(self.peak_lines.keys())
        fit = self.fittype
        if peak_num > 0:
            fit = self.peak_lines[peak_num - 1].fit_type
        self.peak_lines[peak_num] = AdvancedPeakLine(self.fit_tree, fit, self._remove_peak_line,
                                                     self._add_peak_line,
                                                     self._toggle_fit_type,
                                                     peak_num, data_max=self._get_all_max())
        self.peak_lines[peak_num].pack(side=tk.TOP, fill=tk.X, expand=False)
        self._redraw_add_remove_buttons()
        if peak_num > 0:
            AdvancedFitWindow.convert_peak_types(self.peak_lines[peak_num - 1], self.peak_lines[peak_num])

    @staticmethod
    def convert_peak_types(peak1, peak2):
        """
        Peak1 is already existing peak of certain type and with certain parameters. Peak2 is a new peak of a new type,
        for which the parameters should be grabbed from Peak1 and put to the corresponding fields.
        :param peak1: initial peak
        :param peak2: new peak
        :return: None
        """
        if (peak2.fit_type in ('Pseudo Voigt', 'Doniach-Sunjic') and peak1.fit_type in ('Pseudo Voigt', 'Doniach-Sunjic')) or \
                (peak2.fit_type in ('Gauss', 'Lorentz') and peak1.fit_type in ('Gauss', 'Lorentz')):
            peak2.set_all_parameters(*peak1.get_all_parameters(string_output=True))
        elif peak2.fit_type in ('Gauss', 'Lorentz') and peak1.fit_type in ('Pseudo Voigt', 'Doniach-Sunjic'):
            for par_name in ('amplitude', 'center', 'g_fwhm', 'l_fwhm'):
                if peak2.fit_type == 'Gauss' and par_name == 'g_fwhm':
                    peak2.set_parameter('fwhm',*peak1.get_parameter(par_name, string_output=True))
                if peak2.fit_type == 'Lorentz' and par_name == 'l_fwhm':
                    peak2.set_parameter('fwhm', *peak1.get_parameter(par_name, string_output=True))
                if par_name in ('amplitude', 'center'):
                    peak2.set_parameter(par_name, *peak1.get_parameter(par_name, string_output=True))
        elif peak2.fit_type in ('Pseudo Voigt', 'Doniach-Sunjic') and peak1.fit_type in ('Gauss', 'Lorentz'):
            for par_name in ('amplitude', 'center', 'fwhm'):
                if peak1.fit_type == 'Gauss' and par_name == 'fwhm':
                    peak2.set_parameter('g_fwhm', *peak1.get_parameter(par_name, string_output=True))
                if peak1.fit_type == 'Lorentz' and par_name == 'fwhm':
                    peak2.set_parameter('l_fwhm', *peak1.get_parameter(par_name, string_output=True))
                if par_name in ('amplitude', 'center'):
                    peak2.set_parameter(par_name, *peak1.get_parameter(par_name, string_output=True))

    def _display_message(self, msg, timestamp=True):
        # Clearing the previously existing text
        for widget in self.fit_results_tree.winfo_children():
            widget.destroy()
        if timestamp:
            msg = f"{datetime.datetime.now().strftime('%H:%M:%S')} " + msg
        results_msg = tk.Message(self.fit_results_tree, width=self.winfo_toplevel().winfo_width(), text=msg, anchor=tk.W, bg=BG)
        results_msg.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

    def _do_fit(self):
        bg_params = {}
        try:
            for label_name in fitter.Fitter.bg_types:
                if not bool(self.bg_values[label_name]['use'].get()):
                    continue
                bg_params[label_name] = {}
                bg_val = self.bg_values[label_name]['value'].get()
                if label_name == "constant" and bg_val in ('min', 'first'):
                    bg_params[label_name]['value'] = bg_val
                else:
                    bg_params[label_name]['value'] = float(bg_val)
                bg_params[label_name]['fix'] = bool(self.bg_values[label_name]['fix'].get())
                bg_params[label_name]['min'] = self.bg_values[label_name]['min'].get()
                bg_params[label_name]['max'] = self.bg_values[label_name]['max'].get()
        except ValueError:
            self._display_message("Check the values of background parameters. "
                                  "Should be numbers.\n"
                                  "For constant background, 'min' and 'first' are also allowed for Value parameter.")
            return

        peaks_info = []
        for peak_name, peak_line in self.peak_lines.items():
            if not peak_line.use_peak_var.get():
                continue
            peak_info = {}
            peak_info['parameters'] = peak_line.make_global_fit_dictionary()
            peak_info['fittype'] = peak_line.fit_type
            peak_info['peakname'] = f"Peak{peak_name}"
            peaks_info.append(peak_info)

        fit = GlobalFit(self.regions, peaks_info, bg_params)
        self.fitter_objs = fit.fit()
        self.currently_plotted = 0
        self._plot(self.currently_plotted)

        # Showing results
        round_precision = int(service.get_service_parameter('ROUND_PRECISION'))
        self.results_txt = ""
        for region_num in range(len(self.regions)):
            self.results_txt += f"Region #{region_num} ({self.fitter_objs[region_num].get_id()}):\n" \
                                f"--------------------------------------------------\n\n"
            self.results_txt += f"Goodness:\n" \
                                f"Chi^2 = {self.fitter_objs[region_num].get_chi_squared():.2f}\n" \
                                f"RMS = {self.fitter_objs[region_num].get_rms():.2f}\n\n"
            self.results_txt += f"Background parameters:\n"
            if self.fitter_objs[region_num].get_bg() is not None:
                for bg_key, bg_val in self.fitter_objs[region_num].get_bg().items():
                    self.results_txt += f"{bg_key}: {round(bg_val[0], round_precision)} +/- " \
                                        f"{round(bg_val[1], round_precision)}\n"
                self.results_txt += "\n"
            else:
                self.results_txt += f"None:\n\n"
            # Here we also fix the numbering for the proper vizualization in GUI
            pls = list(self.peak_lines.values())
            cnt = 0
            for i, peak in enumerate(self.fitter_objs[region_num].get_peaks()):
                while not pls[cnt].use_peak_var.get():
                    cnt += 1
                if peak:
                    self.results_txt += f"Peak {cnt}\n"
                    peak_area = round(peak.get_peak_area(), round_precision)
                    self.results_txt = "  ".join([self.results_txt, f"Area {peak_area}\n"])
                    peak_pars = [round(par, round_precision) for par in peak.get_parameters()]
                    peak_errors = peak.get_fitting_errors()
                    for i in range(len(peak_errors)):
                        if peak_errors[i] is None:
                            peak_errors[i] = 'NaN'
                        else:
                            peak_errors[i] = round(peak_errors[i], round_precision)
                    for i in range(len(peak_pars)):
                        par_names = fitter.Peak.peak_types[peak.get_peak_type()]
                        self.results_txt = "  ".join(
                            [self.results_txt, f"{par_names[i]}: {peak_pars[i]} +/- {peak_errors[i]}\n"])
                    self.results_txt += '\n'
                cnt += 1
        # Clearing the previously existing text
        for widget in self.fit_results_tree.winfo_children():
            widget.destroy()
        results_msg = tk.Message(self.fit_results_tree, text=self.results_txt, anchor=tk.W, bg=BG)
        results_msg.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

    def _get_all_max(self):
        """
        :return: Maximum intensity of all regions
        """
        allmax_intensity = 0
        for region in self.regions:
            region_max_intensity = np.max(region.get_data('final'))
            if region_max_intensity > allmax_intensity:
                allmax_intensity = region_max_intensity
        return allmax_intensity

    def _get_peak_lines_ids(self):
        return [k for k, v in self.peak_lines.items() if v]

    def _make_fit_dataframe(self):
        if self.fitter_objs is not None:
            data_cols = {}
            for i, fobj in enumerate(self.fitter_objs):
                x, fitline = fobj.get_virtual_fitline()
                data_cols[f"Region{i}_energy"] = x
                data_cols[f"Region{i}_fitline"] = fitline
                for peak in fobj.get_peaks():
                    if peak:
                        _, data_cols[f"Peak{peak.get_peak_id()}"] = peak.get_virtual_data()
            return pd.DataFrame(data_cols)

    def _plot(self, num=None):
        if self.fitter_objs is None:
            self._display_message("Do fitting first.")
            return
        if num is None and self.currently_plotted is not None:
            num = self.currently_plotted
        elif num is None and self.currently_plotted is None:
            num = 0
        assert num < len(self.regions)
        ymax = None
        if self.same_scale_var.get():
            ymax = 1.1 * self._get_all_max()
        if self.spectrum_color.get() != "Default color":
            region_color = self.spectrum_color.get()
        else:
            region_color = None
        self.plot_panel.plot_regions(self.regions[num],
                                     color=region_color,
                                     title=self.plot_options['title'],
                                     legend=self.plot_options['legend'],
                                     legend_features=self.plot_options['legend_features'],
                                     scatter=self.plot_options['scatter'],
                                     font_size=int(service.get_service_parameter("FONT_SIZE")),
                                     ymax=ymax)
        if self.fitter_objs is not None:
            peak_colors = []
            peak_fill = []
            for peak_line in self.peak_lines.values():
                if not peak_line.use_peak_var.get():
                    continue
                peak_colors.append(peak_line.peak_color.get())
                peak_fill.append(bool(peak_line.fill_color_var.get()))
            if self.spectrum_color.get() != "Default color":
                region_color = self.spectrum_color.get()
            else:
                region_color = None
            self.plot_panel.plot_fit(self.regions[num], self.fitter_objs[num], region_color=region_color, colors=peak_colors,
                                     residuals=self.plot_residuals_var.get(), fitline=self.plot_fitline_var.get(),
                                     bg=self.plot_bg_var.get(), fill=peak_fill,
                                     legend_feature=self.plot_options['legend_features'],
                                     title=self.plot_options['title'],
                                     font_size=int(service.get_service_parameter("FONT_SIZE")),
                                     ymax=ymax)

    def _plot_peak_areas(self, colors=None):
        if self.fitter_objs is None:
            self._display_message("Do fitting first.")
            return
        self.areas_plot_window = tk.Toplevel(self)
        self.areas_plot_window.wm_title("Peak areas")
        areas_plot_panel = PlotPanel(self.areas_plot_window, label=None, borderwidth=1, relief="groove")
        areas_plot_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        buttons_area = ttk.Frame(self.areas_plot_window)
        buttons_area.pack(side=tk.TOP, fill=tk.X, expand=False)
        save_data_button = ttk.Button(
            buttons_area,
            text='Save Data',
            command=lambda: self._save_peak_areas([fitter.get_peaks() for fitter in self.fitter_objs])
        )
        save_data_button.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        areas = {}
        labels = []
        x_ax = list(range(len(self.fitter_objs)))
        if colors is None:
            colors = []
            for peak_line in self.peak_lines.values():
                if not peak_line.use_peak_var.get():
                    continue
                if peak_line.peak_color.get() != "Default color":
                    colors.append(peak_line.peak_color.get())
                else:
                    colors.append(None)
        for peak in self.fitter_objs[0].get_peaks():
            areas[peak.get_peak_id()] = []
        for fobj in self.fitter_objs:
            for peak in fobj.get_peaks():
                areas[peak.get_peak_id()].append(peak.get_peak_area())
        for key, val in areas.items():
            labels.append(key)
            areas[key] = np.array(val)
        areas_plot_panel.plot_trends(x_ax, list(areas.values()), ax=None, ymin=None, ymax=None, log_scale=False, y_offset=0.0,
                                     scatter=False, labels=labels, colors=colors, font_size=12, legend=True,
                                     legend_pos='best')

    def _populate_bg_panel(self):
        self.bg_values = {}
        bg_label = ttk.Label(self.bg_panel, text="Fitting Background(s):", anchor=tk.W)
        bg_label.pack(side=tk.TOP, expand=False, anchor=tk.W)
        left_panel = ttk.Frame(self.bg_panel)
        middle_panel = ttk.Frame(self.bg_panel)
        sep = ttk.Separator(self.bg_panel, orient=tk.VERTICAL)
        right_panel = ttk.Frame(self.bg_panel)
        for label_name in fitter.Fitter.bg_types:
            entry_line = ttk.Frame(right_panel)
            # Collecting all values in one dictionary
            self.bg_values[label_name] = {}
            self.bg_values[label_name]['use'] = tk.StringVar(self, value="")
            self.bg_values[label_name]['use_cb'] = tk.Checkbutton(left_panel, var=self.bg_values[label_name]['use'],
                                                                  onvalue="True", offvalue="", background=BG,
                                                                  anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
            self.bg_values[label_name]['value'] = tk.StringVar(self, value="0.0")
            self.bg_values[label_name]['value_entry'] = ttk.Entry(entry_line,
                                                                  textvariable=self.bg_values[label_name]['value'],
                                                                  width=5)
            self.bg_values[label_name]['fix'] = tk.StringVar(self, value="True")
            self.bg_values[label_name]['fix_cb'] = tk.Checkbutton(entry_line, var=self.bg_values[label_name]['fix'],
                                                                  onvalue="True", offvalue="", background=BG,
                                                                  anchor=tk.W, relief=tk.FLAT, highlightthickness=0)
            self.bg_values[label_name]['min'] = tk.StringVar(self, value="")
            self.bg_values[label_name]['min_entry'] = ttk.Entry(entry_line,
                                                                textvariable=self.bg_values[label_name]['min'],
                                                                width=5)
            self.bg_values[label_name]['max'] = tk.StringVar(self, value="")
            self.bg_values[label_name]['max_entry'] = ttk.Entry(entry_line,
                                                                textvariable=self.bg_values[label_name]['max'],
                                                                width=5)
            # Stop collecting values
            self.bg_values[label_name]['use_cb'].pack(side=tk.TOP, fill=tk.Y, anchor=tk.W, expand=True)
            label = ttk.Label(middle_panel, text=label_name.capitalize(), anchor=tk.W)
            label.pack(side=tk.TOP, fill=tk.Y, expand=True, anchor=tk.W)

            val_label = ttk.Label(entry_line, text='Value', anchor=tk.W)
            val_label.pack(side=tk.LEFT, expand=False, anchor=tk.W)
            self.bg_values[label_name]['value_entry'].pack(side=tk.LEFT, anchor=tk.W)
            bounds_label = ttk.Label(entry_line, text='Bounds', anchor=tk.W)
            bounds_label.pack(side=tk.LEFT, expand=False, anchor=tk.W)
            self.bg_values[label_name]['min_entry'].pack(side=tk.LEFT, anchor=tk.W)
            self.bg_values[label_name]['max_entry'].pack(side=tk.LEFT, anchor=tk.W)
            fix_label = ttk.Label(entry_line, text='Fix', anchor=tk.W)
            fix_label.pack(side=tk.LEFT, expand=False, anchor=tk.W)
            self.bg_values[label_name]['fix_cb'].pack(side=tk.LEFT, anchor=tk.W)
            entry_line.pack(side=tk.TOP, fill=tk.X, expand=True)

        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        middle_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        sep.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

    def _populate_fit_tree(self):
        peak_num = len(self.peak_lines.keys())
        self.peak_lines[peak_num] = AdvancedPeakLine(self.fit_tree, self.fittype, self._remove_peak_line,
                                                     self._add_peak_line, self._toggle_fit_type,
                                                     peak_num,
                                                     data_max=self._get_all_max())
        self.peak_lines[peak_num].pack(side=tk.TOP, fill=tk.X, expand=False)
        self._redraw_add_remove_buttons()
        if peak_num > 0:
            self.peak_lines[peak_num].set_all_parameters(
                *self.peak_lines[peak_num - 1].get_all_parameters(string_output=True))

    def _previous(self):
        if self.fitter_objs is None:
            self._display_message("Do fitting first.")
            return
        if self.currently_plotted is None:
            return
        if self.currently_plotted == 0:
            return
        else:
            self.currently_plotted -= 1
            self._plot(self.currently_plotted)

    def _next(self):
        if self.fitter_objs is None:
            self._display_message("Do fitting first.")
            return
        if self.currently_plotted is None:
            return
        if self.currently_plotted == len(self.regions) - 1:
            return
        else:
            self.currently_plotted += 1
            self._plot(self.currently_plotted)

    def _redraw_add_remove_buttons(self):
        line_ids = self._get_peak_lines_ids()
        if len(line_ids) == 1:
            self.peak_lines[line_ids[0]].remove_peak_button.config(state=tk.DISABLED)
            self.peak_lines[line_ids[0]].add_peak_button.config(state=tk.NORMAL)
        else:
            for i, line_id in enumerate(line_ids):
                if i < len(line_ids) - 1:
                    self.peak_lines[line_id].add_peak_button.config(state=tk.DISABLED)
                elif i == len(line_ids) - 1:
                    self.peak_lines[line_id].add_peak_button.config(state=tk.NORMAL)
                self.peak_lines[line_id].remove_peak_button.config(state=tk.NORMAL)

    def _remove_peak_line(self, peak_id):
        self.peak_lines[peak_id].pack_forget()
        self.peak_lines[peak_id].destroy()
        self.peak_lines[peak_id] = None
        # If we remove a peak_line we need to renumber the remaining
        peak_line_copy = {}
        cnt = 0
        for val in self.peak_lines.values():
            if val:
                val.set_id(cnt)
                peak_line_copy[cnt] = val
                cnt += 1
        self.peak_lines = peak_line_copy
        self._redraw_add_remove_buttons()

    def _save_peak_areas(self, peaks):
        """
        :param self:
        :param peaks: list of lists
        :return:
        """
        dat_file_path = filedialog.asksaveasfilename(initialdir=service.get_service_parameter("DEFAULT_OUTPUT_FOLDER"),
                                                     initialfile="areas.dat",
                                                     title="Save peak areas trends...",
                                                     filetypes=(("dat files", "*.dat"), ("all files", "*.*")))
        if dat_file_path:
            headers = []
            peak_data = []
            for i in range(len(peaks[0])):
                headers.append(f"Peak{i}_Pos")
                headers.append(f"Peak{i}_Area")
            for peaks_set in peaks:
                pdat = []
                for peak in peaks_set:
                    pdat.append(peak.get_parameters(parameter='center'))
                    pdat.append(peak.get_peak_area())
                peak_data.append(pdat)
            df = pd.DataFrame(peak_data, columns=headers)
            try:
                with open(dat_file_path, 'w') as f:
                    df.to_csv(f, header=True, index=True, sep='\t')
            except (IOError, OSError):
                gui_logger.error(f"Couldn't save file {dat_file_path}", exc_info=True)
                self.winfo_toplevel().display_message(f"Couldn't save file {dat_file_path}")

    def _save_fit(self):
        if self.fitter_objs is None:
            self._display_message("Do fitting first.")
            return
        if self.results_txt is not None:
            output_dir = service.get_service_parameter("DEFAULT_OUTPUT_FOLDER")
            dat_file_path = filedialog.asksaveasfilename(initialdir=output_dir,
                                                         initialfile="global.fit",
                                                         title="Save as...",
                                                         filetypes=(("fit files", "*.fit"), ("all files", "*.*")))
            if dat_file_path:
                df = self._make_fit_dataframe().round(decimals=2)
                try:
                    with open(dat_file_path, 'w') as f:
                        f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Fitting:\n")
                        for i, region in enumerate(self.regions):
                            f.write(f"{region.get_id()} with {len(self.peak_lines)} peaks\n")
                        f.write(f"\n")
                        f.write(self.results_txt)
                        f.write("\n[Data]\n")
                        df.to_csv(f, header=True, index=False, sep='\t')
                except (IOError, OSError):
                    gui_logger.error(f"Couldn't save file {dat_file_path}", exc_info=True)
                    self.winfo_toplevel().display_message(f"Couldn't save file {dat_file_path}")

                output_dir = os.path.dirname(dat_file_path)
                service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)

    def _save_figures(self, movie=False):
        if self.fitter_objs is None:
            self._display_message("Do fitting first.")
            return
        output_dir = service.get_service_parameter("DEFAULT_OUTPUT_FOLDER")
        if movie:
            movie_file_path = filedialog.asksaveasfilename(
                initialdir=output_dir,
                initialfile=f"{self.regions[0].get_info(datahandler.Region.info_entries[0])}.mp4",
                title="Save movie as...",
                filetypes=(("mp4 files", "*.mp4"), ("all files", "*.*"))
            )
            if movie_file_path:
                while True:
                    try:
                        FFMpegWriter = animation.writers['ffmpeg']
                        metadata = dict(title=self.regions[0].get_id(), artist='SpecQP')
                        writer = FFMpegWriter(fps=15, metadata=metadata)
                        with writer.saving(self.plot_panel.figure, movie_file_path, 1000):
                            for region_num in range(len(self.regions)):
                                self._plot(region_num)
                                writer.grab_frame()
                        return True
                    except (RuntimeError, KeyError):
                        if plt.rcParams['animation.ffmpeg_path'] != service.get_service_parameter("FFMPEG_PATH"):
                            plt.rcParams['animation.ffmpeg_path'] = service.get_service_parameter("FFMPEG_PATH")
                            continue
                        if plt.rcParams['animation.ffmpeg_path'] == service.get_service_parameter("FFMPEG_PATH"):
                            ffmpeg_file_path = filedialog.askopenfilename(
                                initialdir="/",
                                parent=self,
                                title="The 'ffmpeg' codec is required for saving movie files.\n"
                                      "Choose the codec location manually if you have it installed,\n "
                                      "if not - check ffmpeg installation instructions for 'ffmpeg codec' on-line first.\n")
                            if ffmpeg_file_path and os.path.isfile(ffmpeg_file_path):
                                plt.rcParams['animation.ffmpeg_path'] = ffmpeg_file_path
                                service.set_init_parameters("FFMPEG_PATH", ffmpeg_file_path)
                                continue
                            elif ffmpeg_file_path and not os.path.isfile(ffmpeg_file_path):
                                self._display_message("\nNot a file. Choose ffmpeg executable.\n")
                                continue
                            elif not ffmpeg_file_path:
                                self._display_message("\nMovie file has not been saved.\n"
                                                      "The 'ffmpeg' codec installed on your computer is required.\n"
                                                      "Choose the codec location manually"
                                                      "if you have it installed, if not - "
                                                      "check ffmpeg installation instructions"
                                                      "for 'ffmpeg codec' on-line first.\n"
                                                      "Alternatively, save separate images"
                                                      " and combine them into a video manually "
                                                      "using a third-party software.\n"
                                                      )
                                gui_logger.error("Couldn't save the movie file.", exc_info=True)
                                return False
        else:
            save_dir_path = filedialog.askdirectory(initialdir=output_dir, title='Please select a directory')
            if save_dir_path:
                for region_num in range(len(self.regions)):
                    self._plot(region_num)
                    self.plot_panel.figure.savefig(save_dir_path + f'/{region_num}.png')

                return True
        self._display_message(".png/.mp4 files were not saved.")

    def _toggle_fit_type(self, peak_id, new_peak_type):
        peak_tmp = copy.copy(self.peak_lines[peak_id])
        self.peak_lines[peak_id].pack_forget()
        self.peak_lines[peak_id].destroy()
        self.peak_lines[peak_id] = AdvancedPeakLine(self.fit_tree, new_peak_type, self._remove_peak_line,
                                                    self._add_peak_line,
                                                    self._toggle_fit_type,
                                                    peak_id, data_max=self._get_all_max())
        AdvancedFitWindow.convert_peak_types(peak_tmp, self.peak_lines[peak_id])
        peak_tmp.destroy()
        self.update_peaks()

    def update_peaks(self):
        for peak_line in self.peak_lines.values():
            peak_line.pack_forget()
            peak_line.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.fit_tree.update()
        self._redraw_add_remove_buttons()


class MainWindow(ttk.PanedWindow):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["MainWindow"] = self
        self.browser_panel = BrowserPanel(self, borderwidth=1, relief="groove")
        self.add(self.browser_panel)
        self.corrections_panel = CorrectionsPanel(self, borderwidth=1, relief="groove")
        self.add(self.corrections_panel)
        self.plot_panel = PlotPanel(self, label='main', borderwidth=1, relief="groove")
        self.add(self.plot_panel)


class Root(tk.Tk):
    """Main GUI application class
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self._configure_style()
        # Dictionary of all widgets of the main window
        self.gui_widgets = {}
        # List of all toplevel windows with fits of the app (MainWindow is not included)
        self.fit_windows = []
        # Attribute keeping track of all regions loaded in the current GUI session
        self.loaded_regions = datahandler.RegionsCollection()
        self.results_msg = None

        self.main_menu_bar = tk.Menu(self)
        self.file_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.math_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.plot_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.help_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.generate_main_menu()

        tk.Tk.wm_title(self, "SpecQP")
        self.main_window = MainWindow(self, orient=tk.HORIZONTAL)
        self.main_window.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Bottom panel for output
        output_panel = ttk.Frame(self, borderwidth=1, relief="groove")
        self.log_panel = BrowserTreeView(output_panel, label=None, borderwidth=1, relief="groove")
        self.log_panel.pack(side=tk.TOP, fill=tk.X, expand=False)
        output_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False)

        # self.general_outlay_manager = ttk.PanedWindow(self, orient=tk.VERTICAL)
        # self.main_window = MainWindow(self.general_outlay_manager, orient=tk.HORIZONTAL)
        # self.general_outlay_manager.add(self.main_window)
        # self.log_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL, height=50)
        # self.log_panel = BrowserTreeView(self, label=None, borderwidth=1, relief="groove")
        # self.log_window.add(self.log_panel)
        # self.general_outlay_manager.add(self.log_window)
        # self.general_outlay_manager.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _concatenate_regions(self):
        pass

    def _configure_style(self):
        # Setting GUI color style
        self.style = ttk.Style()
        self.style.configure('.', font=LARGE_FONT, bg=BG, disabledbackground=BG, disabledforeground=BG)
        # self.style.configure('.TEntry', bg=BG, fg=BG, disabledforeground=BG, disabledbackground=BG)
        # self.style.configure('default.TCheckbutton', background=BG)
        # self.style.configure('default.TFrame', background=BG)

    def _do_regions_math(self, math):
        math_options = (
            'Add',
            'Subtract',
            'Reversed subtract'
        )
        assert math in math_options

        checked_ids = self.gui_widgets["BrowserPanel"].spectra_tree_panel.get_checked_items()
        if len(checked_ids) < 2:
            self.winfo_toplevel().display_message("Choose at least two regions for doing math.")
            return
        if math == math_options[1] and len(checked_ids) > 2:
            self.winfo_toplevel().display_message("Subtraction of more than two regions is ambiguous. "
                                                  "Choose exactly two for doing math.")
            return
        txt_regions_list = ""
        for reg_id in checked_ids:
            txt_regions_list += reg_id + "\n"
        new_region_id = simpledialog.askstring("Choose new region name (unique)",
                                               f"The following regions will be combined\n{txt_regions_list}",
                                               parent=self)
        if new_region_id is None:
            self.winfo_toplevel().display_message("Can't save region without a name.")
            return
        if new_region_id in self.loaded_regions.get_ids():
            self.winfo_toplevel().display_message("The name of the new region must be unique. "
                                                  "Please try again with a new unique name.")
            return
        try:
            # Addition
            if math == math_options[0]:
                new_region = self.loaded_regions.get_by_id(checked_ids[0])
                for i in range(1, len(checked_ids)):
                    new_region += self.loaded_regions.get_by_id(checked_ids[i])
            # Subtraction
            if math == math_options[1]:
                new_region = self.loaded_regions.get_by_id(checked_ids[0]) - self.loaded_regions.get_by_id(checked_ids[1])
            # Reversed subtraction
            if math == math_options[2]:
                new_region = self.loaded_regions.get_by_id(checked_ids[1]) - self.loaded_regions.get_by_id(checked_ids[0])
            new_region.set_id(new_region_id)
            new_region.set_info_entry(datahandler.Region.info_entries[7], new_region_id, overwrite=True)
            self.loaded_regions.add_regions(new_region)
            self.gui_widgets["BrowserPanel"].spectra_tree_panel.add_items_to_check_list(f"New region after {math}",
                                                                                        new_region_id)
        except Exception:
            self.winfo_toplevel().display_message("The regions you chose are incompatible and can't be combined.")

    def display_message(self, msg, timestamp=True):
        if self.results_msg is not None:
            self.results_msg.destroy()
        if timestamp:
            msg = f"{datetime.datetime.now().strftime('%H:%M:%S')} " + msg
        self.results_msg = tk.Message(self.log_panel.treeview, text=msg,
                                      width=self.winfo_toplevel().winfo_width(), anchor=tk.W, bg=BG)
        self.results_msg.pack(side=tk.TOP, fill=tk.X, expand=True)

    # TODO: write the functionality for the menu, add new menus if needed.
    def generate_main_menu(self):
        """Configuring the app menu
        """
        # File menu
        self.file_menu.add_command(label="Load SCIENTA files", command=self.load_file)
        self.file_menu.add_command(label="Load SPECS files", command=self.load_specs_file)
        self.file_menu.add_command(label="Load other file type", command=self.load_csv_file)
        self.file_menu.add_command(label="Open pressure calibration file", command=self.load_pressure_calibration)
        self.file_menu.add_command(label="Open file as text", command=self._open_file_as_text)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Quit", command=self.quit)
        self.main_menu_bar.add_cascade(label="File", menu=self.file_menu)

        # Plot menu
        self.plot_menu.add_command(label="Set font size", command=self._set_plot_font_size)
        self.plot_menu.add_command(label="Set plot aspect ratio", command=self._set_plot_aspect_ratio)
        self.main_menu_bar.add_cascade(label="Plot", menu=self.plot_menu)

        # Math menu
        self.math_menu.add_command(label="Add", command=lambda: self._do_regions_math(math='Add'))
        self.math_menu.add_command(label="Subtract", command=lambda: self._do_regions_math(math='Subtract'))
        self.math_menu.add_command(label="Reversed subtract",
                                   command=lambda: self._do_regions_math(math='Reversed subtract'))
        # self.file_menu.add_separator()
        # self.math_menu.add_command(label="Concatenate", command=lambda: self._concatenate_regions)
        self.main_menu_bar.add_cascade(label="Math", menu=self.math_menu)

        # Help menu
        self.help_menu.add_command(label="Export log", command=self.export_log)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="About", command=self.show_about)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Help...", command=self.show_help)
        self.main_menu_bar.add_cascade(label="Help", menu=self.help_menu)

        self.config(menu=self.main_menu_bar)

    def load_csv_file(self):
        file_names = filedialog.askopenfilenames(filetypes=[("Tabular text", ".txt .TXT .csv .CSV .dat .DAT"), ("All files", ".*")],
                                                 parent=self,
                                                 title="Choose tabular data files to load",
                                                 initialdir=service.get_service_parameter("DEFAULT_DATA_FOLDER"),
                                                 multiple=True)
        if file_names:
            self.load_file_list(file_names, datahandler.DATA_FILE_TYPES[2])
        else:
            gui_logger.warning("Couldn't get the file path from the load_file dialog in Root class")
            return

    def load_pressure_calibration(self):
        """Load and show pressure calibration file with a button allowing to plot certain column vs another column
        """
        def stylize_pc_ax(ax):
            ax.legend(fancybox=True, framealpha=0, loc='best')
            ax.ticklabel_format(axis='both', style='sci', scilimits=(0, 0))
            ax.set_aspect('auto')
            ax.set_facecolor('None')
            ax.grid(which='both', axis='both', color='grey', linestyle=':')
            ax.spines['bottom'].set_color('black')
            ax.spines['left'].set_color('black')
            ax.tick_params(axis='x', colors='black')
            ax.tick_params(axis='y', colors='black')
            ax.yaxis.label.set_color('black')
            ax.xaxis.label.set_color('black')
            ax.set_xlim(left=0)


        file_names = filedialog.askopenfilenames(filetypes=[("calibration", ".dat .DAT .txt .TXT"), ("All files", ".*")],
                                                 parent=self,
                                                 title="Choose calibration data files to load",
                                                 initialdir=service.get_service_parameter("DEFAULT_DATA_FOLDER"),
                                                 multiple=True)
        if file_names:
            service.set_init_parameters("DEFAULT_DATA_FOLDER", os.path.dirname(file_names[0]))
            calibration_data = datahandler.load_calibration_curves(file_names,
                                                                   columnx='Press_03_value',
                                                                   columny='Press_05_value')
            if len(calibration_data) > 0:
                press03vs05 = tk.Toplevel(self.winfo_toplevel())
                press03vs05.wm_title("Calibration data Press05(Press03)")
                plot_panel_03vs05 = PlotPanel(press03vs05, label=None)
                plot_panel_03vs05.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                for key, val in calibration_data.items():
                    plot_panel_03vs05.figure_axes.scatter(val[0], val[1], label=key, s=6)
                stylize_pc_ax(plot_panel_03vs05.figure_axes)

            calibration_data = datahandler.load_calibration_curves(file_names,
                                                                   columnx='DualGauge_01_value',
                                                                   columny='Press_05_value')
            if len(calibration_data) > 0:
                pressDualvs05 = tk.Toplevel(self.winfo_toplevel())
                pressDualvs05.wm_title("Calibration data Press05(PressDual01)")
                plot_panel_Dualvs05 = PlotPanel(pressDualvs05, label=None)
                plot_panel_Dualvs05.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                for key, val in calibration_data.items():
                    plot_panel_Dualvs05.figure_axes.scatter(val[0], val[1], label=key, s=6)
                stylize_pc_ax(plot_panel_Dualvs05.figure_axes)
        else:
            gui_logger.warning("Couldn't get calibration data files from askopenfiles dialog.")
            self.winfo_toplevel().display_message("Couldn't get calibration data files")

    def _open_file_as_text(self):
        """Open the read-only view of a text file in a Toplevel widget
        """
        file_path = filedialog.askopenfilename(parent=self, initialdir=service.get_service_parameter("DEFAULT_DATA_FOLDER"))
        if file_path:
            # If the user opens a file, remember the file folder to use it next time when the open request is received
            service.set_init_parameters("DEFAULT_DATA_FOLDER", os.path.dirname(file_path))

            text_view = tk.Toplevel(self)
            text_view.wm_title(ntpath.basename(file_path))
            text_panel = FileViewerWindow(text_view, file_path)
            text_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        else:
            gui_logger.warning(f"Couldn't get the file path from the _open_file_as_text dialog in Root class")

    def load_specs_file(self):
        self.load_file(file_type=datahandler.DATA_FILE_TYPES[1])

    def load_file(self, file_type=datahandler.DATA_FILE_TYPES[0]):
        file_names = filedialog.askopenfilenames(filetypes=[("XPS text", ".txt .TXT .xy .XY"), ("All files", ".*")],
                                                 parent=self,
                                                 title="Choose data files to load",
                                                 initialdir=service.get_service_parameter("DEFAULT_DATA_FOLDER"),
                                                 multiple=True)
        if file_names:
            self.load_file_list(file_names, file_type)
        else:
            gui_logger.warning("Couldn't get the file path from the load_file dialog in Root class")
            return

    def load_file_list(self, file_list: list, file_type):
        loaded_ids = {}
        if type(file_type) is str:
            file_type = [file_type]
        # If the user opens a file, remember the file folder to use it next time when the open request is received
        service.set_init_parameters("DEFAULT_DATA_FOLDER", os.path.dirname(file_list[0]))
        if len(file_type) == len(file_list):
            for i, file_name in enumerate(file_list):
                loaded_ids[file_name] = self.loaded_regions.add_regions_from_file(file_name, file_type[i])
        else:
            for file_name in file_list:
                loaded_ids[file_name] = self.loaded_regions.add_regions_from_file(file_name, file_type[0])
        last_region_id = ""
        if loaded_ids:
            for key, val in loaded_ids.items():
                # The 'loaded_ids' dictionary can contain several None values, which will be evaluated as True
                # in the previous 'if' clause. Therefore, we need to check every member as well.
                if val:
                    self.gui_widgets["BrowserPanel"].spectra_tree_panel.add_items_to_check_list(os.path.basename(key), val)
                    last_region_id = val[0]
                else:
                    if key in self.loaded_regions.get_ids():
                        gui_logger.warning(f"No regions loaded from {key}")
        # Fill the photon energy value if available in the file
        pe_from_file = float(self.loaded_regions.get_by_id(last_region_id).get_info(datahandler.Region.info_entries[3]))
        if pe_from_file > 1:
            self.gui_widgets["CorrectionsPanel"].photon_energy.set(str(round(pe_from_file, 2)))

    def export_log(self):
        output_dir = service.get_service_parameter("DEFAULT_OUTPUT_FOLDER")
        file_path = filedialog.asksaveasfilename(initialdir=output_dir,
                                                 initialfile=f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
                                                 title="Save as...",
                                                 filetypes=(("log files", "*.log"), ("all files", "*.*")))
        if file_path:
            try:
                copyfile(service.get_service_parameter("LOG_FILE_NAME"), file_path)
            except (IOError):
                gui_logger.error(f"Couldn't save log file", exc_info=True)

    def _set_plot_aspect_ratio(self):
        aspect_ratio = simpledialog.askfloat("Set plot aspect ratio", "Float value A (height = A * width)", parent=self)
        if aspect_ratio is not None:
            service.set_init_parameters("PLOT_ASPECT_RATIO", aspect_ratio)
            self.display_message(f"[Height = {aspect_ratio} * width] was set as the default aspect ratio for plots.")
        else:
            service.set_init_parameters("PLOT_ASPECT_RATIO", 0.75)
            self.display_message("No aspect ratio value received. Default aspect ratio [height = 0.75 * width] was set for plots.")

    def _set_plot_font_size(self):
        fontsize = simpledialog.askinteger("Set plot font size", "Font size (pt)", parent=self, minvalue=0, maxvalue=100)
        if fontsize is not None:
            service.set_init_parameters("FONT_SIZE", fontsize)
            self.display_message(f"{fontsize}pt was set as the default font size for plots.")
        else:
            service.set_init_parameters("FONT_SIZE", 12)
            self.display_message("No font size value received. Default font size for plotting was set to 12pt.")

    def show_about(self):
        messagebox.showinfo("About", "SpecQP v1.1\n"
                                     "Mikhail Shipilin\n"
                                     "mikhail.shipilin@gmail.com\n\n"
                                     "https://github.com/Shipilin/specqp")

    def show_help(self):
        result = messagebox.askquestion("Go to GitHub", "Do you want to look online?", icon='info')
        if result == 'yes':
            webbrowser.open('https://github.com/Shipilin/specqp', new=2)

def _parse_batch_parameters(container, params):
    for key, val in params.items():
        try:
            if not bool(val):
                continue
            if key == 'PE':
                container.photon_energy.set('; '.join(val))
                continue
            if key == 'ES':
                container.energy_shift.set('; '.join(val))
                continue
            if key == 'NC':
                container.do_const_norm_var.set("True")
                container.const_norm_var.set('; '.join(val))
                continue
            if key == 'CROP':
                if val[0][0] == val[0][1]:
                    continue
                start, stop = val[0][0], val[0][1]
                if all(x == start for x in list(zip(*val))[0]) and \
                   all(x == stop for x in list(zip(*val))[1]):
                    container.do_crop_var.set("True")
                    container.crop_left_var.set(start)
                    container.crop_right_var.set(stop)
            if key == 'CBG':
                if all(bool(x) == False for x in val):
                    container.subtract_const_var.set("")
            if key == 'SBG':
                if all(bool(x) == True for x in val):
                    container.subtract_shirley_var.set("True")
        except ValueError:
            print(f"Couldn't get parameter {key} value from batch file.")


def main(*args, **kwargs):
    app = Root()
    use_batch_parameters = False
    # Loading a batch of files if we know their paths and their types (scienta/specs)
    if "-batchload" in args and "FP" in kwargs and "FT" in kwargs:
        assert len(kwargs["FP"]) == len(kwargs["FT"])
        app.load_file_list(kwargs["FP"], kwargs["FT"])
        if "CO" in kwargs and bool(kwargs["CO"]):
            for i, region in enumerate(app.loaded_regions.get_regions()):
                region.set_conditions({"Comments": kwargs["CO"][i],}, overwrite=True)
        use_batch_parameters = True
    app.update()  # Update to be able to request main window parameters
    app.minsize(app.winfo_width(), app.winfo_height())
    app.resizable(1, 1)
    if use_batch_parameters:
        _parse_batch_parameters(app.gui_widgets["CorrectionsPanel"], kwargs)
        app.gui_widgets["CorrectionsPanel"]._plot()
    app.mainloop()
    # Upon exit save the service file
    service.write_init_file()