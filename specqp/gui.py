import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import ntpath
import logging

import matplotlib
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
import matplotlib.image as mpimg

import service
import datahandler
from plotter import SpecqpPlot

# Default font for the GUI
LARGE_FONT = ("Verdana", "12")

gui_logger = logging.getLogger("specqp.gui")  # Creating child logger
matplotlib.use('TkAgg')  # Configuring matplotlib interaction with tkinter
style.use('ggplot')  # Configuring matplotlib style

logo_img_file = "assets/specqp_icon.png"


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

        self.check_list_items = []
        if default_items:
            for key, val in default_items.items():
                self.add_items_to_check_list(key, val)

    def get_checked_items(self):
        values = []
        for item in self.check_list_items:
            value = item.get()
            if value:
                values.append(value)
        return values

    def add_items_to_check_list(self, section_name, items):
        """A call to the function dinamically adds a section with loaded regions IDs to the checkbox list
        :param section_name: the name of the file that was loaded
        :param items: the IDs of regions loaded from the file
        :return: None
        """
        file_name_label = tk.Label(self, text=section_name, anchor=tk.W)
        file_name_label.pack(side=tk.TOP, fill=tk.X)
        for item in items:
            var = tk.StringVar(value=item)
            self.check_list_items.append(var)
            cb = tk.Checkbutton(self, var=var, text=item,
                                onvalue=item, offvalue="",
                                anchor=tk.W, relief=tk.FLAT, highlightthickness=0
                                )
            cb.pack(side=tk.TOP, fill=tk.X, anchor=tk.W)


class BrowserPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["BrowserPanel"] = self

        # Action buttons panel
        self.buttons_panel = ttk.Frame(self, borderwidth=1, relief="groove")
        # Action buttons
        self.load_label = ttk.Label(self.buttons_panel, text="Load File", anchor=tk.W)
        self.load_label.pack(side=tk.TOP, fill=tk.X)
        self.add_sc_file_button = ttk.Button(self.buttons_panel, text='Load SCIENTA', command=self._ask_load_scienta_file)
        self.add_sc_file_button.pack(side=tk.TOP, fill=tk.X)
        self.add_sp_file_button = ttk.Button(self.buttons_panel, text='Load SPECS', command=self._ask_load_specs_file)
        self.add_sp_file_button.pack(side=tk.TOP, fill=tk.X)
        self.blank_label = ttk.Label(self.buttons_panel, text="", anchor=tk.W)
        self.blank_label.pack(side=tk.TOP, fill=tk.X)
        self.app_quit_button = ttk.Button(self.buttons_panel, text='Quit', command=self._quit)
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


class PlotPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["PlotPanel"] = self

        self.start_page_img = mpimg.imread(logo_img_file)

        self.figure = SpecqpPlot(dpi=100)
        self.figure_axes = self.figure.add_subplot(111)
        self.figure_axes.set_axis_off()
        self.figure_axes.imshow(self.start_page_img)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.draw()

        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.toolbar.update()

        self.canvas.mpl_connect("key_press_event", self._on_key_press)
        # self.canvas.mpl_connect("button_press_event", self._on_mouse_click)

    def _on_key_press(self, event):
        gui_logger.info(f"{event.key} pressed on plot canvas")
        key_press_handler(event, self.canvas, self.toolbar)

    # def _on_mouse_click(self, event):
    #     gui_logger.info(f"{event.button} pressed on plot canvas")
    #     key_press_handler(event, self.canvas, self.toolbar)


class CorrectionsPanel(ttk.Frame):  # TODO: add a slider for y-offseted plotting
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["CorrectionsPanel"] = self
        # Action buttons panel
        self.buttons_panel = ttk.Frame(self, borderwidth=1, relief="groove")
        # Action buttons
        self.plot_checked_button = ttk.Button(self.buttons_panel, text='Plot Checked', command=self._plot_checked)
        self.plot_checked_button.pack(side=tk.TOP, fill=tk.X)
        self.buttons_panel.pack(side=tk.TOP, fill=tk.X, expand=False)

        # TODO: add tree view of corrections
        # Corrections tree panel
#       self.corrections_tree_panel = BrowserTreeView(self, borderwidth=1, relief="groove")
#       self.corrections_tree_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _plot_checked(self):
        if "BrowserTreeView" in self.winfo_toplevel().gui_widgets:
            spectra_for_plotting = self.winfo_toplevel().gui_widgets["BrowserTreeView"].get_checked_items()
            if spectra_for_plotting:
                self.winfo_toplevel().gui_widgets["PlotPanel"].figure_axes.clear()
                for spectrum_ID in spectra_for_plotting:
                    # TODO: write proper plotting routine
                    # helpers.plotRegion(self.winfo_toplevel().loaded_regions.get_by_ID(spectrum_ID),
                    #                    figure=self.winfo_toplevel().gui_widgets["PlotPanel"].figure,
                    #                    )
                    self.winfo_toplevel().gui_widgets["PlotPanel"].figure_axes.plot([1, 2, 3], [1, 2, 3])
                    self.winfo_toplevel().gui_widgets["PlotPanel"].figure_axes.plot([3, 2, 1], [1, 2, 3])
                self.winfo_toplevel().gui_widgets["PlotPanel"].canvas.draw()
        else:
            gui_logger.debug("CorrectionPanel tries to access BrowserTreeView with no success")


class MainWindow(ttk.PanedWindow):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["MainWindow"] = self
        self.browser_panel = BrowserPanel(self, borderwidth=1, relief="groove")
        self.add(self.browser_panel)
        self.corrections_panel = CorrectionsPanel(self, borderwidth=1, relief="groove")
        self.add(self.corrections_panel)
        self.plot_panel = PlotPanel(self, borderwidth=1, relief="groove")
        self.add(self.plot_panel)


class Root(tk.Tk):
    """Main GUI application class
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dictionary of all widgets of the main window
        self.gui_widgets = {}
        # List of toplevel objects of the app (not including MainWindow and its children)
        self.toplevel_windows = []
        # Attribute keeping track of all regions loaded in the current GUI session
        self.loaded_regions = datahandler.RegionsCollection()

        self.main_menu_bar = tk.Menu(self)
        self.file_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.help_menu = tk.Menu(self.main_menu_bar, tearoff=0)
        self.generate_main_menu()

        tk.Tk.wm_title(self, "SpecQP")
        self.main_window = MainWindow(self, orient=tk.HORIZONTAL)
        self.main_window.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def generate_main_menu(self):  # TODO: write the functionality for the menu, add new menus if needed.
        """Configuring the app menu
        """
        # File menu
        self.file_menu.add_command(label="Load SCIENTA File", command=self.load_file)
        self.file_menu.add_command(label="Load SPECS File", command=self.load_specs_file)
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

    def open_file_as_text(self):
        """Open the read-only view of a text file in a Toplevel widget
        """
        file_path = filedialog.askopenfilename(parent=self, initialdir=service.service_vars["DEFAULT_DATA_FOLDER"])
        if file_path:
            # If the user open a file, remember the file folder to use it next time when the open request is received
            service.set_default_data_folder(os.path.dirname(file_path))

            text_view = tk.Toplevel(self)
            self.toplevel_windows.append(text_view)
            text_view.wm_title(ntpath.basename(file_path))
            text_panel = FileViewerWindow(text_view, file_path)
            text_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        else:
            gui_logger.debug(f"Couldn't get the file path from the open_file_as_text dialog in Root class")

    def load_specs_file(self):
        self.load_file(file_type=datahandler.DATA_FILE_TYPES[1])

    def load_file(self, file_type=datahandler.DATA_FILE_TYPES[0]):
        # TODO: add multiple files handling
        # {"file_path": (ID1, ID2,...), ...}
        file_path = filedialog.askopenfilename(parent=self, initialdir=service.service_vars["DEFAULT_DATA_FOLDER"])
        loaded_ids = None
        if file_path:
            # If the user opens a file, remember the file folder to use it next time when the open request is received
            service.set_default_data_folder(os.path.dirname(file_path))
            loaded_ids = self.loaded_regions.add_regions_from_file(file_path, file_type)
        else:
            gui_logger.debug(f"Couldn't get the file path from the load_file dialog in Root class")

        assert loaded_ids, "Loading regions crashed. Loaded_IDs variable is empty"
        if loaded_ids:
            self.gui_widgets["BrowserPanel"].spectra_tree_panel.add_items_to_check_list(os.path.basename(file_path),
                                                                                        loaded_ids)
        else:
            gui_logger.warning(f"The file {file_path} provided 0 regions. Possible reason: it is empty or broken.")

    def export_log(self):
        pass

    def show_about(self):
        print("About")

    def show_help(self):
        print("Help")


def main():
    app = Root()
    app.update()  # Update to be able to request main window parameters
    app.minsize(app.winfo_width(), app.winfo_height())
    app.resizable(1, 1)
    app.mainloop()
