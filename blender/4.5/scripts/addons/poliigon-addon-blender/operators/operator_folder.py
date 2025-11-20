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

from bpy.types import Operator
from bpy.props import IntProperty


from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from ..utils import open_dir
from .. import reporting


class POLIIGON_OT_folder(Operator):
    bl_idname = "poliigon.poliigon_folder"
    bl_label = _t("Open Asset Folder")
    bl_description = _t("Open Asset Folder in system browser")
    bl_options = {"INTERNAL"}

    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @reporting.handle_operator()
    def execute(self, context):
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_name = asset_data.asset_name

        path_asset = asset_data.get_asset_directory()

        if path_asset is None:
            msg = _t("No asset path to open for {0}").format(asset_name)
            self.report({"ERROR"}, msg)
            reporting.capture_message(
                f"open_folder_failed: {msg}")
            return {'CANCELLED'}

        did_open = open_dir(path_asset)
        if not did_open:
            reporting.capture_message("open_folder_failed", path_asset)
            self.report(
                {"ERROR"}, _t("Open folder here: {0}").format(path_asset))
            return {'CANCELLED'}

        return {"FINISHED"}
