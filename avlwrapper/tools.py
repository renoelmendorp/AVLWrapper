from itertools import product

from avlwrapper import Case


def create_sweep_cases(base_case, parameters):
    """Creates cases for a parameter sweep

    :param avlwrapper.Case base_case: base Case object
    :param typing.Sequence parameters: list of a dict with keys: name and values
    """

    # ensure input is a list if a dict (only one parameter) is given
    if isinstance(parameters, dict):
        parameters = [parameters]

    parameter_names = [p['name'] for p in parameters]
    parameter_values = product(*[p['values']
                                 for p in parameters])

    cases = []
    for idx, values in enumerate(parameter_values):
        all_params = dict(zip(parameter_names, values))
        case = Case(name="{}-{}".format(base_case.name, idx), **all_params)
        cases.append(case)

    return cases


def partitioned_cases(cases, n_cases=25):
    """Partitions cases

    :param typing.Sequence cases: list of AVL cases to partition
    :param int n_cases: (optional) number of cases per partition
    """

    # From: https://gist.github.com/renoelmendorp/09e397297ffaef2af81b941d2ef4d321
    for idx in range(0, len(cases), n_cases):
        yield cases[idx:idx + n_cases]
