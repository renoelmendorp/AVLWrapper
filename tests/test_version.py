import os
import sys

import pytest

import avlwrapper as avl
from avlwrapper.session import check_avl_version

CDIR = os.path.dirname(os.path.realpath(__file__))
AVL_FILE = os.path.join(CDIR, "resources", "b737.avl")

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="needs shell scripts as fake AVL"
)


def fake_avl(tmp_path, banner):
    script = tmp_path / "avl"
    script.write_text(f"#!/bin/sh\necho '{banner}'\ncat > /dev/null\n")
    script.chmod(0o755)
    return str(script)


@pytest.mark.parametrize(
    "version, expected", [("3.40", (3, 40)), ("3.40b", (3, 40)), ("3.52", (3, 52))]
)
def test_supported_version(tmp_path, version, expected):
    banner = f"  Athena Vortex Lattice  Program      Version  {version}"
    assert check_avl_version(fake_avl(tmp_path, banner)) == expected


@pytest.mark.parametrize("version", ["3.36", "3.27", "2.99"])
def test_old_version(tmp_path, version):
    banner = f"  Athena Vortex Lattice  Program      Version  {version}"
    with pytest.raises(avl.AvlVersionError, match="not supported"):
        check_avl_version(fake_avl(tmp_path, banner))


def test_unknown_version(tmp_path):
    with pytest.raises(avl.AvlVersionError, match="not found"):
        check_avl_version(fake_avl(tmp_path, "not AVL"))


def test_session_checks_version(tmp_path):
    config = avl.Configuration(
        avl_executable=fake_avl(
            tmp_path, "  Athena Vortex Lattice  Program      Version  3.36"
        )
    )
    model = avl.Aircraft.from_file(AVL_FILE)
    session = avl.Session(geometry=model, cases=[avl.Case(name="case")], config=config)
    with pytest.raises(avl.AvlVersionError, match="3.36"):
        session.run_all_cases()


@pytest.mark.avl
def test_installed_avl():
    assert check_avl_version(avl.default_config.avl_path) >= (3, 40)
