from itertools import product

from avlwrapper import Case


def create_sweep_cases(base_case, parameters):
    """Creates cases for a parameter sweep

    :param base_case: base Case object
    :type base_case: Case

    :param parameters: list of a dict with keys: name and values
    :type parameters: collections.Sequence
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

    :param cases: list of AVL cases to partition
    :type cases: collections.Sequence

    :param n_cases: (optional) number of cases per partition
    :type n_cases: int
    """

    return _partitioned(cases, n_cases)


# From: https://gist.github.com/renoelmendorp/09e397297ffaef2af81b941d2ef4d321
def _partitioned(l, n):
    for idx in range(0, len(l), n):
        yield l[idx:idx + n]
