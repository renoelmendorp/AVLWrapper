#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" AVL Geometry classes
"""
from collections import namedtuple

try:
    from enum import Enum  # On Python 2, requires enum34 pip package
except ImportError:
    raise ImportError('Please install the enum34 pip package.')

from .core import InputError, Input

__author__ = "Reno Elmendorp"
__status__ = "Development"

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


class Geometry(Input):
    """Geometry object, represents the content of an AVL geometry input file"""
    def __init__(self, name, reference_area, reference_chord, reference_span, reference_point,
                 mach=0.0, cd_p=None, y_symmetry=Symmetry.none, z_symmetry=Symmetry.none, z_symmetry_plane=0.0,
                 surfaces=None, bodies=None):
        self.name = name
        self.area = reference_area
        self.chord = reference_chord
        self.span = reference_span
        self.point = reference_point
        self.mach = mach
        self.cd_p = cd_p
        self.y_symm = y_symmetry
        self.z_symm = z_symmetry
        self.z_symm_plane = z_symmetry_plane
        self.surfaces = surfaces
        self.bodies = bodies

    def get_external_airfoil_names(self):
        airfoils = []
        for surface in self.surfaces:
            airfoils += surface.get_external_airfoil_names()
        return list(set(airfoils))

    def create_input(self):
        geom_str = "{name}\n#Mach\n{mach}\n".format(name=self.name, mach=self.mach)
        geom_str += "#iYsym iZsym Zsym\n{iy} {iz} {z_loc}\n".format(iy=self.y_symm.value,
                                                                    iz=self.z_symm.value,
                                                                    z_loc=self.z_symm_plane)
        geom_str += "#Sref Cref Bref\n{s} {c} {b}\n#Xref Yref Zref\n{p.x} {p.y} {p.z}\n".format(s=self.area,
                                                                                                c=self.chord,
                                                                                                b=self.span,
                                                                                                p=self.point)
        if self.cd_p is not None:
            geom_str += "{0}\n".format(self.cd_p)

        if self.surfaces is not None:
            for surface in self.surfaces:
                geom_str += surface.create_input()

        if self.bodies is not None:
            for body in self.bodies:
                geom_str += body.create_input()

        return geom_str


class Surface(Input):
    """Represents an AVL surface definition"""
    def __init__(self, name, n_chordwise, chord_spacing, sections, n_spanwise=None, span_spacing=None, component=None,
                 y_duplicate=None, scaling=None, translation=None, angle=None, profile_drag=None,
                 no_wake=False, fixed=False, no_loads=False):

        self.name = name
        self.n_chordwise = n_chordwise
        self.sections = sections
        self.n_spanwise = n_spanwise
        self.component = component
        self.y_duplicate = y_duplicate
        self.scaling = scaling
        self.translation = translation
        self.angle = angle
        self.profile_drag = profile_drag
        self.no_wake = no_wake
        self.fixed = fixed
        self.no_loads = no_loads

        if isinstance(chord_spacing, Spacing):
            self.chord_spacing = chord_spacing.value
        else:
            self.chord_spacing = chord_spacing
        if isinstance(span_spacing, Spacing):
            self.span_spacing = span_spacing.value
        else:
            self.span_spacing = span_spacing

    def get_external_airfoil_names(self):
        airfoil_names = []
        for section in self.sections:
            if isinstance(section.airfoil, FileAirfoil):
                airfoil_names.append(section.airfoil.file_name)
        return airfoil_names

    def create_input(self):

        header = "SURFACE\n{0}\n#NChordwise ChordSpacing".format(self.name)
        header_data = "{0} {1}".format(self.n_chordwise, self.chord_spacing)

        if (self.n_spanwise is not None) and (self.span_spacing is not None):
            header += " NSpanwise SpanSpacing"
            header_data += " {0} {1}".format(self.n_spanwise, self.span_spacing)

        surface_str = header + "\n" + header_data + "\n"

        if self.component is not None:
            surface_str += "COMPONENT\n{0}\n".format(self.component)

        if self.y_duplicate is not None:
            surface_str += "YDUPLICATE\n{0}\n".format(self.y_duplicate)

        if self.scaling is not None:
            surface_str += "SCALE\n{0.x} {0.y} {0.z}\n".format(self.scaling)

        if self.translation is not None:
            surface_str += "TRANSLATE\n{0.x} {0.y} {0.z}\n".format(self.translation)

        if self.angle is not None:
            surface_str += "ANGLE\n{0}\n".format(self.angle)

        if self.profile_drag is not None:
            surface_str += self.profile_drag.create_input()

        if self.no_wake:
            surface_str += "NOWAKE\n"

        if self.fixed:
            surface_str += "NOALBE\n"

        if self.no_loads:
            surface_str += "NOLOAD\n"

        for section in self.sections:
            surface_str += section.create_input()

        return surface_str


class Section(Input):

    def __init__(self, leading_edge_point, chord, angle=0, n_spanwise=None, span_spacing=None, airfoil=None,
                 controls=None, design=None, cl_alpha_scaling=None, profile_drag=None):
        self.leading_edge_point = leading_edge_point
        self.chord = chord
        self.angle = angle
        self.n_spanwise = n_spanwise
        self.airfoil = airfoil
        self.design = design
        self.controls = controls
        self.cl_alpha_scaling = cl_alpha_scaling
        self.profile_drag = profile_drag

        if isinstance(span_spacing, Spacing):
            self.span_spacing = span_spacing.value
        else:
            self.span_spacing = span_spacing

    def create_input(self):

        header = "SECTION\n#Xle Yle Zle Chord Angle"
        section_data = "{point.x} {point.y} {point.z} {chord} {angle}".format(
            point=self.leading_edge_point, chord=self.chord, angle=self.angle)

        if (self.n_spanwise is not None) and (self.span_spacing is not None):
            header = header + " NSpanwise SpanSpacing"
            section_data += " {0} {1}".format(self.n_spanwise, self.span_spacing)
        section_str = header + "\n" + section_data + "\n"

        if self.airfoil is not None:
            section_str += self.airfoil.create_input()

        if self.controls is not None:
            for control in self.controls:
                section_str += control.create_input()

        if self.design is not None:
            section_str += self.design.create_input()

        if self.cl_alpha_scaling is not None:
            section_str += "CLAF\n{0}\n".format(self.cl_alpha_scaling)

        if self.profile_drag is not None:
            section_str += self.profile_drag.create_input()

        return section_str


class Body(Input):

    def __init__(self, name, n_body, body_spacing, body_section, y_duplicate=None, scaling=None, translation=None):
        self.name = name
        self.n_body = n_body
        self.body_section = body_section
        self.y_duplicate = y_duplicate
        self.scaling = scaling
        self.translation = translation

        if isinstance(body_spacing, Spacing):
            self.body_spacing = body_spacing.value
        else:
            self.body_spacing = body_spacing

    def create_input(self):
        body_str = "BODY\n{0}\n#NBody BSpace\n{1} {2}\n".format(self.name, self.n_body, self.body_spacing)
        body_str += self.body_section.create_input()

        if self.y_duplicate is not None:
            body_str += "YDUPLICATE\n{0}\n".format(self.y_duplicate)

        if self.scaling is not None:
            body_str += "SCALE\n{0.x} {0.y} {0.z}\n".format(self.scaling)

        if self.translation is not None:
            body_str += "TRANSLATE\n{0.x} {0.y} {0.z}\n".format(self.translation)


class Airfoil(Input):

    def __init__(self, af_type, x1=None, x2=None):
        self.af_type = af_type
        self.x1 = x1
        self.x2 = x2

    def create_input(self):
        if (self.x1 is not None) and (self.x2 is not None):
            return "{0} {0} {0}\n".format(self.af_type.upper(), self.x1, self.x2)
        else:
            return "{0}\n".format(self.af_type.upper())


class NacaAirfoil(Airfoil):

    def __init__(self, naca, x1=None, x2=None):
        super(NacaAirfoil, self).__init__('naca', x1, x2)
        self.naca = naca

    def create_input(self):
        header = super(NacaAirfoil, self).create_input()
        return header + "{0}\n".format(self.naca)


class DataAirfoil(Airfoil):

    def __init__(self, x_data, z_data, x1=None, x2=None):
        super(DataAirfoil, self).__init__('airfoil', x1, x2)
        self.x_data = x_data
        self.z_data = z_data

    def create_input(self):
        header = super(DataAirfoil, self).create_input()
        data = ""
        for x, z in zip(self.x_data, self.z_data):
            data += "{0} {1}\n".format(x, z)
        return header + data


class FileAirfoil(Airfoil):

    def __init__(self, file, x1=None, x2=None):
        super(FileAirfoil, self).__init__('afile', x1, x2)
        self.file_name = file

    def create_input(self):
        header = super(FileAirfoil, self).create_input()
        return header + "{0}\n".format(self.file_name)


class Control(Input):

    def __init__(self, name, gain, x_hinge, duplicate_sign, hinge_vector=Vector(0, 0, 0)):
        self.name = name
        self.gain = gain
        self.x_hinge = x_hinge
        self.duplicate_sign = duplicate_sign
        self.hinge_vector = hinge_vector

    def create_input(self):
        return "CONTROL\n#Name Gain XHinge Vector SgnDup\n{name} {gain} {hinge} {vec.x} {vec.y} {vec.z} {sgn}\n".format(
            name=self.name, gain=self.gain, hinge=self.x_hinge, vec=self.hinge_vector, sgn=self.duplicate_sign)


class Design(Input):

    def __init__(self, name, bias):
        self.name = name
        self.bias = bias

    def create_input(self):
        return "DESIGN\n#Name Weight\n{0} {0}\n".format(self.name, self.bias)


class ProfileDrag(Input):

    def __init__(self, cl, cd):
        if len(cl) != 3 or len(cd) != 3:
            raise InputError("Invalid profile drag parameters (should be of 3 CLs and 3 CDs")
        self.cl_data = cl
        self.cd_data = cd

    def create_input(self):
        data_str = "CDCL\n"
        for cl, cd in zip(self.cl_data, self.cd_data):
            data_str += "{0} {1} ".format(cl, cd)
        return data_str + "\n"


class FileWrapper(Input):
    """Wraps an existing input file to be used with the wrapper"""
    def __init__(self, file):
        self.file = file
        with open(self.file, 'r') as in_file:
            self.name = in_file.readline().rstrip()

    def create_input(self):
        with open(self.file, 'r') as in_file:
            lines = in_file.readlines()
        return "".join(lines)
