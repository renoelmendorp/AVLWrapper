""" AVL Wrapper session and input classes
"""
import glob
import os
import shutil
import subprocess
import logging
from tempfile import TemporaryDirectory

import tkinter as tk

from avlwrapper import Case, OutputReader, default_config

logger = logging.getLogger(__name__)

class Session(object):
    """Main class which handles AVL runs and input/output"""
    OUTPUTS = {'Totals': 'ft', 'SurfaceForces': 'fn',
               'StripForces': 'fs', 'ElementForces': 'fe',
               'StabilityDerivatives': 'st', 'BodyAxisDerivatives': 'sb',
               'HingeMoments': 'hm', 'StripShearMoments': 'vm'}

    def __init__(self, geometry, cases=None, name=None, config=default_config):
        """
        :param avlwrapper.Aircaft geometry: AVL geometry
        :param typing.Sequence[Case] cases: Cases to include in input files
        :param str name: session name, defaults to geometry name
        :param avlwrapper.Configuration config: (optional) dictionary
            containing setting
        """

        self.config = config

        self.geometry = geometry
        self.cases = self._prepare_cases(cases)
        self.name = name or self.geometry.name

        self._results = None

    def _prepare_cases(self, cases):

        # guard for cases=None
        if cases is None:
            return []

        # If not set, make sure XYZref, Mach and CD0 default to geometry input
        geom_defaults = {'X_cg': self.geometry.reference_point[0],
                         'Y_cg': self.geometry.reference_point[1],
                         'Z_cg': self.geometry.reference_point[2],
                         'mach': self.geometry.mach,
                         'cd_p': self.geometry.cd_p}

        for idx, case in enumerate(cases):
            case.number = idx + 1
            for key, val in geom_defaults.items():
                if case.states[key].value is None:
                    case.states[key].value = val
        return cases

    @property
    def model_file(self):
        return self.name + '.avl'

    @property
    def case_file(self):
        return self.name + '.case'

    @property
    def requested_output(self):
        requested_outputs = {k for k, v in self.config['output'].items()
                             if v.lower() == 'yes'}
        lc_outputs = {k.lower(): (k, v) for k, v in self.OUTPUTS.items()}

        outputs = {}
        for output in requested_outputs:
            if output not in lc_outputs:
                raise InputError("Invalid output: {}".format(output))
            name, ext = lc_outputs[output]
            outputs[name] = ext
        return outputs

    def _write_geometry(self, target_dir):
        model_path = os.path.join(target_dir, self.model_file)
        with open(model_path, 'w') as avl_file:
            avl_file.write(str(self.geometry))

    def _copy_airfoils(self, target_dir):
        airfoil_paths = self.geometry.external_files
        for airfoil_path in airfoil_paths:
            shutil.copy(airfoil_path, target_dir)

    def _write_cases(self, target_dir):
        # AVL is limited to 25 cases
        if len(self.cases) > 25:
            raise InputError('Number of cases is larger than '
                             'the supported maximum of 25.')

        case_file_path = os.path.join(target_dir, self.case_file)

        with open(case_file_path, 'w') as case_file:
            for case in self.cases:
                case_file.write(str(case))

    def _write_analysis_files(self, target_dir):
        self._write_geometry(target_dir)
        self._copy_airfoils(target_dir)
        if self.cases is not None:
            self._write_cases(target_dir)

    def run_avl(self, cmds, pre_fn, post_fn):
        with TemporaryDirectory(prefix='avl_') as working_dir:
            pre_fn(working_dir)

            process = self._get_avl_process(working_dir)
            process.communicate(input=cmds.encode())
            process.wait()

            ret = post_fn(working_dir)
        return ret

    def _get_cases_run_cmds(self, cases):
        cmds = "oper\n"
        for case in cases:
            cmds += "{0}\nx\n".format(case.number)
            for _, ext in self.requested_output.items():
                out_file = self._get_output_filename(case, ext)
                cmds += "{cmd}\n{file}\n".format(cmd=ext,
                                                 file=out_file)
        return cmds

    @property
    def _load_files_cmds(self):
        cmds = "load {0}\n".format(self.model_file)
        if self.cases:
            cmds += "case {0}\n".format(self.case_file)
        return cmds

    @property
    def _run_all_cases_cmds(self):
        cmds = self._load_files_cmds
        if self.cases:
            cmds += self._get_cases_run_cmds(self.cases)
        else:
            cmds += "oper\n"
            cmds += "x\n"
        cmds += "\nquit\n"
        return cmds

    def run_all_cases(self):
        results = self.run_avl(cmds=self._run_all_cases_cmds,
                               pre_fn=self._write_analysis_files,
                               post_fn=self._read_results)
        return results

    def _get_avl_process(self, working_dir):
        # guard for avl not being present on the system.
        # this used to be check at config read, but this allows
        # dynamic setting of the configuration
        
        if 'avl_bin' not in self.config.settings:
            raise FileNotFoundError("AVL not found or not executable,"
                    " check the configuration file")

        stdin = subprocess.PIPE
        stdout = open(os.devnull, 'w') if not self.config[
            'show_stdout'] else None

        # Buffer size = 0 required for direct stdin/stdout access
        return subprocess.Popen(args=[self.config['avl_bin']],
                                stdin=stdin,
                                stdout=stdout,
                                bufsize=0,
                                cwd=working_dir)

    def _read_results(self, target_dir):
        results = dict()
        for case in self.cases:
            results[case.name] = dict()
            for output, ext in self.requested_output.items():
                file_name = self._get_output_filename(case, ext)
                file_path = os.path.join(target_dir, file_name)
                reader = OutputReader(file_path=file_path)
                results[case.name][output] = reader.get_content()
        return results

    def _get_output_filename(self, case, ext):
        out_file = "{base}-{case}.{ext}".format(base=self.name,
                                                case=case.number,
                                                ext=ext)
        return out_file

    def show_geometry(self):
        with TemporaryDirectory(prefix='avl_') as working_dir:
            self._write_geometry(working_dir)
            cmds = self._show_geometry_cmds
            avl = self._get_avl_process(working_dir)
            run_with_close_window(avl, cmds)

    def _get_plot(self, target_dir, plot_name, file_format, resolution):
        in_file = os.path.join(target_dir, 'plot.ps')
        out_file = os.path.join(os.getcwd(), plot_name + '.{}'.format(file_format))
        if file_format == "ps":
            shutil.copyfile(src=in_file, dst=out_file)
            return [out_file]
        if 'gs_bin' not in self.config.settings:
            raise Exception("Ghostscript should be installed"
                            " and enabled in the configuration file")
        gs = self.config.settings['gs_bin']
        gs_devices = {"pdf": "pdfwrite", "png": "pngalpha", "jpeg": "jpeg"}
        cmd = [gs, '-dBATCH', '-dNOPAUSE', "-r{}".format(resolution), "-q",
               '-sDEVICE={}'.format(gs_devices[file_format]), '-sOutputFile="{}"'.format(out_file), in_file]
        subprocess.call(cmd)
        if '%d' in out_file:
            return glob.glob(out_file.replace('%d', '*'))
        else:
            return [out_file]

    def save_geometry_plot(self, file_format="ps", resolution=300):
        """ Save the geometry plot to a file.

        :param str fileformat: Either "pdf", "jpeg", "png", or "ps"
        :param int resolution: Resolution (dpi) of output file
        """
        plot_name = self.name + '-geometry'
        cmds = self._hide_plot_cmds
        cmds += self._show_geometry_cmds
        cmds += "h\n\n\nquit\n"
        return self.run_avl(cmds=cmds,
                            pre_fn=self._write_geometry,
                            post_fn=lambda d: self._get_plot(d, plot_name, file_format, resolution))

    @property
    def _hide_plot_cmds(self):
        return "plop\ng\n\n"

    @property
    def _show_geometry_cmds(self):
        cmds = "load {0}\n".format(self.model_file)
        cmds += "oper\ng\n"
        return cmds

    def show_trefftz_plot(self, case_number):
        with TemporaryDirectory(prefix='avl_') as working_dir:
            self._write_analysis_files(working_dir)
            cmds = self._load_files_cmds
            cmds += self._show_trefftz_case_cmds(case_number)
            avl = self._get_avl_process(working_dir)
            run_with_close_window(avl, cmds)

    def save_trefftz_plots(self, file_format="ps", resolution=300):
        """ Save the Trefftz plots to a file.

        :param str fileformat: Either "pdf", "jpeg", "png" or "ps"
        :param int resolution: Resolution (dpi) of output file
        """
        plot_name = self.name + '-trefftz-%d'
        cmds = self._hide_plot_cmds
        cmds += self._load_files_cmds
        if self.cases:
            for idx in range(1, len(self.cases) + 1):
                cmds += self._show_trefftz_case_cmds(idx)
                cmds += "h\n\n"
        else:
            cmds += "oper\nx\nt\nh\n\n"
        cmds += "\n\nquit\n"

        return self.run_avl(cmds=cmds,
                            pre_fn=self._write_analysis_files,
                            post_fn=lambda d: self._get_plot(d, plot_name, file_format, resolution))

    @staticmethod
    def _show_trefftz_case_cmds(case_number):
        cmds = "oper\n"
        cmds += "{}\nx\n".format(case_number)
        cmds += "t\n"
        return cmds

    def export_run_files(self, path=None):
        if path is None:
            path = os.path.join(os.getcwd(), self.name)
        if not os.path.exists(path):
            os.mkdir(path)
        self._write_analysis_files(path)
        logger.info("Input files written to: {}".format(path))


class _CloseWindow(tk.Frame):
    def __init__(self, on_open=None, on_close=None, master=None):
        # On Python 2, tk.Frame is an old-style class
        tk.Frame.__init__(self, master)

        # Make sure window is on top
        master.call('wm', 'attributes', '.', '-topmost', '1')
        self.pack()
        self._on_open = on_open
        self._on_close = on_close
        self.close_button = self.create_button()

    def create_button(self):
        # add quit method to button press
        def on_close_wrapper():
            if self._on_close is not None:
                self._on_close()
            top = self.winfo_toplevel()
            top.destroy()
        close_button = tk.Button(self, text="Close",
                                 command=on_close_wrapper)
        close_button.pack()
        return close_button

    def mainloop(self, n=0):
        if self._on_open is not None:
            self._on_open()
        tk.Frame.mainloop(self, n)


class InputError(Exception):
    pass


def run_with_close_window(avl, cmds):
    quit_cmd = '\n\nquit\n'
    tk_root = tk.Tk()

    def open_fn(): avl.stdin.write(cmds.encode())

    def close_fn():
        avl.stdin.write(quit_cmd.encode())
        avl.wait()

    app = _CloseWindow(on_open=open_fn, on_close=close_fn, master=tk_root)
    app.mainloop()
