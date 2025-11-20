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

from typing import Tuple
import os

import bpy

from .modules.poliigon_core.multilingual import _t
from .dialogs.utils_dlg import (
    get_ui_scale,
    wrapped_label)
from .constants import (
    ASSET_ID_ALL,
    HDRI_RESOLUTIONS)
from .toolbox import get_context
from .asset_browser.asset_browser_ui import build_asset_browser_progress
from .preferences_map_prefs import add_map_pref_rows
from . import reporting

# TODO(Andreas): see also THUMB_SIZES in dlg_assets.py
THUMB_SIZES = ["Tiny", "Small", "Medium", "Large", "Huge"]


def update_optin_from_settings():
    if cTB is None:
        return
    settings_optin = cTB.settings_config.getboolean("logging",
                                                    "reporting_opt_in",
                                                    fallback=None)
    prefs = bpy.context.preferences.addons.get(__spec__.parent, None)
    prefs.preferences.reporting_opt_in = settings_optin


def optin_update(self, context) -> None:
    """Update the optin settings."""

    # __spec__.parent since __package__ got deprecated
    prefs = bpy.context.preferences.addons.get(__spec__.parent, None)
    reporting.set_optin(prefs.preferences.reporting_opt_in)
    if cTB is None:
        return
    str_pref = "true" if prefs.preferences.reporting_opt_in else "false"
    cTB.settings_config.set("logging", "reporting_opt_in", str_pref)
    cTB._settings.save_settings()


def verbose_update(self, context) -> None:
    """Clear out print cache, which could prevent new, near-term prinouts."""

    # TODO(Andreas): Need to see, if we need to re-introduce a cached print
    # cTB._cached_print.cache_clear()
    pass


def get_preferences_width(context, subtract_offset: bool = True) -> float:
    """Returns width of user preferences dialog's main region/draw area"""

    width_win = 1
    for area in context.screen.areas:
        if area.type != "PREFERENCES":
            continue

        for region in area.regions:
            if region.type == "WINDOW":
                width_win = region.width
                break
        break

    if subtract_offset:
        width_win = width_win - 25 - 20

    width_win = max(width_win, 1)  # To avoid div by zero errors
    return width_win


class PoliigonPreferences(bpy.types.AddonPreferences):
    # __spec__.parent since __package__ got deprecated
    bl_idname = __spec__.parent
    scriptdir = bpy.path.abspath(os.path.dirname(__file__))

    reporting_opt_in: bpy.props.BoolProperty(
        name=_t("Share addon errors/usage"),  # noqa: F722
        default=True,
        description=_t(
            "Automatically share addon activity and any encountered errors "  # noqa: F722
            "with developers to help improve the product"
        ),
        update=optin_update
    )
    verbose_logs: bpy.props.BoolProperty(
        name=_t("Verbose logging to console"),  # noqa: F722
        default=True,
        description=_t(
            "Print out more verbose errors to the console, useful for "  # noqa: F722
            "troubleshooting issues"
        ),
        update=verbose_update
    )
    _dispopts = [
        ("NORMAL",
         _t("Normal Only"),
         _t("Use the Normal Map for surface details")),
        ("BUMP",
         _t("Bump Only"),
         _t("Use the displacement map for surface details without displacement")),
        ("DISP",
         _t("Displacement and Bump"),
         _t("Use the displacement map for surface details and physical displacement"))
        # Not offering MICRO as a default option, only be case by case usage.
    ]
    mode_disp: bpy.props.EnumProperty(
        name=_t("Disp. Method"),  # noqa: F821
        items=_dispopts,
        default="NORMAL"  # noqa: F821
    )
    show_updater_prefs: bpy.props.BoolProperty(
        name=_t("Show/hide updater preferences"),  # noqa: F722
        default=True,
        description=_t("Show/hide updater-related preferences")  # noqa: F722
    )
    auto_check_update: bpy.props.BoolProperty(
        name=_t("Auto-check for update (daily)"),  # noqa: F722
        default=True,
        description=_t("Check for an addon update once per day,\n"  # noqa: F722
                       "only runs if the addon is in use.")
    )
    asset_browser_library_name: bpy.props.StringProperty(
        name=_t("Library Name"),  # noqa: F722
        default="Polligon Library",  # noqa: F722
        description=_t("Name of the library in Blender's Asset Browser")  # noqa: F722
    )
    _asset_browser_mode_items = [
        ("Disabled",
         _t("Disabled"),
         _t("No automatic synchronization")),
        ("On Download",
         _t("On Download"),
         _t("Synchronize after download")),
        ("Automatic",
         _t("Automatic"),
         _t("Synchronize all local assets on startup"))]
    asset_browser_mode: bpy.props.EnumProperty(
        name=_t("Synchronization Mode"),  # noqa: F722
        default="Disabled",  # noqa: F821
        items=_asset_browser_mode_items,
        description=_t(
            "Depending on this mode P4B will automatically\n"  # noqa: F722
            "synchronize local assets with Blender's Asset Browser.")
    )
    _any_owned_brushes_items = [
        ("undecided",
         _t("Undecided"),
         _t("Still fetching pruchased assets info")),
        ("no_brushes",
         _t("No Brushes"),
         _t("User owns no Brush assets")),
        ("owned_brushes",
         _t("Owned Brushes"),
         _t("User owns Brush assets"))]
    any_owned_brushes: bpy.props.EnumProperty(
        name=_t("Any Owned Brushes"),  # noqa: F722
        default="undecided",  # noqa: F821
        items=_any_owned_brushes_items,
        options={'HIDDEN'},  # noqa: F821
        description=_t(
            "Depending on this value, brush related setings will be "  # noqa: F722
            "hidden.")
    )

    def _draw_prefs_section_header(self,
                                   text: str,
                                   param: str,
                                   tooltip_hide: str,
                                   tooltip_show: str,
                                   have_column: bool = False
                                   ) -> Tuple[bpy.types.UILayout,
                                              bpy.types.UILayout]:
        if param not in cTB.settings:
            msg = f"Section header {param} not found in settings"
            reporting.capture_message("settings_error", msg, "error")

        is_open = cTB.settings.get(param, True)
        icon = "DISCLOSURE_TRI_DOWN" if is_open else "DISCLOSURE_TRI_RIGHT"

        if have_column:
            col = self.layout.column(align=1)
            box = col.box()
        else:
            col = None
            box = self.layout.box()

        op = box.operator(
            "poliigon.poliigon_setting",
            text=text,
            icon=icon,
            emboss=0,
        )
        op.mode = param
        if cTB.settings[param]:
            op.tooltip = tooltip_hide
        else:
            op.tooltip = tooltip_show

        return box, col

    def _draw_prefs_section_header_prop(self,
                                        text: str,
                                        prop_name: str,
                                        do_show: bool,
                                        have_column: bool = False
                                        ) -> Tuple[bpy.types.UILayout,
                                                   bpy.types.UILayout]:
        icon = "DISCLOSURE_TRI_DOWN" if do_show else "DISCLOSURE_TRI_RIGHT"

        if have_column:
            col = self.layout.column(align=1)
            box = col.box()
        else:
            col = None
            box = self.layout.box()

        box.prop(self, prop_name, emboss=False, icon=icon, text=text)

        return box, col

    def _draw_library_prefs(self) -> bool:
        path_library_primary = cTB.settings_config.get(
            "library", "primary", fallback=None)

        box = self.layout.box().column()
        col = box.column()

        col.label(text=_t("Library :"))

        op = col.operator(
            "poliigon.poliigon_library",
            icon="FILE_FOLDER",
            text=path_library_primary,
        )
        op.mode = "update_library"
        op.directory = path_library_primary
        op.tooltip = _t("Set Default Poliigon Library Directory")

        if not os.path.exists(path_library_primary):
            col.label(text=_t("(Poliigon Library not set.)"), icon="ERROR")
            return False

        col.separator()
        return True

    def _draw_additional_dirs_prefs(self) -> None:
        additional_dirs = cTB.get_library_paths()[1:]

        text = _t("{0} Additional Directories").format(len(additional_dirs))
        box, _ = self._draw_prefs_section_header(
            text=text,
            param="show_add_dir",
            tooltip_hide=_t("Hide Additional Directories"),
            tooltip_show=_t("Show Additional Directories"))
        if not cTB.settings["show_add_dir"]:
            return

        col = box.column()

        for directory in additional_dirs:
            row = col.row(align=1)
            check = directory not in cTB.settings["disabled_dirs"]
            op = row.operator(
                "poliigon.poliigon_setting",
                text="",
                depress=check,
                emboss=False,
                icon="CHECKBOX_HLT" if check else "CHECKBOX_DEHLT",
            )
            op.mode = f"disable_dir_{directory}"
            if check:
                op.tooltip = _t("Disable Additional Directory")
            else:
                op.tooltip = _t("Enable Additional Directory")

            row.label(text=directory)

            op = row.operator("poliigon.poliigon_setting", text="", icon="TRASH")
            op.mode = f"del_dir_{directory}"
            op.tooltip = _t("Remove Additional Directory")

            col.separator()

        row = col.row(align=1)
        op = row.operator(
            "poliigon.poliigon_directory",
            text=_t("Add Additional Directory"),
            icon="ADD",
        )
        path_library_primary = cTB.settings_config.get(
            "library", "primary", fallback=None)
        op.directory = path_library_primary
        op.tooltip = _t("Add Additional Asset Directory")

        col.separator()

    def _draw_asset_browser_prefs(self, context) -> None:
        """Draws preferencees related to Blender's Asset Browser."""

        if not cTB.user_legacy_own_assets():
            return

        if bpy.app.version < (3, 0):
            return  # Not available before blender 3.0.

        layout = self.layout
        col_asset_browser = layout.column(align=True)
        box = col_asset_browser.box()

        op = box.operator(
            "poliigon.poliigon_setting",
            text=_t("Asset Browser Preferences"),
            icon="DISCLOSURE_TRI_DOWN"
            if cTB.settings["show_asset_browser_prefs"]
            else "DISCLOSURE_TRI_RIGHT",
            emboss=0,
        )
        op.mode = "show_asset_browser_prefs"
        if cTB.settings["show_asset_browser_prefs"]:
            op.tooltip = _t("Hide Asset Browser Preferences")
        else:
            op.tooltip = _t("Show Asset Browser Preferences")

        if cTB.settings["show_asset_browser_prefs"]:
            name_is_set = cTB.prefs.asset_browser_library_name != ""

            path_library_primary = cTB.settings_config.get(
                "library", "primary", fallback=None)
            directory_is_set = path_library_primary not in [None, ""]
            sync_options_enabled = name_is_set and directory_is_set

            col = box.column()

            width = get_preferences_width(context, subtract_offset=False)
            label = _t(
                "This addon can generate blend files for the Blender Asset "
                "Browser (except for Brushes). You can then use the Poliigon "
                "Library in the Asset Browser.")
            wrapped_label(cTB, width - 26 * get_ui_scale(cTB), label, col)

            col.separator()

            col.prop(self, "asset_browser_library_name")

            if cTB._env.env_name and "dev" in cTB._env.env_name.lower():
                row_mode = col.row(align=True)
                row_mode.prop(self, "asset_browser_mode")
                row_mode.enabled = sync_options_enabled

            col.separator()

            row_manual_sync = col.row(align=True)
            row_manual_sync.label(text=_t("Manually Start Synchronization:"))

            if cTB.num_asset_browser_jobs == 0 and not cTB.lock_client_start.locked():
                op_manual_sync = row_manual_sync.operator(
                    "poliigon.update_asset_browser",
                    text=_t("Synchronize Local Assets"),
                    emboss=True,
                    icon="FILE_REFRESH",
                )
                op_manual_sync.asset_id = ASSET_ID_ALL
                row_manual_sync.enabled = sync_options_enabled
            else:
                build_asset_browser_progress(
                    None, context, row_manual_sync,
                    show_label=False, show_second_line=True)

            col.separator()

    def _draw_display_prefs(self) -> None:
        box, _ = self._draw_prefs_section_header(
            text=_t("Display Preferences"),
            param="show_display_prefs",
            tooltip_hide=_t("Hide Display Preferences"),
            tooltip_show=_t("Show Display Preferences"))
        if not cTB.settings["show_display_prefs"]:
            return

        col = box.column()

        col.label(text=_t("Thumbnail Size :"))
        row = col.row(align=False)
        for size in THUMB_SIZES:
            op = row.operator(
                "poliigon.poliigon_setting",
                text=size,
                depress=cTB.settings["thumbsize"] == size,
            )
            op.mode = f"thumbsize@{size}"
            op.tooltip = _t("Show {0} Thumbnails").format(size)

        col.separator()

        col.label(text=_t("Assets Per Page :"))
        row = col.row(align=False)
        for num_thumbs in [6, 8, 10, 20]:
            op = row.operator(
                "poliigon.poliigon_setting",
                text=str(num_thumbs),
                depress=cTB.settings["page"] == num_thumbs,
            )
            op.mode = f"page@{num_thumbs}"
            op.tooltip = _t("Show {0} Assets per Page").format(num_thumbs)

        row = col.row()
        row.scale_y = 0.25
        row.label(text="")
        row = col.row()
        split = row.split(factor=0.76)
        col_left = split.column()
        col_left.label(
            text=_t(
                "Press Refresh Data to reload icons and reset addon data:"))
        col_right = split.column()
        col_right.operator("poliigon.refresh_data", icon="FILE_REFRESH")

        col.separator()

    def _draw_download_prefs_texture_resolution(
            self, box, prefs_width) -> None:
        col = box.column()

        col.label(text=_t("Default Texture Resolution :"))
        grid = col.grid_flow(
            row_major=1,
            columns=int((prefs_width - 20) / 40),
            even_columns=1,
            even_rows=1,
            align=0,
        )
        for size in ["1K", "2K", "3K", "4K", "6K", "8K", "16K"]:
            op = grid.operator(
                "poliigon.poliigon_setting",
                text=size,
                depress=(size == cTB.settings["res"]),
            )
            op.mode = f"default_res_{size}"
            op.tooltip = _t("The default Resolution to use for Texture Assets")

        col.separator()

    def _draw_download_prefs_map_prefs(
            self, box, prefs_width, context) -> None:
        col = box.column()
        col.label(text=_t("Map Preferences :"))

        width_prefs = get_preferences_width(context, subtract_offset=False)
        width = width_prefs - 50 * get_ui_scale(cTB)

        if cTB.user is None or cTB.user.map_preferences is None:
            col.label(text=_t("Must be logged in to change"), icon="ERROR")
            return

        text_info = _t(
            "Updating your preferences below may require re-downloading some "
            "maps for your local assets before being able to import.")
        wrapped_label(
            cTB,
            width=width,
            text=text_info,
            container=col)

        col.separator()

        op = col.operator(
            "poliigon.reset_map_prefs",
            text=_t("Restore Web Preferences"),
        )
        op.tooltip = _t(
            "Restore Map Preferences chosen in your Poliigon account")

        col.separator()

        add_map_pref_rows(cTB, self, col, context)

        col.separator()

    def _draw_download_prefs_blend_file(self, col) -> None:
        col.separator()

        row = col.row(align=1)
        row.separator()
        if cTB.settings["download_prefer_blend"]:
            icon = "CHECKBOX_HLT"
        else:
            icon = "CHECKBOX_DEHLT"
        op = row.operator(
            "poliigon.poliigon_setting",
            text="",
            depress=cTB.settings["download_prefer_blend"],
            emboss=False,
            icon=icon,
        )
        op.mode = "download_prefer_blend"
        op.tooltip = _t("Prefer .blend file downloads")
        row.label(text=_t(" Download + Import .blend Files (over FBX)"))

        row = col.row(align=1)
        row.separator()
        if cTB.settings["download_link_blend"]:
            icon = "CHECKBOX_HLT"
        else:
            icon = "CHECKBOX_DEHLT"
        op = row.operator(
            "poliigon.poliigon_setting",
            text="",
            depress=cTB.settings["download_link_blend"],
            emboss=False,
            icon=icon,
        )
        op.mode = "download_link_blend"
        op.tooltip = _t("Link blend files instead of appending")
        row.label(text=_t(" Link .blend Files (n/a if any LOD is selected)"))
        row.enabled = cTB.settings["download_prefer_blend"]
        row.separator()

        col.separator()

    def _draw_download_prefs_model_resolution(self, col, prefs_width) -> None:
        col.label(text=_t("Default Model Resolution :"))
        grid = col.grid_flow(
            row_major=1,
            columns=int((prefs_width - 20) / 40),
            even_columns=1,
            even_rows=1,
            align=0,
        )
        for size in ["1K", "2K", "3K", "4K", "6K", "8K", "16K"]:
            vOp = grid.operator(
                "poliigon.poliigon_setting",
                text=size,
                depress=(size == cTB.settings["mres"]),
            )
            vOp.mode = f"default_mres_{size}"
            vOp.tooltip = _t("The default Texture Resolution to use for Model "
                             "Assets")
        col.separator()
        col.separator()

    def _draw_download_prefs_model_lod(self, col, prefs_width) -> None:
        download_lods = cTB.settings["download_lods"]
        row = col.row(align=1)
        row.separator()
        op = row.operator(
            "poliigon.poliigon_setting",
            text="",
            depress=download_lods,
            emboss=False,
            icon="CHECKBOX_HLT" if download_lods else "CHECKBOX_DEHLT",
        )
        op.mode = "download_lods"
        op.tooltip = _t("Download Model LODs")
        row.label(text=_t(" Download Model LODs"))
        row.separator()

        col.separator()

        col_lod = col.column()
        col_lod.enabled = cTB.settings["download_lods"]

        col_lod.label(text=_t("Default LOD to load (NONE imports .blend, "
                              "otherwise loads FBX) :"))
        grid = col_lod.grid_flow(
            row_major=1,
            columns=int((prefs_width - 20) / 50),
            even_columns=1,
            even_rows=1,
            align=0,
        )
        lod_list = ["NONE", "LOD0", "LOD1", "LOD2", "LOD3", "LOD4"]
        for lod in lod_list:
            op = grid.operator(
                "poliigon.poliigon_setting",
                text=lod,
                depress=(lod in cTB.settings["lod"]),
            )
            op.mode = f"default_lod_{lod}"
            op.tooltip = _t("The default LOD to use for Model Assets")

        col.separator()

    def _draw_download_prefs_hdri_resolutions(
            self, col_download, prefs_width) -> None:
        col = col_download.box().column()

        col.separator()

        col.label(text=_t("Default HDRI Lighting Resolution :"))
        grid = col.grid_flow(
            row_major=1,
            columns=int((prefs_width - 20) / 40),
            even_columns=1,
            even_rows=1,
            align=0,
        )
        for size in HDRI_RESOLUTIONS:
            op = grid.operator(
                "poliigon.poliigon_setting",
                text=size,
                depress=(size == cTB.settings["hdri"]),
            )
            op.mode = f"default_hdri_{size}"
            op.tooltip = _t("The default Resolution to use for HDRI Lighting")

        col.separator()

        hdri_use_jpg_bg = cTB.settings["hdri_use_jpg_bg"]

        row = col.row(align=1)
        row.separator()
        op = row.operator(
            "poliigon.poliigon_setting",
            text="",
            depress=hdri_use_jpg_bg,
            emboss=False,
            icon="CHECKBOX_HLT" if hdri_use_jpg_bg else "CHECKBOX_DEHLT",
        )
        op.mode = "hdri_use_jpg_bg"
        op.tooltip = _t(
            "Use different resolution .jpg for display in background")
        row.label(text=_t(" Use JPG for background"))

        col.label(text=_t("Default HDRI Background Resolution :"))
        grid = col.grid_flow(
            row_major=1,
            columns=int((prefs_width - 20) / 40),
            even_columns=1,
            even_rows=1,
            align=0,
        )
        grid.enabled = hdri_use_jpg_bg

        idx_res_light = HDRI_RESOLUTIONS.index(cTB.settings["hdri"])

        _ = grid.column()
        for size in HDRI_RESOLUTIONS[1:]:
            col_button = grid.column()
            col_button.enabled = HDRI_RESOLUTIONS.index(size) > idx_res_light
            op = col_button.operator(
                "poliigon.poliigon_setting",
                text=size,
                depress=(size == cTB.settings["hdrib"]),
            )
            op.mode = f"default_hdrib_{size}"
            op.tooltip = _t(
                "The default Resolution to use for HDRI Backgrounds")

        col.separator()

    def _draw_download_prefs_brush_resolutions(
            self, col_download, prefs_width) -> None:
        return  # TODO(Patrick): Remove other references to self.any_owned_brushes

    def _draw_download_prefs_purchase(self, col_download) -> None:
        if cTB.is_unlimited_user() or cTB.is_free_user():
            return

        col = col_download.box().column()

        col.separator()

        auto_download = cTB.settings["auto_download"]

        col.label(text=_t("Purchase Preferences :"))

        if cTB.is_legacy_limited_user():
            row = col.row(align=1)
            row.separator()
            op = row.operator(
                "poliigon.poliigon_setting",
                text="",
                depress=auto_download,
                emboss=False,
                icon="CHECKBOX_HLT" if auto_download else "CHECKBOX_DEHLT",
            )
            op.mode = "auto_download"
            op.tooltip = _t("Auto-Download Assets on Purchase")
            row.label(text=_t(" Auto-Download Assets on Purchase"))
            row.separator()

        # Note: Blender launched first with a toggle "One Click Purchase",
        # but product-wise later decided a better name to use was inverted
        # logic, "Show Purchase Confirmation". To avoid invalidating the
        # users who already changed their settings, we continue to use the
        # existing back end name, but just invert the displayed logic/icon.
        one_click_purchase = cTB.settings["one_click_purchase"]
        row = col.row(align=1)
        row.separator()
        op = row.operator(
            "poliigon.poliigon_setting",
            text="",
            depress=one_click_purchase,
            emboss=False,
            icon="CHECKBOX_DEHLT" if one_click_purchase else "CHECKBOX_HLT",
        )
        op.mode = "one_click_purchase"
        op.tooltip = _t("Show a confirmation popup when purchasing assets")
        row.label(text=_t(" Show Purchase Confirmation"))
        row.separator()

        col.separator()

    def _draw_download_prefs_import(self, col_download) -> None:
        col = col_download.box().column()

        col.separator()

        col.label(text=_t("Import Preferences :"))

        row = col.row(align=True)
        row.separator()
        row.prop(self, "mode_disp")
        row.separator()

        row = col.row(align=1)
        row.separator()
        op = row.operator(
            "poliigon.poliigon_setting",
            text="",
            depress=cTB.settings["use_16"],
            emboss=False,
            icon="CHECKBOX_HLT" if cTB.settings["use_16"] else "CHECKBOX_DEHLT",
        )
        op.mode = "use_16"
        op.tooltip = _t("Use 16 bit Maps if available")
        row.label(text=_t(" Use 16 bit Maps"))
        row.separator()

    def _draw_download_prefs(self, context) -> None:
        box, col_download = self._draw_prefs_section_header(
            text=_t("Asset Preferences"),
            param="show_default_prefs",
            tooltip_hide=_t("Hide Download Preferences"),
            tooltip_show=_t("Show Download Preferences"),
            have_column=True
        )
        if not cTB.settings["show_default_prefs"]:
            return

        prefs_width = get_preferences_width(context)

        self._draw_download_prefs_texture_resolution(box, prefs_width)

        self._draw_download_prefs_map_prefs(box, prefs_width, context)

        col = col_download.box().column()
        self._draw_download_prefs_blend_file(col)
        self._draw_download_prefs_model_resolution(col, prefs_width)
        self._draw_download_prefs_model_lod(col, prefs_width)

        self._draw_download_prefs_hdri_resolutions(col_download, prefs_width)

        self._draw_download_prefs_brush_resolutions(col_download, prefs_width)

        self._draw_download_prefs_purchase(col_download)

        self._draw_download_prefs_import(col_download)

    def _draw_updater_prefs(self) -> None:
        if cTB._updater.update_ready:
            text = _t("Update available! {0}").format(
                cTB._updater.update_data.version)
        else:
            text = _t("Addon Updates")
        box, _ = self._draw_prefs_section_header_prop(
            text=text,
            prop_name="show_updater_prefs",
            do_show=self.show_updater_prefs,
            have_column=True)
        if not self.show_updater_prefs:
            return

        col = box.column()

        colrow = col.row(align=True)
        rsplit = colrow.split(factor=0.5)
        subcol = rsplit.column()
        row = subcol.row(align=True)
        row.scale_y = 1.5

        # If already checked for update, show a refresh button (no label)
        if cTB._updater.update_ready is not None:
            row.operator("poliigon.check_update",
                         text="", icon="FILE_REFRESH")

        subcol = row.column(align=True)
        if cTB._updater.is_checking:
            subcol.operator("poliigon.check_update",
                            text=_t("Checking..."))
            subcol.enabled = False
        elif cTB._updater.update_ready is True:
            btn_label = _t("Update ready: {0}").format(
                cTB._updater.update_data.version)
            op = subcol.operator(
                "poliigon.poliigon_link",
                text=btn_label,
            )
            op.mode = cTB._updater.update_data.url
            op.tooltip = _t("Download the new update from website")
        elif cTB._updater.update_ready is False:
            subcol.operator("poliigon.check_update",
                            text=_t("No updates available"))
            subcol.enabled = False
        else:  # cTB._updater.update_ready is None
            subcol.operator("poliigon.check_update",
                            text=_t("Check for update"))

        # Display user preference option for auto update.
        subcol = rsplit.column()
        subcol.scale_y = 0.8
        subcol.prop(self, "auto_check_update")

        # Next row, show time since last check.
        if cTB._updater.last_check:
            time = cTB._updater.last_check
            last_update = _t("Last check: {0}").format(time)
        else:
            last_update = _t("(no recent check for update)")
        subcol.label(text=last_update)

    def _draw_legal_prefs(self) -> None:
        self.layout.prop(self, "verbose_logs")
        self.layout.prop(self, "reporting_opt_in")
        row = self.layout.row(align=True)
        op = row.operator(
            "poliigon.poliigon_link",
            text=_t("Terms & Conditions"),
        )
        op.tooltip = _t("Open Terms & Conditions")
        op.mode = "terms"

        op = row.operator(
            "poliigon.poliigon_link",
            text=_t("Privacy Policy"),
        )
        op.tooltip = _t("Open Privacy Policy")
        op.mode = "privacy"

    def _draw_non_prod_environment(self) -> None:
        if not cTB._env.env_name or "prod" in cTB._env.env_name.lower():
            return

        self.layout.alert = True
        msg = _t("Active environment: {0}, API: {1}").format(
            cTB._env.env_name, cTB._env.api_url)
        self.layout.label(text=msg, icon="ERROR")
        self.layout.alert = False

    def _build_settings(self, context) -> None:
        cTB.logger.debug("f_BuildSettings")

        # flag in request's meta data for Mixpanel
        cTB._api._mp_relevant = True

        library_exists = self._draw_library_prefs()
        if not library_exists:
            return

        self._draw_additional_dirs_prefs()

        self._draw_asset_browser_prefs(context)

        self._draw_display_prefs()

        self._draw_download_prefs(context)

        self._draw_updater_prefs()

        self._draw_legal_prefs()

        self._draw_non_prod_environment()

    @reporting.handle_draw()
    def draw(self, context):
        self._build_settings(context)


cTB = None


def register(addon_version: str) -> None:
    global cTB

    cTB = get_context(addon_version)

    bpy.utils.register_class(PoliigonPreferences)

    update_optin_from_settings()
    optin_update(None, bpy.context)


def unregister() -> None:
    bpy.utils.unregister_class(PoliigonPreferences)
