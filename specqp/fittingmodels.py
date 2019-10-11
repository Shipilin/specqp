import numpy as np
from numpy import arctan, cos, pi
from scipy.special import wofz


class Models:
    def __init__(self):
        pass

    def get_model(self, model, energy, intensity, params):
        return getattr(self, model)(energy, intensity, params)

    @staticmethod
    def doniach(x, amplitude=1.0, center=0, gauss=1.0, lorenz=0.0):
        """Return a Doniach Sunjic asymmetric lineshape, used for photo-emission.
            donaich(x, amplitude, center, gauss, lorenz) =
            amplitude / gauss^(1-lorenz) *
            cos(pi*lorenz/2 + (1-lorenz) arctan((x-center)/gauss) /
            (gauss**2 + (x-center)**2)**[(1-lorenz)/2]
            see http://www.casaxps.com/help_manual/line_shapes.htm
        """
        arg = (x - center) / gauss
        gm1 = (1.0 - lorenz)
        scale = amplitude / (gauss ** gm1)
        return scale * cos(pi * lorenz / 2 + gm1 * arctan(arg)) / (1 + arg ** 2) ** (gm1 / 2)

    @staticmethod
    def constant(energy, intensity, params):
        """Calculates constant background for simulated spectrum
        """
        return np.ones_like(energy) * float(params['value'])

    @staticmethod
    def linear(energy, intensity, params):
        """Calculates linear background for simulated spectrum
        """
        bg = np.zeros_like(energy)
        if energy[0] < energy[-1]:
            need_to_reversed = False
        else:
            need_to_reversed = True
            energy = energy[::-1]
        bg = bg + (energy - energy[0]) * params['value']
        if need_to_reversed:
            return bg[::-1]
        else:
            return bg

    @staticmethod
    def square(energy, intensity, params):
        """Calculates square background for simulated spectrum
        """
        bg = np.zeros_like(energy)
        if energy[0] < energy[-1]:
            need_to_reversed = False
        else:
            need_to_reversed = True
            energy = energy[::-1]
        bg = bg + np.square((energy - energy[0])) * params['value']
        if need_to_reversed:
            return bg[::-1]
        else:
            return bg

    @staticmethod
    def shirley(energy, intensity, params):
        """Calculates Shirley background for simulated spectrum
        """
        bg = np.zeros_like(energy)
        if energy[0] < energy[-1]:
            need_to_reversed = False
        else:
            need_to_reversed = True
            intensity = intensity[::-1]
        bg = bg + (np.cumsum(intensity) - intensity) * params['value']
        if need_to_reversed:
            return bg[::-1]
        else:
            return bg

    @staticmethod
    def voigt(self, energy, intensity, params):
        """Returns the Voigt line shape at x with Lorentzian component FWHM lorenz
        and Gaussian component FWHM gauss.
        """
        x = np.array(energy) - params['center']['value']
        gauss = params['gauss']['value'] / np.sqrt(2 * np.log(2))
        return (params['area']['value'] * np.real(wofz((x + 1j * params['lorenz']['value']) /
                gauss / np.sqrt(2))) / gauss / np.sqrt(2 * np.pi))

    @staticmethod
    def voigt_doublet(energy, intensity, params):
        """Returns the double Voigt line shape at x with Lorentzian component FWHM lorenz
        and Gaussian component FWHM gauss.
        """
        x = np.array(energy) - params['centerMain']['value']
        gauss = params['gaussMain']['value'] / np.sqrt(2 * np.log(2))
        component1 = (params['areaMain']['value'] * np.real(wofz((x + 1j * params['lorenzMain']['value']) / gauss /
                      np.sqrt(2))) / gauss / np.sqrt(2 * np.pi))
        x = np.array(energy) - params['centerMain']['value'] - params['separation']['value']
        gauss = params['gaussMain']['value']*params['gaussSecond']['value']/ np.sqrt(2 * np.log(2))
        component2 = (params['areaMain']['value'] * params['areaRation']['value'] * np.real(wofz((x + 1j *
                      params['lorenzMain']['value']*params['lorenzSecond']['value']) / gauss / np.sqrt(2))) / gauss
                      / np.sqrt(2 * np.pi))
        return component1 + component2
