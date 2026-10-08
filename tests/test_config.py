import os

import pytest

import avlwrapper as avl
from avlwrapper.config import AVL_EXECUTABLE_ENV, user_config_dir


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    """No configuration file in the working or user directory, no
    environment variable"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "user"))
    monkeypatch.delenv(AVL_EXECUTABLE_ENV, raising=False)
    return work_dir


def write_config(directory, executable, extra=""):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "config.cfg")
    with open(path, "w") as fp:
        fp.write(f"[environment]\nExecutable = {executable}\n{extra}")
    return path


def test_defaults(clean_env):
    config = avl.Configuration()
    assert config.avl_executable == "avl"
    assert config.ghostscript_executable == "gs"
    assert config.print_output is False
    assert config.log_level == "WARNING"


def test_user_config(clean_env):
    write_config(user_config_dir(), "/opt/avl/user-avl")
    assert avl.Configuration().avl_executable == "/opt/avl/user-avl"


def test_working_directory_before_user_config(clean_env):
    write_config(user_config_dir(), "/opt/avl/user-avl")
    write_config(str(clean_env), "/opt/avl/local-avl")
    assert avl.Configuration().avl_executable == "/opt/avl/local-avl"


def test_environment_before_file(clean_env, monkeypatch):
    write_config(str(clean_env), "/opt/avl/local-avl")
    monkeypatch.setenv(AVL_EXECUTABLE_ENV, "/opt/avl/env-avl")
    assert avl.Configuration().avl_executable == "/opt/avl/env-avl"
    # an argument comes first
    config = avl.Configuration(avl_executable="/opt/avl/arg-avl")
    assert config.avl_executable == "/opt/avl/arg-avl"


def test_from_file(clean_env, tmp_path):
    path = write_config(str(tmp_path / "elsewhere"), "my-avl", "PrintOutput = yes\n")
    config = avl.Configuration.from_file(path)
    assert config.avl_executable == "my-avl"
    assert config.print_output is True
    # missing settings are the defaults
    assert config.log_level == "WARNING"


def test_from_missing_file(clean_env):
    with pytest.raises(FileNotFoundError):
        avl.Configuration.from_file("no-such-config.cfg")


def test_output_section_is_deprecated(clean_env):
    path = write_config(str(clean_env), "avl", "\n[output]\nTotals = yes\n")
    with pytest.warns(avl.AvlWrapperDeprecationWarning, match="Options"):
        config = avl.Configuration.from_file(path)
    assert config.avl_executable == "avl"


def test_local_copy(clean_env):
    config = avl.Configuration(avl_executable="/opt/avl/avl", print_output=True)
    config.local_copy()
    copy = avl.Configuration.from_file(str(clean_env / "config.cfg"))
    assert copy.avl_executable == "/opt/avl/avl"
    assert copy.print_output is True


def test_executable_not_found(clean_env):
    config = avl.Configuration(avl_executable="no-such-avl")
    with pytest.raises(FileNotFoundError, match=AVL_EXECUTABLE_ENV):
        config.avl_path
    assert (
        avl.Configuration(ghostscript_executable="no-such-gs").ghostscript_path is None
    )
