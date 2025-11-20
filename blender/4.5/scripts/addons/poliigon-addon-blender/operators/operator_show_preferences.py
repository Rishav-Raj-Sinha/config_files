# #### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import addon_utils
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import (
    get_context,
    get_prefs)
from .. import reporting


class POLIIGON_OT_show_preferences(Operator):
    """Open user preferences and display Poliigon settings"""
    bl_idname = "poliigon.open_preferences"
    bl_label = _t("Show Poliigon preferences")

    _options = (
        ("skip",
         _t("Skip"),
         _t("Open user preferences as-is without changing visible areas")),
        ("all",
         _t("All"),
         _t("Expand all sections of user preferences")),
        ("show_add_dir",
         _t("Additional library"),
         _t("Show additional library directory preferences")),
        ("show_display_prefs",
         _t("Display"),
         _t("Show display preferences")),
        ("show_default_prefs",
         _t("Asset prefs"),
         _t("Show asset preferences"))
    )

    set_focus: EnumProperty(items=_options, options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @reporting.handle_operator()
    def execute(self, context):
        prefs = get_prefs()
        if self.set_focus == "all":
            cTB.settings["show_add_dir"] = True
            cTB.settings["show_display_prefs"] = True
            cTB.settings["show_default_prefs"] = True
            cTB.settings["show_updater_prefs"] = True
            if prefs:
                prefs.show_updater_prefs = True
        elif self.set_focus != "skip":
            show_add_dir = self.set_focus == "show_add_dir"
            cTB.settings["show_add_dir"] = show_add_dir
            show_display_prefs = self.set_focus == "show_display_prefs"
            cTB.settings["show_display_prefs"] = show_display_prefs
            show_default_prefs = self.set_focus == "show_default_prefs"
            cTB.settings["show_default_prefs"] = show_default_prefs
            if prefs:
                prefs.show_updater_prefs = False

        bpy.ops.screen.userpref_show('INVOKE_AREA')
        bpy.data.window_managers["WinMan"].addon_search = "Poliigon"
        prefs = context.preferences
        try:
            prefs.active_section = "ADDONS"
        except TypeError as err:
            reporting.capture_message(
                "assign_preferences_tab", str(err), "error")

        # __spec__.parent since __package__ got deprecated
        # Since this module moved into operators,
        # we need to split off .operators
        spec_parent = __spec__.parent
        spec_parent = spec_parent.split(".")[0]

        addons_ids = [
            mod for mod in addon_utils.modules(refresh=False)
            if mod.__name__ == spec_parent]
        if not addons_ids:
            msg = "Failed to directly load and open Poliigon preferences"
            reporting.capture_message(
                "preferences_open_no_id", msg, "error")
            return {'CANCELLED'}

        addon_blinfo = addon_utils.module_bl_info(addons_ids[0])
        if not addon_blinfo["show_expanded"]:
            has_prefs = hasattr(bpy.ops, "preferences")
            has_prefs = has_prefs and hasattr(bpy.ops.preferences,
                                              "addon_expand")

            if has_prefs:  # later 2.8 buids
                bpy.ops.preferences.addon_expand(module=spec_parent)
            else:
                self.report(
                    {"INFO"},
                    _t("Search for and expand the Poliigon addon in preferences")
                )

        cTB.signal_view_screen("settings")
        return {'FINISHED'}
