import os

import pytest

import avlwrapper as avl

CDIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(CDIR, "resources")

# options menu as printed by AVL 3.52
MENU_352 = """
   ======================================
    P rint default output for...
        total     :   T
        surfaces  :   F
        strips    :   F
        elements  :   F

    H inge mom. output:   F
    D erivative output:   F

    T rail.leg forces :   F
    V iscous forces   :   T
    B ody forces      :   T
    N ear-field forces:   F

    A xis orient. :  Standard axis orientation,  X fwd, Z down
    R ate,mom axes:  Rates,moments about Stability Axes, X along Vinf
"""

# options menu following the format in the AVL 3.40 source
MENU_340 = """
   ======================================
    T rail.leg forces:   T
    V iscous forces  :   F
    B ody forces     :   T

    A xis orient. :  Geometric axis orientation,  X aft, Z up
    R ate,mom axes:  Rates,moments about Body Axes, X along geometric X axis
"""


def test_read_menu():
    assert avl.Options.read_menu(MENU_352) == {
        "standard_axes": True,
        "stability_axis_rates": True,
        "profile_drag": True,
        "trailing_leg_forces": False,
        "body_induced_velocity": False,
    }
    assert avl.Options.read_menu(MENU_340) == {
        "standard_axes": False,
        "stability_axis_rates": False,
        "profile_drag": False,
        "trailing_leg_forces": True,
        "body_induced_velocity": None,
    }


def test_last_menu_counts():
    toggled = MENU_352 + MENU_352.replace(
        "V iscous forces   :   T", "V iscous forces   :   F"
    )
    assert avl.Options.read_menu(toggled)["profile_drag"] is False


def test_commands_toggle_differences_only():
    current = avl.Options.read_menu(MENU_352)
    options = avl.Options(profile_drag=True, trailing_leg_forces=True)
    assert options.commands(current) == "oper\no\nT\n\n\n"
    assert avl.Options(profile_drag=True).commands(current) == ""


def test_unsupported_option():
    current = avl.Options.read_menu(MENU_340)
    with pytest.raises(avl.InputError, match="body_induced_velocity"):
        avl.Options(body_induced_velocity=True).commands(current)


def test_check():
    avl.Options(profile_drag=True).check(MENU_352)
    with pytest.raises(avl.AvlExecutionError, match="profile_drag"):
        avl.Options(profile_drag=False).check(MENU_352)


@pytest.fixture()
def polar_wing():
    polar = avl.ProfileDrag(cl=[-0.5, 0.3, 1.2], cd=[0.02, 0.008, 0.03])
    sections = [
        avl.Section(
            leading_edge_point=avl.Point(0.0, y, 0.0), chord=1.0, profile_drag=polar
        )
        for y in (0.0, 5.0)
    ]
    wing = avl.Surface(
        name="wing",
        n_chordwise=8,
        chord_spacing=avl.Spacing.cosine,
        n_spanwise=12,
        span_spacing=avl.Spacing.cosine,
        y_duplicate=0.0,
        sections=sections,
    )
    return avl.Aircraft(
        name="polar",
        reference_area=10.0,
        reference_chord=1.0,
        reference_span=10.0,
        reference_point=avl.Point(0.25, 0.0, 0.0),
        surfaces=[wing],
    )


def totals(geometry, case, **options):
    session = avl.Session(geometry, cases=[case], options=avl.Options(**options))
    return session.run_all_cases()[1]["Totals"]


@pytest.mark.avl
def test_profile_drag(polar_wing):
    case = avl.Case(name="cruise", alpha=4.0)
    # on by default, since the geometry has CDCL polars
    assert totals(polar_wing, case)["CDvis"] > 0.0
    assert totals(polar_wing, case, profile_drag=True)["CDvis"] > 0.0
    assert totals(polar_wing, case, profile_drag=False)["CDvis"] == 0.0


@pytest.mark.avl
def test_axes(polar_wing):
    case = avl.Case(name="roll", alpha=4.0, roll_rate=0.05)
    default = totals(polar_wing, case)
    geometric = totals(polar_wing, case, standard_axes=False)
    assert geometric["CXtot"] == pytest.approx(-default["CXtot"])
    body_rates = totals(polar_wing, case, stability_axis_rates=False)
    assert body_rates["Cltot"] != pytest.approx(default["Cltot"], rel=1e-3)


@pytest.mark.avl
def test_trailing_leg_forces():
    model = avl.Aircraft.from_file(os.path.join(RES_DIR, "supra.avl"))
    case = avl.Case.from_file(os.path.join(RES_DIR, "supra.run"))[0]

    def cnr(**options):
        session = avl.Session(model, cases=[case], options=avl.Options(**options))
        return session.run_all_cases()[1]["StabilityDerivatives"]["Cnr"]

    assert cnr(trailing_leg_forces=True) != pytest.approx(
        cnr(trailing_leg_forces=False), rel=1e-3
    )


@pytest.mark.avl
def test_options_in_mode_analysis():
    model = avl.Aircraft.from_file(os.path.join(RES_DIR, "b737.avl"))
    case = avl.Case.from_file(os.path.join(RES_DIR, "b737.run"))[0]
    mass = avl.MassDistribution.from_file(os.path.join(RES_DIR, "b737.mass"))

    def phugoid(**options):
        session = avl.Session(
            model, cases=[case], mass_dist=mass, options=avl.Options(**options)
        )
        return session.run_mode_analysis()["EigenValues"][1][0]

    # the reference eigenvalues in b737.eig were computed by an AVL version
    # which included the trailing-leg forces by default
    assert phugoid(trailing_leg_forces=True) == pytest.approx(
        (-0.29018355, 1.9011338), rel=1e-6
    )
    assert phugoid(trailing_leg_forces=False) != pytest.approx(
        phugoid(trailing_leg_forces=True), rel=1e-3
    )
