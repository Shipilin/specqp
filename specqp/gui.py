import os
import copy
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import Widget
import ntpath
import logging

import matplotlib
from matplotlib import cm
from matplotlib import style
from matplotlib.backend_tools import ToolBase
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
import matplotlib.image as mpimg

import numpy as np

from specqp import service
from specqp import datahandler
from specqp import plotter
from specqp import helpers
from specqp import fitter
from specqp.tools import Ruler

# Default font for the GUI
LARGE_FONT = ("Verdana", "12")

gui_logger = logging.getLogger("specqp.gui")  # Creating child logger
matplotlib.use('TkAgg')  # Configuring matplotlib interaction with tkinter
style.use('ggplot')  # Configuring matplotlib style

logo_img_file = "assets/specqp_icon.png"
tool_bar_images = {
    "invert_x": "assets/invert_x.png"
}
# Global background color hardcoded due to problems with MACOS color representation in tk
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
            self.text.insert(0.0, f"Can't open the file: {filepath}")
            self.text.config(state=tk.DISABLED)
            pass
        except ValueError:
            gui_logger.warning(f"Can't decode the file {filepath}", exc_info=True)
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


class CustomToolbar(NavigationToolbar2Tk):
    def home(self):
        NavigationToolbar2Tk.home(self)
        self.update()
        self.canvas.draw()

    def zoom(self):
        NavigationToolbar2Tk.zoom(self)
        self.update()
        self.canvas.draw()

    def invert_x(self):
        self.canvas.figure.axes[0].invert_xaxis()
        self.canvas.draw()

    def enable_ruler(self):
        markerprops = dict(marker='o', markersize=5, markeredgecolor='red')
        lineprops = dict(color='red', linewidth=2)
        ax = self.winfo_toplevel().gui_widgets["PlotPanel"].figure_axes
        ruler = tools.Ruler(ax=ax, useblit=True, markerprops=markerprops, lineprops=lineprops)

    def save_figure(self):
        NavigationToolbar2Tk.save_figure(self)
        self.update()
        self.canvas.draw()

    def __init__(self, canvas, parent):
        invert_x_tool = ToolBase(self, 'invert_x')
        self.toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            #('Back', 'Back to previous view', 'back', 'back'),
            #('Forward', 'Forward to next view', 'forward', 'forward'),
            #('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            #('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
            (None, None, None, None),
            ('InvertX', 'Invert X-axis', 'back', 'invert_x'),
            ('Ruler', 'Enable ruler', 'forward', 'enable_ruler'),
            (None, None, None, None),
            ('Save', 'Save the figure', 'filesave', 'save_figure'),
            )
        NavigationToolbar2Tk.__init__(self, canvas, parent)


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
        self.toolbar = CustomToolbar(self.canvas, self)  # NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.canvas.mpl_connect("key_press_event", self._on_key_press)
        # self.canvas.mpl_connect("button_press_event", self._on_mouse_click)

    def _on_key_press(self, event):
        gui_logger.debug(f"{event.key} pressed on plot canvas")
        key_press_handler(event, self.canvas, self.toolbar)

    # def _on_mouse_click(self, event):
    #     gui_logger.debug(f"{event.button} pressed on plot canvas")
    #     key_press_handler(event, self.canvas, self.toolbar)

    def plot_regions(self, regions, ax=None, x_data='energy', y_data='final', invert_x=True, log_scale=False,
                     y_offset=0.0, scatter=False, label=None, color=None, title=True, font_size=12, legend=True,
                     legend_features=("ID",), legend_pos='best', add_dimension=False, colormap=None):
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
                                               legend_features=legend_features, legend_pos=legend_pos)
                    offset += y_offset * region.get_add_dimension_counter()
            if len(regions) > 1:
                ax.set_title(None)
            ax.set_aspect('auto')
            ax.set_facecolor('None')
            ax.grid(which='both', axis='both', color='grey', linestyle=':')
            ax.spines['bottom'].set_color('black')
            ax.spines['left'].set_color('black')
            ax.tick_params(axis='x', colors='black')
            ax.tick_params(axis='y', colors='black')
            ax.yaxis.label.set_color('black')
            ax.xaxis.label.set_color('black')
            self.canvas.draw()
            self.toolbar.update()


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
        self.fit.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.select_fit_type = tk.StringVar()
        self.select_fit_type.set("Pseudo Voigt")
        options = list(fitter.Peak.peak_types.keys()) + ['Error Func']
        self.opmenu_fit_type = ttk.OptionMenu(self.fit_subframe, self.select_fit_type, self.select_fit_type.get(), *options)
        self.opmenu_fit_type.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.fit_subframe.pack(side=tk.TOP, fill=tk.X, expand=False)

    def _fit(self):
        fit_type = self.select_fit_type.get()
        regions_in_work = self._get_regions_in_work()
        for region in regions_in_work:
            if fit_type == 'Error Func':
                region.set_fermi_flag()
                # Special case: we didn't know that the region was Fermi before and might have corrected by the specified
                # energy shift. Here we can correct it back. Ambiguous result otherwise
                if region.is_energy_corrected():
                    region._flags["energy_shift_corrected"] = False
                    try:
                        region.correct_energy_shift(float(self.energy_shift.get()))
                    except ValueError:
                        gui_logger.warning("Check 'Energy Shift' parameter value. Must be a number.")
                        return
                    region._flags["energy_shift_corrected"] = False
            fit_window = FitWindow(self.winfo_toplevel(), region, fit_type, label='fit')
            self.winfo_toplevel().update()  # Update to be able to request fit_window parameters
            fit_window.wm_minsize(width=fit_window.winfo_width(), height=fit_window.winfo_height())
            self.winfo_toplevel().fit_windows.append(fit_window)

    def _get_regions_in_work(self):
        reg_ids = self.winfo_toplevel().gui_widgets["BrowserPanel"].spectra_tree_panel.get_checked_items()
        # We will work with copies of regions, so that the temporary changes are not stored
        regions_in_work = copy.deepcopy(self.winfo_toplevel().loaded_regions.get_by_id(reg_ids))
        if regions_in_work:
            pe = self.photon_energy.get()
            es = self.energy_shift.get()
            if pe:
                try:
                    pe = float(pe)
                except ValueError:
                    gui_logger.warning("Check 'Photon Energy' value. Must be a number.")
                    return
            if es:
                try:
                    es = float(es)
                except ValueError:
                    gui_logger.warning("Check 'Energy Shift' value. Must be a number.")
                    return
            if self.plot_use_settings_var.get():
                service.set_init_parameters(["PHOTON_ENERGY", "ENERGY_SHIFT"], [pe, es])
                for region in regions_in_work:
                    # if self.is_fermi_var.get():
                    #     region.set_fermi_flag()
                    if pe:
                        region.set_excitation_energy(pe)
                    if es and not region.get_flags()["fermi_flag"]:
                        region.correct_energy_shift(es)
                        region.add_correction("Energy shift corrected")
                    if self.plot_binding_var.get():
                        region.invert_to_binding()
                    if self.normalize_sweeps_var.get():
                        region.normalize_by_sweeps()
                        region.make_final_column("sweepsNormalized", overwrite=True)
                        region.add_correction("Normalized by sweeps")
                    if self.do_crop_var.get():
                        crop_left, crop_right = self.crop_left_var.get(), self.crop_right_var.get()
                        if crop_left and crop_right:
                            try:
                                region.crop_region(start=float(crop_left), stop=float(crop_right), changesource=True)
                                service.set_init_parameters("CROP", ';'.join([crop_left, crop_right]))
                            except ValueError:
                                gui_logger.warning("Check Crop values. Must be numbers.")
                    if self.subtract_const_var.get():
                        e = region.get_data('energy')
                        helpers.shift_by_background(region, [e[-10], e[-1]])
                        region.make_final_column("bgshifted", overwrite=True)
                        region.add_correction("Constant background subtracted")
                    if self.subtract_shirley_var.get():
                        helpers.subtract_shirley(region)
                        region.make_final_column("no_shirley", overwrite=True)
                        region.add_correction("Shirley background subtracted")
        return regions_in_work

    def _make_plotting_settings_subframe(self):
        # Plot name label
        self.plotting_label = ttk.Label(self, text="Plotting", anchor=tk.W)
        self.plotting_label.pack(side=tk.TOP, fill=tk.X)
        # Initializing two-columns section
        self.plotting_two_columns = ttk.Frame(self)
        self.plotting_left_column = ttk.Frame(self.plotting_two_columns, width=self.settings_left_column.winfo_width())
        self.plotting_right_column = ttk.Frame(self.plotting_two_columns, width=self.settings_right_column.winfo_width())
        # Plot in new window checkbox
        self.plot_separate_label = ttk.Label(self.plotting_left_column, text="Plot in new window", anchor=tk.W)
        self.plot_separate_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_separate_var = tk.StringVar(value="")
        self.plot_separate_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_separate_var,
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                )
        self.plot_separate_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Plot add-dimension if possible checkbox
        self.plot_add_dim_label = ttk.Label(self.plotting_left_column, text="Plot add-dimension", anchor=tk.W)
        self.plot_add_dim_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_add_dim_var = tk.StringVar(value="")
        self.plot_add_dim_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_add_dim_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                               )
        self.plot_add_dim_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Use settings
        self.plot_use_settings_label = ttk.Label(self.plotting_left_column, text="Use settings", anchor=tk.W)
        self.plot_use_settings_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_use_settings_var = tk.StringVar(value="True")
        self.plot_use_settings_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_use_settings_var,
                                                    onvalue="True", offvalue="", background=BG,
                                                    anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                    command=self._toggle_settings)
        self.plot_use_settings_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Binding energy axis
        self.plot_binding_label = ttk.Label(self.plotting_left_column, text="Binding energy axis", anchor=tk.W)
        self.plot_binding_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        if self.photon_energy.get():
            self.plot_binding_var = tk.StringVar(value="True")
        else:
            self.plot_binding_var = tk.StringVar(value="")
        self.plot_binding_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_binding_var,
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                               )
        self.plot_binding_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
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
        self.offset_value_entry.pack(side=tk.RIGHT, expand=False)
        self.offset_subframe.pack(side=tk.TOP, fill=tk.X, expand=True)
        # Legend
        self.plot_legend_label = ttk.Label(self.plotting_left_column, text="Add legend", anchor=tk.W)
        self.plot_legend_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_legend_var = tk.StringVar(value="True")
        self.plot_legend_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_legend_var,
                                              onvalue="True", offvalue="", background=BG,
                                              anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                              )
        self.plot_legend_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Title
        self.plot_title_label = ttk.Label(self.plotting_left_column, text="Add title", anchor=tk.W)
        self.plot_title_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.plot_title_var = tk.StringVar(value="True")
        self.plot_title_box = tk.Checkbutton(self.plotting_right_column, var=self.plot_title_var,
                                             onvalue="True", offvalue="", background=BG,
                                             anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                             )
        self.plot_title_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
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
        self.photon_energy = tk.StringVar(self, value=service.get_service_parameter("PHOTON_ENERGY"))
        self.pe_entry = ttk.Entry(self.settings_right_column, textvariable=self.photon_energy, width=8)
        self.pe_entry.pack(side=tk.TOP, anchor=tk.W, expand=False)
        # Energy shift
        self.eshift_label = ttk.Label(self.settings_left_column, text="Energy Shift (eV)", anchor=tk.W)
        self.eshift_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.energy_shift = tk.StringVar(self, value=service.get_service_parameter("ENERGY_SHIFT"))
        self.eshift_entry = ttk.Entry(self.settings_right_column, textvariable=self.energy_shift, width=8)
        self.eshift_entry.pack(side=tk.TOP, anchor=tk.W, expand=False)
        # Normalize by sweeps
        self.normalize_sweeps_label = ttk.Label(self.settings_left_column, text="Normalize by sweeps", anchor=tk.W)
        self.normalize_sweeps_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.normalize_sweeps_var = tk.StringVar(value="True")
        self.normalize_sweeps_box = tk.Checkbutton(self.settings_right_column, var=self.normalize_sweeps_var,
                                                   onvalue="True", offvalue="", background=BG,
                                                   anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                   )
        self.normalize_sweeps_box.pack(side=tk.TOP, anchor=tk.W)
        # Crop
        self.crop_label = ttk.Label(self.settings_left_column, text="Crop from:to (eV)", anchor=tk.W)
        self.crop_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        crop_entries_frame = ttk.Frame(self.settings_right_column)
        self.do_crop_var = tk.StringVar(value="")
        self.do_crop_box = tk.Checkbutton(crop_entries_frame, var=self.do_crop_var,
                                          onvalue="True", offvalue="", background=BG,
                                          anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                          command=self._read_crop_values
                                          )
        self.do_crop_box.pack(side=tk.LEFT)
        self.crop_left_var = tk.StringVar(self, value="")
        self.crop_right_var = tk.StringVar(self, value="")
        self.crop_left_entry = ttk.Entry(crop_entries_frame, textvariable=self.crop_left_var, width=8)
        self.crop_left_entry.pack(side=tk.LEFT, expand=False)
        self.crop_right_entry = ttk.Entry(crop_entries_frame, textvariable=self.crop_right_var, width=8)
        self.crop_right_entry.pack(side=tk.RIGHT, expand=False)
        crop_entries_frame.pack(side=tk.TOP, expand=False)
        # Subtract linear background
        self.subtract_const_label = ttk.Label(self.settings_left_column, text="Subtract constant bg", anchor=tk.W)
        self.subtract_const_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.subtract_const_var = tk.StringVar(value="True")
        self.subtract_const_box = tk.Checkbutton(self.settings_right_column, var=self.subtract_const_var,
                                                 onvalue="True", offvalue="", background=BG,
                                                 anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                 )
        self.subtract_const_box.pack(side=tk.TOP, anchor=tk.W)
        # Subtract Shirley background
        self.subtract_shirley_label = ttk.Label(self.settings_left_column, text="Subtract Shirley bg", anchor=tk.W)
        self.subtract_shirley_label.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.subtract_shirley_var = tk.StringVar(value="")
        self.subtract_shirley_box = tk.Checkbutton(self.settings_right_column, var=self.subtract_shirley_var,
                                                   onvalue="True", offvalue="", background=BG,
                                                   anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                   )
        self.subtract_shirley_box.pack(side=tk.TOP, anchor=tk.W)
        # Pack two-columns section
        self.settings_left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.settings_right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.settings_two_columns.pack(side=tk.TOP, fill=tk.X, expand=False)

    def _plot(self):
        self.regions_in_work = self._get_regions_in_work()
        offset = (self.offset_slider.get() / 100) * max([np.max(region.get_data(column='final'))
                                                         for region in self.regions_in_work if
                                                         len(region.get_data(column='final')) > 0])
        cmap = None if self.select_colormap.get() == "Default colormap" else self.select_colormap.get()
        if bool(self.plot_separate_var.get()):
            new_plot_window = tk.Toplevel(self.winfo_toplevel())
            new_plot_window.wm_title("Raw data")
            new_plot_panel = PlotPanel(new_plot_window, label=None, borderwidth=1, relief="groove")
            new_plot_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            new_plot_panel.plot_regions(self.regions_in_work,
                                        add_dimension=bool(self.plot_add_dim_var.get()),
                                        legend=bool(self.plot_legend_var.get()),
                                        title=bool(self.plot_title_var.get()),
                                        y_offset=offset, colormap=cmap)
        else:
            self.winfo_toplevel().gui_widgets["PlotPanel"].plot_regions(self.regions_in_work,
                                                                        add_dimension=bool(self.plot_add_dim_var.get()),
                                                                        legend=bool(self.plot_legend_var.get()),
                                                                        title=bool(self.plot_title_var.get()),
                                                                        y_offset=offset, colormap=cmap)

    def _read_crop_values(self):
        if self.crop_left_var.get() or self.crop_right_var.get():
            return
        if service.get_service_parameter("CROP"):
            crop_vals = service.get_service_parameter("CROP").split(';')
            self.crop_left_var.set(crop_vals[0])
            self.crop_right_var.set(crop_vals[1])

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
                    try:
                        with open(name_sqr, 'w') as f:
                            region.save_as_file(f, details=True, add_dimension=save_add_dimension, headers=True)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {name_sqr}", exc_info=True)

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
                    sqr_file_path = dat_file_path.rpartition('.')[0] + '.sqr'
                    try:
                        with open(sqr_file_path, 'w') as f:
                            region.save_as_file(f, details=True, add_dimension=save_add_dimension, headers=True)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {sqr_file_path}", exc_info=True)

                output_dir = os.path.dirname(dat_file_path)
            service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)

    def _toggle_settings(self):
        if self.plot_use_settings_var.get():
            self.photon_energy.set(service.get_service_parameter("PHOTON_ENERGY"))
            self.energy_shift.set(service.get_service_parameter("ENERGY_SHIFT"))
            self.normalize_sweeps_var.set("True")
            self.subtract_const_var.set("True")
            self.plot_binding_var.set("True")
            self.subtract_shirley_var.set("")
            self.do_crop_var.set("")
            try:
                crop_vals = service.get_service_parameter("CROP").split(';')
            except (IndexError, IOError):
                crop_vals = ['','']
            self.crop_left_var.set(crop_vals[0])
            self.crop_right_var.set(crop_vals[1])
            for obj in (self.subtract_const_box,
                        self.subtract_shirley_box,
                        self.do_crop_box,
                        self.crop_left_entry,
                        self.crop_right_entry,
                        self.normalize_sweeps_box,
                        self.plot_binding_box,
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
                        self.normalize_sweeps_var,
                        self.plot_binding_var,
                        self.photon_energy,
                        self.energy_shift
                        ):
                obj.set("")
            # Setting boxes and entries to DISABLED
            for obj in (self.subtract_const_box,
                        self.subtract_shirley_box,
                        self.do_crop_box,
                        self.crop_left_entry,
                        self.crop_right_entry,
                        self.normalize_sweeps_box,
                        self.plot_binding_box,
                        self.pe_entry,
                        self.eshift_entry
                        ):
                obj.config(state=tk.DISABLED)


class PeakLine(ttk.Frame):
    def __init__(self, parent, fit_type, remove_func, add_func, id_, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._id = id_
        self.fit_type = fit_type
        self.use_peak_vars = []
        self.parameter_vals = {}
        self.parameter_bounds = {}
        self.parameter_fix_vals = {}
        self.parameter_fix_boxes = {}

        title_frame = ttk.Frame(self)
        self.remove_peak_button = ttk.Button(title_frame, text='-', command=lambda: remove_func(self._id), width=1)
        self.remove_peak_button.pack(side=tk.RIGHT, expand=False)
        self.add_peak_button = ttk.Button(title_frame, text='+', command=lambda: add_func(), width=1)
        self.add_peak_button.pack(side=tk.RIGHT, expand=False)
        self.id_var = tk.StringVar(value=f"Peak {id_}:")
        self.use_peak_vars.append(tk.StringVar(value="True"))
        use_peak_box = tk.Checkbutton(title_frame, var=self.use_peak_vars[-1],
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
            self.parameter_vals[par_name] = tk.StringVar(self, value="")
            parameter_entry = ttk.Entry(parameter_entry_frame, textvariable=self.parameter_vals[par_name], width=8)
            parameter_entry.pack(side=tk.LEFT, expand=False)
            slash_label = ttk.Label(parameter_entry_frame, text="/")
            slash_label.pack(side=tk.LEFT, expand=False)
            self.parameter_bounds[par_name] = tk.StringVar(self, value="")
            parameter_bounds_entry = ttk.Entry(parameter_entry_frame, textvariable=self.parameter_bounds[par_name], width=8)
            parameter_bounds_entry.pack(side=tk.LEFT, expand=False)
            fix_label = ttk.Label(parameter_entry_frame, text="fix", anchor=tk.W)
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
        """Returns parameter str value and bounds for the specified parameter
        :param par_name: str
        :param string_output: True if type string output required
        :return: (float, list of floats) or (str, str) if string_output=True
        """
        if par_name in self.parameter_vals.keys():
            if string_output:
                return self.parameter_vals[par_name].get(), self.parameter_bounds[par_name].get()
            else:
                try:
                    if self.parameter_vals[par_name].get():
                        val = round(float(self.parameter_vals[par_name].get()), int(service.service_vars['ROUND_PRECISION']))
                    else:
                        val = None
                    if self.parameter_bounds.get():
                        bounds = [round(float(s.strip()), int(service.service_vars['ROUND_PRECISION']))
                                  for s in self.parameter_bounds.get().split(';')]
                    else:
                        bounds = [None, None]
                    return val, bounds
                except ValueError:
                    gui_logger.warning(f"Check parameter entries for Peak {self._id}. Must be numbers.")
                    return None

    def get_all_parameters(self, string_output=False):
        """Returns parameter values and bounds for all parameters
        :return: (list of str,
                  list of floats,
                  list of lists (of two floats))
                  or
                  (list of str,
                  list of str,
                  list of str) if string_output == True
        """
        if string_output:
            vals = [self.parameter_vals[key].get() for key in self.parameter_vals.keys()]
            bounds = [self.parameter_bounds[key].get() for key in self.parameter_vals.keys()]
            return self.parameter_vals.keys(), vals, bounds
        else:
            vals, bounds = [], []
            for key in self.parameter_vals.keys():
                par = self.get_parameter(key, string_output=False)
                if par is None:
                    return
                vals.append(par[0])
                bounds.append(par[1])
        return self.parameter_vals.keys(), vals, bounds

    def set_id(self, new_id):
        self._id = new_id
        self.id_var.set(f"Peak {new_id}:")

    def set_parameter(self, par_name, par_value, par_bounds):
        """Sets parameter value and bounds for the specified parameter
        :param par_name: str
        :param par_value: float or str representing a float
        :param par_bounds: list of two floats or string representing two floats separated with ';'
        """
        if type(par_value) == str and type(par_bounds) == str:
            if par_name in self.parameter_vals.keys():
                self.parameter_vals[par_name].set(par_value)
                self.parameter_bounds[par_name].set(par_bounds)
                return True
        else:
            assert len(par_bounds) == 2
            if par_name in self.parameter_vals.keys():
                self.parameter_vals[par_name].set(round(par_value, int(service.service_vars['ROUND_PRECISION'])))
                self.parameter_bounds[par_name].set(f"{round(par_bounds[0], int(service.service_vars['ROUND_PRECISION']))};"
                                                    f"{round(par_bounds[1], int(service.service_vars['ROUND_PRECISION']))}")
                return True

    def set_all_parameters(self, par_names: list, par_values: list, par_bounds: list):
        """Sets parameter values and bounds for all parameters
        :param par_names: list of str
        :param par_values: list of str or list of floats
        :param par_bounds: list of str or list of lists (of two floats)
        """
        assert len(par_values) == len(par_bounds) == len(par_names)
        for i, pn in enumerate(par_names):
            self.set_parameter(pn, par_values[i], par_bounds[i])


class FitWindow(tk.Toplevel):
    def __init__(self, parent, region, fit_type, label='fit', *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.wm_title(f"Fitting {fit_type} to {region.get_id()}")
        self.fittype = fit_type
        self.label = label
        self.region = region
        self.peak_lines = {}
        self.plot_panel = PlotPanel(self, label=None, borderwidth=1, relief="groove")
        self.plot_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.plot_panel.plot_regions(region)
        if fit_type == 'Error Func':
            self.fit_panel = ttk.Frame(self, borderwidth=1, relief="groove")
            self._add_error_func_section()
        else:
            self.fit_panel = BrowserTreeView(self, label=None, borderwidth=1, relief="groove")
            self.fit_tree = self.fit_panel.treeview
            self._add_peak_line()
        self.fit_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

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
                                  textvariable=parent_obj.error_func_pars_output[-1])
            entry.pack(side=tk.TOP, fill=tk.X, expand=False)

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
                                             self._add_peak_line, peak_num)
        self.peak_lines[peak_num].pack(side=tk.TOP, fill=tk.X, expand=False)
        self._redraw_add_remove_buttons()
        if peak_num > 0:
            self.peak_lines[peak_num].set_all_parameters(*self.peak_lines[peak_num - 1].get_all_parameters(string_output=True))
            for par_name in fitter.Peak.peak_types[self.fittype]:
                if self.peak_lines[peak_num - 1].parameter_fix_vals[par_name].get():
                    self.peak_lines[peak_num].parameter_fix_vals[par_name].set("True")


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
        gauss_fwhm = [2 * (np.log(2.0)) ** (.5) * np.absolute(fit_res[0][2]), fit_res[1][2]]
        self.gauss_fwhm.set(f"Gauss contribution: {round(gauss_fwhm[0], int(service.service_vars['ROUND_PRECISION']))} +/- "
                            f"{round(gauss_fwhm[1], int(service.service_vars['ROUND_PRECISION']))}")
        self._plot_error_func_fit(f"fit: {round(shift[0], int(service.service_vars['ROUND_PRECISION']))} +/- "
                                  f"{round(shift[1], int(service.service_vars['ROUND_PRECISION']))}")

    def _get_peak_lines_ids(self):
        return [k for k, v in self.peak_lines.items() if v]

    def _plot_error_func_fit(self, fit_label):
        ax = self.plot_panel.figure_axes
        ax.clear()
        plotter.plot_region(self.region, ax, y_data="final", scatter=True, title=False, legend_features=('ID',))
        plotter.plot_region(self.region, ax, y_data="fitFermi", title=False, label=fit_label)
        ax.grid(which='both', axis='x', color='grey', linestyle=':')
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
                self.peak_lines[line_id].remove_peak_button.config(state=tk.NORMAL)


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
        self._configure_style()
        # Dictionary of all widgets of the main window
        self.gui_widgets = {}
        # List of all toplevel windows with fits of the app (MainWindow is not included)
        self.fit_windows = []
        # Attribute keeping track of all regions loaded in the current GUI session
        self.loaded_regions = datahandler.RegionsCollection()

        self.main_menu_bar = tk.Menu(self)
        self.file_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.help_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.generate_main_menu()

        tk.Tk.wm_title(self, "SpecQP")
        self.main_window = MainWindow(self, orient=tk.HORIZONTAL)
        self.main_window.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _configure_style(self):
        # Setting GUI color style
        self.style = ttk.Style()
        self.style.configure('.', font=LARGE_FONT, bg=BG, disabledbackground=BG, disabledforeground=BG)
        # self.style.configure('.TEntry', bg=BG, fg=BG, disabledforeground=BG, disabledbackground=BG)
        # self.style.configure('default.TCheckbutton', background=BG)
        # self.style.configure('default.TFrame', background=BG)

    # TODO: write the functionality for the menu, add new menus if needed.
    def generate_main_menu(self):
        """Configuring the app menu
        """
        # File menu
        self.file_menu.add_command(label="Load SCIENTA Files", command=self.load_file)
        self.file_menu.add_command(label="Load SPECS Files", command=self.load_specs_file)
        self.file_menu.add_command(label="Open pressure calibration", command=self.load_pressure_calibration)
        self.file_menu.add_command(label="Open File as Text", command=self._open_file_as_text)

        self.file_menu.add_separator()
        self.file_menu.add_command(label="Quit", command=self.quit)
        self.main_menu_bar.add_cascade(label="File", menu=self.file_menu)

        # Help menu
        self.help_menu.add_command(label="Export log", command=self.export_log)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="About", command=self.show_about)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Help...", command=self.show_help)
        self.main_menu_bar.add_cascade(label="Help", menu=self.help_menu)

        self.config(menu=self.main_menu_bar)

    def load_pressure_calibration(self):
        """Load and show pressure calibration file with a button allowing to plot certain column vs another column
        """
        file_names = filedialog.askopenfilenames(filetypes=[("calibration", ".dat .DAT .txt .TXT"), ("All files", ".*")],
                                                 parent=self,
                                                 title="Choose calibration data files to load",
                                                 initialdir=service.get_service_parameter("DEFAULT_DATA_FOLDER"),
                                                 multiple=True)
        if file_names:
            service.set_init_parameters("DEFAULT_DATA_FOLDER", os.path.dirname(file_names[0]))
            calibration_data = datahandler.load_calibration_curves(file_names)
            new_plot_window = tk.Toplevel(self.winfo_toplevel())
            new_plot_window.wm_title("Calibration data")
            new_plot_panel = PlotPanel(new_plot_window, label=None)
            new_plot_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            for key, val in calibration_data.items():
                new_plot_panel.figure_axes.scatter(val[0], val[1], label=key, s=6)
            new_plot_panel.figure_axes.legend(fancybox=True, framealpha=0, loc='best')
            new_plot_panel.figure_axes.ticklabel_format(axis='both', style='sci', scilimits=(0, 0))
            new_plot_panel.figure_axes.set_aspect('auto')
            new_plot_panel.figure_axes.set_facecolor('None')
            new_plot_panel.figure_axes.grid(which='both', axis='both', color='grey', linestyle=':')
            new_plot_panel.figure_axes.spines['bottom'].set_color('black')
            new_plot_panel.figure_axes.spines['left'].set_color('black')
            new_plot_panel.figure_axes.tick_params(axis='x', colors='black')
            new_plot_panel.figure_axes.tick_params(axis='y', colors='black')
            new_plot_panel.figure_axes.yaxis.label.set_color('black')
            new_plot_panel.figure_axes.xaxis.label.set_color('black')
            new_plot_panel.figure_axes.set_xlim(left=0)
        else:
            gui_logger.warning("Couldn't get calibration data files from askopenfiles dialog.")

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
            loaded_ids = {}
            # If the user opens a file, remember the file folder to use it next time when the open request is received
            service.set_init_parameters("DEFAULT_DATA_FOLDER", os.path.dirname(file_names[0]))
            for file_name in file_names:
                loaded_ids[file_name] = self.loaded_regions.add_regions_from_file(file_name, file_type)
        else:
            gui_logger.warning("Couldn't get the file path from the load_file dialog in Root class")
            return

        if loaded_ids:
            for key, val in loaded_ids.items():
                # The 'loaded_ids' dictionary can contain several None values, which will be evaluated as True
                # in the previous 'if' clause. Therefore, we need to check every member as well.
                if val:
                    self.gui_widgets["BrowserPanel"].spectra_tree_panel.add_items_to_check_list(os.path.basename(key), val)
                else:
                    if key in self.loaded_regions.get_ids():
                        gui_logger.warning(f"No regions loaded from {key}")

    def export_log(self):
        pass

    def show_about(self):
        pass

    def show_help(self):
        pass


def main():
    app = Root()
    app.update()  # Update to be able to request main window parameters
    app.minsize(app.winfo_width(), app.winfo_height())
    app.resizable(1, 1)
    app.mainloop()
