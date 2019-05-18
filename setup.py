#!/usr/bin/env python3

import sys
from setuptools import setup, find_packages

# dependencies; currently none
dependencies = []

# add enum34 package if Python < 3.4
if sys.version_info < (3, 4):
    dependencies.append('enum34')
    
# include files
include_files = ['*.cfg']

setup(
    name='avlwrapper',
    version='0.1',
    url='https://github.com/renoelmendorp/AVLWrapper',
    author='Reno Elmendorp',
    license='LICENCE',
    packages=['avlwrapper'],
    install_requires=dependencies,
    include_package_data=True,
    package_data={
        '': include_files
    }
)
