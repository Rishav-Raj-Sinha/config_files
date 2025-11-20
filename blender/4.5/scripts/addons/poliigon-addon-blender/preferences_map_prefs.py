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

from typing import List, Tuple

import bpy

from .modules.poliigon_core.maps import MAP_DESCRIPTIONS, MapType
from .modules.poliigon_core.multilingual import _t
from .toolbox import get_context
from .toolbox_settings import save_settings


def add_map_pref_rows(cTB, pref, col: bpy.types.UILayout, context) -> None:
    if cTB.user is None or cTB.user.map_preferences is None:
        col.label(text=_t("Must be logged in to change"), icon="ERROR")
        return
    user_prefs = cTB.user.map_preferences

    map_pref_props = context.window_manager.polligon_map_prefs
    for _map_format in user_prefs.texture_maps:
        row_map_type = col.row()
        col_gap_left = row_map_type.column()  # noqa: F841
        col_check = row_map_type.column()
        col_check.enabled = not _map_format.required
        col_label = row_map_type.column()
        col_formats = row_map_type.column()
        col_gap_right = row_map_type.column()  # noqa: F841

        map_type_eff = _map_format.map_type.get_effective()
        if map_type_eff == MapType.AO:
            col_check.prop(map_pref_props, "enabled_ao")
            lbl = f"{MAP_DESCRIPTIONS[MapType.AO].display_name} (optional)"
            col_label.label(
                text=lbl)
            col_formats.enabled = map_pref_props.enabled_ao
            col_formats.prop(map_pref_props, "file_format_ao")
        elif map_type_eff == MapType.ALPHAMASKED:
            col_check.prop(map_pref_props, "enabled_alphamasked")
            lbl = f"{MAP_DESCRIPTIONS[MapType.ALPHAMASKED].display_name} (optional)"
            col_label.label(
                text=lbl)
            col_formats.enabled = map_pref_props.enabled_alphamasked
            col_formats.prop(map_pref_props, "file_format_alphamasked")
        elif map_type_eff == MapType.COL:
            col_check.prop(map_pref_props, "enabled_col")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.COL].display_name)
            col_formats.enabled = map_pref_props.enabled_col
            col_formats.prop(map_pref_props, "file_format_col")
        elif map_type_eff == MapType.DISP:
            col_check.prop(map_pref_props, "enabled_displacement")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.DISP].display_name)
            col_formats.enabled = map_pref_props.enabled_displacement
            col_formats.prop(map_pref_props, "file_format_displacement")
        elif map_type_eff == MapType.METALNESS:
            col_check.prop(map_pref_props, "enabled_metallic")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.METALNESS].display_name)
            col_formats.enabled = map_pref_props.enabled_metallic
            col_formats.prop(map_pref_props, "file_format_metallic")
        elif map_type_eff == MapType.MASK:
            col_check.prop(map_pref_props, "enabled_opacity")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.MASK].display_name)
            col_formats.enabled = map_pref_props.enabled_opacity
            col_formats.prop(map_pref_props, "file_format_opacity")
        elif map_type_eff == MapType.NRM:
            col_check.prop(map_pref_props, "enabled_normal")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.NRM].display_name)
            col_formats.enabled = map_pref_props.enabled_normal
            col_formats.prop(map_pref_props, "file_format_normal")
        elif map_type_eff == MapType.NA_ORM:
            col_check.prop(map_pref_props, "enabled_orm")
            lbl = f"{MAP_DESCRIPTIONS[MapType.NA_ORM].display_name} (optional)"
            col_label.label(
                text=lbl)
            col_formats.enabled = map_pref_props.enabled_orm
            col_formats.prop(map_pref_props, "file_format_orm")
        elif map_type_eff == MapType.ROUGHNESS:
            col_check.prop(map_pref_props, "enabled_roughness")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.ROUGHNESS].display_name)
            col_formats.enabled = map_pref_props.enabled_roughness
            col_formats.prop(map_pref_props, "file_format_roughness")
        elif map_type_eff == MapType.SSS:
            col_check.prop(map_pref_props, "enabled_sss")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.SSS].display_name)
            col_formats.enabled = map_pref_props.enabled_sss
            col_formats.prop(map_pref_props, "file_format_sss")
        elif map_type_eff == MapType.FUZZ:
            col_check.prop(map_pref_props, "enabled_fuzz")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.FUZZ].display_name)
            col_formats.enabled = map_pref_props.enabled_fuzz
            col_formats.prop(map_pref_props, "file_format_fuzz")
        elif map_type_eff == MapType.TRANSLUCENCY:
            col_check.prop(map_pref_props, "enabled_translucency")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.TRANSLUCENCY].display_name)
            col_formats.enabled = map_pref_props.enabled_translucency
            col_formats.prop(map_pref_props, "file_format_translucency")
        elif map_type_eff == MapType.TRANSMISSION:
            col_check.prop(map_pref_props, "enabled_transmission")
            col_label.label(
                text=MAP_DESCRIPTIONS[MapType.TRANSMISSION].display_name)
            col_formats.enabled = map_pref_props.enabled_transmission
            col_formats.prop(map_pref_props, "file_format_transmission")


class MapPrefProperties(bpy.types.PropertyGroup):
    global cTB

    @staticmethod
    def _get_file_format_options(
        context,
        map_type: MapType
    ) -> List[Tuple[str, str, str, str, int]]:
        user_prefs = cTB.user.map_preferences
        if user_prefs is None:
            return []

        # Search AO map prefs
        # TODO(Andreas): I don't want to search here!!!
        map_format = user_prefs.get_map_preferences(map_type)
        if map_format is None:
            return [("NONE", "None", "File format: None", "NONE", 0)]

        options = []
        for _idx_ext, (_ext, _avail) in enumerate(map_format.extensions.items()):
            if not _avail:
                continue
            if _ext in ["png", "jpg"]:
                bits = 8
            else:
                bits = 16
            ext_upper = _ext.upper()
            label = f"{ext_upper} ({bits}bit)"
            options.append(
                (_ext, label, f"File format: {ext_upper}", "NONE", _idx_ext))
        return options

    @staticmethod
    def _map_pref_update(
        context,
        map_type: MapType,
        enabled: bool,
        file_format: str
    ) -> None:
        user_prefs = cTB.user.map_preferences
        if user_prefs is None:
            return

        map_format = user_prefs.get_map_preferences(map_type)
        if map_format is None:
            cTB.logger.error(f"No map prefs found for {map_type.name}")
            return

        map_format.enabled = enabled
        if enabled:
            map_format.selected = file_format
        else:
            map_format.selected = "NONE"
        save_settings(cTB)

    def _get_file_format_options_ao(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.AO)

    def _map_pref_update_ao(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_ao
        file_format = map_pref_props.file_format_ao
        self._map_pref_update(context, MapType.AO, enabled, file_format)

    enabled_ao: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.AO].description,
        update=_map_pref_update_ao
    )
    file_format_ao: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_ao,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.AO].description,
        update=_map_pref_update_ao
    )

    def _get_file_format_options_alphamasked(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(
            context, map_type=MapType.ALPHAMASKED)

    def _map_pref_update_alphamasked(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_alphamasked
        file_format = map_pref_props.file_format_alphamasked
        self._map_pref_update(
            context, MapType.ALPHAMASKED, enabled, file_format)

    enabled_alphamasked: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.ALPHAMASKED].description,
        update=_map_pref_update_alphamasked
    )
    file_format_alphamasked: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_alphamasked,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.ALPHAMASKED].description,
        update=_map_pref_update_alphamasked
    )

    def _get_file_format_options_col(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.COL)

    def _map_pref_update_col(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_col
        file_format = map_pref_props.file_format_col
        self._map_pref_update(context, MapType.COL, enabled, file_format)

    enabled_col: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.COL].description,
        update=_map_pref_update_col
    )
    file_format_col: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_col,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.COL].description,
        update=_map_pref_update_col
    )

    def _get_file_format_options_displacement(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.DISP)

    def _map_pref_update_displacement(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_displacement
        file_format = map_pref_props.file_format_displacement
        self._map_pref_update(context, MapType.DISP, enabled, file_format)

    enabled_displacement: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.DISP].description,
        update=_map_pref_update_displacement
    )
    file_format_displacement: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_displacement,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.DISP].description,
        update=_map_pref_update_displacement
    )

    def _get_file_format_options_metallic(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(
            context, map_type=MapType.METALNESS)

    def _map_pref_update_metallic(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_metallic
        file_format = map_pref_props.file_format_metallic
        self._map_pref_update(context, MapType.METALNESS, enabled, file_format)

    enabled_metallic: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.METALNESS].description,
        update=_map_pref_update_metallic
    )
    file_format_metallic: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_metallic,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.METALNESS].description,
        update=_map_pref_update_metallic
    )

    def _get_file_format_options_normal(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.NRM)

    def _map_pref_update_normal(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_normal
        file_format = map_pref_props.file_format_normal
        self._map_pref_update(context, MapType.NRM, enabled, file_format)

    enabled_normal: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.NRM].description,
        update=_map_pref_update_normal
    )
    file_format_normal: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_normal,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.NRM].description,
        update=_map_pref_update_normal
    )

    def _get_file_format_options_opacity(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.MASK)

    def _map_pref_update_opacity(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_opacity
        file_format = map_pref_props.file_format_opacity
        self._map_pref_update(context, MapType.MASK, enabled, file_format)

    enabled_opacity: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.MASK].description,
        update=_map_pref_update_opacity
    )
    file_format_opacity: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_opacity,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.MASK].description,
        update=_map_pref_update_opacity
    )

    def _get_file_format_options_orm(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.NA_ORM)

    def _map_pref_update_orm(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_orm
        file_format = map_pref_props.file_format_orm
        self._map_pref_update(context, MapType.NA_ORM, enabled, file_format)

    enabled_orm: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.NA_ORM].description,
        update=_map_pref_update_orm
    )
    file_format_orm: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_orm,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.NA_ORM].description,
        update=_map_pref_update_orm
    )

    def _get_file_format_options_roughness(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(
            context, map_type=MapType.ROUGHNESS)

    def _map_pref_update_roughness(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_roughness
        file_format = map_pref_props.file_format_roughness
        self._map_pref_update(context, MapType.ROUGHNESS, enabled, file_format)

    enabled_roughness: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.ROUGHNESS].description,
        update=_map_pref_update_roughness
    )
    file_format_roughness: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_roughness,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.ROUGHNESS].description,
        update=_map_pref_update_roughness
    )

    def _get_file_format_options_sss(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.SSS)

    def _map_pref_update_sss(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_sss
        file_format = map_pref_props.file_format_sss
        self._map_pref_update(context, MapType.SSS, enabled, file_format)

    enabled_sss: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.SSS].description,
        update=_map_pref_update_sss
    )
    file_format_sss: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_sss,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.SSS].description,
        update=_map_pref_update_sss
    )

    def _get_file_format_options_fuzz(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(context, map_type=MapType.FUZZ)

    def _map_pref_update_fuzz(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_fuzz
        file_format = map_pref_props.file_format_fuzz
        self._map_pref_update(context, MapType.FUZZ, enabled, file_format)

    enabled_fuzz: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.FUZZ].description,
        update=_map_pref_update_fuzz
    )
    file_format_fuzz: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_fuzz,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.FUZZ].description,
        update=_map_pref_update_fuzz
    )

    def _get_file_format_options_translucency(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(
            context, map_type=MapType.TRANSLUCENCY)

    def _map_pref_update_translucency(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_translucency
        file_format = map_pref_props.file_format_translucency
        self._map_pref_update(
            context, MapType.TRANSLUCENCY, enabled, file_format)

    enabled_translucency: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.TRANSLUCENCY].description,
        update=_map_pref_update_translucency
    )
    file_format_translucency: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_translucency,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.TRANSLUCENCY].description,
        update=_map_pref_update_translucency
    )

    def _get_file_format_options_transmission(
            self, context) -> List[Tuple[str, str, str, str, int]]:
        return self._get_file_format_options(
            context, map_type=MapType.TRANSMISSION)

    def _map_pref_update_transmission(self, context) -> None:
        map_pref_props = context.window_manager.polligon_map_prefs
        enabled = map_pref_props.enabled_transmission
        file_format = map_pref_props.file_format_transmission
        self._map_pref_update(
            context, MapType.TRANSMISSION, enabled, file_format)

    enabled_transmission: bpy.props.BoolProperty(
        name="",  # noqa: F722
        default=True,
        description=MAP_DESCRIPTIONS[MapType.TRANSMISSION].description,
        update=_map_pref_update_transmission
    )
    file_format_transmission: bpy.props.EnumProperty(
        name="",  # noqa: F722
        items=_get_file_format_options_transmission,
        options={'HIDDEN'},  # noqa: F821
        description=MAP_DESCRIPTIONS[MapType.TRANSMISSION].description,
        update=_map_pref_update_transmission
    )


cTB = None


def register(addon_version: str) -> None:
    global cTB

    cTB = get_context(addon_version)

    bpy.utils.register_class(MapPrefProperties)
    bpy.types.WindowManager.polligon_map_prefs = bpy.props.PointerProperty(
        type=MapPrefProperties)


def unregister() -> None:
    del bpy.types.WindowManager.polligon_map_prefs
    bpy.utils.unregister_class(MapPrefProperties)
