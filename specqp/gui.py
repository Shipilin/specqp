import os
import copy
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import ntpath
import logging

import matplotlib
from matplotlib import style
from matplotlib.backend_tools import ToolBase
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
import matplotlib.image as mpimg

from specqp import service
from specqp import datahandler
from specqp import plotter
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
    def __init__(self, parent, default_items=None, *args, **kwargs):
        """Creates a check list with loaded file names as sections and corresponding regions IDs as checkable items
        :param default_items: dictionary {"file_name1": ("ID1, ID2,..."), "file_name2": ("ID1", "ID2", ...)}
        :param args:
        :param kwargs:
        """
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["BrowserTreeView"] = self

        self.check_all_frame = ttk.Frame(self)
        self.check_all_frame.pack(side=tk.TOP, fill=tk.X, expand=False)

        self.scrollable_canvas = tk.Canvas(self)
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
                                                    onvalue="Check all", offvalue="",
                                                    anchor=tk.W, relief=tk.FLAT, highlightthickness=0,
                                                    command=self._toggle_all
                                                    )
                self.check_all_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
                sep = ttk.Separator(self.check_all_frame, orient=tk.HORIZONTAL)
                sep.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)

        file_name_label = tk.Label(self.treeview, text=section_name, anchor=tk.W)
        file_name_label.pack(side=tk.TOP, fill=tk.X)
        for item in items:
            var = tk.StringVar(value=item)
            self.check_list_items.append(var)
            cb = tk.Checkbutton(self.treeview, var=var, text=item,
                                onvalue=item, offvalue="",
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
        # self.plot_checked_button = ttk.Button(self.buttons_panel,
        #                                       text='Plot Checked', command=self._plot_checked)
        # self.plot_checked_button.pack(side=tk.TOP, fill=tk.X)
        # self.plot_add_dimension = ttk.Button(self.buttons_panel,
        #                                      text='Plot Add Dimension', command=self._plot_add_dimension)
        # self.plot_add_dimension.pack(side=tk.TOP, fill=tk.X)
        self.blank_label = ttk.Label(self.buttons_panel,
                                     text="", anchor=tk.W)
        self.blank_label.pack(side=tk.TOP, fill=tk.X)
        self.app_quit_button = ttk.Button(self.buttons_panel,
                                          text='Quit', command=self._quit)
        self.app_quit_button.pack(side=tk.TOP, fill=tk.X)
        self.buttons_panel.pack(side=tk.TOP, fill=tk.X, expand=False)

        # Files tree panel
        self.spectra_tree_panel = BrowserTreeView(self, borderwidth=1, relief="groove")
        self.spectra_tree_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _ask_load_scienta_file(self):
        self.winfo_toplevel().load_file(file_type=datahandler.DATA_FILE_TYPES[0])

    def _ask_load_specs_file(self):
        self.winfo_toplevel().load_file(file_type=datahandler.DATA_FILE_TYPES[1])

    def _quit(self):
        self.winfo_toplevel().quit()  # stops mainloop

    # def _plot_checked(self):
    #     regions_for_plotting = self.spectra_tree_panel.get_checked_items()
    #     if regions_for_plotting:
    #         self.winfo_toplevel().gui_widgets["PlotPanel"].plot_regions(regions_for_plotting,
    #                                                                     add_dimension=False, legend=True)

    # def _plot_add_dimension(self):
    #     regions_for_plotting = self.spectra_tree_panel.get_checked_items()
    #     if regions_for_plotting:
    #         self.winfo_toplevel().gui_widgets["PlotPanel"].plot_regions(regions_for_plotting,
    #                                                                     add_dimension=True, legend=True)


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
                     y_offset=0.0, scatter=False, label=None, color=None, title=True, font_size=8, legend=True,
                     legend_features=("ID",), legend_pos='best', add_dimension=False):
        if regions:
            if not ax:
                ax = self.figure_axes
            ax.clear()
            for region in regions:
                if not add_dimension or not region.is_add_dimension():
                    plotter.plot_region(region, ax, x_data=x_data, y_data=y_data, invert_x=invert_x, log_scale=log_scale,
                                        y_offset=y_offset, scatter=scatter, label=label, color=color, title=title,
                                        font_size=font_size, legend=legend, legend_features=legend_features,
                                        legend_pos=legend_pos)
                else:
                    plotter.plot_add_dimension(region, ax, x_data=x_data, y_data=y_data, invert_x=invert_x, log_scale=log_scale,
                                               y_offset=1000, scatter=scatter, label=label, color=color, title=title,
                                               font_size=font_size, legend=legend, legend_features=legend_features,
                                               legend_pos=legend_pos)
            if len(regions) > 1:
                ax.set_title(None)
            ax.set_aspect('auto')
            self.canvas.draw()
            self.toolbar.update()


class CorrectionsPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["CorrectionsPanel"] = self
        self.regions_in_work = None
        # Corrections name label
        self.plot_label = ttk.Label(self, text="Settings", anchor=tk.W)
        self.plot_label.pack(side=tk.TOP, fill=tk.X)
        # Settings
        self.settings = ttk.Frame(self)
        self.left_labels = ttk.Frame(self.settings)
        self.right_entries = ttk.Frame(self.settings)
        # photon energy
        self.pe_label = ttk.Label(self.left_labels, text="Photon Energy (eV)", anchor=tk.W)
        self.pe_label.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Read photon energy from init file if available
        self.photon_energy = tk.StringVar(self, value=service.get_service_parameter("PHOTON_ENERGY"))
        self.pe_entry = ttk.Entry(self.right_entries, textvariable=self.photon_energy)
        self.pe_entry.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Energy shift
        self.eshift_label = ttk.Label(self.left_labels, text="Energy Shift (eV)", anchor=tk.W)
        self.eshift_label.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.energy_shift = tk.StringVar(self, value=service.get_service_parameter("ENERGY_SHIFT"))
        self.eshift_entry = ttk.Entry(self.right_entries, textvariable=self.energy_shift)
        self.eshift_entry.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Normalize by sweeps
        self.normalize_sweeps_label = ttk.Label(self.left_labels, text="Normalize by sweeps", anchor=tk.W)
        self.normalize_sweeps_label.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.normalize_sweeps_var = tk.StringVar(value="True")
        self.normalize_sweeps_box = tk.Checkbutton(self.right_entries, var=self.normalize_sweeps_var,
                                                   onvalue="True", offvalue="", background=BG,
                                                   anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                   )
        self.normalize_sweeps_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Pack setting
        self.left_labels.pack(side=tk.LEFT, fill=tk.X, expand=False)
        self.right_entries.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.settings.pack(side=tk.TOP, fill=tk.X, expand=False)
        # Blank label
        self.blank_label = ttk.Label(self, text="", anchor=tk.W)
        self.blank_label.pack(side=tk.TOP, fill=tk.X)
        # Plot name label
        self.plot_label = ttk.Label(self, text="Plotting", anchor=tk.W)
        self.plot_label.pack(side=tk.TOP, fill=tk.X)
        # Plot in new window checkbox
        self.plot_separate_var = tk.StringVar(value="")
        self.plot_separate_box = tk.Checkbutton(self, var=self.plot_separate_var, text="Plot in new window",
                                                onvalue="True", offvalue="", background=BG,
                                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                )
        self.plot_separate_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Plot add-dimension if possible checkbox
        self.plot_add_dim_var = tk.StringVar(value="")
        self.plot_add_dim_box = tk.Checkbutton(self, var=self.plot_add_dim_var, text="Plot add-dimension",
                                               onvalue="True", offvalue="", background=BG,
                                               anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                               )
        self.plot_add_dim_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Use settings
        self.plot_use_settings_var = tk.StringVar(value="True")
        self.plot_use_settings_box = tk.Checkbutton(self, var=self.plot_use_settings_var, text="Use settings",
                                                    onvalue="True", offvalue="", background=BG,
                                                    anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                    )
        self.plot_use_settings_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Binding energy axis
        self.plot_binding_var = tk.StringVar(value="True")
        self.plot_binding_box = tk.Checkbutton(self, var=self.plot_binding_var, text="Binding energy axis",
                                                    onvalue="True", offvalue="", background=BG,
                                                    anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                                    )
        self.plot_binding_box.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)
        # Plot button
        self.plot = ttk.Button(self, text='Plot', command=self._plot)
        self.plot.pack(side=tk.TOP, fill=tk.X)
        # Save buttons
        self.save = ttk.Button(self, text='Save', command=self._save)
        self.save.pack(side=tk.TOP, fill=tk.X)
        self.saveas = ttk.Button(self, text='Save as...', command=self._saveas)
        self.saveas.pack(side=tk.TOP, fill=tk.X)

    def _plot(self):
        reg_ids = self.winfo_toplevel().gui_widgets["BrowserPanel"].spectra_tree_panel.get_checked_items()
        # We will work with copies of regions, so that the temporary changes are not stored
        self.regions_in_work = copy.deepcopy(self.winfo_toplevel().loaded_regions.get_by_id(reg_ids))
        if self.regions_in_work:
            pe = self.photon_energy.get()
            es = self.energy_shift.get()
            if pe:
                try:
                    pe = float(pe)
                except ValueError:
                    gui_logger.warning("Check 'Photon Energy' value.")
                    return
            if es:
                try:
                    es = float(es)
                except ValueError:
                    gui_logger.warning("Check 'Energy Shift' value.")
                    return
            if self.plot_use_settings_var.get():
                service.set_init_parameters(["PHOTON_ENERGY", "ENERGY_SHIFT"], [pe, es])
                for region in self.regions_in_work:
                    if pe:
                        region.set_excitation_energy(pe)
                    if es:
                        region.correct_energy_shift(es)
                    if self.plot_binding_var.get():
                        region.invert_to_binding()
                    if self.normalize_sweeps_var.get():
                        region.normalize_by_sweeps()
                        region.make_final_column("sweepsNormalized", overwrite=True)

            plot_add_dim = bool(self.plot_add_dim_var.get())
            if self.plot_separate_var.get():
                new_plot_window = tk.Toplevel(self.winfo_toplevel())
                new_plot_window.wm_title("Raw data")
                new_plot_panel = PlotPanel(new_plot_window, label=None)
                new_plot_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                new_plot_panel.plot_regions(self.regions_in_work, add_dimension=plot_add_dim, legend=True)
            else:
                self.winfo_toplevel().gui_widgets["PlotPanel"].plot_regions(self.regions_in_work,
                                                                            add_dimension=plot_add_dim, legend=True)

    def _save(self):
        if self.regions_in_work:
            output_dir = filedialog.askdirectory(title="Choose directory for saving",
                                                 initialdir=service.get_service_parameter("DEFAULT_OUTPUT_FOLDER"))
            if output_dir:
                service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)
                for region in self.regions_in_work:
                    name = output_dir + "/" + region.get_info("File Name") + ".dat"
                    try:
                        with open(name, 'w') as f:
                            save_add_dimension = self.plot_use_settings_var.get() and bool(self.plot_add_dim_var.get())
                            region.save_xy(f, add_dimension=save_add_dimension, headers=False)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {name}", exc_info=True)

    def _saveas(self):
        if self.regions_in_work:
            output_dir = service.get_service_parameter("DEFAULT_OUTPUT_FOLDER")
            for region in self.regions_in_work:
                file_path = filedialog.asksaveasfilename(initialdir=output_dir,
                                                         initialfile=region.get_info("File Name") + ".dat",
                                                         title="Save as...",
                                                         filetypes=(("dat files", "*.dat"), ("all files", "*.*")))
                if file_path:
                    try:
                        with open(file_path, 'w') as f:
                            save_add_dimension = self.plot_use_settings_var.get() and bool(self.plot_add_dim_var.get())
                            region.save_xy(f, add_dimension=save_add_dimension, headers=False)
                    except (IOError, OSError):
                        gui_logger.error(f"Couldn't save file {file_path}", exc_info=True)
                output_dir = os.path.dirname(file_path)
            service.set_init_parameters("DEFAULT_OUTPUT_FOLDER", output_dir)


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
        # Dictionary of all widgets of the main window
        self.gui_widgets = {}
        # Attribute keeping track of all regions loaded in the current GUI session
        self.loaded_regions = datahandler.RegionsCollection()

        self.main_menu_bar = tk.Menu(self)
        self.file_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.help_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.generate_main_menu()

        tk.Tk.wm_title(self, "SpecQP")
        self.main_window = MainWindow(self, orient=tk.HORIZONTAL)
        self.main_window.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # TODO: write the functionality for the menu, add new menus if needed.
    def generate_main_menu(self):
        """Configuring the app menu
        """
        # File menu
        self.file_menu.add_command(label="Load SCIENTA Files", command=self.load_file)
        self.file_menu.add_command(label="Load SPECS Files", command=self.load_specs_file)
        self.file_menu.add_command(label="Open pressure calibration", command=self.load_pressure_calibration)
        self.file_menu.add_command(label="Open File as Text", command=self.open_file_as_text)

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
        pass

    def open_file_as_text(self):
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
            gui_logger.warning(f"Couldn't get the file path from the open_file_as_text dialog in Root class")

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
