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

"""General purpose, pure python interface to Poliigon web APIs and services."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, IntEnum
from http import HTTPStatus
from typing import (
    Callable,
    Dict,
    Optional,
    Sequence,
    Union)
from urllib.request import getproxies
from typing import List, Any
import errno
import json
import os
import requests
import time
import webbrowser


from .env import PoliigonEnvironment
from .logger import AddonLogger, MockLogger
from .multilingual import _m
from .notifications import NotificationSystem


TIMEOUT = 60.05  # Request timeout in seconds (slightly over mult. 3 is ideal)
TIMEOUT_STREAM = 120.05  # Request timeout for download streams
MAX_DL_THREADS = 6
MAX_RETRIES_PER_FILE = 3
MIN_VIEW_SCREEN_INTERVAL = 2.0  # seconds min between screen report calls.

# Enum values to reference
ERR_NOT_AUTHORIZED = _m("Not authorized")
ERR_CONNECTION = _m("Connection error")
ERR_OS_NO_SPACE = _m("No space left on device")
ERR_OS_NO_PERMISSION = _m("Disk permission denied")
ERR_OS_WRITE = _m("Failed to write file")
ERR_UNZIP_ERROR = _m("Error during asset unzip")
ERR_NO_POPULATED = _m("Data not populated in response")
ERR_NO_DL_FILES = _m("No files in download response")
ERR_OTHER = _m("Unknown error occurred")
ERR_INTERNAL = _m("Internal Server Error")
ERR_NOT_ENOUGH_CREDITS = _m("User doesn't have enough credits")
ERR_USER_CANCEL_MSG = _m("User cancelled download")
ERR_OPTED_OUT = _m("Did not send event, user is opted out")
ERR_INVALID_SCREEN_NAME = _m("Invalid screen name")
ERR_INTERVAL_VIEW = _m("Last view was too recent per min interval")
ERR_TIMEOUT = _m("Connection timed out after {} seconds").format(TIMEOUT)
ERR_TIMEOUT_STREAM = _m("Connection timed out after {} seconds").format(TIMEOUT_STREAM)
ERR_NO_TOKEN = _m("Failed to get token from login")
ERR_LOGIN_NOT_INITIATED = _m("Failed to initiate login via website")
ERR_WRONG_CREDS = _m("The email/password provided doesn't match our records, "
                     "please try again.")
ERR_PROXY = _m("Cannot connect due to proxy error")
ERR_MISSING_STREAM = _m("Requests response object missing from stream")
ERR_MISSING_URLS = _m("Requests response object lacking URLs")
ERR_URL_EXPIRED = _m("Download URL expired")
ERR_FILESIZE_MISMATCH = _m("Download filesize mismatch")
ERR_DECODE = _m("Cannot decode response content")
# ERR_SUBSCRIPTION_PAUSED _starts_ with this, it continues something like
# asset ID: ..., which I would recommend to not take into account when
# checking for this error.
ERR_SUBSCRIPTION_PAUSED = _m("You do not have an active subscription.")

# Error for when reached the limit of weekly downloads -
#     only happens for unlimited plans
ERR_LIMIT_DOWNLOAD_RATE = _m("Unlimited Fair Use Exceeded")

MSG_ERR_RECORD_NOT_FOUND = _m("Record not found")

STR_NO_PLAN = _m("No plan active")

# Values exactly matching API responses.
API_NOT_ENOUGH_CREDITS = "insufficient-credits"  # status code 422

# Reusable lists of err constants for which don't warrant reporting.
SKIP_REPORT_ERRS = [
    ERR_CONNECTION,
    ERR_LIMIT_DOWNLOAD_RATE,
    ERR_NOT_AUTHORIZED,
    ERR_PROXY,
    ERR_TIMEOUT]

DOWNLOAD_TEMP_SUFFIX = "dl"

HEADERS_LOGIN = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

URL_BASE = "https://www.poliigon.com"
URL_PATHS = {
    "signup": "/register",
    "account": "/account",
    "subscribe": "/pricing",
    # "forgot": "/reset",  # Disabled after login via email is unavailable
    "credits": "/account?tab=dashboard",
    "privacy": "/privacy",
    "terms": "/terms",
    "unlimited_plan_help": "https://help.poliigon.com/en/articles/10003983-unlimited-plans"
    # Common DCC specific additions
    # "help": "...",
    # "survey": "...",
    # "suggestion": "...",
}


DL_RESPONSETYPE_JSON = "json"
DL_RESPONSETYPE_ZIP = "zip"


# In DCCs use SOFTWARE_NAME_xyz to pass to PoliigonAddon
SOFTWARE_NAME_BLENDER = "blender"
SOFTWARE_DOWNLOAD_NAME_BLENDER = "Blender"
PLATFORM_NAME_BLENDER = "addon-blender"

SOFTWARE_NAME_MAX = "3dsmax"
SOFTWARE_DOWNLOAD_NAME_MAX = "3dsMax"
PLATFORM_NAME_MAX = "addon-3dsmax"

SOFTWARE_NAME_MAYA = "maya"
SOFTWARE_DOWNLOAD_NAME_MAYA = "Maya"
PLATFORM_NAME_MAYA = "addon-maya"

SOFTWARE_NAME_C4D = "cinema4d"
SOFTWARE_DOWNLOAD_NAME_C4D = "Cinema4D"
PLATFORM_NAME_C4D = "addon-cinema4d"

SOFTWARE_NAME_SKETCHUP = "sketchup"
SOFTWARE_DOWNLOAD_NAME_SKETCHUP = "SketchUp"
PLATFORM_NAME_SKETCHUP = "addon-sketchup"

SOFTWARE_NAME_UNREAL = "unreal"
SOFTWARE_DOWNLOAD_NAME_UNREAL = "Generic"
PLATFORM_NAME_UNREAL = "addon-unreal"

SOFTWARE_NAME_TEST = "test_dcc"
SOFTWARE_DOWNLOAD_NAME_TEST = "Generic"
PLATFORM_NAME_TEST = "addon-blender"  # Intentionally use a live one.


class RenderEngines(Enum):
    CYCLES = "Cycles"
    VRAY = "Vray"
    ARNOLD = "Arnold"
    REDSHIFT = "Redshift"
    CORONA = "Corona"
    OCTANE = "Octane"

    OTHER = "Other"
    UNDEFINED = "Undefined"

    @classmethod
    def get_list(cls) -> List:
        return [member.value for member in RenderEngines]

    @classmethod
    def from_renderer_name(cls,
                           renderer_name: Optional[str] = None):
        if renderer_name is not None:
            return cls.renderer_name_mapping(renderer_name)
        return cls.UNDEFINED

    @classmethod
    def default_for_dcc(cls, dcc: str) -> Any:
        if dcc in [SOFTWARE_NAME_BLENDER, SOFTWARE_DOWNLOAD_NAME_BLENDER]:
            return cls.CYCLES
        elif dcc in [SOFTWARE_NAME_MAX, SOFTWARE_DOWNLOAD_NAME_MAX]:
            return cls.ARNOLD
        elif dcc in [SOFTWARE_NAME_C4D, SOFTWARE_DOWNLOAD_NAME_C4D]:
            return cls.REDSHIFT
        else:
            # Other DCCs as Unreal, Maya and Sketchup do not have a default
            # engine to return and, so far, are not using addon-core at all;
            return cls.OTHER

    @classmethod
    def renderer_name_mapping(cls, renderer_name: str) -> Any:
        """All the renderers name mappings for should be contained in this
        function. Feel Free to add any needed mapping here to avoid duplications
        in the dcc code side."""

        map_to_cycles = ["BLENDER_WORKBENCH", "BLENDER_EEVEE"]
        map_to_vray = ["V_RAY", "V-RAY"]
        for _renderer in map_to_cycles:
            if _renderer.lower() in renderer_name.lower():
                return cls.CYCLES

        for _renderer in map_to_vray:
            if _renderer.lower() in renderer_name.lower():
                return cls.VRAY

        for member in RenderEngines:
            if member.value.lower() in renderer_name.lower():
                return member

        return cls.OTHER


def construct_error(url: str, response: str, source: dict) -> str:
    """Create a json string with details about an error.

    Args:
        url: The url of the api endpoint called.
        response: Short message describing the error.
        source: Structure of data sent with the the api request.
    """

    error = {
        "request_url": url,
        "server_response": response,
        "source_request": source
    }

    return json.dumps(error, indent=4)


@dataclass
class ApiResponse:
    """Container object for a response from the Poliigon API."""
    body: Dict  # Contents of the reply in all cases.
    ok: bool  # Did the request complete with a successful result.
    error: str  # Meant to be a short, user-friendly message.
    headers: Dict = None  # The response header, used mostly for testing


class ApiStatus(Enum):
    """Event indicator which parent modules can subscribe to listen for."""
    CONNECTION_OK = 1  # Could connect to API, even if transaction failed.
    NO_INTERNET = 2  # Appears to be no internet.
    PROXY_ERROR = 3  # Appears to be a proxy error.


class DownloadStatus(Enum):
    INITIALIZED = 0
    WAITING = 1
    ONGOING = 2
    CANCELLED = 3
    DONE = 4  # final state
    ERROR = 5  # final state


class DQStatus(IntEnum):
    """Used in download quality tracking, enum symbols get send lower case
    as 'status'.
    """

    SUCCESS = 0
    FAILED = 1
    CANCELED = 2


class PoliigonConnector():
    """Poliigon connector used for integrating with the web API."""

    software_source: str = ""  # e.g. blender
    software_version: str = ""  # e.g. 3.2
    software_dl_dcc: str  # e.g. Blender, to match API download software name
    version_str: str = ""  # e.g. 1.2.3, populated after calling init.
    api_url: str
    token: str = None  # Populated on login/settings read, cleared sans auth.
    login_token: str = None  # Used during login with website
    invalidated: bool = False  # Set true if outdated token detected.
    common_meta: Dict  # Fields to add to all POST requests.
    status: ApiStatus = ApiStatus.CONNECTION_OK
    notification_system: Optional[NotificationSystem] = None
    allow_html: bool = False

    _last_screen_view: int = None  # State to avoid excessive reporting.

    # Injected function to check if opted into tracking.
    # args: This function should take in no arguments
    get_optin: callable

    # Injected function to get the current render engine string.
    get_current_renderer_name: Optional[Callable] = None

    # Injected function for remote reporting.
    # args (message, code_msg, level)
    _report_message: callable

    # Injected, called when the overall API status is changed.
    # args (ApiEvent)
    _status_listener: callable

    _mp_relevant: bool  # mp information in message meta data

    # Injected, called when the API login token is invalidated.
    # args (ApiEvent)
    _on_invalidated: callable = None

    _platform: str = "addon"

    _url_paths: Dict[str, str]

    # For local testing only
    _assetdata_overrides: Dict = {}

    logger: Union[AddonLogger, MockLogger]

    def __init__(self,
                 env: PoliigonEnvironment,
                 software: str,  # use SOFTWARE_NAME_xyz from above
                 api_url: str = "",
                 api_url_v2: str = "",
                 get_optin: Optional[callable] = None,
                 report_message: Optional[callable] = None,
                 status_listener: Optional[callable] = None,
                 mp_relevant: bool = False,
                 logger: Optional[AddonLogger] = None,
                 report_exception: Optional[callable] = None):
        self.software_source = software
        self.api_url = api_url if api_url else env.api_url
        self.api_url_v2 = api_url_v2 if api_url_v2 else env.api_url_v2
        self.get_optin = get_optin
        self._report_message = report_message
        self._report_exception = report_exception
        self._status_listener = status_listener
        self._mp_relevant = mp_relevant
        if logger is not None:
            self.logger = logger
        else:
            self.logger = MockLogger()

        # Update platform to be one of the hard coded API allowable types.
        if software == SOFTWARE_NAME_BLENDER:
            self._platform = PLATFORM_NAME_BLENDER
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_BLENDER
        elif software == SOFTWARE_NAME_MAX:
            self._platform = PLATFORM_NAME_MAX
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_MAX
        elif software == SOFTWARE_NAME_MAYA:
            self._platform = PLATFORM_NAME_MAYA
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_MAYA
        elif software == SOFTWARE_NAME_C4D:
            self._platform = PLATFORM_NAME_C4D
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_C4D
        elif software.lower() == SOFTWARE_NAME_SKETCHUP:
            self._platform = PLATFORM_NAME_SKETCHUP
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_SKETCHUP
        elif software == SOFTWARE_NAME_UNREAL:
            self._platform = PLATFORM_NAME_UNREAL
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_UNREAL
        elif software == SOFTWARE_NAME_TEST:
            # Case used for testing, may be disallowed in the future.
            self._platform = PLATFORM_NAME_TEST
            self.software_dl_dcc = SOFTWARE_DOWNLOAD_NAME_TEST
        else:
            raise ValueError(f"Invalid software selection {software}")

        self._url_paths = URL_PATHS
        self.status_notice = None

        # Load API overrides if a nonproduction environment and dir specified
        if env.config is not None:
            override_dir = env.config.get(
                "DEFAULT", "asset_overrides_dir", fallback=None)
            if env.env_name != "prod" and override_dir is not None:
                self._load_asset_overrides(override_dir)

    def set_status_listener(self, callback: callable) -> None:
        """Set the callback for conection status changes."""

        self._status_listener = callback

    def set_on_invalidated(self, func: Callable) -> None:
        """Set the on_invalidated callback."""

        self._on_invalidated = func

    def register_update(self, addon_v: str, software_v: str) -> None:
        """Run soon after __init__ after app has readied itself.

        Args:
            addon_v: In form "1.2.3"
            software_v: In form "3.2"
        """

        self.version_str = addon_v
        self.software_version = software_v
        self.common_meta = {
            "addon_version": self.version_str,
            "software_name": self.software_source
        }

    def report_message(self,
                       message: str,
                       code_msg: str,
                       level: str,
                       max_reports: int = 10
                       ) -> None:
        """Send a report to a downstream system.

        Forwards to a system if callback configured. Any optin or eligibility
        checks are performed downstream.

        Args:
            message: The unique identifier used for issue-grouping.
            code_msg: More details about the situation.
            level: One of error, warning, info.
            max_reports: Maximum reports sent per message string, zero for all
        """

        if self._report_message is None:
            return
        self._report_message(message, code_msg, level, max_reports)

    def report_exception(self, e) -> None:
        """Send an exception report to a downstream system.

        Forwards to a system if callback configured. Any optin or eligibility
        checks are performed downstream.

        Args:
            e: Exception instance
        """

        if self._report_exception is None:
            return
        self._report_exception(e)

    def _flatten_results(self, resp: Dict) -> Dict:
        """Removes 'results' dict, while keeping all conntained data.

        API responses (almost) always contain one additional level of
        redirection. The info we are interested in is located in a 'results'
        sub-dictionary.
        Herein this results dict gets removed, so we can access the data
        directly.
        """

        if "results" not in resp:
            return resp

        results = resp["results"]
        if type(results) is not dict:
            # Happens with event signals, where results is an empty list
            # TODO(Andreas): Left the print here, as API V2 is still in flux
            #                in certain ways. Maybe this case can be removed
            #                completely, later.
            #                It would certainly be nice, of all responses had
            #                the same structure.
            print("RESULTS NOT DICT (signal_event?)")
            return resp

        for _key in resp:
            if _key == "results":
                continue
            if _key in results:
                # TODO(Andreas): This can likely be removed. During development
                #                I wanted to make sure, this case does not
                #                happen (I could have overlooked a duplicate
                #                key in some response...).
                print("Duplicate key: ", _key)
                _key += "_2"
            results[_key] = resp[_key]

        return results

    def _decode_response(self,
                         res: requests.Response,
                         url: str,
                         do_invalidate: bool) -> ApiResponse:
        """Decodes a requests.Response after a successful connection with API."""

        # Encoding as None increases a lot the time for decoding res.text
        # on some systems (issue observed in P4Max for large responses);
        if res.encoding is None:
            res.encoding = "utf-8"

        http_err = f"({res.status_code}) {res.reason}" if not res.ok else None
        error = None

        if res.status_code == HTTPStatus.UNAUTHORIZED:
            resp = {}
            ok = False
            error = ERR_NOT_AUTHORIZED
            self.token = None
            if do_invalidate:
                self.invalidated = True
                if self._on_invalidated is not None:
                    self._on_invalidated()
        elif res.status_code == HTTPStatus.FORBIDDEN:
            resp = {}
            ok = False
            # Not always the correct error to give; maybe use: res.reason
            error = ERR_URL_EXPIRED
        elif res.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            resp = json.loads(res.text)
            ok = False
            error = ERR_LIMIT_DOWNLOAD_RATE
        elif res.text:
            try:
                resp = json.loads(res.text)
                ok = res.ok

                # If server error, pass forward any message from api, but
                # fallback to generic http status number/name.
                # Requests that fail will not return 200 status, and should
                # include a specific message on what was wrong.
                # There is also typically an "errors" field in the body,
                # but that is a more complex structure (not just a string).
                if not ok:
                    error = resp.get("message", http_err)
                    if error == "":
                        error = f"{http_err} - message present but empty"

            except json.decoder.JSONDecodeError:
                resp = {}
                ok = False
                error = f"Failed to parse response as json - {http_err}"
        else:
            resp = {}
            ok = False
            error = f"No contents in response - {http_err}"

        if type(resp) is not dict:
            # TODO(Andreas): Happens for /category/list
            #                Can be removed, if/when endpoint response changes
            print("RESPONSE WITHOUT TOP LEVEL DICT:\n    ", url)
            resp = {"data": resp}

        resp = self._flatten_results(resp)
        resp["request_url"] = url
        return ApiResponse(resp, ok, error, headers=res.headers)

    def _request_url(self,
                     url: str,
                     method: str,
                     payload: Optional[Dict] = None,
                     headers: Optional[Dict] = None,
                     do_invalidate: bool = True,
                     skip_mp: bool = False,
                     have_updated_meta: bool = True
                     ) -> ApiResponse:
        """Request a repsonse from an api.

        Args:
            url: The URL to request from.
            method: Type of http request, e.g. POST or GET.
            payload: The body of the request.
            headers: Prepopulated headers for the request including auth.
        """

        try:
            proxies = getproxies()

            if method in ["POST", "PUT"] and have_updated_meta:
                payload = self._update_meta_payload(payload, skip_mp)

            if method == "POST":
                # TODO: Consider making this a separate special logger,
                # since it is really heavy and reduces the useability of debug
                self.logger.debug(f"API POST {url}\n{json.dumps(payload)}")
                res = requests.post(url,
                                    data=json.dumps(payload),
                                    headers=headers,
                                    proxies=proxies,
                                    timeout=TIMEOUT)
            elif method == "GET":
                self.logger.debug(f"API GET {url}")
                res = requests.get(url,
                                   headers=headers,
                                   proxies=proxies,
                                   timeout=TIMEOUT)
            elif method == "PUT":
                self.logger.debug(f"API PUT {url}\n{json.dumps(payload)}")
                res = requests.put(url,
                                   data=json.dumps(payload),
                                   headers=headers,
                                   proxies=proxies,
                                   timeout=TIMEOUT)
            else:
                raise ValueError("raw_request input must be GET, POST, or PUT")
        except requests.exceptions.ConnectionError as e:
            resp = {"error": str(e), "request_url": url}
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse(resp, False, ERR_CONNECTION)
        except requests.exceptions.Timeout as e:
            resp = {"error": str(e), "request_url": url}
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse(resp, False, ERR_TIMEOUT)
        except requests.exceptions.ProxyError as e:
            resp = {"error": str(e), "request_url": url, "message": ERR_PROXY}
            self.report_message("failed_proxy_error", url, level="error")
            self._trigger_status_change(ApiStatus.PROXY_ERROR)
            return ApiResponse(resp, False, ERR_PROXY)
        except requests.exceptions.ContentDecodingError as e:
            resp = {"error": str(e), "request_url": url, "message": ERR_DECODE}
            self.report_message("failed_decoding_error", url, level="error")
            return ApiResponse(resp, False, ERR_DECODE)

        # Connection to site was a success, signal online.
        self._trigger_status_change(ApiStatus.CONNECTION_OK)

        # If no connection error, decodes the reponse and creates an ApiResponse
        return self._decode_response(res, url, do_invalidate)

    def _request(self,
                 path: str,
                 method: str,
                 payload: Optional[Dict] = None,
                 headers: Optional[Dict] = None,
                 do_invalidate: bool = True,
                 api_v2: bool = False,
                 skip_mp: bool = False
                 ) -> ApiResponse:
        """Request a repsonse from an api.

        Args:
            path: The api endpoint path without the url domain.
            method: Type of http request, e.g. POST or GET.
            payload: The body of the request.
            headers: Prepopulated headers for the request including auth.
        """

        if api_v2:
            url = self.api_url_v2 + path
        else:
            url = self.api_url + path
        return self._request_url(url,
                                 method=method,
                                 payload=payload,
                                 headers=headers,
                                 do_invalidate=do_invalidate,
                                 skip_mp=skip_mp)

    def _request_stream(
            self, url: str, headers: Optional[Dict] = None) -> ApiResponse:
        """Stream a request from an explicit fully defined url.

        Args:
            path: The api endpoint path without the url domain.
            headers: Prepopulated headers for the request including auth.

        Response: ApiResponse where the body is a dict including the key:
            "stream": requests get response object (the streamed connection).
            "session": Session needs to be closed, when done.
        """

        try:
            proxies = getproxies()
            session = requests.Session()
            # See the following about timeouts and read vs connect:
            # https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
            # This page might be misleading but makes a point that the timeout
            # property might not be used at all during streaming requests
            # https://proxiesapi.com/articles/why-your-python-requests-timeout-may-not-be-timing-out-as-expected
            # ...however in our download failure reports, we definitely have a
            # slew of errors saying: "Received Connection timed out after 20
            # seconds error during download", matching the timeout at the time.
            # So, we are increasing the stream timeout to be much larger.
            # Some browser are set to numbers like 5m or even unlimited
            res = session.get(url,
                              headers=headers,
                              proxies=proxies,
                              timeout=TIMEOUT_STREAM,
                              stream=True)
        except requests.exceptions.ConnectionError as e:
            session.close()
            resp = {"error": str(e), "request_url": url}
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse(resp, False, ERR_CONNECTION)
        except requests.exceptions.Timeout as e:
            session.close()
            resp = {"error": str(e), "request_url": url}
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse(resp, False, ERR_TIMEOUT_STREAM)
        except requests.exceptions.ProxyError as e:
            session.close()
            resp = {"error": str(e), "request_url": url, "message": ERR_PROXY}
            self.report_message("failed_proxy_error", url, level="error")
            self._trigger_status_change(ApiStatus.PROXY_ERROR)
            return ApiResponse(resp, False, ERR_PROXY)

        cf_ray = res.headers.get("CF-RAY", "")

        # Connection to site was a success, signal online.
        self._trigger_status_change(ApiStatus.CONNECTION_OK)

        error = f"({res.status_code}) {res.reason}" if not res.ok else None

        invalid_auth = res.status_code == HTTPStatus.UNAUTHORIZED
        url_expired = res.status_code == HTTPStatus.FORBIDDEN

        if invalid_auth:
            session.close()
            resp = {"response": None, "CF-RAY": cf_ray}
            ok = False
            error = ERR_NOT_AUTHORIZED
            self.token = None
            self.invalidated = True
        elif url_expired:
            session.close()
            resp = {"response": None, "CF-RAY": cf_ray}
            ok = False
            error = ERR_URL_EXPIRED
        else:
            resp = {"stream": res, "session": session, "CF-RAY": cf_ray}
            ok = res.ok

        return ApiResponse(resp, ok, error)

    def _request_authenticated(self,
                               path: str,
                               payload: Optional[Dict] = None,
                               skip_mp: bool = False,
                               api_v2: bool = False,
                               method: Optional[str] = None
                               ) -> ApiResponse:
        """Make an authenticated request to the API using the user token."""

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        initial_char = self.identify_initial_char(path)
        format_str = "plain"
        if self.allow_html:
            format_str = "html"

        path += f"{initial_char}format={format_str}"

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            return ApiResponse({}, False, ERR_NOT_AUTHORIZED)

        # TODO(Andreas): I'd vote to remove this implicit choice of method in
        #                favor of always explicitly specifying, what we want
        #                to do.
        #                Mainly because with API V2 we now have quite a few
        #                POST requests without any paylod.
        if method is None:
            method = "POST" if payload is not None else "GET"

        res = self._request(
            path,
            method,
            payload=payload,
            headers=headers,
            skip_mp=skip_mp,
            api_v2=api_v2)
        if res.error and "server error" in res.error.lower():
            res.ok = False
            res.error = ERR_INTERNAL

        return res

    def add_utm_suffix(self, url: str, content: Optional[str] = None) -> str:
        """Return the UTM tag to append to any url requests for tracking."""

        # Detect if the url already has a param.
        initial_char = self.identify_initial_char(url)

        # Ensure the version str starts with a leading v.
        if not self.version_str or self.version_str[0] != "v":
            addon_v = "v" + self.version_str
        else:
            addon_v = self.version_str
        # campaign: Granular addon+software+version
        campaign = f"addon-{self.software_source}-{addon_v}"
        token = self.token
        platform = self._platform
        access = "" if not token else f"access={token}&platform={platform}&"
        source = self.software_source  # Such as "blender"
        medium = "addon"
        count = "" if not content else "&{content}"
        outstr = (f"{url}{initial_char}{access}utm_campaign={campaign}"
                  f"&utm_source={source}&utm_medium={medium}{count}")
        return outstr

    def log_in(self,
               email: str,
               password: str,
               time_since_enable: Optional[int] = None,
               api_v2: bool = True
               ) -> ApiResponse:
        """Log the user in with a password/email combo.

        time_since_enable is the number of seconds since the addon was first
        enabled, only populated if this was the first login event for this
        install, used to identify an install event.
        """

        data = {
            "email": email,
            "password": password,
        }
        if time_since_enable is not None:
            data["time_since_enable"] = time_since_enable

        res = self._request(
            "/login", "POST", data, HEADERS_LOGIN, api_v2=api_v2)
        token = res.body.get("access_token", None)

        if not res.ok:
            msg = res.body.get("message", "")
            err = res.body.get("errors", "")
            if "do not match" in msg:
                res.error = ERR_WRONG_CREDS
            elif msg:
                self.report_message(
                    "login_error_other", f"{res.error}: {msg}", "error")
                res.error = msg
            elif res.error in SKIP_REPORT_ERRS:
                pass
            elif err:
                self.report_message(
                    "login_error_err_no_msg", f"{res.error} - {err}", "error")
                # err can be a struc, not great for ui, prefer res.error
                res.error = res.error or ERR_OTHER
            else:
                self.report_message(
                    "login_error_no_message", str(res.error), "error")
                # Don't override res.error, which can include status code.
                # Pass forward to front end, likely connection or proxy.
        elif token is None:
            self.report_message("login_error_no_token", str(res.body), "error")
            res.ok = False
            res.error = ERR_NO_TOKEN
        else:
            # Request was success.
            self.token = token
            self.invalidated = False
        return res

    def log_in_with_website(
        self,
        time_since_enable: Optional[int] = None,  # Deprecated.
        open_browser: bool = True,
    ) -> ApiResponse:
        """Log the user via website login.

        time_since_enable is deprecated and not used in this request anymore,
        instead it is shifted to the validate login event, to better match the
        end-perceived completion of the login back in the addon.
        """

        data_req = {
            "platform": self._platform,
            "meta": {
                "addon_version": self.version_str,
                "software_version": self.software_version,
                "software_name": self.software_source
            }
        }

        self.login_token = None
        url_login = ""

        res = self._request("/initiate/login",
                            "POST",
                            data_req,
                            HEADERS_LOGIN,
                            api_v2=True)

        # TODO(POL-2961): Move to only the proposed way once POL-2961 is done.
        api_current_ok = res.body.get("message", "").lower() == "success"
        api_proposed_ok = res.body.get("status", "").lower() == "success"

        if not res.ok:
            msg = res.body.get("message", "")
            err = res.body.get("errors", "")
            # TODO(SOFT-603): What errors might occur?
            #                 There're sibling TODOs in
            #                 p4b/toolbox.py:f_login_with_website_handler()
            #                 and below check_login_with_website_success()
            if msg:
                self.report_message(
                    "login_error_other", f"{res.error}: {msg}", "error")
                res.error = msg
            elif err:
                self.report_message(
                    "login_error_err_no_msg", f"{res.error} - {err}", "error")
                # err can be a struct, not great for ui, prefer res.error
                res.error = res.error or ERR_OTHER
            else:
                self.report_message(
                    "login_error_no_message", str(res.error), "error")
                # Don't override res.error, which can include status code.
                # Pass forward to front end, likely connection or proxy.

        elif not api_proposed_ok and not api_current_ok:
            self.report_message("login_error_not_initiated",
                                str(res.body),
                                "error")
            res.ok = False
            res.error = ERR_LOGIN_NOT_INITIATED
        else:
            # Request was success.
            self.login_token = res.body.get("login_token", None)
            url_login = res.body.get("login_url", "")

        if url_login == "" or self.login_token is None:
            self.login_token = None
            res.ok = False
            res.error = ERR_LOGIN_NOT_INITIATED
            return res

        if open_browser:
            webbrowser.open(url_login, new=0, autoraise=True)
        return res

    def check_login_with_website_success(
            self, time_since_enable: Optional[int] = None) -> ApiResponse:
        """Checks if a login with website was successful."""

        data_validate = {
            "platform": self._platform,
            "login_token": self.login_token,
            "meta": {
                "optin": self._is_opted_in(),
                "addon_version": self.version_str,
                "software_version": self.software_version,
                "software_name": self.software_source
            }
        }

        if time_since_enable is not None:
            data_validate["time_since_enable"] = time_since_enable

        res = self._request("/validate/login",
                            "POST",
                            data_validate,
                            HEADERS_LOGIN,
                            do_invalidate=False,
                            api_v2=True)

        # TODO(POL-2961): Move to only the proposed way once POL-2961 is done.
        # TODO(Andreas): I can not find POL-2961 in Jira
        msg_lower = res.body.get("message", "").lower()
        status_lower = res.body.get("status", "").lower()
        api_current_ok = msg_lower == "successful login"
        api_proposed_ok = status_lower == "success"

        if not res.ok:
            if res.error != ERR_NOT_AUTHORIZED:
                # TODO(SOFT-603): Error handling,
                #                 other errors than ERR_NOT_AUTHORIZED
                #                 There're sibling TODOs in
                #                 p4b/toolbox.py:f_login_with_website_handler()
                #                 and above log_in_with_website()

                print(f"Validation error {res.error}")
        elif not api_proposed_ok and not api_current_ok:
            # TODO(SOFT-603): Error handling
            pass
        else:
            # Success case
            self.token = res.body.get("access_token", "")
            self.invalidated = False

        return res

    def poll_login_with_website_success(
        self,
        timeout: int = 300,
        cancel_callback: Callable = lambda: False,
        time_since_enable: Optional[int] = None
    ) -> ApiResponse:
        """Waits for a login with website to finish.

        Args:
        timeout: Number of seconds to wait for a successful login
        cancel_callback: Callable returning True, if the wait is to be aborted
        """

        # Poll for finished login
        while timeout > 0:
            timeout -= 1
            time.sleep(1)

            res = self.check_login_with_website_success(time_since_enable)
            if res.ok:
                break
            else:
                if cancel_callback is not None and cancel_callback():
                    res = ApiResponse(body={},
                                      ok=False,
                                      error="Login cancelled")
                    break
                if res.error == ERR_NOT_AUTHORIZED:
                    continue
                # TODO(SOFT-603): Error handling
                break
        return res

    def log_out(self) -> ApiResponse:
        """Logs the user out."""

        endpoint = "/logout"
        res = self._request_authenticated(
            endpoint, payload={}, api_v2=True, method="POST")
        if res.ok and "data" in res.body:
            res.body = res.body.get("data", [])
        return res

    def categories(self) -> ApiResponse:
        """Get the list of website requests."""

        # TODO(Andreas): Language...
        endpoint = "/category/list?language_code=en"
        res = self._request(endpoint, api_v2=True, method="GET")

        if res.ok and "data" in res.body:
            res.body = res.body.get("data", [])
        return res

# TODO(Andreas): get_user_balance no longer needed, see get_user_info()
#    def get_user_balance(self) -> ApiResponse:
#        """Get the balance for the given user."""
#
#        path = "/available/user/balance"
#        res = self._request_authenticated(path)
#        error_in_body = res.body.get("error", "")
#        if not res.ok and error_in_body == MSG_ERR_RECORD_NOT_FOUND:
#            # This happens for free users without any transactions
#            res = ApiResponse(body={"subscription_balance": 0,
#                                    "ondemand_balance": 0,
#                                    "available_balance": 0,
#                                    "error": error_in_body,
#                                    "request_url": res.body.get("request_url",
#                                                                "")
#                                    },
#                              ok=True,
#                              error=None
#                              )
#        return res

    def get_user_info(self) -> ApiResponse:
        """Get information for the given user."""

        path = "/me"
        res = self._request_authenticated(path, api_v2=True, method="POST")

        subscription = res.body.get("subscription", None)
        if subscription is None:
            res.body["subscription"] = {
                "plan_name": STR_NO_PLAN
            }
            res.ok = True   # No subscription is fine for us
            res.error = None

        return res

    def update_user_profile(self,
                            user_use: str,
                            email_preference: bool,
                            primary_render_engine: Optional[str] = None,
                            assign_dcc: bool = False
                            ) -> ApiResponse:
        """Update the user profile."""
        endpoint = "/users/update"
        payload = {
            "how_will_you_use_poliigon": user_use,
            "subscribed_from_emails": email_preference,
        }

        # Only include primary_3d_software/engine if assign_dcc is True
        if assign_dcc:
            payload["primary_3d_software"] = self.software_dl_dcc
            if primary_render_engine in RenderEngines.get_list():
                payload["primary_rendering_engine"] = primary_render_engine
            else:
                # Fallback to default for current dcc
                fallback_renderer = RenderEngines.default_for_dcc(
                    self.software_dl_dcc)
                payload["primary_rendering_engine"] = fallback_renderer.value

        res = self._request_authenticated(
            endpoint, payload=payload, api_v2=True, method="POST")
        return res

    def get_download_url(self,
                         download_data: dict,
                         is_retry: bool = False
                         ) -> ApiResponse:
        """Request the download URL(s) for a purchased asset.

        Args:
            download_data: Structure of data defining the download.
            is_retry: Boolean to define if this is a retry or not

        Response: ApiResponse where body is a dict including server-given keys:
            uuid: str, files: List[Dict]
        """
        res = self._request_authenticated(
            "/assets/download",
            payload=download_data,
            skip_mp=is_retry,
            # TODO(Andreas): API V2 downloading still to be defined
            api_v2=True,
            # method="POST"
        )
        request_url = res.body.get("request_url", "No request_url in body.")
        if res.ok:
            if res.body.get("message") and "expired" in res.body["message"]:
                res = ApiResponse(
                    {"message": res.body["message"]},
                    False,
                    construct_error(
                        request_url,
                        "Download link expired",
                        download_data
                    )
                )
        elif res.error in SKIP_REPORT_ERRS:
            return res
        else:
            res.error = construct_error(request_url, res.error, download_data)
        return res

    def download_asset_get_urls(self,
                                download_data: dict,
                                is_retry: bool = False
                                ) -> ApiResponse:
        """Request a set of download URLs for a purchased asset.

        Args:
            download_data: Structure of data defining the download.
            is_retry: Define if process is a retrial.

        Response: ApiResponse where the body is a dict including the key:
            "downloads": A list of FileDownload objects.
            "size_asset": Accumulated size of all individual files.
        """

        # Insert the field which ensures multiple downloads are present.
        # Copy DL data in case download data re-referenced (speed tests)
        dl_data = download_data.copy()

        dl_data["response_type"] = DL_RESPONSETYPE_JSON

        # Fetch the download URLs (or legacy: downloader request).
        res = self.get_download_url(dl_data, is_retry)

        if not res.ok:
            # No UUID in this case, download wasn't even able to start,
            # so no download quality tracking here

            return res

        return ApiResponse(res.body,
                           True,
                           None)

    @staticmethod
    def check_exist_and_finished(path: str,
                                 download  # FileDownload (circular import)
                                 ) -> bool:
        if not os.path.exists(path):
            return False
        return os.path.getsize(path) == download.size_expected

    def delete_file(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            os.remove(path)
        except BaseException:
            # Deliberately silencing all exceptions, here!
            # Most of the time, we are here in reaction to an exception
            # during download. Neither can we do anything here, if remove
            # fails, nor would we gain much information from reporting
            # this exception.
            self.logger.exception("Failed to delete partial download")

    def download_asset_file(self,
                            download  # FileDownload (circular import)
                            ) -> ApiResponse:
        """Stream download a single file of a purchased asset.

        Args:
            download: Structure of data defining the download.

        Response: ApiResponse where the body is a dict including the key:
            "download": FileDownload object
                        (for convenience it's identical to the one passed in)
        """

        t_start = time.monotonic()

        path_temp = download.get_path(temp=True)
        file_exists_temp = self.check_exist_and_finished(path_temp, download)
        path_final = download.get_path(temp=False)
        file_exists_final = self.check_exist_and_finished(path_final, download)

        if file_exists_temp or file_exists_final:
            self.logger.warning(
                f"download_asset_file ALREADY EXISTS: {download.filename}")
            download.set_status_done()
            download.size_downloaded = download.size_expected
            return ApiResponse({"download": download}, True, None)

        res = self._request_stream(download.url)
        # Grab header so we can uniquely pair a download error to server-side.
        cf_ray = res.body.get("CF-RAY", "")
        download.cf_ray = cf_ray
        if not res.ok:
            if res.error == ERR_URL_EXPIRED:
                self.logger.error(
                    f"download_asset_file URL timeout {download.filename}")
            else:
                self.logger.error(
                    "download_asset_file ERR request stream "
                    f"{download.filename}")
                body_err = res.body.get("error")  # contains original trace
                err = construct_error(
                    download.url,
                    f"Received {res.error} during download start ({body_err})",
                    download.filename)
                res.error = err
            download.set_status_error()
            return res
        elif "stream" not in res.body:
            self.logger.error(
                f"download_asset_file ERR stream MISSING {download.filename}")
            err = construct_error(
                download.url,
                ERR_MISSING_STREAM,
                download.filename)
            msg = {"message": "Requests response missing from stream",
                   "CF-RAY": cf_ray}
            download.set_status_error()
            return ApiResponse(msg, False, err)

        stream = res.body["stream"]
        stream_size = int(stream.headers["Content-Length"])
        session = res.body["session"]

        if download.status != DownloadStatus.WAITING:
            self.logger.warning(
                "download_asset_file DOWNLOAD STATUS NOT WAITING "
                f"{download.filename} {download.status}")

        if not download.set_status_ongoing():
            self.logger.error(
                "download_asset_file CANCELLED BEFORE START "
                f"{download.filename}")
            session.close()
            msg = ERR_USER_CANCEL_MSG
            return ApiResponse({"error": msg, "CF-RAY": cf_ray}, False, msg)

        asset_id = download.asset_id
        download.size_downloaded = 0

        try:
            with open(path_temp, "wb") as write_file:
                for chunk in stream.iter_content(chunk_size=1024):
                    if chunk is None:
                        continue
                    write_file.write(chunk)
                    download.size_downloaded += len(chunk)
                    if download.status == DownloadStatus.CANCELLED:
                        break
        except requests.exceptions.ConnectionError as e:
            download.set_status_error()
            self.delete_file(path_temp)
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse(
                {"error": e, "CF-RAY": cf_ray}, False, ERR_CONNECTION)
        except requests.exceptions.Timeout as e:
            download.set_status_error()
            self.delete_file(path_temp)
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse(
                {"error": str(e), "CF-RAY": cf_ray}, False, ERR_TIMEOUT_STREAM)
        except OSError as e:
            download.set_status_error()
            self.delete_file(path_temp)
            if e.errno == errno.ENOSPC:
                return ApiResponse(
                    {"error": e, "CF-RAY": cf_ray}, False, ERR_OS_NO_SPACE)
            elif e.errno == errno.EACCES:
                return ApiResponse(
                    {"error": e, "CF-RAY": cf_ray}, False, ERR_OS_NO_PERMISSION)
            else:
                return ApiResponse(
                    {"error": e, "CF-RAY": cf_ray},
                    False,
                    f"Download error for {asset_id} - {ERR_OS_WRITE}\n{e}")
        except Exception as e:
            download.set_status_error()
            self.delete_file(path_temp)
            err = construct_error(
                download.url,
                f"Streaming error during download of {asset_id} ({e})",
                {"filename": download.filename})
            return ApiResponse({"error": e, "CF-RAY": cf_ray}, False, err)
        finally:
            session.close()

        if download.size_expected == download.size_downloaded == stream_size:
            # Download success
            download.set_status_done()
            t_end = time.monotonic()
            download.duration = t_end - t_start
        else:
            # Download cancelled or error
            if download.status == DownloadStatus.ONGOING:
                self.logger.warning(
                    "download_asset_file size difference despite no error!!! "
                    f"{download.filename}")
                # TODO(Andreas): We shouldn't be here
            if download.status == DownloadStatus.CANCELLED:
                msg = ERR_USER_CANCEL_MSG
            else:
                asset_id = download.asset_id
                self.logger.error(
                    f"Download filesize mismatch (Asset ID: {asset_id})!\n"
                    f"  File download: {download.filename}\n"
                    f"  From server expected: {download.size_expected}\n"
                    f"  Downloaded: {download.size_downloaded}\n"
                    f"  Stream size: {stream_size}")
                msg = ERR_FILESIZE_MISMATCH
            download.set_status_error()
            # Delete incomplete file
            self.delete_file(path_temp)
            return ApiResponse({"error": msg, "CF-RAY": cf_ray}, False, msg)

        # Downloaded file does not get its "dl" suffix removed, yet.
        # Needs to be done, when entire asset (all files) is complete.

        return ApiResponse(
            {"download": download, "CF-RAY": cf_ray}, True, None)

    def track_download_quality(self,
                               uuid: str,
                               status: DQStatus,
                               error: str = ""
                               ) -> bool:
        """Send download quality tracking information.

        NOTE: This function only tracks download quality, so it is called even
        if user has not opted in to sharing information;
        """

        payload = {
            "uuid": uuid,
            "status": status.name.lower(),
            "error": error
        }
        res = self._request_authenticated(
            "/t/download_quality", payload=payload, skip_mp=False, api_v2=True)
        if not res.ok:
            self.report_message(
                "download_quality_error",
                f"{res.error}",
                "error")
        return res.ok

    def download_preview(self,
                         url: str,
                         dst_file: str,
                         asset_name: str = ""
                         ) -> ApiResponse:
        """Stream download a preview to a file from a custom domain url."""

        # TODO: Add an optional chunk size callback for UI updates mid stream.
        # print(f"download_asset: Downloading {url} to {dst_file}")
        session = None
        try:
            resp = self._request_stream(url)
            if not resp.ok and resp.error in SKIP_REPORT_ERRS:
                return resp
            elif not resp.ok:
                self.report_message(
                    "download_preview_not_ok",
                    f"{asset_name}: {resp.error}",
                    "error")
                return ApiResponse(
                    {"error": resp.error},
                    False,
                    resp.error)

            stream = resp.body.get("stream")
            session = resp.body.get("session")
            if not stream:
                self.report_message(
                    "download_preview_resp_missing",
                    f"{asset_name}: {ERR_MISSING_STREAM} - {resp.body}",
                    "error")
                return ApiResponse(
                    {"error": ERR_MISSING_STREAM, "body": resp.body},
                    False,
                    ERR_MISSING_STREAM)
            elif resp.ok:
                directory = os.path.dirname(dst_file)
                try:
                    os.makedirs(directory, exist_ok=True)
                except OSError as e:
                    self.report_message(
                        "download_preview_no_directory",
                        ("Failed to create non-existing thumb directory: "
                         f"{directory}\n{e}"),
                        "error")

                if os.path.exists(directory):
                    with open(dst_file, "wb") as fwriter:
                        fwriter.write(stream.content)
            else:
                msg = f"{asset_name}: {resp.error}"
                self.report_message(
                    "download_preview_error", msg, "error")
                return resp
        except requests.exceptions.ConnectionError as e:
            self._trigger_status_change(ApiStatus.NO_INTERNET)
            return ApiResponse({"error": e}, False, ERR_CONNECTION)
        except OSError as e:
            self.report_message(
                "download_preview_error_write", str(e), "error")
            return ApiResponse({"error": e}, False, ERR_OS_WRITE)
        except Exception as e:
            self.report_message(
                "download_preview_error_other", str(e), "error")
            return ApiResponse({"error": e}, False, ERR_OTHER)
        finally:
            if session is not None:
                session.close()

        return ApiResponse({"file": dst_file}, True, None)

    def purchase_asset(
            self, asset_id: int, search: str, category: str) -> ApiResponse:
        """Purchase a given asset for the logged in user.

        Args:
            asset_id: The unique poliigon asset id.
            search: Current active search query.
            category: Current category in slug form: "/brushes/free.
        """
        endpoint = f"/assets/purchase/{asset_id}"
        payload = {}

        if self._is_opted_in():
            # Only send if user is opted in.
            payload["last_search_term"] = search
            payload["last_category"] = category

        res = self._request_authenticated(
            endpoint, payload, api_v2=True, method="POST")
        if not res.ok:
            if "message" in res.body:
                msg = res.body["message"]
                err = str(res.body.get("errors", ""))  # Detailed server error.
                err_code = str(res.body.get("error_code", ""))
                if API_NOT_ENOUGH_CREDITS.lower() == err_code:
                    # TODO: if the status code here is 422 (or if "error code" == insufficient-credits)
                    # then this means insufficient balance.
                    # let's set up test that validates against this.
                    # and a way to reliably check the status code ideally
                    # instead of hard coded text.
                    self.report_message("not_enough_credits", asset_id, "info")
                    res.error = ERR_NOT_ENOUGH_CREDITS
                else:
                    res.error = f"{msg} - asset_id: {asset_id}"
                    self.report_message(
                        "purchase_failed", f"{res.error} {err}", "error")
            else:
                # To API, pass original message before updating to generic one.
                self.report_message("purchase_failed",
                                    f"{res.error}  - asset_id: {asset_id}",
                                    "error")
                res.error = f"{ERR_OTHER} - asset_id: {asset_id}"
        return res

    # TODO(Andreas): Suggestion for a new get_assets() makig the parameters a
    #                bit more explicit.
    #                Here we could also discuss, if we want the old page index
    #                and page size or rather want to change to API V2 style
    #                with asset index/offset and page size.
    def get_assets_NEW(self, idx_page: int, size_page: int) -> ApiResponse:
        """Get the assets with an optional query parameter."""

        query_data = {}
        query_data["page"] = idx_page
        query_data["perPage"] = size_page

        return self.get_assets(query_data)

    def get_assets(self, query_data: Dict) -> ApiResponse:
        """Get the assets with an optional query parameter."""

        # TODO(Andreas): Language...
        idx_page = query_data["page"]
        size_page = query_data["perPage"]
        offset = (idx_page - 1) * size_page
        endpoint = f"/new?language_code=en&limit={size_page}&offset={offset}"

        res = self._request_authenticated(
            endpoint, payload=None, api_v2=True, method="GET")
        if not res.ok:
            if res.error not in SKIP_REPORT_ERRS:
                self.report_message("online_assets_error",
                                    f"{query_data} - {res.error}", "error")
            return res
        elif "data" in res.body:
            # Success case

            # Store page size in response for increased backward compatibility.
            # AssetIndex uses this value to derive part of the query key.
            # In plugins/addons I'd recommend to rather set query key
            # parameters explicitly. Some AssetIndex unit tests rely on this
            # feature, though.
            res.body["per_page"] = size_page
            self._override_assets_payload(res.body)
        else:
            self.report_message(
                "online_assets_no_payload", str(res.body), "error")
            res.ok = False
            res.error = ERR_NO_POPULATED
        return res

    def get_user_assets(self, recent_downloads: bool = False) -> ApiResponse:
        """Get assets the user has already purchased."""

        if not recent_downloads:
            endpoint = "/assets/list/ids"
        else:
            endpoint = "/downloads/ids"
        res = self._request_authenticated(endpoint,
                                          payload=None,
                                          api_v2=True,
                                          method="GET")

        if not res.ok:
            if res.error not in SKIP_REPORT_ERRS:
                self.report_message(
                    "get_user_assets_error", f"{res.error}", "error")
            return res
        elif "asset_ids" in res.body:
            # Success case
            self._override_assets_payload(res.body)
        else:
            self.report_message(
                "get_user_assets_no_payload", str(res.body), "error")
            res.ok = False
            res.error = ERR_NO_POPULATED
        # Copy total number of purchased assets to key 'total' to be compatible
        # with other requests.
        res.body["total"] = res.body.get("asset_ids_count", -1)
        return res

    def get_all_assets(self) -> ApiResponse:
        """Get all assets in one go."""

        # TODO(Andreas): Language...
        res = self._request(
            "/all?language_code=en",
            api_v2=True,
            method="GET"
        )
        if not res.ok:
            if res.error not in SKIP_REPORT_ERRS:
                self.report_message("get_all_assets_error",
                                    f"{res.error}", "error")
            return res
        elif "data" in res.body:
            # Success case
            self._override_assets_payload(res.body)
        else:
            self.report_message(
                "get_all_assets_no_results", str(res.body), "error")
            res.ok = False
            res.error = ERR_NO_POPULATED

        # For compatibility with existing Done callbacks, which try to
        # determine, if it was the last page. Which it always is in this case.
        res.body["last_page"] = 1
        return res

    def get_category_assets(self, path_category: str) -> ApiResponse:
        """Get assets contained in a certain category."""

        # TODO(Andreas): Language...
        params = "language_code=en&addon=1"
        endpoint = f"/category/results/{path_category}?{params}"

        res = self._request(endpoint, payload=None, api_v2=True, method="GET")
        if not res.ok:
            if res.error not in SKIP_REPORT_ERRS:
                self.report_message(
                    "get_category_assets_error",
                    f"{path_category} - {params} - {res.error}",
                    "error")
            return res
        elif "data" in res.body:
            # Success case
            self._override_assets_payload(res.body)
        else:
            self.report_message(
                "get_category_assets_no_results", str(res.body), "error")
            res.ok = False
            res.error = ERR_NO_POPULATED
        return res

    def _algolia_hits_to_data(self, res: ApiResponse) -> None:
        """As Algolia responds in their own data format, this function
        basically converts the data to be in line with our other
        get_xyz_assets() functions, which also return a list of IDs under
        a 'data' key.
        """

        hits = res.body.get("hits", [])
        asset_ids = [_dict_asset["AssetID"] for _dict_asset in hits]
        res.body["data"] = asset_ids
        del res.body["hits"]

    def search_assets(
        self,
        search_term: str,
        idx_page: int = 1,
        size_page: int = 250
    ) -> ApiResponse:
        """Search for assets with a given search term."""

        # Algolia's page index starts at zero, while our API's page index
        # starts at one.
        idx_page = max(idx_page - 1, 0)

        URL_ALGOLIA_QUERY = "https://ci6l4fta7s-dsn.algolia.net/1/indexes/assets/query"
        header = {
            "x-algolia-api-key": "77a376fa69270eee8aa24f82d400b3d3",
            "x-algolia-application-id": "CI6L4FTA7S"
        }
        payload = {
            "query": search_term,
            "attributesToRetrieve": [
                "AssetID",  # Integer value
            ],
            "page": idx_page,
            "hitsPerPage": size_page,
            "facetFilters": [
                # TODO(Andreas): Is there also something like -prod?
                "ReleaseStatus:-Unpublished",
                "ReleaseStatus:-Staging"
            ]
        }

        res = self._request_url(
            url=URL_ALGOLIA_QUERY,
            method="POST",
            payload=payload,
            headers=header,
            do_invalidate=False,  # Since this is no Poliigon API access
            skip_mp=False,  # Will be ignored
            have_updated_meta=False
        )
        if not res.ok:
            return res

        # Convert returned data so we can use it inn the same way we use
        # results from Poliigon API.
        res.body["total"] = res.body["nbHits"]
        res.body["total_pages"] = res.body["nbPages"]
        res.body["current_page"] = res.body["page"]
        self._algolia_hits_to_data(res)
        return res

    def get_asset_details(self, asset_id: int) -> ApiResponse:
        """Retrieve asset data for a specific asset."""

        endpoint = f"/assets/details/{asset_id}?language_code=en"
        res = self._request_authenticated(
            endpoint, api_v2=True, method="GET")
        return res

    def get_user_available_plans(self) -> Optional[ApiResponse]:
        """Retrieves the plans available for upgrade for a given user.

        NOTE: It would return None for free users.
        """

        return self._request_authenticated(
            "/subscriptions/update/plans", api_v2=True, method="GET")

    def get_upgrade_plan(self, plan_id: str) -> ApiResponse:
        """Checks the possibility of upgrading to a given plan and return
        the information about the new plan compared with the current one.
        """

        endpoint = f"/subscriptions/update?item_price_id={plan_id}"
        return self._request_authenticated(endpoint, api_v2=True, method="GET")

    def put_upgrade_plan(self, plan_id: str) -> ApiResponse:
        """Confirm the upgrade to a given plan.

        NOTE: This function should only be called after get_upgrade_plan.
        """

        endpoint = f"/subscriptions/update?item_price_id={plan_id}"
        return self._request_authenticated(endpoint, api_v2=True, method="PUT")

    def resume_paused_plan(self) -> ApiResponse:
        """Resumes a paused plan.

        NOTE: For users with no paused account, this request should fail.
        """

        return self._request_authenticated(
            "/subscription/resume", api_v2=True, method="POST")

    def remove_cancellation_plan(self) -> ApiResponse:
        """Remove a scheduled Plan Cancellation.

        NOTE: For users with no scheduled cancel account, this request should
              fail.
        """

        return self._request_authenticated(
            "/subscription/remove/cancellation", api_v2=True, method="POST")

    def remove_scheduled_paused_plan(self) -> ApiResponse:
        """Remove a scheduled Plan Pause.

        NOTE: For users with no scheduled pause account, this request should
              fail.
        """

        return self._request_authenticated(
            "/subscription/remove/pause", api_v2=True, method="POST")

    def pooled_preview_download(
            self, urls: Sequence, files: str) -> ApiResponse:
        """Threadpool executor for downloading assets or previews.

        Arguments:
            urls: A list of full urls to each download file, not just api stub.
            files: The parallel output list of files to create.
        """

        if len(urls) != len(files):
            raise RuntimeError("List of urls and files are not equal")
        futures = []
        with ThreadPoolExecutor(
                max_workers=MAX_DL_THREADS) as executor:
            for i in range(len(urls)):
                future = executor.submit(
                    self.download_preview,
                    urls[i],
                    files[i]
                )
                futures.append(future)

        any_failures = []
        for ftr in futures:
            res = ftr.result()
            if not res or not res.ok:
                any_failures.append(res)

        if any_failures:
            return ApiResponse(
                any_failures, False, "Error during pooled preview download")
        else:
            return ApiResponse("", True, None)

    def _signal_event(self, event_name: str, payload: Dict) -> ApiResponse:
        """Reusable entry to send an event, only if opted in."""

        if not self._is_opted_in():
            return ApiResponse(None, False, ERR_OPTED_OUT)
        endpoint = f"/t/{event_name}"
        return self._request_authenticated(
            endpoint, payload=payload, api_v2=True, method="POST")

    def signal_install(self) -> ApiResponse:
        """Emits install event (No additional payload needed)."""
        return self._signal_event("install", payload={})

    def signal_preview_asset(self, asset_id: int) -> ApiResponse:
        """Sends quick asset preview event if opted in."""

        payload = {"asset_id": asset_id}
        return self._signal_event("preview_asset", payload=payload)

    def signal_import_asset(self, asset_id: int = 0):
        """Sends import asset event if opted in."""

        payload = {"asset_id": asset_id}
        return self._signal_event("import_asset", payload=payload)

    def signal_search(self, search_term: str):
        """Sends search event if opted in."""

        payload = {"search_term": search_term}
        return self._signal_event("search", payload=payload)

    def signal_view_category(self, category: str):
        """Sends view category event if opted in."""

        payload = {"category": category}
        return self._signal_event("view_category", payload=payload)

    def signal_view_screen(self, screen_name: str) -> ApiResponse:
        """Sends view screen event if opted in.

        Limits one signal event per session per notification type.

        Args:
            screen_name: Explicit agreed upon view names within addon.
        """

        now = time.time()
        if self._last_screen_view:
            if now - self._last_screen_view < MIN_VIEW_SCREEN_INTERVAL:
                return ApiResponse({}, False, ERR_INTERVAL_VIEW)
            else:
                self._last_screen_view = now
        else:
            self._last_screen_view = now

        # Any name changes here require server-side coordination.
        valid_screens = [
            "home",  # Filter option (all assets)
            "my_assets",  # Filter option
            "imported",  # Filter option
            "local_assets",  # Filter option
            "downloads",  # Filter option
            "my_account",
            "settings",
            "help",
            "onboarding",  # Free + Pro plan, introducing previewing
            "update_user",  # Assign user attributes + newsletter selection
            "large_preview",
            "tweak_panel",
            "blend_node_add",
            "blend_browser_lib",  # If the Poliigon lib is visible
            "blend_browser_import"  # If the right side bar is visible
        ]

        if screen_name not in valid_screens:
            print("Screen name is not valid:", screen_name)
            return ApiResponse(
                {"invalid_screen": screen_name},
                False,
                ERR_INVALID_SCREEN_NAME)
        payload = {"screen_name": screen_name}
        return self._signal_event("view_screen", payload=payload)

    def signal_view_notification(self, notification_id: str) -> ApiResponse:
        """Sends view notification event if opted in."""

        payload = {"notification_id": notification_id}
        return self._signal_event("view_notification", payload=payload)

    def signal_click_notification(
            self, notification_id: str, action: str) -> ApiResponse:
        """Sends click notification event if opted in."""

        payload = {"notification_id": notification_id, "action": action}
        return self._signal_event("click_notification", payload=payload)

    def signal_dismiss_notification(self, notification_id: str) -> ApiResponse:
        """Sends dismissed notification event if opted in."""

        payload = {"notification_id": notification_id}
        return self._signal_event("dismiss_notification", payload=payload)

    def _is_opted_in(self) -> bool:
        """Returns True, if user has opted-in for reporting."""

        return self.get_optin and self.get_optin()

    def _update_meta_payload(
            self, payload: Optional[Dict], skip_mp: bool) -> Dict:
        """Take the given payload and add or update its meta fields."""

        if payload is None:
            payload = {}

        if "meta" not in payload:
            payload["meta"] = {}

        render_engine = self._get_current_renderer()
        if self._is_opted_in():
            payload["meta"]["optin"] = True
            payload["meta"]["software_version"] = self.software_version
            # In cases like mid blender startup, render engine isn't available yet
            if render_engine is not None:
                payload["meta"]["render_engine"] = render_engine
        else:
            payload["meta"] = {}  # Clear out any existing tracking.
            payload["meta"]["optin"] = False

        # mp flag is independent of opted_in state
        payload["meta"]["mp"] = self._mp_relevant

        # Very last, override to always assign skip, if skip is defined.
        # But if not specifically skipping, defer to self._mp_relevant
        if skip_mp is True:
            payload["meta"]["mp"] = False

        # Always populate addon version and platform.
        payload["meta"].update(self.common_meta)
        payload["platform"] = self._platform

        return payload

    def _trigger_status_change(self, status_name: ApiStatus) -> None:
        """Trigger callbacks to other modules on API status change.

        Typically used to update the UI in a central location, instead of
        needing to wrap each and every call with the same handler.
        """

        self.status = status_name

        has_notice_class = self.notification_system is not None
        notice_not_created = self.status_notice is None
        create_notice = has_notice_class and notice_not_created
        if create_notice and status_name == ApiStatus.NO_INTERNET:
            self.status_notice = self.notification_system.create_no_internet()
        elif create_notice and status_name == ApiStatus.PROXY_ERROR:
            self.status_notice = self.notification_system.create_proxy()

        # Use this callback to create or clean UI notice banner
        if self._status_listener is not None:
            self._status_listener(status_name)

        # Set status notice to None after callback
        if status_name == ApiStatus.CONNECTION_OK:
            self.status_notice = None

    def get_base_url(self, env_name: str = "prod") -> str:
        """Returns the base API URL, based on environment and API version."""

        if env_name == "prod":
            return URL_BASE

        pos = self.api_url.rfind("/api")
        url_base = self.api_url[:pos]
        api_url_str = "apiv1" if "apiv1" in url_base else "api"
        url_base = url_base.replace(api_url_str, "dev")
        return url_base

    def add_poliigon_urls(self, urls: Dict[str, str]) -> None:
        """Adds or changes Poliigon URLs.

        Arguments:
        urls: Dictionary {key: url}
              url may either be a complete URL or
              a URL path being appended to the base URL (needs to start with /)
        """

        for key, _url in urls.items():
            self._url_paths[key] = _url

    def get_poliigon_link(self,
                          link_type: str,
                          add_utm_suffix: bool = True,
                          env_name: str = "prod"
                          ) -> str:
        """Returns one of Poliigon's predefined URLs,
        optionally extended by UTM suffix.
        """

        if link_type not in self._url_paths:
            raise KeyError(f"Unknown link_type: {link_type}")

        url_path = self._url_paths[link_type]
        if url_path.startswith("/"):
            url_base = self.get_base_url(env_name)
            url = f"{url_base}{url_path}"
        else:
            url = url_path

        if add_utm_suffix:
            url = self.add_utm_suffix(url)

        return url

    def open_poliigon_link(self,
                           link_type: str,
                           add_utm_suffix: bool = True,
                           env_name: str = "prod"
                           ) -> None:
        """Opens a Poliigon URL"""

        if link_type not in self._url_paths:
            raise KeyError(f"Unknown link_type: {link_type}")

        url = self.get_poliigon_link(link_type, add_utm_suffix, env_name)

        webbrowser.open(url)

    def patch_download_url_increment_version(self, url: str) -> str:
        """Deprecated due to change in preview hosting solution."""

        return url

        # TODO(Andreas): Can be removed? Code was already deactivated before
        #                these API V2 changes.
        # Prior implementation
#        if "?" not in url:
#            return url
#        url_new_base, url_new_all_params = url.split("?", 1)
#        url_new_params = url_new_all_params.split("&")
#        for idx_param, param in enumerate(url_new_params):
#            if not param.startswith("v="):
#                continue
#            _, version = param.split("=")
#            try:
#                version = int(version) + 1
#                url_new_params[idx_param] = f"v={int(version)}"
#            except ValueError:
#                print("Version in URL not numeric")
#            break
#        url_new_all_params = "&".join(url_new_params)
#        url_new = "?".join([url_new_base, url_new_all_params])
#        return url_new

    def _load_asset_overrides(self, json_dir: str) -> None:
        """Loads all json files to override data per asset_id from api.

        Should point to a shallow directory of .json files, where each json
        contains either directly the direct data for a single asset with "id"
        as a top-level key, or be a top-level list of dictionaries where each
        dictionary contains a field for "id" ie the asset_id.
        """

        if not os.path.isdir(json_dir):
            return
        json_files = [
            os.path.join(json_dir, jfile)
            for jfile in os.listdir(json_dir)
            if jfile.endswith(".json") and os.path.isfile(
                os.path.join(json_dir, jfile))
        ]
        for jfile in json_files:
            try:
                with open(jfile, "r") as jopen:
                    jdata = json.load(jopen)
                self.logger.info(f"Loaded json data for {jfile}")
            except Exception:
                self.logger.exception(f"Failed to open json file {jfile}")
                continue
            extracted_overrides = self._extract_assetdata_from_dict(jdata)
            self._assetdata_overrides.update(extracted_overrides)

    def _extract_assetdata_from_dict(
            self, json_data: Union[Dict, Sequence]) -> Dict:

        extracted = {}
        toplevel_id = json_data.get("id")
        if toplevel_id:
            # Single asset data in one json file
            extracted[toplevel_id] = json_data
        elif isinstance(json_data, list):
            # Multiple assets contained in one json list
            for itm in json_data:
                if not isinstance(itm, dict):
                    self.logger.error(
                        f"Invalid override data, not a dict\n{itm}")
                    continue
                _id = itm.get("id", None)
                if _id is None:
                    self.logger.error(
                        f"Invalid override data, id is invalid\n{itm}")
                    continue
                extracted[_id] = itm

        if extracted:
            over_keys = extracted.keys()
            self.logger.info(f"Loaded overrides: {over_keys}")
        else:
            self.logger.info(f"No overrides extracted from json: {json_data}")

        return extracted

    def _override_assets_payload(self, src_assets_data) -> None:
        """Patches raw assets api response structure with loaded overrides."""

        assetdata_overrides = self._assetdata_overrides
        if not assetdata_overrides:
            return
        if not src_assets_data.get("data"):
            return

        for idx, itm in enumerate(src_assets_data["data"]):
            if itm["id"] in assetdata_overrides.keys():
                src_assets_data["data"][idx] = assetdata_overrides[itm["id"]]
                self.logger.info(f"Patched {itm['id']}")

    def _get_current_renderer(self) -> Optional[str]:
        try:
            renderer_type = RenderEngines.from_renderer_name(
                self.get_current_renderer_name()
            )
        except TypeError:
            # There is no injected function for getting the current Renderer Name
            renderer_type = RenderEngines.UNDEFINED
        if renderer_type == RenderEngines.UNDEFINED:
            return None
        return renderer_type.value.lower()

    def identify_initial_char(self, path: str) -> str:
        """Identify the initial character of a path."""

        if path[-1] == "/":
            return "?"
        elif path[-1] == "?":
            return ""
        elif path[-1] == "&":
            return ""
        elif "?" in path:
            return "&"
        else:
            return "?"
