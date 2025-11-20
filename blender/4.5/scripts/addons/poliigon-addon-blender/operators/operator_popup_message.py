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

from ..dialogs.utils_dlg import (
    get_ui_scale,
    wrapped_label)
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_popup_message(Operator):
    bl_idname = "poliigon.popup_message"
    bl_label = ""
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    message_body: StringProperty(options={"HIDDEN"})  # noqa: F821
    message_url: StringProperty(options={"HIDDEN"})  # noqa: F821
    notice_id: StringProperty(options={"HIDDEN"})  # noqa: F821

    target_width = 400

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def invoke(self, context, event):
        width = self.target_width  # Blender handles scaling to ui.

        notice = cTB.notify.get_top_notice(do_signal_view=False)
        if notice is not None:
            cTB.notify.clicked_notice(notice)

        return context.window_manager.invoke_props_dialog(self, width=width)

    @reporting.handle_draw()
    def draw(self, context):
        layout = self.layout
        target_wrap = self.target_width * get_ui_scale(cTB)
        target_wrap -= 25 * get_ui_scale(cTB)
        wrapped_label(cTB, target_wrap, self.message_body, layout)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if self.message_url:
            if self.message_url in cTB._api._url_paths:
                cTB._api.open_poliigon_link(self.message_url,
                                            env_name=cTB._env.env_name)
            else:
                bpy.ops.wm.url_open(url=self.message_url)

        notice = cTB.notify.get_top_notice(do_signal_view=False)
        if notice is not None:
            cTB.notify.dismiss_notice(notice)

        cTB.refresh_ui()
        return {'FINISHED'}
