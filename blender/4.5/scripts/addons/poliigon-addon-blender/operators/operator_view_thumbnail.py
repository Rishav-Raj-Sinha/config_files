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

import os
from typing import Tuple

import bpy
from bpy.types import Operator
from bpy.props import (
    IntProperty,
    StringProperty)
import bpy.utils.previews

from ..modules.poliigon_core.assets import AssetData
from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_view_thumbnail(Operator):
    bl_idname = "poliigon.view_thumbnail"
    bl_label = ""
    bl_description = _t("View larger thumbnail")
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    thumbnail_index: IntProperty(min=0, options={"HIDDEN"})  # noqa: F821
    resolution: IntProperty(min=300, default=900, options={"HIDDEN"})  # noqa: F821

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
        asset_data = cTB._asset_index.get_asset(self.asset_id)

        op_dims_backup = self._backup_show_render_op_dimensions(context)

        # Don't modify by get_ui_scale(), as it uses physical pixel size. Also
        # making it smaller than 1024 to minimize margins around image.
        pixels = int(self.resolution + 100)
        pixels = min(pixels, 1000)

        res = {'CANCELLED'}
        try:
            # Modify render settings to force new window to appear.
            self._set_show_render_op_dimensions(context, pixels, pixels)

            # Main loading steps
            area = self._create_window(asset_data)
            download_ok = self._download_preview(asset_data)
            if download_ok:
                res = self._load_preview(area, asset_data)

        except Exception as e:
            # If exception occurs, will run after the finally block below.
            raise e

        finally:
            # Ensure we always restore render settings and preferences.
            self._restore_show_render_op_dimensions(context, op_dims_backup)

        cTB.signal_view_screen("large_preview")
        return res

    def _backup_show_render_op_dimensions(
            self, context) -> Tuple[int, int, str]:
        """Stores/backups dimensions of 'show render' operator."""

        # We use the show render operator to hack setting an explicit size,
        # be sure to capture the resolution to revert back.
        render = bpy.context.scene.render
        init_res_x = render.resolution_x
        init_res_y = render.resolution_y
        if hasattr(context.preferences.view, "render_display_type"):
            init_display = bpy.context.preferences.view.render_display_type
        else:
            init_display = context.scene.render.display_mode
        return (init_res_x, init_res_y, init_display)

    def _restore_show_render_op_dimensions(
            self, context, dims_backup: Tuple[int, int, str]) -> None:
        """Restores dimensions of 'show render' operator."""
        init_res_x, init_res_y, init_display = dims_backup

        render = bpy.context.scene.render
        render.resolution_x = init_res_x
        render.resolution_y = init_res_y
        if hasattr(context.preferences.view, "render_display_type"):
            context.preferences.view.render_display_type = init_display
        else:
            context.scene.render.display_mode = init_display

    def _set_show_render_op_dimensions(
            self, context, width: int, height: int) -> None:
        """Sets dimensions of 'show render' operator."""

        render = bpy.context.scene.render
        render.resolution_x = width
        render.resolution_y = height
        if hasattr(context.preferences.view, "render_display_type"):
            context.preferences.view.render_display_type = "WINDOW"
        else:
            context.scene.render.display_mode = "WINDOW"

    def _get_thumb_path_and_url(self) -> Tuple[str, str]:
        path_thumb, url_thumb = cTB._asset_index.get_cf_thumbnail_info(
            self.asset_id,
            resolution=self.resolution,
            index=self.thumbnail_index
        )
        if path_thumb is None or url_thumb is None:
            # Issue already reported inside get_cf_thumbnail_info()
            return None, None

        path, ext = os.path.splitext(path_thumb)
        path_thumb = f"{path}_{self.resolution}px{ext}"

        return path_thumb, url_thumb

    @staticmethod
    def _delete_temp_file(path_thumb_dl: str) -> None:
        """Delete temp file from previous download attempts."""

        if not os.path.exists(path_thumb_dl):
            return

        try:
            os.remove(path_thumb_dl)
        except Exception:
            # TODO(Andreas): Not sure, what to do now.
            #                Would we want to report this?
            pass

    @staticmethod
    def _rename_successful_download(
            path_thumb_dl: str, path_thumb: str) -> None:
        if not os.path.isfile(path_thumb_dl):
            return

        try:
            os.rename(path_thumb_dl, path_thumb)
        except Exception:
            POLIIGON_OT_view_thumbnail._delete_temp_file(path_thumb_dl)
            # TODO(Andreas): Not sure, we would want to report this?

    def _download_preview_exec(self, asset_data: AssetData) -> bool:
        path_thumb, url_thumb = self._get_thumb_path_and_url()
        if path_thumb is None or url_thumb is None:
            return False

        if os.path.isfile(path_thumb):
            return True  # already local

        asset_name = asset_data.asset_name
        path_thumb_dl = f"{path_thumb}_dl"
        self._delete_temp_file(path_thumb_dl)

        resp = cTB._api.download_preview(url_thumb, path_thumb_dl, asset_name)
        if not resp.ok:
            # Issue already reported inside download_preview()
            self._delete_temp_file(path_thumb_dl)
            return False  # Failed download

        self._rename_successful_download(path_thumb_dl, path_thumb)
        return True

    def _download_preview(
            self, asset_data: AssetData) -> bool:
        """Download the target thumbnail if not local, no threading."""

        cTB.logger.debug("POLIIGON_OT_view_thumbnail Download thumbnail index "
                         f"{self.thumbnail_index}")

        bpy.context.window.cursor_set("WAIT")
        result = self._download_preview_exec(asset_data)
        bpy.context.window.cursor_set("DEFAULT")
        return result

    def _create_window(self, asset_data: AssetData):
        # Call image editor window
        asset_name = asset_data.asset_name
        bpy.ops.render.view_show("INVOKE_DEFAULT")

        # Set up the window as needed.
        area = None
        for _window in bpy.context.window_manager.windows:
            this_area = _window.screen.areas[0]
            if this_area.type == "IMAGE_EDITOR":
                area = this_area
                break
        if not area:
            return None

        dispaly_details = asset_data.get_display_details_data()
        details = dispaly_details.get("Physical Size", "")
        rwsize = f" ({details})" if details else ""

        area.header_text_set(_t("Asset thumbnail: {0} {1}").format(
            asset_name, rwsize))
        area.show_menus = False
        return area

    def _load_preview(self, area, asset_data: AssetData):
        """Load in the image preview based on the area."""

        asset_name = asset_data.asset_name
        path_thumb, _ = self._get_thumb_path_and_url()

        if not os.path.isfile(path_thumb):
            self.report({"ERROR"}, _t("Could not find image preview"))
            msg = f"{asset_name}: Could not find image preview {path_thumb}"
            reporting.capture_message("thumbnail_file_missing", msg, "error")
            return {'CANCELLED'}

        thumbnail = bpy.data.images.load(path_thumb)

        if area:
            area.spaces[0].image = thumbnail
        else:
            msg = _t("Open the image now loaded in an image viewer")
            self.report({"ERROR"}, msg)
            err = "Failed to open window for preview"
            reporting.capture_message("img_window_failed_open", err, "info")

        # Tag this image with a property, could be used to trigger UI draws in
        # the viewer in the future.
        thumbnail["poliigon_thumbnail"] = True
        return {'FINISHED'}
