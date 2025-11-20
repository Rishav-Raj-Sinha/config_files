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

from typing import Callable, Dict, List, Optional, Tuple, Union
import atexit
import datetime
import faulthandler
import json
import os
import queue
import threading
import time

import bpy
from bpy.app.handlers import persistent
import bpy.utils.previews

from . import reporting

from .modules.poliigon_core.addon import PoliigonAddon
from .modules.poliigon_core.api import (
    ApiStatus,
    ERR_LIMIT_DOWNLOAD_RATE,
    PoliigonConnector,
    SOFTWARE_NAME_BLENDER)
from .modules.poliigon_core.api_remote_control import (
    ApiJob,
    ApiRemoteControl,
    JobType)
from .modules.poliigon_core.api_remote_control_params import (
    CATEGORY_ALL,
    get_search_key,
    KEY_TAB_IMPORTED,
    KEY_TAB_MY_ASSETS,
    KEY_TAB_RECENT_DOWNLOADS,
    KEY_TAB_ONLINE,
    KEY_TAB_LOCAL,
    IDX_PAGE_ACCUMULATED,
    PAGE_SIZE_ACCUMULATED)
from .modules.poliigon_core.assets import (
    API_TYPE_TO_ASSET_TYPE,
    AssetType,
    ModelType)
from .modules.poliigon_core.assets import AssetData
from .modules.poliigon_core.logger import (  # noqa: F401
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL)
from .modules.poliigon_core.multilingual import _t
from .modules.poliigon_core.settings import PoliigonSettings
from .modules.poliigon_core.upgrade_content import UpgradeContent
from .modules.poliigon_core import env
from .modules.poliigon_core import updater
# from .thumb_cache import ThumbCache
from .constants import (
    ADDON_NAME,
    ICONS,
    SUPPORTED_CONVENTION,
    URLS_BLENDER)
from .material_importer import MaterialImporter
from .notifications import (
    build_restart_notification,
    add_survey_notification)
from .preferences_map_prefs_util import update_map_prefs_properties
from .toolbox_settings import (
    get_settings,
    get_settings_section_map_prefs,
    save_settings)
from .utils import (
    f_Ex,
    f_MDir)

# TODO(Andreas): Just left these in for some quick notification testing
# from .notifications import (
#     build_material_template_error_notification,
#     build_writing_settings_failed_notification,
#     build_lost_client_notification,
#     build_new_catalogue_notification,
#     build_no_refresh_notification,
#     build_survey_notification
# )

ADDON_PATH = os.path.dirname(os.path.abspath(__file__))


def panel_update(context=None) -> None:
    """Force a redraw of the 3D and preferences panel from operator calls."""

    if context is None:
        context = bpy.context
    try:
        for wm in bpy.data.window_managers:
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type not in ("VIEW_3D", "PREFERENCES"):
                        continue
                    for region in area.regions:
                        # Compare panel's bl_category
                        # TODO(Andreas): Disabled, due to missing progress
                        # bar refreshes
                        # if region.active_panel_category != "Poliigon":
                        #    continue
                        region.tag_redraw()
    except AttributeError:
        pass  # Startup condition, nothing to redraw anyways.


def get_prefs() -> Optional[bpy.types.Preferences]:
    """User preferences call wrapper, separate to support test mocking."""

    # __spec__.parent since __package__ got deprecated
    prefs = bpy.context.preferences.addons.get(__spec__.parent, None)
    # Fallback, if command line and using the standard install name.
    if prefs is None:
        addons = bpy.context.preferences.addons
        prefs = addons.get(ADDON_NAME, None)
    if prefs is not None and hasattr(prefs, "preferences"):
        return prefs.preferences
    else:
        return None


class c_Toolbox(PoliigonAddon):

    # Container for any notifications to show user in the panel UI.
    # Containers for errors to persist in UI for drawing, e.g. after dload err.
    ui_errors = []

    updater = None  # Callable set up on register.

    # Used to indicate if register function has finished for the first time
    # or not, to differentiate initial register to future ones such as on
    # toggle or update
    initial_register_complete = False
    # Container for the last time we performed a check for updated addon files,
    # only triggered from UI code so it doesn't run when addon is not open.
    last_update_addon_files_check = 0

    # Icon containers.
    ui_icons = None
    thumbs = None

    # Container for threads.
    # Initialized here so it can be referenced before register completes.
    threads = []

    # Establish locks for general usage:
    lock_thumbs = threading.Lock()  # locks access to thumbs
    lock_client_start = threading.Lock()
    lock_settings_file = threading.Lock()

    # Reporting sample rates, None until value read from remote json
    reporting_error_rate = None
    reporting_transaction_rate = None

    def __init__(
            self, addon_version: str, api_service: PoliigonConnector = None):
        self.register_success = False
        environment = env.PoliigonEnvironment(
            addon_name=ADDON_NAME,
            base=os.path.dirname(__file__)
        )
        if environment.env_name is not None and environment.env_name == "test":
            settings_filename = "settings_test.ini"
        else:
            settings_filename = "settings.ini"
        settings = PoliigonSettings(
            addon_name=ADDON_NAME,
            software_source=SOFTWARE_NAME_BLENDER,
            settings_filename=settings_filename
        )

        addon_version_t = tuple([int(val) for val in addon_version.split(".")])
        super(c_Toolbox, self).__init__(
            addon_name=ADDON_NAME,
            addon_version=addon_version_t,
            software_source=SOFTWARE_NAME_BLENDER,
            software_version=bpy.app.version,
            addon_env=environment,
            addon_settings=settings,
            addon_convention=SUPPORTED_CONVENTION,
            addon_supported_model=[ModelType.BLEND, ModelType.FBX],
            addon_root_path=ADDON_PATH
        )

        if api_service is not None:
            self._api = api_service

        self.init_addon_parameters(
            get_optin=reporting.get_optin,
            callback_on_invalidated_token=self._callback_on_invalidated_token,
            report_message=reporting.capture_message,
            report_exception=reporting.capture_exception,
            report_thread=reporting.handle_thread,
            status_listener=self.api_status_listener,
            get_renderer_name=self.api_get_renderer,
            urls_dcc=URLS_BLENDER,
            notify_icon_info="INFO",
            notify_icon_no_connection="NONE",
            notify_icon_survey="NONE",
            notify_icon_warn="ERROR",
            notify_icon_wm_onboarding="HIDE_OFF",
            notify_update_body=_t("Download the {0} update"),
            onboarding_wm_title=_t("Preview textures in 1K by clicking the eye icon"),
        )

    def register(self, version: str) -> None:
        """Deferred registration, to ensure properties exist."""

        if self._env.env_name and "dev" in self._env.env_name.lower():
            faulthandler.enable(all_threads=False)

        self.vRunning = 0
        self.quitting = False

        self.version = version
        software_version = ".".join([str(x) for x in bpy.app.version])

        # TODO(Andreas): Also move into PoliigonAddon.init_addon()
        page_size_get_assets = 500
        self.api_rc = ApiRemoteControl(self)
        addon_params = self.api_rc._addon_params
        addon_params.online_assets_chunk_size = page_size_get_assets
        addon_params.my_assets_chunk_size = page_size_get_assets
        addon_params.callback_get_categories_done = self.callback_get_categories_done
        addon_params.callback_get_asset_done = self.callback_get_asset_done
        addon_params.callback_get_user_data_done = self.callback_get_user_data_done
        addon_params.callback_get_download_prefs_done = self.callback_get_download_prefs
        addon_params.callback_get_available_plans = self.callback_plan_upgrades
        addon_params.callback_get_upgrade_plan = self.callback_plan_upgrades
        addon_params.callback_put_upgrade_plan = self.callback_put_upgrade_plan
        addon_params.callback_resume_plan = self.callback_put_upgrade_plan

        self._api.register_update(self.version, software_version)
        self._updater.last_check_callback = self._callback_last_update

        self._init_directories()
        self._init_logger()

        self.mat_import = MaterialImporter(self)  # implicitly sets Cycles

        # Have defaults or forced sampling, regardless of any online info
        self.reporting_error_rate = 1.0 if self._env.forced_sampling else 0.2
        self.reporting_transaction_rate = 1.0 if self._env.forced_sampling else 0.2

        self._init_reporting(has_updater=False)  # init with defaults

        # Pixel width, init to non-zero to avoid div by zero.
        self.width_draw_ui = 1
        self.ui_scale_checked = False

        self.login_mode_browser = True
        self.login_cancelled = False
        self.login_time_start = 0
        self.login_in_progress = False
        self.login_is_signup = False  # Track if signup or login was clicked
        self.last_login_error = None
        self.did_show_profile_survey = False  # To avoid repeating survey
        self.signal_for_profile_survey_emitted = False

        self.msg_download_limit = None

        self.vSearch = self._init_tabs_dict("")
        self.vLastSearch = self._init_tabs_dict("")
        self.vPage = self._init_tabs_dict(0)
        self.vPages = self._init_tabs_dict(0)

        self.vEditPreset = None

        # TODO(Andreas): New importing code does not have any exceptions like this.
        #                Should it, though?
        # self.vModSecondaries = ["Footrest", "Vase"]

        # TODO(Andreas): Likely no longer needed, since there are only
        #                one-shot signalling events stored in here.
        self.threads = []

        # Note: When being called, the function will set this to None,
        #       in order to avoid burning additional CPU cycles on this
        self.f_add_survey_notification_once = add_survey_notification

        self.settings = {}
        get_settings(self)  # -> sets self.settings
        self.prefs = get_prefs()

        self.ui_errors = []

        self.vActiveCat = self.settings["category"]
        self.vAssetType = self.vActiveCat[0]

        # Initial value to use for linking set by prefrences.
        # This way, it initially will match the preferences setting on startup,
        # but then changing this value will also persist with a single sesison
        # without changing the saved value.
        self.link_blend_session = self.settings["download_link_blend"]

        self.vCategories = self._init_tabs_dict_dict()
        self.vCategories["new"] = {}  # TODO(Andreas): ???
        self.category_ids = {}
        self.num_assets = self._init_tabs_dict(0)
        self.num_assets_current_query = 0

        self.vActiveObjects = []
        self.vActiveAsset = None
        self.vActiveMat = None
        self.vActiveMatProps = {}
        self.vActiveTextures = {}
        self.vActiveFaces = {}
        self.vActiveMode = None

        self.vActiveMixProps = {}
        self.vActiveMix = None
        self.vActiveMixMat = None

        # Asset Browser synchronization
        self.proc_blender_client = None
        # blender_client_starting is True not only while Blender process starts,
        # but also during asset data fetch phase
        self.blender_client_starting = False
        self.listener_running = False
        self.thd_listener = None
        self.sender_running = False
        self.thd_sender = None
        self.queue_send = queue.Queue()
        self.queue_ack = queue.Queue()
        self.event_hello = None
        self.num_asset_browser_jobs = 0
        self.num_jobs_ok = 0
        self.num_jobs_error = 0
        self.asset_browser_jobs_cancelled = False
        self.asset_browser_quitting = False

        # TODO(Andreas): Just left these in for some quick notification testing
        # build_survey_notification(self)
        # build_material_template_error_notification(self)
        # build_writing_settings_failed_notification(self, "test error")
        # build_lost_client_notification(self)
        # build_new_catalogue_notification(self)
        # build_no_refresh_notification(self)
        # # Test these three separately, as they can not be dismissed:
        # # build_no_internet_notification(self)
        # # build_proxy_notification(self)
        # # build_restart_notification(self)

        # if no_startup:
        #     return

        # Output used to recognize a fresh install (or update).
        any_updated = self.update_files(self.dir_script)
        self._init_icons()

        self.vRunning = 1

        # TODO(Andreas): If we want to use ThumbCache
        # self.thumb_cache = ThumbCache(
        #     self,h
        #     self._asset_index,
        #     self.api_rc,
        #     path_cache=self.dir_online_previews,
        #     size_download=300,
        #     bmp_downloading=self.ui_icons["GET_preview"].icon_id,
        #     bmp_error=self.ui_icons["NO_preview"].icon_id,
        #     cleanup_check_interval_s=360.0,
        #     cleanup_not_used_for_s=360.0,
        #     num_load_threads=8,
        #     force_dummy=0
        # )
        with self.lock_thumbs:
            if self.thumbs is None:
                self.thumbs = bpy.utils.previews.new()
            else:
                self.thumbs.clear()

        self._init_update_info()

        if self.settings["last_update"]:
            self._updater.last_check = self.settings["last_update"]

        if any_updated and not self._api.token:
            # This means this was a new install without a local login token.
            # This setup won't pick up installs in new blender instances
            # where no login event had to happen, but will pick up the first
            # install on the same machine.
            now = datetime.datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            self.settings["first_enabled_time"] = now_str
            save_settings(self)

        if self._api._is_opted_in():
            self.logger.info(f"Sentry error rate: {self.reporting_error_rate}")
            self.logger.info(
                f"Sentry transaction rate: {self.reporting_transaction_rate}")

        self._convert_legacy_library_directories()

        # fetching_asset_data is used to disable last page and refresh data
        # buttons during get assets job being processed.
        self.fetching_asset_data = self._init_tabs_dict_dict()
        key_fetch_all = ((CATEGORY_ALL, ), "")
        self.fetching_asset_data[KEY_TAB_MY_ASSETS][key_fetch_all] = True
        self.fetching_asset_data[KEY_TAB_ONLINE][key_fetch_all] = True
        if self.user is not None:
            user_name = self.user.user_name
            user_id = self.user.user_id
        else:
            user_name = ""
            user_id = 0

        self._init_upgrade_content()
        self.plan_upgrade_in_progress = False
        self.plan_upgrade_finished = False
        self.error_plan_upgrade = None
        self.msg_plan_upgrade_finished = None

        # If no token available, there is no reason to add a /me job - will
        # be redirected to login page;
        if self._api.token:
            self.fetching_user_data = True
            self.api_rc.add_job_get_user_data(
                user_name,
                user_id,
                callback_cancel=None,
                callback_progress=None,
                do_fetch_asset_data=not self.all_assets_fetched,
                callback_done=self.callback_get_user_data_done,
                force=True
            )

        self.initial_screen_viewed = False
        self.initial_register_complete = True
        self.register_success = True

    def _init_directories(self) -> None:
        self.dir_script = os.path.join(os.path.dirname(__file__), "files")

        # TODO(SOFT-58): Defer folder creation and prompt for user path.
        dir_user_home = os.path.expanduser("~")
        dir_base = os.path.join(dir_user_home.replace("\\", "/"), "Poliigon")

        self.dir_settings = os.path.join(dir_base, "Blender")
        f_MDir(self.dir_settings)

        self.dir_online_previews = os.path.join(dir_base, "OnlinePreviews")
        f_MDir(self.dir_online_previews)

        if self._env.env_name is not None and self._env.env_name == "test":
            filename_settings = "Poliigon_Blender_Settings_test.ini"
        else:
            filename_settings = "Poliigon_Blender_Settings.ini"

        self.path_settings = os.path.join(self.dir_settings, filename_settings)

    def _init_logger(self) -> None:
        self.logger_ab = self.log_manager.initialize_logger("P4B.AB")
        self.logger_ui = self.log_manager.initialize_logger("P4B.UI")

        # TODO(Andreas): Maybe these should stay unconditional prints?
        self.logger.info("\nStarting the Poliigon Addon for Blender...\n")
        self.logger.info(self.path_settings)
        self.logger.info("Toggle verbose logging in addon preferences")

    def _init_icons(self) -> None:
        # Separating UI icons from asset previews.
        if self.ui_icons is None:
            self.ui_icons = bpy.utils.previews.new()
        else:
            self.ui_icons.clear()

        for _name, _filename, _icontype in ICONS:
            path_icon = os.path.join(self.dir_script, _filename)
            if not os.path.isfile(path_icon):
                # Logging as critical, not because it is,
                # but so we do not miss such errors upon release.
                self.logger.critical(f"Icon file missing:\n  {path_icon}")
                continue
            self.ui_icons.load(_name, path_icon, _icontype)

    @staticmethod
    def _init_tabs_dict(value: any) -> Dict:
        """Initializes a dictionary with the main tabs as keys and an arbitrary
        value per tab.
        """

        dict_tabs = {
            KEY_TAB_ONLINE: value,
            KEY_TAB_MY_ASSETS: value,
            KEY_TAB_RECENT_DOWNLOADS: value,
            KEY_TAB_IMPORTED: value,
            KEY_TAB_LOCAL: value
        }
        return dict_tabs

    @staticmethod
    def _init_tabs_dict_dict() -> None:
        """Initializes a dictionary with the main tabs as keys and
        a dict per tab.
        """

        dict_tabs = {
            KEY_TAB_ONLINE: {},
            KEY_TAB_MY_ASSETS: {},
            KEY_TAB_RECENT_DOWNLOADS: {},
            KEY_TAB_IMPORTED: {},
            KEY_TAB_LOCAL: {}
        }
        return dict_tabs

    def _init_reporting(self, has_updater: bool = True) -> None:
        """(Re)Initialize sentry with current known sample rates.

        Called once immediately on startup, and then again once we have the
        latest remote reporting information.
        """

        if has_updater:
            # Get Sentry sampling rates from update info and store
            # in settings, if needed
            curr_ver = self._updater.current_version
            env_force_sample = self._env.forced_sampling
            if curr_ver.error_sample_rate is not None and not env_force_sample:
                self.reporting_error_rate = curr_ver.error_sample_rate
                self.settings["reporting_error_rate"] = self.reporting_error_rate
            if curr_ver.traces_sample_rate is not None and not env_force_sample:
                self.reporting_transaction_rate = curr_ver.traces_sample_rate
                self.settings["reporting_transaction_rate"] = self.reporting_transaction_rate

            save_settings(self)

        reporting.register(
            software_name=self._api.software_source,
            software_version=self._api.software_version,
            tool_version=self._api.version_str,
            env=self._env,
            error_rate=self.reporting_error_rate,
            transaction_rate=self.reporting_transaction_rate)

    def _init_update_info(self) -> None:
        """If we have no Sentry sample rates, do an inital synchronous update
        check, otherwise just init the sample rates.
        """

        is_new_version = self.settings["version"] != self.version
        error_rate = self.settings["reporting_error_rate"]
        transaction_rate = self.settings["reporting_transaction_rate"]
        if error_rate != -1 and transaction_rate != -1 and not is_new_version:
            self.reporting_error_rate = error_rate
            self.reporting_transaction_rate = transaction_rate
            self._init_reporting()
            return

        self.settings["version"] = self.version

        # Synchronously get update info to get reporting rates
        self._updater.check_for_update(
            # Note: This "update available" callback is not needed here.
            #       The _callback_last_update does all we want.
            callback=None,
            create_notifications=False)

    def _init_online_all_assets_page_1(self) -> None:
        """Clears out any user choices (search, category,...) and switches to
        page 1 of online tab.
        """

        self.settings["area"] = KEY_TAB_ONLINE
        self.settings["show_settings"] = 0
        self.settings["show_user"] = 0
        self.vPage[KEY_TAB_ONLINE] = 0
        self.vPages[KEY_TAB_ONLINE] = 1

        self.settings["category"] = [CATEGORY_ALL]
        self.vActiveAsset = None
        self.vActiveMat = None
        self.vActiveMode = None

        props = bpy.context.window_manager.poliigon_props
        props.search = ""

    def _init_upgrade_content(self) -> None:
        """Initializes UpgradeContent with P4B specifics."""

        if self.upgrade_manager is None:
            return
        upgrade_content = UpgradeContent(
            self.upgrade_manager,
            as_single_paragraph=True,
            icons=("ICON_plan_upgrade_check",
                   "ICON_plan_upgrade_info",
                   "ICON_plan_upgrade_unlimited"))
        self.upgrade_manager.content = upgrade_content

    def _convert_legacy_library_directories(self) -> None:
        """Before we went addon-core, P4B stored library directories in its
        own Poliigon_Blender_Settings.ini. This caused issues with addon-core
        keeping track of library directories on its own in settings.ini.
        Thus we convert from old to new in here, basically, after converting
        the config, removing library dir config from Poliigon_Blender_Settings.ini.
        """

        settings = self.settings

        if "library" not in settings and "add_dirs" not in settings:
            return

        path_primary = ""
        paths_additional = []
        if "library" in settings:
            path_primary = settings.get("library", "")
            del settings["library"]
        if "add_dirs" in settings:
            paths_additional = settings.get("add_dirs", [])
            del settings["add_dirs"]

        save_settings(self)

        if len(path_primary) == 0 and len(paths_additional) == 0:
            return

        # Overwrite anything addon-core might assume so far.
        self.library_paths = []
        self.add_library_path(path_primary, primary=True)
        for _path_library in paths_additional:
            self.add_library_path(_path_library, primary=False)

    @staticmethod
    def api_get_renderer() -> Optional[str]:
        try:
            renderer = bpy.context.scene.render.engine
        except AttributeError:  # Startup condition
            renderer = None
        return renderer

    def api_status_listener(self, status: ApiStatus) -> None:
        """Updates notifications according to the form of the API event.

        This is called by API's event_listener when API events occur.
        """

        if self._api.status_notice is None:
            return

        if status == ApiStatus.CONNECTION_OK:
            self.notify.dismiss_notice(self._api.status_notice, force=True)
        # TODO(Andreas): We need to discuss, how to throttle in this case.
        #                The sleep would work, but is kind of ugly here.
        # elif status == ApiStatus.NO_INTERNET:
        #     time.sleep(1.0)  # just throttling further requests

    def _callback_on_invalidated_token(self) -> None:
        """This function is passed to addon-core.

        It gets called by api.request functions to invalidate the token upon
        failed API requests.

        Called on thread level!
        """

        self._api.token = None
        self.settings_config.set("user", "token", "")
        reporting.assign_user(None)
        save_settings(self)

        self.login_in_progress = False

        self._asset_index.flush()
        self._asset_index.flush_is_local()
        self._asset_index.flush_is_purchased()
        self._asset_index.flush_state()

        self.refresh_ui()

    def _callback_last_update(self, value: any) -> None:
        """Called by the updated module to allow saving in local system."""

        if self._updater is None:
            return

        self._init_reporting()
        self.settings["last_update"] = self._updater.last_check
        save_settings(self)

    def callback_update_api_status_banners(self, arg) -> None:
        # TODO(Andreas)
        self.refresh_ui()

    def callback_get_user_data_done(self, job: ApiJob) -> None:
        """DCC specific finalization of 'get user data' job."""

        if not job.result.ok:
            self.fetching_asset_data = self._init_tabs_dict_dict()
            self.logger.warn("callback_get_user_data_done NOK")
            self._callback_on_invalidated_token()
            self.refresh_ui()
            return

        self.login_in_progress = False
        self.fetching_user_data = False

        if self.user is not None:
            reporting.assign_user(self.user.user_id)
        else:
            reporting.assign_user(None)
            reporting.capture_message(
                "none_user_after_get_user_data_done",
                "User is none after logging in with OK response",
                "error")

        self.refresh_ui()

    def callback_plan_upgrades(self, job: ApiJob) -> None:
        """DCC specific finalization of 'get available plans' and
        'get upgrade plan' jobs.
        """

        if self.upgrade_manager is None:
            return
        self.refresh_ui()

    def callback_put_upgrade_plan(self, job: ApiJob) -> None:
        """DCC specific finalization of 'put upgrade plan' and
        'resume plan' jobs.
        """

        if bpy.app.timers.is_registered(t_check_change_plan_response):
            bpy.app.timers.unregister(t_check_change_plan_response)

        if job.result.ok:
            self.error_plan_upgrade = None
        else:
            self.error_plan_upgrade = job.result.error

        self.plan_upgrade_finished = True
        self.refresh_ui()

    def callback_get_download_prefs(self, job: ApiJob) -> None:
        if self.quitting:
            # We are not allowed to set properties during shutdown
            return
        if self.user is None:
            return
        user_prefs = self.user.map_preferences
        if user_prefs is None:
            return

        self.user.use_preferences_on_download = True
        # At this point addon-core has server's map prefs.
        # Now, read and override with any locally store settings.
        get_settings_section_map_prefs(self)
        # And transfer map prefs from addon-core to our properties
        # used in prefs.
        update_map_prefs_properties(self)

    def callback_login_done(self, job: ApiJob) -> None:
        """Callback to be called after a login job has finished.

        Informs the addon about the outcome of the login job.

        Called on thread level!
        """

        if not job.result.ok:
            # TODO(Andreas): Proper error communication, as soon as the UI
            #                provides a common way of displaying errors
            #                (maybe like Notifications in P4B)
            #                NOTE: We end up here for cancelled logins, too.
            if job.result.error != "Login cancelled":
                self.logger.error("Login")
                self.logger.error(job.result)
                self.last_login_error = job.result.error

            self._callback_on_invalidated_token()
            return

        self.login_in_progress = False

        token = job.result.body.get("access_token", "")
        self.settings_config.set("user", "token", token)

        # Clear time since install since successful.
        if self.login_elapsed_s is not None:
            self.settings["first_enabled_time"] = ""

        self._settings.save_settings()

        user_info = job.result.body.get("user", {})
        name_user = user_info.get("name", "")
        id_user = user_info.get("id", -1)

        if self.user is not None:
            reporting.assign_user(self.user.user_id)
        else:
            reporting.assign_user(None)

        key_fetch_all = ((CATEGORY_ALL, ), "")
        self.fetching_asset_data[KEY_TAB_MY_ASSETS][key_fetch_all] = True
        self.fetching_asset_data[KEY_TAB_ONLINE][key_fetch_all] = True
        self.fetching_user_data = True
        self.api_rc.add_job_get_user_data(
            name_user,
            id_user,
            callback_cancel=None,
            callback_progress=None,
            do_fetch_asset_data=not self.all_assets_fetched,
            callback_done=self.callback_get_user_data_done,
            force=True
        )

        # TODO(Andreas): Check the first run mechanic (P4Cinema does below)
        # ### set_pref(ID_INTERNAL_TIME_FIRST_RUN, "")

        self._init_online_all_assets_page_1()
        save_settings(self)
        self.refresh_ui()

    def callback_logout_done(self, job: ApiJob) -> None:
        """Callback to be called after a logout job has finished.

        Informs the addon about the outcome of the logout job.

        Called on thread level!
        """

        if not job.result.ok:
            # TODO(Andreas): Proper error communication,
            #                something like DisplayError
            self.logger.error("Logout")
            self.logger.error(job.result)

        self.fetching_user_data = True

        # TODO(Andreas): any_owned_brushes can likely be removed
        self.prefs.any_owned_brushes = "undecided"
        self._callback_on_invalidated_token()

        self.refresh_ui()

    def callback_login_cancel(self) -> bool:
        """Callback communicating the 'login cancel' button got pressed.

        The flag gets set by execution of this login command in mode
        'login cancel'.

        Called on thread level!
        """

        return self.login_cancelled

    def callback_get_categories_done(self, job: ApiJob) -> None:
        """DCC specific finalization of 'get categories' job."""

        if job.result.ok:
            body = job.result.body
            if not len(body):
                error = job.result.error
                self.logger.error(
                    f"callback_get_categories_done: ERROR {error}\n    {body}")

            for _category in body:
                type_cat = _category.get("name", "Unknown Category")
                self.logger.debug(
                    f"callback_get_categories_done: Type: {type_cat}")
                if type_cat not in self.vCategories[KEY_TAB_ONLINE].keys():
                    self.vCategories[KEY_TAB_ONLINE][type_cat] = {}

                id_category = _category.get("id", -1)
                cat_path = _category.get("path", "")
                cat_path = cat_path.replace("/hdrs", "/HDRIs")
                self.category_ids[id_category] = cat_path
                self.f_GetCategoryChildren(type_cat, _category)

            path_category_file = os.path.join(
                self.dir_settings, "TB_Categories.json")
            with open(path_category_file, "w") as file_categories:
                json.dump(self.vCategories, file_categories)

        self.refresh_ui()

    def _check_asset_browser(self, asset_id_list: List[str]) -> None:
        """Checks all assets in list for a _LIB.blend file and
        accordingly marks them as 'in asset browser' (or not).
        """

        asset_data_list = self._asset_index.get_asset_data_list(
            asset_id_list)
        for _asset_data in asset_data_list:
            if not _asset_data.is_local:
                continue
            directory = _asset_data.get_asset_directory()
            if directory is None:
                continue

            filename = f"{_asset_data.asset_name}_LIB.blend"
            path_lib_file = os.path.join(directory, filename)
            lib_file_exists = os.path.isfile(path_lib_file)
            _asset_data.runtime.set_in_asset_browser(
                in_asset_browser=lib_file_exists)

    def callback_get_asset_done(self, job: ApiJob) -> None:
        """DCC specific finalization of 'get assets' job."""

        params = job.params
        key_fetch = (tuple(params.category_list), params.search)

        if not job.result.ok:
            if key_fetch in self.fetching_asset_data[params.tab]:
                del self.fetching_asset_data[params.tab][key_fetch]
            self.refresh_ui()
            return

        if params.already_in_index and not params.force_request:
            if key_fetch in self.fetching_asset_data[params.tab]:
                del self.fetching_asset_data[params.tab][key_fetch]
            self.refresh_ui()
            return

        asset_id_list = params.asset_id_list
        if asset_id_list is None:
            asset_id_list = []

        first_page = params.idx_page == 1
        last_page = params.idx_page >= job.result.body.get("last_page", -1)

        # self.thumb_cache.add_asset_list(
        #     asset_id_list,
        #     do_prefetch=first_page,
        #     callback_done=self.callback_asset_update_ui
        # )

        if first_page:
            asset_data_list = self._asset_index.get_asset_data_list(
                asset_id_list[:self.settings["page"]])
            for _asset_data in asset_data_list:
                path_thumb, url_thumb = self._asset_index.get_cf_thumbnail_info(
                    _asset_data.asset_id)
                self.start_thumb_download(
                    _asset_data, path_thumb, url_thumb, idx_thumb=0)

            category_list = params.category_list
            if len(category_list) == 1 and category_list[0] == CATEGORY_ALL and len(params.search) == 0:
                self.num_assets[params.tab] = job.result.body.get("total", -1)

        tab_active = self.settings["area"]
        is_imported_request = tab_active == KEY_TAB_IMPORTED
        imported_refresh = is_imported_request and params.tab in [KEY_TAB_MY_ASSETS,
                                                                  KEY_TAB_RECENT_DOWNLOADS]
        tab_refresh = tab_active == params.tab or imported_refresh

        idx_ui_page_current = self.vPage[tab_active]  # this is a UI page index
        num_per_ui_page = self.settings["page"]
        idx_first_ui_asset = idx_ui_page_current * num_per_ui_page
        idx_last_ui_asset = idx_first_ui_asset + num_per_ui_page

        idx_first_job_asset = (params.idx_page - 1) * params.page_size
        idx_last_job_asset = idx_first_job_asset + len(asset_id_list)

        ui_page_in_job = idx_first_job_asset <= idx_first_ui_asset < idx_last_job_asset
        # Note: If either UI page size is not a divisor of API page size or
        #       simply due to Substance assets being filtered the UI page can
        #       be spread across two API requests
        ui_page_in_job |= idx_first_job_asset <= idx_last_ui_asset < idx_last_job_asset

        user_assets_tab = params.tab in [KEY_TAB_MY_ASSETS, KEY_TAB_RECENT_DOWNLOADS]
        if user_assets_tab or self.is_unlimited_user():
            self.f_GetSceneAssets()
            self._check_asset_browser(asset_id_list)

        if last_page and key_fetch in self.fetching_asset_data[params.tab]:
            del self.fetching_asset_data[params.tab][key_fetch]

        if (tab_refresh and ui_page_in_job) or self.vPage[tab_active] == 0 or last_page:
            self.refresh_ui()

    def callback_asset_update_ui(self, job: ApiJob) -> None:
        """Triggers a redraw of an asset's thumb widget.

        DCC specific progress and finalization of 'download thumb',
        'purchase asset' and 'download asset' jobs.
        """

        if job.job_type == JobType.DOWNLOAD_ASSET:
            result = job.result
            if not result.ok and result.error == ERR_LIMIT_DOWNLOAD_RATE:
                # Have popup opened by main thread
                self.msg_download_limit = job.params.download.res_error_message
                # TODO(Andreas): Temporarily disable opening the popup,
                #                since it is not working reliably.
                # bpy.app.timers.register(
                #     f_do_on_main_thread, first_interval=0.05, persistent=False)

        # try:
        #     # Thumb download
        #     asset_id = job.params.asset_id
        # except AttributeError:
        #     # Asset purchase/download
        #     asset_id = job.params.asset_data.asset_id

        # TODO(Andreas): purchase error forwarding
        # if job.job_type == JobType.PURCHASE_ASSET:
        #     state_purchase = job.params.asset_data.state.purchase
        #     if state_purchase.has_error():
        #         c4d.SpecialEventAdd(PLUGIN_ID_CMSG_NOTIFY,
        #                             CMSG_NOTIFY_PURCHASE_ERROR,
        #                             asset_id)

        # TODO(Andreas): Would be super nice, if we could trigger a redraw
        #                of only a single thumb widget
        self.refresh_ui()

    def refresh_ui(self) -> None:
        """Wrapper to decouple blender UI drawing from callers of self."""

        if self.quitting:
            return
        panel_update(bpy.context)

    def user_invalidated(self) -> bool:
        """Returns whether or not the user token was invalidated."""

        if self._api.invalidated:
            self.prefs.any_owned_brushes = "undecided"
        return self._api.invalidated

    def clear_user_invalidated(self) -> None:
        """Clears any invalidation flag for a user."""

        self._api.invalidated = False

    def initial_view_screen(self) -> None:
        """Reports view from a draw panel, to avoid triggering until use."""

        if self.initial_screen_viewed is True:
            return
        self.initial_screen_viewed = True
        self.track_screen_from_area()

    def track_screen_from_area(self) -> None:
        """Signals the active screen in background if opted in"""

        area = self.settings["area"]
        if area == KEY_TAB_ONLINE:
            self.signal_view_screen("home")
        elif area == KEY_TAB_MY_ASSETS:
            self.signal_view_screen(KEY_TAB_MY_ASSETS)
        elif area == KEY_TAB_IMPORTED:
            self.signal_view_screen(KEY_TAB_IMPORTED)
        elif area == KEY_TAB_LOCAL:
            self.signal_view_screen(KEY_TAB_LOCAL)
        elif area == KEY_TAB_RECENT_DOWNLOADS:
            # Can't it be only "downloads", since that is the tab used for all requests?
            self.signal_view_screen(KEY_TAB_RECENT_DOWNLOADS)
        elif area == "account":
            self.signal_view_screen("my_account")

    def signal_popup(
            self, *, popup: str, click: Optional[str] = None) -> None:
        """Signals an onboarding popup being viewed or clicked in the
        background
        """
        if click is not None:
            self.signal_click_notification(popup, click)
        else:
            self.signal_view_notification(popup)

    def f_GetCategoryChildren(self, type_cat: str, category: Dict) -> None:
        children = category.get("children", [])
        for _child in children:
            cat_path = []
            child_path = _child["path"]
            for _path_parts in child_path.split("/"):
                _path_parts = " ".join([_part.capitalize()
                                        for _part in _path_parts.split("-")])
                cat_path.append(_path_parts)

            cat_path = ("/".join(cat_path)).replace("/" + type_cat + "/", "/")
            cat_path = cat_path.replace("/Hdris/", "/")

            if "Generators" in cat_path:
                continue

            self.logger.debug(f"f_GetCategoryChildren {cat_path}")

            id_category = _child.get("id", -1)
            child_path = child_path.replace("/hdrs", "/HDRIs")

            self.category_ids[id_category] = child_path
            self.vCategories[KEY_TAB_ONLINE][type_cat][cat_path] = []
            if len(_child.get("children", [])) > 0:
                self.f_GetCategoryChildren(type_cat, _child)

    # @timer
    def f_GetAssets(
        self,
        area: Optional[str] = None,
        categories: Optional[List[str]] = None,
        search: Optional[str] = None,
        force: bool = False,
        force_request: bool = False,
        callback_done: Optional[Callable] = None
    ) -> None:

        self.logger.debug(
            f"f_GetAssets area={area}, force={force}")
        self.logger.debug(
            f"            search={search}")
        self.logger.debug(
            f"            categories={categories}")

        if area is None:
            area = self.settings["area"]

        if categories is None:
            categories = self.settings["category"].copy()

        if area == KEY_TAB_LOCAL:
            # For Local assets we should always force the request (and not rely
            # on cached queries). There is no Api request involved - so there
            # is no major counterpoint in this case;
            force_request = True

        if search is None:
            search = self.vSearch[area]
        if search != self.vLastSearch[area]:
            self.flush_thumb_prefetch_queue()

        if callback_done is None:
            callback_done = self.callback_get_asset_done

        do_my_assets = False
        if area == KEY_TAB_IMPORTED:
            if self.is_unlimited_user():
                area = KEY_TAB_ONLINE
            else:
                area = KEY_TAB_RECENT_DOWNLOADS
                do_my_assets = self.user_legacy_own_assets()

        key_fetch = (tuple(categories), search)
        if key_fetch in self.fetching_asset_data[area]:
            return  # Already waiting for results

        self.fetching_asset_data[area][key_fetch] = True
        self.api_rc.add_job_get_assets(
            library_paths=self.get_library_paths(),
            tab=area,
            category_list=categories,
            search=search,
            idx_page=1,  # Always fetch all beginning from page 1
            page_size=None,
            force_request=force_request,
            do_get_all=True,
            callback_cancel=None,
            callback_progress=None,
            callback_done=callback_done,
            do_my_assets=do_my_assets,
            force=force)

    def flush_thumb_prefetch_queue(self) -> None:
        self.api_rc.wait_for_all(JobType.DOWNLOAD_THUMB, do_wait=False)

        # TODO(Andreas): prefetching
        # # Flush prefetch queue, i.e. prefetch requests not yet in thread pool
        # while not self.queue_thumb_prefetch.empty():
        #     try:
        #         self.queue_thumb_prefetch.get_nowait()
        #     except Exception:
        #         pass  # not interested in exceptions in here

        # # Try to cancel download threads in threadpool
        # with self.lock_thumb_download_futures:
        #     # As the done callback of the futures removes from this list
        #     # (using the same lock) we need a copy
        #     futures_to_cancel = self.thumb_download_futures.copy()
        # # Now cancel the futures without lock acquired
        # for fut, asset_name in futures_to_cancel:
        #     if not fut.cancel():
        #         # Thread either executing or done already
        #         continue
        #     with self.lock_thumbs:
        #         if asset_name in self.thumbsDownloading:
        #             self.thumbsDownloading.remove(asset_name)
        # with self.lock_thumbs:
        #     self.thumbsDownloading = []

    # @timer
    def f_GetPageAssets(self, idx_page: int) -> Tuple[Optional[List[int]], int]:
        area = self.settings["area"]
        search = self.vSearch[area]
        num_per_page = self.settings["page"]

        self.logger.debug(f"f_GetPageAssets area={area}, search={search}, "
                          f"idx_page={idx_page}")

        category_list = self.settings["category"]
        key = get_search_key(
            tab=area, search=search, category_list=category_list)

        if not self.all_assets_fetched:
            return None, 0

        if area != KEY_TAB_ONLINE and not self.are_user_assets_fetched():
            return None, 0

        asset_ids = self._asset_index.query(key_query=key,
                                            chunk=IDX_PAGE_ACCUMULATED,
                                            chunk_size=PAGE_SIZE_ACCUMULATED)
        idx_first_asset = idx_page * num_per_page
        idx_last_asset = idx_first_asset + num_per_page

        try:
            self.num_assets_current_query = len(asset_ids)
        except TypeError:
            self.num_assets_current_query = 0

        if asset_ids is not None:
            self.logger.debug(f"f_GetPageAssets num ids: {len(asset_ids)}")
            asset_ids_page = asset_ids[idx_first_asset:idx_last_asset]
            num_pages = len(asset_ids) // num_per_page
            if len(asset_ids) % num_per_page > 0:
                num_pages += 1

            # An empty list here means, we're on a page, which has not been
            # fetched, yet.
            # But returning empty list leads to "No results" display",
            # which we want to avoid in this situation.
            # Lets double check, we are really still fetching and then
            # return None instead:
            if len(asset_ids_page) == 0:
                key_fetch = (tuple(category_list), search)
                if key_fetch in self.fetching_asset_data[area]:
                    asset_ids_page = None
        else:
            # This case is different from a query leading to no results.
            # We'll return 'asset_ids_page = None', so UI can differentiate
            # between a 'loading screen' and a 'no results screen'.
            self.logger.debug("f_GetPageAssets: No query cache entry, yet!")
            asset_ids_page = None
            num_pages = 0

            self.f_GetAssets()
        return asset_ids_page, num_pages

    # @timer
    def f_GetAssetsSorted(self, idx_page: int) -> List[int]:
        area = self.settings["area"]
        self.logger.debug(
            f"f_GetAssetsSorted idx_page={idx_page}, area={area}")

        asset_ids_page, num_pages = self.f_GetPageAssets(idx_page)
        if asset_ids_page is None:
            self.logger.debug("f_GetAssetsSorted Dummy Assets")
            return self._get_dummy_assets()
        elif len(asset_ids_page) > 0:
            self.vPages[area] = num_pages
            return asset_ids_page
        else:
            self.logger.debug("f_GetAssetsSorted No Assets")
            return []

    def check_if_purchased(self, asset_id) -> bool:
        """Workaround to ensure only truly purchased assets are included here,

        since asset_data.is_purchased actually means "purchased or downloads"
        Old code: owned = bool(asset_data.is_purchased)
        """
        query_key_all_user_assets = (
            KEY_TAB_MY_ASSETS,
            None,
            None,
            None,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED)
        try:
            asset_ids_my_assets = cTB._asset_index.cached_queries[
                query_key_all_user_assets]
        except KeyError:
            asset_ids_my_assets = []
        return asset_id in asset_ids_my_assets

    def get_pref_size(self, asset_type: AssetType) -> str:
        if asset_type == AssetType.TEXTURE:
            return self.settings["res"]
        elif asset_type == AssetType.MODEL:
            return self.settings["mres"]
        elif asset_type == AssetType.HDRI:
            return self.settings["hdri"]
        elif asset_type == AssetType.BRUSH:
            return self.settings["brush"]
        else:
            self.logger.error("get_pref_size: UNKNOWN ASSET TYPE")
            return ""

    # TODO(Andreas): No longer in use, but may get revived, e.g. for getting
    #                asset_id for old Poliigon porperties storing
    #                asset name, only
    # def get_data_for_asset_name(self,
    #                             asset_name: str,
    #                             *,
    #                             area_order: List[str] = [KEY_TAB_ONLINE,
    #                                                      KEY_TAB_MY_ASSETS,
    #                                                      "local"]
    #                             ) -> Dict:
    #     """Get the data structure for an asset by asset_name alone."""
    #     for area in area_order:
    #         with self.lock_assets:
    #             subcats = list(self.vAssets[area])
    #             for cat in subcats:
    #                 for asset in self.vAssets[area][cat]:
    #                     if asset == asset_name:
    #                         return self.vAssets[area][cat][asset]
    #     # Failed to fetch asset, return empty structure.
    #     return {}

    def _get_dummy_assets(self) -> List[int]:
        self.logger.debug("_get_dummy_assets")

        list_dummy_assets = []

        for _ in range(self.settings["page"]):
            list_dummy_assets.append(0)  # asset ID 0 = dummy asset

        return list_dummy_assets

    def start_thumb_download(
        self,
        asset_data: AssetData,
        path_thumb: str,
        url_thumb: str,
        idx_thumb: int = 0,
        callback_done: Optional[Callable] = None
    ) -> None:
        if callback_done is None:
            callback_done = self.callback_asset_update_ui

        asset_id = asset_data.asset_id
        self.logger.debug(
            f"start_thumb_download asset_id={asset_id}, "
            f"path_thumb={path_thumb}, url_thumb={url_thumb}, "
            f"idx_thumb={idx_thumb}")

        asset_data.runtime.set_thumb_downloading(is_downloading=True)
        self.api_rc.add_job_download_thumb(
            asset_id,
            url_thumb,
            path_thumb,
            callback_cancel=None,
            callback_progress=None,
            callback_done=callback_done,
            force=False
        )

    @reporting.handle_function(silent=True)
    def refresh_data(self, icons_only: bool = False) -> None:
        """Reload data structures of the addon to update UI and stale data.

        This function could be called in main or background thread.
        """
        self.ui_errors.clear()

        # Clear out state variables.
        with self.lock_thumbs:
            self.thumbs.clear()

        self._asset_index.flush()

        if icons_only is True:
            self.refresh_ui()
            return

        self.refresh_top_level_queries_flags()

        # Get updated account data, fresh "All Assets" data for both tabs
        # and category counts
        key_fetch_all = ((CATEGORY_ALL, ), "")
        self.fetching_asset_data[KEY_TAB_MY_ASSETS][key_fetch_all] = True
        self.fetching_asset_data[KEY_TAB_ONLINE][key_fetch_all] = True
        self.fetching_user_data = True
        self.api_rc.add_job_get_user_data(
            self.user.user_name,
            self.user.user_id,
            callback_cancel=None,
            callback_progress=None,
            do_fetch_asset_data=True,
            callback_done=self.callback_get_user_data_done,
            force=True
        )
        self.refresh_ui()

    def get_accumulated_query_cache_key(self,
                                        tab: str,
                                        search: str = "",
                                        category_list: List[str] = ["All Assets"]
                                        ) -> Tuple:
        key = get_search_key(
            tab=tab, search=search, category_list=category_list)
        query_key = self._asset_index._query_key_to_tuple(
            key, chunk=IDX_PAGE_ACCUMULATED, chunk_size=PAGE_SIZE_ACCUMULATED)
        return query_key

    @staticmethod
    def _get_asset_type_from_property(
        entity: Union[bpy.types.Image, bpy.types.Material, bpy.types.Object]
    ) -> AssetType:

        try:
            asset_type_name = entity.poliigon_props.asset_type
            asset_type = AssetType[asset_type_name]
        except KeyError:
            asset_type = API_TYPE_TO_ASSET_TYPE[asset_type_name]
        return asset_type

    def _find_asset_ids_in_scene(self) -> List[int]:
        """Finds all asset IDs in scene."""

        asset_ids_in_scene = []
        for _entity_coll in [bpy.data.images,
                             bpy.data.materials,
                             bpy.data.objects]:
            for _entity in _entity_coll:
                try:
                    # TODO(Andreas): Issue HDRS vs HDRIs?
                    asset_id = _entity.poliigon_props.asset_id
                    asset_type = self._get_asset_type_from_property(_entity)
                    if asset_type not in [AssetType.HDRI,
                                          AssetType.MODEL,
                                          AssetType.TEXTURE]:
                        # Old projects could still contain BRUSH type
                        continue
                    if asset_id in asset_ids_in_scene:
                        continue
                    if asset_type == AssetType.TEXTURE:
                        size = _entity.poliigon_props.size
                        if size == "WM":
                            continue
                    asset_ids_in_scene.append(asset_id)
                except Exception:
                    # Don't use this log message, if not actively debugging here!
                    # self.logger.exception(f"NO POLIIGON PROPS? {_entity.name}")
                    pass
        return asset_ids_in_scene

    def _get_tab_base_assets(self) -> List[int]:
        # To the server "Imported" tab acts as if it was
        # "My Assets" + "Downloads" tab.
        # And its responses will be stored as accumulated "My Assets" and
        # "Downloads"entries in query cache.
        # These will then be used in here to create proper query cache entries
        # for "Imported" tab, which will always be just filtered down versions
        # of the "My Assets" requests.
        #
        # For unlimited users this needs to work a bit different, as local
        # assets do not appear on My Assets tab, in this case the Online tab
        # needs to be used as reference.
        if self.is_unlimited_user():
            tab_base = [KEY_TAB_ONLINE]
        else:
            tab_base = [KEY_TAB_MY_ASSETS, KEY_TAB_RECENT_DOWNLOADS]

        base_ids = []
        for _tab in tab_base:
            query_base = self.get_accumulated_query_cache_key(
                tab=_tab,
                search=self.vSearch[KEY_TAB_IMPORTED],
                category_list=self.settings["category"])

            if query_base not in self._asset_index.cached_queries:
                continue

            base_ids += self._asset_index.cached_queries[query_base]
        return base_ids

    def f_GetSceneAssets(self) -> None:
        self.logger.debug("f_GetSceneAssets")

        user_asset_ids = self._get_tab_base_assets()
        try:
            asset_ids_in_scene = self._find_asset_ids_in_scene()
        except AttributeError as e:
            if "_RestrictData" in str(e):
                # Blender still starting up, can't access local data yet
                return
            raise e

        # Filter My Assets IDs by asset IDs in scene
        # (so we maintain order and category/search filtering)
        asset_ids_in_query = []
        for _asset_id in user_asset_ids:
            if _asset_id not in asset_ids_in_scene:
                continue
            asset_ids_in_query.append(_asset_id)

        # Finally store result in query cache
        query_key_imported = self.get_accumulated_query_cache_key(
            tab=KEY_TAB_IMPORTED,
            search=self.vSearch[KEY_TAB_IMPORTED],
            category_list=self.settings["category"])
        self._asset_index.cached_queries[query_key_imported] = asset_ids_in_query

    # TODO(Andreas): f_GetActiveData is in dire need for some love
    def f_GetActiveData(self) -> None:
        self.logger.debug("f_GetActiveData")

        self.vActiveMatProps = {}
        self.vActiveTextures = {}
        self.vActiveMixProps = {}

        if self.vActiveMat is None:
            return

        vMat = bpy.data.materials[self.vActiveMat]

        if self.vActiveMode == "mixer":
            vMNodes = vMat.node_tree.nodes
            vMLinks = vMat.node_tree.links
            for vN in vMNodes:
                if vN.type == "GROUP":
                    if "Mix Texture Value" in [vI.name for vI in vN.inputs]:
                        vMat1 = None
                        vMat2 = None
                        vMixTex = None
                        for vL in vMLinks:
                            if vL.to_node == vN:
                                if vL.to_socket.name in ["Base Color1",
                                                         "Base Color2"]:
                                    vProps = {}
                                    for vI in vL.from_node.inputs:
                                        if vI.is_linked:
                                            continue
                                        if vI.type == "VALUE":
                                            vProps[vI.name] = vL.from_node

                                    if vL.to_socket.name == "Base Color1":
                                        vMat1 = [vL.from_node, vProps]
                                    elif vL.to_socket.name == "Base Color2":
                                        vMat2 = [vL.from_node, vProps]
                                elif vL.to_socket.name == "Mix Texture":
                                    if vN.inputs["Mix Texture"].is_linked:
                                        vMixTex = vL.from_node

                        vProps = {}
                        for vI in vN.inputs:
                            if vI.is_linked:
                                continue
                            if vI.type == "VALUE":
                                vProps[vI.name] = vN

                        self.vActiveMixProps[vN.name] = [
                            vN,
                            vMat1,
                            vMat2,
                            vProps,
                            vMixTex,
                        ]

            if self.settings["mix_props"] == []:
                vK = list(self.vActiveMatProps.keys())[0]
                self.settings["mix_props"] = list(self.vActiveMatProps[vK][3].keys())
        else:
            vMNodes = vMat.node_tree.nodes
            for vN in vMNodes:
                if vN.type == "GROUP":
                    for vI in vN.inputs:
                        if vI.type == "VALUE":
                            self.vActiveMatProps[vI.name] = vN
                elif vN.type == "BUMP" and vN.name == "Bump":
                    for vI in vN.inputs:
                        if vI.type == "VALUE" and vI.name == "Strength":
                            self.vActiveMatProps[vI.name] = vN

            if self.settings["mat_props"] == []:
                self.settings["mat_props"] = list(self.vActiveMatProps.keys())

            if vMat.use_nodes:
                for vN in vMat.node_tree.nodes:
                    if vN.type == "TEX_IMAGE":
                        if vN.image is None:
                            continue
                        vFile = vN.image.filepath.replace("\\", "/")
                        if f_Ex(vFile):
                            vType = vN.name
                            if vType == "COLOR":
                                vType = "COL"
                            elif vType == "DISPLACEMENT":
                                vType = "DISP"
                            elif vType == "NORMAL":
                                vType = "NRM"
                            elif vType == "OVERLAY":
                                vType = "OVERLAY"

                            self.vActiveTextures[vType] = vN

                    elif vN.type == "GROUP":
                        for vN1 in vN.node_tree.nodes:
                            if vN1.type == "TEX_IMAGE":
                                if vN1.image is None:
                                    continue
                                vFile = vN1.image.filepath.replace("\\", "/")
                                if f_Ex(vFile):
                                    vType = vN1.name
                                    if vType == "COLOR":
                                        vType = "COL"
                                    if vType == "OVERLAY":
                                        vType = "OVERLAY"
                                    elif vType == "DISPLACEMENT":
                                        vType = "DISP"
                                    elif vType == "NORMAL":
                                        vType = "NRM"
                                    self.vActiveTextures[vType] = vN1
                            elif vN1.type == "BUMP" and vN1.name == "Bump":
                                for vI in vN1.inputs:
                                    if vI.type == "VALUE" and vI.name == "Distance":
                                        self.vActiveMatProps[vI.name] = vN1

    def f_GetPreview(self,
                     asset_data: AssetData,
                     idx_thumb: int = 0,
                     load_image: bool = True
                     ) -> Optional[int]:
        """Queue download for a preview if not already local.

        Use a non-zero index to fetch another preview type thumbnail.
        """

        asset_id = asset_data.asset_id
        asset_name = asset_data.asset_name
        self.logger.debug(
            f"f_GetPreview asset_id={asset_id}, idx_thumb={idx_thumb}, "
            f"load_image={load_image}")

        if asset_name == "dummy" or asset_id < 0:
            # asset_id < 0 means backdoor imported asset with no thumb info
            return None

        with self.lock_thumbs:
            if asset_name in self.thumbs:
                # TODO(SOFT-447): See if there's another way at this moment to
                #                 inspect whether the icon we are returning
                #                 here is gray or not.
                # TODO(Andreas): While SOFT-447 is marked done, the actual
                #                problem of grey thumbs still persists.
                #                Thus this TODO is still valid.
                # print(
                #     "Returning icon id",
                #     asset_name,
                #     self.thumbs[asset_name].image_size[:])
                return self.thumbs[asset_name].icon_id

        f_MDir(self.dir_online_previews)

        path_thumb, url_thumb = self._asset_index.get_cf_thumbnail_info(
            asset_id)
        if path_thumb is not None and os.path.isfile(path_thumb):
            if not load_image:  # special case used by thumb prefetcher
                return None

            with self.lock_thumbs:
                try:
                    self.thumbs.load(asset_name, path_thumb, "IMAGE")
                except KeyError:
                    self.thumbs[asset_name].reload()

                self.logger.debug(f"f_GetPreview {path_thumb}")

                return self.thumbs[asset_name].icon_id

        self.start_thumb_download(asset_data, path_thumb, url_thumb, idx_thumb)
        return None

    def get_verbose(self) -> bool:
        """Returns verbosity setting from prefs."""

        prefs = self.prefs
        if prefs is None:
            prefs = get_prefs()
        if prefs is not None:
            return prefs.verbose_logs
        else:
            return False

    def interval_check_update(self) -> None:
        """Checks with an interval delay for any updated files.

        Used to identify if an update has occurred. Note: If the user installs
        and updates by manually pasting files in place, or even from install
        addon via zip in preferences, and the addon is already active, there
        is no event-based function ran to let us know. Hence we use this
        polling method instead.
        """

        interval = 10
        now = time.time()
        if self.last_update_addon_files_check + interval > now:
            return
        self.last_update_addon_files_check = now
        self.update_files(self.dir_script)

    def update_files(self, path: str) -> bool:
        """Updates files in the specified path within the addon."""

        update_key = "_update"
        files_to_update = [f for f in os.listdir(path)
                           if os.path.isfile(os.path.join(path, f))
                           and os.path.splitext(f)[0].endswith(update_key)]

        for f in files_to_update:
            f_split = os.path.splitext(f)
            tgt_file = f_split[0][:-len(update_key)] + f_split[1]

            try:
                os.replace(os.path.join(path, f), os.path.join(path, tgt_file))
                self.logger.debug(f"update_files Updated {tgt_file}")
            except PermissionError as e:
                reporting.capture_message("file_permission_error", e, "error")
            except OSError as e:
                reporting.capture_message("os_error", e, "error")

        # If the intial register already completed, then this must be the
        # second time we have run the register function. If files were updated,
        # it means this was a fresh update install.
        # Thus: We must notify users to restart.
        any_updates = len(files_to_update) > 0
        if any_updates and self.initial_register_complete:
            self.notify_restart_required()

        return any_updates

    def notify_restart_required(self) -> None:
        """Creates a UI-blocking banner telling users they need to restart.

        This will occur if the user has installed an updated version of the
        addon but has not yet restarted Blender. This is important to avoid
        errors caused by only paritally reloaded modules.
        """

        build_restart_notification(self)

    def check_update_callback(self) -> None:
        """Callback run by the updater instance."""

        # Hack to force it to think update is available
        fake_update = False
        if fake_update:
            self._updater.update_ready = True
            self._updater.update_data = updater.VersionData(
                version=(1, 0, 0),
                url="https://poliigon.com/blender")

        self.refresh_ui()

    def _any_local_assets(self) -> bool:
        """Returns True, if there are local assets"""

        asset_ids_local = self._asset_index.get_asset_id_list(
            purchased=True, local=True)
        return len(asset_ids_local) > 0


def f_tick_handler() -> float:
    """Called on by blender timer handlers to check toolbox status.

    The returned value signifies how long until the next execution.
    """

    next_call_s = 60  # Long to prevent frequent checks for updates.
    if not cTB.vRunning:
        return next_call_s

    # Thread cleanup.
    for vT in list(cTB.threads):
        if not vT.is_alive():
            cTB.threads.remove(vT)

    # Updater callback.
    if cTB.prefs and cTB.prefs.auto_check_update:
        if cTB._updater.has_time_elapsed(hours=24):
            cTB._updater.async_check_for_update(
                cTB.check_update_callback,
                create_notifications=True)

    return next_call_s


def f_do_on_main_thread() -> float:
    """Called on by blender timer handlers to allow execution on main thread.

    The returned value signifies how long until the next execution.
    """

    if cTB.msg_download_limit is not None:
        bpy.ops.poliigon.popup_download_limit(
            "INVOKE_DEFAULT", msg=cTB.msg_download_limit)
        cTB.msg_download_limit = None

    return None  # Auto disarm, one-shot timer


@persistent
def f_load_handler(*args) -> None:
    """Runs when a new file is opened to refresh data."""

    if cTB.vRunning:
        cTB.f_GetSceneAssets()


def t_check_change_plan_response() -> float:
    """Timer used for 'plan upgrading', just in case API RC doesn't call
    our callback (not very likely...).
    """

    if cTB.plan_upgrade_in_progress and not cTB.plan_upgrade_finished:
        cTB.error_plan_upgrade = "Timeout, please try again later"
    return None  # Auto disarm, one-shot timer


cTB = None  # TODO(Andreas): At some point rename!


def init_context(addon_version: str) -> None:
    global cTB

    cTB = c_Toolbox(addon_version)


def get_context(addon_version: str) -> c_Toolbox:
    global cTB

    if cTB is None:
        init_context(addon_version)
    return cTB


def shutdown_asset_browser_client() -> None:
    """Shuts down client Blender process"""

    cTB.asset_browser_jobs_cancelled = True
    cTB.asset_browser_quitting = True

    # Needed for some unit tests to not cause exception on shutdown
    # if ran in "single" mode
    if not cTB.register_success:
        return

    if cTB.proc_blender_client is not None:
        cTB.proc_blender_client.terminate()


def shutdown_thumb_prefetch() -> None:
    # TODO(Andreas): Thumb prefetch still WIP
    # cTB.thread_prefetch_running = False

    # Avoid issues with Blender exit during unit tests
    # if not hasattr(cTB, "queue_thumb_prefetch"):
    #     return
    # if not hasattr(cTB, "dir_online_previews"):
    #     return
    # Just put something into queue, in order to have
    # thread return immediately, instead of waiting for timeout
    # cTB.enqueue_thumb_prefetch("quit")

    # TODO(Andreas): If we use ThumbCache we need to do:
    # cTB.thumb_cache.shutdown()
    pass


def shutdown_addon() -> None:
    """Shuts down all addon services.
    _Afterwards_ everything is ready for unregister.
    """

    cTB.quitting = True
    shutdown_thumb_prefetch()
    shutdown_asset_browser_client()
    cTB.api_rc.shutdown()

    cTB.vRunning = 0


@atexit.register
def blender_quitting() -> None:
    # CAREFUL! When this exit handler gets called, many Blender data structures
    # are already destructed. We must not use any Blender resources inside here.
    global cTB

    if cTB is None:
        return

    if cTB.vRunning == 1 and not cTB.quitting:
        shutdown_addon()


def register(addon_version: str) -> None:
    cTB.register(addon_version)

    bpy.app.timers.register(
        f_tick_handler, first_interval=0.05, persistent=True)

    if f_load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(f_load_handler)


def unregister() -> None:
    global cTB

    if cTB is None:
        print("cTB is None during unregister")
        return

    shutdown_addon()

    if cTB.log_manager.file_handler is not None:
        cTB.log_manager.file_handler.close()

    reporting.unregister()

    if bpy.app.timers.is_registered(f_do_on_main_thread):
        bpy.app.timers.unregister(f_do_on_main_thread)

    if bpy.app.timers.is_registered(f_tick_handler):
        bpy.app.timers.unregister(f_tick_handler)

    if f_load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(f_load_handler)

    # Don't block unregister or closing blender.
    # for vT in cTB.threads:
    #    vT.join()

    cTB.ui_icons.clear()
    try:
        bpy.utils.previews.remove(cTB.ui_icons)
    except KeyError:
        pass

    with cTB.lock_thumbs:
        cTB.thumbs.clear()

        try:
            bpy.utils.previews.remove(cTB.thumbs)
        except KeyError:
            pass
    cTB = None
