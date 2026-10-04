#!/usr/bin/env python3

import os.path
from setuptools import setup, find_packages

current_dir = os.path.abspath(os.path.dirname(__file__))

# read the version without importing the package
version_globals = {}
with open(os.path.join(current_dir, "avlwrapper", "_version.py")) as fh:
    exec(fh.read(), version_globals)
AVL_VERSION = version_globals["VERSION"]

# dependencies; currently none
dependencies = []

# include files
include_files = ["*.cfg"]

# include README as long description
readme_path = os.path.join(current_dir, "README.md")
with open(readme_path, "r") as fh:
    long_description = fh.read()

setup(
    name="avlwrapper",
    version=AVL_VERSION,
    url="https://github.com/renoelmendorp/AVLWrapper",
    author="Reno Elmendorp",
    description="Python interface for MIT AVL (Athena Vortex Lattice)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GPL-3.0-only",
    license_files=["LICENSE"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=dependencies,
    extras_require={"plot": ["numpy", "matplotlib"]},
    include_package_data=True,
    package_data={"": include_files},
)
