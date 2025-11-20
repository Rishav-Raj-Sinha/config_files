
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

"""This module contains the API Remote Control parameter classes."""

from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import partial
import os
from typing import Callable, Dict, List, Optional, Tuple, Any

from .user import (PoliigonSubscription,
                   PoliigonUser,
                   PoliigonUserProfiles,
                   UserDownloadPreferences)
from .plan_manager import (PoliigonPlanUpgradeInfo,
                           PlanUpgradeStatus,
                           SubscriptionState)
from .download_asset import AssetDownload
from .api import ApiResponse, ERR_NOT_ENOUGH_CREDITS
from .assets import AssetData
from .thread_manager import PoolKeys

# For use in query keys
KEY_TAB_RECENT_DOWNLOADS = "downloads"
KEY_TAB_IMPORTED = "imported"
KEY_TAB_MY_ASSETS = "my_assets"
KEY_TAB_LOCAL = "local_assets"
KEY_TAB_ONLINE = "poliigon"
KEY_TAB_UNPUBLISHED = "unpublished"

CATEGORY_ALL = "All Assets"
CATEGORY_FREE = "Free"

IDX_PAGE_ACCUMULATED = -1
PAGE_SIZE_ACCUMULATED = 1000000


@unique
class CmdLoginMode(IntEnum):
    # Do not have zero value members!
    LOGIN_CREDENTIALS = 1
    LOGIN_BROWSER = 2
    LOGOUT = 3
    LOGIN_CANCEL = 4


def get_search_key(tab: str, search: str, category_list: List[str]) -> str:
    """Returns a search/query string."""

    if search != "":
        sep = "@"
        search_ext = f"{sep}{search}"
    else:
        sep = "/"
        search_ext = ""
    categories = sep.join(category_list)
    key = f"{tab}{sep}{categories}{search_ext}"
    return key


@dataclass
class ApiResponseShutdown(ApiResponse):
    # This class is deliberately empty.
    # It only serves the purpose of being able to identify the ApiResponse
    # returned from get_shutdown_response() via instanceof().
    pass


def get_shutdown_response() -> ApiResponseShutdown:
    resp = ApiResponseShutdown(
        body={"data": []},
        # We don't want any error reporting, due to us shutting down
        ok=True,
        error="job shutdown"
    )
    return resp


# TODO(Andreas): Move these THUMB_SIZE_ constants to a better place.
# NOTE: THUMB_SIZE_DOWNLOAD needs to match one of the available download sizes!
THUMB_SIZE_MIN = 100
THUMB_SIZE_PROG = 145  # progress bar switches to short label
THUMB_SIZE_DEFAULT = 150
THUMB_SIZE_MAX = 200
THUMB_SIZE_DOWNLOAD = 300


@dataclass
class AddonRemoteControlParams():
    """ Parameters to be set in the Addon Side.

    NOTE: These processes are ran by default by API RC, so it is not possible
    to only parse using done_callback parameter in the ApiJob"""

    online_assets_chunk_size: int = 100
    my_assets_chunk_size: int = 100
    callback_get_categories_done: Optional[Callable] = None
    callback_get_asset_done: Optional[Callable] = None
    callback_get_user_data_done: Optional[Callable] = None
    callback_get_download_prefs_done: Optional[Callable] = None
    callback_get_available_plans: Optional[Callable] = None
    callback_get_upgrade_plan: Optional[Callable] = None
    callback_put_upgrade_plan: Optional[Callable] = None
    callback_resume_plan: Optional[Callable] = None


@dataclass
class ApiJobParams():
    """Job parameters.

    NOTE: Nothing in here.
          Only used as a parent class for type hints and defining interfaces.
    """

    def __eq__(self, other):
        raise NotImplementedError(
            "Some derived class forgot to implement __eq__")

    def __str__(self) -> str:
        raise NotImplementedError(
            "Some derived class forgot to implement __str__")

    def thread_execute(self,
                       api_rc,  # : ApiRemoteControl
                       job  # : ApiJob
                       ) -> None:
        """Executes job in a thread, started from thread_schedule."""

        raise NotImplementedError

    def finish(self,
               api_rc,  # : ApiRemoteControl
               job  # : ApiJob
               ) -> None:
        """Finishes a job, called from thread_collect."""

        raise NotImplementedError


@dataclass
class ApiJobParamsLogin(ApiJobParams):
    """Login specific parameters"""

    mode: CmdLoginMode
    email: Optional[str] = None
    pwd: Optional[str] = None
    time_since_enable: Optional[int] = None

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return self.mode == other.mode and self.email == other.email

    def __str__(self) -> str:
        # No email or password, as the resulting string might be reported to
        # server!
        return (
            f"ApiJobParamsLogin - mode: {self.mode.name}, "
            f"time_since_enable: {self.time_since_enable}"
        )

    def _exec_job_login_credential(self, api_rc, job) -> None:
        """Executes a login with email and password.
        Gets called in thread (thread_exec_job_login).
        """

        job.result = api_rc._api.log_in(self.email,
                                        self.pwd,
                                        self.time_since_enable)

    def _exec_job_login_browser(self, api_rc, job) -> None:
        """Executes a login via browser.
        Gets called in thread (thread_exec_job_login).
        """

        job.result = api_rc._api.log_in_with_website(self.time_since_enable)

        if not job.result.ok:
            return

        job.result = api_rc._api.poll_login_with_website_success(
            timeout=300,
            cancel_callback=job.callback_cancel,
            time_since_enable=self.time_since_enable
        )

    def _exec_job_logout(self, api_rc, job) -> None:
        """Executes a logout.
        Gets called in thread (thread_exec_job_login).
        """

        job.result = api_rc._api.log_out()

    def thread_execute(self, api_rc, job) -> None:
        """Executes any login/logout jobs in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        if self.mode == CmdLoginMode.LOGIN_CREDENTIALS:
            self._exec_job_login_credential(api_rc, job)
        elif self.mode == CmdLoginMode.LOGIN_BROWSER:
            self._exec_job_login_browser(api_rc, job)
        elif self.mode == CmdLoginMode.LOGOUT:
            self._exec_job_logout(api_rc, job)

    def finish(self, api_rc, job) -> None:
        """Finishes login/logout jobs, called from thread_collect."""

        if api_rc.in_shutdown:
            return

        # TODO(Andreas): Evaluate res and store in prefs?
        #                Currently done in CommandDataLogin.callback_xyz_done.
        #                Not sure, yet, where the better place would be.
        #                To have it here, would need abstract ways to set prefs.

        # TODO(Andreas): Strange! Should likely be fixed in addon-core.api
        #                or even server side. Will look into it at a later point.
        if "results" in job.result.body:
            # Login via browser response
            job.result.body = job.result.body["results"]

        if not job.result.ok or self.mode == CmdLoginMode.LOGOUT:
            api_rc.logger.debug("### Set user None")
            api_rc._asset_index.flush()
            api_rc._addon.all_assets_fetched = False
            api_rc._addon.my_assets_fetched = False
            api_rc._addon.recent_downloads_fetched = False
            api_rc._addon.user = None
        else:
            user_info = job.result.body.get("user", {})
            id_user = user_info.get("id", -1)
            name_user = user_info.get("name", "")

            # Checking if student or teacher - the value can be set as null in
            # the user_data, due to that we are falling back to an empty string
            user_use = user_info.get("how_will_you_use_poliigon", "")
            user_use = user_use if user_use is not None else ""
            is_student = "student" in user_use
            is_teacher = "teacher" in user_use

            # Checking owned and downloaded assets
            user_assets = job.result.body.get("assets")
            purchases = None
            downloads = None
            if user_assets is not None:
                purchases = user_assets.get("purchases")
                purchases = purchases if type(purchases) is int else None
                downloads = user_assets.get("purchases")
                downloads = downloads if type(downloads) is int else None

            primary_dcc = user_info.get("primary_3d_software")
            primary_dcc = None if not primary_dcc else primary_dcc
            primary_renderer = user_info.get("primary_rendering_engine")
            primary_renderer = None if not primary_renderer else primary_renderer

            subscription_info = job.result.body.get("subscription", {})
            subscription_info = subscription_info if subscription_info is not None else {}
            plan = PoliigonSubscription()
            plan.update_from_dict(subscription_info)
            api_rc._addon.user = PoliigonUser(
                user_name=name_user,
                user_id=id_user,
                is_student=is_student,
                is_teacher=is_teacher,
                count_assets_owned=purchases,
                count_assets_downloads=downloads,
                plan=plan,
                primary_3d_software=primary_dcc,
                primary_rendering_engine=primary_renderer,
                user_profile=PoliigonUserProfiles.from_string(user_use)
            )
            api_rc._addon.check_onboarding_notice()
            api_rc._addon.upgrade_manager.refresh(clean_plans=True)


@dataclass
class ApiJobParamsGetCategories(ApiJobParams):
    """Get Categories specific parameters"""

    # no parameters needed
    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return True

    def __str__(self) -> str:
        # Assuming user ID is fine in here, as we know it anyway!
        return "ApiJobParamsGetCategories"

    def thread_execute(self, api_rc, job) -> None:
        """Executes any get categories jobs in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        job.result = api_rc._api.categories()

    def finish(self, api_rc, job) -> None:
        """Finishes get categories jobs, called from thread_collect."""

        # For the moment nothing to do here.
        # Will likely change with dynamic category counts.
        pass


@dataclass
class ApiJobParamsGetUserData(ApiJobParams):
    """Get User Data specific parameters"""

    user_name: str = ""
    user_id: str = ""
    do_fetch_plans: bool = True
    do_fetch_categories: bool = True
    do_fetch_asset_data: bool = True

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return self.user_name == other.user_name and \
            self.user_id == other.user_id

    def __str__(self) -> str:
        # Assuming user ID is fine in here, as we know it anyway!
        return f"ApiJobParamsGetUserData - user id: {self.user_id}"

    def _evaluate_result_user(self, api_rc, result: ApiResponse) -> None:
        user_data = result.body.get("user", {})
        api_rc._addon.user.user_name = user_data.get("name", None)
        api_rc._addon.user.user_id = user_data.get("id", None)

        # Checking if student or teacher - the value can be set as null in
        # the user_data, due to that we are falling back to an empty string
        user_use = user_data.get("how_will_you_use_poliigon", "")
        user_use = user_use if user_use is not None else ""
        is_student = "student" in user_use
        is_teacher = "teacher" in user_use

        api_rc._addon.user.is_student = is_student
        api_rc._addon.user.is_teacher = is_teacher
        api_rc._addon.user.user_profile = PoliigonUserProfiles.from_string(user_use)

        # Checking owned and downloaded assets
        user_assets = result.body.get("assets")
        if user_assets is not None:
            purchases = user_assets.get("purchases")
            purchases = purchases if type(purchases) == int else None
            downloads = user_assets.get("purchases")
            downloads = downloads if type(downloads) == int else None

            api_rc._addon.user.count_assets_owned = purchases
            api_rc._addon.user.count_assets_downloads = downloads

        primary_dcc = user_data.get("primary_3d_software")
        primary_dcc = None if not primary_dcc else primary_dcc
        primary_renderer = user_data.get("primary_rendering_engine")
        primary_renderer = None if not primary_renderer else primary_renderer

        api_rc._addon.user.primary_3d_software = primary_dcc
        api_rc._addon.user.primary_rendering_engine = primary_renderer

        api_rc._addon.login_error = None

    def _evaluate_result_credits(self, api_rc, result: Dict) -> None:
        credits = result.body.get("credits", {})
        api_rc._addon.user.credits = credits.get("subscription_balance")
        api_rc._addon.user.credits_od = credits.get("ondemand_balance")
        # TODO(Andreas): Maybe we should consider usig this?
        # self.user.credits_avail = credits.get("available_balance")

    def _evaluate_result_subscription(self, api_rc, result: Dict) -> None:
        plan = result.body.get("subscription", {})
        api_rc._addon.user.plan.update_from_dict(plan)

    def _evaluate_result_download_prefs(self, api_rc, job) -> None:
        result = job.result
        download_prefs = result.body.get("download_preferences", {})
        api_rc._addon.user.map_preferences = UserDownloadPreferences(
            download_prefs)

        callback_get_download_prefs_done = api_rc._addon_params.callback_get_download_prefs_done
        if callback_get_download_prefs_done is not None:
            callback_get_download_prefs_done(job)

    def thread_execute(self, api_rc, job) -> None:
        """Executes any get user data jobs in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        job.result = api_rc._addon._api.get_user_info()

    def finish(self, api_rc, job) -> None:
        """Finishes get user data jobs, called from thread_collect."""

        if api_rc.in_shutdown:
            return

        if api_rc._addon.user is None:
            api_rc._addon.user = PoliigonUser(
                user_name=self.user_name,
                user_id=self.user_id,
                plan=PoliigonSubscription(
                    subscription_state=SubscriptionState.NOT_POPULATED))

        if not job.result.ok:
            api_rc._addon.user.credits = None
            api_rc._addon.user.credits_od = None

            error = job.result.error
            api_rc._addon.login_error = error
            api_rc.logger.error(f"get_user_info (me) failed: {error}")
            return

        self._evaluate_result_user(api_rc, job.result)
        self._evaluate_result_credits(api_rc, job.result)
        self._evaluate_result_subscription(api_rc, job.result)
        self._evaluate_result_download_prefs(api_rc, job)

        api_rc._addon.check_onboarding_notice()
        api_rc._addon.upgrade_manager.refresh()

        ok = api_rc._addon.user is not None
        ok &= api_rc._addon.login_error is None
        job.result = ApiResponse(ok=ok, body={}, error="")

        addon_params = api_rc._addon_params

        # Using get user data finish function to check Install event since
        # this is the first step for all addons;
        api_rc._addon.check_install_event()

        if self.do_fetch_plans:
            api_rc.add_job_get_available_plans(
                callback_cancel=None,
                callback_progress=None,
                callback_done=addon_params.callback_get_available_plans,
                force=True
            )
        if self.do_fetch_categories:
            api_rc.add_job_get_categories(
                callback_cancel=None,
                callback_progress=None,
                callback_done=addon_params.callback_get_categories_done,
                force=True
            )
        if self.do_fetch_asset_data:
            api_rc.add_job_get_all_assets(
                library_paths=api_rc._addon.get_library_paths(),
                force_request=False,
                do_my_assets=True,
                callback_cancel=None,
                callback_progress=None,
                callback_done=addon_params.callback_get_asset_done,
                force=True
            )


@dataclass
class ApiJobParamsGetDownloadPrefs(ApiJobParams):
    """Get User Download Preferences."""

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return True

    def __str__(self) -> str:
        return "ApiJobParamsGetDownloadPrefs"

    @staticmethod
    def _fetch_user_maps_preferences(api_rc) -> ApiResponse:
        res = api_rc._addon._api.get_user_info()
        return res

    def thread_execute(self, api_rc, job) -> None:
        """Executes the request for getting Download Preferences."""

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        if api_rc._addon.user is None:
            api_rc.logger.error(
                "User not defined when fetching Download preferences.")
            return

        job.result = self._fetch_user_maps_preferences(api_rc)
        if not job.result.ok:
            api_rc.logger.error(
                f"Error fetching download preferences. {job.result.error}")

    def finish(self, api_rc, job) -> None:
        """Finishes get Download Prefs, and stores in Poliigon User."""

        if api_rc.in_shutdown:
            return

        download_preferences = job.result.body.get("download_preferences")
        if not job.result.ok or download_preferences is None:
            return

        map_preferences = job.result.body.get("download_preferences", {})
        api_rc._addon.user.map_preferences = UserDownloadPreferences(
            map_preferences)


@dataclass
class ApiJobParamsGetAvailablePlans(ApiJobParams):
    """Get User Upgrade Plans."""

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return True

    def __str__(self) -> str:
        return "ApiJobParamsGetAvailablePlans"

    def thread_execute(self, api_rc, job) -> None:
        """Executes the request for getting User's Upgrade Plans."""

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        if api_rc._addon.user is None:
            api_rc.logger.error(
                "User not defined when fetching Available Plans.")
            return

        if api_rc._addon.is_free_user():
            job.ok = True
            job.result = ApiResponse(ok=True,
                                     body={"data": []},
                                     error=("Fetching available plans for "
                                            "free user cancelled."))
            return

        job.result = api_rc._addon._api.get_user_available_plans()
        if not job.result.ok:
            api_rc.logger.error(
                f"Error fetching upgrade Plans. {job.result.error}")

    def finish(self, api_rc, job) -> None:
        """Finishes get Upgrade Plans, and stores in Poliigon User
        Upgrade Manager.
        """

        if api_rc.in_shutdown:
            return

        if not job.result.ok or job.result.body is None:
            api_rc._addon.upgrade_manager.refresh()
            return

        api_rc._addon.upgrade_manager.refresh(job.result.body)

        if api_rc._addon.upgrade_manager.upgrade_plan is not None:
            api_rc.add_job_get_upgrade_plan(
                callback_done=api_rc._addon_params.callback_get_upgrade_plan)


@dataclass
class ApiJobParamsGetUpgradePlan(ApiJobParams):
    """Get Information for Upgrading current Plan."""

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return True

    def __str__(self) -> str:
        return "ApiJobParamsGetUpgradePlan"

    def thread_execute(self, api_rc, job) -> None:
        """Executes the request for getting Information for Upgrading current
        Plan.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        if api_rc._addon.user is None:
            api_rc.logger.error(
                "User not defined when getting Upgrade Plan info.")
            return
        upgrade_manager = api_rc._addon.upgrade_manager
        if upgrade_manager.upgrade_plan is None:
            api_rc.logger.error(
                "Upgrade plan not defined when getting Upgrade Plan info.")
            return

        to_upgrade_plan_id = upgrade_manager.upgrade_plan.plan_price_id
        job.result = api_rc._addon._api.get_upgrade_plan(to_upgrade_plan_id)

        if not job.result.ok:
            api_rc.logger.error(
                f"Error getting Upgrading Plan to {to_upgrade_plan_id}. {job.result.error}")

    def finish(self, api_rc, job) -> None:
        """Finishes get Upgrade Plan, and stores Upgrade information."""

        if api_rc.in_shutdown:
            return

        if not job.result.ok or job.result.body is None:
            if api_rc._addon.user is not None:
                info = PoliigonPlanUpgradeInfo(
                    ok=False, error=job.result.error)
                api_rc._addon.upgrade_manager.upgrade_info = info
            return

        info = PoliigonPlanUpgradeInfo.from_dict(
            job.result.body)
        api_rc._addon.upgrade_manager.upgrade_info = info
        api_rc._addon.upgrade_manager.refresh()


@dataclass
class ApiJobParamsPutUpgradePlan(ApiJobParams):
    """Confirm current Plan Upgrade."""

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return True

    def __str__(self) -> str:
        return "ApiJobParamsPutUpgradePlan"

    def thread_execute(self, api_rc, job) -> None:
        """Executes the request for confirming the Upgrade of the current
        Plan.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return
        if api_rc._addon.user is None:
            api_rc.logger.error(
                "User not defined when confirming Upgrade Plan.")
            return
        if api_rc._addon.upgrade_manager.upgrade_plan is None:
            api_rc.logger.error(
                "Upgrade plan not defined when confirming Upgrade Plan.")
            return

        to_upgrade_plan_id = api_rc._addon.upgrade_manager.upgrade_plan.plan_price_id
        job.result = api_rc._addon._api.put_upgrade_plan(to_upgrade_plan_id)

        if not job.result.ok:
            api_rc.logger.error(
                f"Error confirming Plan Upgrade. {job.result.error}")

    def finish(self, api_rc, job) -> None:
        """Finishes put Upgrade Plan."""
        if api_rc.in_shutdown:
            return

        if not job.result.ok or job.result.body is None:
            return

        new_plan_details = job.result.body.get("subscription")
        plan_info = PoliigonSubscription()
        plan_info.update_from_dict(new_plan_details)
        api_rc._addon.user.plan = plan_info

        api_rc.add_job_get_available_plans(
            callback_done=api_rc._addon_params.callback_get_available_plans)

        api_rc.add_job_get_user_data(
            api_rc._addon.user.user_name,
            api_rc._addon.user.user_id,
            callback_cancel=None,
            callback_progress=None,
            do_fetch_asset_data=not api_rc._addon.all_assets_fetched,
            callback_done=api_rc._addon_params.callback_get_user_data_done,
            force=True
        )


@dataclass
class ApiJobParamsResumePlan(ApiJobParams):
    """Get Information for Resuming paused Plan or remove cancellation."""

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return True

    def __str__(self) -> str:
        return "ApiJobParamsResumePlan"

    def thread_execute(self, api_rc, job) -> None:
        """Executes the request for Resume current Plan."""

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        if api_rc._addon.user is None or api_rc._addon.upgrade_manager is None:
            api_rc.logger.error("User not defined when resuming Plan.")
            return

        upgrade_status = api_rc._addon.upgrade_manager.status
        if upgrade_status == PlanUpgradeStatus.RESUME_PLAN:
            job.result = api_rc._addon._api.resume_paused_plan()
        elif upgrade_status == PlanUpgradeStatus.REMOVE_SCHEDULED_PAUSE:
            job.result = api_rc._addon._api.remove_scheduled_paused_plan()
        elif upgrade_status == PlanUpgradeStatus.REMOVE_CANCELLATION:
            job.result = api_rc._addon._api.remove_cancellation_plan()
        else:
            msg = "Invalid Plan Status for resuming."
            api_rc.logger.error(msg)
            job.result.error = msg
            return

        if not job.result.ok:
            api_rc.logger.error(
                f"Error resuming Plan. {job.result.error}")

    def finish(self, api_rc, job) -> None:
        """Finishes get Upgrade Plan, and stores Upgrade information."""

        if api_rc.in_shutdown:
            return

        if not job.result.ok or job.result.body is None:
            return

        payload = job.result.body.get("payload", {})
        subscription_details = payload.get("subscriptionDetails")
        if subscription_details is not None:
            api_rc._addon.user.plan.update_from_dict(subscription_details)

        # Refreshing Upgrade Manager - and only the content success popup with
        # the new data for Subscription Details after resuming
        # (new renewal date)
        api_rc._addon.upgrade_manager.refresh(only_resume_popup=True)

        api_rc.add_job_get_user_data(
            api_rc._addon.user.user_name,
            api_rc._addon.user.user_id,
            callback_cancel=None,
            callback_progress=None,
            do_fetch_asset_data=not api_rc._addon.all_assets_fetched,
            callback_done=api_rc._addon_params.callback_get_user_data_done,
            force=True
        )


@dataclass
class ApiJobParamsGetAssets(ApiJobParams):
    """Get Assets specific parameters"""

    library_paths: List[str]
    tab: str  # KEY_TAB_ONLINE or KEY_TAB_MY_ASSETS
    category_list: List[str] = field(default_factory=lambda: [CATEGORY_ALL])
    search: str = ""
    idx_page: int = 1
    page_size: Optional[int] = None
    force_request: bool = False
    do_get_all: bool = True
    do_my_assets: bool = False
    # Not exactly parameters, more results, may be used in callback_done
    already_in_index: bool = False
    asset_id_list: List[int] = field(default_factory=lambda: [])

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return self.tab == other.tab and \
            self.category_list == other.category_list and \
            self.search == other.search and \
            self.idx_page == other.idx_page and \
            self.page_size == other.page_size and \
            self.force_request == other.force_request and \
            self.do_get_all == other.do_get_all and \
            self.do_my_assets == other.do_my_assets

    def __str__(self) -> str:
        # No library paths in here, as the string might be reported to server!
        return (
            "ApiJobParamsGetAssets - "
            f"tab: {self.tab}, cat_list: {self.category_list}, "
            f"search: {self.search}, idx_page: {self.idx_page}, "
            f"page_size: {self.page_size}, force: {self.force_request}, "
            f"do_get_all: {self.do_get_all}, do_my_assets: {self.do_my_assets}, "
            f"already_in_index: {self.already_in_index}, "
            f"asset_id_list: {self.asset_id_list}"
        )

    def _get_key(self, overwrite_tab: Optional[str] = None) -> str:
        """Returns search key for this job."""

        tab = self.tab
        if overwrite_tab is not None:
            tab = overwrite_tab

        return get_search_key(tab, self.search, self.category_list)

    def _determine_page_size(self, api_rc) -> None:
        """Determines 'get asset' page size from API RC's addon parameters."""

        if self.page_size is not None:
            return

        addon_params = api_rc._addon_params
        if self.tab == KEY_TAB_ONLINE:
            self.page_size = addon_params.online_assets_chunk_size
        elif self.tab in [KEY_TAB_MY_ASSETS,
                          KEY_TAB_LOCAL,
                          KEY_TAB_RECENT_DOWNLOADS]:
            self.page_size = addon_params.my_assets_chunk_size
        else:
            msg = f"Job 'Get Assets': Unknown tab {self.tab}"
            api_rc.logger.error(msg)
            api_rc._addon._api.report_message(
                "get_assets_failed_other", msg, "warning")
            self.page_size = 10  # arbitrary size

    def _is_toplevel_request(self) -> bool:
        """Returns True, if this job is a top level (no search or category)
        request.
        """

        if self.search != "":
            return False
        elif self.category_list != [CATEGORY_ALL]:
            return False
        return True

    def _get_asset_ids_from_body(self, job) -> List[int]:
        """Returns list of asset IDs for all innvolved request types
        (search, category, my assets, online assets, ...).
        """

        asset_id_list = []
        if "asset_ids" in job.result.body:
            asset_id_list = job.result.body.get("asset_ids", [])
        elif "data" in job.result.body:
            asset_id_list = job.result.body.get("data", [])
        return asset_id_list

    def thread_execute(self, api_rc, job) -> None:
        """Executes a get assets job in a thread,
        started from thread_schedule.
        """

        if self.is_my_assets_top_level():
            api_rc._addon.my_assets_fetched = False
        elif self.is_recent_downloads_top_level():
            api_rc._addon.recent_downloads_fetched = False

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        # Get Assets should only be called after all assets are fetched
        # (Changed with API v2 "get all assets" (/all) endpoint)
        if not api_rc._addon.all_assets_fetched:
            job.result = ApiResponse(ok=False,
                                     body={"data": []},
                                     error="Dependency requests not done yet.")

        is_toplevel = self._is_toplevel_request()
        key = self._get_key()
        api_rc.logger.debug(f"Cat/search change: {key}")

        self._determine_page_size(api_rc)

        query_exists = api_rc._asset_index.query_exists(
            key, self.idx_page, self.page_size)
        if query_exists and not self.force_request:
            self.already_in_index = True
            job.result = ApiResponse(ok=True,
                                     body={"data": []},
                                     error="job cancelled, query exists")
            return

        if is_toplevel:
            if self.tab == KEY_TAB_MY_ASSETS:
                job.result = api_rc._api.get_user_assets()
            elif self.tab == KEY_TAB_RECENT_DOWNLOADS:
                job.result = api_rc._api.get_user_assets(recent_downloads=True)
            elif self.tab == KEY_TAB_LOCAL:
                check_purchased = None if api_rc._addon.is_unlimited_user() else True
                local_ids = api_rc._asset_index.get_asset_id_list(local=True,
                                                                  purchased=check_purchased,
                                                                  check_map_prefs=True)
                job.result = ApiResponse(ok=True,
                                         body={"asset_ids": local_ids},
                                         error="")
            else:
                # TODO(Joao): Remove this get_assets_NEW call here, All Assets
                #  queries should never get here once the assets were already
                #  fetched by get all assets;
                # During normal operation this case should not be in use,
                # currently.
                # Basically we are using the "get all" job to populate
                # AssetIndex and from then on, the above three cases should be
                # all that's needed.
                # Yet, I opted to keep this case here, as it may come in handy
                # for example to just check the first n new assets, e.g. to
                # find out if we need more updates.
                msg = f"get_assets() aka '/new' endpoint\n    {str(self)}"
                api_rc.logger.warning(msg)
                api_rc._api.report_message(
                    "unexpected_new_endpoint", msg, "error")

                job.result = api_rc._api.get_assets_NEW(
                    idx_page=self.idx_page, size_page=self.page_size)
        else:
            if self.category_list != [CATEGORY_ALL]:
                path_category = "/".join(self.category_list)
                path_category = path_category.replace(" ", "-").lower()
                job.result = api_rc._api.get_category_assets(
                    path_category=path_category)
            elif self.search != "":
                job.result = api_rc._api.search_assets(
                    search_term=self.search,
                    idx_page=self.idx_page,
                    size_page=self.page_size)
            else:
                msg = f"Unexpected case\n    {str(self)}"
                api_rc.logger.error(msg)
                api_rc._api.report_message(
                    "get_assets_unexpected_case", msg, "error")

                job.result = ApiResponse(
                    ok=False,
                    body={"data": []},
                    error=("Unexpected case, no endpoint to choose."))

    def _filter_by_known_asset_ids(
            self, api_rc, asset_ids: List[int]) -> List[int]:
        """Filters list of asset IDs to contain only known asset IDs.

        For example in cases where a user owns a Substance, the list of
        'my asset IDs' might contzain asset IDs we do not have i asset index.
        """

        asset_ids_all = api_rc._asset_index.all_assets.keys()
        asset_ids_filtered = [_asset_id
                              for _asset_id in asset_ids
                              if _asset_id in asset_ids_all]
        return asset_ids_filtered

    def _finish_toplevel_requests(self, api_rc, job) -> List[int]:
        """Finalizes online or my assets top level (nno search or category)
        requests.
        """

        key = self._get_key()
        is_later_page = self.idx_page > 1

        if self.tab == KEY_TAB_MY_ASSETS or self.tab == KEY_TAB_RECENT_DOWNLOADS:
            # Response of get_user_assets() ('/assets/list/ids' endpoint)
            # Received all My Assets IDs, we just need to store them
            asset_ids_resp = self._get_asset_ids_from_body(job)
            asset_ids_resp = self._filter_by_known_asset_ids(
                api_rc, asset_ids_resp)

            for _asset_id in asset_ids_resp:
                api_rc._asset_index.mark_purchased(_asset_id)
                # TODO(Joao): Adapt all addon UIs to work with the
                #  is_recent_downloaded flag. For simplicity the Recent Downloads
                #  assets are being set as purchased AND recent downloaded
                if self.tab == KEY_TAB_RECENT_DOWNLOADS:
                    api_rc._asset_index.mark_recent_downloaded(_asset_id)

            api_rc._asset_index.store_query(
                asset_ids_resp,
                key,
                IDX_PAGE_ACCUMULATED,
                PAGE_SIZE_ACCUMULATED)
        elif self.tab == KEY_TAB_LOCAL:
            asset_ids_resp = self._get_asset_ids_from_body(job)
            api_rc._asset_index.store_query(
                asset_ids_resp,
                key,
                IDX_PAGE_ACCUMULATED,
                PAGE_SIZE_ACCUMULATED)
        else:
            # Response of get_assets() ('/new' endpoint)
            asset_ids_resp = api_rc._asset_index.populate_assets(
                job.result,
                key,
                IDX_PAGE_ACCUMULATED,
                PAGE_SIZE_ACCUMULATED,
                append_query=is_later_page)

        return asset_ids_resp

    def _filter_by_user_assets(self, api_rc, asset_ids_resp: List[int]):
        query_key_all_user_assets = (
            self.tab,
            None,
            None,
            None,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED)

        try:
            asset_ids_my_assets = api_rc._asset_index.cached_queries[
                query_key_all_user_assets]
        except KeyError:
            asset_ids_my_assets = []

        asset_ids_filtered = [_asset_id
                              for _asset_id in asset_ids_my_assets
                              if _asset_id in asset_ids_resp]
        return asset_ids_filtered

    def _filter_for_tabs(self,
                         api_rc,
                         asset_ids_resp: List[int],
                         key: str,
                         is_later_page: bool):
        asset_ids_filtered = []
        if self.tab in [KEY_TAB_MY_ASSETS, KEY_TAB_RECENT_DOWNLOADS]:
            asset_ids_filtered = self._filter_by_user_assets(api_rc, asset_ids_resp)
        elif self.tab == KEY_TAB_LOCAL:
            check_purchased = None if api_rc._addon.is_unlimited_user() else True
            local_ids = api_rc._asset_index.get_asset_id_list(local=True,
                                                              purchased=check_purchased)
            asset_ids_filtered = [_asset_id
                                  for _asset_id in asset_ids_resp
                                  if _asset_id in local_ids]
        api_rc._asset_index.store_query(
            asset_ids_filtered,
            key,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED,
            do_append=is_later_page)  # search can result in multiple pages

        return asset_ids_filtered

    def _finish_category_search_requests(self, api_rc, job) -> List[int]:
        key = self._get_key()
        is_later_page = self.idx_page > 1

        # Response of either get_category_assets() ('/category/results'
        # endpoint) or search_assets() (Algolia endpoint).
        asset_ids_resp = self._get_asset_ids_from_body(job)

        # These endpoints only deliver online results, so we can store the
        # response for Online tab right away.
        key_online = get_search_key(
            KEY_TAB_ONLINE, self.search, self.category_list)
        api_rc._asset_index.store_query(
            asset_ids_resp,
            key_online,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED,
            do_append=is_later_page)  # search can result in multiple pages

        # If tab is Online, no filter is needed
        if self.tab == KEY_TAB_ONLINE:
            return asset_ids_resp
        else:
            return self._filter_for_tabs(api_rc,
                                         asset_ids_resp,
                                         key,
                                         is_later_page)

    def is_my_assets_top_level(self) -> bool:
        return self._is_toplevel_request() and self.tab == KEY_TAB_MY_ASSETS

    def is_recent_downloads_top_level(self) -> bool:
        return self._is_toplevel_request() and self.tab == KEY_TAB_RECENT_DOWNLOADS

    def finish(self, api_rc, job) -> None:
        """Finishes get asset jobs, called from thread_collect."""

        if self.is_my_assets_top_level():
            api_rc._addon.my_assets_fetched = True
        elif self.is_recent_downloads_top_level():
            api_rc._addon.recent_downloads_fetched = True

        if api_rc.in_shutdown:
            return

        if not job.result.ok or self.already_in_index:
            return

        key = self._get_key()
        is_toplevel = self._is_toplevel_request()

        api_rc.logger.debug(f"Cat/search change FINISHED: {key}")

        if is_toplevel:
            asset_ids_resp = self._finish_toplevel_requests(api_rc, job)
        else:
            asset_ids_resp = self._finish_category_search_requests(api_rc, job)

        api_rc._asset_index.store_query(
            asset_ids_resp, key, self.idx_page, self.page_size)

        # Store asset ID list for potential use in done callback
        self.asset_id_list = asset_ids_resp
        user_assets_tabs = self.tab in [KEY_TAB_MY_ASSETS,
                                        KEY_TAB_RECENT_DOWNLOADS]

        if user_assets_tabs or api_rc._addon.is_unlimited_user():
            filter_id_list = self.asset_id_list
            if api_rc._addon.is_unlimited_user():
                # TODO(Joao): Implement it in a way that the benefit of filtering
                #  asset id list also works for unlimited users
                filter_id_list = None
            api_rc._asset_index.update_all_local_assets(
                self.library_paths, asset_id_list=filter_id_list)

        if self.tab == KEY_TAB_MY_ASSETS:
            return

        job_is_done = self.idx_page >= job.result.body.get("total_pages", -1)

        if not self.do_get_all or job_is_done:
            # With API V2 we get asset data either via 'new' or via 'all'
            # endpoints, only. All other endpoints (category, search, ...)
            # deliver lists of Asset IDs, which rely on AssetIndex already
            # populated.
            # So, we can only start requesting my assets, after we have
            # complete asset data.
            if self.do_my_assets:
                api_rc.add_job_get_assets(
                    library_paths=self.library_paths,
                    tab=KEY_TAB_MY_ASSETS,
                    category_list=[CATEGORY_ALL],
                    search="",
                    idx_page=1,
                    page_size=self.page_size,
                    force_request=self.force_request,
                    do_get_all=self.do_get_all,
                    do_my_assets=False,  # We are already fetching my assets
                    callback_cancel=None,
                    callback_progress=None,
                    callback_done=job.callback_done,
                    force=True
                )
            return

        api_rc.add_job_get_assets(
            library_paths=self.library_paths,
            tab=self.tab,
            category_list=self.category_list,
            search=self.search,
            idx_page=self.idx_page + 1,
            page_size=self.page_size,
            force_request=self.force_request,
            do_get_all=self.do_get_all,
            do_my_assets=self.do_my_assets,
            callback_cancel=None,
            callback_progress=None,
            callback_done=job.callback_done,
            force=True)


@dataclass
class ApiJobParamsGetAllAssets(ApiJobParams):
    library_paths: List[str]
    force_request: bool = False
    do_my_assets: bool = False
    # Not exactly parameters, rather constants for comaptibility with existing
    # done callbacks.
    tab: str = KEY_TAB_ONLINE
    category_list: List[str] = field(default_factory=lambda: [CATEGORY_ALL])
    search: str = ""
    idx_page: int = 1
    # page_size: Any value should do, as this job is not actually paged
    page_size: Optional[int] = 500
    # Not exactly parameters, more results, may be used in callback_done
    already_in_index: bool = False
    asset_id_list: List[int] = field(default_factory=lambda: [])

    all_assets_key = get_search_key(KEY_TAB_ONLINE, "", [CATEGORY_ALL])
    unpublished_assets_key = get_search_key(KEY_TAB_UNPUBLISHED, "", [CATEGORY_ALL])

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return self.force_request == other.force_request and \
            self.do_my_assets == other.do_my_assets

    def __str__(self) -> str:
        # No library paths in here, as the string might be reported to server!
        return (
            "ApiJobParamsGetAllAssets - "
            f"force: {self.force_request}, do_my_assets: {self.do_my_assets}"
            f"asset_id_list: {self.asset_id_list}"
        )

    def thread_execute(self, api_rc, job) -> None:
        """Executes a get assets job in a thread,
        started from thread_schedule.
        """
        api_rc._addon.all_assets_fetched = False
        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        query_exists = api_rc._asset_index.query_exists(self.all_assets_key,
                                                        IDX_PAGE_ACCUMULATED,
                                                        PAGE_SIZE_ACCUMULATED)
        if query_exists and not self.force_request:
            self.already_in_index = True
            job.result = ApiResponse(ok=True,
                                     body={"data": []},
                                     error="job cancelled, query exists")
            return

        job.result = api_rc._api.get_all_assets()

        # TODO(Andreas): ==> api.py
        # For compatibility with existing Done callbacks, which try to
        # determine, if it was the last page. Which it always is in this case.
        # job.result.body["last_page"] = self.idx_page

    def _filter_upublished_assets(
            self, job) -> Tuple[ApiResponse, ApiResponse]:
        asset_dict_list = job.result.body.get("data", [])
        asset_dicts_published = []
        asset_dicts_unpublished = []

        resp_published = ApiResponse(
            ok=job.result.ok,
            body=job.result.body,
            error=job.result.error)
        resp_unpublished = ApiResponse(
            ok=job.result.ok,
            body=job.result.body.copy(),
            error=job.result.error)

        cnt_published = 0
        cnt_unpublished = 0
        for _asset_dict in asset_dict_list:
            release_status = _asset_dict.get("ReleaseStatus", "")
            if release_status == "Unpublished":
                cnt_unpublished += 1
                asset_dicts_unpublished.append(_asset_dict)
            else:
                cnt_published += 1
                asset_dicts_published.append(_asset_dict)

        resp_published.body["data"] = asset_dicts_published
        resp_published.body["total"] = len(asset_dicts_published)
        resp_unpublished.body["data"] = asset_dicts_unpublished
        resp_unpublished.body["total"] = len(asset_dicts_unpublished)

        return resp_published, resp_unpublished

    def finish(self, api_rc, job) -> None:
        """Finishes get asset jobs, called from thread_collect."""

        api_rc._addon.all_assets_fetched = True

        if api_rc.in_shutdown:
            return

        if not job.result.ok or self.already_in_index:
            return

        api_rc.logger.debug(f"All assets FINISHED: {self.all_assets_key}")

        resp_published, resp_unpublished = self._filter_upublished_assets(job)
        job.result = resp_published

        asset_ids_published = api_rc._asset_index.populate_assets(
            resp_published,
            self.all_assets_key,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED,
            append_query=False)

        asset_ids_unpublished = api_rc._asset_index.populate_assets(
            resp_unpublished,
            self.unpublished_assets_key,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED,
            append_query=False)

        asset_id_list = asset_ids_published + asset_ids_unpublished

        # Store a virtual first page, so we do not get get_assets() requests
        # just from returning to All Assets on Online tab.
        page_size = api_rc._addon_params.online_assets_chunk_size
        api_rc._asset_index.store_query(asset_id_list, self.all_assets_key, 1, page_size)

        # Store asset ID list for potential use in done callback
        #  self.asset_id_list = asset_id_list
        self.asset_id_list = asset_ids_published

        # With API V2 we get asset data either via 'new' or via 'all'
        # endpoint.
        # In either case, we can only start requesting my assets (now,
        # nicely being only a list of IDs), after we have complete asset
        # data.
        if not self.do_my_assets:
            return

        api_rc.add_job_get_assets(
            library_paths=self.library_paths,
            tab=KEY_TAB_RECENT_DOWNLOADS,
            category_list=[CATEGORY_ALL],
            search="",
            idx_page=1,
            page_size=page_size,
            force_request=self.force_request,
            do_get_all=True,
            do_my_assets=False,
            callback_cancel=None,
            callback_progress=None,
            callback_done=job.callback_done,
            force=True
        )

        if api_rc._addon.user_legacy_own_assets():
            # Do not use the page size from this "All Assets" job, as it is faked
            # for compatibility reasons.
            page_size = api_rc._addon_params.my_assets_chunk_size
            api_rc.add_job_get_assets(
                library_paths=self.library_paths,
                tab=KEY_TAB_MY_ASSETS,
                category_list=[CATEGORY_ALL],
                search="",
                idx_page=1,
                page_size=page_size,
                force_request=self.force_request,
                do_get_all=True,
                do_my_assets=False,  # This is the "my assets" request
                callback_cancel=None,
                callback_progress=None,
                callback_done=job.callback_done,
                force=True
            )


@dataclass
class ApiJobParamsDownloadThumb(ApiJobParams):
    """Download Thumb specific parameters"""

    asset_id: int
    url: str
    path: str
    do_update: bool = False
    skip_download: bool = False
    idx_thumb: int = -1

    POOL_KEY = PoolKeys.PREVIEW_DL

    def __eq__(self, other):
        return self.url == other.url

    def __str__(self) -> str:
        # No paths in here, as the string might be reported to server!
        return (
            "ApiJobParamsDownloadThumb - "
            f"asset_id: {self.asset_id}, url: {self.url}, "
            f"do_update: {self.do_update}, skip_download: {self.skip_download}"
        )

    def thread_execute(self, api_rc, job) -> None:
        """Executes a download thumb job in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        if not self.do_update and os.path.exists(self.path):
            job.result = ApiResponse(ok=True, body={}, error="")
            return

        try:
            self.skip_download = job.callback_progress(downloading=True,
                                                       job=job)
        except TypeError:
            self.skip_download = False

        if self.skip_download:
            job.result = ApiResponse(ok=True, body={}, error="")
            return

        path_download = f"{self.path}_dl"

        job.result = api_rc._api.download_preview(self.url, path_download)

        # TODO(Andreas): error reporting,
        try:
            if os.path.exists(path_download):
                if os.path.exists(self.path):
                    os.remove(self.path)
                os.rename(path_download, self.path)
        except OSError:  # TODO(Andreas)
            api_rc.logger.exception(f"### rename exc: {self.path}")

    def finish(self, api_rc, job) -> None:
        """Finishes download thumb jobs, called from thread_collect."""

        if api_rc.in_shutdown:
            return

        if self.skip_download:
            return
        try:
            job.callback_progress(downloading=False, job=job)
        except TypeError:
            pass  # nothing to do

        if os.path.isfile(f"{self.path}_temp"):
            os.remove(f"{self.path}_temp")


@dataclass
class ApiJobParamsPurchaseAsset(ApiJobParams):
    """Asset purchase specific parameters"""

    asset_data: AssetData
    category_list: List[str] = field(default_factory=lambda: [CATEGORY_ALL])
    search: str = ""
    # An optional follow-up download job
    job_download: Optional = None  # type ApiJob

    POOL_KEY = PoolKeys.INTERACTIVE

    def __eq__(self, other):
        return self.asset_data.asset_id == other.asset_data.asset_id

    def __str__(self) -> str:
        return (
            "ApiJobParamsPurchaseAsset - "
            f"asset_data (id): {self.asset_data.asset_id}, "
            f"cat_list: {self.category_list}, "
            f"search: {self.search}, job_download: {self.job_download}"
        )

    def _get_category_slug(self) -> str:
        """Gets the slug format of the active category.
        E.g.:
        from ["All Models"] to "/"
        from ["Models", "Bathroom"] to "/models/bathroom"
        and undo transforms of f_GetCategoryChildren.
        """

        # TODO(related to SOFT-762 and SOFT-598):
        #      Refactor f_GetCategoryChildren as part of Core migration.
        category_slug = "/" + "/".join(
            [cat.lower().replace(" ", "-") for cat in self.category_list]
        )
        if category_slug == "/all-assets":
            category_slug = "/"
        return category_slug

    def thread_execute(self, api_rc, job) -> None:
        """Executes a purchase asset job in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        asset_data = self.asset_data
        asset_id = asset_data.asset_id

        search = self.search.lower()
        category_slug = self._get_category_slug()

        asset_data.state.purchase.start()
        job.result = api_rc._api.purchase_asset(
            asset_id, search, category_slug)

    def finish(self, api_rc, job) -> None:
        """Finishes purchase asset jobs, called from thread_collect."""

        if api_rc.in_shutdown:
            return

        asset_data = self.asset_data
        asset_id = asset_data.asset_id
        if job.result.ok:
            api_rc._asset_index.mark_purchased(asset_id)
            if self.job_download is not None:
                api_rc.enqueue_job(self.job_download)
        else:
            asset_data.state.purchase.set_error(error_msg=job.result.error)
            # See comment in ApiRemoteControl.create_job_download_asset()
            # In order to guarantee immediate feedback to user, the download
            # state already gets set upon creation of the follow-up
            # auto-download job. But this wont be executed in case of a
            # purchase error. Thus the flag needs to be reset, here.
            asset_data.state.dl.end()
            err = job.result.body.get("error", job.result.error)
            api_rc.logger.error((f"Failed to purchase asset {asset_id}"
                                 f"\nerror: {err}"
                                 f"\nbody: {job.result.body}"))
            if ERR_NOT_ENOUGH_CREDITS not in err:
                # "Not enough credits" is already reported earlier
                api_rc._addon._api.report_message(
                    "purchase_failed_other", f"{asset_id}: {err}", "error")

        asset_data.state.purchase.end()

        api_rc._asset_index.flush_queries_by_tab(KEY_TAB_MY_ASSETS)

        # By requesting user data multiple follow up jobs get kicked off
        # (besides updating credits):
        # - Update plan upgrade data
        api_rc.add_job_get_user_data(
            api_rc._addon.user.user_name,
            api_rc._addon.user.user_id,
            do_fetch_plans=True,
            do_fetch_categories=False,
            do_fetch_asset_data=False,
            callback_cancel=None,
            callback_progress=None,
            callback_done=api_rc._addon_params.callback_get_user_data_done,
            force=True
        )

        # Before API V2 we had the "get user data" job do a final "get assets",
        # which implied fetching a fresh "my assets" and "downloads" cache.
        # As a small optimization, we now skip fetching assets within
        # "get user data", but we still need a fresh "my assets" cache.
        page_size = api_rc._addon_params.my_assets_chunk_size
        api_rc.add_job_get_assets(
            library_paths=api_rc._addon.get_library_paths(),
            tab=KEY_TAB_RECENT_DOWNLOADS,
            category_list=[CATEGORY_ALL],
            search="",
            idx_page=1,
            page_size=page_size,
            force_request=True,
            do_get_all=True,
            do_my_assets=False,
            callback_cancel=None,
            callback_progress=None,
            callback_done=api_rc._addon_params.callback_get_asset_done,
            force=True
        )

        if api_rc._addon.user_legacy_own_assets():
            api_rc.add_job_get_assets(
                library_paths=api_rc._addon.get_library_paths(),
                tab=KEY_TAB_MY_ASSETS,
                category_list=[CATEGORY_ALL],
                search="",
                idx_page=1,
                page_size=page_size,
                force_request=True,
                do_get_all=True,
                do_my_assets=False,  # This is the "my assets" request
                callback_cancel=None,
                callback_progress=None,
                callback_done=api_rc._addon_params.callback_get_asset_done,
                force=True
            )


@dataclass
class ApiJobParamsDownloadAsset(ApiJobParams):
    """Asset download specific parameters"""

    download: AssetDownload
    asset_data: AssetData
    size: str
    size_bg: str = ""
    type_bg: str = "EXR"

    # Lods are currently not being used in the AssetDownload class,
    # if download_lods is True, then all available lods will be added to
    # the download payload.
    lods: Optional[List[str]] = None

    variant: str = ""
    download_lods: bool = False
    native_mesh: bool = True
    renderer: str = ""

    POOL_KEY = PoolKeys.ASSET_DL

    def __eq__(self, other):
        return self.asset_data.asset_id == other.asset_data.asset_id and \
            self.size == other.size and \
            self.size_bg == other.size_bg and \
            self.type_bg == other.type_bg and \
            self.lods == other.lods and \
            self.variant == other.variant

    def __str__(self) -> str:
        return (
            "ApiJobParamsDownloadAsset - "
            f"download: {self.download}, size: {self.size}, "
            f"size_bg: {self.size_bg}, type_bg: {self.type_bg}, "
            f" variant: {self.variant}, download_lods: {self.download_lods}, "
            f"native_mesh: {self.native_mesh}, renderer: {self.renderer}"
        )

    def _init_download_data_callback(self, api_rc):
        # This get_assets callback is automatically triggered when downloading
        # an asset (after the download data is requested from the API), due to
        # the new /downloads asset filter.
        # This way, the /downloads filter gets updated without needing
        # to wait for the actual download to finish.
        #
        # NOTE: No callback should be called for this get assets job;

        query_key_downloads = (
            KEY_TAB_RECENT_DOWNLOADS,
            None,
            None,
            None,
            IDX_PAGE_ACCUMULATED,
            PAGE_SIZE_ACCUMULATED)

        try:
            downloads_assets = api_rc._asset_index.cached_queries[query_key_downloads]
        except KeyError:
            downloads_assets = []

        # If the asset being downloaded is already on /downloads, there is no
        # reason to proceed with the request;
        if self.asset_data.asset_id in downloads_assets:
            return

        api_rc._asset_index.flush_queries_by_tab(KEY_TAB_RECENT_DOWNLOADS)
        api_rc.add_job_get_assets(
            library_paths=api_rc._addon.get_library_paths(),
            tab=KEY_TAB_RECENT_DOWNLOADS,
            category_list=[CATEGORY_ALL],
            search="",
            idx_page=1,
            page_size=None,
            force_request=True,
            do_get_all=True,
            do_my_assets=False,
            callback_cancel=None,
            callback_progress=None,
            callback_done=None,
            # Marking force as False to avoid racing conditions when multiple
            # assets are downloaded in a sequence (if the same job is enqueued,
            # it is not added);
            force=False
        )

    def thread_execute(self, api_rc, job) -> None:
        """Executes an asset download job in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        # Wrap to pass job through api
        try:
            partial_progress = partial(job.callback_progress, job)
        except TypeError:
            # No progress callback
            partial_progress = None

        download_dir = api_rc._addon.get_library_path(primary=True)
        valid_sizes = self.asset_data.get_type_data().get_size_list()
        if self.size not in valid_sizes:
            self.size = api_rc._addon.get_type_default_size(self.asset_data)

        self.download = AssetDownload(
            addon=api_rc._addon,
            asset_data=self.asset_data,
            size=self.size,
            dir_target=download_dir,
            download_lods=self.download_lods,
            native_mesh=self.native_mesh,
            renderer=self.renderer,
            update_callback=partial_progress,
            get_download_data_callback=partial(self._init_download_data_callback,
                                               api_rc)
        )
        result = self.download.kickoff_download()
        job.result = ApiResponse(ok=result,
                                 body={},
                                 error="")

    def finish(self, api_rc, job) -> None:
        """Finishes download asset jobs, called from thread_collect."""

        if api_rc.in_shutdown:
            return

        asset_data = self.asset_data
        asset_id = asset_data.asset_id
        error = asset_data.state.dl.error

        asset_data.state.dl.end()
        if job.result.ok:
            download_dir = asset_data.state.dl.get_directory()
            api_rc._asset_index.update_from_directory(asset_id, download_dir)
            if self.size != "NONE":
                asset_data.runtime.store_current_size(self.size)
            asset_data.state.dl.set_recently_downloaded(True)
        elif error not in [None, ""]:
            job.result.error = asset_data.state.dl.error


@dataclass
class ApiJobParamsDownloadWMPreview(ApiJobParams):
    """Asset download specific parameters"""

    asset_data: AssetData
    renderer: str = ""
    # Not exactly parameters, more results, may be used in callback_done
    files: List[str] = field(default_factory=lambda: [])

    POOL_KEY = PoolKeys.ASSET_DL

    def __eq__(self, other):
        return self.asset_data.asset_id == other.asset_data.asset_id

    def __str__(self) -> str:
        # No files in here, as the string might be reported to server!
        return (
            "ApiJobParamsDownloadWMPreview - "
            f"asset_data (id): {self.asset_data.asset_id}, "
            f"renderer: {self.renderer}"
        )

    def _download_material_wm(self,
                              api_rc: Any,
                              files_to_download: List[Tuple[str, str]]
                              ) -> ApiResponse:
        """Synchronous function to download material preview."""

        urls = []
        files_dl = []
        for _url_wm, _filename_wm_dl in files_to_download:
            urls.append(_url_wm)
            files_dl.append(_filename_wm_dl)

        resp = api_rc._addon._api.pooled_preview_download(urls, files_dl)
        if not resp.ok:
            msg = f"Failed to download WM preview\n{resp}"
            api_rc._addon._api.report_message(
                "download_mat_preview_dl_failed", msg, "error")
            # Continue, as some may have worked.

        for _filename_wm_dl in files_dl:
            filename_wm = _filename_wm_dl[:-3]  # cut of _dl

            try:
                file_exists = os.path.exists(filename_wm)
                dl_exists = os.path.exists(_filename_wm_dl)
                if file_exists and dl_exists:
                    os.remove(filename_wm)
                elif not file_exists and not dl_exists:
                    raise FileNotFoundError
                if dl_exists:
                    os.rename(_filename_wm_dl, filename_wm)
            except FileNotFoundError:
                msg = f"Neither {filename_wm}, nor {_filename_wm_dl} exist"
                api_rc._addon._api.report_message(
                    "download_mat_existing_file", msg, "error")
            except FileExistsError:
                msg = f"File {filename_wm} already exists, failed to rename"
                api_rc._addon._api.report_message(
                    "download_mat_rename", msg, "error")
            except Exception as e:
                api_rc.logger.exception("Unexpected exception while renaming WM preview")
                msg = f"Unexpected exception while renaming {_filename_wm_dl}\n{e}"
                api_rc._addon._api.report_message(
                    "download_wm_exception", msg, "error")
        return resp

    def thread_execute(self, api_rc, job) -> None:
        """Executes an download watermarked preview job in a thread,
        started from thread_schedule.
        """

        if api_rc.in_shutdown:
            job.result = get_shutdown_response()
            return

        path_wm_previews = api_rc._addon.get_wm_download_path(
            self.asset_data.asset_name)

        asset_type_data = self.asset_data.get_type_data()
        urls_wm = asset_type_data.get_watermark_preview_url_list()

        files_to_download = []
        if self.asset_data.is_backplate():
            # TODO(Andreas): Untested branch
            path_wm = os.path.join(path_wm_previews,
                                   self.asset_data.asset_name + "_WM.jpg_dl")
            if not os.path.exists(path_wm):
                files_to_download.append((urls_wm[0], path_wm))
        else:
            try:
                os.makedirs(path_wm_previews, exist_ok=True)
            except BaseException:
                # TODO(Andreas)
                api_rc.logger.exception("Failed to create dir for WM previews")

            for url in urls_wm:
                filename_wm_dl = os.path.basename(url.split("?")[0])
                filename_wm_dl += "_dl"
                # Might need to skip certain maps to improve performance
                # if any(vM in vFName for vM in ['BUMP','DISP']+[f'VAR{i}' for i in range(2,9)]) :
                #    continue

                path_wm = os.path.join(path_wm_previews, filename_wm_dl)
                if not os.path.exists(path_wm):
                    files_to_download.append((url, path_wm))

        if len(files_to_download) > 0:
            job.result = self._download_material_wm(api_rc, files_to_download)
        else:
            job.result = ApiResponse(ok=True, body={}, error="")

    def finish(self, api_rc, job) -> None:
        """Finishes download asset jobs, called from thread_collect."""

        if api_rc.in_shutdown:
            return

        path_wm_previews = api_rc._addon.get_wm_download_path(
            self.asset_data.asset_name)
        asset_id = self.asset_data.asset_id
        api_rc._asset_index.update_from_directory(
            asset_id, path_wm_previews, workflow_fallback="METALNESS")
