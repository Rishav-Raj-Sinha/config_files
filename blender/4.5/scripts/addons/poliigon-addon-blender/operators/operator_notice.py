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
from bpy.props import StringProperty

from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_notice_operator(Operator):
    bl_idname = "poliigon.notice_operator"
    bl_label = ""
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    notice_id: StringProperty(options={"HIDDEN"})  # noqa: F821
    ops_name: StringProperty(options={"HIDDEN"})  # noqa: F821

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
        # Execute the operator via breaking into parts e.g. "wm.quit_blender"
        atr = self.ops_name.split(".")
        if len(atr) != 2:
            reporting.capture_message("bad_notice_operator", self.ops_name)
            return {'CANCELLED'}

        # Safeguard to avoid injection.
        if self.ops_name not in ("wm.quit_blender"):
            cTB.logger.error("POLIIGON_OT_notice_operator Unsupported "
                             f"operation: {self.ops_name}")
            return {'CANCELLED'}

        notice = cTB.notify.get_top_notice(do_signal_view=False)
        if notice is not None:
            cTB.notify.clicked_notice(notice)

        cTB.logger.debug(
            f"POLIIGON_OT_notice_operator Running {self.ops_name}")

        # Using invoke acts like in the interface, so any "save?" dialogue
        # will pick up, for instance if a "quit" operator.
        getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
        if notice is not None:
            cTB.notify.dismiss_notice(notice)
        return {'FINISHED'}
