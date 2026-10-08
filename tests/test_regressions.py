"""Regression tests for the fixes in 0.4.1"""

import copy
import os
import subprocess
import sys

import pytest

import avlwrapper as avl

CDIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(CDIR, "resources")
AVL_FILE = os.path.join(RES_DIR, "b737.avl")
CASE_FILE = os.path.join(RES_DIR, "b737.run")

MASS_HEADER = [
    "Lunit = 1.0 m",
    "Munit = 1.0 kg",
    "Tunit = 1.0 s",
    "g = 9.81",
    "rho = 1.225",
]


def surface_lines(n_sections):
    lines = ["SURFACE", "wing", "4 1.0"]
    for idx in range(n_sections):
        lines += [
            "SECTION",
            f"0.0 {idx}.0 0.0 1.0 0.0",
            "CDCL",
            f"0.{idx} 0.01 0.5 0.02 1.0 0.05",
        ]
    return lines


@pytest.mark.parametrize("n_sections", [2, 3, 4])
def test_profile_drag_on_all_sections(n_sections):
    surface = avl.Surface.from_lines(surface_lines(n_sections))
    assert len(surface.sections) == n_sections
    assert surface.profile_drag is None
    for idx, section in enumerate(surface.sections):
        assert section.profile_drag.cl[0] == pytest.approx(idx / 10)
    parsed = avl.Surface.from_lines(str(surface).splitlines())
    assert str(parsed) == str(surface)


def test_surface_and_section_profile_drag():
    lines = surface_lines(2)
    lines[3:3] = ["CDCL", "0.9 0.01 1.0 0.02 1.1 0.05"]
    surface = avl.Surface.from_lines(lines)
    assert surface.profile_drag.cl[0] == pytest.approx(0.9)
    assert all(s.profile_drag is not None for s in surface.sections)


def test_malformed_body():
    lines = ["BODY", "body", "12 1.0 99 0.0", "BFILE", "a1.dat"]
    with pytest.raises(avl.InputError):
        avl.Body.from_lines(lines)


def test_input_error_message():
    assert str(avl.InputError("Invalid state")) == "Invalid state"
    assert str(avl.InputError(["line 1", "line 2"])) == "Invalid input:\nline 1\nline 2"


def test_negative_mass():
    lines = MASS_HEADER + ["10.0 1.0 0.0 0.0", "-2.0 1.0 0.0 0.0", ".5 2.0 0.0 0.0"]
    mass_dist = avl.MassDistribution.from_lines(lines)
    assert [m.mass for m in mass_dist.masses] == [10.0, -2.0, 0.5]


def test_modifier_without_inertia():
    lines = MASS_HEADER + [
        "* 2.0 1.0 1.0 1.0",
        "+ 0.0 1.0 0.0 0.0",
        "10.0 1.0 0.0 0.0",
        "-2.0 3.0 0.0 0.0 1.0 2.0 3.0",
    ]
    mass_dist = avl.MassDistribution.from_lines(lines)
    mass_dist.simplify()
    assert [m.mass for m in mass_dist.masses] == [20.0, -4.0]
    assert [m.position.x for m in mass_dist.masses] == [2.0, 4.0]
    assert mass_dist.masses[1].inertia.Izz == pytest.approx(3.0)
    assert avl.MassDistribution.from_lines(str(mass_dist).splitlines())


def test_session_does_not_modify_cases():
    model_a = avl.Aircraft.from_file(AVL_FILE)
    model_b = copy.deepcopy(model_a)
    model_b.reference_point = avl.Point(999.0, 0.0, 0.0)
    case = avl.Case(name="case", alpha=2.0)

    session_a = avl.Session(geometry=model_a, cases=[case])
    session_b = avl.Session(geometry=model_b, cases=[case])

    assert case.states["X_cg"].value is None
    assert session_a.cases[0].states["X_cg"].value == model_a.reference_point.x
    assert session_b.cases[0].states["X_cg"].value == 999.0


def test_case_str_without_session():
    case = avl.Case(name="plain", alpha=2.0)
    assert "plain" in str(case)
    with pytest.raises(avl.InputError, match="cd_p"):
        case.validate()


def test_unknown_control(tmp_path):
    model = avl.Aircraft.from_file(AVL_FILE)
    assert "elevator" in model.control_names

    session = avl.Session(geometry=model, cases=[avl.Case(name="typo", alhpa=5.0)])
    with pytest.raises(avl.InputError, match="alhpa"):
        session.export_run_files(str(tmp_path))

    session = avl.Session(geometry=model, cases=[avl.Case(name="ok", elevator=5.0)])
    session.export_run_files(str(tmp_path))


@pytest.mark.avl
def test_eigen_values_indexed_like_cases():
    model = avl.Aircraft.from_file(AVL_FILE)
    cases = avl.Case.from_file(CASE_FILE)
    session = avl.Session(geometry=model, cases=cases)
    assert set(session.run_mode_analysis()) == set(session.run_all_cases())


@pytest.mark.parametrize(
    "ext", ["ft", "fn", "fb", "fs", "fe", "st", "sb", "hm", "vm", "sys", "eig"]
)
def test_empty_output(tmp_path, ext):
    file_path = tmp_path / f"empty.{ext}"
    file_path.write_text("")
    with pytest.raises(avl.OutputError, match="empty"):
        avl.OutputReader(str(file_path)).get_content()


@pytest.mark.parametrize("ext", ["ft", "fn", "fb", "fs", "fe", "st", "sb"])
def test_truncated_output(tmp_path, ext):
    file_path = tmp_path / f"truncated.{ext}"
    file_path.write_text("TOT\nVERSION 1.0\n  1.0 2.0 | Alpha\n")
    with pytest.raises(avl.OutputError):
        avl.OutputReader(str(file_path), body_names=[]).get_content()


def fake_avl(tmp_path, version="3.52"):
    """An 'AVL' which prints its banner and writes nothing"""
    script = tmp_path / "avl"
    script.write_text(
        "#!/bin/sh\n"
        f"echo '  Athena Vortex Lattice  Program      Version  {version}'\n"
        "cat > /dev/null\n"
    )
    script.chmod(0o755)
    return str(script)


@pytest.mark.skipif(sys.platform == "win32", reason="needs a shell script")
def test_avl_failure(tmp_path):
    config = avl.Configuration(avl_executable=fake_avl(tmp_path))
    model = avl.Aircraft.from_file(AVL_FILE)
    session = avl.Session(geometry=model, cases=[avl.Case(name="case")], config=config)
    with pytest.raises(avl.AvlExecutionError, match="expected output"):
        session.run_all_cases()


@pytest.mark.avl
def test_unloadable_geometry_reported():
    model = avl.Aircraft.from_file(AVL_FILE)
    model.surfaces = []
    model.bodies = []
    session = avl.Session(geometry=model, cases=[avl.Case(name="case")])
    with pytest.raises(avl.AvlExecutionError) as exc_info:
        session.run_all_cases()
    assert exc_info.value.output


def test_local_copy_uses_current_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    avl.default_config.local_copy()
    assert (tmp_path / "config.cfg").exists()


def test_check_bin_absolute_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        avl.config.check_bin(str(tmp_path / "avl"))


def test_import_without_tkinter():
    code = "import sys, avlwrapper; sys.exit('tkinter' in sys.modules)"
    root = os.path.dirname(CDIR)
    assert subprocess.run([sys.executable, "-c", code], cwd=root).returncode == 0


def test_aircraft_equality_ignores_source_file():
    from_file = avl.Aircraft.from_file(AVL_FILE)
    with open(AVL_FILE) as fp:
        from_lines = avl.Aircraft.from_lines(fp.readlines())
    assert from_file == from_lines
