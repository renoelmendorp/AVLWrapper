import itertools
import logging
import os
import os.path
import shutil
import warnings
from configparser import ConfigParser

if os.name == "nt":
    import winreg

CONFIG_FILE = "config.cfg"
MODULE_DIR = os.path.dirname(__file__)

# environment variable with the path to the AVL executable
AVL_EXECUTABLE_ENV = "AVL_EXECUTABLE"

logger = logging.getLogger("avlwrapper")
logger.addHandler(logging.NullHandler())


class AvlWrapperDeprecationWarning(DeprecationWarning):
    """Deprecated use of avlwrapper, shown by default"""


warnings.filterwarnings("default", category=AvlWrapperDeprecationWarning)


def user_config_dir():
    """Directory of the user's configuration file"""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get(
            "XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")
        )
    return os.path.join(base, "avlwrapper")


def find_config_file():
    """
    The configuration file to use: config.cfg in the working directory, else
    in the user's configuration directory, else the defaults of the module
    """
    for directory in (os.getcwd(), user_config_dir()):
        file_path = os.path.join(directory, CONFIG_FILE)
        if os.path.exists(file_path):
            return file_path
    return os.path.join(MODULE_DIR, CONFIG_FILE)


# keys in the [environment] section of the configuration file
_FILE_KEYS = {
    "avl_executable": "Executable",
    "ghostscript_executable": "GhostscriptExecutable",
    "print_output": "PrintOutput",
    "log_level": "LogLevel",
}


def _read_file(file_path):
    """Settings in a configuration file, missing settings are taken from the
    module's configuration file"""
    parser = ConfigParser()
    parser.read([os.path.join(MODULE_DIR, CONFIG_FILE), file_path])
    if _has_output_section(file_path):
        warnings.warn(
            f"The [output] section in {file_path} is no longer used and is "
            "ignored. Select the outputs in the code with "
            "Session(..., options=Options(outputs={Output.TOTALS, ...})).",
            AvlWrapperDeprecationWarning,
            stacklevel=4,
        )
    section = parser["environment"]
    return {name: section[key] for name, key in _FILE_KEYS.items()}


def _has_output_section(file_path):
    parser = ConfigParser()
    parser.read(file_path)
    return parser.has_section("output")


class Configuration:
    """
    Settings of the machine: where AVL and Ghostscript are installed and how
    much AVL output to show. Settings which aren't given are read from a
    configuration file, see find_config_file. The AVL executable can also be
    set with the AVL_EXECUTABLE environment variable.

    :param Optional[str] avl_executable: name or path of the AVL executable
    :param Optional[str] ghostscript_executable: name or path of Ghostscript,
        used to convert plots
    :param Optional[bool] print_output: print the output of AVL
    :param Optional[str] log_level: level of the avlwrapper logger
    :param Optional[str] filepath: configuration file to read the other
        settings from
    """

    def __init__(
        self,
        avl_executable=None,
        ghostscript_executable=None,
        print_output=None,
        log_level=None,
        filepath=None,
    ):
        if filepath is not None and not os.path.exists(filepath):
            raise FileNotFoundError(filepath)
        self.filepath = filepath or find_config_file()
        file_settings = _read_file(self.filepath)

        self.avl_executable = (
            avl_executable
            or os.environ.get(AVL_EXECUTABLE_ENV)
            or file_settings["avl_executable"]
        )
        self.ghostscript_executable = (
            ghostscript_executable or file_settings["ghostscript_executable"]
        )
        self.print_output = (
            print_output
            if print_output is not None
            else is_enabled(file_settings["print_output"])
        )
        self.log_level = log_level or file_settings["log_level"]

    @classmethod
    def from_file(cls, filepath, **kwargs):
        """Configuration from a configuration file, see Configuration"""
        return cls(filepath=filepath, **kwargs)

    def __repr__(self):
        return (
            f"Configuration(avl_executable={self.avl_executable!r}, "
            f"ghostscript_executable={self.ghostscript_executable!r}, "
            f"print_output={self.print_output!r}, log_level={self.log_level!r})"
        )

    @property
    def avl_path(self):
        """Path to the AVL executable"""
        try:
            return check_bin(self.avl_executable)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"AVL executable '{self.avl_executable}' not found. Install AVL "
                "3.40 or later and set its location with "
                f"Configuration(avl_executable=...), the {AVL_EXECUTABLE_ENV} "
                "environment variable or a configuration file."
            ) from None

    @property
    def ghostscript_path(self):
        """Path to Ghostscript, None if it's not found"""
        try:
            return get_ghostscript(self.ghostscript_executable)
        except (FileNotFoundError, OSError):
            return None

    def apply_log_level(self):
        """Sets the level of the avlwrapper logger to the configured level"""
        logger.setLevel(self.log_level)

    def save(self, file_path):
        """Writes the settings to a configuration file"""
        parser = ConfigParser()
        parser.optionxform = str
        parser["environment"] = {
            "Executable": self.avl_executable,
            "GhostscriptExecutable": self.ghostscript_executable,
            "PrintOutput": "yes" if self.print_output else "no",
            "LogLevel": self.log_level,
        }
        with open(file_path, "w") as fp:
            parser.write(fp)

    def local_copy(self, target=None):
        """Writes the settings to config.cfg in target (a directory or file),
        defaults to the working directory"""
        if target is None:
            target = os.getcwd()
        if os.path.isdir(target):
            target = os.path.join(target, CONFIG_FILE)
        self.save(target)


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
