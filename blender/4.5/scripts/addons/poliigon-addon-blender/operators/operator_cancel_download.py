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
from .. import reporting


class POLIIGON_OT_cancel_download(Operator):
    bl_idname = "poliigon.cancel_download"
    bl_label = _t("Cancel download")
    bl_description = _t("Cancel downloading this asset")
    bl_options = {"INTERNAL"}

    asset_id: IntProperty(default=0, options={'SKIP_SAVE'})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if self.asset_id <= 0:
            return {'CANCELLED'}

        asset_data = cTB._asset_index.get_asset(self.asset_id)
        if asset_data is None:
            return {'CANCELLED'}
        asset_data.state.dl.cancel()

        cTB.logger.debug(f"Cancelled download {self.asset_id}")
        self.report({'WARNING'}, _t("Cancelling download"))
        return {'FINISHED'}
