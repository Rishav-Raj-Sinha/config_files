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

from enum import IntEnum
from functools import partial
import os
from threading import Event
import time
from typing import Callable, Dict, List, Optional

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    FloatProperty,
    IntProperty)
from bpy.types import Operator
import bpy.utils.previews

from ..modules.poliigon_core.api_remote_control import ApiJob
from ..modules.poliigon_core.assets import (
    AssetData,
    AssetType)
from ..modules.poliigon_core.multilingual import _t
from ..dialogs.utils_dlg import check_convention
from ..dialogs.dlg_assets import (
    _asset_is_local,
    _determine_in_scene_sizes,
    _determine_thumb_width,
    _draw_button_download,
    _draw_button_hdri_local,
    _draw_button_model_local,
    _draw_button_purchase,
    _draw_button_quick_menu,
    _draw_button_texture_local,
    _draw_button_unsupported_convention,
    _draw_thumb_state_asset_downloading,
    _draw_thumb_state_asset_purchasing,
    _draw_thumb_state_cancelling_download,
    THUMB_SIZE_FACTOR)
from ..toolbox import get_context
from ..utils import load_image
from .. import reporting


MAX_NUM_PREVIEWS = 10000
TIMEOUT_THUMB_DOWNLOAD = 15.0  # per single thumb download


class MODE_SELECT(IntEnum):
    # Negative values, as zero and positive ones represent an index
    NEXT = -1
    PREVIOUS = -2


class DetailViewState():
    """Global state class used to transfer information between the three
    involved operators.
    """

    def __init__(
        self,
        num_previews: int,
        ts: float,
        context: bpy.types.Context
    ):
        self.ts: float = ts
        self.context: bpy.types.Context = context
        self.partial_periodic_redraw: Optional[Callable] = None
        self.partials_load_and_redraw: List[Callable] = []

        self.num_previews: int = num_previews
        self.idx_preview: int = 0
        self.img_downloading: Optional[bpy.types.Image] = None
        self.img_error: Optional[bpy.types.Image] = None
        self.imgs_preview: Dict[int, bpy.types.Image] = {}
        self.region_popup: Optional[bpy.types.Region] = None
        self.popup_closed: bool = False  # new state, popup about to open

        self.load_dummy_images()
        self.init_preview_image_dict(num_previews)

    def __del__(self):
        self.cleanup_images()
        self.popup_closed = True

    def load_dummy_images(self) -> None:
        """Loads the dummy images for 'downloading' and 'download error'."""

        theme = bpy.context.preferences.themes[0]
        color_bg = theme.user_interface.wcol_menu_back.inner

        name_downloading = f".POLIIGON_PREVIEW_downloading_{self.ts:.4f}"
        name_error = f".POLIIGON_PREVIEW_error_{self.ts:.4f}"

        path = os.path.join(cTB.dir_script, "get_preview_600px.png")
        self.img_downloading = load_image(
            name_downloading,
            path,
            do_remove_alpha=False,
            color_bg=color_bg)
        # We do not want this image saved into the blend file
        self.img_downloading.user_clear()

        path = os.path.join(cTB.dir_script, "icon_nopreview_600px.png")
        self.img_error = load_image(
            name_error,
            path,
            do_remove_alpha=False,
            color_bg=color_bg)
        # We do not want this image saved into the blend file
        self.img_error.user_clear()

    def init_preview_image_dict(self, num_previews: int) -> None:
        """Prepares the image dictionary with 'downloading dummies'."""

        self.imgs_preview = {}
        for _idx_preview in range(num_previews):
            self.imgs_preview[_idx_preview] = self.img_downloading

    def set_image(self, idx_preview: int, img: bpy.types.Image) -> None:
        """Stores the given image in previews dictionary."""

        self.imgs_preview[idx_preview] = img

    def set_error_image(self, idx_preview: int) -> None:
        """Sets given preview index to error state (storing error image in
        preview dictionary).
        """

        self.imgs_preview[idx_preview] = self.img_error

    def cleanup_images(self) -> None:
        """Removes all images from blend data."""

        name_downloading = f".POLIIGON_PREVIEW_downloading_{self.ts:.4f}"
        name_error = f".POLIIGON_PREVIEW_error_{self.ts:.4f}"

        for _img in self.imgs_preview.values():
            if _img.name in [name_downloading,
                             name_error]:
                # Skip any dummy images (thumbs with error or not yet
                # downloaded), the actual dummy images get free'd below.
                continue
            _img.user_clear()
            bpy.data.images.remove(_img)

        self.imgs_preview = {}

        if self.img_error is not None and name_error in bpy.data.images:
            self.img_error.user_clear()
            bpy.data.images.remove(self.img_error)
            self.img_error = None
        if self.img_downloading is not None and name_downloading in bpy.data.images:
            self.img_downloading.user_clear()
            bpy.data.images.remove(self.img_downloading)
            self.img_downloading = None

    def next_index(self) -> None:
        """Select the next preview image."""

        self.idx_preview = (self.idx_preview + 1) % self.num_previews

    def previous_index(self) -> None:
        """Select the previous preview image."""

        self.idx_preview = (self.idx_preview - 1) % self.num_previews

    def set_index(self, idx_preview: int) -> None:
        """Select a specific preview image by index."""

        self.idx_preview = idx_preview


# Global state(s), states found in here are only valid between opening
# and closing the popup.
# Definition is down here for the type hinting purposes.
g_states: Dict[int, DetailViewState] = {}


class POLIIGON_OT_detail_view_select(Operator):
    bl_idname = "poliigon.detail_view_select"
    bl_label = ""
    bl_description = _t("Select another large thumb in detail view")
    bl_options = {"INTERNAL"}

    select_preview: IntProperty(min=MODE_SELECT.PREVIOUS, options={"HIDDEN"})  # noqa: F821
    ts: FloatProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        select_preview = properties.select_preview
        if select_preview == MODE_SELECT.NEXT:
            return _t("Next Preview")
        elif select_preview == MODE_SELECT.PREVIOUS:
            return _t("Previous Preview")
        elif 0 <= select_preview < MAX_NUM_PREVIEWS:
            return _t("Select Preview #{0}").format(select_preview)
        else:
            # Not reported, consequences are rather minimal
            cTB.logger.error(
                "Operator detail_view_select, tooltip unknown mode! "
                f"{select_preview}")
        return ""  # Should not happen

    @reporting.handle_operator()
    def execute(self, context):
        global g_states

        state = g_states.get(self.ts, None)
        if state is None:
            return {'CANCELLED'}

        if self.select_preview == MODE_SELECT.NEXT:
            state.next_index()
        elif self.select_preview == MODE_SELECT.PREVIOUS:
            state.previous_index()
        elif 0 <= self.select_preview < MAX_NUM_PREVIEWS:
            state.set_index(self.select_preview)
        else:
            # Not reported, consequences are rather minimal
            cTB.logger.error(
                "Operator detail_view_select, execute unknown mode! "
                f"{self.select_preview}")

        return {'FINISHED'}


class POLIIGON_OT_detail_view(Operator):
    bl_idname = "poliigon.detail_view"
    bl_label = _t("Asset Details")
    bl_description = _t("View larger thumbnails and asset details")
    bl_options = {"INTERNAL"}

    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    resolution_dl: IntProperty(min=300, default=600, options={"HIDDEN"})  # noqa: F821
    ts: FloatProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return cls.bl_description

    @reporting.handle_invoke()
    def invoke(self, context, event):
        global g_states

        self.asset_data = cTB._asset_index.get_asset(self.asset_id)
        if self.asset_data is None:
            msg = (f"Asset ID {self.asset_id} not found in AssetIndex upon "
                   "opening Detail View")
            cTB.logger.error(msg)
            reporting.capture_message("detail-view-no-asset-2", msg, "error")
            return {'CANCELLED'}

        num_previews = len(self.asset_data.cloudflare_thumb_urls)

        self.ts = time.monotonic()

        state = DetailViewState(num_previews, self.ts, context)
        partial_periodic_redraw = partial(
            t_periodic_redraw,
            ts=self.ts,
            asset_data=self.asset_data)
        state.partial_periodic_redraw = partial_periodic_redraw

        g_states[self.ts] = state

        self._get_all_thumbs(num_previews)

        cTB.signal_view_screen("large_preview")

        return context.window_manager.invoke_props_dialog(self, width=450)

    def _start_timer_periodic_redraw(self, asset_data: AssetData) -> None:
        """Starts a timer to periodically upate/redraw the popup.

        For longer running actions like asset download, we want regular popup
        updates, so it can display progress bars and switch to different
        buttons after the action has finished. Therefore we start a timer,
        which will do the trick and which will auto-disarm itself, once the
        asset's state signals no more ongoing actions in background.
        """

        global g_states

        state = g_states.get(self.ts, None)
        if state is None:
            return
        if bpy.app.timers.is_registered(state.partial_periodic_redraw):
            return

        bpy.app.timers.register(
            state.partial_periodic_redraw,
            first_interval=0,
            persistent=False)

    def _callback_thumb_done(self, event: Event, job: ApiJob) -> None:
        """DCC specific finalization of 'download thumb' job."""

        event.set()

    def _load_thumb_image(
        self,
        idx_preview: int,
        path_preview: str,
        img_error: bpy.types.Image
    ) -> bpy.types.Image:
        """Loads in a preview image, returning the img_error upon failure."""

        theme = bpy.context.preferences.themes[0]
        color_bg = theme.user_interface.wcol_menu_back.inner

        img_preview = load_image(
            f"POLIIGON_PREVIEW_{self.ts:.4f}_{idx_preview}",
            path_preview,
            # With some (NOT all) preview images, setting colorspace fails
            do_set_colorspace=False,
            # Index 0 preview (identical to the thumbnail image) comes with an
            # alpha channel, confusing our template_icon widget. So, we'll replace
            # the transparent parts with a new background color.
            do_remove_alpha=idx_preview == 0,
            color_bg=color_bg,
            force=True)
        if img_preview is None:
            img_preview = img_error
        return img_preview

    def _get_thumb(
        self,
        state: DetailViewState,
        events_download: List[Event],
        idx_preview: Optional[int] = None,
    ) -> None:
        """Either loads a large preview (if file exists) or
        starts a job to download it.
        """

        if idx_preview is None:
            idx_preview = state.idx_preview

        path_preview, url_preview = cTB._asset_index.get_cf_thumbnail_info(
            self.asset_id, self.resolution_dl, idx_preview)
        if path_preview is None:
            msg = (
                f"Asset ID {self.asset_id}: "
                f"Encountered preview index {idx_preview} returning no path")
            cTB.logger.warning(msg)
            reporting.capture_message("detail-view-thumb-index", msg, "error")
            state.set_error_image(idx_preview)
            return

        if os.path.isfile(path_preview):
            img_preview = self._load_thumb_image(
                idx_preview, path_preview, state.img_error)

            img_preview.user_clear()

            state.set_image(idx_preview, img_preview)
        else:
            ev_download = Event()

            events_download.append((idx_preview, path_preview, ev_download))

            partial_callback_done = partial(
                self._callback_thumb_done,
                event=ev_download)

            cTB.api_rc.add_job_download_thumb(
                asset_id=self.asset_id,
                url=url_preview,
                path=path_preview,
                idx_thumb=idx_preview,
                callback_done=partial_callback_done
            )

    def _await_all_thumb_downloads(
        self,
        state: DetailViewState,
        events_download: List[Event]
    ) -> None:
        """Waits dor all events in events_download and loads thumbs
        which finished download.
        """

        for _idx_preview, _path_preview, _ev_download in events_download:
            is_event_set = _ev_download.wait(TIMEOUT_THUMB_DOWNLOAD)
            if not is_event_set:
                msg = (f"Thumb download timeout ({self.asset_id}, "
                       f"{_idx_preview})!")
                reporting.capture_message(
                    "detail-view-thumb-timeout", msg, "error")
                # Continue nevertheless, if the file appeared on disc we are
                # still fine

            if os.path.isfile(_path_preview):
                img_preview = self._load_thumb_image(
                    _idx_preview, _path_preview, state.img_error)
                img_preview.user_clear()
                state.imgs_preview[_idx_preview] = img_preview
            else:
                state.set_error_image(_idx_preview)

    def _get_all_thumbs(self, num_previews: int) -> None:
        """Requests all large previews for the asset."""

        global g_state

        state = g_states.get(self.ts, None)
        if state is None:
            return

        events_download = []
        for _idx_preview in range(num_previews):
            self._get_thumb(state, events_download, _idx_preview)

        self._await_all_thumb_downloads(state, events_download)

    def _add_preview_image(
            self, layout: bpy.types.UILayout, idx_selected: int) -> None:
        """Adds the actual preview image to the popup dialog."""

        global g_states

        row_image = layout.row()
        col_image = row_image.column()
        col_image.scale_y = 1.125

        state = g_states.get(self.ts, None)
        if state is None:
            return

        imgs_preview = state.imgs_preview
        if idx_selected in imgs_preview and imgs_preview[idx_selected] is not None:
            id_icon = imgs_preview[idx_selected].preview.icon_id
        else:
            id_icon = state.img_error.preview.icon_id

        col_image.template_icon(
            icon_value=id_icon,
            scale=18.0)

    def _add_select_previous_button(self, layout: bpy.types.UILayout) -> None:
        """Adds the button to select the previous preview image to the popup
        dialog.
        """

        col_btn_prev = layout.column()
        col_btn_prev.alignment = "LEFT"
        op = col_btn_prev.operator(
            "poliigon.detail_view_select",
            text="",
            icon="TRIA_LEFT",
            emboss=False)
        op.select_preview = int(MODE_SELECT.PREVIOUS)
        op.ts = self.ts

    def _add_select_next_button(self, layout: bpy.types.UILayout) -> None:
        """Adds the button to select the next preview image to the popup
        dialog.
        """

        col_btn_next = layout.column()
        col_btn_next.alignment = "RIGHT"
        op = col_btn_next.operator(
            "poliigon.detail_view_select",
            text="",
            icon="TRIA_RIGHT",
            emboss=False)
        op.select_preview = int(MODE_SELECT.NEXT)
        op.ts = self.ts

    def _add_select_index_buttons(
            self, layout: bpy.types.UILayout, idx_selected: int) -> None:
        """Adds buttons to select a specific preview image to the popup
        dialog.
        """

        global g_states

        state = g_states.get(self.ts, None)
        if state is None:
            return
        for _idx in range(state.num_previews):
            if _idx == idx_selected:
                icon = "RADIOBUT_ON"
            else:
                icon = "RADIOBUT_OFF"
            op = layout.operator(
                "poliigon.detail_view_select",
                text="",
                icon=icon,
                emboss=False,
                depress=_idx == idx_selected)
            op.select_preview = _idx
            op.ts = self.ts

    def _add_selection_buttons(
            self, layout: bpy.types.UILayout, idx_selected: int) -> None:
        """Adds a row with various buttons to select the preview image to
        display.
        """

        row_select = layout.row(align=True)
        self._add_select_previous_button(row_select)
        row_select.separator()
        row_select.label(text="")  # Needed for dot buttons centered
        self._add_select_index_buttons(row_select, idx_selected)
        row_select.label(text="")  # Needed for dot buttons centered
        row_select.separator()
        self._add_select_next_button(row_select)

    def _add_meta_data_asset_name(self, layout: bpy.types.UILayout) -> None:
        """Adds labels with the asset name to the popup dialog."""

        col_asset_name = layout.column()
        col_asset_name.scale_y = 0.8
        col_asset_name.label(text=self.asset_data.display_name)
        col_asset_name.label(text=self.asset_data.asset_name)

    def _add_action_buttons(self, layout: bpy.types.UILayout) -> None:
        """Adds row with 'action buttons' to the popup dialog."""

        # TODO(Andreas): No need to comment on this function. It currently is
        #                a replica of what dlg_assets is doing.
        #                Possible backlog task: Would like to restructure the
        #                button implementation in dlg_assets (maybe introducing
        #                a few helper functions in addon-core) so it can be
        #                easily re-used here.

        asset_data = self.asset_data
        api_convention = asset_data.get_convention()
        asset_id = asset_data.asset_id
        asset_type = asset_data.asset_type
        asset_type_data = asset_data.get_type_data()
        is_tex = asset_type == AssetType.TEXTURE
        is_purchased = asset_data.is_purchased
        is_local = asset_data.is_local
        is_downloaded = _asset_is_local(cTB, asset_data)
        is_unlimited = cTB.is_unlimited_user()
        is_selection = len(bpy.context.selected_objects) > 0
        is_purchase_in_progress = asset_data.state.purchase.is_in_progress()
        is_cancelled = asset_data.state.dl.is_cancelled()
        is_download_in_progress = asset_data.state.dl.is_in_progress()

        thumb_size_factor = THUMB_SIZE_FACTOR[cTB.settings["thumbsize"]]
        thumb_width = _determine_thumb_width(cTB, thumb_size_factor)

        size_pref = cTB.get_pref_size(asset_type)
        size_default = asset_type_data.get_size(
            size_pref,
            local_only=is_downloaded,
            addon_convention=cTB._asset_index.addon_convention,
            local_convention=self.asset_data.local_convention)
        sizes_in_scene, size_default = _determine_in_scene_sizes(
            cTB, asset_data, size_default)

        size_default = asset_data.get_current_size(
            size_default,
            local_only=is_local,
            addon_convention=cTB.addon_convention)

        if is_tex and api_convention >= 1:
            map_prefs = cTB.user.map_preferences
            is_downloaded = asset_type_data.all_expected_maps_local(
                map_prefs, size=size_default)

        is_in_progress = is_purchase_in_progress or is_cancelled or is_download_in_progress
        have_folder_button = not is_in_progress and is_downloaded

        row_action_buttons = layout.row()

        if have_folder_button:
            split_action_buttons = row_action_buttons.split(factor=0.3333)
            row_main_action = split_action_buttons.row(align=True)
            split_other_buttons = split_action_buttons.split(factor=0.5)
            row_folder_button = split_other_buttons.row()
            row_link_button = split_other_buttons.row()
        else:
            split_action_buttons = row_action_buttons.split(factor=0.5)
            row_main_action = split_action_buttons.row(align=True)
            row_link_button = split_action_buttons.row()

        if is_purchase_in_progress:
            _draw_thumb_state_asset_purchasing(row_main_action, asset_data)
            self._start_timer_periodic_redraw(asset_data)
        elif is_cancelled:
            _draw_thumb_state_cancelling_download(row_main_action, asset_data)
            self._start_timer_periodic_redraw(asset_data)
        elif is_download_in_progress:
            _draw_thumb_state_asset_downloading(
                row_main_action, asset_data, thumb_width)
            self._start_timer_periodic_redraw(asset_data)

        elif is_purchased or is_unlimited:
            if is_downloaded:
                if asset_type == AssetType.MODEL:
                    _draw_button_model_local(
                        cTB, row_main_action, asset_data, error=None)
                elif asset_type == AssetType.TEXTURE:
                    _draw_button_texture_local(
                        cTB,
                        row_main_action,
                        asset_data,
                        error=None,
                        sizes_in_scene=sizes_in_scene,
                        size_default=size_default,
                        is_selection=is_selection)
                elif asset_type == AssetType.HDRI:
                    _draw_button_hdri_local(
                        cTB,
                        row_main_action,
                        asset_data,
                        error=None,
                        size_default=size_default)
            else:
                if not check_convention(asset_data):
                    _draw_button_unsupported_convention(row_main_action)
                else:
                    _draw_button_download(
                        cTB,
                        row_main_action, asset_data,
                        error=None,
                        size_default=size_default)
        else:
            if not check_convention(asset_data):
                _draw_button_unsupported_convention(row_main_action)
            else:
                _draw_button_purchase(
                    cTB,
                    row_main_action,
                    asset_data,
                    error=None,
                    size_default=size_default)

        have_quickmenu = is_downloaded or check_convention(
            asset_data, is_local)
        if have_quickmenu and not is_in_progress:
            _draw_button_quick_menu(
                row_main_action, asset_data, hide_detail_view=True)

        if have_folder_button:
            op = row_folder_button.operator(
                "poliigon.poliigon_folder",
                text=_t("Open folder location"),
                icon="FILE_FOLDER"
            )
            op.asset_id = asset_id

        op = row_link_button.operator(
            "poliigon.poliigon_link",
            text=_t("View online"),
            icon_value=cTB.ui_icons["ICON_poliigon"].icon_id,
        )
        op.mode = str(asset_id)
        op.tooltip = _t("View on Poliigon.com")

    def _add_meta_data_details_map_types(
        self,
        col_key: bpy.types.UILayout,
        col_value: bpy.types.UILayout,
        key: str,
        value: str
    ) -> None:
        """Map type details need to be wrapped into multiple lines."""

        MAX_CHAR_PER_LINE = 40

        map_type_names = value.split(", ")
        num_char_on_line = 0
        lines = []
        line_current = []
        for _map_type_name in map_type_names:
            num_char_type = len(_map_type_name)
            if num_char_on_line + num_char_type < MAX_CHAR_PER_LINE:
                line_current.append(_map_type_name)
                num_char_on_line += num_char_type
            else:
                line = ", ".join(line_current)
                lines.append(line)
                num_char_on_line = num_char_type
                line_current = [_map_type_name]
        if len(line_current) > 0:
            line = ", ".join(line_current)
            lines.append(line)

        for _line in lines:
            col_key.label(text=key)
            col_value.label(text=_line)
            key = ""

    def _add_meta_data_details(self, layout: bpy.types.UILayout) -> None:
        """Adds a 'table' with asset's details to the popup dialog."""

        row_infos = layout.split(factor=0.3)
        col_key = row_infos.column()
        col_key.scale_y = 0.8
        col_value = row_infos.column()
        col_value.scale_y = 0.8

        details = self.asset_data.get_display_details_data()
        for _key, _value in details.items():
            if _key == "Maps":
                self._add_meta_data_details_map_types(
                    col_key, col_value, _key, _value)
            else:
                col_key.label(text=_key)
                col_value.label(text=str(_value))

    def _add_meta_data_section(self, layout: bpy.types.UILayout) -> None:
        """Adds the meta data section to the popup dialog."""

        col_meta_data = layout.column()
        self._add_meta_data_asset_name(col_meta_data)
        col_meta_data.separator()
        self._add_action_buttons(col_meta_data)
        col_meta_data.separator()
        self._add_meta_data_details(col_meta_data)

    @reporting.handle_draw()
    def draw(self, context):
        global g_state

        state = g_states.get(self.ts, None)
        if state is None:
            return

        state.context = context
        state.region_popup = context.region_popup

        col_content = self.layout.column()
        self._add_preview_image(col_content, state.idx_preview)
        self._add_selection_buttons(col_content, state.idx_preview)
        col_content.separator()
        self._add_meta_data_section(col_content)

    def _cleanup(self) -> None:
        """Cleans up behind ourselves. When the popup closes, we need to get
        rid of any timers, we registered and all images we loaded.
        """

        global g_states

        state = g_states.get(self.ts, None)
        if state is None:
            return

        if bpy.app.timers.is_registered(state.partial_periodic_redraw):
            bpy.app.timers.unregister(state.partial_periodic_redraw)
        for _partial in state.partials_load_and_redraw:
            if bpy.app.timers.is_registered(_partial):
                bpy.app.timers.unregister(_partial)

        # Important, so state instances get actuelly free'd
        self.partial_periodic_redraw = None
        self.partials_load_and_redraw = []

        del g_states[self.ts]

    @reporting.handle_operator()
    def execute(self, context):
        """The real action happens in invoke() and draw(), execute() only runs
        after user clicks 'Ok' button, then we need to clean up here.
        """

        self._cleanup()
        return {'FINISHED'}

    def cancel(self, context):
        """Upon user clicking 'Cancel' or popup loosing focus we'll cleanup
        here.
        """

        self._cleanup()


@persistent
def t_periodic_redraw(
    ts: float,
    asset_data: AssetData
) -> Optional[float]:
    """Timer function to redraw/update the popup dialog.

    Based on asset's state, the timer will either be scheduled to fire again or
    auto-disarm itself, if asset's state shows no more ongoing actions like for
    example 'downloading'.
    """

    global g_states

    state = g_states.get(ts, None)
    if state is None:
        return None

    region_popup = state.region_popup

    next_update_s = None  # Auto-disarm, if none of the states below
    is_purchasing = asset_data.state.purchase.is_in_progress()
    is_downloading = asset_data.state.dl.is_in_progress()
    is_cancelling = asset_data.state.dl.is_cancelled()
    if is_purchasing or is_downloading or is_cancelling:
        next_update_s = 0.250
    has_region_popup = region_popup is not None
    if has_region_popup and region_popup.type == "TEMPORARY":
        region_popup.tag_refresh_ui()
    return next_update_s
