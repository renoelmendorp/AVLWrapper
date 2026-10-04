"""AVL settings of the OPER options menu"""

import re
from dataclasses import dataclass, fields
from typing import Optional

from avlwrapper.errors import AvlExecutionError, InputError


@dataclass
class Options:
    """
    Settings which change what AVL's results mean. Every setting defaults to
    None, which keeps the AVL default.

    :param Optional[bool] standard_axes: forces and moments in the standard
        axes (X forward, Z down), or in the geometric axes (X aft, Z up)
    :param Optional[bool] stability_axis_rates: the rates of the cases
        (pb/2V, qc/2V, rb/2V) are about the stability axes (X along the
        free-stream velocity), or about the body axes (X along the geometric
        X axis)
    :param Optional[bool] profile_drag: include the profile drag of CDCL
        polars in the forces. AVL switches this on when the geometry
        contains a CDCL polar
    :param Optional[bool] trailing_leg_forces: include the forces on the
        trailing legs of the horseshoe vortices
    :param Optional[bool] body_induced_velocity: include the velocity induced
        by bodies in the near-field forces (not available in AVL 3.40)
    """

    standard_axes: Optional[bool] = None
    stability_axis_rates: Optional[bool] = None
    profile_drag: Optional[bool] = None
    trailing_leg_forces: Optional[bool] = None
    body_induced_velocity: Optional[bool] = None

    # option: (command which toggles it, pattern in the options menu, value
    # of the pattern's group which means True)
    _MENU = {
        "standard_axes": ("A", r"A xis orient\.\s*:\s*(\w+)", "Standard"),
        "stability_axis_rates": (
            "R",
            r"R ate,mom axes\s*:\s*Rates,moments about (\w+)",
            "Stability",
        ),
        "profile_drag": ("V", r"V iscous forces\s*:\s*([TF])", "T"),
        "trailing_leg_forces": ("T", r"T rail\.leg forces\s*:\s*([TF])", "T"),
        "body_induced_velocity": ("N", r"N ear-field forces\s*:\s*([TF])", "T"),
    }

    @property
    def requested(self):
        """The options which are set, as a dictionary"""
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if getattr(self, f.name) is not None
        }

    @classmethod
    def read_menu(cls, avl_output):
        """
        The settings as printed by AVL's options menu, the last menu in the
        output counts. Settings which this AVL version doesn't have are None.

        :param str avl_output: output of AVL
        """
        settings = {}
        for name, (_, pattern, true_value) in cls._MENU.items():
            matches = re.findall(pattern, avl_output)
            settings[name] = matches[-1] == true_value if matches else None
        return settings

    def commands(self, current):
        """
        AVL commands which change the current settings to the requested ones.
        The commands start and end in AVL's main menu.

        :param dict current: current settings, see read_menu
        """
        toggles = []
        for name, value in self.requested.items():
            if current[name] is None:
                raise InputError(
                    f"Option '{name}' is not supported by this version of AVL"
                )
            if current[name] != value:
                toggles.append(self._MENU[name][0])
        if not toggles:
            return ""
        # options menu is part of the OPER menu
        return "oper\no\n" + "".join(f"{t}\n" for t in toggles) + "\n\n"

    def check(self, avl_output):
        """
        Checks whether AVL's options menu shows the requested settings

        :param str avl_output: output of AVL
        """
        current = self.read_menu(avl_output)
        wrong = {
            name: value
            for name, value in self.requested.items()
            if current[name] != value
        }
        if wrong:
            raise AvlExecutionError(
                f"AVL did not apply the options {wrong}", avl_output
            )
