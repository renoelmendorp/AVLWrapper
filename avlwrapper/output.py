import os.path
import re

# Regular expressions used to find tables in the output files
KEY_VALUE_RE = '(\S+)\s+=\s+([-\dE.]+)'
SURFACE_RE = 'Surface\s+#\s*\d+\s+(.*)'
VM_SURFACE_RE = 'Surface:\s*\d+\s+(.*)'
STRIP_RE = 'Strip\s+#\s+(\d+)\s+'
FORCES_HEADER_RE = '(j\s+Yle\s+Chord)'
VM_HEADER_RE = '(2Y.*\s+Vz)'
HINGE_RE = '(\w+)\s+([-\dE.]+)'


class ParseError(Exception):
    pass


class OutputReader(object):

    """Reads AVL output files. Type is determined based on file extension"""
    def __init__(self, file_path):

        self.path = file_path
        _, self.extension = os.path.splitext(file_path)

    def get_content(self):
        with open(self.path, 'r') as out_file:
            content = out_file.readlines()

        if self.extension == '.ft':
            result = read_totals(content)
        elif self.extension == '.fn':
            result = read_surface_forces(content)
        elif self.extension == '.fs':
            result = read_strip_forces(content)
        elif self.extension == '.fe':
            result = read_element_forces(content)
        elif self.extension == '.st':
            result = read_stability_derivatives(content)
        elif self.extension == '.sb':
            result = read_body_derivatives(content)
        elif self.extension == '.hm':
            result = read_hinge_moments(content)
        elif self.extension == '.vm':
            result = read_strip_shear_moments(content)
        else:
            print("Unknown output file: {0}".format(self.path))
            result = []
        return result


def read_totals(content):
    return get_vars(content)


def read_surface_forces(content):

    # Find start of table based on header
    start_line, end_line = get_table_start_end(content,
                                               '(n\s+Area\s+CL)')
    table_content = content[start_line:end_line]

    surface_data = process_surface_table(table_content)
    return surface_data


def process_surface_table(table_content):
    header = extract_header(table_content)
    surface_data = dict()
    for line in table_content[1:]:
        line_data = get_line_values(line)

        # ignore first column
        line_data = line_data[1:]

        name = re.findall('(\D+)(?=\n)', line)[0].strip()

        if len(line_data) != len(header):
            raise ParseError("Incorrect table format")

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


def read_strip_forces(content):
    table_content = get_surface_tables(content, SURFACE_RE,
                                       FORCES_HEADER_RE)
    strip_results = process_surface_tables(table_content)

    return strip_results


def process_surface_tables(table_content, ignore_first=True, skip_ydup=False):
    strip_results = dict()
    # sort so (YDUP) surfaces are always behind the main surface
    for name in sorted(table_content.keys()):
        header = extract_header(table_content[name], ignore_first)

        # check for YDUP
        if '(YDUP)' in name:
            if skip_ydup:
                continue
            else:
                result_name = remove_ydup(name)
        else:
            result_name = name
            strip_results[result_name] = {key: [] for key in header}

        for data_line in table_content[name][1:]:
            # Convert to floats
            values = get_line_values(data_line)
            # ignore first column
            if ignore_first:
                values = values[1:]
            for key, value in zip(header, values):
                strip_results[result_name][key].append(value)
    return strip_results


def get_surface_tables(content, surface_re, header_re):
    table_lines = split_lines(content, surface_re)
    table_dict = dict()
    for name, lines in list(table_lines.items()):
        start_line, end_line = get_table_start_end(lines, header_re)
        if start_line is not None and end_line is not None:
            table_dict[name] = lines[start_line:end_line]
    return table_dict


def read_element_forces(content):
    data_tables = get_element_tables(content)
    element_results = process_element_tables(data_tables)

    return element_results


def get_element_tables(content):
    # tables split by surface
    surface_tables = split_lines(content, SURFACE_RE)
    data_tables = dict()
    for surface_name, surface_lines in list(surface_tables.items()):
        # tables split by strip
        strip_tables = split_lines(surface_lines,
                                   STRIP_RE)
        data_tables[surface_name] = dict()
        for strip_name, strip_lines in list(strip_tables.items()):
            start_line, end_line = (get_table_start_end(
                strip_lines, '(I\s+X\s+Y\s+Z)'))
            data = strip_lines[start_line:end_line]
            data_tables[surface_name][int(strip_name)] = data
    return data_tables


def process_element_tables(data_tables):
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


def read_stability_derivatives(content):

    idx = [i for (i, line) in enumerate(content)
           if 'Stability-axis derivatives...' in line or
           'Neutral point' in line]

    all_vars = get_vars(content[idx[0]:idx[1]+1])
    controls = get_controls(content)
    all_vars = replace_controls(all_vars, controls)

    return all_vars


def read_body_derivatives(content):
    idx = [i for (i, line) in enumerate(content)
           if 'Geometry-axis derivatives...' in line]

    all_vars = get_vars(content[idx[0]:])
    controls = get_controls(content)
    all_vars = replace_controls(all_vars, controls)

    return all_vars


def read_hinge_moments(content):
    results = dict()
    for line in content:
        match = re.search(HINGE_RE, line)
        if match is not None:
            results[match.group(1)] = float(match.group(2))
    return results


def read_strip_shear_moments(content):
    table_content = get_surface_tables(content, surface_re=VM_SURFACE_RE,
                                       header_re=VM_HEADER_RE)
    results = process_surface_tables(table_content, ignore_first=False,
                                     skip_ydup=True)
    return results


def get_vars(content):
    # Search for "key = value" tuples and store in a dictionary
    result = dict()
    for name, value in re.findall(KEY_VALUE_RE,
                                  ''.join(content)):
        result[name] = float(value)
    return result


def extract_header(table_content, ignore_first=True):
    # Get headers (might contain spaces, but no double spaces)
    header = re.split('\s{2,}', table_content[0])
    # remove starting and trailing spaces, empty strings and EOL
    header = list(filter(None, [s.strip() for s in header]))
    # ignore first column
    if ignore_first:
        header = header[1:]
    return header


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


def get_line_values(data_line):
    data_list = re.findall('([-\dE.]+|\*{8})', data_line)
    values = []
    raised_warning = False
    for val in data_list:
        if val == '*'*8:
            values.append(float('nan'))
            if not raised_warning:
                print("Warning: AVL returned unreadable output\n"
                      "Most likely the value contained more characters than "
                      "the AVL output formatter supports:\n",
                      data_line)
            raised_warning = True
        else:
            values.append(float(val))

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
