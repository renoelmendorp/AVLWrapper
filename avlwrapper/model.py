from abc import ABC
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
import os
import re
from typing import Iterable, List, Optional, Union
import warnings

from avlwrapper import VERSION


class InputError(ValueError):
    def __init__(self, lines_in):
        if isinstance(lines_in, Iterable):
            full_str = "\n".join(lines_in)
        else:
            full_str = str(lines_in)
        msg = f"Invalid input:\n{full_str}"
        super().__init__(msg)


class Input(ABC):
    @classmethod
    def from_lines(cls, lines_in: List[str]):
        """
        To be implemented by subclasses. This method creates an instance
        from a list of strings from the input file representing the object
        """
        raise NotImplementedError


class ModelInput(Input, ABC):
    @classmethod
    def parse_lines(cls, lines):
        tokens = cls.tokenize(lines)
        kwargs = cls._parse_to_kwargs(lines, tokens)
        return kwargs

    @classmethod
    def tokenize(cls, lines):
        # Applicable keywords are in KEYWORDS dictionary indexed by class
        keywords = list(KEYWORDS[cls].keys())
        # AVL only considers the first 4 characters to be significant
        short_keys = [key[0:4] for key in keywords]
        # create a list of tuples containing line numbers and keywords
        tokens = []
        for idx, line in enumerate(lines):
            key = line.strip()[0:4]
            if key in short_keys:
                tokens.append((idx, keywords[short_keys.index(key)]))
        # append end of file
        tokens.append((len(lines), "EOF"))
        return tokens

    @classmethod
    def _parse_to_kwargs(cls, lines, tokens):
        kwargs = defaultdict(list)
        for (idx, token), (next_idx, _) in zip(tokens[:-1], tokens[1:]):
            data = lines[idx:next_idx]
            param = KEYWORDS[cls][token]
            if not param.attr_type == AttrType.list and param.attr in kwargs:
                raise ValueError(f"Only one {token} is allowed")

            if param.cls is None:
                if param.attr_type == AttrType.scalar:
                    value = float(data[1].strip())
                elif param.attr_type == AttrType.boolean:
                    value = True
                elif param.attr_type == AttrType.vector:
                    vals = [float(s) for s in data[1].split()]
                    if len(vals) != 3:
                        raise InputError(data)
                    value = Vector(*vals)
                else:
                    assert False
                kwargs[param.attr] = value
            else:
                obj = param.cls.from_lines(data)
                if param.attr_type == AttrType.scalar:
                    kwargs[param.attr] = obj
                elif param.attr_type == AttrType.list:
                    kwargs[param.attr].append(obj)
                else:
                    assert False
        return kwargs


Spacial = namedtuple("Spacial", ["x", "y", "z"])
Spacial.__str__ = lambda self: f"{self.x} {self.y} {self.z}"

Point = Spacial
Vector = Spacial


class IntStrEnum(IntEnum):
    def __str__(self):
        return str(self.value)


class Spacing(IntStrEnum):
    sine = 2
    cosine = 1
    equal = 0
    neg_sine = -2


class Symmetry(IntStrEnum):
    none = 0
    symmetric = 1
    anti_symmetric = -1


# The Airfoil and the _NacaAirfoil, _DataAirfoil, etc. are combined into
# the NacaAirfoil, DataAirfoil, etc. classes to solve the issue with attribute
# ordering with default values in parent classes.
# Explanation: https://stackoverflow.com/a/53085935
@dataclass
class Airfoil(ModelInput, ABC):
    """
    Airfoil object, not to be instantiated directly

    :param float or None x1: start of x/c range (optional)
    :param float or None x2: end of x/c range (optional)
    """

    x1: Optional[float] = None
    x2: Optional[float] = None

    @property
    def af_type(self):
        raise NotImplementedError

    def __str__(self):
        s = (
            f"{self.af_type.upper()} "
            f"{optional_str(self.x1)} {optional_str(self.x2)}\n"
        )
        # Because of MRO, super().__str__() will be called on the classes below
        return s + super().__str__()

    @staticmethod
    def read_x1_x2(in_str):
        # line contains the airfoil type and optionally x1 and x2 values
        split_str = in_str.split()
        if len(split_str) == 1:
            return None, None
        elif len(split_str) == 3:
            return tuple(split_str[1:])
        else:
            raise InputError(in_str)


@dataclass
class _NacaAirfoil:
    naca: str

    def __str__(self):
        return f"{self.naca}\n"


@dataclass
class _DataAirfoil:
    x_data: List[float]
    z_data: List[float]

    def __str__(self):
        s = "\n".join([f"{x} {z}" for x, z in zip(self.x_data, self.z_data)])
        return s + "\n"


@dataclass
class _FileAirfoil:
    filename: str

    def __str__(self):
        return f"{self.filename}\n"


@dataclass
class NacaAirfoil(Airfoil, _NacaAirfoil):
    """
    NACA 4-digit airfoil

    :param str naca: NACA-4 digit designation
    :param Optional[float] x1: start of x/c range (optional)
    :param Optional[float] x2: end of x/c range (optional)
    """

    @property
    def af_type(self):
        return "naca"

    @classmethod
    def from_lines(cls, lines_in):
        if len(lines_in) != 2:
            raise InputError(lines_in)
        x1, x2 = cls.read_x1_x2(lines_in[0])
        naca = lines_in[1].strip()
        if len(naca) < 4 or len(naca) > 5:
            raise ValueError(f"Invalid NACA airfoil: {naca}")
        return cls(naca, x1, x2)


@dataclass
class DataAirfoil(Airfoil, _DataAirfoil):
    """
    Airfoil defined with x and z ordinates

    :param List[float] x_data: x ordinates
    :param List[float] z_data: z ordinates
    :param Optional[float] x1: start of x/c range (optional)
    :param Optional[float] x2: end of x/c range (optional)
    """

    @property
    def af_type(self):
        return "airfoil"

    @classmethod
    def from_lines(cls, lines_in):
        x1, x2 = cls.read_x1_x2(lines_in[0])
        xs, zs = zip(
            *[
                (float(line[0]), float(line[1]))
                for line in [line.split() for line in lines_in]
            ]
        )
        return cls(list(xs), list(zs), x1, x2)


@dataclass
class FileAirfoil(Airfoil, _FileAirfoil):
    """
    Airfoil defined from .dat file

    :param str filename: .dat file name
    :param Optional[float] x1: start of x/c range (optional)
    :param Optional[float] x2: end of x/c range (optional)
    """

    @property
    def af_type(self):
        return "afile"

    @classmethod
    def from_lines(cls, lines_in):
        if len(lines_in) != 2:
            raise InputError(lines_in)
        x1, x2 = cls.read_x1_x2(lines_in[0])
        filename = lines_in[1].strip()
        return cls(filename, x1, x2)


@dataclass
class BodyProfile(FileAirfoil):
    """
    Body profile from .dat file

    :param str filename: .dat file name
    :param Optional[float] x1: start of x/c range (optional)
    :param Optional[float] x2: end of x/c range (optional)
    """

    @property
    def af_type(self):
        return "bfile"


@dataclass
class Control(ModelInput):
    """
    Adds a control surface hinge point to a section.
    Note that two adjacent sections need to contain a control to define
    a control surface.

    :param str name: control name
    :param float gain: control deflection gain
    :param float x_hinge: x/c location of the hinge
    :param int duplicate_sign: sign of deflection for duplicated surface
    :param Vector hinge_vector: hinge_vector. Defaults to Vector(0,0,0)
        which puts the hinge vector along the hinge
    """

    name: str
    gain: float
    x_hinge: float
    duplicate_sign: int
    hinge_vector: Vector = Vector(0, 0, 0)

    def __str__(self):
        return (
            "CONTROL\n#Name Gain XHinge Vector SgnDup\n"
            + f"{self.name} {self.gain} {self.x_hinge} "
            + f"{self.hinge_vector} {self.duplicate_sign}\n"
        )

    @classmethod
    def from_lines(cls, lines_in):
        if len(lines_in) != 2:
            raise InputError(lines_in)
        params = lines_in[1].split()
        if len(params) != 7:
            raise InputError(lines_in)

        name = params[0]
        gain = float(params[1])
        x_hinge = float(params[2])
        vector = Vector(*[float(s) for s in params[3:6]])
        duplicate_sign = int(float(params[6]))

        return cls(
            name=name,
            gain=gain,
            x_hinge=x_hinge,
            hinge_vector=vector,
            duplicate_sign=duplicate_sign,
        )


@dataclass
class DesignVar(ModelInput):
    """
    Defines a design variable on the section local inflow angle
    Used to solve for a twist distribution

    :param str name: variable name
    :param float weight: variable weight
    """

    name: str
    weight: float

    def __str__(self):
        return f"DESIGN\n#Name Weight\n{self.name} {self.weight}\n"

    @classmethod
    def from_lines(cls, lines_in):
        if len(lines_in) != 2:
            raise InputError(lines_in)
        params = lines_in[1].split()
        return cls(name=params[0], weight=float(params[1]))


@dataclass
class ProfileDrag(ModelInput):
    """
    Specifies a simple profile-drag CD(CL) function.
    The function is parabolic between CL1..CL2 and
    CL2..CL3, with rapid increases in CD below CL1 and above CL3.
    See AVL documentation for details

    :param List[float] cl: lift-coefficients
    :param List[float] cd: drag-coefficients
    """

    cl: List[float]
    cd: List[float]

    def __post_init__(self):
        if len(self.cl) != 3 or len(self.cd) != 3:
            raise ValueError(
                "Invalid profile drag parameters (should be of 3 CLs and 3 CDs"
            )

    def __str__(self):
        header = "CDCL\n"
        body = "\n".join([f"{cl} {cd}" for cl, cd in zip(self.cl, self.cd)])
        return header + body + "\n"

    @classmethod
    def from_lines(cls, lines_in):
        if len(lines_in) != 2:
            raise InputError(lines_in)
        params = [float(s) for s in lines_in[1].split()]
        if len(params) != 6:
            raise InputError(lines_in)
        return cls(cl=params[:3], cd=params[3:])


@dataclass
class Section(ModelInput):
    """
    Wing surface section to be used in a Surface object.

    :param Point leading_edge_point: section leading edge point
    :param float chord: the chord length
    :param Optional[float] angle: the section angle. This will rotate
        the normal vectors of the VLM panels.
        The panels will remain in stream-wise direction
    :param Optional[int] n_spanwise: number of spanwise panels
        in the next wing segment
    :param Optional[Union[Spacing, float]] span_spacing: panel distribution
        type. See `Spacing` enum
    :param Optional[Airfoil] airfoil: Airfoil to be used at the section.
        AVL uses the airfoil camber to calculate the surface normals.
    :param List[Control] or None controls: hinge deflection
    :param List[DesignVar] design_vars: perturbation of
        the local inflow angle by a set of design variables.
    :param Optional[float] cl_alpha_scaling: scales the effective dcl/dalpha
        of the section
    :param Optional[ProfileDrag] profile_drag: set custom drag polar.
        See AVL documentation for details.
    """

    leading_edge_point: Point
    chord: float
    angle: float = 0.0
    n_spanwise: Optional[int] = None
    span_spacing: Optional[Union[Spacing, float]] = None
    airfoil: Optional[Airfoil] = None
    controls: List[Control] = field(default_factory=list)
    design_vars: List[DesignVar] = field(default_factory=list)
    cl_alpha_scaling: Optional[float] = None
    profile_drag: Optional[ProfileDrag] = None

    @property
    def _header_str(self):
        header = "SECTION\n#Xle Yle Zle Chord Angle"
        section_data = f"{self.leading_edge_point} {self.chord} {self.angle}"
        if (self.n_spanwise is not None) and (self.span_spacing is not None):
            header += " NSpanwise SpanSpacing"
            section_data += f" {self.n_spanwise} {self.span_spacing}"
        return header + "\n" + section_data + "\n"

    @property
    def _body_str(self):
        body_str = "".join(
            # apply optional_str so None object return and empty string
            map(
                lambda s: optional_str(s),
                [self.airfoil, *self.controls, *self.design_vars, self.profile_drag],
            )
        )
        if self.cl_alpha_scaling is not None:
            body_str += f"CLAF\n{self.cl_alpha_scaling}\n"
        return body_str

    def __str__(self):
        return self._header_str + self._body_str

    @classmethod
    def from_lines(cls, lines_in):
        # first 2 lines contain section data, rest contains airfoils, etc.
        header_lines = lines_in[:2]
        body_lines = lines_in[2:]
        params = line_to_floats(header_lines[1])
        if len(params) != 5 and len(params) != 7:
            raise InputError(header_lines)

        kwargs = {
            "leading_edge_point": Point(*params[0:3]),
            "chord": params[3],
            "angle": params[4],
        }
        if len(params) == 7:
            kwargs["n_spanwise"] = params[5]
            kwargs["span_spacing"] = params[6]

        kwargs.update(cls.parse_lines(body_lines))

        return cls(**kwargs)


@dataclass
class Surface(ModelInput):
    """
    Wing surface

    :param str name: (unique) surface name
    :param int n_chordwise: number of chordwise panels
    :param Union[Spacing, float] chord_spacing: chordwise distribution
        type. See `Spacing` enum
    :param List[avlwrapper.Section] sections: surface sections
    :param Optional[int] n_spanwise: number of spanwise panels
    :param Optional[Union[Spacing, float]] span_spacing: spanwise
        distribution type. See `Spacing` enum
    :param Optional[int] component: component number for surface grouping.
        for detailed explanation see AVL documentation
    :param Optional[float] y_duplicate: mirrors the surface with a plane
        normal to the y-axis see AVL documentation
    :param Optional[Vector] scaling: x, y, z scaling factors
    :param Optional[Vector] translation: x, y, z translation vector
    :param Optional[float] angle: surface incidence angle
    :param Optional[ProfileDrag] profile_drag: custom drag polar.
        See AVL documentation for details.
    :param bool no_wake: disables the kutta-condition on the surface
        (will shed no wake)
    :param bool fixed: surface will not be influenced
        by freestream direction changes (for wind-tunnel walls, etc.)
    :param bool no_loads: surface forces are not included in the totals
    """

    name: str
    n_chordwise: int
    chord_spacing: Union[Spacing, float]
    sections: List[Section]
    n_spanwise: Optional[float] = None
    span_spacing: Optional[Union[Spacing, float]] = None
    component: Optional[int] = None
    y_duplicate: Optional[float] = None
    scaling: Optional[Vector] = None
    translation: Optional[Vector] = None
    angle: Optional[float] = None
    profile_drag: Optional[ProfileDrag] = None
    no_wake: bool = False
    fixed: bool = False
    no_loads: bool = False

    def __post_init__(self):
        if len(self.sections) < 2:
            raise ValueError("At least two sections are needed")

    @property
    def _header_str(self):
        header = f"SURFACE\n{self.name}\n#NChordwise ChordSpacing"
        data = f"{self.n_chordwise} {self.chord_spacing}"
        if (self.n_spanwise is not None) and (self.span_spacing is not None):
            header += " NSpanwise SpanSpacing"
            data += f" {self.n_spanwise} {self.span_spacing}"
        return header + "\n" + data + "\n"

    @property
    def _options_str(self):
        s = ""
        if self.component is not None:
            s += f"COMPONENT\n{int(self.component)}\n"
        if self.y_duplicate is not None:
            s += f"YDUPLICATE\n{self.y_duplicate}\n"
        if self.scaling is not None:
            s += f"SCALE\n{self.scaling}\n"
        if self.translation is not None:
            s += f"TRANSLATE\n{self.translation}\n"
        if self.angle is not None:
            s += f"ANGLE\n{self.angle}\n"
        if self.no_wake:
            s += "NOWAKE\n"
        if self.fixed:
            s += "NOALBE\n"
        if self.no_loads:
            s += "NOLOAD\n"
        s += optional_str(self.profile_drag)
        return s

    def __str__(self):
        return "".join([self._header_str, self._options_str, *map(str, self.sections)])

    @classmethod
    def tokenize(cls, lines):
        tokens = super().tokenize(lines)

        # special case: CDCL can be defined inside a surface as well as in
        # a section; only CDCL that's defined before any section is tokenized
        remove = []
        is_section_defined = False
        for idx, (_, token) in enumerate(tokens):
            if is_section_defined and token == "CDCL":
                remove.append(idx)
            elif token == "SECTION":
                is_section_defined = True
        for idx in remove:
            del tokens[idx]

        return tokens

    @classmethod
    def from_lines(cls, lines_in):
        # first 3 lines contain name and surface parameters
        header_lines = lines_in[:3]
        body_lines = lines_in[3:]

        name = header_lines[1].strip()
        params = line_to_floats(header_lines[2])
        if len(params) != 2 and len(params) != 4:
            raise InputError(header_lines)

        kwargs = {
            "name": name,
            "n_chordwise": int(params[0]),
            "chord_spacing": params[1],
        }
        if len(params) == 4:
            kwargs["n_spanwise"] = int(params[2])
            kwargs["span_spacing"] = params[3]

        kwargs.update(cls.parse_lines(body_lines))

        return cls(**kwargs)


@dataclass
class Body(ModelInput):
    """Non-lifting body of revolution

    :param str name: body name
    :param int n_body: number of panels on body
    :param Union[Spacing, float] body_spacing: panel distribution
    :param BodyProfile body_section: body section profile
    :param Optional[float] y_duplicate: mirror the surface normal to the y-axis
    :param Optional[Vector] scaling: x, y, z scaling factors
    :param Optional[Vector] translation: x, y, z translation vector
    """

    name: str
    n_body: int
    body_spacing: Union[Spacing, float]
    body_section: BodyProfile
    y_duplicate: Optional[float] = None
    scaling: Optional[Vector] = None
    translation: Optional[Vector] = None

    def __str__(self):
        s = (
            f"BODY\n{self.name}\n#NBody BSpace\n"
            + f"{self.n_body} {self.body_spacing}\n"
        )
        s += str(self.body_section)

        if self.y_duplicate is not None:
            s += f"YDUPLICATE\n{self.y_duplicate}\n"
        if self.scaling is not None:
            s += f"SCALE\n{self.scaling}\n"
        if self.translation is not None:
            s += f"TRANSLATE\n{self.translation}\n"

    @classmethod
    def from_lines(cls, lines_in):
        # first 3 lines contain name and body parameters
        header_lines = lines_in[:3]
        body_lines = lines_in[3:]

        name = header_lines[1].strip()
        params = line_to_floats(header_lines[2])
        if len(params) != 2:
            InputError(header_lines)
        kwargs = {"name": name, "n_body": int(params[0]), "body_spacing": params[1]}

        kwargs.update(cls.parse_lines(body_lines))

        return cls(**kwargs)


@dataclass
class Aircraft(ModelInput):
    """
    Aircraft object, top level object representing the whole model

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
    :param List[avlwrapper.Surface] surfaces: AVL surfaces
    :param List[avlwrapper.Body] bodies: AVL bodies
    """

    name: str
    reference_area: float
    reference_chord: float
    reference_span: float
    reference_point: Point
    surfaces: List[Surface] = field(default_factory=list)
    bodies: List[Body] = field(default_factory=list)
    mach: float = 0.0
    cd_p: float = 0.0
    y_symmetry: Symmetry = Symmetry.none
    z_symmetry: Symmetry = Symmetry.none
    z_symmetry_plane: float = 0.0
    
    _from_file: Optional[str] = None

    def __str__(self):
        return "\n".join(
            [
                f"{self.name}",
                f"#AVL input file written by avlwrapper {VERSION}"
                f"#Mach\n{self.mach}",
                "#iYsym iZsym Zsym",
                f"{self.y_symmetry} {self.z_symmetry} {self.z_symmetry_plane}",
                "#Sref Cref Bref",
                f"{self.reference_area} {self.reference_chord} {self.reference_span}",
                f"#Xref Yref Zref\n{self.reference_point}",
                f"{self.cd_p}",
                *map(str, self.surfaces),
                *map(str, self.bodies),
            ]
        )

    @classmethod
    def from_lines(cls, lines_in, file_path=None):
        # first 5 or 6 lines contain name and parameters
        keywords = [k[:5] for k in list(KEYWORDS[Aircraft].keys())]
        if any([lines_in[5].startswith(key) for key in keywords]):
            idx = 5
        else:
            idx = 6
        header_lines = lines_in[:idx]
        body_lines = lines_in[idx:]

        kwargs = {
            "name": header_lines[0].strip(),
            "mach": float(header_lines[1].strip()),
            "_from_file": file_path
        }

        symmetry_params = line_to_floats(header_lines[2])
        kwargs["y_symmetry"] = Symmetry(int(symmetry_params[0]))
        kwargs["z_symmetry"] = Symmetry(int(symmetry_params[1]))
        kwargs["z_symmetry_plane"] = symmetry_params[2]

        reference_params = line_to_floats(header_lines[3])
        kwargs["reference_area"] = reference_params[0]
        kwargs["reference_chord"] = reference_params[1]
        kwargs["reference_span"] = reference_params[2]
        pnt = Point(*line_to_floats(header_lines[4]))
        kwargs["reference_point"] = pnt

        kwargs.update(cls.parse_lines(body_lines))

        return cls(**kwargs)

    @classmethod
    def from_file(cls, filename):
        """
        Generates Aircraft from AVL input file
        """
        
        if not os.path.isabs(filename):
            filename = os.path.abspath(filename)

        # read file to lines
        with open(filename, "rt") as fp:
            lines = fp.readlines()

        # remove commented lines
        lines = list(filter(line_has_no_comment, lines))

        # remove empty lines
        lines = list(filter(line_is_empty, lines))

        return cls.from_lines(lines, filename)

    @property
    def external_files(self):
        files = set()
        for surface in self.surfaces:
            for section in surface.sections:
                if hasattr(section.airfoil, "filename"):
                    files.add(section.airfoil.filename)
        for body in self.bodies:
            files.add(body.body_section)
        
        if self._from_file is None:
            af_dir = os.getcwd()
        else:
            (af_dir, _) = os.path.split(self._from_file)
        files = [os.path.join(af_dir, file) for file in files]
        return files


class Geometry(Aircraft):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Use avlwrapper.Aircraft, this class will be removed in a future version",
            DeprecationWarning,
        )
        super().__init__(*args, **kwargs)


@dataclass
class Parameter(Input):
    """Parameter used in the case definition
    :param str name: Parameter name, if not in Case.CASE_PARAMETERS, it's
        assumed to by a control name
    :param float value: Parameter value
    :param str or None setting: Parameter setting,
        see `Case.VALID_SETTINGS`
    """

    name: str
    value: float
    setting: Optional[str] = None

    def __post_init__(self):
        if self.setting is None:
            self.setting = self.name

    @classmethod
    def from_lines(cls, lines_in: List[str]):
        if len(lines_in) != 1:
            raise InputError(lines_in)
        name, setting, value_str = (
            s.strip() for s in multi_split(lines_in[0], "->", "=")
        )
        value = float(value_str)
        return cls(name=name, value=value, setting=setting)

    def __str__(self):
        return f" {self.name:<12} -> {self.setting:<12} = {self.value}\n"


@dataclass
class State(Input):
    """State used in the case definition"""

    name: str
    value: float
    unit: str = ""

    @classmethod
    def from_lines(cls, lines_in: List[str]):
        if len(lines_in) != 1:
            raise InputError(lines_in)
        params = multi_split(lines_in[0], "=", " ")
        name, rest = (s.strip() for s in lines_in[0].split("="))
        if " " in rest:
            value, unit = (s.strip() for s in rest.split(" ", maxsplit=1))
        else:
            value = rest
            unit = ""
        value = float(value)
        if len(params) == 2:
            obj = cls(name=name, value=value)
        else:
            obj = cls(name=name, value=value, unit=unit)
        return obj

    def __str__(self):
        return f" {self.name:<10} = {self.value:<10} {self.unit}\n"


class Case(Input):
    """AVL analysis case containing parameters and states"""

    CASE_PARAMETERS = {
        "alpha": "alpha",
        "beta": "beta",
        "roll_rate": "pb/2V",
        "pitch_rate": "qc/2V",
        "yaw_rate": "rb/2V",
    }

    VALID_SETTINGS = {
        "alpha",
        "beta",
        "pb/2V",
        "qc/2V",
        "rb/2V",
        "CL",
        "CY",
        "Cl",
        "Cm",
        "Cn",
    }

    CASE_STATES = {
        "alpha": ("alpha", 0.0, "deg"),
        "beta": ("beta", 0.0, "deg"),
        "roll_rate": ("pb/2V", 0.0, ""),
        "pitch_rate": ("qc/2V", 0.0, ""),
        "yaw_rate": ("rb/2V", 0.0, ""),
        "CL": ("CL", 0.0, ""),
        "cd_p": ("CDo", None, ""),
        "bank": ("bank", 0.0, "deg"),
        "elevation": ("elevation", 0.0, "deg"),
        "heading": ("heading", 0.0, "deg"),
        "mach": ("Mach", None, ""),
        "velocity": ("velocity", 0.0, "m/s"),
        "density": ("density", 1.225, "kg/m^3"),
        "gravity": ("grav.acc.", 9.81, "m/s^2"),
        "turn_rad": ("turn_rad.", 0.0, "m"),
        "load_fac": ("load_fac.", 0.0, ""),
        "X_cg": ("X_cg", None, "m"),
        "Y_cg": ("Y_cg", None, "m"),
        "Z_cg": ("Z_cg", None, "m"),
        "mass": ("mass", 1.0, "kg"),
        "Ixx": ("Ixx", 1.0, "kg-m^2"),
        "Iyy": ("Iyy", 1.0, "kg-m^2"),
        "Izz": ("Izz", 1.0, "kg-m^2"),
        "Ixy": ("Ixy", 0.0, "kg-m^2"),
        "Iyz": ("Iyz", 0.0, "kg-m^2"),
        "Izx": ("Izx", 0.0, "kg-m^2"),
        "visc_CL_a": ("visc CL_a", 0.0, ""),
        "visc_CL_u": ("visc CL_u", 0.0, ""),
        "visc_CM_a": ("visc CM_a", 0.0, ""),
        "visc_CM_u": ("visc CM_u", 0.0, ""),
    }

    def __init__(self, name, *args, **kwargs):
        """
        :param str name: case name

        :param kwargs: key-value pairs
            keys should be Case.CASE_PARAMETERS, Case.CASE_STATES or a control.
            values should be a numeric value or a Parameter object
        """
        self.name = name
        if "number" in kwargs:
            self.number = kwargs.pop("number")
        else:
            self.number = 1
        self.parameters = self._set_default_parameters()
        self.states = self._set_default_states()

        self.controls = []

        for arg in args:
            if isinstance(arg, Parameter):
                key = self._get_parameter_key_by_name(arg.name)
                self.parameters[key] = arg
            elif isinstance(arg, State):
                key = self._get_state_key_by_name(arg.name)
                self.states[key] = arg

        self.update(**kwargs)

    def update(self, **kwargs):
        """
        Update case parameters and/or states

        :param kwargs: key-value pairs
            keys should be Case.CASE_PARAMETERS, Case.CASE_STATES or a control.
            values should be a numeric value or a Parameter object
        """
        for key, value in kwargs.items():
            # if a parameter object is given, add to the dict
            if isinstance(value, Parameter):
                self.parameters[key] = value
            else:
                # if the key is an existing case parameter, set the value
                if key in self.CASE_PARAMETERS:
                    param_str = self.CASE_PARAMETERS[key]
                    self.parameters[param_str].value = value
                elif key in self.CASE_STATES:
                    self.states[key].value = value
                # if an unknown key-value pair is given,
                # assume its a control and create a parameter
                else:
                    param_str = key
                    self.controls.append(key)
                    self.parameters[param_str] = Parameter(name=param_str, value=value)

    @classmethod
    def from_lines(cls, lines_in: List[str]):
        """
        Create a Case instance from lines in case-file format
        """
        # get case number and title
        re_str = r"(?<=Run case)\s*(\d+)\s*:\s*(\w+)"
        match = re.search(re_str, lines_in[0], re.IGNORECASE)
        if match is not None:
            number = int(match.group(1))
            name = match.group(2)
        else:
            warnings.warn("Case name or number not found, check format")
            number = 1
            name = "unknown"

        params = []
        for line in lines_in[1:]:
            if "->" in line:
                param = Parameter.from_lines([line.strip()])
            else:
                param = State.from_lines([line.strip()])
            params.append(param)

        return cls(name, *params, number=number)

    def _set_default_parameters(self):
        # parameters default to 0.0
        return {
            name: Parameter(name=name, setting=name, value=0.0)
            for _, name in self.CASE_PARAMETERS.items()
        }

    def _set_default_states(self):
        return {
            key: State(name=value[0], value=value[1], unit=value[2])
            for key, value in self.CASE_STATES.items()
        }

    def _check_states(self):
        for key in self.states.keys():
            if key not in self.CASE_STATES:
                raise InputError(f"Invalid state variable: {key}")

    def _check_parameters(self):
        for param in self.parameters.values():
            if (
                param.setting not in self.VALID_SETTINGS
                and param.setting not in self.controls
            ):
                raise InputError(f"Invalid setting on parameter: {param.name}.")

    def _check(self):
        self._check_parameters()
        self._check_states()

    def _get_parameter_key_by_name(self, name):
        for key, value in self.CASE_PARAMETERS.items():
            if value.lower().strip() == name.lower().strip():
                return key
        raise LookupError(f"{name} not found")

    def _get_state_key_by_name(self, name):
        for key, value in self.CASE_STATES.items():
            if value[0].lower().strip() == name.lower().strip():
                return key
        raise LookupError(f"{name} not found")

    def __str__(self):
        self._check()

        # case header
        case_str = " " + "-" * 45 + f"\n Run case {self.number:<2}:  {self.name}\n\n"

        # write parameters
        for param in self.parameters.values():
            case_str += str(param)

        case_str += "\n"

        # write cases
        for state in self.states.values():
            case_str += str(state)

        return case_str


def read_case_file(filename):
    with open(filename, "rt") as fp:
        lines = fp.readlines()

    # remove empty lines
    lines = list(filter(line_is_empty, lines))

    # remove separator lines
    lines = list(filter(lambda line: not line.strip().startswith("-"), lines))

    # split the cases
    line_idx = [idx for idx, line in enumerate(lines) if "run case" in line.lower()]
    line_idx.append(len(lines))

    cases = []
    for start, end in zip(line_idx[:-1], line_idx[1:]):
        cases.append(Case.from_lines(lines[start:end]))

    return cases


def optional_str(obj):
    """Converts to string if object is not None"""
    return str(obj) if obj is not None else ""


def line_to_floats(line):
    return [float(s) for s in line.split()]


def multi_split(str_in, *seps):
    str_lst = [str_in]
    for sep in seps:
        new_lst = []
        for s in str_lst:
            new_lst.extend(s.split(sep))
        str_lst = new_lst
    # remove empty strings
    str_lst = list(filter(lambda s: s, str_lst))
    return str_lst


def line_is_empty(line):
    return line.strip() != ""


def line_has_no_comment(line):
    return not (line.startswith("!") or line.startswith("#"))


ParameterType = namedtuple("ParameterType", ["cls", "attr", "attr_type"])


class AttrType(Enum):
    scalar = auto()
    list = auto()
    vector = auto()
    boolean = auto()


# Mapping of keywords to avlwrapper classes
PT = ParameterType  # Short-hand
KEYWORDS = {
    Aircraft: {
        "SURFACE": PT(Surface, "surfaces", AttrType.list),
        "BODY": PT(Surface, "bodies", AttrType.list),
    },
    Surface: {
        "COMPONENT": PT(None, "component", AttrType.scalar),
        "INDEX": PT(None, "component", AttrType.scalar),
        "YDUPLICATE": PT(None, "y_duplicate", AttrType.scalar),
        "SCALE": PT(None, "scaling", AttrType.vector),
        "TRANSLATE": PT(None, "translation", AttrType.vector),
        "ANGLE": PT(None, "angle", AttrType.scalar),
        "NOWAKE": PT(None, "no_wake", AttrType.boolean),
        "NOALBE": PT(None, "fixed", AttrType.boolean),
        "NOLOAD": PT(None, "no_loads", AttrType.boolean),
        "CDCL": PT(ProfileDrag, "profile_drag", AttrType.scalar),
        "SECTION": PT(Section, "sections", AttrType.list),
    },
    Body: {
        "YDUPLICATE": PT(None, "y_duplicate", AttrType.scalar),
        "SCALE": PT(None, "scaling", AttrType.vector),
        "TRANSLATE": PT(None, "translation", AttrType.vector),
        "BFILE": PT(BodyProfile, "body_section", AttrType.scalar),
    },
    Section: {
        "NACA": PT(NacaAirfoil, "airfoil", AttrType.scalar),
        "AIRFOIL": PT(DataAirfoil, "airfoil", AttrType.scalar),
        "CLAF": PT(None, "cl_alpha_scaling", AttrType.scalar),
        "CDCL": PT(ProfileDrag, "profile_drag", AttrType.scalar),
        "AFILE": PT(FileAirfoil, "airfoil", AttrType.scalar),
        "CONTROL": PT(Control, "controls", AttrType.list),
    },
}
