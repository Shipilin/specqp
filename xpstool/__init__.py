from .datahandler import Experiment, Spectrum, AddDimensionSpectrum, Region
from .fitter import Fitter
__appname__ = "XPS tool"
__version__ = "1.0.2"
__authors__ = ["Mikhail Shipilin <mikhail.shipilin@gmail.com>"]
__website__ = "https://github.com/Shipilin/xps-tool"

__all__ = [
        'datahandler',
        'helpers',
        'fitter'
        ]
