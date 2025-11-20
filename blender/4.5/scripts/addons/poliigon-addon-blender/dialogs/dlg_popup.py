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

from typing import List, Optional

import bpy

from ..modules.poliigon_core.multilingual import _t
from .utils_dlg import (
    get_ui_scale,
    wrapped_label)


def open_popup(cTB,
               title: str = "",
               msg: str = "",
               buttons: List[str] = [_t("OK")],
               commands: List[Optional[str]] = [None],
               mode: str = None,
               w_limit: int = 0
               ) -> None:
    cTB.logger_ui.debug(f"open_popup mode={mode}, w_limit={w_limit}"
                        f"    title={title}, msg={msg},\n"
                        f"    buttons={buttons},\n"
                        f"    commands={commands}")

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)

        icon = "INFO"
        if mode == "question":
            icon = "QUESTION"
        elif mode == "error":
            icon = "ERROR"

        col.label(text=title, icon=icon)

        col.separator()

        if w_limit == 0:
            col.label(text=msg)
        else:
            wrapped_label(cTB, w_limit * get_ui_scale(cTB), msg, col)

        col.separator()
        col.separator()

        vRow = col.row()
        for idx_button in range(len(buttons)):
            if commands[idx_button] in [None, "cancel"]:
                op = vRow.operator(
                    "poliigon.poliigon_setting",
                    text=buttons[idx_button])
                op.mode = "none"
            elif commands[idx_button] == "credits":
                op = vRow.operator(
                    "poliigon.poliigon_link",
                    text=_t("Add Credits"),
                    depress=1)
                op.mode = "credits"
            elif commands[idx_button] == "open_p4b_url":
                op = vRow.operator(
                    "poliigon.poliigon_link",
                    text=buttons[idx_button],
                    depress=1)
                op.mode = "p4b"
            elif commands[idx_button] == "check_update":
                vRow.operator("poliigon.check_update",
                              text=buttons[idx_button])

    bpy.context.window_manager.popover(draw)
