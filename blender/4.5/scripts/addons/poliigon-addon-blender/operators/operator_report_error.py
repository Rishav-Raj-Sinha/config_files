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
import bpy.utils.previews


from ..modules.poliigon_core.multilingual import _t
from ..dialogs.utils_dlg import (
    get_ui_scale,
    wrapped_label)
from ..toolbox import get_context
from .. import reporting


USER_COMMENT_LENGTH = 512  # Max length for user submitted error messages.


class POLIIGON_OT_report_error(Operator):
    bl_idname = "poliigon.report_error"
    bl_label = _t("Report error")
    bl_description = _t("Report an error to the developers")
    bl_options = {"INTERNAL"}

    error_report: StringProperty(options={"HIDDEN"})  # noqa: F821
    user_message: StringProperty(
        default="",  # noqa: F722
        maxlen=USER_COMMENT_LENGTH,
        options={'SKIP_SAVE'})  # noqa: F821

    target_width = 600

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    def invoke(self, context, event):
        width = self.target_width  # Blender handles scaling to ui.
        return context.window_manager.invoke_props_dialog(self, width=width)

    @reporting.handle_draw()
    def draw(self, context):
        layout = self.layout

        # Display the error message (no word wrapping in case too long)
        box = layout.box()
        box.scale_y = 0.5
        box_wrap = self.target_width * get_ui_scale(cTB)
        box_wrap -= 20 * get_ui_scale(cTB)
        lines = self.error_report.split("\n")
        if len(lines) > 10:  # Prefer the last few lines.
            lines = lines[-10:]
        for ln in lines:
            if not ln:
                continue
            box.label(text=ln)

        # Display instructions to submit a comment.
        label_txt = _t("(Optional) What were you doing when this error occurred?")
        target_wrap = self.target_width * get_ui_scale(cTB)
        target_wrap -= 10 * get_ui_scale(cTB)
        wrapped_label(cTB, target_wrap, label_txt, layout)
        layout.prop(self, "user_message", text="")

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if bpy.app.background:  # No user to give feedback anyways.
            return {'CANCELLED'}
        reporting.user_report(self.error_report, self.user_message)
        self.report({"INFO"}, _t("Thanks for sharing this report"))
        return {'FINISHED'}
