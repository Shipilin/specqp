import tkinter as tk
from tkinter import ttk
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

LARGE_FONT= ("Verdana", 12)

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

class AppliedCorrectionPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

class FileViewPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

class InfoPanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        grid = {"nrows": 1, "ncolumns": 3, "rweights": (1,), "cweights": (5, 1, 1)}
        _configure_frame_grid(self, grid)



        label = ttk.Label(self, text="This is info panel", font=LARGE_FONT)
        label.grid(row=0, column=0, sticky="s")
        plot_button = ttk.Button(master=self, text='Plot', command= lambda: print("Plot"))
        plot_button.grid(row=0, column=1, sticky="se")
        app_quit_button = ttk.Button(master=self, text='Quit', command=self.master._quit)
        app_quit_button.grid(row=0, column=2, sticky="sw")

class AdministrativePanel(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        grid = {"nrows": 1, "ncolumns": 2, "rweights": (1,), "cweights": (1,3)}
        _configure_frame_grid(self, grid)

        file_view_container = FileViewPanel(self, borderwidth=1, relief="groove")
        file_view_container.grid(row=0, column=0, sticky="nsew")
        applied_corrections_container = AppliedCorrectionPanel(self,
                                                                borderwidth=1,
                                                                relief="groove")
        applied_corrections_container.grid(row=0, column=1, sticky="nsew")

class MainWindow(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        grid = {"nrows": 2, "ncolumns": 1, "rweights": (5, 1), "cweights": (1,)}
        _configure_frame_grid(self, grid)

        adminisrative_container = AdministrativePanel(self, borderwidth=1, relief="groove")
        adminisrative_container.grid(row=0, column=0, sticky="nsew")
        info_container = InfoPanel(self, borderwidth=1, relief="groove")
        info_container.grid(row=1, column=0, sticky="nsew")

    def _quit(self):
        self.master.quit()     # stops mainloop
        self.master.destroy()  # this is necessary on Windows to prevent
                            # Fatal Python Error: PyEval_RestoreThread: NULL tstate

class Root(tk.Tk):
    """Main application class
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grid = {"nrows": 1, "ncolumns": 1, "rweights": (1,), "cweights": (1,)}
        _configure_frame_grid(self, grid)

        tk.Tk.wm_title(self, "XPS tool")
        main_container = MainWindow(self)
        main_container.grid(column=0, row=0, sticky = "nsew")

def main():
    app = Root()
    #ani = animation.FuncAnimation(f, animate, interval=1000)
    screen_width = app.winfo_screenwidth()
    screen_height = app.winfo_screenheight()
    app.geometry(f"{screen_width//2}x{screen_height//2}+{screen_width//4}+{screen_height//4}")
    app.mainloop()

if __name__ == '__main__':
    main()
