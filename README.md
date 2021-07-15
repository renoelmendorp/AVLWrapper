# AVLWrapper
Python interface for MIT AVL (Athena Vortex Lattice)

## Description
Currently implemented:

* Geometry definition
* Case definition
* Running operating-point run cases
* Results parsing

Not implemented (yet):

* Mass definition
* Eigen-mode analyses
* Time-domain analyses

## Installation
AVLWrapper can be installed from PyPI:
```
$ pip install avlwrapper
```

Or can be installed from Git:
```
$ pip install git+https://gitlab.com/relmendorp/avlwrapper.git@master
```

### Requirements

AVL ([link](http://web.mit.edu/drela/Public/web/avl/), [repo](https://gitlab.com/relmendorp/avl)) should be installed. If installed on a location in `$PATH` or in the module directory, the wrapper will locate it with the default configuration. See [Changing settings](#changing-settings) how to change the executable path to a custom location.

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
