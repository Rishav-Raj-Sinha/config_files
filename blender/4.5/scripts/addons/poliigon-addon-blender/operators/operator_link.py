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

import webbrowser
import bpy

from bpy.types import Operator
from bpy.props import (
    IntProperty,
    BoolProperty,
    StringProperty)

from ..modules.poliigon_core.multilingual import _t
from ..modules.poliigon_core.notifications import (
    NOTICE_ID_SURVEY_FREE,
    NOTICE_ID_SURVEY_ACTIVE,
    NOTICE_ID_UPDATE)
from ..notifications import get_datetime_now
from ..toolbox import get_context
from ..toolbox_settings import save_settings
from .. import reporting


class POLIIGON_OT_link(Operator):
    bl_idname = "poliigon.poliigon_link"
    bl_label = ""
    bl_description = _t("(Find asset on Poliigon.com in your default browser)")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    confirm_popup: BoolProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @reporting.handle_operator()
    def execute(self, context):
        global cTB

        if self.confirm_popup:
            self._confirmation_popup()
            self.confirm_popup = False
            return {"FINISHED"}

        notice = cTB.notify.get_top_notice(do_signal_view=False)
        if self.mode.startswith("notify") and notice is not None:
            cTB.notify.clicked_notice(notice)

            open_free_survey = notice.id_notice == NOTICE_ID_SURVEY_FREE
            open_paying_survey = notice.id_notice == NOTICE_ID_SURVEY_ACTIVE
            update_clicked = notice.id_notice == NOTICE_ID_UPDATE
            if open_free_survey or open_paying_survey:
                time_now = get_datetime_now()
                cTB.settings["last_nps_open"] = time_now.timestamp()
                save_settings(cTB)
                webbrowser.open(notice.url)
            elif update_clicked:
                # TODO(patrick): Remove reliance on the @struc, and _api itself
                if "@Logs" in self.mode:
                    cTB._api.open_poliigon_link("changelog")
                elif "@Update" in self.mode:
                    webbrowser.open(notice.download_url)
            elif hasattr(notice, "url"):
                webbrowser.open(notice.url)
            else:
                reporting.capture_message(
                    "invalid_notify_url", str(notice), "error")
        elif self.mode == "survey" and notice is not None:
            cTB._api.open_poliigon_link(self.mode, env_name=cTB._env.env_name)
            cTB.notify.clicked_notice(notice)
        elif self.mode == "subscribe_banner":
            cTB.upgrade_manager.emit_signal(clicked=True)
            cTB._api.open_poliigon_link("subscribe", env_name=cTB._env.env_name)
        elif self.mode == "signup":
            # Open the signup URL but don't update UI or set login_in_progress flag
            cTB._api.open_poliigon_link(self.mode, env_name=cTB._env.env_name)
        elif self.mode in cTB._api._url_paths:
            cTB._api.open_poliigon_link(self.mode, env_name=cTB._env.env_name)
        elif self.mode.startswith("https:"):
            webbrowser.open(self.mode)
        else:
            # Assume passed in asset id, open asset page.
            asset_id = int(self.mode)
            cTB.open_asset_url(asset_id)

        if notice is not None:
            cTB.notify.dismiss_notice(notice)
        return {"FINISHED"}

    def _confirmation_popup(self):
        bpy.ops.poliigon.popup_message("INVOKE_DEFAULT",
                                       message_body=_t("Open Addon Help in browser?"),
                                       message_url=self.mode)
