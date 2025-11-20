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
from .utils_dlg import (
    get_ui_scale,
    wrapped_label)
from ..toolbox import c_Toolbox


# TODO(Andreas): Currently not sure about this error
ERR_LOGIN_TIMEOUT = _t("Login with website timed out, please try again")

# Base threshold for responsive layout adjustment (unscaled)
RESPONSIVE_WIDTH_BASE = 250


def _draw_welcome_or_error(cTB: c_Toolbox, layout: bpy.types.UILayout) -> None:
    if cTB.user_invalidated() and not cTB.login_in_progress:
        layout.separator()

        if cTB.last_login_error == ERR_LOGIN_TIMEOUT:
            wrapped_label(
                cTB,
                cTB.width_draw_ui,
                cTB.last_login_error,
                layout,
                icon="ERROR"
            )
        else:
            wrapped_label(
                cTB,
                cTB.width_draw_ui,
                _t("Warning : You have been logged out as this account was "
                   "signed in on another device."),
                layout,
                icon="ERROR"
            )

    else:
        wrapped_label(
            cTB,
            cTB.width_draw_ui,
            _t("Welcome to the Poliigon Addon!"),
            layout
        )

    layout.separator()


def _draw_share_addon_errors(cTB: c_Toolbox,
                             layout: bpy.types.UILayout,
                             enabled: bool = True) -> None:
    row_opt = layout.row()
    row_opt.alignment = "CENTER"
    row_opt.enabled = enabled
    # __spec__.parent since __package__ got deprecated
    # Since this module moved into dialogs,
    # we need to split off .dialogs
    spec_parent = __spec__.parent
    spec_parent = spec_parent.split(".")[0]
    prefs = bpy.context.preferences.addons.get(spec_parent, None)
    if prefs and prefs.preferences:
        row_opt.prop(prefs.preferences, "reporting_opt_in", text="")
        twidth = int(cTB.width_draw_ui - 42 * get_ui_scale(cTB))
        wrapped_label(
            cTB,
            twidth,
            _t("Share addon errors / usage"),
            row_opt
        )


def _draw_login(cTB, layout: bpy.types.UILayout) -> None:
    """Draw the simplified login UI with only web login option."""
    # Calculate the responsive width threshold with proper scaling
    responsive_width_threshold = RESPONSIVE_WIDTH_BASE * get_ui_scale(cTB)

    row_welcome = layout.row()
    row_welcome.alignment = 'CENTER'
    wrapped_label(
        cTB,
        int(cTB.width_draw_ui * 0.9),
        _t("Welcome to the Poliigon Addon!"),
        row_welcome
    )

    row_subtitle = layout.row()
    row_subtitle.alignment = 'CENTER'
    row_subtitle.enabled = False  # Darker shading for subtitle
    wrapped_label(
        cTB,
        int(cTB.width_draw_ui * 0.9),
        _t("Login or Sign Up below in your browser to get started"),
        row_subtitle,
        alignment='CENTER'
    )

    layout.separator()

    # Content with padding for buttons and other elements
    col = layout.column(align=True)
    col.separator(factor=0.5)

    if cTB.login_in_progress:
        # Create a row for the main button
        main_row = col.row(align=True)
        main_row.scale_y = 1.25

        # Left side: "Opening browser..." button (90% of width)
        openingcol = main_row.column(align=True)
        openingcol.enabled = False
        main_button = openingcol.operator(
            "poliigon.poliigon_user",
            text=_t("Opening browser..."),
            depress=True
        )
        main_button.mode = "none"
        main_button.tooltip = _t("Complete authentication via opened webpage")

        # Right side: X button (10% of width)
        cancelcol = main_row.column(align=True)
        cancel_button = cancelcol.operator(
            "poliigon.poliigon_user",
            text="",
            icon="X"
        )
        cancel_button.mode = "login_cancel"
        cancel_button.tooltip = _t("Cancel Authentication")

        # Disable only the main button, not the whole row
        main_row.enabled = True

        # Add space where the second button would be
        col.separator()
    else:
        # Login button
        row_login = col.row()
        row_login.scale_y = 1.25
        op_login = row_login.operator(
            "poliigon.poliigon_user",
            text=_t("Login"),
            depress=True
        )
        op_login.mode = "login_with_website"
        op_login.tooltip = _t("Login via Browser")

    col.separator()

    # Pass enabled=False to _draw_share_addon_errors when login is in progress
    _draw_share_addon_errors(cTB, col, enabled=not cTB.login_in_progress)

    # Help and legal links - responsive layout
    col.separator()

    # Get current region width and log it for reference
    region_width = bpy.context.region.width if hasattr(bpy.context, "region") else 0
    cTB.logger_ui.debug(f"Current region width: {region_width}")

    # Determine layout based on width threshold
    if region_width > 0 and region_width < responsive_width_threshold:
        # Narrow layout - display links in three separate rows in new order
        # 1. Help
        row_help = col.row()
        row_help.alignment = 'CENTER'
        row_help.enabled = not cTB.login_in_progress
        op_help = row_help.operator(
            "poliigon.poliigon_link",
            text=_t("Need Help?"),
            emboss=False
        )
        op_help.mode = "help"
        op_help.tooltip = _t("Get help with the Poliigon addon")

        # 2. Privacy Policy
        row_privacy = col.row()
        row_privacy.alignment = 'CENTER'
        row_privacy.enabled = not cTB.login_in_progress
        op_privacy = row_privacy.operator(
            "poliigon.poliigon_link",
            text=_t("Privacy Policy"),
            emboss=False
        )
        op_privacy.mode = "privacy"
        op_privacy.tooltip = _t("View the Privacy Policy")

        # 3. Terms & Conditions
        row_terms = col.row()
        row_terms.alignment = 'CENTER'
        row_terms.enabled = not cTB.login_in_progress
        op_terms = row_terms.operator(
            "poliigon.poliigon_link",
            text=_t("Terms & Conditions"),
            emboss=False
        )
        op_terms.mode = "terms"
        op_terms.tooltip = _t("View the terms and conditions page")
    else:
        # Wide layout - two rows but with reordered links
        # First row: Help and Privacy Policy
        row_first = col.row(align=True)
        row_first.enabled = not cTB.login_in_progress

        op_help = row_first.operator(
            "poliigon.poliigon_link",
            text=_t("Need Help?"),
            emboss=False
        )
        op_help.mode = "help"
        op_help.tooltip = _t("Get help with the Poliigon addon")

        op_privacy = row_first.operator(
            "poliigon.poliigon_link",
            text=_t("Privacy Policy"),
            emboss=False
        )
        op_privacy.mode = "privacy"
        op_privacy.tooltip = _t("View the Privacy Policy")

        # Second row: Terms & Conditions
        row_second = col.row()
        row_second.alignment = 'CENTER'
        row_second.enabled = not cTB.login_in_progress
        op_terms = row_second.operator(
            "poliigon.poliigon_link",
            text=_t("Terms & Conditions"),
            emboss=False
        )
        op_terms.mode = "terms"
        op_terms.tooltip = _t("View the terms and conditions page")


def build_login(cTB):
    cTB.logger_ui.debug("build_login")
    _draw_login(cTB, cTB.vBase)
