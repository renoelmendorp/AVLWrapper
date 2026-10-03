import itertools
import logging
import os
import os.path
import shutil
from configparser import ConfigParser

if os.name == "nt":
    import winreg

CONFIG_FILE = "config.cfg"
MODULE_DIR = os.path.dirname(__file__)

logger = logging.getLogger("avlwrapper")
logger.addHandler(logging.NullHandler())


class Configuration:
    def __init__(self, filepath=None):

        self._settings = None

        if filepath is not None:
            self.filepath = filepath
        else:
            # check working directory
            local_config_path = os.path.join(os.getcwd(), CONFIG_FILE)
            if os.path.exists(local_config_path):
                self.filepath = local_config_path
            else:
                # default to config file in module
                self.filepath = os.path.join(MODULE_DIR, CONFIG_FILE)

    def read(self):
        parser = ConfigParser()
        parser.read(self.filepath)

        settings = dict()
        avl_path = parser["environment"]["executable"]
        try:
            settings["avl_bin"] = check_bin(bin_path=avl_path)
        except FileNotFoundError:
            pass

        gs_path = parser["environment"]["ghostscriptexecutable"]
        try:
            settings["gs_bin"] = get_ghostscript(bin_path=gs_path)
        except FileNotFoundError:
            pass

        # show stdout of avl
        settings["show_stdout"] = is_enabled(parser["environment"]["printoutput"])

        # Output files
        settings["output"] = dict(parser["output"].items())

        settings["loglevel"] = parser["environment"]["loglevel"]

        return settings

    def apply_log_level(self):
        """Sets the level of the avlwrapper logger to the configured level"""
        logger.setLevel(self["loglevel"])

    def local_copy(self, target=None):
        if target is None:
            target = os.getcwd()
        shutil.copy(self.filepath, target)

    @property
    def settings(self):
        if self._settings is None:
            self._settings = self.read()
        return self._settings

    def __getitem__(self, key):
        return self.settings[key]

    def __setitem__(self, key, value):
        self.settings[key] = value


def is_enabled(value):
    """Whether a setting ("yes"/"no" or a boolean) is switched on"""
    if isinstance(value, str):
        return value.strip().lower() == "yes"
    return bool(value)


def _is_executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def check_bin(bin_path, error_msg=""):
    # if absolute path is given, it either is the executable or it's not
    if os.path.isabs(bin_path):
        if _is_executable(bin_path):
            return bin_path
        raise FileNotFoundError(error_msg or bin_path)

    # append .exe if on Windows
    if os.name == "nt" and not bin_path.endswith(".exe"):
        bin_path += ".exe"

    # check working dir and module dir
    for directory in (os.getcwd(), MODULE_DIR):
        candidate_path = os.path.join(directory, bin_path)
        if _is_executable(candidate_path):
            return candidate_path

    # check system path
    system_bin = shutil.which(bin_path)
    if system_bin is not None:
        return system_bin

    raise FileNotFoundError(error_msg or bin_path)


def get_ghostscript(bin_path):
    try:
        return check_bin(bin_path)
    except FileNotFoundError as e:
        # when running on Windows, use the registry to find Ghostscript
        if os.name == "nt":
            key_path = r"SOFTWARE\Artifex\GPL Ghostscript"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                sub_keys = list(_get_reg_sub_keys(key))
                gs_dir = winreg.QueryValue(key, sub_keys[-1])
            gs_bin = os.path.join(gs_dir, "bin", "gswin64c.exe")
            if _is_executable(gs_bin):
                return gs_bin
        raise e


def _get_reg_sub_keys(key):
    for idx in itertools.count():
        try:
            yield winreg.EnumKey(key, idx)
        except OSError:
            break


default_config = Configuration()
