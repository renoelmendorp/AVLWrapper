"""Readers for AVL's machine-readable output format (MRF)

AVL 3.40 and later write full-precision output files with the MRF command.
Each file starts with an identifier line and a version line, e.g.:

    TOT
    VERSION 1.0

Labelled lines carry their values on the left and the labels on the right:

    1.9184E+00 -0.0000E+00 -0.0000E+00      | Alpha, pb/2V, p'b/2V

The readers return the same structure, with the same keys, as the readers of
the regular (formatted) output files in avlwrapper 0.4.
"""

import re

from avlwrapper.errors import OutputError

MRF_IDS = {
    "TOT",
    "SURF",
    "BODY",
    "STRP",
    "ELE",
    "DERMATS",
    "DERMATB",
    "HINGE",
    "VM",
    "CPOML",
}

# labels which differ from the regular output files
_RENAMES = {
    "surfaces": "Surfaces",
    "strips": "Strips",
    "vortices": "Vortices",
    "cl_perp": "cl_norm",
}


def is_mrf(lines):
    """Whether the lines are an output file in machine-readable format"""
    return (
        len(lines) > 1
        and lines[0].strip() in MRF_IDS
        and lines[1].strip().startswith("VERSION")
    )


def parse(lines, file_path, body_names=None):
    """Parses an MRF output file

    :param List[str] lines: lines of the file
    :param str file_path: file path, used in error messages
    :param Optional[List[str]] body_names: names of the bodies in the order of
        the geometry, including (YDUP) duplicates. AVL leaves the body names
        empty in the MRF body forces file.
    """
    reader = _Lines(lines, file_path)
    file_id = reader.next().strip()
    reader.next()  # version
    parsers = {
        "TOT": _parse_totals,
        "SURF": _parse_surfaces,
        "BODY": lambda r: _parse_bodies(r, body_names),
        "STRP": _parse_strips,
        "ELE": _parse_elements,
        "DERMATS": lambda r: _parse_derivatives(r, "Stability-axis derivatives"),
        "DERMATB": lambda r: _parse_derivatives(r, "Geometry-axis derivatives"),
        "HINGE": _parse_hinge_moments,
        "VM": _parse_shear_moments,
        "CPOML": _parse_surface_pressures,
    }
    return parsers[file_id](reader)


class _Lines:
    """Line cursor with error reporting"""

    def __init__(self, lines, file_path):
        self.lines = [line.rstrip("\n") for line in lines]
        self.file_path = file_path
        self.idx = 0

    def error(self, msg):
        return OutputError(f"MRF: {msg} at line {self.idx} of {self.file_path}")

    def at_end(self):
        return self.idx >= len(self.lines)

    def peek(self):
        if self.at_end():
            raise self.error("unexpected end of file")
        return self.lines[self.idx]

    def next(self):
        line = self.peek()
        self.idx += 1
        return line

    def seek(self, text):
        """Moves to the first line starting with text"""
        while not self.at_end():
            if self.peek().strip().startswith(text):
                return
            self.idx += 1
        raise self.error(f"'{text}' not found")

    def skip_to(self, text):
        """Moves to the line after the first line starting with text"""
        self.seek(text)
        self.idx += 1

    def expect(self, keyword):
        line = self.next().strip()
        if line != keyword:
            raise self.error(f"expected '{keyword}', found '{line}'")

    def values(self):
        """Values of the next line, labels are ignored"""
        return _split(self.next())[0]

    def count(self, label):
        """Reads the next count of label, e.g. '   5  | # control vars'"""
        while not self.at_end():
            data, _, text = self.next().partition("|")
            if label in text:
                return int(data)
        raise self.error(f"number of {label} not found")


def _split(line):
    """Splits a line into its values and labels"""
    data, _, label = line.partition("|")
    try:
        values = [float(v) for v in data.split()]
    except ValueError:
        values = []
    # the labels follow the description, e.g. "z' force CL  : CLa, CLb"
    _, colon, label_list = label.partition(":")
    if not colon:
        label_list = label
    labels = [s.strip() for s in label_list.split(",") if s.strip()]
    if len(labels) == 1 and len(values) > 1:
        # space separated labels, e.g. "n Area CL CD"
        labels = labels[0].split()
    else:
        # last word is the name, e.g. "Neutral point  Xnp"
        labels = [s.split()[-1] for s in labels]
    return values, [_RENAMES.get(s, s) for s in labels]


def _index_row(line):
    """Values and labels of a row starting with an I4 index, the index is
    dropped (it overflows to '****' above 9999)"""
    return _split(line[4:])


def _fixed_ints(line, n, width=4):
    """Integers written without separators, e.g. format 3(I4)"""
    return [int(line[i * width : (i + 1) * width]) for i in range(n)]


def _labelled_values(reader, result):
    """Adds the values of the next line to result"""
    values, labels = _split(reader.next())
    if len(values) != len(labels):
        raise reader.error("number of values and labels differ")
    result.update(zip(labels, values))


def _named_values(reader):
    """Reads a block of a count and 'value name' lines"""
    result = {}
    for _ in range(int(reader.next().split()[0])):
        value, name = reader.next().split("|")[0].split()[:2]
        result[name] = float(value)
    return result


def _names(reader, label):
    return [reader.next().strip() for _ in range(reader.count(label))]


def _remove_ydup(name):
    return re.sub(r"\(YDUP\)", "", name).strip()


def _parse_totals(reader):
    result = {}
    while not reader.at_end():
        line = reader.peek().strip()
        if line in ("CONTROL", "DESIGN"):
            reader.next()
            result.update(_named_values(reader))
        elif "|" in line:
            _labelled_values(reader, result)
        else:
            # title, configuration name, axes, case name
            reader.next()
    return result


def _parse_derivatives(reader, section):
    reader.skip_to(section)
    result = {}
    controls, design = [], []
    while not reader.at_end():
        line = reader.peek()
        if "|" not in line:
            # column descriptions, e.g. "alpha, beta"
            reader.next()
        elif "# control vars" in line:
            controls = _names(reader, "control vars")
        elif "# design vars" in line:
            design = _names(reader, "design vars")
        else:
            values, labels = _split(reader.next())
            if len(labels) == 1 and labels[0].endswith("*"):
                # derivatives with respect to the controls or design variables,
                # e.g. CLd* or CDffg*, named as CL_elevator
                base, kind = labels[0][:-2], labels[0][-2]
                names = controls if kind == "d" else design
                if len(values) != len(names):
                    raise reader.error("number of values and variables differ")
                result.update({f"{base}_{n}": v for n, v in zip(names, values)})
            else:
                if len(values) != len(labels):
                    raise reader.error("number of values and labels differ")
                result.update(zip(labels, values))
                if "Xnp" in labels:
                    # the spiral stability ratio below is not included
                    break
    return result


def _add_forces(result, name, data):
    """Adds forces to result, forces of (YDUP) duplicates are added"""
    if "(YDUP)" in name:
        base = result[_remove_ydup(name)]
        for key, value in data.items():
            base[key] += value
    else:
        result[name] = data


def _parse_surfaces(reader):
    result = {}
    for _ in range(reader.count("surfaces")):
        reader.expect("SURFACE")
        name = reader.next().strip()
        values, labels = _split(reader.next())
        # second line: forces referred to the surface area
        reader.next()
        # first column is the surface number
        _add_forces(result, name, dict(zip(labels[1:], values[1:])))
    return result


def _parse_bodies(reader, body_names):
    result = {}
    n_bodies = reader.count("bodies")
    if body_names is not None and len(body_names) != n_bodies:
        raise reader.error(f"expected {len(body_names)} bodies, found {n_bodies}")
    for idx in range(n_bodies):
        reader.expect("BODY")
        # AVL 3.52 writes an empty name (NUL characters)
        name = reader.next().replace("\x00", "").strip()
        if not name:
            if body_names is None:
                raise reader.error("body name missing")
            name = body_names[idx]
        values, labels = _split(reader.next())
        # first column is the body number
        _add_forces(result, name, dict(zip(labels[1:], values[1:])))
    return result


def _parse_strips(reader):
    result = {}
    for _ in range(reader.count("surfaces")):
        reader.expect("SURFACE")
        name = reader.next().strip()
        _, _, n_strips, _ = reader.values()
        reader.skip_to("Strip Forces")
        header = [_RENAMES.get(s.strip(), s.strip()) for s in reader.next().split(",")]
        # first column is the strip number
        header = header[1:]
        table = result.setdefault(_remove_ydup(name), {key: [] for key in header})
        for _ in range(int(n_strips)):
            values = _index_row(reader.next())[0]
            if len(values) != len(header):
                raise reader.error("number of values and columns differ")
            for key, value in zip(header, values):
                table[key].append(value)
    return result


def _parse_elements(reader):
    result = {}
    for _ in range(reader.count("surfaces")):
        reader.expect("SURFACE")
        name = reader.next().strip()
        _, _, n_strips, _ = reader.values()
        surface = result.setdefault(_remove_ydup(name), {})
        for _ in range(int(n_strips)):
            reader.skip_to("STRIP")
            strip, n_elements, _ = _fixed_ints(reader.next(), 3)
            # strip geometry and forces
            reader.next()
            reader.next()
            elements = None
            for _ in range(int(n_elements)):
                values, labels = _index_row(reader.next())
                # first label is the element number
                labels = labels[1:]
                if elements is None:
                    elements = {key: [] for key in labels}
                for key, value in zip(labels, values):
                    elements[key].append(value)
            surface[strip] = elements or {}
    return result


def _parse_hinge_moments(reader):
    reader.next()  # axes
    reader.next()  # Sref, Cref
    result = {}
    for _ in range(reader.count("controls")):
        value, name = reader.next().split("|")[0].split()
        result[name] = float(value)
    return result


def _parse_shear_moments(reader):
    result = {}
    reader.seek("SURFACE")
    while not reader.at_end():
        reader.expect("SURFACE")
        name = reader.next().strip()
        reader.next()  # surface number, number of strips
        reader.next()  # 2Ymin/Bref, 2Ymax/Bref
        rows = []
        while not reader.at_end() and reader.peek().strip() != "SURFACE":
            line = reader.next()
            if "|" in line:
                rows.append(line)
        if "(YDUP)" in name:
            continue
        # the first row is labelled "... : root"
        header = [s.strip() for s in rows[0].split("|")[1].split(":")[0].split(",")]
        table = {key: [] for key in header}
        for row in rows:
            for key, value in zip(header, _split(row)[0]):
                table[key].append(value)
        result[name] = table
    return result


def _grid(reader, n_rows, n_columns):
    """Reads a block of n_rows * n_columns lines, labelled by the line before
    it, e.g. 'VERTEX_GRID (x_lo, x_up, y_lo, y_up, z_lo, z_up)'. Each column
    is a list of n_rows lists of n_columns values."""
    labels = reader.next().partition("(")[2].rstrip(")").split(",")
    labels = [label.strip() for label in labels]
    grid = {label: [] for label in labels}
    for _ in range(n_rows):
        for label in labels:
            grid[label].append([])
        for _ in range(n_columns):
            values = reader.values()
            if len(values) != len(labels):
                raise reader.error("number of values and labels differ")
            for label, value in zip(labels, values):
                grid[label][-1].append(value)
    return grid


def _parse_surface_pressures(reader):
    """Pressures on the outer mould lines of the surfaces (CPOM command)"""
    result = {}
    for _ in range(reader.count("surfaces")):
        reader.expect("SURFACE")
        name = reader.next().strip()
        component = int(reader.values()[0])
        n_span, n_chord = (int(v) for v in reader.values())
        reader.next()  # imags
        n_sections = int(reader.values()[0])
        indices = []
        while len(indices) < n_sections:
            indices.extend(int(v) for v in reader.next().split())
        reader.seek("VERTEX_GRID")
        vertices = _grid(reader, n_span + 1, n_chord + 1)
        reader.seek("ELEMENT_CP")
        elements = _grid(reader, n_span, n_chord)
        result[name] = {
            "Component": component,
            "SectionIndices": indices,
            "VertexGrid": vertices,
            "ElementCp": elements,
        }
    return result
