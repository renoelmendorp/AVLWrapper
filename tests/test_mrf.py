"""AVL's machine-readable output (MRF)

The files in resources/avl352 are written by AVL 3.52 with the MRF command.
"""

import os

import pytest

import avlwrapper as avl

CDIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(CDIR, "resources", "avl352")

BODY_NAMES = {
    "b737": [],
    "supra": ["Fuse pod"],
    "bodies": ["Fuse pod", "Pod A", "Pod A (YDUP)", "Pod B"],
    "design": [],
}

FILES = (
    [("b737", ext) for ext in ["ft", "fn", "fs", "fe", "fb", "st", "sb", "hm", "vm"]]
    + [("supra", ext) for ext in ["ft", "fn", "fs", "fb", "st", "sb", "hm", "vm"]]
    + [("bodies", "fb"), ("design", "ft"), ("design", "st"), ("design", "sb")]
)


def read(name, ext, body_names=None):
    file_path = os.path.join(RES_DIR, f"{name}.{ext}")
    return avl.OutputReader(file_path, body_names).get_content()


@pytest.mark.parametrize("name, ext", FILES)
def test_parse(name, ext):
    assert read(name, ext, body_names=BODY_NAMES[name]) is not None


def test_full_precision():
    res = read("b737", "ft")
    assert res["Xref"] == 65.26859063854802
    assert res["Surfaces"] == 11


def test_strip_numbers_above_99():
    # AVL writes the strip header without separators: "  99  241002"
    res = read("b737", "fe")
    strips = [strip for surface in res.values() for strip in surface]
    assert sorted(strips) == list(range(1, 138))
    assert res["Nacelle"][137]["dCp"][0] == pytest.approx(0.619, abs=1e-3)


def test_body_names_from_geometry():
    res = read("bodies", "fb", body_names=BODY_NAMES["bodies"])
    assert set(res) == {"Fuse pod", "Pod A", "Pod B"}
    # duplicated body is added to the original
    assert res["Pod A"]["Length"] == pytest.approx(2 * 67.5)


def test_body_names_missing():
    with pytest.raises(avl.OutputError, match="body name"):
        read("bodies", "fb")


def test_body_count_mismatch():
    with pytest.raises(avl.OutputError, match="bodies"):
        read("bodies", "fb", body_names=["Fuse pod"])


def test_design_variable_names():
    res = read("design", "st")
    assert res["CL_twist"] == pytest.approx(0.1221313, 1e-6)
    assert res["CL_flap"] == pytest.approx(0.05268490, 1e-6)
    assert read("design", "ft")["twist"] == 0.0


def test_truncated_file(tmp_path):
    with open(os.path.join(RES_DIR, "b737.fs")) as fp:
        lines = fp.readlines()
    file_path = tmp_path / "truncated.fs"
    file_path.write_text("".join(lines[: len(lines) // 2]))
    with pytest.raises(avl.OutputError, match="MRF"):
        avl.OutputReader(str(file_path)).get_content()


@pytest.mark.avl
def test_session_reads_mrf_bodies():
    model = avl.Aircraft.from_file(os.path.join(CDIR, "resources", "bodies.avl"))
    session = avl.Session(geometry=model, cases=[avl.Case(name="case", alpha=4.0)])
    bodies = session.run_all_cases()[1]["BodyForces"]
    assert set(bodies) == {"Fuse pod", "Pod A", "Pod B"}
