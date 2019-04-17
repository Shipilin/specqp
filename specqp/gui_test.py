import os
import tkinter as tk
from tkinter import ttk
import warnings

import matplotlib
matplotlib.use('TkAgg')
# import matplotlib.animation as animation
from matplotlib import style
style.use('ggplot')


class PlotWindow(tk.Frame):
    def __init__(self, master, window_ID):
        super().__init__(master=master)
        self.windowID = window_ID
        print(self.windowID)

class MainWindow(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master=master)
        self.windowID = 0 # Main window ID is always 0
        self.childrenIDs = [] # List of children windows
        self.frames = {}
        frame = StartPage(container, self)
        self.frames[StartPage] = frame
        frame.grid(row=0, column=0, sticky="nsew")
        self._init_window()

    def _init_window(self):
        self.master.title("XPS tool v1.1.0")
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        button = tk.Button(master=self, text='Quit', command=self._quit)
        button.pack(side=tk.RIGHT)
        button = tk.Button(master=self,
                           text='Plot',
                           command=lambda:self._plot(plot_window_title="Plot"))
        button.pack(side=tk.LEFT)
        # Menu
        menu = tk.Menu(self.master)
        self.master.config(menu=menu)
        file = tk.Menu(menu)
        file.add_command(label="Save", command=self._save)
        file.add_separator()
        file.add_command(label="Exit", command=self._quit)
        menu.add_cascade(label="File", menu=file)
        edit = tk.Menu(menu)
        edit.add_command(label="Undo")
        menu.add_cascade(label="Edit", menu=edit)

    def _plot(self, plot_window_title):
        self.newWindow = tk.Toplevel(master=self.master)
        self.app = PlotWindow(self.newWindow, 1)
        self.app.master.title(plot_window_title)

    # def _plotFigure(self):
    #     pltWin = PlotWindow(master=self, window_name="Plottttt")
    #
    #     f = Figure(figsize=(5, 4), dpi=100)
    #     a = f.add_subplot(111)
    #     t = arange(0.0, 3.0, 0.01)
    #     s = sin(2*pi*t)
    #     a.plot(t, s)
    #
    #     # tk.DrawingArea
    #     canvas = FigureCanvasTkAgg(f, master=pltWin)
    #     canvas.show()
    #     canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    #
    #     toolbar = NavigationToolbar2TkAgg(canvas, pltWin)
    #     toolbar.update()
    #     canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    #
    #     def on_key_event(event):
    #         print('you pressed %s' % event.key)
    #         key_press_handler(event, canvas, toolbar)
    #     canvas.mpl_connect('key_press_event', on_key_event)

    def _save(self):
        pass

    def _quit(self):
        self.master.quit()     # stops mainloop
        self.master.destroy()  # this is necessary on Windows to prevent
                        # Fatal Python Error: PyEval_RestoreThread: NULL tstate
