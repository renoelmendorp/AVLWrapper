#!/usr/bin/env python3

import sys
import os.path
from setuptools import setup, find_packages

current_dir = os.path.abspath(os.path.dirname(__file__))

# dependencies; currently none
dependencies = []

# add enum34 package if Python < 3.4
if sys.version_info < (3, 4):
    dependencies.append('enum34')
    
# include files
include_files = ['*.cfg']

# include README as long description
readme_path = os.path.join(current_dir, "README.md")
try:
    import pypandoc
    long_description = pypandoc.convert_file(readme_path, 'rst')
except ImportError:
    with open(readme_path, "r") as fh:
        long_description = fh.read()

setup(
    name="avlwrapper",
    version="0.1.5",
    url="https://github.com/renoelmendorp/AVLWrapper",
    author="Reno Elmendorp",
    author_email="reno.elmendorp@icloud.com",
    description="Python interface for MIT AVL (Athena Vortex Lattice)",
    long_description=long_description,
    license="LICENSE",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent"
    ],
    packages=find_packages(),
    install_requires=dependencies,
    include_package_data=True,
    package_data={
        '': include_files
    }
)
