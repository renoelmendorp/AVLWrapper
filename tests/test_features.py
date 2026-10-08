"""Eigenmodes, mass properties, trim, design changes, off-body flow,
body-axis strip forces and surface pressures"""

import math
import os

import pytest

import avlwrapper as avl
from avlwrapper import listings

CDIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(CDIR, "resources")
MRF_DIR = os.path.join(RES_DIR, "avl352")


def read_text(file_name):
    with open(os.path.join(MRF_DIR, file_name)) as fp:
        return fp.read()


# readers, on output of AVL 3.52


def test_read_eigenmodes():
    modes = listings.read_eigenmodes(read_text("b737-modes.txt"))
    assert list(modes) == [1]
    assert len(modes[1]) == 8
    mode = modes[1][1]
    assert mode["eigenvalue"] == pytest.approx((-0.291925, 1.87048))
    assert mode["v"] == pytest.approx((10.7938, 8.1219))
    assert mode["x"] == pytest.approx((0.4536e-05, 0.2966e-06))
    assert set(mode) == {"eigenvalue", *listings.EIGENVECTOR_COMPONENTS}


def test_read_mass_properties():
    props = listings.read_mass_properties(read_text("b737-msho.txt"))
    assert props["Mass"] == pytest.approx(0.7715e05)
    assert props["CG"] == pytest.approx((19.89, 0.0, 0.3553))
    assert props["ReferencePoint"] == pytest.approx((60.0, 0.0, 0.0))
    assert props["Inertia"]["Ixx"] == pytest.approx(0.7067e06)
    assert props["Inertia"]["Izx"] == pytest.approx(0.2699e05)
    assert props["ApparentMass"]["myy"] == pytest.approx(933.5)
    assert props["ApparentInertia"]["Izx"] == pytest.approx(-3809.0)


def test_read_strip_forces_body_axes():
    res = avl.OutputReader(os.path.join(MRF_DIR, "b737.fsb")).get_content()
    assert set(res) == {
        "Wing",
        "Stab",
        "Fin",
        "Fuselage H",
        "Fuselage V Bottom",
        "Fuselage V Top",
        "Nacelle",
    }
    # strips of the duplicated wing follow the original ones
    assert len(res["Wing"]["CFZstrp"]) == 52
    assert res["Wing"]["CFZstrp"][0] == pytest.approx(-0.35706)
    assert res["Wing"]["Yc/4"][26] == pytest.approx(-6.14044)
    assert res["Nacelle"]["CAXLstrp"][-1] == pytest.approx(-0.39521e-02)


def test_read_off_body_flow():
    res = avl.OutputReader(os.path.join(MRF_DIR, "b737.ob")).get_content()
    assert res["X"] == [60.0, 80.0]
    assert res["Vmag"] == pytest.approx([1.045685, 1.007944])
    assert res["Cp0"] == pytest.approx([-0.093457, -0.015951])


# runs of AVL


@pytest.fixture()
def b737_session():
    model = avl.Aircraft.from_file(os.path.join(RES_DIR, "b737.avl"))
    case = avl.Case.from_file(os.path.join(RES_DIR, "b737.run"))[0]
    mass = avl.MassDistribution.from_file(os.path.join(RES_DIR, "b737.mass"))
    return avl.Session(model, cases=[case], mass_dist=mass)


@pytest.fixture()
def supra_session():
    model = avl.Aircraft.from_file(os.path.join(RES_DIR, "supra.avl"))
    cases = avl.Case.from_file(os.path.join(RES_DIR, "supra.run"))
    mass = avl.MassDistribution.from_file(os.path.join(RES_DIR, "supra.mass"))
    return avl.Session(model, cases=cases, mass_dist=mass)


@pytest.fixture()
def wing():
    sections = [
        avl.Section(
            leading_edge_point=avl.Point(0.0, y, 0.0),
            chord=1.0,
            airfoil=avl.NacaAirfoil("2412"),
        )
        for y in (0.0, 5.0)
    ]
    surface = avl.Surface(
        name="wing",
        n_chordwise=8,
        chord_spacing=avl.Spacing.cosine,
        n_spanwise=12,
        span_spacing=avl.Spacing.cosine,
        y_duplicate=0.0,
        sections=sections,
    )
    return avl.Aircraft(
        name="wing",
        reference_area=10.0,
        reference_chord=1.0,
        reference_span=10.0,
        reference_point=avl.Point(0.25, 0.0, 0.0),
        surfaces=[surface],
    )


@pytest.mark.avl
def test_eigenmodes(b737_session):
    res = b737_session.run_mode_analysis()
    assert set(res) == {1}
    assert set(res[1]) == {"EigenValues", "EigenModes", "SystemMatrix"}
    modes, values = res[1].modes, res[1].eigenvalues
    assert len(modes) == len(values) > 0
    assert [mode.eigenvalue for mode in modes] == values
    assert all(isinstance(value, complex) for value in values)
    assert set(modes[0].vector) == set(listings.EIGENVECTOR_COMPONENTS)
    assert res[1].system_matrix == res[1]["SystemMatrix"]


@pytest.mark.avl
def test_mode_analysis_per_case(supra_session):
    all_cases = supra_session.run_mode_analysis()
    numbers = [case.number for case in supra_session.cases]
    assert set(all_cases) == set(numbers)

    single = supra_session.run_mode_analysis(cases=[2])
    assert set(single) == {2}
    assert single[2].eigenvalues == all_cases[2].eigenvalues
    for key, column in single[2].system_matrix.items():
        # round-off differences between the runs
        expected = all_cases[2].system_matrix[key]
        assert column == pytest.approx(expected, rel=1e-3, abs=1e-12)

    with pytest.raises(avl.InputError, match="99"):
        supra_session.run_mode_analysis(cases=[99])


@pytest.mark.avl
def test_mass_properties(b737_session):
    props = b737_session.mass_properties()
    # the mass applied to the cases by MSET
    states = b737_session.run_all_cases()[1]["States"]
    assert props["Mass"] == pytest.approx(states["mass"], rel=1e-3)
    assert props["Inertia"]["Ixx"] == pytest.approx(states["Ixx"], rel=1e-3)
    assert props["Inertia"]["Izx"] == pytest.approx(states["Izx"], rel=1e-3)


def test_mass_properties_without_mass(wing):
    with pytest.raises(avl.InputError, match="mass"):
        avl.Session(wing).mass_properties()


@pytest.mark.avl
def test_states(b737_session):
    res = b737_session.run_all_cases()[1]
    assert res["States"]["alpha"] == pytest.approx(res["Totals"]["Alpha"], rel=1e-5)
    assert res["States"]["CL"] == pytest.approx(res["Totals"]["CLtot"], rel=1e-5)


@pytest.mark.avl
@pytest.mark.parametrize("bank", [0.0, 30.0])
def test_level_flight(wing, bank):
    mass, velocity, density, gravity = 10.0, 20.0, 1.225, 9.81
    case = avl.Case(
        name="level",
        trim=avl.Trim.level_flight,
        mass=mass,
        velocity=velocity,
        density=density,
        gravity=gravity,
        bank=bank,
    )
    res = avl.Session(wing, cases=[case]).run_all_cases()[1]
    cos_bank = math.cos(math.radians(bank))
    expected_cl = 2 * mass * gravity / (density * 10.0 * velocity**2 * cos_bank)
    assert res["Totals"]["CLtot"] == pytest.approx(expected_cl, rel=1e-4)
    assert res["States"]["load_fac"] == pytest.approx(1 / cos_bank, rel=1e-4)
    if bank:
        radius = velocity**2 / (gravity * math.tan(math.radians(bank)))
        assert res["States"]["turn_rad"] == pytest.approx(radius, rel=1e-4)


@pytest.mark.avl
def test_looping(wing):
    mass, density, cl = 10.0, 1.225, 0.6
    case = avl.Case(
        name="loop",
        trim=avl.Trim.looping,
        mass=mass,
        velocity=20.0,
        density=density,
        CL=cl,
    )
    res = avl.Session(wing, cases=[case]).run_all_cases()[1]
    radius = mass / (0.5 * density * 10.0 * cl)
    assert res["States"]["turn_rad"] == pytest.approx(radius, rel=1e-4)
    assert res["States"]["pitch_rate"] > 0.0


@pytest.mark.avl
def test_trim_in_mode_analysis(wing):
    mass = avl.MassDistribution(
        masses=[
            avl.MassItem(
                mass=10.0,
                position=avl.Point(0.1, 0.0, 0.0),
                inertia=avl.Inertia(5.0, 1.0, 6.0),
            )
        ]
    )
    case = avl.Case(name="level", trim=avl.Trim.level_flight, velocity=20.0)
    session = avl.Session(wing, cases=[case], mass_dist=mass)
    assert session.run_mode_analysis()[1].eigenvalues


@pytest.mark.avl
def test_design_changes():
    model = avl.Aircraft.from_file(os.path.join(RES_DIR, "design.avl"))
    assert model.design_names == ["twist", "sweep"]
    case = avl.Case(name="cruise", alpha=4.0)

    def results(**changes):
        session = avl.Session(model, cases=[case], design_changes=changes)
        return session.run_all_cases()[1]

    base = results()
    changed = results(twist=0.2)
    expected = base["StabilityDerivatives"]["CL_twist"] * 0.2
    delta = changed["Totals"]["CLtot"] - base["Totals"]["CLtot"]
    assert delta == pytest.approx(expected, rel=0.02)
    # design variables are numbered in the order of the geometry
    assert results(sweep=0.2)["Totals"]["CLtot"] != pytest.approx(
        changed["Totals"]["CLtot"], rel=1e-4
    )


def test_unknown_design_variable(wing):
    with pytest.raises(avl.InputError, match="twist"):
        avl.Session(wing, design_changes={"twist": 1.0})


@pytest.mark.avl
def test_off_body_flow(wing):
    points = [avl.Point(-100.0, 0.0, 0.0), avl.Point(2.0, 2.0, 0.5)]
    case = avl.Case(name="cruise", alpha=4.0)
    res = avl.Session(wing, cases=[case], survey_points=points).run_all_cases()[1]
    flow = res["OffBodyFlow"]
    assert flow["X"] == [-100.0, 2.0]
    # far upstream the flow is undisturbed
    assert flow["Vmag"][0] == pytest.approx(1.0, abs=1e-3)
    assert flow["Vmag"][1] != pytest.approx(1.0, abs=1e-3)


def test_too_many_survey_points(wing):
    points = [avl.Point(0.0, 0.0, float(z)) for z in range(1001)]
    with pytest.raises(avl.InputError, match="1000"):
        avl.Session(wing, survey_points=points)


@pytest.mark.avl
def test_surface_pressures(wing):
    options = avl.Options(outputs={avl.Output.TOTALS, avl.Output.SURFACE_PRESSURES})
    cases = [avl.Case(name="low", alpha=2.0), avl.Case(name="high", alpha=6.0)]
    res = avl.Session(wing, cases=cases, options=options).run_all_cases()
    assert set(res[1]) == {"Name", "States", "Totals", "SurfacePressures"}
    low, high = (res[n]["SurfacePressures"] for n in (1, 2))
    assert set(low) == {"wing", "wing (YDUP)"}
    cp = low["wing"]["ElementCp"]
    # 12 spanwise, 8 chordwise elements
    assert len(cp["cp_up"]) == 12
    assert all(len(row) == 8 for row in cp["cp_up"])
    assert len(low["wing"]["VertexGrid"]["x_lo"]) == 13
    # each case is computed separately
    assert high["wing"]["ElementCp"]["cp_up"][5][0] != pytest.approx(
        cp["cp_up"][5][0], rel=1e-3
    )
