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

from typing import Dict
import os

try:
    import ConfigParser
except Exception:
    import configparser as ConfigParser

from . import reporting
from .modules.poliigon_core.api_remote_control_params import (
    CATEGORY_ALL,
    KEY_TAB_IMPORTED,
    KEY_TAB_MY_ASSETS,
    KEY_TAB_RECENT_DOWNLOADS,
    KEY_TAB_ONLINE,
    KEY_TAB_LOCAL)
from .modules.poliigon_core.plan_manager import PoliigonSubscription
from .modules.poliigon_core.user import PoliigonUser

from .dialogs.utils_dlg import check_dpi
from .notifications import build_writing_settings_failed_notification
from .utils import (
    f_Ex,
    f_MDir)


# Use _get_default_settings() to get the default settings.
DEFAULT_SETTINGS = {
    "area": KEY_TAB_ONLINE,
    "auto_download": 1,
    "category": {
        KEY_TAB_IMPORTED: [CATEGORY_ALL],
        KEY_TAB_MY_ASSETS: [CATEGORY_ALL],
        KEY_TAB_RECENT_DOWNLOADS: [CATEGORY_ALL],
        KEY_TAB_ONLINE: [CATEGORY_ALL],
        KEY_TAB_LOCAL: [CATEGORY_ALL]
    },
    "conform": 0,
    "default_lod": "LOD1",
    "del_zip": 1,
    "disabled_dirs": [],
    "download_lods": 1,
    "download_prefer_blend": 1,
    "download_link_blend": 0,
    "hdri_use_jpg_bg": False,
    "hide_labels": 1,
    "hide_scene": 0,
    "hide_suggest": 0,
    "location": "Properties",
    "mapping_type": "UV + UberMapping",
    "mat_props": [],
    "mix_props": [],
    "new_release": "",
    "last_update": "",
    "new_top": 1,
    "notify": 5,
    "one_click_purchase": 1,
    "page": 6,
    "popup_welcome": 0,
    "popup_download": 0,
    "popup_preview": 0,
    "preview_size": 7,  # 7 currently constant/hard coded
    "previews": 1,
    # Note on reporting rates:
    # These will only be changed upon successful update-requests
    # and only ever store custom rates from updater. Any default
    # values and/or forced sampling values will and must not be stored
    # here!
    "reporting_error_rate": -1,  # no valid value
    "reporting_transaction_rate": -1,  # no valid value
    "set_library": "",
    "show_active": 1,
    "show_add_dir": 1,
    "show_asset_info": 1,
    "show_credits": 1,
    "show_default_prefs": 1,
    "show_display_prefs": 1,
    "show_import_prefs": 1,
    "show_asset_browser_prefs": True,
    "show_mat_ops": 0,
    "show_mat_props": 0,
    "show_mat_texs": 0,
    "show_mix_props": 1,
    "show_pass": 0,
    "show_plan": 1,
    "show_feedback": 0,
    "show_settings": 0,
    "show_user": 0,
    "sorting": "Latest",
    "thumbsize": "Medium",
    "unzip": 1,
    "update_sel": 1,
    "use_16": 1,
    "use_ao": 1,
    "use_bump": 1,
    "use_disp": 1,
    "use_subdiv": 1,
    "version": None,  # initialized in _get_default_settings()
    "win_scale": 1,
    "first_enabled_time": "",

    "res": "2K",
    "lod": "NONE",
    "mres": "2K",
    "hdri": "1K",
    "hdrib": "8K",
    "hdrif": "EXR",  # TODO(Andreas): constant and used in commented code, only
    "brush": "2K",

    # TODO(Andreas): Why did we store a list of map types in settings???
    # "maps": cTB.vMaps,
}


def _get_default_settings(cTB) -> Dict[str, any]:
    """Returns default settings from above dictionary, augmented with runtime
    infos like e.g. version.
    """

    settings = DEFAULT_SETTINGS
    settings["version"] = cTB.version
    return settings


def _read_config(cTB):
    """Safely reads the config or returns an empty one if corrupted."""

    config = ConfigParser.ConfigParser()
    config.optionxform = str
    with cTB.lock_settings_file:
        try:
            config.read(cTB.path_settings)
        except ConfigParser.Error:
            # Corrupted file, return empty config.
            cTB.logger.exception(
                "Config parsing error, using fresh empty config instead.")
            config = ConfigParser.ConfigParser()
            config.optionxform = str
    return config


def _get_settings_section_user(cTB, config: ConfigParser) -> bool:
    """Returns False, if section 'user' is not found."""

    if not config.has_section("user"):
        return False

    if cTB.user is None:
        # Note: Marking non existing user by setting user ID None
        cTB.user = PoliigonUser(
            user_name="", user_id=None, plan=PoliigonSubscription())

    user = cTB.user
    for _key in config.options("user"):
        if _key in cTB.skip_legacy_settings:
            continue
        if _key in ["credits", "credits_od"]:
            try:
                setattr(user, _key, int(config.get("user", _key)))
            except ValueError:
                setattr(user, _key, 0)
        elif _key == "token":
            token = config.get("user", "token")
            if token and token != "None":
                cTB._api.token = config.get("user", "token")
        elif _key == "user_name":
            setattr(user, _key, config.get("user", _key))
        elif _key == "id":
            try:
                user_id_config = config.get("user", _key)
                user.user_id = int(user_id_config)
            except ValueError:
                if user_id_config not in [None, "None"]:  # Typical logged out case
                    cTB.logger.exception(f"Couldn't set user '{user_id_config}':")
                user.user_id = None  # mark user not existent
        elif _key == "user_id":
            pass  # ignore, likely a remnant from a bug during development
        # elif _key == "plan_name":
        #     user.plan.plan_name = config.get("user", _key)
        elif _key == "plan_credit":
            try:
                setattr(user.plan, _key, int(config.get("user", _key)))
            except ValueError:
                setattr(user.plan, _key, None)
        elif _key in ["plan_name", "plan_paused_at", "plan_paused_until"]:
            setattr(user.plan, _key, config.get("user", _key))
        elif _key == "plan_next_renew":
            user.plan.next_subscription_renewal_date = config.get("user", _key)
        elif _key == "plan_next_credits":
            user.plan.next_credit_renewal_date = config.get("user", _key)
        elif _key == "plan_paused":
            pass  # we do get this info from addon-core, now
        elif _key == "is_free_user":
            pass  # we do get this info from addon-core, now
        else:
            # TODO(Andreas): Remove, when working. Or add logging/reporting
            cTB.logger.debug("UNSET USER PARAM", _key)

    if user.user_id is None:
        cTB.user = None
    else:
        reporting.assign_user(cTB.user.user_id)

    return True


def _get_settings_section_settings(cTB, config: ConfigParser) -> None:
    if not config.has_section("settings"):
        return

    for _key in config.options("settings"):
        if _key.startswith("category"):
            try:
                cTB.settings["category"] = config.get(
                    "settings", _key
                ).split("/")
                if "" in cTB.settings[_key]:
                    cTB.settings["category"].remove("")
            except Exception:
                pass
        else:
            cTB.settings[_key] = config.get("settings", _key)

            if _key in [
                "add_dirs",
                "disabled_dirs",
                "mat_props",
                "mix_props",
            ]:
                cTB.settings[_key] = cTB.settings[_key].split(";")
                if "" in cTB.settings[_key]:
                    cTB.settings[_key].remove("")
            elif cTB.settings[_key] == "True":
                cTB.settings[_key] = 1
            elif cTB.settings[_key] == "False":
                cTB.settings[_key] = 0
            else:
                try:
                    cTB.settings[_key] = int(cTB.settings[_key])
                except Exception:
                    try:
                        cTB.settings[_key] = float(cTB.settings[_key])
                    except Exception:
                        pass
            # Fallback, if lod was set to SOURCE
            if _key == "lod" and cTB.settings[_key] == "SOURCE":
                # TODO(Andreas): Fallback to LOD0 correct?
                cTB.settings[_key] = "LOD0"


def _get_settings_section_presets(cTB, config: ConfigParser) -> None:
    if not config.has_section("presets"):
        return

    for _key in config.options("presets"):
        try:
            cTB.vPresets[_key] = [
                float(_value)
                for _value in config.get("presets", _key).split(";")
            ]
        except Exception:
            pass


def _get_settings_section_mixpresets(cTB, config: ConfigParser) -> None:
    if not config.has_section("mixpresets"):
        return

    for _key in config.options("mixpresets"):
        try:
            cTB.vMixPresets[_key] = [
                float(_value)
                for _value in config.get("mixpresets", _key).split(";")
            ]
        except Exception:
            pass


def _get_settings_section_download(cTB, config: ConfigParser) -> None:
    if not config.has_section("download"):
        return

    for _key in config.options("download"):
        if _key == "res":
            cTB.settings["res"] = config.get("download", _key)
        elif _key == "maps":
            value = config.get("download", _key)
            cTB.settings["maps"] = value.split(";")


def get_settings_section_map_prefs(cTB) -> None:
    config = _read_config(cTB)
    if not config.has_section("map_preferences"):
        return

    user_prefs = cTB.user.map_preferences
    if user_prefs is None:
        return

    for _map_format in user_prefs.texture_maps:
        map_name = _map_format.map_type.name
        local_ext_pref = config.get(
            "map_preferences", str(map_name), fallback="")
        local_ext_available = _map_format.extensions.get(
            local_ext_pref.lower(), True)

        if local_ext_pref in [None, ""] or not local_ext_available:
            continue
        elif local_ext_pref == "NONE":
            _map_format.selected = None
            _map_format.enabled = False
        else:
            _map_format.selected = local_ext_pref.lower()
            _map_format.enabled = True


def get_settings(cTB) -> None:
    cTB.logger.debug("get_settings")

    cTB.skip_legacy_settings = ["name", "email"]

    cTB.settings = _get_default_settings(cTB)

    check_dpi(cTB)

    cTB.vPresets = {}
    cTB.vMixPresets = {}

    cTB.vReleases = {}

    if f_Ex(cTB.path_settings):  # check done outside of lock should still be ok
        config = _read_config(cTB)

        if not _get_settings_section_user(cTB, config):
            with cTB.lock_settings_file:
                os.remove(cTB.path_settings)
            config = ConfigParser.ConfigParser()

        _get_settings_section_settings(cTB, config)
        _get_settings_section_presets(cTB, config)
        _get_settings_section_mixpresets(cTB, config)
        _get_settings_section_download(cTB, config)
        # Loading of map prefs works differently, as it happens upon
        # receiving map prefs from server.

    if cTB.settings.get("library", "") == "":
        cTB.settings["set_library"] = cTB.dir_settings.replace(
            "Blender", "Library")

    cTB.settings["show_user"] = 0
    cTB.settings["mat_props_edit"] = 0

    cTB.settings["area"] = KEY_TAB_ONLINE
    cTB.settings["category"] = [CATEGORY_ALL]

    save_settings(cTB)


def _save_settings_section_user(cTB, config: ConfigParser) -> None:
    if not config.has_section("user"):
        config.add_section("user")

    # for vK in cTB.vUser.keys():
    #     if vK in cTB.skip_legacy_settings:
    #         config.remove_option("user", vK)
    #         continue
    #     config.set("user", vK, str(cTB.vUser[vK]))
    if cTB.user is not None:
        config.set("user", "id", str(cTB.user.user_id))
        config.set("user", "user_name", str(cTB.user.user_name))

    # Save token as if cTB field, on load will be parsed to _api.token
    config.set("user", "token", str(cTB._api.token))


def _save_settings_section_settings(cTB, config: ConfigParser) -> None:
    if not config.has_section("settings"):
        config.add_section("settings")

    for _key in cTB.settings.keys():
        if _key == "category":
            config.set("settings", _key, "/".join(cTB.settings[_key]))
        elif _key in ["add_dirs", "disabled_dirs", "mat_props", "mix_props"]:
            config.set("settings", _key, ";".join(cTB.settings[_key]))
        else:
            config.set("settings", _key, str(cTB.settings[_key]))


def _save_settings_section_presets(cTB, config: ConfigParser) -> None:
    if not config.has_section("presets"):
        config.add_section("presets")

    for _key in cTB.vPresets.keys():
        config.set(
            "presets", _key,
            ";".join([str(_value) for _value in cTB.vPresets[_key]])
        )


def _save_settings_section_mixpresets(cTB, config: ConfigParser) -> None:
    if not config.has_section("mixpresets"):
        config.add_section("mixpresets")

    for _key in cTB.vMixPresets.keys():
        config.set(
            "mixpresets",
            _key, ";".join([str(_value) for _value in cTB.vMixPresets[_key]])
        )


def _save_settings_section_download(cTB, config: ConfigParser) -> None:
    if config.has_section("download"):
        config.remove_section("download")

    config.add_section("download")

    for _key in cTB.settings:
        if _key == "res":
            config.set("download", _key, cTB.settings[_key])
        elif _key == "maps":
            config.set("download", _key, ";".join(cTB.settings[_key]))


def _remove_replaced_legacy_settings(cTB, config: ConfigParser) -> None:
    try:
        config.remove_option("settings", "library")
    except ConfigParser.NoSectionError:
        pass  # it's fine if not existing
    try:
        config.remove_option("settings", "add_dirs")
    except ConfigParser.NoSectionError:
        pass  # it's fine if not existing


def _save_settings_section_map_prefs(cTB, config: ConfigParser) -> None:
    if not config.has_section("map_preferences"):
        config.add_section("map_preferences")

    if cTB.user is None:
        return
    user_prefs = cTB.user.map_preferences
    if user_prefs is None:
        return

    for _map_format in user_prefs.texture_maps:
        map_name = _map_format.map_type.name
        selected = _map_format.selected
        extension = selected if selected is not None else "NONE"

        config.set("map_preferences", str(map_name), str(extension))


def save_settings(cTB) -> None:
    cTB.logger.debug("save_settings")

    config = _read_config(cTB)

    _remove_replaced_legacy_settings(cTB, config)

    _save_settings_section_user(cTB, config)
    _save_settings_section_settings(cTB, config)
    _save_settings_section_presets(cTB, config)
    _save_settings_section_mixpresets(cTB, config)
    _save_settings_section_download(cTB, config)
    _save_settings_section_map_prefs(cTB, config)

    f_MDir(cTB.dir_settings)

    with cTB.lock_settings_file:
        try:
            with open(cTB.path_settings, "w+") as file:
                config.write(file)
        except OSError as e:
            if e.errno != 28:
                # Below notice assumes the OSError is for disk space only,
                # so let's report if this ever isn't the case
                reporting.capture_exception(e)
            build_writing_settings_failed_notification(cTB, e.strerror)
