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

import datetime
from threading import Event
import time

import bpy
from bpy.types import Operator
from bpy.props import (BoolProperty, StringProperty)

from ..modules.poliigon_core.api_remote_control import ApiJob
from ..modules.poliigon_core.api_remote_control_params import CmdLoginMode
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_user(Operator):
    bl_idname = "poliigon.poliigon_user"
    bl_label = ""
    bl_description = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    do_synchronous: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def _login_determine_elapsed(self) -> None:
        """Calculates the time between addon enable and login.

        This is included in the initiate login or direct email/pwd login only
        if this is the first time install+login. This value gets included in
        the initiate/login request which will treat as an addon install event.
        """

        cTB.login_elapsed_s = None
        if not cTB.settings["first_enabled_time"]:
            return

        now = datetime.datetime.now()
        install_tstr = cTB.settings["first_enabled_time"]
        install_t = datetime.datetime.strptime(
            install_tstr, "%Y-%m-%d %H:%M:%S")
        elapsed = now - install_t
        cTB.login_elapsed_s = int(elapsed.total_seconds())
        if cTB.login_elapsed_s <= 0:
            cTB.logger.debug(
                "POLIIGON_OT_user Throwing out negative elapsed time")
            cTB.login_elapsed_s = None

    def _callback_login_done_sync(self, job: ApiJob) -> None:
        cTB.callback_login_done(job)
        self.event_sync.set()

    def _callback_logout_done_sync(self, job: ApiJob) -> None:
        cTB.callback_logout_done(job)
        self.event_sync.set()

    def _do_login(self, cTB) -> None:
        cTB.logger.debug(
            "POLIIGON_OT_user Sending login with website request")

        cTB.login_cancelled = False
        cTB.login_res = None
        cTB.login_time_start = time.time()

        cTB.login_in_progress = True
        cTB.last_login_error = None

        if self.do_synchronous:
            self.event_sync = Event()
            callback_login_done = self._callback_login_done_sync
            callback_logout_done = self._callback_logout_done_sync
        else:
            callback_login_done = cTB.callback_login_done
            callback_logout_done = cTB.callback_logout_done

        if self.mode == "login_with_website":
            mode = CmdLoginMode.LOGIN_BROWSER
            callback_cancel = cTB.callback_login_cancel
            callback_done = callback_login_done
            email = None
            pwd = None
            login_elapsed_s = cTB.login_elapsed_s
            cTB.login_is_signup = False  # Flag to indicate login was clicked
        elif self.mode == "login":  # Now only used in tests
            mode = CmdLoginMode.LOGIN_CREDENTIALS
            callback_cancel = None
            callback_done = callback_login_done
            email = bpy.context.window_manager.poliigon_props.vEmail
            pwd = bpy.context.window_manager.poliigon_props.vPassHide
            login_elapsed_s = cTB.login_elapsed_s
        elif self.mode == "logout":
            mode = CmdLoginMode.LOGOUT
            callback_cancel = None
            callback_done = callback_logout_done
            email = None
            pwd = None
            login_elapsed_s = None

        cTB.api_rc.add_job_login(
            mode=mode,
            email=email,
            pwd=pwd,
            time_since_enable=login_elapsed_s,
            callback_cancel=callback_cancel,
            callback_done=callback_done,
            force=True
        )

        if self.do_synchronous:
            self.event_sync.wait(30.0)

    @reporting.handle_operator()
    def execute(self, context):
        global cTB

        self._login_determine_elapsed()

        if self.mode in ["login", "login_with_website", "logout"]:
            self._do_login(cTB)
        elif self.mode == "login_cancel":
            cTB.login_cancelled = True
            # Reset the login_in_progress flag to return UI to normal state
            cTB.login_in_progress = False
            cTB.login_is_signup = False  # Reset signup flag when cancelling
            cTB.last_login_error = None
        else:
            cTB.logger.error(
                f"POLIIGON_OT_user UNKNOWN LOGIN COMMAND {self.mode}")

        cTB.refresh_ui()
        return {"FINISHED"}
