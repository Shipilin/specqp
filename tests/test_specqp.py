from matplotlib import pyplot as plt
import unittest
import specqp as sp
import numpy as np


class TestHelpers(unittest.TestCase):
    def test_is_iterable(self):
        self.assertTrue(sp.helpers.is_iterable([1, 2, 3]))
        self.assertTrue(sp.helpers.is_iterable((1, 2, 3)))
        arr = np.ndarray(range(10))
        self.assertTrue(sp.helpers.is_iterable(arr))
        self.assertTrue(sp.helpers.is_iterable((1, 2, 3)))
        self.assertFalse(sp.helpers.is_iterable(1))
        self.assertTrue(1)


def doniachtest():
    x = np.linspace(714.96, 702.16, 61, endpoint=True)
    amp, cen, gfwhm, lfwhm, reverse = 6.34, 709.0, 2, 0.91, None
    y = sp.fitter.Fitter.doniach_sunjic(x[::-1], amp, cen, gfwhm, lfwhm)
    y2 = np.ones_like(x)
    plt.plot(x[::-1], y, x, y2)
    plt.gca().invert_xaxis()
    plt.show()


def shirleytest():
    x = np.linspace(714.96, 702.16, 61, endpoint=True)
    y = [ 4.09974404e+00,  4.08549832e+00,  4.11214206e+00,  4.28109103e+00,
          4.33858583e+00,  4.30001600e+00,  4.39268917e+00,  4.42246841e+00,
          4.47486802e+00,  4.64455287e+00,  4.62125260e+00,  4.69875220e+00,
          4.84191329e+00,  4.87371621e+00,  4.98736202e+00,  5.07505199e+00,
          5.19087346e+00,  5.30921453e+00,  5.49130539e+00,  5.51066229e+00,
          5.74675252e+00,  5.84502480e+00,  5.98661014e+00,  6.08369061e+00,
          6.02580387e+00,  6.03721805e+00,  6.05379939e+00,  6.03497040e+00,
          6.07546793e+00,  6.10429531e+00,  6.10463926e+00,  6.24841625e+00,
          6.28337866e+00,  6.44102544e+00,  6.63068309e+00,  6.93672212e+00,
          7.44953607e+00,  8.41378979e+00,  9.26994881e+00,  9.90373540e+00,
          1.11497680e+01,  1.30781155e+01,  1.41555031e+01,  1.05690210e+01,
          4.93501040e+00,  2.07736362e+00,  1.04520877e+00,  6.44288914e-01,
          4.23492241e-01,  2.90737482e-01,  2.09998400e-01,  1.35570309e-01,
          7.20444729e-02,  4.51847704e-02,  2.30283155e-02,  1.71252600e-02,
         -5.35914254e-03, -4.77763558e-02, -4.07294833e-02, -6.35178371e-02,
         -7.82834746e-02]
    sh = sp.fitter.Fitter.shirley(x, y, 0.01, tolerance=1e-5, maxiter=10, asymmetry=None)
    plt.plot(x, y, x, sh)
    plt.gca().invert_xaxis()
    plt.show()

shirleytest()


# if __name__ == '__main__':
#     unittest.main()
