""" AVL Wrapper session and input classes
"""
import os
import re
import shutil
import subprocess
import sys

from .config import default_config
from .output import OutputReader

if not sys.version_info[0] < 3: # Python 3
    import tkinter as tk
    from tempfile import TemporaryDirectory

else:
    import Tkinter as tk
    import tempfile

    # simple class which provides TemporaryDirectory-esque functionality
    class TemporaryDirectory(object):
        def __init__(self, suffix='', prefix='', dir=None):
            self.name = tempfile.mkdtemp(suffix=suffix,
                                         prefix=prefix,
                                         dir=dir)

        def cleanup(self):
            shutil.rmtree(self.name)


class Input(object):
    def create_input(self):
        raise NotImplementedError


class Parameter(Input):
    """Parameter used in the case definition"""
    def __init__(self, name, value, constraint=None):
        """
        :param name: Parameter name, if not in Case.CASE_PARAMETERS, it's
            assumed to by a control name
        :type name: str

        :param value: Parameter value
        :type value: float

        :param constraint: Parameter constraint, see Case.VALID_CONSTRAINTS
        :type constraint: str or None
        """
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

    CASE_STATES = {'alpha': ('alpha', 0.0, 'deg'),
                   'beta': ('beta', 0.0, 'deg'),
                   'pb2V': ('pb/2V', 0.0, ''), 'qc2V': ('qc/2V', 0.0, ''),
                   'rb2V': ('rb/2V', 0.0, ''), 'CL': ('CL', 0.0, ''),
                   'cd_p': ('CDo', None, ''),
                   'bank': ('bank', 0.0, 'deg'),
                   'elevation': ('elevation', 0.0, 'deg'),
                   'heading': ('heading', 0.0, 'deg'),
                   'mach': ('Mach', None, ''),
                   'velocity': ('velocity', 0.0, 'm/s'),
                   'density': ('density', 1.225, 'kg/m^3'),
                   'gravity': ('grav.acc.', 9.81, 'm/s^2'),
                   'turn_rad': ('turn_rad.', 0.0, 'm'),
                   'load_fac': ('load_fac.', 0.0, ''),
                   'X_cg': ('X_cg', None, 'm'),
                   'Y_cg': ('Y_cg', None, 'm'),
                   'Z_cg': ('Z_cg', None, 'm'),
                   'mass': ('mass', 1.0, 'kg'),
                   'Ixx': ('Ixx', 1.0, 'kg-m^2'),
                   'Iyy': ('Iyy', 1.0, 'kg-m^2'),
                   'Izz': ('Izz', 1.0, 'kg-m^2'),
                   'Ixy': ('Ixy', 0.0, 'kg-m^2'),
                   'Iyz': ('Iyz', 0.0, 'kg-m^2'),
                   'Izx': ('Izx', 0.0, 'kg-m^2'),
                   'visc_CL_a': ('visc CL_a', 0.0, ''),
                   'visc_CL_u': ('visc CL_u', 0.0, ''),
                   'visc_CM_a': ('visc CM_a', 0.0, ''),
                   'visc_CM_u': ('visc CM_u', 0.0, '')}

    def __init__(self, name, **kwargs):
        """
        :param name: case name
        :type name: str

        :param kwargs: key-value pairs
            keys should be Case.CASE_PARAMETERS, Case.CASE_STATES or a control
            values should be a numeric value or a Parameter object
        """
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
                    name = self.CASE_STATES[key][0]
                    if name in self.VALID_CONSTRAINTS:
                        msg = "{} will be changed on runtime, specify " \
                              "constraint to set this parameter.".format(name)
                        print(msg)
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
        return {key: State(name=value[0], value=value[1], unit=value[2])
                for key, value in self.CASE_STATES.items()}

    def _check(self):
        self._check_parameters()
        self._check_states()

    def _check_states(self):
        for key in self.states.keys():
            if key not in self.CASE_STATES.keys():
                raise InputError("Invalid state variable: {0}"
                                 .format(key))

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

    def __init__(self, geometry=None, cases=None,
                 run_keys=None, config=default_config):
        """
        :param geometry: AVL geometry
        :type geometry: Geometry

        :param cases: Cases to include in input files
        :type cases: collections.Sequence[Case] or None

        :param run_keys: (optional) run keys (if not provided, all cases will
            be evaluated
        :type run_keys: str
        
        :param config: (optional) dictionary containing setting
        :type config: Configuration
        """

        self._temp_dir = None
        self.config = config

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

    def _create_temp_dir(self):
        self._temp_dir = TemporaryDirectory(prefix='avl_')

    def _clean_temp_dir(self):
        self.temp_dir.cleanup()

    @property
    def _output(self):
        return {k: v for k, v in self.OUTPUTS.items()
                if k.lower() in self.config['output']}

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
            
    def _prepare_cases(self):
        # If not set, make sure XYZref, Mach and CD0 default to geometry input
        geom_defaults = {'X_cg': self.geometry.point[0],
                         'Y_cg': self.geometry.point[1],
                         'Z_cg': self.geometry.point[2],
                         'mach': self.geometry.mach,
                         'cd_p': self.geometry.cd_p}
        
        for case in self.cases:
            for key, val in geom_defaults.items():
                if case.states[key].value is None:
                    case.states[key].value = val

    def _write_cases(self):
        self._prepare_cases()
        
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
            for _, ext in self._output.items():
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
            for output, ext in self._output.items():
                file_name = self._get_output_file(case, ext)
                file_path = os.path.join(self.temp_dir.name, file_name)
                reader = OutputReader(file_path=file_path)
                results[case.name][output] = reader.get_content()

        return results

    def _run_analysis(self, run_keys=None):

        if not self._calculated:
            self._write_geometry()
            self._copy_airfoils()

            if self.cases is not None:
                self._write_cases()

            if run_keys is None:
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

    def _run_with_close_window(self, run):
        process = self._get_avl_process()

        def open_fn(): process.stdin.write(run.encode())

        def close_fn(): process.stdin.write("\n\nquit\n".encode())

        tk_root = tk.Tk()
        app = _CloseWindow(on_open=open_fn, on_close=close_fn, master=tk_root)
        app.mainloop()

    def show_geometry(self):
        self._write_geometry()
        run = "load {0}\n".format(self.model_file)
        run += "oper\ng\n"

        self._run_with_close_window(run)

    def show_trefftz_plot(self, case_number):
        self._write_geometry()
        self._write_cases()

        run = "load {}\n".format(self.model_file)
        run += "case {}\n".format(self.case_file)
        run += "oper\n"
        run += "{}\nx\n".format(case_number)
        run += "t\n"

        self._run_with_close_window(run)


class _CloseWindow(tk.Frame):
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
