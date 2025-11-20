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
import bpy

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting
from . import asset_browser as ab


class POLIIGON_OT_asset_browser_reprocess(Operator):
    bl_idname = "poliigon.asset_browser_reprocess"
    bl_label = _t("Show additional import options")
    bl_space_type = "FILE_BROWSER"

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def poll(cls, context):
        if not ab.is_asset_browser(context):
            return False
        if not ab.is_poliigon_library(context):
            return False
        if not ab.is_only_poliigon_selected(context):
            return False
        if ab.get_num_selected_assets(context) == 0:
            return False
        return True

    @classmethod
    def description(cls, context, properties):
        num_selected = ab.get_num_selected_assets(context)
        if num_selected == 0:
            return _t("No asset selected.\nPlease, select a single asset")
        else:
            return _t("Re-process selected assets")

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if not ab.is_poliigon_library(context):
            # As the operator should be shown for Poliigon Library
            # we shouldn't be here
            error_msg = ("POLIIGON_OT_asset_browser_reprocess(): "
                         "Poliigon library not selected!")
            reporting.capture_message(
                "asset_browser_reproc_not_sel", error_msg, "error")
            return {"CANCELLED"}

        asset_files = ab.get_selected_assets(context)

        for asset_file in asset_files:
            asset_name = ab.get_asset_name_from_browser_asset(asset_file)
            asset_data = ab.get_asset_data_from_browser_asset(asset_file)

            if asset_data is None:
                error_msg = ("POLIIGON_OT_asset_browser_reprocess(): "
                             f"Asset {asset_name} not found!")
                reporting.capture_message(
                    "asset_browser_reproc_asset_missing", error_msg, "error")
                self.report({"ERROR"}, f"Asset {asset_name} not found!")
                continue

            bpy.ops.poliigon.update_asset_browser(
                asset_id=asset_data.asset_id, force=True)

        return {"FINISHED"}
