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
    def __init__(self, name, reference_area, reference_chord, reference_span,
                 reference_point, mach=0.0, cd_p=None,
                 y_symmetry=Symmetry.none, z_symmetry=Symmetry.none,
                 z_symmetry_plane=0.0, surfaces=None, bodies=None):
        """
        :param name: aircraft name
        :type name: str

        :param reference_area: reference planform area for normalisation
        :type reference_area: float

        :param reference_chord: reference chord for normalisation
        :type reference_chord: float

        :param reference_span:  reference span for normalisation
        :type reference_span: float

        :param reference_point: reference point for moment calculations
        :type reference_point: Point

        :param mach: mach number
        :type mach: float

        :param cd_p: addition profile drag
        :type cd_p: float or None

        :param y_symmetry: symmetry normal to y-axis
        :type y_symmetry: Symmetry

        :param z_symmetry: symmetry normal to z-axis
        :type z_symmetry: Symmetry

        :param z_symmetry_plane: z-normal symmetry plane offset
        :type z_symmetry_plane float

        :param surfaces: AVL surfaces
        :type surfaces: collections.Sequence[Surface]

        :param bodies: AVL bodies
        :type bodies: collections.Sequence[Body]
        """
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
        geom_str = ("{name}\n#Mach\n{mach}\n" .format(name=self.name,
                                                      mach=self.mach))
        geom_str += ("#iYsym iZsym Zsym\n{iy} {iz} {z_loc}\n"
            .format(iy=self.y_symm.value,
                    iz=self.z_symm.value,
                    z_loc=self.z_symm_plane))
        geom_str += "#Sref Cref Bref\n{s} {c} {b}\n".format(s=self.area,
                                                            b=self.span,
                                                            c=self.chord)

        geom_str += "#Xref Yref Zref\n{p.x} {p.y} {p.z}\n".format(p=self.point)

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
    def __init__(self, name, n_chordwise, chord_spacing, sections,
                 n_spanwise=None, span_spacing=None, component=None,
                 y_duplicate=None, scaling=None, translation=None,
                 angle=None, profile_drag=None, no_wake=False,
                 fixed=False, no_loads=False):

        """
        :param name: (unique) surface name
        :type name: str

        :param n_chordwise: number of chordwise panels
        :type n_chordwise: int

        :param chord_spacing: chordwise distribution type. See `Spacing` enum
        :type chord_spacing: Spacing or float

        :param sections: surface sections
        :type sections: collections.Sequence[Section]

        :param n_spanwise: number of spanwise panels
        :type n_spanwise: int or None

        :param span_spacing: spanwise distribution type. See `Spacing` enum
        :type span_spacing: Spacing or float or None

        :param component: component number for surface grouping. for detailed
            explanation see AVL documentation
        :type component: int or None

        :param y_duplicate: mirrors the surface with a plane normal to the y-axis
            see AVL documentation
        :type y_duplicate: float or None

        :param scaling: x, y, z scaling factors
        :type scaling: Vector or None

        :param translation: x, y, z translation vector
        :type translation: Vector or None

        :param angle: surface incidence angle
        :type angle: float or None

        :param profile_drag: set custom drag polar.
            See AVL documentation for details.
        :type profile_drag: ProfileDrag or None

        :param no_wake: disables the kutta-condition on the surface
            (will shed no wake)
        :type no_wake: bool

        :param fixed: surface will not be influenced
            by freestream direction changes (for wind-tunnel walls, etc.)
        :type fixed: bool

        :param no_loads: surface forces are not included in the totals
        :type no_loads: bool
        """

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
                airfoil_names.append(section.airfoil.filename)
        return airfoil_names

    def create_input(self):

        surface_str = self._create_header()
        surface_str += self._create_options()

        for section in self.sections:
            surface_str += section.create_input()

        return surface_str

    def _create_header(self):
        header = "SURFACE\n{0}\n#NChordwise ChordSpacing".format(self.name)
        header_data = "{0} {1}".format(self.n_chordwise, self.chord_spacing)
        if (self.n_spanwise is not None) and (self.span_spacing is not None):
            header += " NSpanwise SpanSpacing"
            header_data += " {0} {1}".format(self.n_spanwise,
                                             self.span_spacing)
        return header + "\n" + header_data + "\n"

    def _create_options(self):
        options_str = ""
        if self.component is not None:
            options_str += "COMPONENT\n{0}\n".format(self.component)
        if self.y_duplicate is not None:
            options_str += "YDUPLICATE\n{0}\n".format(self.y_duplicate)
        if self.scaling is not None:
            options_str += "SCALE\n{0.x} {0.y} {0.z}\n".format(self.scaling)
        if self.translation is not None:
            options_str += "TRANSLATE\n{0.x} {0.y} {0.z}\n".format(
                self.translation)
        if self.angle is not None:
            options_str += "ANGLE\n{0}\n".format(self.angle)
        if self.profile_drag is not None:
            options_str += self.profile_drag.create_input()
        if self.no_wake:
            options_str += "NOWAKE\n"
        if self.fixed:
            options_str += "NOALBE\n"
        if self.no_loads:
            options_str += "NOLOAD\n"
        return options_str


class Section(Input):
    """AVL section"""
    def __init__(self, leading_edge_point, chord, angle=0, n_spanwise=None,
                 span_spacing=None, airfoil=None, controls=None, design_vars=None,
                 cl_alpha_scaling=None, profile_drag=None):
        """
        :param leading_edge_point: section leading edge point
        :type leading_edge_point: Point

        :param chord: the chord length
        :type chord: float

        :param angle: the section angle. This will rotate the normal vectors
            of the VLM panels. The panels will remain in stream-wise direction
        :type angle: float or None

        :param n_spanwise: number of spanwise panels in the next wing segment
        :type n_spanwise: int or None

        :param span_spacing: panel distribution type. See `Spacing` enum
        :type span_spacing: Spacing or float or None

        :param airfoil: Airfoil to be used at the section. AVL uses the airfoil
            camber to calculate the surface normals.
        :type airfoil: _Airfoil or collections.Sequence[None]

        :param design_vars: perturbation of the local inflow angle by a set of
            design variables.
        :type design_vars: collections.Sequence[DesignVar] or
            collections.Sequence[none]

        :param controls: defines a hinge deflection
        :type controls: collections.Sequence[Control] or
            collections.Sequence[None]

        :param cl_alpha_scaling: scales the effective dcl/dalpha of the section
        :type cl_alpha_scaling: float or None

        :param profile_drag: set custom drag polar.
            See AVL documentation for details.
        :type profile_drag: ProfileDrag or None
        """

        self.leading_edge_point = leading_edge_point
        self.chord = chord
        self.angle = angle
        self.n_spanwise = n_spanwise
        self.airfoil = airfoil
        self.design_vars = design_vars
        self.controls = controls
        self.cl_alpha_scaling = cl_alpha_scaling
        self.profile_drag = profile_drag

        if isinstance(span_spacing, Spacing):
            self.span_spacing = span_spacing.value
        else:
            self.span_spacing = span_spacing

    def create_input(self):

        section_str = self._create_header()
        section_str += self._create_body()

        return section_str

    def _create_header(self):
        header = "SECTION\n#Xle Yle Zle Chord Angle"
        section_data = "{point.x} {point.y} {point.z} {chord} {angle}".format(
            point=self.leading_edge_point, chord=self.chord, angle=self.angle)
        if (self.n_spanwise is not None) and (self.span_spacing is not None):
            header = header + " NSpanwise SpanSpacing"
            section_data += " {0} {1}".format(self.n_spanwise,
                                              self.span_spacing)
        return header + "\n" + section_data + "\n"

    def _create_body(self):
        section_str = ""
        if self.airfoil is not None:
            section_str += self.airfoil.create_input()
        if self.controls is not None:
            for control in self.controls:
                if control is not None:
                    section_str += control.create_input()
        if self.design_vars is not None:
            for design_var in self.design_vars:
                if design_var is not None:
                    section_str += design_var.create_input()
        if self.cl_alpha_scaling is not None:
            section_str += "CLAF\n{0}\n".format(self.cl_alpha_scaling)
        if self.profile_drag is not None:
            section_str += self.profile_drag.create_input()
        return section_str


class Body(Input):
    """AVL non-lifting body of revolution"""
    def __init__(self, name, n_body, body_spacing, body_section,
                 y_duplicate=None, scaling=None, translation=None):
        """
        :param name: body name
        :type name: str

        :param n_body: number of panels on body
        :type n_body: int

        :param body_spacing: panel distribution
        :type body_spacing: Spacing

        :param body_section: body section profile
        :type body_section: BodyProfile

        :param y_duplicate: mirror the surface normal to the y-axis
        :type y_duplicate: float

        :param scaling: x, y, z scaling factors
        :type scaling: Vector or None

        :param translation: x, y, z translation vector
        :type translation: Vector or None
        """

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
        body_str = "BODY\n{0}\n#NBody BSpace\n{1} {2}\n".format(
            self.name, self.n_body, self.body_spacing)
        body_str += self.body_section.create_input()

        if self.y_duplicate is not None:
            body_str += "YDUPLICATE\n{0}\n".format(self.y_duplicate)

        if self.scaling is not None:
            body_str += "SCALE\n{0.x} {0.y} {0.z}\n".format(self.scaling)

        if self.translation is not None:
            body_str += ("TRANSLATE\n{0.x} {0.y} {0.z}\n"
                         .format(self.translation))


class _Airfoil(Input):
    """Generic airfoil"""
    def __init__(self, af_type, x1=None, x2=None):
        self.af_type = af_type
        self.x1 = x1
        self.x2 = x2

    def create_input(self):
        if (self.x1 is not None) and (self.x2 is not None):
            return "{0} {1} {2}\n".format(self.af_type.upper(),
                                          self.x1, self.x2)
        else:
            return "{0}\n".format(self.af_type.upper())


class NacaAirfoil(_Airfoil):
    """NACA 4-digit airfoil"""

    def __init__(self, naca, x1=None, x2=None):
        """
        :param naca: NACA-4 digit designation
        :type naca: str

        :param x1: start of x/c range (optional)
        :type x1: float or None

        :param x2: end of x/c range (optional)
        :type x2: float or None
        """
        super(NacaAirfoil, self).__init__('naca', x1, x2)
        self.naca = naca

    def create_input(self):
        header = super(NacaAirfoil, self).create_input()
        return header + "{0}\n".format(self.naca)


class DataAirfoil(_Airfoil):
    """Airfoil defined with x and z ordinates"""

    def __init__(self, x_data, z_data, x1=None, x2=None):
        """
        :param x_data: x ordinates
        :type x_data: collections.Sequence[float]

        :param z_data: z ordinates
        :type z_data: collections.Sequence[float]

        :param x1: start of x/c range (optional)
        :type x1: float or None

        :param x2: end of x/c range (optional)
        :type x2: float or None
        """
        super(DataAirfoil, self).__init__('airfoil', x1, x2)
        self.x_data = x_data
        self.z_data = z_data

    def create_input(self):
        header = super(DataAirfoil, self).create_input()
        data = ""
        for x, z in zip(self.x_data, self.z_data):
            data += "{0} {1}\n".format(x, z)
        return header + data


class FileAirfoil(_Airfoil):
    """Airfoil defined from .dat file"""

    def __init__(self, filename, x1=None, x2=None):
        """
        :param filename: .dat file name
        :type filename: str

        :param x1: start of x/c range (optional)
        :type x1: float or None

        :param x2: end of x/c range (optional)
        :type x2: float or None
        """
        super(FileAirfoil, self).__init__('afile', x1, x2)
        self.filename = filename

    def create_input(self):
        header = super(FileAirfoil, self).create_input()
        return header + "{0}\n".format(self.filename)


class BodyProfile(_Airfoil):
    """Body profile from a data file"""

    def __init__(self, filename, x1=None, x2=None):
        """
        :param filename: .dat file name
        :type filename: str

        :param x1: start of x/c range (optional)
        :type x1: float or None

        :param x2: end of x/c range (optional)
        :type x2: float or None
        """
        super(BodyProfile, self).__init__('bfile', x1, x2)
        self.filename = filename

    def create_input(self):
        header = super(BodyProfile, self).create_input()
        return header + "{}\n".format(self.filename)


class Control(Input):
    """Defines a hinge deflection"""

    def __init__(self, name, gain, x_hinge, duplicate_sign,
                 hinge_vector=Vector(0, 0, 0)):
        """
        :param name: control name
        :type name: str

        :param gain: control deflection gain
        :type gain: float

        :param x_hinge: x/c location of the hinge
        :type x_hinge: float

        :param duplicate_sign: sign of deflection for duplicated surface
        :type duplicate_sign: int

        :param hinge_vector: hinge_vector. Defaults to Vector(0,0,0) which puts
                the hinge vector along the hinge
        :type hinge_vector: Vector
        """
        self.name = name
        self.gain = gain
        self.x_hinge = x_hinge
        self.duplicate_sign = duplicate_sign
        self.hinge_vector = hinge_vector

    def create_input(self):
        header = "CONTROL\n#Name Gain XHinge Vector SgnDup\n"
        body = ("{name} {gain} {hinge} {vec.x} {vec.y} {vec.z} {sgn}\n"
                .format(name=self.name, gain=self.gain, hinge=self.x_hinge,
                        vec=self.hinge_vector, sgn=self.duplicate_sign))
        return header + body


class DesignVar(Input):
    """Defines a design variable on the section local inflow angle"""

    def __init__(self, name, weight):
        """
        :param name: variable name
        :type name: str

        :param weight: variable weight
        :type weight: float
        """
        self.name = name
        self.weight = weight

    def create_input(self):
        return "DESIGN\n#Name Weight\n{0} {1}\n".format(self.name, self.weight)


class ProfileDrag(Input):
    """ Specifies a simple profile-drag CD(CL) function.
        The function is parabolic between CL1..CL2 and
        CL2..CL3, with rapid increases in CD below CL1 and above CL3.
        See AVL documentation for details"""

    def __init__(self, cl, cd):
        """
        :param cl: lift-coefficients
        ":type cl: collections.Sequence[float]

        :param cd: drag-coefficients
        :type cd: collections.Sequence[float]
        """

        if len(cl) != 3 or len(cd) != 3:
            raise InputError("Invalid profile drag parameters "
                             "(should be of 3 CLs and 3 CDs")
        self.cl_data = cl
        self.cd_data = cd

    def create_input(self):
        data_str = "CDCL\n"
        for cl, cd in zip(self.cl_data, self.cd_data):
            data_str += "{0} {1} ".format(cl, cd)
        return data_str + "\n"


class FileWrapper(Input):
    """Wraps an existing input file to be used with the wrapper"""

    def __init__(self, filename):
        """
        :param filename: AVL input file
        :type filename: str
        """
        self.file = filename
        with open(self.filename, 'r') as in_file:
            self.name = in_file.readline().rstrip()

    def create_input(self):
        with open(self.filename, 'r') as in_file:
            lines = in_file.readlines()
        return "".join(lines)
