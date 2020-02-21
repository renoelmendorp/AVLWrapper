""" AVL Geometry classes
"""
from collections import namedtuple

try:
    from enum import Enum  # On Python 2, requires enum34 pip package
except ImportError:
    raise ImportError('Please install the enum34 pip package.')

from avlwrapper.session import InputError, Input

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
                 reference_point, mach=0.0, cd_p=0.0,
                 y_symmetry=Symmetry.none, z_symmetry=Symmetry.none,
                 z_symmetry_plane=0.0, surfaces=None, bodies=None):
        """
        :param str name: aircraft name
        :param float reference_area: reference planform area for normalisation
        :param float reference_chord: reference chord for normalisation
        :param float reference_span:  reference span for normalisation
        :param Point reference_point: reference point for moment calculations
        :param float mach: mach number
        :param float cd_p: addition profile drag
        :param Symmetry y_symmetry: symmetry normal to y-axis
        :param Symmetry z_symmetry: symmetry normal to z-axis
        :param float z_symmetry_plane: z-normal symmetry plane offset
        :param typing.Sequence[avlwrapper.Surface] surfaces: AVL surfaces
        :param typing.Sequence[avlwrapper.Body] bodies: AVL bodies
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

    def to_string(self):
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

        geom_str += "{0}\n".format(self.cd_p)

        if self.surfaces is not None:
            for surface in self.surfaces:
                geom_str += surface.to_string()

        if self.bodies is not None:
            for body in self.bodies:
                geom_str += body.to_string()

        return geom_str


class Surface(Input):
    """Represents an AVL surface definition"""
    def __init__(self, name, n_chordwise, chord_spacing, sections,
                 n_spanwise=None, span_spacing=None, component=None,
                 y_duplicate=None, scaling=None, translation=None,
                 angle=None, profile_drag=None, no_wake=False,
                 fixed=False, no_loads=False):

        """
        :param str name: (unique) surface name
        :param int n_chordwise: number of chordwise panels
        :param Spacing or float chord_spacing: chordwise distribution
            type. See `Spacing` enum
        :param typing.Sequence[avlwrapper.Section] sections: surface sections
        :param int or None n_spanwise: number of spanwise panels
        :param Spacing or float or None span_spacing: spanwise
            distribution type. See `Spacing` enum
        :param int or None component: component number for surface grouping.
            for detailed explanation see AVL documentation
        :param float or None y_duplicate: mirrors the surface with a plane
            normal to the y-axis see AVL documentation
        :param Vector or None scaling: x, y, z scaling factors
        :param Vector or None translation: x, y, z translation vector
        :param float or None angle: surface incidence angle
        :param avlwrapper.ProfileDrag or None profile_drag: custom drag polar.
            See AVL documentation for details.
        :param bool no_wake: disables the kutta-condition on the surface
            (will shed no wake)
        :param bool fixed: surface will not be influenced
            by freestream direction changes (for wind-tunnel walls, etc.)
        :param bool no_loads: surface forces are not included in the totals
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

    def to_string(self):

        surface_str = self._create_header()
        surface_str += self._create_options()

        for section in self.sections:
            surface_str += section.to_string()

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
            options_str += self.profile_drag.to_string()
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
                 span_spacing=None, airfoil=None, controls=None,
                 design_vars=None, cl_alpha_scaling=None, profile_drag=None):
        """
        :param Point leading_edge_point: section leading edge point
        :param float chord: the chord length
        :param float or None angle: the section angle. This will rotate
            the normal vectors of the VLM panels.
            The panels will remain in stream-wise direction
        :param int or None n_spanwise: number of spanwise panels
            in the next wing segment
        :param Spacing or float or None span_spacing: panel distribution type.
            See `Spacing` enum
        :param _Airfoil or None airfoil: Airfoil to be used at the section.
            AVL uses the airfoil camber to calculate the surface normals.
        :param typing.Sequence[DesignVar] or None design_vars: perturbation of
            the local inflow angle by a set of design variables.
        :param typing.Sequence[Control] or None controls: hinge deflection
        :param float or None cl_alpha_scaling: scales the effective dcl/dalpha
            of the section
        :param ProfileDrag or None profile_drag: set custom drag polar.
            See AVL documentation for details.
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

    def to_string(self):

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
            section_str += self.airfoil.to_string()
        if self.controls is not None:
            for control in self.controls:
                if control is not None:
                    section_str += control.to_string()
        if self.design_vars is not None:
            for design_var in self.design_vars:
                if design_var is not None:
                    section_str += design_var.to_string()
        if self.cl_alpha_scaling is not None:
            section_str += "CLAF\n{0}\n".format(self.cl_alpha_scaling)
        if self.profile_drag is not None:
            section_str += self.profile_drag.to_string()
        return section_str


class Body(Input):
    """AVL non-lifting body of revolution"""
    def __init__(self, name, n_body, body_spacing, body_section,
                 y_duplicate=None, scaling=None, translation=None):
        """
        :param str name: body name
        :param int n_body: number of panels on body
        :param avlwrapper.Spacing body_spacing: panel distribution
        :param avlwrapper.BodyProfile body_section: body section profile
        :param float y_duplicate: mirror the surface normal to the y-axis
        :param Vector or None scaling: x, y, z scaling factors
        :param Vector or None translation: x, y, z translation vector
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

    def to_string(self):
        body_str = "BODY\n{0}\n#NBody BSpace\n{1} {2}\n".format(
            self.name, self.n_body, self.body_spacing)
        body_str += self.body_section.to_string()

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

    def to_string(self):
        if (self.x1 is not None) and (self.x2 is not None):
            return "{0} {1} {2}\n".format(self.af_type.upper(),
                                          self.x1, self.x2)
        else:
            return "{0}\n".format(self.af_type.upper())


class NacaAirfoil(_Airfoil):
    """NACA 4-digit airfoil"""

    def __init__(self, naca, x1=None, x2=None):
        """
        :param str naca: NACA-4 digit designation
        :param float or None x1: start of x/c range (optional)
        :param float or None x2: end of x/c range (optional)
        """
        super(NacaAirfoil, self).__init__('naca', x1, x2)
        self.naca = naca

    def to_string(self):
        header = super(NacaAirfoil, self).to_string()
        return header + "{0}\n".format(self.naca)


class DataAirfoil(_Airfoil):
    """Airfoil defined with x and z ordinates"""

    def __init__(self, x_data, z_data, x1=None, x2=None):
        """
        :param typing.Sequence[float] x_data: x ordinates
        :param typing.Sequence[float] z_data: z ordinates
        :param float or None x1: start of x/c range (optional)
        :param float or None x2: end of x/c range (optional)
        """
        super(DataAirfoil, self).__init__('airfoil', x1, x2)
        self.x_data = x_data
        self.z_data = z_data

    def to_string(self):
        header = super(DataAirfoil, self).to_string()
        data = ""
        for x, z in zip(self.x_data, self.z_data):
            data += "{0} {1}\n".format(x, z)
        return header + data


class FileAirfoil(_Airfoil):
    """Airfoil defined from .dat file"""

    def __init__(self, filename, x1=None, x2=None):
        """
        :param str filename: .dat file name
        :param float or None x1: start of x/c range (optional)
        :param float or None x2: end of x/c range (optional)
        """
        super(FileAirfoil, self).__init__('afile', x1, x2)
        self.filename = filename

    def to_string(self):
        header = super(FileAirfoil, self).to_string()
        return header + "{0}\n".format(self.filename)


class BodyProfile(_Airfoil):
    """Body profile from a data file"""

    def __init__(self, filename, x1=None, x2=None):
        """
        :param str filename: .dat file name
        :param float or None x1: start of x/c range (optional)
        :param float or None x2: end of x/c range (optional)
        """
        super(BodyProfile, self).__init__('bfile', x1, x2)
        self.filename = filename

    def to_string(self):
        header = super(BodyProfile, self).to_string()
        return header + "{}\n".format(self.filename)


class Control(Input):
    """Defines a hinge deflection"""

    def __init__(self, name, gain, x_hinge, duplicate_sign,
                 hinge_vector=Vector(0, 0, 0)):
        """
        :param str name: control name
        :param float gain: control deflection gain
        :param float x_hinge: x/c location of the hinge
        :param int duplicate_sign: sign of deflection for duplicated surface
        :param Vector hinge_vector: hinge_vector. Defaults to Vector(0,0,0)
            which puts the hinge vector along the hinge
        """
        self.name = name
        self.gain = gain
        self.x_hinge = x_hinge
        self.duplicate_sign = duplicate_sign
        self.hinge_vector = hinge_vector

    def to_string(self):
        header = "CONTROL\n#Name Gain XHinge Vector SgnDup\n"
        body = ("{name} {gain} {hinge} {vec.x} {vec.y} {vec.z} {sgn}\n"
                .format(name=self.name, gain=self.gain, hinge=self.x_hinge,
                        vec=self.hinge_vector, sgn=self.duplicate_sign))
        return header + body


class DesignVar(Input):
    """Defines a design variable on the section local inflow angle"""

    def __init__(self, name, weight):
        """
        :param str name: variable name
        :param float weight: variable weight
        """
        self.name = name
        self.weight = weight

    def to_string(self):
        return "DESIGN\n#Name Weight\n{0} {1}\n".format(self.name, self.weight)


class ProfileDrag(Input):
    """ Specifies a simple profile-drag CD(CL) function.
        The function is parabolic between CL1..CL2 and
        CL2..CL3, with rapid increases in CD below CL1 and above CL3.
        See AVL documentation for details"""

    def __init__(self, cl, cd):
        """
        :param typing.Sequence[float] cl: lift-coefficients
        :param typing.Sequence[float] cd: drag-coefficients
        """

        if len(cl) != 3 or len(cd) != 3:
            raise InputError("Invalid profile drag parameters "
                             "(should be of 3 CLs and 3 CDs")
        self.cl_data = cl
        self.cd_data = cd

    def to_string(self):
        data_str = "CDCL\n"
        for cl, cd in zip(self.cl_data, self.cd_data):
            data_str += "{0} {1} ".format(cl, cd)
        return data_str + "\n"


class FileWrapper(Input):
    """Wraps an existing input file to be used with the wrapper"""

    def __init__(self, filename):
        """
        :param str filename: AVL input file
        """
        self.filename = filename
        self._file_content = None

    @property
    def file_content(self):
        if self._file_content is None:
            with open(self.filename, 'r') as in_file:
                lines = in_file.readlines()
            lines = remove_comments(lines)
            lines = remove_empty(lines)
            self._file_content = list(lines)
        return self._file_content

    @property
    def name(self):
        return self.file_content[0].strip()

    @property
    def mach(self):
        return float(self.file_content[1])

    @property
    def point(self):
        return [float(s) for s in self.file_content[4].split()]

    @property
    def cd_p(self):
        try:
            return float(self.file_content[5])
        except ValueError:
            return 0.0

    def to_string(self):
        return "".join(self.file_content)

    def get_external_airfoil_names(self):
        airfoils = []
        get_next = False
        for line in self.file_content:
            if get_next:
                airfoils.append(line.strip())
                get_next = False
            if 'AFILE' in line:
                get_next = True
        return airfoils


def remove_comments(lines):
    def has_no_comment(line):
        return not (line.startswith('!') or line.startswith('#'))
    return filter(has_no_comment, lines)


def remove_empty(lines):
    return filter(lambda line: line.strip() != '', lines)
