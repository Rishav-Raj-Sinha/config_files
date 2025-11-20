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

import bpy

from .modules.poliigon_core.maps import MapType


def update_map_prefs_properties(cTB) -> None:
    user_prefs = cTB.user.map_preferences
    if user_prefs is None:
        return

    map_pref_props = bpy.context.window_manager.polligon_map_prefs
    for _map_format in user_prefs.texture_maps:
        selected_format = _map_format.selected
        enabled = selected_format is not None
        if selected_format is None:
            selected_format = list(_map_format.extensions.keys())[0]
        map_type_eff = _map_format.map_type.get_effective()
        if map_type_eff == MapType.AO:
            map_pref_props.enabled_ao = enabled
            if enabled:
                map_pref_props.file_format_ao = selected_format
        elif map_type_eff == MapType.ALPHAMASKED:
            map_pref_props.enabled_alphamasked = enabled
            if enabled:
                map_pref_props.file_format_alphamasked = selected_format
        elif map_type_eff == MapType.COL:
            map_pref_props.enabled_col = enabled
            if enabled:
                map_pref_props.file_format_col = selected_format
        elif map_type_eff == MapType.DISP:
            map_pref_props.enabled_displacement = enabled
            if enabled:
                map_pref_props.file_format_displacement = selected_format
        elif map_type_eff == MapType.METALNESS:
            map_pref_props.enabled_metallic = enabled
            if enabled:
                map_pref_props.file_format_metallic = selected_format
        elif map_type_eff == MapType.MASK:
            map_pref_props.enabled_opacity = enabled
            if enabled:
                map_pref_props.file_format_opacity = selected_format
        elif map_type_eff == MapType.NRM:
            map_pref_props.enabled_normal = enabled
            if enabled:
                map_pref_props.file_format_normal = selected_format
        elif map_type_eff == MapType.NA_ORM:
            map_pref_props.enabled_orm = enabled
            if enabled:
                map_pref_props.file_format_orm = selected_format
        elif map_type_eff == MapType.ROUGHNESS:
            map_pref_props.enabled_roughness = enabled
            if enabled:
                map_pref_props.file_format_roughness = selected_format
        elif map_type_eff == MapType.SSS:
            map_pref_props.enabled_sss = enabled
            if enabled:
                map_pref_props.file_format_sss = selected_format
        elif map_type_eff == MapType.FUZZ:
            map_pref_props.enabled_fuzz = enabled
            if enabled:
                map_pref_props.file_format_fuzz = selected_format
        elif map_type_eff == MapType.TRANSLUCENCY:
            map_pref_props.enabled_translucency = enabled
            if enabled:
                map_pref_props.file_format_translucency = selected_format
        elif map_type_eff == MapType.TRANSMISSION:
            map_pref_props.enabled_transmission = enabled
            if enabled:
                map_pref_props.file_format_transmission = selected_format
