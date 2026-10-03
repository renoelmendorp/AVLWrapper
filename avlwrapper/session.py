"""AVL Wrapper session and input classes"""

import copy
import glob
import os
import subprocess
import shutil
from tempfile import TemporaryDirectory

from avlwrapper.config import default_config, is_enabled, logger
from avlwrapper.errors import AvlExecutionError, InputError, OutputError
from avlwrapper.output import CASE_OUTPUTS, MODE_OUTPUTS, OutputReader


class Session:
    """Main class which handles AVL runs and input/output"""

    OUTPUTS = {output.name: output.extension for output in CASE_OUTPUTS}

    MODE_OUTPUTS = {output.name: output.extension for output in MODE_OUTPUTS}

    def __init__(
        self,
        geometry,
        cases=None,
        mass_dist=None,
        name=None,
        config=default_config,
        timeout=None,
    ):
        """
        :param avlwrapper.Aircraft geometry: AVL geometry
        :param List[Case] cases: Cases to include in input files. The session
            works on copies, the given cases are not modified.
        :param Optional[MassDistribution] mass_dist: Mass distribution
        :param str name: session name, defaults to geometry name
        :param avlwrapper.Configuration config: (optional) dictionary
            containing setting
        :param Optional[float] timeout: (optional) maximum run time of AVL
            in seconds
        """

        self.config = config
        self.config.apply_log_level()
        self.timeout = timeout

        self.geometry = geometry
        self.cases = self._prepare_cases(cases)
        self.name = name or self.geometry.name
        self.mass_dist = mass_dist

    def _prepare_cases(self, cases):
        # guard for cases=None
        if cases is None:
            return []

        # If not set, make sure XYZref, Mach and CD0 default to geometry input
        geom_defaults = {
            "X_cg": self.geometry.reference_point[0],
            "Y_cg": self.geometry.reference_point[1],
            "Z_cg": self.geometry.reference_point[2],
            "mach": self.geometry.mach,
            "cd_p": self.geometry.cd_p,
        }

        # the cases are owned by the caller, so work on copies
        cases = copy.deepcopy(list(cases))
        for idx, case in enumerate(cases):
            case.number = idx + 1
            for key, val in geom_defaults.items():
                if case.states[key].value is None:
                    case.states[key].value = val
        return cases

    @property
    def model_file(self):
        return self.name + ".avl"

    @property
    def case_file(self):
        return self.name + ".case"

    @property
    def mass_file(self):
        return self.name + ".mass"

    @property
    def requested_output(self):
        requested_outputs = {
            k.lower() for k, v in self.config["output"].items() if is_enabled(v)
        }
        lc_outputs = {k.lower(): (k, v) for k, v in self.OUTPUTS.items()}

        outputs = {}
        for output in requested_outputs:
            if output not in lc_outputs:
                raise ValueError(f"Invalid output: {output}")
            name, ext = lc_outputs[output]
            outputs[name] = ext
        return outputs

    def _write_geometry(self, target_dir):
        model_path = os.path.join(target_dir, self.model_file)
        with open(model_path, "w") as avl_file:
            avl_file.write(str(self.geometry))

    def _write_mass(self, target_dir):
        mass_path = os.path.join(target_dir, self.mass_file)
        with open(mass_path, "w") as mass_file:
            mass_file.write(str(self.mass_dist))

    def _copy_airfoils(self, target_dir):
        airfoil_paths = self.geometry.external_files
        for airfoil_path in airfoil_paths:
            shutil.copy(airfoil_path, target_dir)

    def _write_cases(self, target_dir):
        # AVL is limited to 25 cases
        if len(self.cases) > 25:
            raise RuntimeError(
                "Number of cases is larger than " "the supported maximum of 25."
            )

        valid_controls = self.geometry.control_names
        for case in self.cases:
            case.validate(valid_controls)

        case_file_path = os.path.join(target_dir, self.case_file)

        with open(case_file_path, "w") as case_file:
            for case in self.cases:
                case_file.write(str(case))

    def _write_analysis_files(self, target_dir):
        self._write_geometry(target_dir)
        self._copy_airfoils(target_dir)
        if self.cases:
            self._write_cases(target_dir)
        if self.mass_dist:
            self._write_mass(target_dir)

    def run_avl(self, cmds, pre_fn, post_fn):
        with TemporaryDirectory(prefix="avl_") as working_dir:
            pre_fn(working_dir)

            output = self._run_avl_process(cmds, working_dir)

            # AVL doesn't reliably report failures with its exit status, they
            # show up as missing or incomplete output files
            try:
                ret = post_fn(working_dir)
            except (FileNotFoundError, OutputError) as e:
                raise AvlExecutionError(
                    f"AVL did not produce the expected output ({e})", output
                ) from e
        return ret

    def _run_avl_process(self, cmds, working_dir):
        try:
            process = subprocess.run(
                [self._get_avl_bin()],
                input=cmds.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=working_dir,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            output = (e.stdout or b"").decode(errors="replace")
            raise AvlExecutionError(
                f"AVL did not finish within {self.timeout} s", output
            ) from e

        output = process.stdout.decode(errors="replace")
        if self.config["show_stdout"]:
            print(output)
        logger.debug(output)

        if process.returncode != 0:
            raise AvlExecutionError(
                f"AVL exited with status {process.returncode}", output
            )
        return output

    def _get_cases_run_cmds(self, cases):
        cmds = "oper\n"
        for case in cases:
            cmds += "{0}\nx\n".format(case.number)
            for _, ext in self.requested_output.items():
                out_file = self._get_output_filename(case, ext)
                cmds += "{cmd}\n{file}\n".format(cmd=ext, file=out_file)
        return cmds

    @property
    def _load_files_cmds(self):
        cmds = f"load {self.model_file}\n"
        if self.cases:
            cmds += f"case {self.case_file}\n"
        if self.mass_dist:
            cmds += f"mass {self.mass_file}\n"
            cmds += f"mset\n\n"
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
        results = self.run_avl(
            cmds=self._run_all_cases_cmds,
            pre_fn=self._write_analysis_files,
            post_fn=self._read_case_results,
        )
        return results

    @property
    def _run_mode_analysis_cmds(self):
        cmds = self._load_files_cmds
        cmds += self._hide_plot_cmds
        cmds += "mode\n"
        cmds += "n\n"
        cmds += f"s\n{self.name}.sys\n"
        cmds += f"w\n{self.name}.eig\n"
        cmds += "\nquit\n"
        return cmds

    def run_mode_analysis(self):
        return self.run_avl(
            cmds=self._run_mode_analysis_cmds,
            pre_fn=self._write_analysis_files,
            post_fn=self._read_mode_results,
        )

    def _get_avl_bin(self):
        # guard for avl not being present on the system.
        # this used to be check at config read, but this allows
        # dynamic setting of the configuration
        if "avl_bin" not in self.config.settings:
            raise FileNotFoundError(
                "AVL not found or not executable," " check the configuration file"
            )
        else:
            return self.config["avl_bin"]

    def _get_avl_process(self, working_dir):
        """Starts AVL for interactive use: commands are written to stdin"""
        stdout = None if self.config["show_stdout"] else subprocess.DEVNULL

        # Buffer size = 0 required for direct stdin/stdout access
        return subprocess.Popen(
            args=[self._get_avl_bin()],
            stdin=subprocess.PIPE,
            stdout=stdout,
            bufsize=0,
            cwd=working_dir,
        )

    def _read_case_results(self, target_dir):
        results = dict()
        for case in self.cases:
            results[case.number] = {"Name": case.name}
            for output, ext in self.requested_output.items():
                file_name = self._get_output_filename(case, ext)
                file_path = os.path.join(target_dir, file_name)
                reader = OutputReader(file_path=file_path)
                results[case.number][output] = reader.get_content()
        return results

    def _get_output_filename(self, case, ext):
        out_file = "{base}-{case}.{ext}".format(
            base=self.name, case=case.number, ext=ext
        )
        return out_file

    def _read_mode_results(self, target_dir):
        results = dict()
        for name, ext in self.MODE_OUTPUTS.items():
            file_path = os.path.join(target_dir, f"{self.name}.{ext}")
            results[name] = OutputReader(file_path=file_path).get_content()
        return results

    def show_geometry(self):
        with TemporaryDirectory(prefix="avl_") as working_dir:
            self._write_geometry(working_dir)
            cmds = self._show_geometry_cmds
            avl = self._get_avl_process(working_dir)
            run_with_close_window(avl, cmds)

    def _get_plot(self, target_dir, plot_name, file_format, resolution, output_dir):
        in_file = os.path.join(target_dir, "plot.ps")
        if not os.path.exists(in_file):
            raise FileNotFoundError(in_file)
        if output_dir is None:
            output_dir = os.getcwd()
        out_file = os.path.join(output_dir, plot_name + ".{}".format(file_format))
        if file_format == "ps":
            shutil.copyfile(src=in_file, dst=out_file)
            return [out_file]
        gs_devices = {"pdf": "pdfwrite", "png": "pngalpha", "jpeg": "jpeg"}
        if file_format not in gs_devices:
            raise InputError(f"Invalid file format: {file_format}")
        if "gs_bin" not in self.config.settings:
            raise FileNotFoundError(
                "Ghostscript should be installed"
                " and enabled in the configuration file"
            )
        gs = self.config.settings["gs_bin"]
        cmd = [
            gs,
            "-dBATCH",
            "-dNOPAUSE",
            "-r{}".format(resolution),
            "-q",
            "-sDEVICE={}".format(gs_devices[file_format]),
            "-sOutputFile={}".format(out_file),
            in_file,
        ]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if process.returncode != 0:
            raise AvlExecutionError(
                f"Ghostscript exited with status {process.returncode}",
                process.stdout.decode(errors="replace"),
            )
        if "%d" in out_file:
            return sorted(glob.glob(out_file.replace("%d", "*")))
        else:
            return [out_file]

    def save_geometry_plot(self, file_format="ps", resolution=300, output_dir=None):
        """Save the geometry plot to a file.

        :param str file_format: Either "pdf", "jpeg", "png", or "ps"
        :param int resolution: Resolution (dpi) of output file
        :param Optional[str] output_dir: Directory to save the plot in,
            defaults to the working directory
        """
        plot_name = self.name + "-geometry"
        cmds = self._hide_plot_cmds
        cmds += self._show_geometry_cmds
        cmds += "h\n\n\nquit\n"
        return self.run_avl(
            cmds=cmds,
            pre_fn=self._write_geometry,
            post_fn=lambda d: self._get_plot(
                d, plot_name, file_format, resolution, output_dir
            ),
        )

    @property
    def _hide_plot_cmds(self):
        return "plop\ng\n\n"

    @property
    def _show_geometry_cmds(self):
        cmds = "load {0}\n".format(self.model_file)
        cmds += "oper\ng\n"
        return cmds

    def show_trefftz_plot(self, case_number):
        with TemporaryDirectory(prefix="avl_") as working_dir:
            self._write_analysis_files(working_dir)
            cmds = self._load_files_cmds
            cmds += self._show_trefftz_case_cmds(case_number)
            avl = self._get_avl_process(working_dir)
            run_with_close_window(avl, cmds)

    def save_trefftz_plots(self, file_format="ps", resolution=300, output_dir=None):
        """Save the Trefftz plots to a file.

        :param str file_format: Either "pdf", "jpeg", "png" or "ps"
        :param int resolution: Resolution (dpi) of output file
        :param Optional[str] output_dir: Directory to save the plots in,
            defaults to the working directory
        """
        plot_name = self.name + "-trefftz-%d"
        cmds = self._hide_plot_cmds
        cmds += self._load_files_cmds
        if self.cases:
            for idx in range(1, len(self.cases) + 1):
                cmds += self._show_trefftz_case_cmds(idx)
                cmds += "h\n\n"
        else:
            cmds += "oper\nx\nt\nh\n\n"
        cmds += "\n\nquit\n"

        return self.run_avl(
            cmds=cmds,
            pre_fn=self._write_analysis_files,
            post_fn=lambda d: self._get_plot(
                d, plot_name, file_format, resolution, output_dir
            ),
        )

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


def run_with_close_window(avl, cmds):
    # tkinter is only needed for the interactive plots, so it's imported here
    # to keep the rest of the wrapper usable on systems without a GUI toolkit
    try:
        import tkinter as tk
    except ImportError as e:
        raise ImportError(
            "tkinter is required to show plots interactively, "
            "use the save_*_plot methods instead"
        ) from e

    quit_cmd = "\n\nquit\n"
    tk_root = tk.Tk()

    # Make sure window is on top
    tk_root.call("wm", "attributes", ".", "-topmost", "1")
    frame = tk.Frame(tk_root)
    frame.pack()

    def on_close():
        avl.stdin.write(quit_cmd.encode())
        avl.stdin.close()
        avl.wait()
        tk_root.destroy()

    tk.Button(frame, text="Close", command=on_close).pack()

    avl.stdin.write(cmds.encode())
    frame.mainloop()
