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
AVLWrapper can be installed from pip:
```
$ pip install avlwrapper
```

Or can be installed from Git:
```
$ pip install git+https://github.com/renoelmendorp/AVLWrapper@master
```

AVL ([link](http://web.mit.edu/drela/Public/web/avl/)) should be installed.

By default, the wrapper will check the current directory, the module directory and the system path.
See [Changing settings](#changing-settings) how to change the executable path to a custom location.

## Usage
For an usage example, see `example.py`

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
