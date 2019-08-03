import sys
sys.path.append('../')
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
        self.assertTrue(0)


if __name__ == '__main__':
    unittest.main()
