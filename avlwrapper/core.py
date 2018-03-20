#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" AVL Wrapper core classes
"""
import configparser
import os
import re
import subprocess
import tempfile

__author__ = "Reno Elmendorp"
__status__ = "Development"


__MODULE_DIR__ = os.path.dirname(__file__)


class Input(object):
    def create_input(self):
        raise NotImplementedError


class Parameter(Input):

    def __init__(self, name, value, constraint=None):

        self.name = name
        self.value = value

        if constraint is None:
            self.constraint = name
        else:
            self.constraint = constraint

    def create_input(self):
        return " {0:<12} -> {1:<12} = {2}\n".format(self.name, self.constraint, self.value)


class State(Input):

    def __init__(self, name, value, unit=''):
        self.name = name
        self.value = value
        self.unit = unit

    def create_input(self):
        return " {0:<10} = {1:<10} {2}\n".format(self.name, self.value, self.unit)


class Case(Input):

    CASE_PARAMETERS = {'alpha': 'alpha', 'beta': 'beta', 'roll_rate': 'pb/2V', 'pitch_rate': 'qc/2V',
                       'yaw_rate': 'rb/2V'}

    VALID_CONSTRAINTS = ['alpha', 'beta', 'pb/2V', 'qc/2V', 'rb/2V', 'CL', 'CY', 'Cl', 'Cm', 'Cn']

    CASE_STATES = {'alpha': (0.0, 'deg'), 'beta': (0.0, 'deg'),
                   'pb/2V': (0.0, ''), 'qc/2V': (0.0, ''), 'rb/2V': (0.0, ''),
                   'CL': (0.0, ''), 'CDo': (0.0, ''),
                   'bank': (0.0, 'beg'), 'elevation': (0.0, 'deg'), 'heading': (0.0, 'deg'),
                   'Mach': (0.0, ''), 'velocity': (0.0, 'm/s'),
                   'density': (1.225, 'kg/m^3'), 'grav.acc.': (9.81, 'm/s^2'),
                   'turn_rad.': (0.0, 'm'), 'load_fac.': (0.0, ''),
                   'X_cg': (0.0, 'm'), 'Y_cg': (0.0, 'm'), 'Z_cg': (0.0, 'm'),
                   'mass': (1.0, 'kg'),
                   'Ixx': (1.0, 'kg-m^2'), 'Iyy': (1.0, 'kg-m^2'), 'Izz': (1.0, 'kg-m^2'),
                   'Ixy': (0.0, 'kg-m^2'), 'Iyz': (0.0, 'kg-m^2'), 'Izx': (0.0, 'kg-m^2'),
                   'visc CL_a': (0.0, ''), 'visc CL_u': (0.0, ''), 'visc CM_a': (0.0, ''), 'visc CM_u': (0.0, '')}

    def __init__(self, name, **kwargs):

        self.name = name
        self.number = 1
        self.parameters = self._set_default_parameters()
        self.states = self._set_default_states()

        self.controls = []
        for key, value in kwargs.items():
            if isinstance(value, Parameter):
                self.parameters[key] = value
            elif key in self.CASE_PARAMETERS.keys():
                param_str = self.CASE_PARAMETERS[key]
                self.parameters[param_str].value = value
            else:
                param_str = key
                self.controls.append(key)
                self.parameters[param_str] = Parameter(name=param_str, value=value)

    def _set_default_parameters(self):
        return {name: Parameter(name=name, constraint=name, value=0.0) for _, name in self.CASE_PARAMETERS.items()}

    def _set_default_states(self):
        return {key: State(name=key, value=value[0], unit=value[1]) for key, value in self.CASE_STATES.items()}

    def _check(self):
        for param in self.parameters.values():
            if param.constraint not in self.VALID_CONSTRAINTS and param.constraint not in self.controls:
                raise InputError("Invalid constraint on parameter: {0}.".format(param.name))

        for state in self.states.values():
            if state.name not in self.CASE_STATES.keys():
                raise InputError("Invalid state variable: {0}".format(state.name))

    def create_input(self):
        self._check()

        case_str = " " + "-"*45 + "\n Run case {0:<2}:  {1}\n\n".format(self.number, self.name)

        for param in self.parameters.values():
            case_str += param.create_input()

        case_str += "\n"

        for state in self.states.values():
            case_str += state.create_input()

        return case_str


class Session(object):

    CONFIG_FILE = os.path.join(__MODULE_DIR__, 'config.cfg')
    OUTPUTS = {'Totals': 'ft', 'SurfaceForces': 'fn', 'StripForces': 'fs', 'ElementForces': 'fe',
               'StabilityDerivatives': 'st', 'BodyAxisDerivatives': 'sb', 'HingeMoments': 'hm'}

    def __init__(self, geometry, cases=None, run_keys=None):
        self._temp_dir = None

        if (cases is None) and (run_keys is None):
            raise InputError("Either cases or run keys should be provided.")

        self.config = self._read_config(self.CONFIG_FILE)

        self.geometry = geometry
        self.base_name = geometry.name
        self.cases = cases
        self.run_keys = run_keys

        self._calculated = False
        self._results = None

    def __del__(self):
        if self._temp_dir is not None:
            self._temp_dir.cleanup()

    @property
    def temp_dir(self):
        if self._temp_dir is None:
            self._create_temp_dir()
        return self._temp_dir

    def _read_config(self, file):
        config = configparser.ConfigParser()
        config.read(file)

        settings = dict()
        settings['avl_bin'] = config['environment']['Executable']

        # check if avl binary exists
        self._check_bin(settings['avl_bin'])

        # Output files
        settings['output'] = []
        for output in self.OUTPUTS.keys():
            if config['output'][output] == 'yes':
                settings['output'].append(output)

        return settings

    @staticmethod
    def _check_bin(binary):
        error_msg = 'AVL not found or not executable, check {}config.cfg'.format(__MODULE_DIR__ + os.sep)
        if os.path.isabs(binary):
            if not os.path.exists(binary) or not os.access(binary, os.X_OK):
                raise FileNotFoundError(error_msg)
        else:
            if not any(os.access(os.path.join(path, binary), os.X_OK)
                       for path in os.environ['PATH'].split(os.pathsep)):
                raise FileNotFoundError(error_msg)
        return True

    def _create_temp_dir(self):
        self._temp_dir = tempfile.TemporaryDirectory(prefix='avl_')

    def _clean_temp_dir(self):
        self.temp_dir.cleanup()

    def _write_geometry(self):
        self.model_file = self.base_name + '.avl'
        with open(os.path.join(self.temp_dir.name, self.model_file), 'w') as avl_file:
            avl_file.write(self.geometry.create_input())

    def _write_cases(self):
        # AVL is limited to 25 cases
        if len(self.cases) > 25:
            raise InputError('Number of cases is larger than the supported maximum of 25.')

        self.case_file = self.base_name + '.case'
        with open(os.path.join(self.temp_dir.name, self.case_file), 'w') as case_file:
            for idx, case in enumerate(self.cases):
                case.number = idx + 1  # Case numbers start at 1
                case_file.write(case.create_input())

    def _get_default_run_keys(self):

        run = "load {0}\n".format(self.model_file)
        run += "case {0}\n".format(self.case_file)
        run += "oper\n"

        for idx, _ in enumerate(self.cases):
            case_id = idx + 1  # cases start at 1
            run += "{0}\nx\n".format(case_id)
            for output in self.config['output']:
                ext = self.OUTPUTS[output]
                run += "{out}\n{base}-{case}.{out}\n".format(out=ext,
                                                             base=self.base_name,
                                                             case=case_id)

        run += "\nquit\n"

        return run

    def _read_results(self):

        results = dict()
        for case in self.cases:
            results[case.name] = dict()
            for output in self.config['output']:
                ext = self.OUTPUTS[output]
                file_name = '{base}-{case}.{out}'.format(out=ext,
                                                         base=self.base_name,
                                                         case=case.number)
                reader = OutputReader(file_path=os.path.join(self.temp_dir.name, file_name))
                results[case.name][output] = reader.get_content()

        return results

    def _run_avl(self):

        if not self._calculated:
            self._write_geometry()

            if self.cases is not None:
                self._write_cases()

            if self.run_keys is None:
                run_keys = self._get_default_run_keys()
            else:
                run_keys = self.run_keys

            avl_proc = subprocess.Popen([self.config['avl_bin']], stdin=subprocess.PIPE, cwd=self.temp_dir.name)
            avl_proc.communicate(input=run_keys.encode())
            self._calculated = True

    def get_results(self):
        if self._results is None:
            self._run_avl()
            self._results = self._read_results()

        return self._results

    def reset(self):
        self._temp_dir.cleanup()
        self._temp_dir = None
        self._results = None
        self._calculated = False


class OutputReader(object):

    def __init__(self, file_path):

        self.path = file_path
        _, self.extension = os.path.splitext(file_path)

    def get_content(self):
        with open(self.path, 'r') as file:
            content = file.readlines()
        if self.extension == '.ft':
            return self._read_totals(content)
        elif self.extension == '.fn':
            return self._read_surface_forces(content)
        elif self.extension == '.fs':
            return self._read_strip_forces(content)
        elif self.extension == '.fe':
            return self._read_element_forces(content)
        elif self.extension == '.st':
            return self._read_stability_derivatives(content)
        elif self.extension == '.sb':
            return self._read_body_derivatives(content)
        elif self.extension == '.hm':
            return self._read_hinge_moments(content)
        else:
            print("Unknown output file: {0}".format(self.path))

    @staticmethod
    def _get_vars(content):
        # Search for "key = value" tuples in the content lines and store in a dictionary
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

    def _read_totals(self, content):
        return self._get_vars(content)

    def _read_surface_forces(self, content):
        # Find data table
        start_line, end_line = None, None
        for line_nr, line in enumerate(content):
            # Find start of table based on header
            if re.search('(n\s+Area\s+CL)', line) is not None:
                start_line = line_nr

            # Find end of table based on the empty line
            if start_line is not None and line.strip() == '':
                end_line = line_nr
                break

        if start_line is None or end_line is None:
            ParseError("Table not found in file {0}".format(self.path))

        table_content = content[start_line:end_line]
        header = self._extract_header(table_content)

        surface_data = dict()

        for line in table_content[1:]:
            line_data = self._get_line_values(line)

            # ignore first column
            line_data = line_data[1:]

            name = re.findall('(\D+)(?=\n)', line)[0].strip()

            if len(line_data) != len(header):
                ParseError("Incorrect table format in file {0}".format(self.path))

            # Create results dictionary
            # Combine surfaces labeled with (YDUP)
            if '(YDUP)' in name:
                base_name = re.sub('\(YDUP\)', '', name).strip()
                base_data = surface_data[base_name]
                surface_data[base_name] = {key: base_value + value
                                           for key, base_value, value in zip(header,
                                                                             [base_data[key] for key in header],
                                                                             line_data)}
            else:
                surface_data[name] = {key: value for key, value in zip(header,
                                                                       line_data)}

        return surface_data

    def _read_strip_forces(self, content):

        table_content = dict()
        start_line, end_line, surface_name = None, None, None
        for line_nr, line in enumerate(content):

            # Find surface name
            match = re.search('Surface\s+#\s*\d+\s+(.*)', line)
            if match is not None:
                surface_name = match.group(1).strip()

            # Find start of table based on header
            if re.search('(j\s+Yle\s+Chord)', line) is not None:
                start_line = line_nr

            # Find end of table based on the empty line
            if start_line is not None and line.strip() == '':
                end_line = line_nr

                # Check if surface name is defined
                if surface_name is None:
                    ParseError("Unexpected file structure {0}".format(self.path))

                table_content[surface_name] = content[start_line:end_line]

                # Reset start_line, end_line and name
                start_line, end_line, surface_name = None, None, None

        strip_results = dict()

        for name in table_content.keys():
            header = self._extract_header(table_content[name])

            # check for YDUP
            if '(YDUP)' in name:
                result_name = re.sub('\(YDUP\)', '', name).strip()
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

    @staticmethod
    def _get_line_values(data_line):
        values = [float(s) for s in re.findall('([-\dE.]+)', data_line)]
        return values

    def _read_element_forces(self, content):

        data_tables = dict()
        start_line, end_line, surface_name, strip_nr = None, None, None, None
        for line_nr, line in enumerate(content):

            # Find surface name
            match = re.search('Surface\s+#\s*\d+\s+(.*)', line)
            if match is not None:
                surface_name = match.group(1).strip()
                data_tables[surface_name] = dict()

            # Find strip number
            match = re.search('Strip\s+#\s+(\d+)\s+', line)
            if match is not None:
                strip_nr = int(match.group(1).strip())

            # Find start of table based on header
            if re.search('(I\s+X\s+Y\s+Z)', line) is not None:
                start_line = line_nr

            # Find end of table based on the empty line
            if start_line is not None and line.strip() == '':
                end_line = line_nr

                # Check if surface name is defined
                if surface_name is None:
                    ParseError("Unexpected file structure {0}".format(self.path))
                # Check if strip number is defined
                if strip_nr is None:
                    ParseError("Unexpected file structure {0}".format(self.path))

                data_tables[surface_name][strip_nr] = content[start_line:end_line]

                # Reset start_line, end_line and number
                start_line, end_line, strip_nr = None, None, None

        element_results = dict()
        for name in data_tables.keys():

            # check for YDUP
            if '(YDUP)' in name:
                result_name = re.sub('\(YDUP\)', '', name).strip()
            else:
                result_name = name
                element_results[result_name] = dict()

            for strip in data_tables[name].keys():
                header = self._extract_header(data_tables[name][strip])
                element_results[result_name][strip] = {key: [] for key in header}
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
        return {number: name for (name, number) in re.findall('(\S+)\s+(d\d+)', ''.join(content))}

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


class InputError(Exception):
    pass


class ParseError(Exception):
    pass
