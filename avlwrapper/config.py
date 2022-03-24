import itertools
import os
import os.path
import shutil
import sys

if os.name == 'nt':
    import winreg

IS_PYTHON_3 = sys.version_info[0] >= 3

if IS_PYTHON_3:
    from configparser import ConfigParser
else:
    from ConfigParser import ConfigParser as _ConfigParser

    # FileNotFoundError doesn't exist yet in Python 2
    FileNotFoundError = IOError

    # sub-class built-in ConfigParser to add Python 3-like behaviour
    class ConfigParser(_ConfigParser):
        def __getitem__(self, item):
            return {key: value
                    for key, value in self.items(item)}

CONFIG_FILE = 'config.cfg'
MODULE_DIR = os.path.dirname(__file__)


class Configuration(object):

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
        avl_path = parser['environment']['executable']
        try:
            settings['avl_bin'] = check_bin(bin_path=avl_path)
        except FileNotFoundError:
            pass
        
        gs_path = parser['environment']['ghostscriptexecutable']
        try:
            settings['gs_bin'] = get_ghostscript(bin_path=gs_path)
        except FileNotFoundError:
            pass

        # show stdout of avl
        show_output = parser['environment']['printoutput']
        settings['show_stdout'] = show_output == 'yes'

        # Output files
        settings['output'] = {k: v
                              for k, v in parser['output'].items()
                              if v == 'yes'}

        return settings

    def local_copy(self, target=os.getcwd()):
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


def check_bin(bin_path, error_msg=""):
    # if absolute path is given, check if exits and executable
    if os.path.isabs(bin_path):
        if os.path.exists(bin_path) and os.access(bin_path, os.X_OK):
            return bin_path

    # append .exe if on Windows
    if os.name == 'nt' and not bin_path.endswith('.exe'):
        bin_path += '.exe'

    # check working dir
    local_bin = os.path.join(os.getcwd(), bin_path)
    if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin

    # check module dir
    module_bin = os.path.join(MODULE_DIR, bin_path)
    if os.path.exists(module_bin) and os.access(module_bin, os.X_OK):
        return module_bin

    # check system path
    system_paths = os.environ['PATH'].split(os.pathsep)
    system_paths.extend(sys.path)
    for path in system_paths:
        candidate_path = os.path.join(path, bin_path)
        if (os.path.exists(candidate_path)
                and os.access(candidate_path, os.X_OK)):
            return candidate_path

    raise FileNotFoundError(error_msg)


def get_ghostscript(bin_path):
    try:
        return check_bin(bin_path)
    except FileNotFoundError as e:
        # when running on Windows, use the registry to find Ghostscript
        if os.name == 'nt':
            key_path = r'SOFTWARE\Artifex\GPL Ghostscript'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                sub_keys = list(_get_reg_sub_keys(key))
                gs_dir = winreg.QueryValue(key, sub_keys[-1])
            gs_bin = os.path.join(gs_dir, 'bin', 'gswin64c.exe')
            if (os.path.exists(gs_bin)
                    and os.access(gs_bin, os.X_OK)):
                return gs_bin
        raise e


def _get_reg_sub_keys(key):
    for idx in itertools.count():
        try:
            yield winreg.EnumKey(key, idx)
        except OSError:
            break


default_config = Configuration()
