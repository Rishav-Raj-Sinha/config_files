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


def fill_size_drop_down(addon, asset_id: int) -> List[Tuple[str, str, str]]:
    """Returns a list of enum items with locally available sizes."""

    asset_data = addon._asset_index.get_asset(asset_id)
    asset_type_data = asset_data.get_type_data()

    local_sizes = asset_type_data.get_size_list(
        local_only=True,
        addon_convention=addon._asset_index.addon_convention,
        local_convention=asset_data.get_convention(local=True))
    # Populate dropdown items
    items_size = []
    for size in local_sizes:
        # Tuple: (id, name, description, icon, enum value)
        items_size.append((size, size, size))
    return items_size
