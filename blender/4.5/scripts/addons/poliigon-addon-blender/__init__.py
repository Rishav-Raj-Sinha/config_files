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

bl_info = {
    "name": "Poliigon",
    "author": "Poliigon",
    "version": (1, 14, 1),
    "blender": (2, 83, 0),
    "location": "3D View",
    "description": "Load models, textures, and more from Poliigon and locally",
    "doc_url": "https://help.poliigon.com/en/articles/6342599-poliigon-blender-addon-2023?utm_source=blender&utm_medium=addon",  # noqa: E501
    "tracker_url": "https://help.poliigon.com/en/?utm_source=blender&utm_medium=addon",  # noqa: E501
    "category": "3D View",
}


if "bpy" in locals():
    import importlib
    import bpy

    importlib.reload(dlg_account)  # noqa: F821
    importlib.reload(dlg_add_node_groups)  # noqa: F821
    importlib.reload(dlg_area_categories)  # noqa: F821
    importlib.reload(dlg_area_notifications)  # noqa: F821
    importlib.reload(dlg_area_tabs)  # noqa: F821
    importlib.reload(dlg_assets)  # noqa: F821
    importlib.reload(dlg_init_library)  # noqa: F821
    importlib.reload(dlg_login)  # noqa: F821
    importlib.reload(dlg_popup)  # noqa: F821
    importlib.reload(dlg_quickmenu)  # noqa: F821
    importlib.reload(utils_dlg)  # noqa: F821
    importlib.reload(operator_active)  # noqa: F821
    importlib.reload(operator_add_converter_node)  # noqa: F821
    importlib.reload(operator_apply)  # noqa: F821
    importlib.reload(operator_cancel_download)  # noqa: F821
    importlib.reload(operator_category)  # noqa: F821
    importlib.reload(operator_check_update)  # noqa: F821
    importlib.reload(operator_close_notification)  # noqa: F821
    importlib.reload(operator_detail)  # noqa: F821
    importlib.reload(operator_directory)  # noqa: F821
    importlib.reload(operator_download)  # noqa: F821
    importlib.reload(operator_folder)  # noqa: F821
    importlib.reload(operator_hdri)  # noqa: F821
    importlib.reload(operator_library)  # noqa: F821
    importlib.reload(operator_link)  # noqa: F821
    importlib.reload(operator_local_asset_sync)  # noqa: F821
    importlib.reload(operator_load_asset_from_list)  # noqa: F821
    importlib.reload(operator_material)  # noqa: F821
    importlib.reload(operator_model)  # noqa: F821
    importlib.reload(operator_options)  # noqa: F821
    importlib.reload(operator_notice)  # noqa: F821
    importlib.reload(operator_popup_message)  # noqa: F821
    importlib.reload(operator_preview)  # noqa: F821
    importlib.reload(operator_refresh_data)  # noqa: F821
    importlib.reload(operator_report_error)  # noqa: F821
    importlib.reload(operator_select)  # noqa: F821
    importlib.reload(operator_setting)  # noqa: F821
    importlib.reload(operator_show_preferences)  # noqa: F821
    importlib.reload(operator_show_quick_menu)  # noqa: F821
    importlib.reload(operator_unsupported_convention)  # noqa: F821
    importlib.reload(operator_user)  # noqa: F821
    importlib.reload(operator_view_thumbnail)  # noqa: F821
    importlib.reload(register_operators)  # noqa: F821
    importlib.reload(utils_operator)  # noqa: F821
    importlib.reload(constants)  # noqa: F821
    importlib.reload(preferences_map_prefs)  # noqa: F821
    importlib.reload(preferences)  # noqa: F821
    importlib.reload(props)  # noqa: F821
    importlib.reload(reporting)  # noqa: F821
    importlib.reload(toolbox)  # noqa: F821
    importlib.reload(toolbox_settings)  # noqa: F821
    importlib.reload(ui)  # noqa: F821
    if bpy.app.version >= (3, 0):
        importlib.reload(asset_browser_sync_commands)  # noqa: F821
        importlib.reload(asset_browser)  # noqa: F821
        importlib.reload(asset_browser_ui)  # noqa: F821
        importlib.reload(asset_browser_operator_import)  # noqa: F821
        importlib.reload(asset_browser_operator_quick_menu)  # noqa: F821
        importlib.reload(asset_browser_operator_reprocess)  # noqa: F821
        importlib.reload(asset_browser_operator_sync_cancel)  # noqa: F821
        importlib.reload(asset_browser_operator_sync_client)  # noqa: F821
        importlib.reload(asset_browser_operator_update)  # noqa: F821
        importlib.reload(asset_browser_operators)  # noqa: F821
    importlib.reload(api)  # noqa: F821
    importlib.reload(env)  # noqa: F821
    importlib.reload(updater)  # noqa: F821
else:
    import bpy

    from .dialogs import dlg_account  # noqa: F401
    from .dialogs import dlg_add_node_groups  # noqa: F401
    from .dialogs import dlg_area_categories  # noqa: F401
    from .dialogs import dlg_area_notifications  # noqa: F401
    from .dialogs import dlg_area_tabs  # noqa: F401
    from .dialogs import dlg_assets  # noqa: F401
    from .dialogs import dlg_init_library  # noqa: F401
    from .dialogs import dlg_login  # noqa: F401
    from .dialogs import dlg_popup  # noqa: F401
    from .dialogs import dlg_quickmenu  # noqa: F401
    from .dialogs import utils_dlg  # noqa: F401
    from .operators import operator_active  # noqa: F401
    from .operators import operator_add_converter_node  # noqa: F401
    from .operators import operator_apply  # noqa: F401
    from .operators import operator_cancel_download  # noqa: F401
    from .operators import operator_category  # noqa: F401
    from .operators import operator_check_update  # noqa: F401
    from .operators import operator_close_notification  # noqa: F401
    from .operators import operator_detail  # noqa: F401
    from .operators import operator_directory  # noqa: F401
    from .operators import operator_download  # noqa: F401
    from .operators import operator_folder  # noqa: F401
    from .operators import operator_hdri  # noqa: F401
    from .operators import operator_library  # noqa: F401
    from .operators import operator_link  # noqa: F401
    from .operators import operator_local_asset_sync  # noqa: F401
    from .operators import operator_load_asset_from_list  # noqa: F401
    from .operators import operator_material  # noqa: F401
    from .operators import operator_model  # noqa: F401
    from .operators import operator_options  # noqa: F401
    from .operators import operator_notice  # noqa: F401
    from .operators import operator_popup_message  # noqa: F401
    from .operators import operator_preview  # noqa: F401
    from .operators import operator_refresh_data  # noqa: F401
    from .operators import operator_report_error  # noqa: F401
    from .operators import operator_select  # noqa: F401
    from .operators import operator_setting  # noqa: F401
    from .operators import operator_show_preferences  # noqa: F401
    from .operators import operator_show_quick_menu  # noqa: F401
    from .operators import operator_unsupported_convention  # noqa: F401
    from .operators import operator_user  # noqa: F401
    from .operators import operator_view_thumbnail  # noqa: F401
    from .operators import register_operators
    from .operators import utils_operator  # noqa: F401
    from . import constants  # noqa: F401
    from . import preferences_map_prefs
    from . import preferences
    from . import props
    from . import reporting  # noqa: F401
    from . import toolbox
    from . import toolbox_settings  # noqa: F401
    from . import ui
    if bpy.app.version >= (3, 0):
        from .asset_browser import asset_browser_sync_commands  # noqa: F401
        from .asset_browser import asset_browser  # noqa: F401
        from .asset_browser import asset_browser_ui
        from .asset_browser import asset_browser_operator_import  # noqa: F401
        from .asset_browser import asset_browser_operator_quick_menu  # noqa: F401
        from .asset_browser import asset_browser_operator_reprocess  # noqa: F401
        from .asset_browser import asset_browser_operator_sync_cancel  # noqa: F401
        from .asset_browser import asset_browser_operator_sync_client  # noqa: F401
        from .asset_browser import asset_browser_operator_update  # noqa: F401
        from .asset_browser import asset_browser_operators
    from .modules.poliigon_core import api  # noqa: F401, needed for tests
    from .modules.poliigon_core import env  # noqa: F401, needed for tests
    from .modules.poliigon_core import updater  # noqa: F401, needed for tests


def register():
    aver = ".".join([str(x) for x in bl_info["version"]])

    toolbox.init_context(aver)

    preferences_map_prefs.register(aver)  # needed in props
    props.register()
    preferences.register(aver)
    toolbox.register(aver)
    register_operators.register(aver)
    ui.register(aver)
    if bpy.app.version >= (3, 0):
        asset_browser.register(aver)
        asset_browser_operators.register(aver)
        asset_browser_ui.register(aver)


def unregister():
    # Reverse order of register.
    if toolbox.cTB is not None:
        toolbox.shutdown_addon()
    if bpy.app.version >= (3, 0):
        asset_browser_ui.unregister()
        asset_browser_operators.unregister()
        asset_browser.unregister()
    ui.unregister()
    register_operators.unregister()
    toolbox.unregister()
    preferences.unregister()
    props.unregister()
    preferences_map_prefs.unregister()


if __name__ == "__main__":
    register()
