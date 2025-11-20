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

import bpy.utils.previews

from .operator_active import POLIIGON_OT_active
from .operator_add_converter_node import POLIIGON_OT_add_converter_node
from .operator_apply import POLIIGON_OT_apply
from .operator_cancel_download import POLIIGON_OT_cancel_download
from .operator_category import POLIIGON_OT_category
from .operator_check_update import POLIIGON_OT_check_update
from .operator_close_notification import POLIIGON_OT_close_notification
from .operator_detail import POLIIGON_OT_detail
from .operator_detail_view import (
    POLIIGON_OT_detail_view,
    POLIIGON_OT_detail_view_select)
from .operator_directory import POLIIGON_OT_directory
from .operator_download import (
    POLIIGON_OT_download,
    POLIIGON_OT_popup_purchase)
from .operator_folder import POLIIGON_OT_folder
from .operator_hdri import POLIIGON_OT_hdri
from .operator_library import POLIIGON_OT_library
from .operator_link import POLIIGON_OT_link
from .operator_local_asset_sync import POLIIGON_OT_get_local_asset_sync
from .operator_load_asset_from_list import (
    POLIIGON_OT_load_asset_size_from_list)
from .operator_material import POLIIGON_OT_material
from .operator_model import POLIIGON_OT_model
from .operator_options import POLIIGON_OT_options
from .operator_notice import POLIIGON_OT_notice_operator
from .operator_popup_download_limit import POLIIGON_OT_popup_download_limit
from .operator_popup_message import POLIIGON_OT_popup_message
from .operator_popup_change_plan import (
    POLIIGON_OT_banner_change_plan_dismiss,
    POLIIGON_OT_banner_finish_dismiss,
    POLIIGON_OT_change_plan,
    POLIIGON_OT_popup_change_plan)
from .operator_popups_onboarding import (
    POLIIGON_OT_popup_welcome,
    POLIIGON_OT_popup_first_download)
from .operator_preview import (
    POLIIGON_OT_popup_first_preview,
    POLIIGON_OT_preview)
from .operator_refresh_data import POLIIGON_OT_refresh_data
from .operator_report_error import POLIIGON_OT_report_error
from .operator_reset_map_prefs import POLIIGON_OT_reset_map_prefs
from .operator_show_preferences import POLIIGON_OT_show_preferences
from .operator_select import POLIIGON_OT_select
from .operator_setting import POLIIGON_OT_setting
from .operator_show_quick_menu import POLIIGON_OT_show_quick_menu
from .operator_asset_filter import POLIIGON_OT_asset_filter

try:
    from .operator_unit_test_helper import (
        POLIIGON_OT_unit_test_helper,
        UnitTestProperties)
    HAVE_UNIT_TEST_HELPER = True
except ImportError:
    # It is fine, to not have this. We only use it in uit tests.
    HAVE_UNIT_TEST_HELPER = False
from .operator_unsupported_convention import POLIIGON_OT_unsupported_convention
from .operator_user import POLIIGON_OT_user
from .operator_view_thumbnail import POLIIGON_OT_view_thumbnail
from .operator_onboarding_survey import POLIIGON_OT_onboarding_survey
from ..toolbox import get_context


classes = (
    POLIIGON_OT_active,
    POLIIGON_OT_add_converter_node,
    POLIIGON_OT_apply,
    POLIIGON_OT_banner_change_plan_dismiss,
    POLIIGON_OT_banner_finish_dismiss,
    POLIIGON_OT_cancel_download,
    POLIIGON_OT_category,
    POLIIGON_OT_change_plan,
    POLIIGON_OT_check_update,
    POLIIGON_OT_close_notification,
    POLIIGON_OT_detail,
    POLIIGON_OT_detail_view,
    POLIIGON_OT_detail_view_select,
    POLIIGON_OT_directory,
    POLIIGON_OT_download,
    POLIIGON_OT_folder,
    POLIIGON_OT_get_local_asset_sync,
    POLIIGON_OT_hdri,
    POLIIGON_OT_library,
    POLIIGON_OT_link,
    POLIIGON_OT_load_asset_size_from_list,
    POLIIGON_OT_material,
    POLIIGON_OT_model,
    POLIIGON_OT_notice_operator,
    POLIIGON_OT_onboarding_survey,
    POLIIGON_OT_options,
    POLIIGON_OT_popup_change_plan,
    POLIIGON_OT_popup_download_limit,
    POLIIGON_OT_popup_first_download,
    POLIIGON_OT_popup_first_preview,
    POLIIGON_OT_popup_message,
    POLIIGON_OT_popup_purchase,
    POLIIGON_OT_popup_welcome,
    POLIIGON_OT_preview,
    POLIIGON_OT_refresh_data,
    POLIIGON_OT_report_error,
    POLIIGON_OT_reset_map_prefs,
    POLIIGON_OT_select,
    POLIIGON_OT_setting,
    POLIIGON_OT_show_preferences,
    POLIIGON_OT_show_quick_menu,
    POLIIGON_OT_unsupported_convention,
    POLIIGON_OT_user,
    POLIIGON_OT_view_thumbnail,
    POLIIGON_OT_asset_filter
)


cTB = None


def register_unit_test_helper() -> None:
    global classes

    if not HAVE_UNIT_TEST_HELPER:
        return

    if POLIIGON_OT_unit_test_helper not in classes:
        # Have operator un-/registered like all others
        classes = (*classes, POLIIGON_OT_unit_test_helper)

    bpy.utils.register_class(UnitTestProperties)
    bpy.types.WindowManager.polligon_unit_test = bpy.props.PointerProperty(
        type=UnitTestProperties)


def unregister_unit_test_helper() -> None:
    if not HAVE_UNIT_TEST_HELPER:
        return

    del bpy.types.WindowManager.polligon_unit_test
    bpy.utils.unregister_class(UnitTestProperties)


def register(addon_version: str) -> None:
    global cTB

    register_unit_test_helper()

    cTB = get_context(addon_version)

    for cls in classes:
        bpy.utils.register_class(cls)
        cls.init_context(addon_version)


def unregister() -> None:
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    unregister_unit_test_helper()
