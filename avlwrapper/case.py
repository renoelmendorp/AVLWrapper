from avlwrapper.general import Input, InputError


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
            if key in self.CASE_PARAMETERS.keys():
                param_str = self.CASE_PARAMETERS[key]
            else:
                param_str = key
                self.controls.append(key)

            self.parameters[param_str] = value

    def _set_default_parameters(self):
        return [Parameter(name=name, constraint=name, value=0.0) for _, name in self.CASE_PARAMETERS.items()]

    def _set_default_states(self):
        return [State(name=key, value=value[0], unit=value[1]) for key, value in self.CASE_STATES.items()]

    def _check(self):
        for param in self.parameters:
            if param.constraint not in self.VALID_CONSTRAINTS and param.constraint not in self.controls:
                raise InputError("Invalid constraint on parameter: {0}.".format(param.name))

        for state in self.states:
            if state.name not in self.CASE_STATES.keys():
                raise InputError("Invalid state variable: {0}".format(state.name))

    def create_input(self):
        self._check()

        case_str = " " + "-"*45 + "\n Run case {0:<2}:  {1}\n\n".format(self.number, self.name)

        for param in self.parameters:
            case_str += param.create_input()

        case_str += "\n"

        for state in self.states:
            case_str += state.create_input()

        return case_str


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
