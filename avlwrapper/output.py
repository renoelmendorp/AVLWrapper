import os.path
import re
from typing import NamedTuple

from avlwrapper import mrf
from avlwrapper.config import logger
from avlwrapper.errors import OutputError
from avlwrapper.tools import (
    FLOATING_POINT_PATTERN,
    line_is_not_empty,
    line_has_no_comment,
)


class FileReader:
    def __init__(self, file_path):
        self.file_path = file_path
        if os.path.exists(file_path):
            with open(file_path, "r") as avl_file:
                self.lines = avl_file.readlines()
        else:
            raise FileNotFoundError(file_path)

    def parse(self):
        raise NotImplementedError

    def error(self, msg):
        return OutputError(f"{type(self).__name__}: {msg} in {self.file_path}")

    @staticmethod
    def get_line_values(data_line):
        data_list = re.findall(rf"({FLOATING_POINT_PATTERN}|\*+)", data_line)
        values = []
        raised_warning = False
        for val in data_list:
            if "*" in val:
                values.append(float("nan"))
                if not raised_warning:
                    msg = (
                        "Warning: AVL returned unreadable output\n"
                        "Most likely the value contained more characters "
                        "than the AVL output formatter supports:\n"
                    )
                    logger.warning(msg + data_line)
                raised_warning = True
            else:
                values.append(float(val))
        return values


class GenericReader(FileReader):
    def parse(self):
        return "\n".join(self.lines)


class MachineReadableFileReader(FileReader):
    """Reads the outputs of the OPER menu, written in AVL's machine-readable
    format (MRF), see avlwrapper.mrf"""

    def __init__(self, file_path, body_names=None):
        super().__init__(file_path)
        self.body_names = body_names

    def parse(self):
        if not mrf.is_mrf(self.lines):
            raise self.error(
                "file is not in AVL's machine-readable format (AVL 3.40 or "
                "later writes it with the MRF command)"
            )
        return mrf.parse(self.lines, self.file_path, self.body_names)


class _TableFileReader(FileReader):
    """Base class for AVL's formatted tables, which have no machine-readable
    format: a header line with the column names, followed by rows of values
    which start with an index column"""

    def read_table(self, start, is_header):
        """
        Reads the first table after line start

        :param int start: line index to start searching for the header
        :param is_header: function which tells whether a line is the header
        :return: the columns as {name: [values]}, the index of the line
            after the table
        """
        idx = start
        while idx < len(self.lines) and not is_header(self.lines[idx]):
            idx += 1
        if idx == len(self.lines):
            raise self.error("table header not found")
        # first column is the index
        header = self.lines[idx].split()[1:]
        table = {key: [] for key in header}
        idx += 1
        for idx in range(idx, len(self.lines)):
            line = self.lines[idx].strip()
            if not line:
                # empty line before the first row
                if not table[header[0]]:
                    continue
                break
            if set(line) == {"-"}:
                break
            values = self.get_line_values(line)[1:]
            if len(values) != len(header):
                raise self.error(f"number of values and columns differ: '{line}'")
            for key, value in zip(header, values):
                table[key].append(value)
        return table, idx


class StripForcesBodyAxesFileReader(_TableFileReader):
    """Strip forces in body axes (FSB), AVL has no machine-readable format for
    them. Values have 5 to 6 significant digits."""

    def parse(self):
        result = {}
        surfaces = [
            (idx, match.group(1).strip())
            for idx, line in enumerate(self.lines)
            if (match := re.match(r"\s*Surface #\s*\d+\s+(.*)", line))
        ]
        for idx, name in surfaces:
            table, _ = self.read_table(idx, lambda line: line.split()[:1] == ["j"])
            base_name = re.sub(r"\(YDUP\)", "", name).strip()
            if base_name in result:
                # strips of the duplicated surface follow the original ones
                for key, values in table.items():
                    result[base_name][key].extend(values)
            else:
                result[base_name] = table
        return result


class OffBodyFlowFileReader(_TableFileReader):
    """Off-body flow survey (OB), AVL has no machine-readable format for it.
    Velocities are normalised with the free-stream velocity, values have 6
    decimals."""

    def parse(self):
        table, _ = self.read_table(0, lambda line: line.split()[:2] == ["I", "X"])
        return table


class SystemMatrixFileReader(FileReader):
    def parse(self):
        # remove empty lines
        lines = list(filter(line_is_not_empty, [s.strip() for s in self.lines]))
        if not lines:
            raise self.error("system matrix not found")
        header = lines[0].replace("|", " ").split()
        result = {key: [] for key in header}
        for line in lines[1:]:
            values = self.get_line_values(line)
            for key, val in zip(header, values):
                result[key].append(val)
        return result


class EigenValuesFileReader(FileReader):
    def parse(self):
        lines = filter(
            lambda s: line_has_no_comment(s) and line_is_not_empty(s),
            [s.strip() for s in self.lines],
        )
        result = dict()
        for line in lines:
            values = self.get_line_values(line)
            if len(values) < 3:
                raise self.error(f"invalid eigenvalue line '{line}'")
            case_nr = int(values[0])
            eigen_val = (values[1], values[2])
            if case_nr in result:
                result[case_nr].append(eigen_val)
            else:
                result[case_nr] = [eigen_val]
        return result


class OutputType(NamedTuple):
    name: str
    extension: str
    reader: type


# Single registry of the supported AVL outputs. The extension is also the
# AVL command which writes the file.
CASE_OUTPUTS = [
    OutputType("Totals", "ft", MachineReadableFileReader),
    OutputType("SurfaceForces", "fn", MachineReadableFileReader),
    OutputType("BodyForces", "fb", MachineReadableFileReader),
    OutputType("StripForces", "fs", MachineReadableFileReader),
    OutputType("ElementForces", "fe", MachineReadableFileReader),
    OutputType("StabilityDerivatives", "st", MachineReadableFileReader),
    OutputType("BodyAxisDerivatives", "sb", MachineReadableFileReader),
    OutputType("HingeMoments", "hm", MachineReadableFileReader),
    OutputType("StripShearMoments", "vm", MachineReadableFileReader),
    OutputType("StripForcesBodyAxes", "fsb", StripForcesBodyAxesFileReader),
]

# outputs which are written with other commands, see Session
SURFACE_PRESSURES = OutputType("SurfacePressures", "cpom", MachineReadableFileReader)
OFF_BODY_FLOW = OutputType("OffBodyFlow", "ob", OffBodyFlowFileReader)

# the MODE menu has no machine-readable format
MODE_OUTPUTS = [
    OutputType("EigenValues", "eig", EigenValuesFileReader),
    OutputType("SystemMatrix", "sys", SystemMatrixFileReader),
]


class OutputReader:
    """Reads AVL output files. Type is determined based on file extension.

    The outputs of the OPER menu (.ft, .fn, .fb, .fs, .fe, .st, .sb, .hm,
    .vm) need to be in AVL's machine-readable format (MRF).

    :param str file_path: path to the output file
    :param Optional[List[str]] body_names: (optional) names of the bodies in
        the geometry, including (YDUP) duplicates. Needed for body forces
        files, in which AVL leaves the names empty.
    """

    _reader_classes = {
        "." + output.extension: output.reader
        for output in [*CASE_OUTPUTS, *MODE_OUTPUTS, SURFACE_PRESSURES, OFF_BODY_FLOW]
    }

    def __init__(self, file_path, body_names=None):
        self.file_path = file_path
        _, extension = os.path.splitext(file_path)
        reader_class = self._reader_classes.get(extension)
        if reader_class is MachineReadableFileReader:
            self.reader = reader_class(file_path, body_names)
        elif reader_class is not None:
            self.reader = reader_class(file_path)
        else:
            logger.warning(f"Unknown output file: {file_path}")
            self.reader = GenericReader(file_path)

    def get_content(self):
        if not any(line.strip() for line in self.reader.lines):
            raise OutputError(f"{self.file_path} is empty")
        try:
            return self.reader.parse()
        except (IndexError, KeyError, ValueError) as e:
            # incomplete or unexpected file content
            reader_name = type(self.reader).__name__
            raise OutputError(
                f"{reader_name}: could not parse {self.file_path} "
                f"({type(e).__name__}: {e}), the file is incomplete or has an "
                "unexpected format"
            ) from e
