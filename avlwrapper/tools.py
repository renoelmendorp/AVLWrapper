import copy
from itertools import product

from avlwrapper import Case


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

    parameter_names = [p['name'] for p in parameters]
    parameter_values = product(*[p['values']
                                 for p in parameters])

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
        yield cases[idx:idx + n_cases]


def show_image(image_path, rotate=True):
    import numpy as np
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    image = mpimg.imread(image_path)
    if rotate:
        image = np.rot90(image, k=3)

    plt.figure()
    plt.imshow(image)
    plt.axis('off')
    plt.show()
