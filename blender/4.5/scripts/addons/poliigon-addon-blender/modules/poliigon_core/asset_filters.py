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

import enum
from typing import List, Optional, Any

from .multilingual import _m, _t
from .user import PoliigonUser
from .api_remote_control_params import (KEY_TAB_ONLINE,
                                        KEY_TAB_MY_ASSETS,
                                        KEY_TAB_RECENT_DOWNLOADS,
                                        KEY_TAB_IMPORTED,
                                        KEY_TAB_LOCAL)


class FilterOptions(enum.Enum):
    ALL_ASSETS = _m("All Assets")
    OWNED_ASSETS = _m("Owned")
    RECENT_DOWNLOADED_ASSETS = _m("Downloads")
    LOCAL_ASSETS = _m("Local")
    IMPORTED_ASSETS = _m("Imported")

    @classmethod
    def get_list(cls):
        return [member for member in FilterOptions]

    @classmethod
    def get_list_for_user(cls, user: PoliigonUser):
        # If a user doesn't own any asset, the owned filter is not shown
        if user.count_assets_owned is not None and user.count_assets_owned == 0:
            return [member for member in FilterOptions
                    if member != cls.OWNED_ASSETS]
        return cls.get_list()

    @classmethod
    def get_string_list(cls, short_string: bool = False) -> List[str]:
        if short_string:
            return [member.map_to_short_value() for member in FilterOptions]
        return [member.value for member in FilterOptions]

    @classmethod
    def get_translated_string_list(cls, short_string: bool = False) -> List[str]:
        if short_string:
            return [_t(member.map_to_short_value()) for member in FilterOptions]
        return [_t(member.value) for member in FilterOptions]

    @classmethod
    def get_from_query(cls, key_query: str) -> Optional[Any]:
        if key_query == KEY_TAB_ONLINE:
            return cls.ALL_ASSETS
        elif key_query == KEY_TAB_MY_ASSETS:
            return cls.OWNED_ASSETS
        elif key_query == KEY_TAB_RECENT_DOWNLOADS:
            return cls.RECENT_DOWNLOADED_ASSETS
        elif key_query == KEY_TAB_LOCAL:
            return cls.LOCAL_ASSETS
        elif key_query == KEY_TAB_IMPORTED:
            return cls.IMPORTED_ASSETS
        else:
            return None

    def map_to_query(self) -> Optional[str]:
        if self == self.ALL_ASSETS:
            return KEY_TAB_ONLINE
        elif self == self.OWNED_ASSETS:
            return KEY_TAB_MY_ASSETS
        elif self == self.RECENT_DOWNLOADED_ASSETS:
            return KEY_TAB_RECENT_DOWNLOADS
        elif self == self.LOCAL_ASSETS:
            return KEY_TAB_LOCAL
        elif self == self.IMPORTED_ASSETS:
            return KEY_TAB_IMPORTED
        else:
            return None

    def map_to_short_value(self) -> Optional[str]:
        if self == self.ALL_ASSETS:
            return _m("All")
        elif self == self.OWNED_ASSETS:
            return self.value
        elif self == self.RECENT_DOWNLOADED_ASSETS:
            return self.value
        elif self == self.LOCAL_ASSETS:
            return self.value
        elif self == self.IMPORTED_ASSETS:
            return self.value
        else:
            return None
