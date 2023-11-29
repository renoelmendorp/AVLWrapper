import copy
import itertools
from itertools import product
import re


FLOATING_POINT_PATTERN = r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"


def create_sweep_cases(base_case, parameters):
    """Creates cases for a parameter sweep

    :param avlwrapper.Case base_case: base Case object
    :param typing.Sequence parameters: list of a dict with keys: name and values

    Example:
    ```
    cases = create_sweep_cases(base_case=cruise_case,
                               parameters=[{'name':   'alpha',
                                            'values': list(range(15))},
                                           {'name':   'beta',
                                            'values': list(range(-5, 6))}])
    ```
    """

    # ensure input is a list if a dict (only one parameter) is given
    if isinstance(parameters, dict):
        parameters = [parameters]

    parameter_names = [p["name"] for p in parameters]
    parameter_values = product(*[p["values"] for p in parameters])

    cases = []
    for idx, values in enumerate(parameter_values):
        all_params = dict(zip(parameter_names, values))
        case = copy.deepcopy(base_case)
        case.name = "{}-{}".format(base_case.name, idx)
        case.update(**all_params)
        cases.append(case)

    return cases


def partitioned_cases(cases, n_cases=25):
    """Partitions cases

    :param typing.Sequence cases: list of AVL cases to partition
    :param int n_cases: (optional) number of cases per partition
    """

    for idx in range(0, len(cases), n_cases):
        yield cases[idx : idx + n_cases]


def show_image(image_path, rotate=True):
    import numpy as np
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    image = mpimg.imread(image_path)
    if rotate:
        image = np.rot90(image, k=3)

    plt.figure()
    plt.imshow(image)
    plt.axis("off")
    plt.show()


def get_vars(lines):
    # Search for "key = value" tuples and store in a dictionary
    result = dict()
    for name, value in re.findall(
        rf"(\S+)\s+=\s*({FLOATING_POINT_PATTERN})", "\n".join(lines)
    ):
        result[name] = float(value)
    return result


def line_to_floats(line, limit=None):
    elements = line.split()
    counter = itertools.count() if limit is None else range(limit)

    lst = []
    for el, _ in zip(elements, counter):
        if el.startswith("!") or el.startswith("#"):  # rest of the line is a comment
            break
        lst.append(float(el))
    return lst


def multi_split(str_in, *seps):
    str_lst = [str_in]
    for sep in seps:
        new_lst = []
        for s in str_lst:
            new_lst.extend(s.split(sep))
        str_lst = new_lst
    # remove empty strings
    str_lst = list(filter(lambda s: s, str_lst))
    return str_lst


def line_is_not_empty(line):
    return line != ""


def line_has_no_comment(line):
    return not (line.startswith("!") or line.startswith("#"))


def line_is_not_separator(line):
    return set(line) != {"-"}
