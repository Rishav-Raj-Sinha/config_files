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

from .asset_browser_operator_import import POLIIGON_OT_asset_browser_import
from .asset_browser_operator_quick_menu import POLIIGON_OT_asset_browser_quick_menu
from .asset_browser_operator_reprocess import POLIIGON_OT_asset_browser_reprocess
from .asset_browser_operator_sync_cancel import POLIIGON_OT_cancel_asset_browser_sync
from .asset_browser_operator_sync_client import POLIIGON_OT_sync_client
from .asset_browser_operator_update import POLIIGON_OT_update_asset_browser


classes = (
    POLIIGON_OT_update_asset_browser,
    POLIIGON_OT_cancel_asset_browser_sync,
    POLIIGON_OT_asset_browser_import,
    POLIIGON_OT_asset_browser_quick_menu,
    POLIIGON_OT_asset_browser_reprocess,
    POLIIGON_OT_sync_client
)


def register(addon_version: str):
    for cls in classes:
        bpy.utils.register_class(cls)
        cls.init_context(addon_version)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
