import os

import unittest
import pytest

import avlwrapper as avl


THIS_DIR = os.path.dirname(os.path.realpath(__file__))


class TestBodyFileReader(unittest.TestCase):
    def test_get_vars_output_scientific_format(self):
        fname = os.path.join(THIS_DIR, 'resources/aircraft-1.sb')
        reader = avl.output.BodyFileReader(fname)
        res = reader.parse()
        assert res
        assert res['CXu'] == pytest.approx(-0.002741, abs=1e-6)

    def test_get_vars_decimal_format(self):
        fname = os.path.join(THIS_DIR, 'resources/aircraft-1.scientific.sb')
        reader = avl.output.BodyFileReader(fname)
        res = reader.parse()
        assert res
        assert res['CXu'] == pytest.approx(-0.27412958E-02, abs=1e-8)
