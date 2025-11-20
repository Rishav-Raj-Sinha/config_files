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


class POLIIGON_OT_close_notification(Operator):
    bl_idname = "poliigon.close_notification"
    bl_label = ""
    bl_description = _t("Close notification")
    bl_options = {"INTERNAL"}

    notification_index: IntProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return _t("Close notification")  # Avoids having an extra blank line.

    @reporting.handle_operator()
    def execute(self, context):
        notice = cTB.notify.get_top_notice(do_signal_view=False)
        if notice is None:
            self.report(
                {'ERROR'},
                _t("Could not dismiss notification, out of bounds.")
            )
            return {'CANCELLED'}

        cTB.notify.dismiss_notice(notice)
        return {'FINISHED'}
