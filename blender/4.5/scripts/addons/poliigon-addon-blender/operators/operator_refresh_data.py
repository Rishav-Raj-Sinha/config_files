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

from bpy.props import StringProperty
from bpy.types import Operator

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_refresh_data(Operator):
    bl_idname = "poliigon.refresh_data"
    bl_label = _t("Refresh data")
    bl_description = _t("Refresh thumbnails and reload data")
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(
        options={"HIDDEN"},  # noqa: F821
        default=_t("Refresh thumbnails and reload data"))  # noqa: F722

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        cTB.refresh_data()
        return {'FINISHED'}
