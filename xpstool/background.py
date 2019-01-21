"""Provides classes and functions for data background processing
"""
import numpy as np
from .region import Region

def calculateShirley(energy, counts, tolerance=1e-5, maxiter=50):
    """Calculates shirley background.
    """
    if energy[0] < energy[-1]:
        is_reversed = True
        energy = energy[::-1]
        counts = counts[::-1]
    else:
        is_reversed = False

    background = np.ones(energy.shape) * counts[-1]
    integral = np.zeros(energy.shape)
    spacing = (energy[-1] - energy[0]) / (len(energy) - 1)

    subtracted = counts - background
    ysum = subtracted.sum() - np.cumsum(subtracted)
    for i in range(len(energy)):
        integral[i] = spacing * (ysum[i] - 0.5
                                 * (subtracted[i] + subtracted[-1]))

    iteration = 0
    while iteration < maxiter:
        subtracted = counts - background
        integral = spacing * (subtracted.sum() - np.cumsum(subtracted))
        bnew = ((counts[0] - counts[-1])
                * integral / integral[0] + counts[-1])
        if np.linalg.norm((bnew - background) / counts[0]) < tolerance:
            background = bnew.copy()
            break
        else:
            background = bnew.copy()
        iteration += 1
    if iteration >= maxiter:
        print("Background calculation failed due to excessive iterations")

    if is_reversed:
        return background[::-1]
    return background
