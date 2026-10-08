"""Results of an analysis

The results are read-only mappings: their parts are available as attributes
(results[1].totals) and by name (results[1]["Totals"]). The tables inside them
are dictionaries keyed by AVL's own labels, e.g. totals["CLtot"].
"""

import math
from collections.abc import Mapping

from avlwrapper.output import Output


def _plain(value):
    """Converts results to dictionaries, lists and floats, e.g. for JSON.
    Complex numbers become [real, imaginary]."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, complex):
        return [value.real, value.imag]
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


class ResultMapping(Mapping):
    """Read-only mapping, base class of the results"""

    def __init__(self, data):
        self._data = dict(data)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"{type(self).__name__}({self._data!r})"

    def to_dict(self):
        """The results as dictionaries, lists and floats, e.g. for JSON.
        Complex numbers become [real, imaginary]."""
        return _plain(self)

    def _get(self, key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(f"'{key}' is not in the results") from None


def _item(key, doc):
    return property(lambda self: self._get(key), doc=doc)


def _output(output):
    def get(self):
        try:
            return self._data[output.value]
        except KeyError:
            raise AttributeError(
                f"'{output.value}' is not in the results, select it with "
                f"Options(outputs={{..., Output.{output.name}}})"
            ) from None

    return property(get, doc=f"{output.value} output, see Output.{output.name}")


class CaseResults(ResultMapping):
    """Results of a case"""

    name = _item("Name", "Name of the case")
    states = _item(
        "States", "States of the case as solved, e.g. alpha, CL and velocity"
    )
    totals = _output(Output.TOTALS)
    surface_forces = _output(Output.SURFACE_FORCES)
    body_forces = _output(Output.BODY_FORCES)
    strip_forces = _output(Output.STRIP_FORCES)
    strip_forces_body_axes = _output(Output.STRIP_FORCES_BODY_AXES)
    element_forces = _output(Output.ELEMENT_FORCES)
    stability_derivatives = _output(Output.STABILITY_DERIVATIVES)
    body_axis_derivatives = _output(Output.BODY_AXIS_DERIVATIVES)
    hinge_moments = _output(Output.HINGE_MOMENTS)
    strip_shear_moments = _output(Output.STRIP_SHEAR_MOMENTS)
    surface_pressures = _output(Output.SURFACE_PRESSURES)
    off_body_flow = _item(
        "OffBodyFlow",
        "Off-body flow survey, when the session has survey points",
    )


class Results(ResultMapping):
    """Results of the cases of a session, by case number"""

    def by_name(self, name):
        """
        Results of the case with this name

        :param str name: case name, the first case with this name is returned
        """
        for case in self.values():
            if case.name == name:
                return case
        raise KeyError(f"No case named '{name}'")


class EigenMode(ResultMapping):
    """
    Eigenmode: the eigenvalue with the eigenvector, all complex numbers.
    The eigenvector components are AVL's state variables: u, v, w (velocity),
    p, q, r (rates), x, y, z (position) and the, phi, psi (angles).
    """

    eigenvalue = _item("eigenvalue", "Eigenvalue, 1/s")

    @property
    def vector(self):
        """Eigenvector, by state variable"""
        return {key: value for key, value in self.items() if key != "eigenvalue"}

    @property
    def natural_frequency(self):
        """Undamped natural frequency, rad/s"""
        return abs(self.eigenvalue)

    @property
    def damped_frequency(self):
        """Frequency of the oscillation, rad/s (0 for a real eigenvalue)"""
        return abs(self.eigenvalue.imag)

    @property
    def damping_ratio(self):
        """Damping ratio, negative when unstable"""
        magnitude = abs(self.eigenvalue)
        return -self.eigenvalue.real / magnitude if magnitude else math.nan

    @property
    def period(self):
        """Period of the oscillation, s (infinite for a real eigenvalue)"""
        return (
            2 * math.pi / self.damped_frequency if self.damped_frequency else math.inf
        )

    @property
    def time_to_half_or_double(self):
        """Time to half the amplitude (stable) or to double it (unstable), s"""
        real = abs(self.eigenvalue.real)
        return math.log(2) / real if real else math.inf

    @property
    def is_stable(self):
        return self.eigenvalue.real < 0


class CaseModes(ResultMapping):
    """Eigenmode analysis of a case"""

    eigenvalues = _item("EigenValues", "Eigenvalues, complex, 1/s")
    modes = _item("EigenModes", "Eigenmodes, see EigenMode")
    system_matrix = _item("SystemMatrix", "System matrix, by column")


class ModeResults(ResultMapping):
    """Eigenmode analyses of the cases of a session, by case number"""


class MassProperties(ResultMapping):
    """
    Mass properties as computed by AVL, with 4 significant digits. Mass and
    CG are in the units of the mass file, the reference point in Lunit. The
    inertias are the elements of the inertia tensor about the CG, the same
    convention as the inertias of a run case.
    """

    mass = _item("Mass", "Mass")
    cg = _item("CG", "Centre of gravity")
    reference_point = _item("ReferencePoint", "Reference point")
    inertia = _item("Inertia", "Inertia about the CG (Ixx, Iyy, Izz, Ixy, Iyz, Izx)")
    apparent_mass = _item("ApparentMass", "Apparent mass of the air")
    apparent_inertia = _item("ApparentInertia", "Apparent inertia of the air")
