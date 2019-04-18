import os
import tkinter as tk
import tkinter.tix as tix
from tkinter import ttk
from tkinter import filedialog
import ntpath
import logging

import matplotlib
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
import matplotlib.image as mpimg

from service import set_default_data_folder
from service import get_default_data_folder
from plotter import SpecqpPlot
from datahandler import SpectraCollection

# Default font for the GUI
LARGE_FONT = ("Verdana", "12")

gui_logger = logging.getLogger("specqp.gui")  # Configuring child logger
matplotlib.use('TkAgg')  # Configuring matplotlib interaction with tkinter
style.use('ggplot')  # Configuring matplotlib style

logo_img_file = "assets/specqp_icon.png"
test_file = "../tests/scienta_single_region_1.txt"


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
        except IOError:
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
        """Creates a check list with loaded file names as sections and corresponding spectra IDs as checkable items
        :param default_items: dictionary {"file_name1": ("ID1, ID2,..."), "file_name2": ("ID1", "ID2", ...)}
        :param args:
        :param kwargs:
        """
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["BrowserTreeView"] = self

        self.check_list_items = []
        if default_items:
            self.add_items_to_check_list(default_items.keys(), default_items.items())

    def get_checked_items(self):
        values = []
        for item in self.check_list_items:
            value = item.get()
            if value:
                values.append(value)
        return values

    def add_items_to_check_list(self, section_name, items):
        """A call to the function dinamically adds a section with loaded spectra IDs to the checkbox list
        :param section_name: the name of the file that was loaded
        :param items: the IDs of spectra loaded from the file
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
        self.add_file_button = ttk.Button(self.buttons_panel, text='Load File', command=self._ask_load_file)
        self.add_file_button.pack(side=tk.TOP, fill=tk.X)
        self.app_quit_button = ttk.Button(self.buttons_panel, text='Quit', command=self._quit)
        self.app_quit_button.pack(side=tk.TOP, fill=tk.X)
        self.buttons_panel.pack(side=tk.TOP, fill=tk.X, expand=False)

        # Files tree panel
        self.spectra_tree_panel = BrowserTreeView(self, borderwidth=1, relief="groove")
        self.spectra_tree_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _ask_load_file(self):
        file_path, loaded_IDs = self.winfo_toplevel().load_file()
        if file_path and loaded_IDs:
            self.spectra_tree_panel.add_items_to_check_list(os.path.basename(file_path), loaded_IDs)
        else:
            gui_logger.debug("Something went wrong when loading spectra by clicking the button in BrowserPanel")

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

        self.canvas = FigureCanvasTkAgg(figure, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.draw()

        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X, expand=False)
        self.toolbar.update()

        self.canvas.mpl_connect("key_press_event", self._on_key_press)

    def _on_key_press(self, event):
        gui_logger.info(f"{event.key} pressed on plot canvas")
        key_press_handler(event, self.canvas, self.toolbar)


class CorrectionsPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.winfo_toplevel().gui_widgets["CorrectionsPanel"] = self
        # Action buttons panel
        self.buttons_panel = ttk.Frame(self, borderwidth=1, relief="groove")
        # Action buttons
        self.plot_checked_button = ttk.Button(self.buttons_panel, text='Plot Checked', command=self._plot_checked)
        self.plot_checked_button.pack(side=tk.TOP, fill=tk.X)
        self.buttons_panel.pack(side=tk.TOP, fill=tk.X, expand=False)

        # Corrections tree panel
#       self.corrections_tree_panel = BrowserTreeView(self, borderwidth=1, relief="groove")
#       self.corrections_tree_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _plot_checked(self):
        if "BrowserTreeView" in self.winfo_toplevel().gui_widgets:
            # TODO: write functionality for "Plot checked" button
            print(self.winfo_toplevel().gui_widgets["BrowserTreeView"].get_checked_items())
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
        # Attribute keeping track of all spectra loaded in the current GUI session
        self.loaded_spectra = SpectraCollection()

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
        self.file_menu.add_command(label="Load File", command=self.load_file)
        self.file_menu.add_command(label="Open File as Text", command=self.open_file_as_text)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Quit", command=self.quit)
        self.main_menu_bar.add_cascade(label="File", menu=self.file_menu)

        # Help menu
        self.help_menu.add_command(label="About", command=self.show_about)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Help...", command=self.show_help)
        self.main_menu_bar.add_cascade(label="Help", menu=self.help_menu)

        self.config(menu=self.main_menu_bar)

    def open_file_as_text(self):
        """Open the read-only view of a text file in a Toplevel widget
        """
        file_path = filedialog.askopenfilename(parent=self, initialdir=get_default_data_folder())
        if file_path:
            # If the user open a file, remember the file folder to use it next time when the open request is received
            set_default_data_folder(os.path.dirname(file_path))

            text_view = tk.Toplevel(self)
            self.toplevel_windows.append(text_view)
            text_view.wm_title(ntpath.basename(file_path))
            text_panel = FileViewerWindow(text_view, file_path)
            text_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def load_file(self):
        file_path = filedialog.askopenfilename(parent=self, initialdir=get_default_data_folder())
        if file_path:
            # If the user open a file, remember the file folder to use it next time when the open request is received
            set_default_data_folder(os.path.dirname(file_path))
            # TODO: exchange dummy code with the proper one
            #loaded_IDs = self.loaded_spectra.add_spectra_from_file(file_path)
            loaded_IDs = [1, 2, 3]
            return file_path, loaded_IDs
        else:
            gui_logger.debug(f"Couldn't get the file path from the load_file function in Root class")

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
