from math import radians, tan
import os.path

import pytest

import avlwrapper as avl


CDIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(CDIR, "resources")
MASS_FILE = os.path.join(RES_DIR, "b737.mass")


@pytest.fixture()
def avl_wing():
    wing_span = 12
    wing_aspect_ratio = 8
    wing_taper = 0.3
    wing_le_sweep = radians(20)
    wing_dihedral = radians(4)

    wing_root_chord = 2 * wing_span / (wing_aspect_ratio * (1 + wing_taper))
    wing_tip_chord = wing_root_chord * wing_taper

    wing_root_le_pnt = avl.Point(0.0, 0.0, 0.0)
    wing_tip_le_pnt = avl.Point(
        x=0.5 * wing_span * tan(wing_le_sweep),
        y=0.5 * wing_span,
        z=0.5 * wing_span * tan(wing_dihedral),
    )

    data_airfoil = avl.DataAirfoil(
        x_data=[e / 19 for e in list(range(20))], z_data=[0.0] * 20
    )

    root_section = avl.Section(
        leading_edge_point=wing_root_le_pnt,
        chord=wing_root_chord,
        airfoil=avl.NacaAirfoil("2414"),
    )
    mid_section = avl.Section(
        leading_edge_point=(wing_root_le_pnt + wing_tip_le_pnt) / 2,
        chord=(wing_root_chord + wing_tip_chord) / 2,
        airfoil=data_airfoil,
    )
    tip_section = avl.Section(
        leading_edge_point=wing_tip_le_pnt,
        chord=wing_tip_chord,
        airfoil=avl.FileAirfoil("a1.dat"),
    )

    # y_duplicate=0.0 duplicates the wing over a XZ-plane at Y=0.0
    return avl.Surface(
        name="wing",
        n_chordwise=12,
        chord_spacing=avl.Spacing.equal,
        n_spanwise=20,
        span_spacing=avl.Spacing.cosine,
        y_duplicate=0.0,
        component=1,
        sections=[root_section, mid_section, tip_section],
    )


@pytest.fixture()
def avl_body():
    body_section = avl.BodyProfile("a1.dat")
    return avl.Body(
        name="Test body",
        n_body=12,
        body_spacing=avl.Spacing.sine,
        body_section=body_section,
    )


def test_wing_parse(avl_wing):
    parsed_wing = avl.Surface.from_lines(str(avl_wing).splitlines())
    assert str(avl_wing) == str(parsed_wing)


def test_body_parse(avl_body):
    parsed_body = avl.Body.from_lines(str(avl_body).splitlines())
    assert str(avl_body) == str(parsed_body)


def test_aircraft(avl_wing, avl_body):
    aircraft = avl.Aircraft(
        name="aircraft",
        reference_area=20.0,
        reference_chord=5.0,
        reference_span=12.0,
        reference_point=avl.Point(0.0, 0.0, 0.0),
        mach=0.4,
        surfaces=[avl_wing],
        bodies=[avl_body],
    )
    parsed_aircraft = avl.Aircraft.from_lines(str(aircraft).splitlines())
    assert str(aircraft) == str(parsed_aircraft)


def test_mass_dist():
    assert avl.MassDistribution.from_file(MASS_FILE)


def test_mass_simplify():
    mass_dist = avl.MassDistribution.from_file(MASS_FILE)
    mass_dist.simplify()
    mass_sum = sum([m.mass for m in mass_dist.masses])
    assert mass_sum == pytest.approx(170112.5, 1e-6)
