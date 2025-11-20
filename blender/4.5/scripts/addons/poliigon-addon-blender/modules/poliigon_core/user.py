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

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

from .assets import (MapType)
from .plan_manager import PoliigonSubscription
from .multilingual import _m, _t
from .logger import (DEBUG,  # noqa F401, allowing downstream const usage
                     ERROR,
                     INFO,
                     get_addon_logger,
                     NOT_SET,
                     WARNING)


class PoliigonUserProfiles(Enum):
    USER_HOBBYIST = _m("As a hobbyist")
    USER_STUDENT = _m("As a student")
    USER_PROFESSIONAL = _m("As a professional (individual)")
    USER_STUDIO = _m("As a professional (studio/team)")
    USER_TEACHER = _m("As a teacher")

    def to_ui_display(self) -> Optional[str]:
        if self == self.USER_STUDENT:
            return _t("Student")
        elif self == self.USER_TEACHER:
            return _t("Teacher")
        elif self == self.USER_HOBBYIST:
            return _t("Hobbyist")
        elif self == self.USER_PROFESSIONAL:
            return _t("Freelancer")
        elif self == self.USER_STUDIO:
            return _t("Team")
        else:
            return None

    @classmethod
    def from_string(cls, use_string: str) -> Optional[Any]:
        try:
            return cls(use_string)
        except ValueError:
            return None

    @classmethod
    def get_list(cls, addon_display: bool = False) -> List[str]:
        if not addon_display:
            return [member.value for member in PoliigonUserProfiles]
        else:
            return [member.to_ui_display() for member in PoliigonUserProfiles]


@dataclass
class MapFormats:
    map_type: MapType
    default: str
    required: bool
    extensions: Dict[str, bool]
    enabled: bool
    selected: Optional[str] = None


class UserDownloadPreferences:
    resolution_options: List[str]
    default_resolution: str
    selected_resolution: Optional[str] = None

    texture_maps: List[MapFormats]

    software_selected: Optional[str] = None
    render_engine_selected: Optional[str] = None

    lod_options: List[str]
    lod_selected: Optional[str] = None

    def __init__(self, res: Dict):
        self.res = res

        self.set_resolution()
        self.set_lods()
        self.set_software()
        self.set_texture_maps()

    def set_resolution(self) -> None:
        resolution_info = self.res.get("default_resolution", {})
        self.resolution_options = resolution_info.get("resolution_options")
        self.default_resolution = resolution_info.get("default")
        self.selected_resolution = resolution_info.get("selected")

    def set_lods(self) -> None:
        lods_info = self.res.get("lods", {})
        self.lod_options = lods_info.get("lod_options")
        self.lod_selected = lods_info.get("selected")

    def set_software(self) -> None:
        software_info = self.res.get("softwares", {})
        for _soft, soft_inf in software_info.items():
            soft_selected = soft_inf.get("selected", None)
            renderer_selected = soft_inf.get("selected_render_engine", None)
            if soft_selected is not None and renderer_selected is not None:
                self.software_selected = soft_selected
                self.render_engine_selected = renderer_selected
                break

    def set_texture_maps(self) -> None:
        self.texture_maps = []
        texture_maps_info = self.res.get("texture_maps", {})
        for _map, map_info in texture_maps_info.items():
            map_type = MapType.from_type_code(_map)
            enabled = map_info.get("selected") is not None
            map_format = MapFormats(map_type=map_type,
                                    default=map_info.get("default"),
                                    enabled=enabled,
                                    selected=map_info.get("selected"),
                                    required=map_info.get("required"),
                                    extensions=map_info.get("formats"))

            self.texture_maps.append(map_format)

    def string_stamp(self) -> str:
        string_stamp = ""
        for _map in self.texture_maps:
            string_stamp += f"{_map.map_type.name}:{str(_map.selected)};"
        return string_stamp

    def get_map_preferences(self, map_type: MapType) -> Optional[MapFormats]:
        for _map in self.texture_maps:
            if _map.map_type.get_effective() == map_type.get_effective():
                return _map
        return None

    def get_all_maps_enabled(self):
        return [_map for _map in self.texture_maps if _map.enabled]


@dataclass
class PoliigonUser:
    """Container object for a user."""

    user_name: str
    user_id: int
    is_student: Optional[bool] = False
    is_teacher: Optional[bool] = False
    credits: Optional[int] = None
    credits_od: Optional[int] = None
    count_assets_owned: Optional[int] = None
    count_assets_downloads: Optional[int] = None
    plan: Optional[PoliigonSubscription] = None
    map_preferences: Optional[UserDownloadPreferences] = None
    user_profile: PoliigonUserProfiles = None
    email_preference: Optional[bool] = None
    primary_3d_software: Optional[str] = None
    # Primary Render engine might be changed/decided in the Dcc side if
    # not yet available (None) in user data;
    primary_rendering_engine: Optional[str] = None
    # Todo(Joao): remove this flag when all addons are using map prefs
    use_preferences_on_download: bool = False
