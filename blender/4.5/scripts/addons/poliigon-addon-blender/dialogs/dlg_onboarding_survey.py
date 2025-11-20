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

from ..modules.poliigon_core.multilingual import _t
from ..modules.poliigon_core.user import PoliigonUserProfiles
from .utils_dlg import (
    get_ui_scale,
    wrapped_label)
from ..toolbox import c_Toolbox


def _draw_welcome_message(cTB: c_Toolbox, layout: bpy.types.UILayout) -> None:
    """Draw the welcome message and setup prompt."""
    row = layout.row()
    row.enabled = False
    row.alignment = "CENTER"
    wrapped_label(
        cTB,
        int(cTB.width_draw_ui * 0.9),
        _t("Success! You are now logged in."),
        row,
        alignment='CENTER'
    )

    layout.separator()

    wrapped_label(
        cTB,
        int(cTB.width_draw_ui * 0.9),
        _t("Please complete your account setup below to continue"),
        layout,
        alignment='CENTER'
    )

    layout.separator()


def _draw_user_type_selection(cTB: c_Toolbox, layout: bpy.types.UILayout) -> None:
    """Draw the user type selection radio buttons."""
    twidth = cTB.width_draw_ui - 42 * get_ui_scale(cTB)
    wrapped_label(
        cTB,
        int(twidth),
        _t("Which best describes you?"),
        layout,
        alignment="CENTER"
    )
    layout.separator()

    if not cTB.signal_for_profile_survey_emitted:
        cTB.signal_for_profile_survey_emitted = True
        cTB.signal_view_screen("update_user")

    for user_type in PoliigonUserProfiles.get_list():
        row = layout.row()
        row.scale_y = 1.2
        display_type = PoliigonUserProfiles.from_string(user_type).to_ui_display()

        op = row.operator(
            "poliigon.poliigon_onboarding_survey",
            text=_t(display_type))
        op.user_type = user_type

    layout.separator()


def _draw_email_preference(cTB: c_Toolbox, layout: bpy.types.UILayout) -> None:
    """Draw the email preference checkbox."""
    vProps = bpy.context.window_manager.poliigon_props

    row_opt = layout.row()
    row_opt.alignment = "LEFT"

    row_opt.prop(vProps, "onboarding_email_preference", text="")

    twidth = cTB.width_draw_ui - 28 * get_ui_scale(cTB)
    wrapped_label(
        cTB,
        int(twidth),
        _t("Send me emails about new assets and other product updates"),
        row_opt
    )


def _draw_onboarding_survey(cTB: c_Toolbox, layout: bpy.types.UILayout) -> None:
    """Draw the main onboarding survey form."""
    spc = 1.0 / cTB.width_draw_ui

    _draw_welcome_message(cTB, layout)

    # User type selection in darker box
    box = layout.box()
    row = box.row()
    row.separator(factor=spc)
    col = row.column()
    row.separator(factor=spc)

    _draw_user_type_selection(cTB, col)

    # Email preference outside the box
    layout.separator()
    layout.separator()
    _draw_email_preference(cTB, layout)


def build_onboarding_survey(cTB: c_Toolbox):
    """Main function to build the onboarding survey dialog."""
    vProps = bpy.context.window_manager.poliigon_props
    # Initialize properties if they don't exist
    vProps.onboarding_user_type = ""
    _draw_onboarding_survey(cTB, cTB.vBase)
