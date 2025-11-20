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


def _draw_unlimited_icon(cTB, *, row: bpy.types.UILayout) -> None:
    icon_value = cTB.ui_icons["LOGO_unlimited"].icon_id
    op_icon = row.operator(
        "poliigon.poliigon_setting", text="", emboss=True, icon_value=icon_value)
    op_icon.mode = "show_user"
    # TODO(Andreas): Tooltip???
    op_icon.tooltip = _t("Switch to your account details")


def _draw_asset_balance(cTB, *, row: bpy.types.UILayout) -> None:
    if cTB.is_unlimited_user():
        _draw_unlimited_icon(cTB, row=row)
        return

    # Asset balance
    credits = cTB.get_user_credits()
    balance_icon = cTB.ui_icons["ICON_asset_balance"].icon_id
    if cTB.is_paused_subscription() and credits <= 0:
        balance_icon = cTB.ui_icons["ICON_subscription_paused"].icon_id

    op_credits = row.operator(
        "poliigon.poliigon_setting",
        text=str(credits),
        icon_value=balance_icon  # TODO: use new asset icon
    )
    op_credits.tooltip = _t(
        "Your asset balance shows how many assets you can\n"
        "purchase. Free assets and downloading assets you\n"
        "already own doesn’t affect your balance")
    op_credits.mode = "show_user"


def _add_asset_tab(cTB,
                   row: bpy.types.UILayout,
                   *,
                   tab: str,
                   mode: str,
                   icon: str = "NONE",
                   icon_value: int = 0,
                   tooltip: str = ""
                   ) -> None:
    no_user = not cTB.settings["show_user"]
    no_settings = not cTB.settings["show_settings"]
    no_user_or_settings = no_user and no_settings

    col = row.column(align=True)
    is_tab_active = cTB.settings["area"] == tab
    op = col.operator(
        "poliigon.poliigon_setting",
        text="",
        icon=icon,
        icon_value=icon_value,
        depress=is_tab_active and no_user_or_settings,
    )
    op.mode = mode
    op.tooltip = tooltip


# @timer
def build_areas(cTB):
    cTB.logger_ui.debug("build_areas")
    cTB.initial_view_screen()

    row = cTB.vBase.row()
    label_column = row.column(align=True)
    label_column.alignment = "LEFT"

    icon = 0
    label_txt = _t("Browse Assets")
    if cTB.is_unlimited_user():
        icon = cTB.ui_icons["LOGO_unlimited"].icon_id
        label_txt = _t("Pro Unlimited")
    elif not cTB.is_free_user():
        icon = cTB.ui_icons["ICON_asset_balance"].icon_id
        if cTB.is_paused_subscription() and cTB.get_user_credits() <= 0:
            icon = cTB.ui_icons["ICON_subscription_paused"].icon_id
        label_txt = _t("Downloads")
        label_txt = f"{cTB.get_user_credits()} {label_txt}"

    if not cTB.settings["show_user"]:
        label_column.label(text=label_txt, icon_value=icon)
    else:
        back_button = label_column.operator(
            "poliigon.poliigon_setting",
            text=_t("Back"),
            icon="BACK"
        )
        back_button.mode = "show_user"

    row_right = row.row(align=True)
    row_right.alignment = "RIGHT"

    op = row_right.operator(
        "poliigon.poliigon_setting",
        text="",
        icon="COMMUNITY",
        depress=cTB.settings["show_user"],
    )
    op.mode = "show_user"
    op.tooltip = _t("Show Your Account Details")

    op = row_right.operator(
        "poliigon.poliigon_link",
        text="",
        icon="HELP"
    )
    op.confirm_popup = True
    op.mode = "help"
    op.tooltip = _t("Addon help")

    _ = row_right.operator(
        "poliigon.open_preferences",
        text="",
        icon="PREFERENCES",
    )

    # TODO(Joao): Check if this operator should be moved somewhere else
    # _draw_asset_balance(cTB, row=row_prefs)

    cTB.vBase.separator()
