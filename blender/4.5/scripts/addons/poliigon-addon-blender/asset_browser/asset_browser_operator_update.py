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

from threading import Thread

from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    IntProperty
)
import bpy

from ..modules.poliigon_core.multilingual import _t
from ..constants import ASSET_ID_ALL
from ..toolbox import get_context
from .. import reporting
from . import asset_browser as ab


class POLIIGON_OT_update_asset_browser(Operator):
    bl_idname = "poliigon.update_asset_browser"
    bl_label = _t("Sync Local Assets")
    bl_category = "Poliigon"
    bl_description = _t("Synchronize local assets with Asset Browser")
    bl_options = {"INTERNAL"}

    asset_id: IntProperty(options={"HIDDEN"}, default=ASSET_ID_ALL)  # noqa: F821
    force: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if bpy.app.version < (3, 0):
            self.report(
                {"ERROR"},
                "Asset browser not available in this blender version")
            return {"CANCELLED"}

        bpy.ops.poliigon.get_local_asset_sync(
            await_startup_poliigon=False,
            await_startup_my_assets=False,
            get_poliigon=False,
            get_my_assets=True,
            asset_id=self.asset_id)

        if self.asset_id != ASSET_ID_ALL:
            asset_ids = cTB._asset_index.get_asset_id_list(
                purchased=True, local=True)
            if self.asset_id not in asset_ids:
                self.report(
                    {"ERROR"},
                    f"Asset ID {self.asset_id} not found")
                return {"CANCELLED"}

        if ab.create_poliigon_library() is None:
            cTB.logger_ab.debug("HOST: No Poliigon library in Asset Browser!")
            error_msg = "No Poliigon library in Asset."
            reporting.capture_message(
                "asset_browser_no_polii_lib", error_msg, "error")
            self.report({"ERROR"}, error_msg)
            return {"CANCELLED"}

        thd_init_sync = Thread(
            target=ab.thread_initiate_asset_synchronization,
            args=(self.asset_id, self.force, ))
        thd_init_sync.start()
        cTB.threads.append(thd_init_sync)

        return {"FINISHED"}
