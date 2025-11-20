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
from bpy.props import StringProperty
from bpy.types import Operator

from ..modules.poliigon_core.api import TIMEOUT
from ..modules.poliigon_core.multilingual import _t
from ..modules.poliigon_core.upgrade_content import UpgradeContent
from ..dialogs.utils_dlg import get_ui_scale, wrapped_label
from ..constants import POPUP_WIDTH_LABEL
from ..toolbox import (
    get_context,
    t_check_change_plan_response)
from .. import reporting


# A bit longer than API timeouts
TIMEOUT_CHANGE_PLAN = TIMEOUT + 1.0


class POLIIGON_OT_popup_change_plan(Operator):
    """This operator provides the 'subscription plan update' details popup
    dialog.
    """

    bl_idname = "poliigon.popup_change_plan"
    bl_label = _t("Change Plan")
    bl_options = {"INTERNAL", "REGISTER", "UNDO"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def invoke(self, context, event):
        cTB.plan_upgrade_in_progress = False
        cTB.plan_upgrade_finished = False
        cTB.msg_plan_upgrade_finished = None
        cTB.upgrade_manager.emit_signal(clicked=True)
        return context.window_manager.invoke_props_popup(self, event)

    def _draw_plan_details(
        self,
        layout: bpy.types.UILayout,
        upgrade_content: UpgradeContent
    ) -> None:
        """Draws the plan details table."""

        upgrade_popup_table = upgrade_content.upgrade_popup_table
        upgrade_popup_key_value = upgrade_content.upgrade_popup_key_value
        if upgrade_popup_table is None and upgrade_popup_key_value is None:
            return

        row = layout.row()
        col_left = row.column(align=True)
        col_right = row.column(align=True)

        if upgrade_popup_table is not None:
            for _label, _value in upgrade_popup_table.items():
                col_left.label(text=_label)
                col_right.label(text=_value)

        col_left.label(text=_t(" "))
        col_right.label(text=_t(" "))

        if upgrade_popup_key_value is not None:
            for _label, _value in upgrade_popup_key_value.items():
                col_left.label(text=_label)
                col_right.label(text=_value)

        layout.separator()

    def _draw_note(
        self,
        layout: bpy.types.UILayout,
        label_width: float,
        upgrade_content: UpgradeContent
    ) -> None:
        """Draws a text note (e.g. tax advice...)."""

        text = upgrade_content.upgrade_popup_text
        if text is None:
            return

        row = layout.row()
        col = row.column(align=True)
        wrapped_label(
            cTB,
            width=label_width,
            text=text,
            container=col,
            add_padding_bottom=True)

    def _draw_button_change_plan(
        self,
        layout: bpy.types.UILayout,
        upgrade_content: UpgradeContent
    ) -> None:
        """Draws the confirmation button to actually change the subscription
        plan.
        """

        label = upgrade_content.upgrade_popup_confirm_button

        row_button = layout.row()
        row_button.operator_context = 'INVOKE_DEFAULT'
        op = row_button.operator(
            "poliigon.change_plan", text=label)
        op.tooltip = _t("Confirm the change of your subscription plan")

    def _draw_legal(
        self,
        layout: bpy.types.UILayout,
        upgrade_content: UpgradeContent
    ) -> None:
        """Draws legal web links."""

        row = layout.row()
        col = row.column(align=True)

        if upgrade_content.upgrade_popup_pricing_button is not None:
            label = upgrade_content.upgrade_popup_pricing_button
            op_pricing = col.operator("poliigon.poliigon_link",
                                      text=label,
                                      emboss=False)
            op_pricing.tooltip = _t("View all pricing details online")
            op_pricing.mode = "subscribe"

        if upgrade_content.upgrade_popup_terms_button is not None:
            label = upgrade_content.upgrade_popup_terms_button
            op_terms = col.operator("poliigon.poliigon_link",
                                    text=label,
                                    emboss=False)
            op_terms.tooltip = _t("View our terms & policy documents online")
            op_terms.mode = "terms_policy"

    @reporting.handle_draw()
    def draw(self, context):
        label_width = POPUP_WIDTH_LABEL * get_ui_scale(cTB)
        # Accounting for the left+right border columns (eyeballing):
        if bpy.app.version >= (4, 0):
            label_width -= 10.0
        elif bpy.app.version >= (3, 0):
            # TODO(Andreas): Scale for other versions and in other popups, too?
            label_width -= 25.0 * get_ui_scale(cTB)
        else:
            label_width -= 10.0

        col_content = self.layout.column()

        upgrade_content = cTB.upgrade_manager.content

        self._draw_plan_details(col_content, upgrade_content)

        self._draw_note(col_content, label_width, upgrade_content)

        self._draw_button_change_plan(col_content, upgrade_content)

        self._draw_legal(col_content, upgrade_content)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        return {'FINISHED'}


class POLIIGON_OT_banner_change_plan_dismiss(Operator):
    """This operator provides the functionality to dismiss any
    'subscription plan update' banner (if the banner type allows dismissal).
    """

    bl_idname = "poliigon.popup_change_plan_dismiss"
    bl_label = _t("Dismiss upgrade notice")
    bl_options = {"INTERNAL", "REGISTER"}
    bl_description = _t("Dismiss upgrade notice")

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return cls.bl_description

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        cTB.upgrade_manager.dismiss_upgrade()
        cTB.refresh_ui()
        return {'FINISHED'}


class POLIIGON_OT_banner_finish_dismiss(Operator):
    """This operator provides the functionality to dismiss the final
    success/error banner of a 'subscription plan update'.
    """

    bl_idname = "poliigon.banner_finish_dismiss"
    bl_label = _t("Dismiss this message")
    bl_options = {"INTERNAL", "REGISTER"}
    bl_description = _t("Dismiss this message")

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return cls.bl_description

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        cTB.plan_upgrade_in_progress = False
        cTB.plan_upgrade_finished = False
        cTB.msg_plan_upgrade_finished = None
        cTB.refresh_ui()
        return {'FINISHED'}


class POLIIGON_OT_change_plan(Operator):
    """This operator (usually triggered by button in 'change plan' popup)
    executes the actual change of the subscription plan.
    """

    bl_idname = "poliigon.change_plan"
    bl_label = _t("Change Plan")
    bl_options = {"INTERNAL", "REGISTER"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @reporting.handle_draw()
    def draw(self, context):
        return

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        # Close the 'change plan' popup
        # (yeah, I know, but it indeed works...)
        # From: https://blender.stackexchange.com/questions/202550/close-a-popup-with-an-op-call
        context.window.screen = context.window.screen

        cTB.plan_upgrade_in_progress = True
        cTB.upgrade_manager.finish_upgrade_plan()

        # Just to make sure, the progress banner does not stay on,
        # even if hell freezes over.
        if bpy.app.timers.is_registered(t_check_change_plan_response):
            bpy.app.timers.unregister(t_check_change_plan_response)
        bpy.app.timers.register(
            t_check_change_plan_response,
            first_interval=TIMEOUT_CHANGE_PLAN,
            persistent=True)

        cTB.refresh_ui()
        return {'FINISHED'}
