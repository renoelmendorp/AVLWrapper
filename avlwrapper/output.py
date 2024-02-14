import os.path
import re

from avlwrapper import logger
from avlwrapper.tools import (
    FLOATING_POINT_PATTERN,
    get_vars,
    line_is_not_empty,
    line_has_no_comment,
)


# pattern to match a floating point number with:
# optional leading '+' or '-'
# at least one value before the decimal point,
# at least one value after the decimal point,
# (optionally) an exponent
#   - with lowercase 'e' or uppercase 'E'
#   - (optionally) with a '+' or '-' before the power


class FileReader:
    def __init__(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, "r") as avl_file:
                self.lines = avl_file.readlines()
        else:
            raise FileNotFoundError(file_path)

    def parse(self):
        raise NotImplementedError

    @staticmethod
    def get_table_start_end(lines, header_re):
        start_line, end_line = None, None
        for line_nr, line in enumerate(lines):
            if re.search(header_re, line) is not None:
                start_line = line_nr

            # Find end of table based on the empty line
            if start_line is not None and (
                line.strip() == "" or line_nr == len(lines) - 1
            ):
                end_line = line_nr
                break

        return start_line, end_line

    @staticmethod
    def extract_header(table_lines, ignore_first=True):
        # Get headers (might contain spaces, but no double spaces)
        header = re.split(r"\s{2,}", table_lines[0])
        # remove starting and trailing spaces, empty strings and EOL
        header = list(filter(None, [s.strip() for s in header]))
        # ignore first column
        if ignore_first:
            header = header[1:]
        return header

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

    @staticmethod
    def remove_ydup(name):
        return re.sub(r"\(YDUP\)", "", name).strip()

    @staticmethod
    def split_lines(lines, re_str):
        splitted = dict()
        name = None
        next_line_name = False
        for line in lines:
            match = re.search(re_str, line)
            if match is not None:
                name = match.group(1).strip()
                if name:
                    splitted[name] = [line]
                else:
                    next_line_name = True
            elif name:
                splitted[name].append(line)
            elif next_line_name:
                name = line.strip()
                splitted[name] = [line]
                next_line_name = False
        return splitted


class GenericReader(FileReader):
    def parse(self):
        return "\n".join(self.lines)


class TotalsFileReader(FileReader):
    def parse(self):
        return get_vars(self.lines)


class _ForcesFileReader(FileReader):
    def __init__(self, file_path, header_re):
        self._header_re = header_re
        super().__init__(file_path)

    def parse(self):
        start_line, end_line = self.get_table_start_end(self.lines, self._header_re)
        table_content = self.lines[start_line:end_line]
        surface_data = self.parse_table(table_content)
        return surface_data

    def parse_table(self, table_lines):
        header = self.extract_header(table_lines)
        forces_data = dict()
        for line in table_lines[1:]:
            line_data = self.get_line_values(line)

            # ignore first column
            line_data = line_data[1:]

            name = re.findall(r"(\D*)$", line)[0].strip()

            if len(line_data) < len(header):
                raise ValueError("Incorrect table format")

            # Create results dictionary
            # Combine surfaces labeled with (YDUP)
            if "(YDUP)" in name:
                base_name = self.remove_ydup(name)
                base_data = forces_data[base_name]
                all_data = zip(header, [base_data[key] for key in header], line_data)
                forces_data[base_name] = {
                    key: base_value + value for key, base_value, value in all_data
                }
            else:
                forces_data[name] = {
                    key: value for key, value in zip(header, line_data)
                }
        return forces_data


class SurfaceFileReader(_ForcesFileReader):
    def __init__(self, file_path):
        super().__init__(file_path, r"(n\s+Area\s+CL)")


class BodyFileReader(_ForcesFileReader):
    def __init__(self, file_path):
        super().__init__(file_path, r"Ibdy\s+Length\s+Asurf")


class StripFileReader(FileReader):
    def parse(self):
        table_content = self.get_tables(
            self.lines,
            surface_re=r"Surface\s+#\s*\d+\s+(.*)",
            header_re=r"(j\s+.*Chord)",
        )
        strip_results = self.parse_tables(table_content)
        return strip_results

    def get_tables(self, lines, surface_re, header_re):
        table_lines = self.split_lines(lines, surface_re)
        table_dict = dict()
        for name, lines in list(table_lines.items()):
            start_line, end_line = self.get_table_start_end(lines, header_re)
            if start_line is not None and end_line is not None:
                table_dict[name] = lines[start_line:end_line]
        return table_dict

    def parse_tables(self, table_content, ignore_first=True, skip_ydup=False):
        strip_results = dict()
        # sort so (YDUP) surfaces are always behind the main surface
        for name in sorted(table_content.keys()):
            header = self.extract_header(table_content[name], ignore_first)

            # check for YDUP
            if "(YDUP)" in name:
                if skip_ydup:
                    continue
                else:
                    result_name = self.remove_ydup(name)
            else:
                result_name = name
                strip_results[result_name] = {key: [] for key in header}

            for data_line in table_content[name][1:]:
                # Convert to floats
                values = self.get_line_values(data_line)
                # ignore first column
                if ignore_first:
                    values = values[1:]

                if len(values) < len(header):
                    logger.warning("Table values missing. Replaced with NaN")
                    values += [float("nan")] * (len(header) - len(values))
                elif len(values) > len(header):
                    raise ValueError("Incorrect table format")

                for key, value in zip(header, values):
                    strip_results[result_name][key].append(value)
        return strip_results


class ElementFileReader(FileReader):
    def parse(self):
        data_tables = self.get_tables(self.lines)
        element_results = self.parse_tables(data_tables)

        return element_results

    def get_tables(self, lines):
        # tables split by surface
        surface_tables = self.split_lines(lines, r"Surface\s+#\s*\d+\s+(.*)")
        data_tables = dict()
        for surface_name, surface_lines in list(surface_tables.items()):
            # tables split by strip
            strip_tables = self.split_lines(surface_lines, r"Strip\s+#\s*(\d+)\s+")
            header_re = r"(I\s+X\s+Y\s+Z)"
            data_tables[surface_name] = dict()
            for strip_name, strip_lines in list(strip_tables.items()):
                start_line, end_line = self.get_table_start_end(strip_lines, header_re)
                data = strip_lines[start_line:end_line]
                data_tables[surface_name][int(strip_name)] = data
        return data_tables

    def parse_tables(self, data_tables):
        element_results = dict()
        # sort so (YDUP) surfaces are always behind the main surface
        for name in sorted(data_tables.keys()):
            # check for YDUP
            if "(YDUP)" in name:
                result_name = self.remove_ydup(name)
            else:
                result_name = name
                element_results[result_name] = dict()

            for strip in data_tables[name].keys():
                header = self.extract_header(data_tables[name][strip])
                # create empty lists
                element_results[result_name][strip] = {key: [] for key in header}
                for data_line in data_tables[name][strip][1:]:
                    values = self.get_line_values(data_line)
                    # ignore first column
                    values = values[1:]
                    for key, value in zip(header, values):
                        element_results[result_name][strip][key].append(value)
        return element_results


class StabilityFileReader(FileReader):
    @property
    def var_lines(self):
        idx = [
            i
            for (i, line) in enumerate(self.lines)
            if "Stability-axis derivatives..." in line or "Neutral point" in line
        ]
        return self.lines[idx[0] : idx[1] + 1]

    def parse(self):
        all_vars = get_vars(self.var_lines)
        controls = self.get_controls(self.lines)
        all_vars = self.replace_controls(all_vars, controls)

        return all_vars

    @staticmethod
    def get_controls(lines):
        controls = re.findall(r"(\S+)\s+(d\d+)", "".join(lines))
        return {number: name for (name, number) in controls}

    @staticmethod
    def replace_controls(var_dict, controls):
        # replace d# with control name
        new_dict = var_dict.copy()
        for key in var_dict.keys():
            match = re.search(r"d\d+", key)
            if match is not None:
                d = match.group(0)
                name = "_" + controls[d]
                new_key = re.sub(d, name, key)
                new_dict[new_key] = new_dict[key]
                new_dict.pop(key)
        return new_dict


class BodyAxisFileReader(StabilityFileReader):
    @property
    def var_lines(self):
        idx = [
            i
            for (i, line) in enumerate(self.lines)
            if "Geometry-axis derivatives..." in line
        ]
        return self.lines[idx[0] :]


class HingeFileReader(FileReader):
    def parse(self):
        results = dict()
        for line in self.lines:
            match = re.search(r"(\w+)\s+([-\dE.]+)", line)
            if match is not None:
                results[match.group(1)] = float(match.group(2))
        return results


class ShearFileReader(StripFileReader):
    def parse(self):
        table_content = self.get_tables(
            self.lines, surface_re=r"Surface:\s*\d+\s+(.*)", header_re=r"(2Y.*\s+Vz)"
        )
        results = self.parse_tables(table_content, ignore_first=False, skip_ydup=True)
        return results


class SystemMatrixFileReader(FileReader):
    def parse(self):
        # remove empty lines
        lines = list(filter(line_is_not_empty, [s.strip() for s in self.lines]))
        header = lines[0].replace("|", " ").split()
        result = {key: [] for key in header}
        for line in lines[1:]:
            values = self.get_line_values(line)
            for key, val in zip(header, values):
                result[key].append(val)
        return result


class EigenValuesFileReader(GenericReader):
    def parse(self):
        lines = filter(
            lambda s: line_has_no_comment(s) and line_is_not_empty(s),
            [s.strip() for s in self.lines],
        )
        result = dict()
        for line in lines:
            values = self.get_line_values(line)
            case_nr = str(int(values[0]))
            eigen_val = (values[1], values[2])
            if case_nr in result:
                result[case_nr].append(eigen_val)
            else:
                result[case_nr] = [eigen_val]
        return result


class OutputReader:
    """Reads AVL output files. Type is determined based on file extension"""

    _reader_classes = {
        ".ft": TotalsFileReader,
        ".fn": SurfaceFileReader,
        ".fb": BodyFileReader,
        ".fs": StripFileReader,
        ".fe": ElementFileReader,
        ".st": StabilityFileReader,
        ".sb": BodyAxisFileReader,
        ".hm": HingeFileReader,
        ".vm": ShearFileReader,
        ".sys": SystemMatrixFileReader,
        ".eig": EigenValuesFileReader,
    }

    def __init__(self, file_path):
        _, extension = os.path.splitext(file_path)
        if extension in self._reader_classes:
            self.reader = self._reader_classes[extension](file_path)
        else:
            logger.warning(f"Unknown output file: {file_path}")
            self.reader = GenericReader(file_path)

    def get_content(self):
        return self.reader.parse()
