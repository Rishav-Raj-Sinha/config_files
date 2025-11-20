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

import bpy
from bpy.types import Operator
from bpy.props import (
    EnumProperty,
    StringProperty)
import bpy.utils.previews

from ..modules.poliigon_core.multilingual import _t
from ..asset_browser.asset_browser import create_poliigon_library
from ..toolbox import get_context
from ..toolbox_settings import save_settings
from .. import reporting


class POLIIGON_OT_library(Operator):
    bl_idname = "poliigon.poliigon_library"
    bl_label = _t("Poliigon Library")
    bl_description = _t("(Set Poliigon Library Location)")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    _enum_items = [
        ("set_library", "set_library", _t("Set path on first load")),
        ("update_library", "update_library", _t("Update path from preferences"))
    ]

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    directory: StringProperty(subtype="DIR_PATH")  # noqa: F821
    mode: EnumProperty(items=_enum_items, options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @reporting.handle_operator()
    def execute(self, context):
        global cTB

        directory = self.directory.replace("\\", "/")

        if self.mode == "set_library":
            # Stage for confirmation on startup (or after deleted)
            cTB.settings["set_library"] = directory
        else:
            # Update_library, from user preferences

            if bpy.app.version >= (3, 0) and cTB.user_legacy_own_assets():
                create_poliigon_library(force=True)

            path_old = cTB.get_library_path(primary=True)
            cTB.replace_library_path(
                path_old=path_old,
                path_new=directory,
                primary=True,
                update_local_assets=True)

            cTB.refresh_ui()

        save_settings(cTB)

        # if os.path.exists(vDir):
        #    bpy.ops.poliigon.poliigon_setting("INVOKE_DEFAULT")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
