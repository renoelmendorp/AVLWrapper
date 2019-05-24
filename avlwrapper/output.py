import os.path
import re

class ParseError(Exception):
    pass

class OutputReader(object):

    SURFACE_RE = 'Surface\s+#\s*\d+\s+(.*)'
    STRIP_RE = 'Strip\s+#\s+(\d+)\s+'

    """Reads AVL output files. Type is determined based on file extension"""
    def __init__(self, file_path):

        self.path = file_path
        _, self.extension = os.path.splitext(file_path)

    def get_content(self):
        with open(self.path, 'r') as out_file:
            content = out_file.readlines()

        if self.extension == '.ft':
            result = self._read_totals(content)
        elif self.extension == '.fn':
            result = self._read_surface_forces(content)
        elif self.extension == '.fs':
            result = self._read_strip_forces(content)
        elif self.extension == '.fe':
            result = self._read_element_forces(content)
        elif self.extension == '.st':
            result = self._read_stability_derivatives(content)
        elif self.extension == '.sb':
            result = self._read_body_derivatives(content)
        elif self.extension == '.hm':
            result = self._read_hinge_moments(content)
        else:
            print("Unknown output file: {0}".format(self.path))
            result = []
        return result

    def _read_totals(self, content):
        return get_vars(content)

    def _read_surface_forces(self, content):

        # Find start of table based on header
        start_line, end_line = get_table_start_end(content,
                                                   '(n\s+Area\s+CL)')
        table_content = content[start_line:end_line]

        surface_data = self._process_surface_table(table_content)
        return surface_data

    def _process_surface_table(self, table_content):
        header = extract_header(table_content)
        surface_data = dict()
        for line in table_content[1:]:
            line_data = get_line_values(line)

            # ignore first column
            line_data = line_data[1:]

            name = re.findall('(\D+)(?=\n)', line)[0].strip()

            if len(line_data) != len(header):
                raise ParseError("Incorrect table format in file {0}"
                                 .format(self.path))

            # Create results dictionary
            # Combine surfaces labeled with (YDUP)
            if '(YDUP)' in name:
                base_name = remove_ydup(name)
                base_data = surface_data[base_name]
                all_data = zip(header, [base_data[key]
                                        for key in header], line_data)
                surface_data[base_name] = {key: base_value + value
                                           for key, base_value, value
                                           in all_data}
            else:
                surface_data[name] = {key: value
                                      for key, value in zip(header,
                                                            line_data)}
        return surface_data

    def _read_strip_forces(self, content):

        table_content = self._get_surface_tables(content)
        strip_results = self.process_surface_tables(table_content)

        return strip_results

    def process_surface_tables(self, table_content):
        strip_results = dict()
        # sort so (YDUP) surfaces are always behind the main surface
        for name in sorted(table_content.keys()):
            header = extract_header(table_content[name])

            # check for YDUP
            if '(YDUP)' in name:
                result_name = remove_ydup(name)
            else:
                result_name = name
                strip_results[result_name] = {key: [] for key in header}

            for data_line in table_content[name][1:-1]:
                # Convert to floats
                values = get_line_values(data_line)
                # ignore first column
                values = values[1:]
                for key, value in zip(header, values):
                    strip_results[result_name][key].append(value)
        return strip_results

    def _get_surface_tables(self, content):
        table_lines = split_lines(content, self.SURFACE_RE)
        table_dict = dict()
        for name, lines in list(table_lines.items()):
            re_str = '(j\s+Yle\s+Chord)'
            start_line, end_line = get_table_start_end(lines, re_str)
            if start_line is not None and end_line is not None:
                table_dict[name] = lines[start_line:end_line]
        return table_dict

    def _read_element_forces(self, content):
        data_tables = self._get_element_tables(content)
        element_results = self._process_element_tables(data_tables)

        return element_results

    def _get_element_tables(self, content):
        # tables split by surface
        surface_tables = split_lines(content, self.SURFACE_RE)
        data_tables = dict()
        for surface_name, surface_lines in list(surface_tables.items()):
            # tables split by strip
            strip_tables = split_lines(surface_lines,
                                       self.STRIP_RE)
            data_tables[surface_name] = dict()
            for strip_name, strip_lines in list(strip_tables.items()):
                start_line, end_line = (get_table_start_end(
                    strip_lines, '(I\s+X\s+Y\s+Z)'))
                data = strip_lines[start_line:end_line]
                data_tables[surface_name][int(strip_name)] = data
        return data_tables

    def _process_element_tables(self, data_tables):
        element_results = dict()
        # sort so (YDUP) surfaces are always behind the main surface
        for name in sorted(data_tables.keys()):
            # check for YDUP
            if '(YDUP)' in name:
                result_name = remove_ydup(name)
            else:
                result_name = name
                element_results[result_name] = dict()

            for strip in data_tables[name].keys():
                header = extract_header(data_tables[name][strip])
                # create empty lists
                element_results[result_name][strip] = {key: []
                                                       for key in header}
                for data_line in data_tables[name][strip][1:]:
                    values = get_line_values(data_line)
                    # ignore first column
                    values = values[1:]
                    for key, value in zip(header, values):
                        element_results[result_name][strip][key].append(value)
        return element_results

    def _read_stability_derivatives(self, content):

        idx = [i for (i, line) in enumerate(content)
               if 'Stability-axis derivatives...' in line or
               'Neutral point' in line]

        all_vars = get_vars(content[idx[0]:idx[1]+1])
        controls = get_controls(content)
        all_vars = replace_controls(all_vars, controls)

        return all_vars

    def _read_body_derivatives(self, content):
        idx = [i for (i, line) in enumerate(content)
               if 'Geometry-axis derivatives...' in line]

        all_vars = get_vars(content[idx[0]:])
        controls = get_controls(content)
        all_vars = replace_controls(all_vars, controls)

        return all_vars

    @staticmethod
    def _read_hinge_moments(content):
        results = dict()
        for line in content:
            match = re.search('(\w+)\s+([-\dE.]+)', line)
            if match is not None:
                results[match.group(1)] = float(match.group(2))
        return results

def get_vars(content):
    # Search for "key = value" tuples and store in a dictionary
    result = dict()
    for name, value in re.findall('(\S+)\s+=\s+([-\dE.]+)',
                                  ''.join(content)):
        result[name] = float(value)
    return result

def extract_header(table_content):
    # Get headers (might contain spaces, but no double spaces)
    header = re.split('\s{2,}', table_content[0])
    # remove starting and trailing spaces, empty strings and EOL
    header = list(filter(None, [s.strip() for s in header]))
    # ignore first column
    header = header[1:]
    return header

def split_lines(lines, re_str):
    splitted = dict()
    name = None
    for line in lines:
        match = re.search(re_str, line)
        if match is not None:
            name = match.group(1).strip()
            splitted[name] = [line]
        elif name is not None:
            splitted[name].append(line)

    return splitted

def get_line_values(data_line):
    values = [float(s) for s in re.findall('([-\dE.]+)', data_line)]
    return values

def remove_ydup(name):
    return re.sub('\(YDUP\)', '', name).strip()

def get_table_start_end(content, re_str):
    start_line, end_line = None, None
    for line_nr, line in enumerate(content):
        if re.search(re_str, line) is not None:
            start_line = line_nr

        # Find end of table based on the empty line
        if (start_line is not None
                and (line.strip() == '' or line_nr == len(content)-1)):
            end_line = line_nr
            break

    return start_line, end_line

def get_controls(content):
    controls = re.findall('(\S+)\s+(d\d+)', ''.join(content))
    return {number: name for (name, number) in controls}

def replace_controls(var_dict, controls):
    # replace d# with control name
    new_dict = var_dict.copy()
    for key in var_dict.keys():
        match = re.search('d\d+', key)
        if match is not None:
            d = match.group(0)
            name = controls[d]
            new_key = re.sub(d, name, key)
            new_dict[new_key] = new_dict[key]
            new_dict.pop(key)
    return new_dict