import json
import math
import os

import pytest

import avlwrapper as avl

CDIR = os.path.dirname(os.path.realpath(__file__))
AVL_FILE = os.path.join(CDIR, "resources", "b737.avl")


@pytest.fixture()
def results():
    cruise = avl.CaseResults(
        {
            "Name": "cruise",
            "Totals": {"CLtot": 0.5, "CDtot": 0.02},
            "States": {"alpha": 2.0},
        }
    )
    climb = avl.CaseResults({"Name": "climb", "Totals": {"CLtot": 0.8}})
    return avl.Results({1: cruise, 2: climb})


def test_access(results):
    assert results[1].totals["CLtot"] == 0.5
    assert results[1]["Totals"]["CLtot"] == 0.5
    assert results[1].name == "cruise"
    assert results[1].states == {"alpha": 2.0}
    assert list(results) == [1, 2]


def test_missing_output(results):
    with pytest.raises(AttributeError, match="Output.STRIP_FORCES"):
        results[1].strip_forces
    assert not hasattr(results[1], "strip_forces")


def test_read_only(results):
    with pytest.raises(TypeError):
        results[1]["Totals"] = {}


def test_by_name(results):
    assert results.by_name("climb").totals["CLtot"] == 0.8
    with pytest.raises(KeyError, match="descent"):
        results.by_name("descent")


def test_to_dict(results):
    data = results.to_dict()
    assert data == {
        1: {
            "Name": "cruise",
            "Totals": {"CLtot": 0.5, "CDtot": 0.02},
            "States": {"alpha": 2.0},
        },
        2: {"Name": "climb", "Totals": {"CLtot": 0.8}},
    }
    json.dumps(data)


@pytest.fixture()
def mode():
    return avl.EigenMode({"eigenvalue": complex(-0.5, 2.0), "phi": complex(0.1, -0.2)})


def test_eigenmode(mode):
    assert mode.vector == {"phi": complex(0.1, -0.2)}
    assert mode.natural_frequency == pytest.approx(math.sqrt(4.25))
    assert mode.damped_frequency == pytest.approx(2.0)
    assert mode.damping_ratio == pytest.approx(0.5 / math.sqrt(4.25))
    assert mode.period == pytest.approx(math.pi)
    assert mode.time_to_half_or_double == pytest.approx(math.log(2) / 0.5)
    assert mode.is_stable


def test_real_eigenmode():
    mode = avl.EigenMode({"eigenvalue": complex(0.2, 0.0)})
    assert mode.period == math.inf
    assert mode.damping_ratio == pytest.approx(-1.0)
    assert not mode.is_stable


def test_eigenmode_to_dict(mode):
    modes = avl.ModeResults(
        {1: avl.CaseModes({"EigenValues": [mode.eigenvalue], "EigenModes": [mode]})}
    )
    data = modes.to_dict()
    assert data[1]["EigenValues"] == [[-0.5, 2.0]]
    assert data[1]["EigenModes"][0]["phi"] == [0.1, -0.2]
    json.dumps(data)


def test_mass_properties():
    props = avl.MassProperties(
        {"Mass": 10.0, "CG": avl.Point(1.0, 0.0, 0.5), "Inertia": {"Ixx": 2.0}}
    )
    assert props.mass == 10.0
    assert props.cg.x == 1.0
    assert props.to_dict()["CG"] == [1.0, 0.0, 0.5]


def test_default_outputs():
    outputs = avl.Options().outputs
    assert avl.Output.TOTALS in outputs
    assert avl.Output.SURFACE_PRESSURES not in outputs


def test_outputs_by_name():
    options = avl.Options(outputs=["Totals", avl.Output.STRIP_FORCES])
    assert options.outputs == {avl.Output.TOTALS, avl.Output.STRIP_FORCES}
    with pytest.raises(avl.InputError, match="Totls"):
        avl.Options(outputs=["Totls"])


def test_session_outputs():
    model = avl.Aircraft.from_file(AVL_FILE)
    options = avl.Options(outputs={avl.Output.STABILITY_DERIVATIVES})
    session = avl.Session(model, options=options)
    assert session.requested_output == {avl.Output.STABILITY_DERIVATIVES: "st"}
