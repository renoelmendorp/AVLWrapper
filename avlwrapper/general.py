import os.path
from collections import namedtuple
from enum import Enum


class InputError(Exception):
    pass


class ParseError(Exception):
    pass


class Input(object):
    def create_input(self):
        raise NotImplementedError


Point = namedtuple('Point', 'x y z')
Vector = namedtuple('Vector', 'x y z')


class Spacing(Enum):
    sine = 2
    cosine = 1
    equal = 0
    neg_sine = -2


class Symmetry(Enum):
    none = 0
    symmetric = 1
    anti_symmetric = -1


MODULE_DIR = os.path.dirname(__file__)
