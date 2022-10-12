#!/bin/bash

VERSION=`python setup.py --version` \
	conda mambabuild \
	# -c https://artifactory.int.flyarcher.com/artifactory/api/conda/conda \
	-c conda-forge \
	-c main \
	conda.recipe

