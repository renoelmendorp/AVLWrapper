"""Readers for results which AVL only prints to the screen"""

import re

from avlwrapper.errors import OutputError
from avlwrapper.model import Point

# components of an eigenvector, as listed by AVL
EIGENVECTOR_COMPONENTS = [
    "u",
    "v",
    "w",
    "p",
    "q",
    "r",
    "x",
    "y",
    "z",
    "the",
    "phi",
    "psi",
]


def _float(text):
    # F11.4 fields overflow to asterisks
    text = text.strip()
    return float("nan") if "*" in text else float(text)


def _eigenvector_line(line):
    """
    Reads a line like
    ' u  :     0.0000     0.0000      v  :    -0.8010     0.0000      x  : ...'
    format (1X, A,':', 2F11.4, 6X, A,':', 2F11.4, 6X, A,':', 2G12.4)
    """
    fields = {}
    for start, width in ((1, 11), (33, 11), (65, 12)):
        name = line[start : start + 3].strip()
        values = line[start + 4 : start + 4 + 2 * width]
        fields[name] = (_float(values[:width]), _float(values[width:]))
    return fields


def read_eigenmodes(avl_output):
    """
    Eigenvalues and eigenvectors, as listed by the MODE menu's N command

    :param str avl_output: output of AVL
    :return: {case number: [{"eigenvalue": (re, im), "u": (re, im), ...}]}
    """
    lines = avl_output.splitlines()
    result = {}
    case_number = None
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        case_match = re.match(r"^ Run case\s*(\d+):", line)
        mode_match = re.match(r"^\s+mode\s*\d+:\s*(\S+)\s+(\S+)\s*$", line)
        if case_match:
            case_number = int(case_match.group(1))
            result[case_number] = []
        elif mode_match and case_number is not None:
            mode = {"eigenvalue": (_float(mode_match[1]), _float(mode_match[2]))}
            try:
                for vector_line in lines[idx + 1 : idx + 5]:
                    mode.update(_eigenvector_line(vector_line))
            except ValueError as e:
                raise OutputError(f"Invalid eigenvector in AVL output: {e}") from e
            if set(mode) != {"eigenvalue", *EIGENVECTOR_COMPONENTS}:
                raise OutputError("Incomplete eigenvector in AVL output")
            result[case_number].append(mode)
            idx += 4
        idx += 1
    return result


def _numbers(text):
    """Numbers in text, units are skipped"""
    numbers = []
    for word in text.split():
        try:
            numbers.append(_float(word))
        except ValueError:
            pass
    return numbers


def read_mass_properties(avl_output):
    """
    Mass properties, as listed by the MSHO command

    The inertias are the elements of the inertia tensor about the CG (so the
    off-diagonal elements are -Ixy, -Iyz, -Izx), the same convention as the
    inertias of a run case. Values have 4 significant digits.

    :param str avl_output: output of AVL
    """
    lines = avl_output.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("Mass        ="):
            start = idx
    if start is None:
        raise OutputError("Mass properties not found in AVL output")
    # the mass is listed twice when the mass unit isn't 1; the last listing
    # of the mass and CG is in the mass file's units
    while lines[start - 1].strip().startswith("Mass        ="):
        start -= 1

    result = {}
    tensors = []
    tensor = None
    for line in lines[start:]:
        text = line.strip()
        label, _, values = text.partition("=")
        if text.startswith("Mass "):
            result["Mass"] = _numbers(values)[0]
        elif text.startswith("Ref. x,y,z"):
            result["ReferencePoint"] = Point(*_numbers(values)[:3])
        elif text.startswith("C.G. x,y,z"):
            result["CG"] = Point(*_numbers(values)[:3])
        elif "|" in text:
            # rows of a symmetric 3x3 matrix, upper triangle only
            row = _numbers(text.split("|")[1])
            if tensor is None or len(tensor) == 3:
                tensor = []
                tensors.append(tensor)
            tensor.append(row)
        elif text.startswith("AVL") or text.startswith("Use MSET"):
            break

    if len(tensors) != 3 or any(len(t) != 3 for t in tensors):
        raise OutputError("Incomplete mass properties in AVL output")

    def elements(tensor, names):
        (xx, xy, xz), (yy, yz), (zz,) = tensor
        return dict(zip(names, (xx, yy, zz, xy, yz, xz)))

    inertia_names = ("Ixx", "Iyy", "Izz", "Ixy", "Iyz", "Izx")
    result["Inertia"] = elements(tensors[0], inertia_names)
    result["ApparentMass"] = elements(
        tensors[1], ("mxx", "myy", "mzz", "mxy", "myz", "mxz")
    )
    result["ApparentInertia"] = elements(tensors[2], inertia_names)
    return result
