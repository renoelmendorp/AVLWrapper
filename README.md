# AVLWrapper
Python interface for MIT AVL (Athena Vortex Lattice)

## Description
Currently implemented:

* Geometry definition
* Case definition
* Mass distribution definition
* Running operating-point run cases
* Eigen-mode analysis
* Results parsing

## Installation
AVLWrapper can be installed from PyPI:
```
$ pip install avlwrapper
```

Or can be installed from Git:
```
$ pip install git+https://github.com/renoelmendorp/AVLWrapper.git@master
```

### Requirements

AVL 3.40 or later ([link](http://web.mit.edu/drela/Public/web/avl/)) should be installed. Older versions don't write the machine-readable output the wrapper reads; the wrapper checks the version before it uses AVL and raises an `AvlVersionError` for an older version. If installed on a location in `$PATH` or in the module directory, the wrapper will locate it with the default configuration. See [Changing settings](#changing-settings) how to change the executable path to a custom location.

(optional) Ghostscript is required to convert and save plots as pdf, jpeg, or
png. Ghostscript can be installed on Linux/MacOS with a package manager:

Linux:
```
$ apt-get install ghostscript
```
MacOS:
```
$ brew install ghostscript
```

For Windows, Ghostscript can be found on the [website](https://www.ghostscript.com).

## Usage
For usage examples, see the `example.ipynb` notebook.

## Changing settings
To change settings, make a local copy of the settings file:
```python
from avlwrapper import default_config
default_config.local_copy()
```
By default the wrapper will look for a configuration file in the working directory and module directory.
If you would like to use a different configuration file, you need to give the path to the session:
```python
from avlwrapper import Configuration
my_config = Configuration(path_to_file)
session = Session(..., config=my_config)
```


## AVL options
AVL settings which change the meaning of the results can be set per session:
```python
options = avl.Options(
    profile_drag=False,          # leave out the profile drag of CDCL polars
    stability_axis_rates=False,  # rates of the cases are about the body axes
    standard_axes=True,          # X forward, Z down
    trailing_leg_forces=True,    # include forces on the trailing legs
)
session = avl.Session(geometry=aircraft, cases=cases, options=options)
```
Options which are not set keep the AVL default. The defaults differ between AVL
versions, e.g. trailing-leg forces are included by default in AVL 3.40 but not
in 3.52, so set the options your results depend on.

## Trimmed flight
AVL can set up a case as level or banked horizontal flight, or as steady
looping flight, from the states of the case:
```python
case = avl.Case(
    name="cruise",
    trim=avl.Trim.level_flight,
    velocity=20.0,
    mass=10.0,
    density=1.225,
    bank=30.0,
)
results = avl.Session(geometry=aircraft, cases=[case]).run_all_cases()
results[1]["States"]  # CL, turn radius, load factor, ... as solved
```

## Eigenmodes and mass properties
```python
session = avl.Session(geometry=aircraft, cases=cases, mass_dist=mass)
modes = session.run_mode_analysis(cases=[1, 3])  # defaults to all cases
modes["EigenModes"][1]   # eigenvalues with their eigenvectors
modes["SystemMatrix"][1]
session.mass_properties()  # mass, CG, inertia and apparent mass
```

## Off-body flow, surface pressures and design changes
```python
session = avl.Session(
    geometry=aircraft,
    cases=cases,
    survey_points=[avl.Point(10.0, 0.0, 1.0)],  # results in "OffBodyFlow"
    design_changes={"twist": 1.5},  # DESIGN variables of the geometry
)
```
Surface pressures on the outer mould lines are computed when
`SurfacePressures = yes` in the configuration. AVL computes them only for
surfaces with airfoils over their full chord, and needs a separate run per case.

## Output precision
The wrapper reads AVL's machine-readable output, which has full precision.
AVL has no machine-readable format for the strip forces in body axes (5 to 6
significant digits), the off-body flow (6 decimals), the eigenvectors (4
decimals) and the mass properties (4 significant digits).

## Error handling
All errors raised by the wrapper derive from `avlwrapper.AvlError`:

* `InputError`: invalid geometry, case or mass input
* `AvlExecutionError`: AVL did not produce the expected results. The AVL output is available in the `output` attribute
* `AvlVersionError` (an `AvlExecutionError`): the AVL version is older than 3.40, or could not be determined
* `OutputError`: an AVL output file could not be parsed

## Development
# Tests
To run tests in development, first install the development requirement into your environment:
```shell
pip install -r requirements-dev.txt
```

Then, from the source directory of the repo:
```
pytest -vv tests
```

Tests which run AVL are skipped when the AVL executable is not found. To build
AVL from source (Linux, macOS), use `ci/build-avl.sh`, which is also used by
the CI workflow:
```shell
ci/build-avl.sh 3.52 ~/.local
```
