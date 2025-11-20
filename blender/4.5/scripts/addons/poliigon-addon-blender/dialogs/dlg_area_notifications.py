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
from ..modules.poliigon_core.notifications import ActionType
from ..constants import URLS_BLENDER
from .utils_dlg import (
    get_ui_scale,
    wrapped_label)
# from .. import reporting


def build_mode(url, action, id_notice):
    return "notify@{}@{}@{}".format(url, action, id_notice)


def _draw_notification_open_url_two_rows(
        cTB, notice, first_row, main_col, icon) -> None:
    # Two rows (or more, if text wrapping).
    col = first_row.column(align=True)
    col.alert = True
    # Empirically found squaring worked best for 1 & 2x displays,
    # which accounts for the box+panel padding and the 'x' button.
    if notice.allow_dismiss:
        padding_width = 32 * get_ui_scale(cTB)
    else:
        padding_width = 17 * get_ui_scale(cTB)
    wrapped_label(
        cTB, cTB.width_draw_ui - padding_width, notice.title, col)
    col.alert = False

    second_row = main_col.row(align=True)
    second_row.scale_y = 1.0
    op = second_row.operator(
        "poliigon.poliigon_link",
        icon=icon,
        text=notice.label,
    )
    if notice.tooltip != "":
        op.tooltip = notice.tooltip
    op.mode = build_mode(
        notice.url,
        notice.label,
        notice.id_notice)


def _draw_notification_open_url(
        cTB, notice, first_row, main_col, panel_width, icon) -> None:
    _draw_notification_open_url_two_rows(cTB, notice, first_row, main_col, icon)


def _draw_notification_update_ready_single_row(cTB, notice, first_row, icon) -> None:
    # Single row with text + button.
    first_row.alert = True
    first_row.label(text=notice.title)
    first_row.alert = False
    splitrow = first_row.split(factor=0.7, align=True)
    splitcol = splitrow.split(align=True)

    label = notice.label
    if label == "":
        label = notice.title

    op = splitcol.operator(
        "poliigon.poliigon_link",
        icon=icon,
        text=label,
    )
    if notice.tooltip != "":
        op.tooltip = notice.tooltip
    op.mode = build_mode(
        notice.download_url, notice.label, notice.id_notice)

    splitcol = splitrow.split(align=True)
    op = splitcol.operator(
        "poliigon.poliigon_link",
        text="Logs",
    )
    # if notice.tooltip is not None:
    op.tooltip = _t("See changes in this version")
    op.mode = build_mode(
        URLS_BLENDER["changelog"], "Logs", notice.id_notice)


def _draw_notification_update_ready_two_rows(
        cTB, notice, first_row, main_col, icon) -> None:
    # Two rows (or more, if text wrapping).
    col = first_row.column(align=True)
    col.alert = True
    if notice.allow_dismiss:
        padding_width = 32 * get_ui_scale(cTB)
    else:
        padding_width = 17 * get_ui_scale(cTB)
    wrapped_label(
        cTB, cTB.width_draw_ui - padding_width, notice.title, col)
    col.alert = False

    label = notice.label
    if label == "":
        label = notice.title

    second_row = main_col.row(align=True)
    splitrow = second_row.split(factor=0.7, align=True)
    splitcol = splitrow.split(align=True)
    op = splitcol.operator(
        "poliigon.poliigon_link",
        icon=icon,
        text=label,
    )
    if notice.tooltip != "":
        op.tooltip = notice.tooltip
    op.mode = build_mode(
        notice.download_url, notice.label, notice.id_notice)
    splitcol = splitrow.split(align=True)
    op = splitcol.operator(
        "poliigon.poliigon_link",
        text="Logs",
    )
    op.tooltip = _t("See changes in this version")
    op.mode = build_mode(
        URLS_BLENDER["changelog"], "Logs", notice.id_notice)


def _draw_notification_update_ready(
        cTB, notice, first_row, main_col, panel_width, icon) -> None:
    # Empirical for width for "Update ready: Download | logs".
    single_row_width = 300
    if panel_width > single_row_width:
        _draw_notification_update_ready_single_row(
            cTB, notice, first_row, icon)
    else:
        _draw_notification_update_ready_two_rows(
            cTB, notice, first_row, main_col, icon)


def _draw_notification_popup_message_two_rows(
        cTB, notice, first_row, main_col, icon) -> bpy.types.Operator:
    # Two rows (or more, if text wrapping).
    col = first_row.column(align=True)
    col.alert = notice.alert
    # Empirically found squaring worked best for 1 & 2x displays,
    # which accounts for the box+panel padding and the 'x' button.
    if notice.allow_dismiss:
        padding_width = 32 * get_ui_scale(cTB)
    else:
        padding_width = 17 * get_ui_scale(cTB)
    wrapped_label(
        cTB, cTB.width_draw_ui - padding_width, notice.title, col)
    col.alert = False

    second_row = main_col.row(align=True)
    second_row.scale_y = 1.0
    op = second_row.operator(
        "poliigon.popup_message",
        icon=icon,
        text="View",
    )
    return op


def _draw_notification_popup_message(
        cTB, notice, first_row, main_col, panel_width, icon) -> None:
    op = _draw_notification_popup_message_two_rows(
        cTB, notice, first_row, main_col, icon)

    op.message_body = notice.body
    op.notice_id = notice.id_notice
    if notice.tooltip != "":
        op.tooltip = notice.tooltip
    if notice.url != "":
        op.message_url = notice.url


def _draw_notification_run_operator(cTB, notice, first_row, icon) -> None:
    # Single row with only a button.
    op = first_row.operator(
        "poliigon.notice_operator",
        text=notice.title,
        icon=icon,
    )
    op.notice_id = notice.id_notice
    op.ops_name = notice.ops_name
    op.tooltip = notice.tooltip


def _draw_notification_none_action(cTB, notice, first_row, icon) -> None:
    """Draws a notification with no clickable action - just text with dismiss button."""
    # Create a row with icon on the left and text in center (X button handled by main function)
    row = first_row.row(align=True)

    # Icon column on the left - single row for compact height
    icon_col = row.column(align=True)
    icon_col.alignment = "CENTER"
    icon_col.label(text="", icon=icon)

    # Text column in center - fills remaining space
    text_col = row.column()
    text_col.alignment = "CENTER"
    # Using full available width for text
    wrapped_label(
        cTB, cTB.width_draw_ui, notice.title, text_col)
    text_col.alert = False


# TODO(Andreas): deactivated reporting here, as I needed a third parameter and
#                was not able to quickly make handle_draw() work
# @reporting.handle_draw()
def notification_banner(cTB, layout):
    """General purpose notification banner UI draw element."""

    notice = cTB.notify.get_top_notice()

    if notice is None:
        return

    box = layout.box()
    row = box.row(align=True)
    main_col = row.column(align=True)

    scale = max(get_ui_scale(cTB), 1)
    panel_width = cTB.width_draw_ui / scale

    first_row = main_col.row(align=False)
    x_row = first_row  # x_row is the row to add the x button to, if there.

    # Only purpose is to trigger view signal (only once)
    cTB.notify.notification_popup(notice, do_signal_view=True)

    icon = notice.icon
    if icon is None:
        icon = "NONE"

    if notice.action == ActionType.OPEN_URL:
        _draw_notification_open_url(
            cTB, notice, first_row, main_col, panel_width, icon)
    elif notice.action == ActionType.UPDATE_READY:
        _draw_notification_update_ready(
            cTB, notice, first_row, main_col, panel_width, icon)
    elif notice.action == ActionType.POPUP_MESSAGE:
        _draw_notification_popup_message(
            cTB, notice, first_row, main_col, panel_width, icon)
    elif notice.action == ActionType.RUN_OPERATOR:
        _draw_notification_run_operator(cTB, notice, first_row, icon)
    elif notice.action == ActionType.NONE:
        _draw_notification_none_action(cTB, notice, first_row, icon)
    else:
        main_col.label(text=notice.title)
        cTB.logger_ui.error("Invalid notifcation type")

    if notice.allow_dismiss:
        right_col = x_row.column(align=True)
        right_col.operator(
            "poliigon.close_notification", icon="X", text="", emboss=False)

    layout.separator()
