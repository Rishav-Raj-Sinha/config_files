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

from ..modules.poliigon_core.multilingual import _t
from .utils_dlg import (
    get_ui_scale,
    wrapped_label)


# @timer
def build_library(cTB):
    cTB.logger_ui.debug("build_library")
    factor_space = 1.0 / cTB.width_draw_ui

    wrapped_label(
        cTB,
        cTB.width_draw_ui,
        _t("Welcome to the Poliigon Addon!"),
        cTB.vBase
    )

    cTB.vBase.separator()

    disabled_row = cTB.vBase.row()
    disabled_row.enabled = False
    wrapped_label(
        cTB,
        cTB.width_draw_ui,
        _t("Select where you will store Poliigon assets."),
        disabled_row
    )

    cTB.vBase.separator()

    box_row = cTB.vBase.box().row()
    box_row.separator(factor=factor_space)
    col = box_row.column()
    box_row.separator(factor=factor_space)

    col.label(text=_t("Library Location"))

    label_library = cTB.settings["set_library"]
    if label_library == "":
        label_library = _t("Select Location")

    op = col.operator(
        "poliigon.poliigon_library",
        icon="FILE_FOLDER",
        text=label_library,
    )
    op.mode = "set_library"
    op.directory = cTB.settings["set_library"]
    op.tooltip = _t("Select Location")

    col.separator()
    row_confirm = col.row()
    row_confirm.scale_y = 1.5

    op = row_confirm.operator(
        "poliigon.poliigon_setting", text=_t("Confirm"))
    op.mode = "set_library"
    op.tooltip = _t("Confirm Library location")

    col.separator()

    wrapped_label(
        cTB,
        cTB.width_draw_ui - 30 * get_ui_scale(cTB),
        _t("You can change this and add more directories in the settings "
           "at any time."),
        col
    )

    col.separator()
    cTB.vBase.separator()
