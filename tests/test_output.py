"""Output readers

The OPER outputs in resources/avl352 are written by AVL 3.52 in its
machine-readable format, the MODE outputs (.sys, .eig) in resources.
"""

import os

import pytest

import avlwrapper as avl

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(THIS_DIR, "resources")
MRF_DIR = os.path.join(RES_DIR, "avl352")


def get_output(file, body_names=None, res_dir=MRF_DIR):
    filename = os.path.join(res_dir, file)
    reader = avl.OutputReader(filename, body_names)
    return reader.get_content()


def test_totals():
    res = get_output("b737.ft")
    assert res["Alpha"] == pytest.approx(1.918401, 1e-6)
    assert res["CDind"] == pytest.approx(0.01052887, 1e-6)
    assert res["elevator"] == pytest.approx(0.8967975, 1e-6)
    assert res["Surfaces"] == 11


def test_surface_forces():
    res = get_output("b737.fn")
    assert res["Wing"]["Area"] == pytest.approx(2 * 531.687, 1e-6)
    assert res["Nacelle"]["CY"] == pytest.approx(0.0, abs=1e-12)


def test_body_forces():
    res = get_output("supra.fb", body_names=["Fuse pod"])
    assert res["Fuse pod"]["Length"] == pytest.approx(67.500, 1e-6)
    assert res["Fuse pod"]["Cm"] == pytest.approx(0.001081043, 1e-6)


def test_empty_body_forces():
    res = get_output("b737.fb", body_names=[])
    assert res == {}


def test_strip_forces():
    res = get_output("b737.fs")
    assert res["Wing"]["Chord"][0] == pytest.approx(20.906362, 1e-6)
    assert res["Wing"]["Chord"][-1] == pytest.approx(3.522282, 1e-6)
    assert res["Fin"]["C.P.x/c"][0] == pytest.approx(0.5210746, 1e-6)
    assert res["Fin"]["C.P.x/c"][-1] == pytest.approx(0.1824546, 1e-6)


def test_element_forces():
    res = get_output("b737.fe")
    assert res["Wing"][1]["X"][0] == pytest.approx(49.695930, 1e-6)
    assert res["Wing"][1]["X"][-1] == pytest.approx(70.171907, 1e-6)
    assert res["Nacelle"][137]["dCp"][0] == pytest.approx(0.6192103, 1e-6)
    assert res["Nacelle"][137]["dCp"][-1] == pytest.approx(-0.1730701, 1e-6)


def test_stability_derivatives():
    res = get_output("b737.st")
    assert res["CLa"] == pytest.approx(7.299206, 1e-6)
    assert res["Cnr"] == pytest.approx(-0.4885038, 1e-6)
    assert res["Cm_elevator"] == pytest.approx(-0.07159010, 1e-6)
    assert res["Xnp"] == pytest.approx(68.108783, 1e-6)


def test_body_axis_derivatives():
    res = get_output("b737.sb")
    assert res["CYv"] == pytest.approx(-1.319243, 1e-6)
    assert res["Cm_slat"] == pytest.approx(-0.001073507, 1e-6)


def test_hinge_moments():
    res = get_output("b737.hm")
    assert res["slat"] == pytest.approx(-0.5992505e-02, 1e-6)
    assert res["elevator"] == pytest.approx(-0.4889555e-03, 1e-6)


def test_shear_forces():
    res = get_output("b737.vm")
    assert res["Wing"]["Vz/(q*Sref)"][0] == pytest.approx(0.2208966, 1e-6)
    assert res["Wing"]["Vz/(q*Sref)"][-1] == pytest.approx(0.0, abs=1e-12)
    assert res["Nacelle"]["Mx/(q*Bref*Sref)"][0] == pytest.approx(0.2315755e-02, 1e-6)
    assert res["Nacelle"]["Mx/(q*Bref*Sref)"][-1] == pytest.approx(0.0, abs=1e-12)


def test_system_matrix():
    res = get_output("b737.sys", res_dir=RES_DIR)
    assert res["u"][0] == pytest.approx(-0.0001, 1e-6)
    assert res["psi"][9] == pytest.approx(249.8599, 1e-6)
    assert res["rudder"][-1] == pytest.approx(0.000, 1e-6)


def test_eigen_values():
    res = get_output("b737.eig", res_dir=RES_DIR)
    assert res[1][0] == pytest.approx((-0.29018355, 1.9011338), 1e-6)
    assert res[1][-1] == pytest.approx((-0.98895929e-03, -0.51790625e-01), 1e-6)


def test_regular_format_rejected(tmp_path):
    # regular (formatted) output, as written without the MRF command
    file_path = tmp_path / "regular.ft"
    file_path.write_text(
        " Vortex Lattice Output -- Total Forces\n"
        "  Alpha =   1.91840     pb/2V =  -0.00000\n"
    )
    with pytest.raises(avl.OutputError, match="machine-readable"):
        avl.OutputReader(str(file_path)).get_content()
