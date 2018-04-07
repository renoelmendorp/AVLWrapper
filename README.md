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

## Requirements
* Developed and tested with Python 3.6, compatible with Python 2.7
* AVL ([link](http://web.mit.edu/drela/Public/web/avl/)) should be installed and the executable path should be set in `avlwrapper/config.cfg`.

For an usage example, see `example.py`
