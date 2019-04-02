import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import warnings

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.animation as animation
from matplotlib import style
style.use('ggplot')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
# implement the default mpl key bindings
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure

LARGE_FONT = ("Verdana", "12")
# SCIENTA file path for testing
test_file = os.path.abspath("/".join([os.path.dirname(__file__), "../", "tests/tmp/0091.txt"]))

def _configure_frame_grid(frame, kwargs):
    """Service function to set the grid dimensions for frames in the app.
    Custom kwargs are: {"nrows": int}, {"rweights": (1,2,3,...)}
                       {"ncolumns": int}, {"cweights": (1,2,3,...)}
    """
    if ("nrows" in kwargs) and ("rweights" in kwargs):
        ### Check that integer number of rows and columns was sent
        assert (type(kwargs["nrows"]) == int and type(kwargs["ncolumns"]) == int), \
        f"{_configure_frame_grid.__name__}: wrong type of argument."
        ###
        for i in range(kwargs["nrows"]):
            frame.grid_rowconfigure(i, weight=kwargs["rweights"][i])
    else:
        warnings.warn(f"Grid rows were not specified for the frame {frame.__name__}")
    if ("ncolumns" in kwargs) and ("cweights" in kwargs):
        ### Check that every row and column has the corresponding weight
        assert (len(kwargs["rweights"]) == kwargs["nrows"] \
        and len(kwargs["cweights"]) == kwargs["ncolumns"]), \
        f"{_configure_frame_grid.__name__}: wrong number of weights."
        ###
        for i in range(kwargs["ncolumns"]):
            frame.grid_columnconfigure(i, weight=kwargs["cweights"][i])
    else:
        warnings.warn(f"Grid columns were not specified for the frame {frame.__name__}")

# f = Figure(figsize=(5,5), dpi=100)
# a = f.add_subplot(111)
#
# def animate(i):
#     pullData = open("tmp/sampleText.txt","r").read()
#     dataList = pullData.split('\n')
#     xList = []
#     yList = []
#     for eachLine in dataList:
#         if len(eachLine) > 1:
#             x, y = eachLine.split(',')
#             xList.append(int(x))
#             yList.append(int(y))
#
#     a.clear()
#     a.plot(xList, yList)

class CustomText(tk.Text):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

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
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
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

class FileHandlerPanel(ttk.Frame):
    """Frame containing open/save widgets and relative functionality to handle
    the files
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

class AppliedCorrectionPanel(ttk.Frame):
    """Frame containing functionality for data treatment by the user
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        plot_button = ttk.Button(self, text='Plot', command= lambda: print("Plot"))
        plot_button.pack(side=tk.TOP)

class FileViewPanel(ttk.Frame):
    """Frame with a text widget for displaying the data files
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.text = CustomText(self,
                                highlightthickness=0,
                                font=LARGE_FONT,
                                background="lightgrey",
                                borderwidth=0)
        self.vsb = tk.Scrollbar(self,
                                highlightthickness=0,
                                borderwidth=0,
                                orient=tk.VERTICAL,
                                command=self.text.yview)
        self.text.configure(yscrollcommand=self.vsb.set)
        self.linenumbers = TextLineNumbers(self,
                                            highlightthickness=0,
                                            borderwidth=0,
                                            background="lightgrey",
                                            width=30)
        self.linenumbers.attach(self.text)

        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.linenumbers.pack(side=tk.LEFT, fill=tk.Y)
        self.text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

        file = open(test_file, "r")
        self.text.insert(0.0, file.read())
        file.close()
        self.text.config(state=tk.DISABLED)

    def _on_change(self, event):
        self.linenumbers.redraw()

class ServicePanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.file_handler_container = FileHandlerPanel(self)
        self.file_handler_container.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        self.file_path = tk.StringVar(self, value=os.getcwd())
        self.file_path_entry = ttk.Entry(self.file_handler_container,
                                    textvariable=self.file_path,
                                    font=LARGE_FONT)
        self.file_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.file_open_button = ttk.Button(self.file_handler_container,
                                        text='Open',
                                        command=lambda: self._askOpenFile(self.file_path.get()))
        self.file_open_button.pack(side=tk.RIGHT)

        self.buttons_container = ttk.Frame(self)
        self.buttons_container.pack(side=tk.TOP, fill=tk.X, expand=False)
        self.app_quit_button = ttk.Button(self.buttons_container,
                                        text='Quit',
                                        command=self.master._quit)
        self.app_quit_button.pack(side=tk.BOTTOM)

    def _askOpenFile(self, dir):
        self.file_path = filedialog.askopenfilename(parent=self, initialdir=dir)
        self.update()

class WorkingPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        applied_corrections_container = AppliedCorrectionPanel(self,
                                                                borderwidth=1,
                                                                relief="groove")
        applied_corrections_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        file_view_container = FileViewPanel(self, borderwidth=1, relief="groove")
        file_view_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

class MainWindow(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        work_panel_container = WorkingPanel(self, borderwidth=1, relief="groove")
        work_panel_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        service_panel_container = ServicePanel(self, borderwidth=1, relief="groove")
        service_panel_container.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False)

    def _quit(self):
        self.master.quit()     # stops mainloop
        self.master.destroy()  # this is necessary on Windows to prevent
                            # Fatal Python Error: PyEval_RestoreThread: NULL tstate

class Root(tk.Tk):
    """Main application class
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #grid = {"nrows": 1, "ncolumns": 1, "rweights": (1,), "cweights": (1,)}
        #_configure_frame_grid(self, grid)
        tk.Tk.wm_title(self, "SpecQP")
        main_container = MainWindow(self)
        main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        #main_container.grid(column=0, row=0, sticky = "nsew")

def main():
    app = Root()
    app.update() #Update to be able to request main window parameters
    #ani = animation.FuncAnimation(f, animate, interval=1000)
    app.minsize(app.winfo_width(), app.winfo_height())
    app.resizable(1, 1)
    app.mainloop()

if __name__ == '__main__':
    main()
