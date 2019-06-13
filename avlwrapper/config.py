#!/usr/bin/env python3

import os
import os.path
import shutil
import sys

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
        executable_path = parser['environment']['executable']
        settings['avl_bin'] = check_bin(executable_path)

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


def check_bin(bin_path):
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
    for path in os.environ['PATH'].split(os.pathsep):
        candidate_path = os.path.join(path, bin_path)
        if (os.path.exists(candidate_path)
                and os.access(candidate_path, os.X_OK)):
            return candidate_path

    raise FileNotFoundError('AVL not found or not executable, '
                            'check config file')


default_config = Configuration()
