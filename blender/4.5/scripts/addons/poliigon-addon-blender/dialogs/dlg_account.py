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


def _build_section_free_user(cTB) -> None:
    w_label = cTB.width_draw_ui - 20 * get_ui_scale(cTB)

    box_free = cTB.vBase.box()
    col = box_free.column()

    col.label(text=_t("Get more with Pro"),
              icon_value=cTB.ui_icons["ICON_checkmark_verified"].icon_id)
    spacer = col.row()
    spacer.scale_y = 0.5
    spacer.label(text="")

    msg = _t("Access the full resolution downloads of 5,000+ assets")
    wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True, icon="CHECKMARK")
    msg = _t("Commercial & personal use license")
    wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True, icon="CHECKMARK")
    msg = _t("Cancel or pause at any time in a few clicks")
    wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True, icon="CHECKMARK")
    msg = _t("50% discount for students and teachers")
    wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True, icon="CHECKMARK")

    button_row = col.row()
    button_row.scale_y = 1.3
    op = button_row.operator("poliigon.poliigon_link", text=_t("View Pricing"), depress=True)
    op.mode = "subscribe"
    # TODO(Andreas): Figma did not contain any tooltips...
    op.tooltip = _t("View Poliigon Pricing Online")


def _build_section_paid_plan(cTB) -> None:
    w_label = cTB.width_draw_ui - 20 * get_ui_scale(cTB)

    box_free = cTB.vBase.box()
    col = box_free.column()

    col.label(text=_t("My Account"),
              icon="COMMUNITY")
    spacer = col.row()
    spacer.scale_y = 0.5
    spacer.label(text="")

    name_plan = cTB.user.plan.plan_name
    wrapped_label(cTB, w_label, name_plan, col, add_padding=False, add_padding_bottom=True)

    if not cTB.is_unlimited_user():
        credits = cTB.user.plan.plan_credit
        msg = _t("Assets per month: {0}").format(credits)
        wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True)

    next_renew = cTB.user.plan.next_subscription_renewal_date
    msg = _t("Renewal Date: {0}").format(next_renew)
    wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True)

    is_paused = cTB.is_paused_subscription()
    status = _t("Paused") if is_paused else _t("Active")
    msg = _t("Status: {0}").format(status)
    wrapped_label(cTB, w_label, msg, col, add_padding=False, add_padding_bottom=True)

    button_row = col.row()
    button_row.scale_y = 1.3
    op = button_row.operator("poliigon.poliigon_link", text=_t("Manage Account"))
    op.mode = "credits"
    # TODO(Andreas): Figma did not contain any tooltips...
    op.tooltip = _t("View details of your plan online")


def _build_still_loading(cTB) -> None:
    box_free = cTB.vBase.box()
    col = box_free.column()
    w_label = cTB.width_draw_ui - 20 * get_ui_scale(cTB)
    wrapped_label(
        cTB, w_label, "Fetching user data...", col, add_padding=False)


def build_user(cTB) -> None:
    cTB.logger_ui.debug("build_user")
    free_account = cTB.is_free_user() or cTB.user.plan.plan_name is None

    if cTB.fetching_user_data:
        _build_still_loading(cTB)
        return

    if free_account:
        _build_section_free_user(cTB)
    else:
        _build_section_paid_plan(cTB)

    cTB.vBase.separator()
    op = cTB.vBase.operator("poliigon.poliigon_user", text=_t("Log Out"))
    op.mode = "logout"
    op.tooltip = _t("Log Out of Poliigon")
