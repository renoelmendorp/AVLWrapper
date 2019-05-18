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
The wrapper can be installed directly from Git with pip:
```
$ pip install git+https://github.com/renoelmendorp/AVLWrapper@master
```

## Usage
* AVL ([link](http://web.mit.edu/drela/Public/web/avl/)) should be installed and the executable path should be set in `avlwrapper/config.cfg`.
For an usage example, see `example.py`
