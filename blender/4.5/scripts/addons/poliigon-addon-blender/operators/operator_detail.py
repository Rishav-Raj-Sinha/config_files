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
from bpy.props import StringProperty

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


# TODO(Andreas): currently not used at all?
class POLIIGON_OT_detail(Operator):
    bl_idname = "poliigon.poliigon_detail"
    bl_label = ""
    bl_description = _t("Reset Property to Default")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    data: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    @reporting.handle_operator()
    def execute(self, context):
        if context.object.cycles.dicing_rate != context.scene.vDispDetail:
            context.object.cycles.dicing_rate = context.scene.vDispDetail
            context.object.modifiers["Subdivision"].subdivision_type = "SIMPLE"

        return {"FINISHED"}
