import os

import pytest

import avlwrapper as avl


THIS_DIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(THIS_DIR, 'resources')

# OUTPUTS = {
#     "Totals": "ft",
#     "SurfaceForces": "fn",
#     "StripForces": "fs",
#     "ElementForces": "fe",
#     "StabilityDerivatives": "st",
#     "BodyAxisDerivatives": "sb",
#     "HingeMoments": "hm",
#     "StripShearMoments": "vm",
# }


def get_output(file):
    filename = os.path.join(RES_DIR, file)
    reader = avl.OutputReader(filename)
    return reader.get_content()


def test_totals():
    res = get_output('b737.ft')
    assert res['Alpha'] == pytest.approx(1.91840, 1e-6)
    assert res['CDind'] == pytest.approx(0.0105289, 1e-6)


def test_surface_forces():
    res = get_output('b737.fn')
    assert res['Wing']['Area'] == pytest.approx(2*531.687, 1e-6)
    assert res['Nacelle']['CY'] == pytest.approx(0.0, 1e-6)


def test_strip_forces():
    res = get_output('b737.fs')
    assert res['Wing']['Chord'][0] == pytest.approx(20.9064, 1e-6)
    assert res['Wing']['Chord'][-1] == pytest.approx(3.5223, 1e-6)
    assert res['Fin']['C.P.x/c'][0] == pytest.approx(1.228, 1e-6)
    assert res['Fin']['C.P.x/c'][-1] == pytest.approx(1.176, 1e-6)


def test_element_forces():
    res = get_output('b737.fe')
    assert res['Wing'][1]['X'][0] == pytest.approx(49.69593, 1e-6)
    assert res['Wing'][1]['X'][-1] == pytest.approx(70.17191, 1e-6)
    assert res['Nacelle'][137]['dCp'][0] == pytest.approx(0.61921, 1e-6)
    assert res['Nacelle'][137]['dCp'][-1] == pytest.approx(-0.17307, 1e-6)


def test_stability_derivatives():
    res = get_output('b737.st')
    assert res['CLa'] == pytest.approx(7.299206, 1e-6)
    assert res['Cnr'] == pytest.approx(-0.491477, 1e-6)


def test_body_axis_derivatives():
    res = get_output('b737.sb')
    assert res['CYv'] == pytest.approx(-1.326015, 1e-6)
    assert res['Cm_slat'] == pytest.approx(-0.001052, 1e-6)


def test_hinge_moments():
    res = get_output('b737.hm')
    assert res['slat'] == pytest.approx(-0.5993E-02, 1e-6)
    assert res['elevator'] == pytest.approx(-0.4890E-03, 1e-6)


def test_shear_forces():
    res = get_output('b737.vm')
    assert res['Wing']['Vz/(q*Sref)'][0] == pytest.approx(0.221016, 1e-6)
    assert res['Wing']['Vz/(q*Sref)'][-1] == pytest.approx(0.00000, 1e-6)
    assert res['Nacelle']['Mx/(q*Bref*Sref)'][0] == pytest.approx(0.231575E-02, 1e-6)
    assert res['Nacelle']['Mx/(q*Bref*Sref)'][-1] == pytest.approx(0.00000, 1e-6)


def test_get_vars_output_scientific_format():
    res = get_output('aircraft-1.scientific.sb')
    assert res['CXu'] == pytest.approx(-0.002741, abs=1e-6)


def test_get_vars_decimal_format():
    res = get_output('aircraft-1.sb')
    assert res['CXu'] == pytest.approx(-0.27412958E-02, abs=1e-6)
