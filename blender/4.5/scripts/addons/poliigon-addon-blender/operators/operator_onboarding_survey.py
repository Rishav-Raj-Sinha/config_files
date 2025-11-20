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

from ..modules.poliigon_core.multilingual import _t
from ..modules.poliigon_core.user import PoliigonUserProfiles
from ..toolbox import get_context
from ..toolbox_settings import save_settings
from .. import reporting


class POLIIGON_OT_onboarding_survey(Operator):
    bl_idname = "poliigon.poliigon_onboarding_survey"
    bl_label = _t("Onboarding Survey")
    bl_description = _t("Handle onboarding survey interactions")
    bl_options = {"REGISTER", "INTERNAL"}

    user_type: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""
        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        """Return description based on user type."""
        # Default description
        desc = cls.bl_description

        # Get specific descriptions based on user_type
        if properties.user_type == "As a student":
            desc = _t("As a student")
        elif properties.user_type == "As a teacher":
            desc = _t("As a teacher")
        elif properties.user_type == "As a hobbyist":
            desc = _t("As a hobbyist")
        elif properties.user_type == "As a professional (individual)":
            desc = _t("As a professional (individual)")
        elif properties.user_type == "As a professional (studio/team)":
            desc = _t("As a professional (studio/team)")

        return desc

    def _submit_onboarding_survey(self, vProps) -> None:
        """Submit the onboarding survey"""
        user_type_enum = PoliigonUserProfiles.from_string(self.user_type)
        email_optin = vProps.onboarding_email_preference

        if not user_type_enum:
            err = f"Invalid user type selected: {user_type_enum}"
            cTB.logger.error(err)
            reporting.capture_message("invalid_user_type", err, "error")
            return

        cTB.user.user_profile = user_type_enum
        cTB.user.email_preference = email_optin
        cTB.update_user_use()

    @reporting.handle_operator()
    def execute(self, context):
        """Handle onboarding survey interactions."""
        vProps = context.window_manager.poliigon_props
        cTB.logger.debug(f"Selected user type: {self.user_type}")

        # Clear the onboarding survey flag to hide the dialog immediately
        cTB.did_show_profile_survey = True

        # Persist the selection
        save_settings(cTB)

        self._submit_onboarding_survey(vProps)
        cTB.refresh_ui()
        return {'FINISHED'}


def register():
    bpy.utils.register_class(POLIIGON_OT_onboarding_survey)


def unregister():
    bpy.utils.unregister_class(POLIIGON_OT_onboarding_survey)
