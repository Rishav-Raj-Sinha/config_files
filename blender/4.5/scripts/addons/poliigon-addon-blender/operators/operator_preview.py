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

from typing import List
import threading
import time

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    IntProperty,
    StringProperty)
import bpy.utils.previews
import bmesh

from ..modules.poliigon_core.api_remote_control import ApiJob
from ..modules.poliigon_core.multilingual import _t
from ..dialogs.utils_dlg import get_ui_scale, wrapped_label
from ..constants import POPUP_WIDTH_NARROW, POPUP_WIDTH_LABEL_NARROW
from ..toolbox import get_context
from ..toolbox_settings import save_settings
from ..utils import load_image
from .. import reporting


class POLIIGON_OT_preview(Operator):
    """Download and apply a watermarked version of this texture for previewing."""

    bl_idname = "poliigon.poliigon_preview"
    bl_label = _t("Texture Preview")
    bl_description = _t("Download and apply a watermarked version of this texture for previewing")
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "INTERNAL", "UNDO"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)
        self.asset_data = None

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
        self.asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_name = self.asset_data.asset_name

        t_start = time.time()
        files = self.download_preview(context)
        t_downloaded = time.time()

        if len(files) == 0:
            self.report({'ERROR'}, _t("Failed to download preview files"))
            struc_str = f"asset_name: {asset_name}"
            reporting.capture_message(
                "quick_preview_download_failed", struc_str, "error")
            return {'CANCELLED'}

        # Warn user on viewport change before post process, so that any later
        # warnings will popup and take priority to be visible to user. Blender
        # shows the last "self.report" message only (but all print to console).
        self.report_viewport(context)
        cTB.refresh_ui()

        res = self.post_process_material(context, files)

        t_post_processed = time.time()
        total_time = t_post_processed - t_start
        download_time = t_downloaded - t_start

        debug_str = (f"Preview Total time: {total_time}, "
                     f"download: {download_time}")
        cTB.logger.debug(f"POLIIGON_OT_preview {debug_str}")

        # Set the flag that user has used watermarked preview
        cTB.set_onboarding_wm_preview_done()
        save_settings(cTB)

        cTB.signal_preview_asset(asset_id=self.asset_id)
        return res

    def _callback_download_wm_preview_done(self, job: ApiJob) -> None:
        self.ev_download_done.set()

    def download_preview(self, context) -> List[str]:
        """Download a preview and return expected files."""

        asset_name = self.asset_data.asset_name
        asset_type_data = self.asset_data.get_type_data()

        self._name = f"PREVIEW_{asset_name}"

        if len(asset_type_data.watermarked_urls):
            bpy.context.window.cursor_set("WAIT")

            self.ev_download_done = threading.Event()

            cTB.api_rc.add_job_download_wm_preview(
                self.asset_data,
                renderer="Cycles",  # TODO(Andreas)
                callback_done=self._callback_download_wm_preview_done
            )
            self.ev_download_done.wait()
            self.ev_download_done = None
            workflow = asset_type_data.get_workflow("METALNESS")
            tex_maps = asset_type_data.get_maps(workflow=workflow, size="WM")
            files = [_tex_map.get_path() for _tex_map in tex_maps]
            return files
        else:
            return []

    @staticmethod
    def create_plane(context,
                     scale: float = 5.0,
                     aspect_ratio: float = 1.0,
                     name: str = "Preview Plane",
                     do_select: bool = True
                     ) -> bpy.types.Object:
        """Creates a new primitive plane object."""

        mesh = bpy.data.meshes.new(name)
        uv_layer = mesh.uv_layers.new()
        mesh.uv_layers.active = uv_layer

        obj = bpy.data.objects.new(name, mesh)

        bpy.context.collection.objects.link(obj)

        bm = bmesh.new()
        bm.from_mesh(mesh)

        x = (scale / 2.0) * aspect_ratio
        y = scale / 2.0
        bm.verts.new((x, y, 0))
        bm.verts.new((x, -y, 0))
        bm.verts.new((-x, -y, 0))
        bm.verts.new((-x, y, 0))

        bm.verts.ensure_lookup_table()
        # Have inverted vertex order for our normal to point upward
        face = bm.faces.new(
            (bm.verts[3], bm.verts[2], bm.verts[1], bm.verts[0]))
        bm.faces.ensure_lookup_table()

        uv_layer = bm.loops.layers.uv.verify()

        face.loops[0][uv_layer].uv = (1.0, 1.0)
        face.loops[1][uv_layer].uv = (1.0, -1.0)
        face.loops[2][uv_layer].uv = (-1.0, -1.0)
        face.loops[3][uv_layer].uv = (-1.0, 1.0)

        bmesh.ops.contextual_create(bm, geom=bm.verts)
        bm.to_mesh(mesh)
        bm.free()

        obj.location = context.scene.cursor.location
        if do_select:
            obj.select_set(True)
        return obj

    def post_process_material(self, context, files):
        """Run after the download of WM textures has completed."""

        asset_name = self.asset_data.asset_name
        asset_type_data = self.asset_data.get_type_data()
        workflow = asset_type_data.get_workflow("METALNESS")

        bpy.context.window.cursor_set("DEFAULT")

        mat = cTB.mat_import.import_material(
            asset_data=self.asset_data,
            do_apply=False,
            workflow=workflow,
            size="WM",
            size_bg=None,
            lod="",
            variant=None,
            name_material=None,
            name_mesh=None,
            ref_objs=None,
            projection="UV",
            use_16bit=True,
            mode_disp="NORMAL",
            translate_x=0.0,
            translate_y=0.0,
            scale=1.0,
            global_rotation=0.0,
            aspect_ratio=1.0,
            displacement=0.0,
            keep_unused_tex_nodes=False,
            reuse_existing=True,
            map_prefs=None  # Previews ignore map prefs
        )
        if mat is None:
            self.report({"ERROR"}, _t("Material could not be created."))
            reporting.capture_message(
                "could_not_create_preview_mat", asset_name, "error")
            return {"CANCELLED"}

        objs_selected = [_obj
                         for _obj in context.scene.objects
                         if _obj.select_get()]
        if len(objs_selected) == 0:
            img_preview = None
            for _img in bpy.data.images:
                if _img.filepath in files:
                    img_preview = _img
                    # TODO(Andreas): Added this break as it seemed appropriate.
                    #                Correct???
                    #                Consequence is we take AR from first
                    #                instead of last image in sequence
                    break

            if img_preview is not None:
                aspect_ratio = img_preview.size[0] / img_preview.size[1]
            else:
                aspect_ratio = 1.0

            self.create_plane(
                context, aspect_ratio=aspect_ratio, do_select=True)

        result = bpy.ops.poliigon.poliigon_apply(
            "INVOKE_DEFAULT",
            asset_id=self.asset_id,
            name_material=mat.name
        )
        if result == {"CANCELLED"}:
            self.report(
                {"WARNING"}, _t("Could not apply materials to selection"))

        bpy.context.window.cursor_set("DEFAULT")
        return {"FINISHED"}

    def report_viewport(self, context):
        """Send the appropriate report based on the current shading mode."""

        any_mat_or_render = False
        for vA in context.screen.areas:
            if vA.type != "VIEW_3D":
                continue
            for vSpace in vA.spaces:
                if vSpace.type != "VIEW_3D":
                    continue
                if vSpace.shading.type in ["MATERIAL", "RENDERED"]:
                    any_mat_or_render = True

        if not any_mat_or_render:
            msg = _t(
                "Enter material or rendered mode to view applied quick preview"
            )
            self.report({'WARNING'}, msg)


class POLIIGON_OT_popup_first_preview(Operator):
    bl_idname = "poliigon.popup_first_preview"
    bl_label = _t("Texture Preview")
    bl_description = _t("Download and apply a watermarked version of this texture for previewing")
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    force: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def _load_images(self) -> None:
        path = os.path.join(cTB.dir_script, "onboarding_watermarked.png")
        self.img_welcome = load_image("POPUP_watermarked", path)

    def invoke(self, context, event):
        if cTB.settings["popup_preview"] and not self.force:
            return {'FINISHED'}

        self._load_images()
        save_settings(cTB)
        cTB.signal_popup(popup="ONBOARD_WMPREVIEW")
        return context.window_manager.invoke_props_dialog(
            self, width=POPUP_WIDTH_NARROW)

    @reporting.handle_draw()
    def draw(self, context):
        label_width = POPUP_WIDTH_LABEL_NARROW * get_ui_scale(cTB)
        # Accounting for the left+right border columns:
        label_width -= 10.0

        col_content = self.layout.column()

        col_image = col_content.column()
        col_image.scale_y = 0.5
        col_image.template_icon(
            icon_value=self.img_welcome.preview.icon_id,
            scale=18.0)

        row_text = col_content.row()
        if bpy.app.version >= (3, 0):
            col_left_gap = row_text.column()
            col_left_gap.alignment = "LEFT"
            col_left_gap.label(text=" ")
            col_text = row_text.column()
        else:
            col_left_gap = row_text.column()
            col_left_gap.alignment = "LEFT"
            # Note, here no label in left column. Otherwise we'd end up with a
            # way too larger border gap.
            col_text = row_text.column()
            col_text.alignment = "CENTER"

        wrapped_label(
            cTB,
            width=label_width,
            text=_t("Previews are watermarked 1K resolution textures."),
            container=col_text,
            add_padding=True)
        wrapped_label(
            cTB,
            width=label_width,
            text=_t("Subscribe to download high-resolution textures up to 8K "
                    "without watermarks."),
            container=col_text,
            add_padding_bottom=True)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        cTB.settings["popup_preview"] = 1
        # Set the flag that user has used watermarked preview
        cTB.set_onboarding_wm_preview_done()
        save_settings(cTB)
        cTB.signal_popup(popup="ONBOARD_WMPREVIEW", click="ONBOARD_WMPREVIEW")
        bpy.ops.poliigon.poliigon_preview(asset_id=self.asset_id)
        cTB.refresh_ui()
        return {'FINISHED'}
