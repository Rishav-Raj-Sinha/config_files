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
from bpy.props import BoolProperty, StringProperty

from ..modules.poliigon_core.multilingual import _t
from ..dialogs.utils_dlg import (
    get_ui_scale,
    wrapped_label)
from ..constants import (
    POPUP_WIDTH_LABEL_WIDE,
    POPUP_WIDTH_WIDE)
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_popup_download_limit(Operator):
    bl_idname = "poliigon.popup_download_limit"
    bl_label = _t("Unlimited Fair Use Exceeded")
    bl_options = {"INTERNAL"}

    msg: StringProperty(options={"HIDDEN"}, default="")  # noqa: F821, F722
    force: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    def invoke(self, context, event):
        if not cTB.is_unlimited_user():
            # We shouldn't even be here. Just a safety to never show this
            # to non-unlimited users.
            return {'FINISHED'}

        cTB.signal_popup(popup="DOWNLOAD_RATE_LIMITED")
        return context.window_manager.invoke_props_dialog(
            self, width=POPUP_WIDTH_WIDE)

    @reporting.handle_draw()
    def draw(self, context):
        label_width = POPUP_WIDTH_LABEL_WIDE * get_ui_scale(cTB)

        col_content = self.layout.column()
        wrapped_label(
            cTB,
            width=label_width,
            text=self.msg,
            container=col_content,
            add_padding_bottom=True)

        op = col_content.operator(
            "poliigon.poliigon_link", text=_t("Learn More"))
        op.mode = "unlimited_plan_help"
        op.tooltip = _t("See more info about Unlimited Fair Use policy on our "
                        "website.")

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        cTB.refresh_ui()
        return {'FINISHED'}
