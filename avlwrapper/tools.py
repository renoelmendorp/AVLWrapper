#!/usr/bin/env python3

from itertools import product

from avlwrapper import Case


class ParameterSweep(object):
    """Helper class to generate cases to evaluate parameter sweeps"""
    def __init__(self, base_case, parameters):
        """
        :param base_case: default case
        :type base_case: Case

        :param parameters: list of dictionaries with 'name' and 'value' keys
        :type parameters: collections.Sequence[dict]
        """
        self.base_case = base_case
        self.parameters = parameters

    @property
    def cases(self):
        if isinstance(self.parameters, dict):
            parameter_names = [self.parameters['name']]
            parameter_values = [self.parameters['values']]
        else:
            parameter_names = [p['name'] for p in self.parameters]
            parameter_values = product(*[p['values']
                                         for p in self.parameters])

        cases = []
        for idx, values in enumerate(parameter_values):
            all_params = dict(zip(parameter_names, values))
            case = Case(name="{}-{}".format(self.base_case.name, idx),
                        **all_params)
            cases.append(case)

        return cases
