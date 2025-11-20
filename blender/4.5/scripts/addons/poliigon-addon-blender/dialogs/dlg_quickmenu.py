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
import re

import bpy

from ..modules.poliigon_core.api_remote_control_params import (
    CATEGORY_ALL,
    get_search_key,
    KEY_TAB_IMPORTED)
from ..modules.poliigon_core.assets import (
    AssetData,
    AssetType,
    ModelType)
from ..modules.poliigon_core.multilingual import _t
from ..operators.operator_material import set_op_mat_disp_strength
# TODO(SOFT-2421): Deactivated as it seems to have unwanted side effects.
# from .dlg_assets import _draw_button_quick_preview
from .utils_dlg import (
    check_convention,
    get_model_op_details,
    safe_size_apply)
from .. import reporting


def show_quick_menu(
        cTB, asset_data: AssetData, hide_detail_view: bool = False) -> None:
    """Generates the quick options menu next to an asset in the UI grid."""

    asset_type_data = asset_data.get_type_data()
    asset_name = asset_data.asset_name
    asset_id = asset_data.asset_id
    asset_type = asset_data.asset_type
    credits = 0 if asset_data.credits is None else asset_data.credits
    is_free = credits == 0

    # Configuration
    if asset_data.is_purchased:
        # If downloading and already purchased.
        title = _t("Choose Texture Size")
    else:
        title = asset_name

    in_scene = False

    sizes = asset_type_data.get_size_list(local_only=False)
    downloaded = asset_type_data.get_size_list(
        local_only=True,
        addon_convention=cTB._asset_index.addon_convention,
        local_convention=asset_data.get_convention(local=True))

    key = get_search_key(
        tab=KEY_TAB_IMPORTED, search="", category_list=[CATEGORY_ALL])
    query_key = cTB._asset_index._query_key_to_tuple(
        key, chunk=-1, chunk_size=1000000)
    if query_key not in cTB._asset_index.cached_queries:
        # The request is probably still be in flight
        in_scene = False
    elif asset_id in cTB._asset_index.cached_queries[query_key]:
        in_scene = True

    prefer_blend = cTB.settings["download_prefer_blend"]
    link_blend = cTB.link_blend_session

    blend_exists = False
    fbx_exists = False
    if asset_type == AssetType.MODEL:
        blend_exists = asset_type_data.has_mesh(
            model_type=ModelType.BLEND,
            native_only=True,
            renderer=None)  # None is for legacy cycles models w/o engine name
        fbx_exists = asset_type_data.has_mesh(
            model_type=ModelType.FBX,
            native_only=False,
            renderer="")

    any_model = blend_exists or fbx_exists
    is_linked_blend_import = prefer_blend and link_blend and blend_exists

    def _imported_model_extras(
            context, layout: bpy.types.UILayout) -> None:
        area = cTB.settings["area"]
        if area != KEY_TAB_IMPORTED or asset_type != AssetType.MODEL:
            return

        op = layout.operator(
            "poliigon.poliigon_select",
            text=_t("Select"),
            icon="RESTRICT_SELECT_OFF",
        )
        op.mode = "model"
        op.data = asset_name
        op.tooltip = _t("{0}\n(Select all instances)").format(asset_name)

        layout.separator()

    @reporting.handle_draw()
    def draw(self, context):
        layout = self.layout

        _imported_model_extras(context, layout)

        # List the different resolution sizes to provide.
        have_size_opts = asset_data.is_purchased or is_free or cTB.is_unlimited_user()
        have_size_opts &= not asset_data.state.has_error
        if have_size_opts:
            for size in sizes:
                if asset_type == AssetType.TEXTURE:
                    draw_material_sizes(context, size, layout)
                elif asset_type == AssetType.MODEL:
                    draw_model_sizes(context, size, layout)
                elif asset_type == AssetType.HDRI:
                    draw_hdri_sizes(context, size, layout)
                else:
                    label = _t("{0} not implemented yet").format(asset_type)
                    layout.label(text=label)
        # TODO(SOFT-2421): Deactivated as it seems to have unwanted side effects.
        # else:
        #     _draw_button_quick_preview(
        #         cTB,
        #         layout_row=layout,
        #         asset_data=asset_data,
        #         is_selection=True,
        #         have_text_label=True
        #     )
        # If else branch is activated, the following separator needs to be
        # outside if/else
            layout.separator()

        op = layout.operator(
            "poliigon.open_preferences",
            text=_t("Open Import options in Preferences"),
            icon="PREFERENCES",
        )
        op.set_focus = "show_default_prefs"
        layout.separator()

        # Always show view online and high res previews.
        if not hide_detail_view:
            if bpy.app.version >= (4, 2):
                row_detail_view = layout.row()
                row_detail_view.operator_context = 'INVOKE_DEFAULT'
                op = row_detail_view.operator(
                    "poliigon.detail_view",
                    text=_t("View Asset Details"),
                    icon="OUTLINER_OB_IMAGE",
                )
            else:
                op = layout.operator(
                    "poliigon.view_thumbnail",
                    text=_t("View Large Preview"),
                    icon="OUTLINER_OB_IMAGE",
                )
            op.asset_id = asset_data.asset_id

        op = layout.operator(
            "poliigon.poliigon_link",
            text=_t("View online"),
            icon_value=cTB.ui_icons["ICON_poliigon"].icon_id,
        )
        op.mode = str(asset_id)
        op.tooltip = _t("View on Poliigon.com")

        # If already local, support opening the folder location.
        if not downloaded:
            return

        op = layout.operator(
            "poliigon.poliigon_folder",
            text=_t("Open folder location"),
            icon="FILE_FOLDER")
        op.asset_id = asset_id

        # ... and provide option to sync with asset browser
        # TODO(Andreas): Asset Browser integration and AssetIndex
        # in_asset_browser = asset_data.get("in_asset_browser", False)
        in_asset_browser = asset_data.runtime.is_in_asset_browser()
        is_feature_avail = bpy.app.version >= (3, 0)
        missing_local_model = asset_type == AssetType.MODEL and not any_model
        if not is_feature_avail or missing_local_model:
            return

        # Asset browser sync option
        client_starting = cTB.lock_client_start.locked()
        owned = cTB.check_if_purchased(asset_data.asset_id)
        layout.separator()
        row = layout.row()
        msg = _t("Synchronize with Asset Browser")
        if not owned:
            msg = _t("Must own to sync with Asset Browser")
        elif in_asset_browser:
            msg = _t("Already synced with Asset Browser")
        elif client_starting:
            msg = _t("Starting Asset Browser sync...")

        if cTB.user_legacy_own_assets():
            op = row.operator(
                "poliigon.update_asset_browser",
                text=msg,
                icon="FILE_REFRESH")
            op.asset_id = asset_id
            row.enabled = not in_asset_browser and not client_starting and owned

    def draw_material_sizes(
            context, size: str, layout: bpy.types.UILayout) -> None:
        """Draw the menu row for a materials' single resolution size."""

        row = layout.row()
        imported = f"{asset_name}_{size}" in bpy.data.materials

        if asset_data.get_convention() >= 1:
            all_expected_maps_for_size = asset_type_data.all_expected_maps_local(
                cTB.user.map_preferences, size)
        else:
            all_expected_maps_for_size = size in downloaded

        if imported or all_expected_maps_for_size:
            # Action: Load and apply it
            if imported:
                label = _t("{0} (apply material)").format(size)
                tip = _t("Apply {0} Material\n{1}").format(size, asset_name)
            elif context.selected_objects:
                label = _t("{0} (import + apply)").format(size)
                tip = _t("Apply {0} Material\n{1}").format(size, asset_name)
            else:
                label = _t("{0} (import)").format(size)
                tip = _t("Import {0} Material\n{1}").format(size, asset_name)

            # If nothing is selected and this size is already importing,
            # then there's nothing to do.
            if imported and not context.selected_objects:
                row.enabled = False

            op = row.operator(
                "poliigon.poliigon_material",
                text=label,
                icon="TRACKING_REFINE_BACKWARDS")
            # Order is relevant here. vType needs to be set before vSize!
            op.asset_id = asset_id
            safe_size_apply(cTB, op, size, asset_name)
            op.mapping = "UV"
            op.scale = 1.0
            op.use_16bit = cTB.settings["use_16"]
            op.reuse_material = True
            op.tooltip = tip
            set_op_mat_disp_strength(op, asset_name, op.mode_disp)
        else:
            # Action: Download
            # (for free assets this is purchase + implicit auto-download)
            if check_convention(asset_data):
                label = _t("{0} (download)").format(size)
            else:
                label = _t("{size} (Update needed)").format(size)
                row.enabled = False
            op = row.operator(
                "poliigon.poliigon_download",
                text=label,
                icon="IMPORT")
            op.asset_id = asset_id
            safe_size_apply(cTB, op, size, asset_name)
            if is_free and not asset_data.is_purchased:
                op.mode = "purchase"
            else:
                op.mode = "download"
            op.tooltip = _t("Download {0} Material\n{1}").format(
                size, asset_name)

    def draw_model_sizes(
            context, size: str, layout: bpy.types.UILayout) -> None:
        """Draw the menu row for a model's single resolution size."""
        row = layout.row()

        if size in downloaded and any_model:
            # Action: Load and apply it
            lod, label, tip = get_model_op_details(
                cTB, asset_data, size)
            if is_linked_blend_import:
                label += _t(" (disable link .blend to import size)")

            op = row.operator(
                "poliigon.poliigon_model",
                text=label,
                icon="TRACKING_REFINE_BACKWARDS")
            op.asset_id = asset_id
            safe_size_apply(cTB, op, size, asset_name)
            op.tooltip = tip
            op.lod = lod if len(lod) > 0 else "NONE"
            row.enabled = not is_linked_blend_import
        else:
            # Action: Download
            if check_convention(asset_data):
                label = _t("{0} (download)").format(size)
            else:
                label = _t("{0} (Update needed)").format(size)
                row.enabled = False
            op = row.operator(
                "poliigon.poliigon_download",
                text=label,
                icon="IMPORT")
            op.asset_id = asset_id
            safe_size_apply(cTB, op, size, asset_name)
            if is_free and not asset_data.is_purchased:
                op.mode = "purchase"
            else:
                op.mode = "download"
            op.tooltip = _t("Download {0} textures\n{1}").format(
                size, asset_name)

    def draw_hdri_sizes(
            context, size: str, layout: bpy.types.UILayout) -> None:
        """Draw the menu row for an HDRI's single resolution size."""
        row = layout.row()

        size_light = ""
        if in_scene:
            image_name_light = asset_name + "_Light"
            if image_name_light in bpy.data.images.keys():
                path_light = bpy.data.images[image_name_light].filepath
                filename = os.path.basename(path_light)
                match_object = re.search(r"_(\d+K)[_\.]", filename)
                size_light = match_object.group(1) if match_object else cTB.settings["hdri"]

        if size in downloaded:
            # Action: Load and apply it
            if size == size_light:
                label = _t("{0} (apply HDRI)").format(size)
                tip = _t("Apply {0} HDRI\n{1}").format(size, asset_name)
            else:
                label = _t("{0} (import HDRI)").format(size)
                tip = _t("Import {0} HDRI\n{1}").format(size, asset_name)

            op = row.operator(
                "poliigon.poliigon_hdri",
                text=label,
                icon="TRACKING_REFINE_BACKWARDS")
            op.asset_id = asset_id
            safe_size_apply(cTB, op, size, asset_name)
            if cTB.settings["hdri_use_jpg_bg"]:
                size_bg = cTB.settings["hdrib"]
                size_bg = asset_type_data.get_size(
                    size_bg,
                    local_only=True,
                    addon_convention=cTB.addon_convention,
                    local_convention=asset_data.get_convention(local=True))
                op.size_bg = f"{size_bg}_JPG"
            else:
                op.size_bg = f"{size}_EXR"
            op.tooltip = tip

        else:
            # Action: Download
            if check_convention(asset_data):
                label = _t("{0} (download)").format(size)
            else:
                label = _t("{0} (Update needed)").format(size)
                row.enabled = False
            op = row.operator(
                "poliigon.poliigon_download",
                text=label,
                icon="IMPORT")
            op.asset_id = asset_id
            safe_size_apply(cTB, op, size, asset_name)
            if is_free and not asset_data.is_purchased:
                op.mode = "purchase"
            else:
                op.mode = "download"
            op.tooltip = _t("Download {0}\n{1}").format(size, asset_name)

    # Generate the popup menu.
    bpy.context.window_manager.popup_menu(draw, title=title, icon="QUESTION")
