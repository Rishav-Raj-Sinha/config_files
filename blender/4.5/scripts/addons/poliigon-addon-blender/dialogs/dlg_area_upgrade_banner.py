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
from ..modules.poliigon_core.upgrade_content import UpgradeContent
from ..dialogs.utils_dlg import (
    get_ui_scale,
    wrapped_label)


def _draw_banner(cTB, upgrade_content: UpgradeContent) -> None:
    """Draws the actual banner and its buttons."""

    width = cTB.width_draw_ui - 42 * get_ui_scale(cTB)

    row = cTB.vBase.row(align=True)
    row.scale_x = 1.1
    row.scale_y = 1.1

    box = row.box()
    col = box.column()

    text = upgrade_content.banner_primary_text
    label = upgrade_content.banner_button_text
    key_icon = upgrade_content.icon_path

    wrapped_label(
        cTB, width=width, text=text, container=col)

    row_buttons = col.row(align=True)
    if upgrade_content.open_popup:
        op = row_buttons.operator(
            "poliigon.popup_change_plan",
            text=label,
            icon_value=cTB.ui_icons[key_icon].icon_id)
        op.tooltip = _t("By clicking here, we will change the subscription "
                        "plan as shown above")
        if upgrade_content.allow_dismiss:
            op = row_buttons.operator(
                "poliigon.popup_change_plan_dismiss",
                text="",
                icon="PANEL_CLOSE")
    else:
        op = row_buttons.operator(
            "poliigon.poliigon_link",
            text=label,
            icon_value=cTB.ui_icons[key_icon].icon_id)
        op.mode = "subscribe_banner"
        op.tooltip = "Opens the website to view available plans"


def _draw_banner_in_progress(cTB, upgrade_content: UpgradeContent) -> None:
    """Draws an 'upgrade in progress' banner."""

    width = cTB.width_draw_ui - 42 * get_ui_scale(cTB)

    row = cTB.vBase.row(align=True)
    row.scale_x = 1.1
    row.scale_y = 1.1

    box = row.box()
    col = box.column()

    primary = upgrade_content.upgrading_primary_text
    secondary = upgrade_content.upgrading_secondary_text
    text = f"{primary}   {secondary}"  # three spaces are deliberate
    wrapped_label(cTB, width=width, text=text, container=col)


def _draw_banner_finished(cTB, upgrade_content: UpgradeContent) -> None:
    """Draws the final sucess/error banner."""

    width = cTB.width_draw_ui - 42 * get_ui_scale(cTB)

    row = cTB.vBase.row(align=True)
    row.scale_x = 1.1
    row.scale_y = 1.1

    box = row.box()
    col = box.column()

    if cTB.msg_plan_upgrade_finished is not None:
        text = cTB.msg_plan_upgrade_finished
    elif cTB.error_plan_upgrade is not None:
        head = upgrade_content.error_popup_title
        text = upgrade_content.error_popup_text.format(
            cTB.error_plan_upgrade)
        text = f"{head}: {text}"
    else:
        head = upgrade_content.success_popup_title
        text = upgrade_content.success_popup_text
        text = f"{head}: {text}"

    cTB.msg_plan_upgrade_finished = text
    wrapped_label(cTB, width=width, text=text, container=col)
    row.operator(
        "poliigon.banner_finish_dismiss",
        text="",
        icon="PANEL_CLOSE")


# @timer
def build_upgrade_banner(cTB) -> None:
    """Draws an 'upgrade subscription plan' banner, including a progress
    banner and a success/error banner.
    """

    cTB.logger_ui.debug("build_upgrade_paths")

    if cTB.user is None:
        return
    if cTB.upgrade_manager is None:
        return
    if cTB.upgrade_manager.content is None:
        return

    upgrade_content = cTB.upgrade_manager.content
    if cTB.plan_upgrade_finished:
        _draw_banner_finished(cTB, upgrade_content)
    elif cTB.plan_upgrade_in_progress:
        _draw_banner_in_progress(cTB, upgrade_content)
    elif cTB.upgrade_manager.check_show_banner():
        _draw_banner(cTB, upgrade_content)
    else:
        return

    cTB.vBase.separator()
