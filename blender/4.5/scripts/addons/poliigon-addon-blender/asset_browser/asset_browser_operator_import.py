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

from ..modules.poliigon_core.assets import AssetType
from ..modules.poliigon_core.multilingual import _t
from .. import reporting
from ..toolbox import get_context
from . import asset_browser as ab


# https://blender.stackexchange.com/questions/249837/how-do-i-get-the-selected-assets-in-the-asset-browser-using-the-api
class POLIIGON_OT_asset_browser_import(Operator):
    bl_idname = "poliigon.asset_browser_import"
    bl_label = _t("Import Selected Assets")
    bl_space_type = "FILE_BROWSER"

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def poll(cls, context):
        is_poliigon_lib = ab.is_poliigon_library(context)
        assets_selected = ab.get_num_selected_assets(context) > 0
        return is_poliigon_lib and assets_selected

    @classmethod
    def description(cls, context, properties):
        num_selected = ab.get_num_selected_assets(context)
        if num_selected > 0:
            return _t("Import selected assets (default parameters)")
        else:
            return _t("No asset selected.\nPlease, select an asset")

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if not ab.is_poliigon_library(context):
            # As the operator should be shown for Poliigon Library, only
            # we shouldn't be here
            error_msg = ("POLIIGON_OT_asset_browser_import(): "
                         "Poliigon library not selected!")
            reporting.capture_message(
                "asset_browser_lib_not_sel", error_msg, "error")
            return {"CANCELLED"}

        asset_files = ab.get_selected_assets(context)

        for _asset_file in asset_files:
            asset_name = ab.get_asset_name_from_browser_asset(_asset_file)
            asset_data = ab.get_asset_data_from_browser_asset(_asset_file)
            if asset_data is None:
                error_msg = ("POLIIGON_OT_asset_browser_import(): "
                             f"Asset {asset_name} not found!")
                reporting.capture_message(
                    "asset_browser_asset_not_found", error_msg, "error")
                cTB.logger_ab.error(error_msg)
                # TODO(Andreas): user notification
                continue

            asset_type = asset_data.asset_type
            if asset_type == AssetType.HDRI:
                # TODO(Andreas): Do actual import
                pass
            elif asset_type == AssetType.MODEL:
                # TODO(Andreas): Do actual import
                pass
            elif asset_type == AssetType.TEXTURE:
                # TODO(Andreas): Do actual import
                pass
            else:
                error_msg = ("POLIIGON_OT_asset_browser_import():"
                             f" Unexpected asset type: {asset_name} "
                             f"{asset_type}")
                reporting.capture_message(
                    "asset_browser_unexpected_type", error_msg, "error")
                cTB.logger_ab.error(error_msg)
                # TODO(Andreas): user notification
                continue

        return {"FINISHED"}
