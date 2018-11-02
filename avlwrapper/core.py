#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" AVL Wrapper core classes
"""
import os
import re
import shutil
import subprocess
import sys

if not sys.version_info[0] < 3: # Python 3
    import tkinter as tk
    from configparser import ConfigParser
    from tempfile import TemporaryDirectory

else:
    import Tkinter as tk
    from ConfigParser import ConfigParser as _ConfigParser
    import tempfile

    # FileNotFoundError doesn't exist yet in Python 2
    FileNotFoundError = IOError

    # simple class which provides TemporaryDirectory-esque functionality
    class TemporaryDirectory(object):
        def __init__(self, suffix='', prefix='', dir=None):
            self.name = tempfile.mkdtemp(suffix=suffix,
                                         prefix=prefix,
                                         dir=dir)

        def cleanup(self):
            shutil.rmtree(self.name)


    # sub-class built-in ConfigParser to add Python 3-like behaviour
    class ConfigParser(_ConfigParser):
        def __getitem__(self, item):
            return {key: value
                    for key, value in self.items(item)}


__MODULE_DIR__ = os.path.dirname(__file__)
CONFIG_FILE = 'config.cfg'


class Input(object):
    def create_input(self):
        raise NotImplementedError


class Parameter(Input):
    """Parameter used in the case definition"""
    def __init__(self, name, value, constraint=None):

        self.name = name
        self.value = value

        # by default, a parameter is not constraint, but set to its own value
        if constraint is None:
            self.constraint = name
        else:
            self.constraint = constraint

    def create_input(self):
        return " {0:<12} -> {1:<12} = {2}\n".format(self.name,
                                                    self.constraint,
                                                    self.value)


class State(Input):
    """State used in the case definition"""
    def __init__(self, name, value, unit=''):
        self.name = name
        self.value = value
        self.unit = unit

    def create_input(self):
        return " {0:<10} = {1:<10} {2}\n".format(self.name,
                                                 self.value,
                                                 self.unit)


class Case(Input):
    """AVL analysis case containing parameters and states"""
    CASE_PARAMETERS = {'alpha': 'alpha', 'beta': 'beta',
                       'roll_rate': 'pb/2V', 'pitch_rate': 'qc/2V',
                       'yaw_rate': 'rb/2V'}

    VALID_CONSTRAINTS = ['alpha', 'beta', 'pb/2V', 'qc/2V',
                         'rb/2V', 'CL', 'CY', 'Cl', 'Cm', 'Cn']

    CASE_STATES = {'alpha': (0.0, 'deg'), 'beta': (0.0, 'deg'),
                   'pb/2V': (0.0, ''), 'qc/2V': (0.0, ''), 'rb/2V': (0.0, ''),
                   'CL': (0.0, ''), 'CDo': (0.0, ''),
                   'bank': (0.0, 'beg'), 'elevation': (0.0, 'deg'),
                   'heading': (0.0, 'deg'), 'Mach': (0.0, ''),
                   'velocity': (0.0, 'm/s'), 'density': (1.225, 'kg/m^3'),
                   'grav.acc.': (9.81, 'm/s^2'), 'turn_rad.': (0.0, 'm'),
                   'load_fac.': (0.0, ''),
                   'X_cg': (0.0, 'm'), 'Y_cg': (0.0, 'm'), 'Z_cg': (0.0, 'm'),
                   'mass': (1.0, 'kg'),
                   'Ixx': (1.0, 'kg-m^2'), 'Iyy': (1.0, 'kg-m^2'),
                   'Izz': (1.0, 'kg-m^2'), 'Ixy': (0.0, 'kg-m^2'),
                   'Iyz': (0.0, 'kg-m^2'), 'Izx': (0.0, 'kg-m^2'),
                   'visc CL_a': (0.0, ''), 'visc CL_u': (0.0, ''),
                   'visc CM_a': (0.0, ''), 'visc CM_u': (0.0, '')}

    def __init__(self, name, **kwargs):

        self.name = name
        self.number = 1
        self.parameters = self._set_default_parameters()
        self.states = self._set_default_states()

        self.controls = []
        for key, value in kwargs.items():
            # if a parameter object is given, add to the dict
            if isinstance(value, Parameter):
                self.parameters[key] = value
            else:
                # if the key is an existing case parameter, set the value
                if key in self.CASE_PARAMETERS.keys():
                    param_str = self.CASE_PARAMETERS[key]
                    self.parameters[param_str].value = value
                elif key in self.CASE_STATES.keys():
                    self.states[key].value = value
                # if an unknown key-value pair is given,
                # assume its a control and create a parameter
                else:
                    param_str = key
                    self.controls.append(key)
                    self.parameters[param_str] = Parameter(name=param_str,
                                                           value=value)

    def _set_default_parameters(self):
        # parameters default to 0.0
        return {name: Parameter(name=name, constraint=name, value=0.0)
                for _, name in self.CASE_PARAMETERS.items()}

    def _set_default_states(self):
        return {key: State(name=key, value=value[0], unit=value[1])
                for key, value in self.CASE_STATES.items()}

    def _check(self):
        self._check_parameters()
        self._check_states()

    def _check_states(self):
        for state in self.states.values():
            if state.name not in self.CASE_STATES.keys():
                raise InputError("Invalid state variable: {0}"
                                 .format(state.name))

    def _check_parameters(self):
        for param in self.parameters.values():
            if (param.constraint not in self.VALID_CONSTRAINTS
                    and param.constraint not in self.controls):
                raise InputError("Invalid constraint on parameter: {0}."
                                 .format(param.name))

    def create_input(self):
        self._check()

        # case header
        case_str = (" " + "-"*45 + "\n Run case {0:<2}:  {1}\n\n"
                    .format(self.number, self.name))

        # write parameters
        for param in self.parameters.values():
            case_str += param.create_input()

        case_str += "\n"

        # write cases
        for state in self.states.values():
            case_str += state.create_input()

        return case_str


class Session(object):
    """Main class which handles AVL runs and input/output"""
    OUTPUTS = {'Totals': 'ft', 'SurfaceForces': 'fn',
               'StripForces': 'fs', 'ElementForces': 'fe',
               'StabilityDerivatives': 'st', 'BodyAxisDerivatives': 'sb',
               'HingeMoments': 'hm'}

    def __init__(self, geometry=None, cases=None, run_keys=None):
        self._temp_dir = None

        config_path = os.path.join(__MODULE_DIR__, CONFIG_FILE)
        self.config = self._read_config(config_path)

        self.geometry = geometry
        self.cases = cases
        self.run_keys = run_keys

        self._calculated = False
        self._results = None

    def _get_base_name(self):
        return self.geometry.name

    def _check(self):
        if (self.cases is None) and (self.run_keys is None):
            raise InputError("Either cases or run keys should be provided.")

    def __del__(self):
        if self._temp_dir is not None:
            self._temp_dir.cleanup()

    @property
    def temp_dir(self):
        if self._temp_dir is None:
            self._create_temp_dir()
        return self._temp_dir

    def _read_config(self, filename):
        config = ConfigParser()
        config.read(filename)

        settings = dict()
        executable_path = config['environment']['executable']
        settings['avl_bin'] = self._check_bin(executable_path)

        # show stdout of avl
        show_output = config['environment']['printoutput']
        settings['show_stdout'] = show_output == 'yes'

        # Output files
        settings['output'] = []
        for output in self.OUTPUTS.keys():
            if config['output'][output.lower()] == 'yes':
                settings['output'].append(output)

        return settings

    @staticmethod
    def _check_bin(bin_path):
        # if absolute path is given, check if exits and executable
        if os.path.isabs(bin_path):
            if os.path.exists(bin_path) and os.access(bin_path, os.X_OK):
                return bin_path

        # check module dir
        local_bin = os.path.join(__MODULE_DIR__, bin_path)
        if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
            return local_bin

        # check system path
        for path in os.environ['PATH'].split(os.pathsep):
            candidate_path = os.path.join(path, bin_path)
            if (os.path.exists(candidate_path)
                    and os.access(candidate_path, os.X_OK)):
                return candidate_path

        raise FileNotFoundError('AVL not found or not executable, '
                                'check config file')

    def _create_temp_dir(self):
        self._temp_dir = TemporaryDirectory(prefix='avl_')

    def _clean_temp_dir(self):
        self.temp_dir.cleanup()

    def _write_geometry(self):
        self.model_file = self._get_base_name() + '.avl'
        model_path = os.path.join(self.temp_dir.name, self.model_file)
        with open(model_path, 'w') as avl_file:
            avl_file.write(self.geometry.create_input())

    def _copy_airfoils(self):
        airfoil_names = self.geometry.get_external_airfoil_names()
        current_dir = os.getcwd()
        for airfoil in airfoil_names:
            airfoil_path = os.path.join(current_dir, airfoil)
            shutil.copy(airfoil_path, self.temp_dir.name)

    def _write_cases(self):
        # AVL is limited to 25 cases
        if len(self.cases) > 25:
            raise InputError('Number of cases is larger than '
                             'the supported maximum of 25.')

        self.case_file = self._get_base_name() + '.case'
        case_file_path = os.path.join(self.temp_dir.name, self.case_file)

        with open(case_file_path, 'w') as case_file:
            for idx, case in enumerate(self.cases):
                case.number = idx + 1  # Case numbers start at 1
                case_file.write(case.create_input())

    def _get_default_run_keys(self):

        run = "load {0}\n".format(self.model_file)
        run += "case {0}\n".format(self.case_file)
        run += "oper\n"

        for case in self.cases:
            run += "{0}\nx\n".format(case.number)
            for output in self.config['output']:
                ext = self.OUTPUTS[output]
                out_file = self._get_output_file(case, ext)
                run += "{cmd}\n{file}\n".format(cmd=ext,
                                                file=out_file)

        run += "\nquit\n"

        return run

    def _get_output_file(self, case, ext):
        out_file = "{base}-{case}.{ext}".format(base=self._get_base_name(),
                                                case=case.number,
                                                ext=ext)
        return out_file

    def _read_results(self):

        results = dict()
        for case in self.cases:
            results[case.name] = dict()
            for output in self.config['output']:
                ext = self.OUTPUTS[output]
                file_name = self._get_output_file(case, ext)
                file_path = os.path.join(self.temp_dir.name, file_name)
                reader = OutputReader(file_path=file_path)
                results[case.name][output] = reader.get_content()

        return results

    def _run_analysis(self):

        if not self._calculated:
            self._write_geometry()
            self._copy_airfoils()

            if self.cases is not None:
                self._write_cases()

            if self.run_keys is None:
                run_keys = self._get_default_run_keys()
            else:
                run_keys = self.run_keys

            process = self._get_avl_process()
            process.communicate(input=run_keys.encode())
            self._calculated = True

    def _get_avl_process(self):
        stdin = subprocess.PIPE
        stdout = open(os.devnull, 'w') if not self.config[
            'show_stdout'] else None
        working_dir = self.temp_dir.name

        # Buffer size = 0 required for direct stdin/stdout access
        return subprocess.Popen(args=[self.config['avl_bin']],
                                stdin=stdin,
                                stdout=stdout,
                                bufsize=0,
                                cwd=working_dir)

    def get_results(self):
        if self._results is None:
            self._run_analysis()
            self._results = self._read_results()

        return self._results

    def reset(self):
        self._temp_dir.cleanup()
        self._temp_dir = None
        self._results = None
        self._calculated = False

    def show_geometry(self):
        self._write_geometry()
        run = "load {0}\n".format(self.model_file)
        run += "oper\ng\n"

        process = self._get_avl_process()

        def open_fn(): process.stdin.write(run.encode())

        def close_fn(): process.stdin.write("\n\nquit\n".encode())

        tk_root = tk.Tk()
        app = CloseWindow(on_open=open_fn, on_close=close_fn, master=tk_root)
        app.mainloop()


class OutputReader(object):

    SURFACE_RE = 'Surface\s+#\s*\d+\s+(.*)'
    STRIP_RE = 'Strip\s+#\s+(\d+)\s+'

    """Reads AVL output files. Type is determined based on file extension"""
    def __init__(self, file_path):

        self.path = file_path
        _, self.extension = os.path.splitext(file_path)

    def get_content(self):
        with open(self.path, 'r') as out_file:
            content = out_file.readlines()

        if self.extension == '.ft':
            result = self._read_totals(content)
        elif self.extension == '.fn':
            result = self._read_surface_forces(content)
        elif self.extension == '.fs':
            result = self._read_strip_forces(content)
        elif self.extension == '.fe':
            result = self._read_element_forces(content)
        elif self.extension == '.st':
            result = self._read_stability_derivatives(content)
        elif self.extension == '.sb':
            result = self._read_body_derivatives(content)
        elif self.extension == '.hm':
            result = self._read_hinge_moments(content)
        else:
            print("Unknown output file: {0}".format(self.path))
            result = []
        return result

    @staticmethod
    def _remove_ydup(name):
        return re.sub('\(YDUP\)', '', name).strip()

    @staticmethod
    def _get_vars(content):
        # Search for "key = value" tuples and store in a dictionary
        result = dict()
        for name, value in re.findall('(\S+)\s+=\s+([-\dE.]+)',
                                      ''.join(content)):
            result[name] = float(value)
        return result

    @staticmethod
    def _extract_header(table_content):
        # Get headers (might contain spaces, but no double spaces)
        header = re.split('\s{2,}', table_content[0])
        # remove starting and trailing spaces, empty strings and EOL
        header = list(filter(None, [s.strip() for s in header]))
        # ignore first column
        header = header[1:]
        return header

    @staticmethod
    def _split_lines(lines, re_str):
        splitted = dict()
        name = None
        for line in lines:
            match = re.search(re_str, line)
            if match is not None:
                name = match.group(1).strip()
                splitted[name] = [line]
            elif name is not None:
                splitted[name].append(line)

        return splitted

    def _read_totals(self, content):
        return self._get_vars(content)

    @staticmethod
    def _get_table_start_end(content, re_str):
        start_line, end_line = None, None
        for line_nr, line in enumerate(content):
            if re.search(re_str, line) is not None:
                start_line = line_nr

            # Find end of table based on the empty line
            if (start_line is not None
                    and (line.strip() == '' or line_nr == len(content)-1)):
                end_line = line_nr
                break

        return start_line, end_line

    def _read_surface_forces(self, content):

        # Find start of table based on header
        start_line, end_line = self._get_table_start_end(content,
                                                         '(n\s+Area\s+CL)')
        table_content = content[start_line:end_line]

        surface_data = self._process_surface_table(table_content)
        return surface_data

    def _process_surface_table(self, table_content):
        header = self._extract_header(table_content)
        surface_data = dict()
        for line in table_content[1:]:
            line_data = self._get_line_values(line)

            # ignore first column
            line_data = line_data[1:]

            name = re.findall('(\D+)(?=\n)', line)[0].strip()

            if len(line_data) != len(header):
                raise ParseError("Incorrect table format in file {0}"
                                 .format(self.path))

            # Create results dictionary
            # Combine surfaces labeled with (YDUP)
            if '(YDUP)' in name:
                base_name = self._remove_ydup(name)
                base_data = surface_data[base_name]
                all_data = zip(header, [base_data[key]
                                        for key in header], line_data)
                surface_data[base_name] = {key: base_value + value
                                           for key, base_value, value
                                           in all_data}
            else:
                surface_data[name] = {key: value
                                      for key, value in zip(header,
                                                            line_data)}
        return surface_data

    def _read_strip_forces(self, content):

        table_content = self._get_surface_tables(content)
        strip_results = self.process_surface_tables(table_content)

        return strip_results

    def process_surface_tables(self, table_content):
        strip_results = dict()
        # sort so (YDUP) surfaces are always behind the main surface
        for name in sorted(table_content.keys()):
            header = self._extract_header(table_content[name])

            # check for YDUP
            if '(YDUP)' in name:
                result_name = self._remove_ydup(name)
            else:
                result_name = name
                strip_results[result_name] = {key: [] for key in header}

            for data_line in table_content[name][1:-1]:
                # Convert to floats
                values = self._get_line_values(data_line)
                # ignore first column
                values = values[1:]
                for key, value in zip(header, values):
                    strip_results[result_name][key].append(value)
        return strip_results

    def _get_surface_tables(self, content):
        table_lines = self._split_lines(content, self.SURFACE_RE)
        table_dict = dict()
        for name, lines in list(table_lines.items()):
            re_str = '(j\s+Yle\s+Chord)'
            start_line, end_line = self._get_table_start_end(lines, re_str)
            if start_line is not None and end_line is not None:
                table_dict[name] = lines[start_line:end_line]
        return table_dict

    @staticmethod
    def _get_line_values(data_line):
        values = [float(s) for s in re.findall('([-\dE.]+)', data_line)]
        return values

    def _read_element_forces(self, content):
        data_tables = self._get_element_tables(content)
        element_results = self._process_element_tables(data_tables)

        return element_results

    def _get_element_tables(self, content):
        # tables split by surface
        surface_tables = self._split_lines(content, self.SURFACE_RE)
        data_tables = dict()
        for surface_name, surface_lines in list(surface_tables.items()):
            # tables split by strip
            strip_tables = self._split_lines(surface_lines,
                                             self.STRIP_RE)
            data_tables[surface_name] = dict()
            for strip_name, strip_lines in list(strip_tables.items()):
                start_line, end_line = (self._get_table_start_end(
                    strip_lines, '(I\s+X\s+Y\s+Z)'))
                data = strip_lines[start_line:end_line]
                data_tables[surface_name][int(strip_name)] = data
        return data_tables

    def _process_element_tables(self, data_tables):
        element_results = dict()
        # sort so (YDUP) surfaces are always behind the main surface
        for name in sorted(data_tables.keys()):
            # check for YDUP
            if '(YDUP)' in name:
                result_name = self._remove_ydup(name)
            else:
                result_name = name
                element_results[result_name] = dict()

            for strip in data_tables[name].keys():
                header = self._extract_header(data_tables[name][strip])
                # create empty lists
                element_results[result_name][strip] = {key: []
                                                       for key in header}
                for data_line in data_tables[name][strip][1:]:
                    values = self._get_line_values(data_line)
                    # ignore first column
                    values = values[1:]
                    for key, value in zip(header, values):
                        element_results[result_name][strip][key].append(value)
        return element_results

    def _read_stability_derivatives(self, content):

        idx = [i for (i, line) in enumerate(content)
               if 'Stability-axis derivatives...' in line or
               'Neutral point' in line]

        all_vars = self._get_vars(content[idx[0]:idx[1]+1])
        controls = self._get_controls(content)
        all_vars = self._replace_controls(all_vars, controls)

        return all_vars

    @staticmethod
    def _get_controls(content):
        controls = re.findall('(\S+)\s+(d\d+)', ''.join(content))
        return {number: name for (name, number) in controls}

    @staticmethod
    def _replace_controls(var_dict, controls):
        # replace d# with control name
        new_dict = var_dict.copy()
        for key in var_dict.keys():
            match = re.search('d\d+', key)
            if match is not None:
                d = match.group(0)
                name = controls[d]
                new_key = re.sub(d, name, key)
                new_dict[new_key] = new_dict[key]
                new_dict.pop(key)
        return new_dict

    def _read_body_derivatives(self, content):
        idx = [i for (i, line) in enumerate(content)
               if 'Geometry-axis derivatives...' in line]

        all_vars = self._get_vars(content[idx[0]:])
        controls = self._get_controls(content)
        all_vars = self._replace_controls(all_vars, controls)

        return all_vars

    @staticmethod
    def _read_hinge_moments(content):
        results = dict()
        for line in content:
            match = re.search('(\w+)\s+([-\dE.]+)', line)
            if match is not None:
                results[match.group(1)] = float(match.group(2))
        return results


class CloseWindow(tk.Frame):
    def __init__(self, on_open=None, on_close=None, master=None):
        # On Python 2, tk.Frame is an old-style class
        tk.Frame.__init__(self, master)

        # Make sure window is on top
        master.call('wm', 'attributes', '.', '-topmost', '1')
        self.pack()
        self._on_open = on_open
        self._on_close = on_close
        self.close_button = self.create_button()

    def create_button(self):
        # add quit method to button press
        def on_close_wrapper():
            if self._on_close is not None:
                self._on_close()
            top = self.winfo_toplevel()
            top.destroy()
        close_button = tk.Button(self, text="Close",
                                 command=on_close_wrapper)
        close_button.pack()
        return close_button

    def mainloop(self, n=0):
        if self._on_open is not None:
            self._on_open()
        tk.Frame.mainloop(self, n)


class InputError(Exception):
    pass


class ParseError(Exception):
    pass
