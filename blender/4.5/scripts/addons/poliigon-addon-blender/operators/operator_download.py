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

from threading import Event
from typing import Optional

import bpy
from bpy.props import (
    BoolProperty,
    IntProperty,
    StringProperty)
from bpy.types import Operator

from ..modules.poliigon_core.api_remote_control import ApiJob
from ..modules.poliigon_core.assets import AssetData
from ..modules.poliigon_core.multilingual import _t
from ..dialogs.utils_dlg import get_ui_scale, wrapped_label
from ..constants import POPUP_WIDTH_NARROW, POPUP_WIDTH_LABEL_NARROW
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_download(Operator):
    bl_idname = "poliigon.poliigon_download"
    bl_label = ""
    bl_description = _t("(Download Asset from Poliigon.com)")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    size: StringProperty(options={"HIDDEN"})  # noqa: F821
    do_synchronous: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def _callback_done_sync(self, job: ApiJob) -> None:
        cTB.callback_asset_update_ui(job)
        self.event_sync.set()

    def create_auto_download_job(self, asset_data: AssetData) -> Optional[ApiJob]:
        """Create the follow up download job to attach to purchase job."""

        # NOTE: Free assets are implicitly always "auto-download"
        credits = 0 if asset_data.credits is None else asset_data.credits
        if not cTB.settings["auto_download"] and credits > 0:
            return None

        name_renderer = "Cycles"

        fbx_only = False
        if fbx_only:
            native_mesh = False
        else:
            native_mesh = bool(cTB.settings["download_prefer_blend"])
        if native_mesh:
            download_lods = False
        else:
            download_lods = bool(cTB.settings["download_lods"])

        if self.do_synchronous:
            self.event_sync = Event()
            callback_done = self._callback_done_sync
        else:
            callback_done = cTB.callback_asset_update_ui

        job_download = cTB.api_rc.create_job_download_asset(
            asset_data,
            size=self.size,
            size_bg=self.size,
            type_bg=None,
            lod="NONE",
            variant="",
            download_lods=download_lods,
            native_mesh=native_mesh,
            renderer=name_renderer,
            callback_progress=cTB.callback_asset_update_ui,
            callback_done=callback_done
        )
        return job_download

    @reporting.handle_operator()
    def execute(self, context):

        asset_data = cTB._asset_index.get_asset(self.asset_id)

        if self.mode == "download":
            if ";" in self.size:
                # Presumed previously supported multi size downloads using ;
                # as a separator. No longer allowed.
                reporting.capture_message(
                    "reached_legacy_multi_vsize_for_dl",
                    f"size contained unexpected `;` {self.size}")
                self.report(
                    {"ERROR"},
                    _t("Failed to download, multiple sizes specified")
                )
                return {"CANCELLED"}

            size = None
            if self.size != "":
                size = self.size

            cTB.logger.debug("POLIIGON_OT_download Queue download asset "
                             f"{self.asset_id}")

            name_renderer = "Cycles"

            fbx_only = False
            if fbx_only:
                native_mesh = False
                download_lods = cTB.settings["download_lods"]
            else:
                native_mesh = bool(cTB.settings["download_prefer_blend"])
            if native_mesh:
                download_lods = False
            else:
                download_lods = bool(cTB.settings["download_lods"])

            if self.do_synchronous:
                self.event_sync = Event()
                callback_done = self._callback_done_sync
            else:
                callback_done = cTB.callback_asset_update_ui

            cTB.api_rc.add_job_download_asset(
                asset_data,
                size=size,
                size_bg="",
                type_bg="EXR",
                lod="NONE",
                variant=None,
                download_lods=download_lods,
                native_mesh=native_mesh,
                renderer=name_renderer,
                callback_progress=cTB.callback_asset_update_ui,
                callback_done=callback_done
            )

            bpy.ops.poliigon.popup_first_download("INVOKE_DEFAULT")
        elif self.mode == "purchase":
            cTB.logger.debug("POLIIGON_OT_download Purchase asset "
                             f"{self.asset_id}")

            job_download = self.create_auto_download_job(asset_data)

            area = cTB.settings["area"]
            search = cTB.vSearch[area]

            if self.do_synchronous and job_download is None:
                self.event_sync = Event()
                callback_done = self._callback_done_sync
            else:
                callback_done = cTB.callback_asset_update_ui

            cTB.api_rc.add_job_purchase_asset(
                asset_data,
                cTB.settings["category"],
                search,
                job_download=job_download,
                callback_done=callback_done,
                force=True
            )
            one_click_purchase = cTB.settings["one_click_purchase"]
            if one_click_purchase:
                bpy.ops.poliigon.popup_first_download("INVOKE_DEFAULT")

        if self.do_synchronous:
            self.event_sync.wait(30.0)

        cTB.refresh_ui()
        return {"FINISHED"}


class POLIIGON_OT_popup_purchase(Operator):
    bl_idname = "poliigon.popup_purchase"
    bl_label = _t("Purchase Confirmation")
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    size: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def invoke(self, context, event):
        cTB.signal_popup(popup="CONFIRM_PURCHASE")
        return context.window_manager.invoke_props_dialog(
            self, width=POPUP_WIDTH_NARROW)

    @reporting.handle_draw()
    def draw(self, context):
        label_width = POPUP_WIDTH_LABEL_NARROW * get_ui_scale(cTB)

        col_content = self.layout.column()
        wrapped_label(
            cTB,
            width=label_width,
            text=_t("Would you like to confirm purchase of this asset?"),
            container=col_content,
            add_padding_bottom=True)
        wrapped_label(
            cTB,
            width=label_width,
            text=_t("You can turn this reminder off in preferences by "
                    "unchecking Show Purchase Confirmation"),
            container=col_content)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        cTB.signal_popup(popup="CONFIRM_PURCHASE", click="CONFIRM_PURCHASE")
        bpy.ops.poliigon.poliigon_download(
            asset_id=self.asset_id,
            mode=self.mode,
            size=self.size)
        cTB.refresh_ui()
        return {'FINISHED'}
