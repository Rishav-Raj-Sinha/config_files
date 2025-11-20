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

import os

from bpy.types import Operator
from bpy.props import StringProperty
import bpy.utils.previews

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


# TODO(Andreas): Pull all lib dir handling into this, instead of having it
#                spread here and in two "modes" of operator_setting and operator_library!!!

class POLIIGON_OT_directory(Operator):
    bl_idname = "poliigon.poliigon_directory"
    bl_label = _t("Add Additional Directory")
    bl_description = _t("Add Additional Directory to search for assets")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    directory: StringProperty(subtype="DIR_PATH")  # noqa: F821

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
        cTB.logger.debug(f"POLIIGON_OT_directory execute: {directory}")

        if not os.path.exists(directory):
            return {"FINISHED"}

        if directory in cTB.settings["disabled_dirs"]:
            cTB.settings["disabled_dirs"].remove(directory)

        cTB.add_library_path(
            directory, primary=False, update_local_assets=True)

        cTB.refresh_ui()

        # TODO(Andreas): What is this?
        #                poliigon_setting has no invoke function...
        bpy.ops.poliigon.poliigon_setting("INVOKE_DEFAULT")

        return {"FINISHED"}

    def invoke(self, context, event):
        cTB.logger.debug(f"POLIIGON_OT_directory invoke: {self.directory}")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
