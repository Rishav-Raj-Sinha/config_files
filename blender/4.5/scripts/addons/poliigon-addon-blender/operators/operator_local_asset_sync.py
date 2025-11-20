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

import time
from threading import Event

from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty)
from bpy.types import Operator

from ..modules.poliigon_core.api_remote_control import ApiJob
from ..modules.poliigon_core.api_remote_control_params import (
    CATEGORY_ALL,
    KEY_TAB_MY_ASSETS,
    KEY_TAB_ONLINE)
from ..constants import ASSET_ID_ALL
from ..toolbox import get_context


class POLIIGON_OT_get_local_asset_sync(Operator):
    bl_idname = "poliigon.get_local_asset_sync"
    bl_label = "For internal testing, only"
    bl_description = "For internal testing, only"
    bl_options = {"INTERNAL"}

    timeout: FloatProperty(options={"HIDDEN"}, default=60.0)  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"}, default=ASSET_ID_ALL)  # noqa: F821
    await_startup_poliigon: BoolProperty(options={"HIDDEN"}, default=True)  # noqa: F821
    await_startup_my_assets: BoolProperty(options={"HIDDEN"}, default=True)  # noqa: F821
    get_poliigon: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821
    get_my_assets: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821
    abort_ongoing_jobs: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    def _callback_get_asset_done(self, job: ApiJob) -> None:
        """Calls the standard done callback and sets local event afterwards."""

        cTB.callback_get_asset_done(job)

        last_page = job.params.idx_page >= job.result.body.get("last_page", -1)
        if last_page:
            self.ev_done.set()

    @staticmethod
    def _is_startup_done(
            *, await_poliigon: bool, await_my_assets: bool) -> bool:
        """Returns True, if the addon is fetching no more asset data."""
        startup_done = True
        if await_poliigon:
            startup_done = cTB.all_assets_fetched
        if await_my_assets:
            startup_done &= cTB.are_user_assets_fetched()
        return startup_done

    def _await_end_of_startup(self) -> None:
        to_wait_s = int(self.timeout)
        startup_done = False
        while to_wait_s > 0:
            startup_done = self._is_startup_done(
                await_poliigon=self.await_startup_poliigon,
                await_my_assets=self.await_startup_my_assets)
            if startup_done:
                break
            time.sleep(1)
            to_wait_s -= 1
        if not startup_done:
            print("FAILED TO AWAIT STARTUP END")

    def _do_sync_get_assets(self) -> bool:
        tabs = []
        if self.get_poliigon:
            tabs.append(KEY_TAB_ONLINE)
        if self.get_my_assets:
            tabs.append(KEY_TAB_MY_ASSETS)

        search = None
        if self.asset_id != ASSET_ID_ALL:
            asset_ids = cTB._asset_index.get_asset_id_list()
            if self.asset_id in asset_ids:
                return True

            search = str(self.asset_id)

        self.ev_done = Event()

        for _tab in tabs:
            cTB.f_GetAssets(
                area=_tab,
                categories=[CATEGORY_ALL],
                search=search,
                force=True,
                # Not only force the job to be added, but also force the actual
                # request, we want fresh data!
                force_request=True,
                callback_done=self._callback_get_asset_done
            )
            if not self.ev_done.wait(self.timeout):
                msg = ("POLIIGON_OT_get_local_asset_sync: Failed to get assets, "
                       f"tab: {_tab}")
                cTB.logger.error(msg)
                return False

            self.ev_done.clear()

        return True

    def execute(self, context):
        if self.abort_ongoing_jobs:
            cTB.api_rc.wait_for_all(do_wait=False)

        self._await_end_of_startup()

        if not self.get_poliigon and not self.get_my_assets:
            return {"FINISHED"}

        result = self._do_sync_get_assets()
        if not result:
            return {"CANCELLED"}

        return {"FINISHED"}
