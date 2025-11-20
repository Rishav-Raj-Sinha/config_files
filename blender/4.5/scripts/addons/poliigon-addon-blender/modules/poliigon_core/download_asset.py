# ##### BEGIN GPL LICENSE BLOCK #####
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

import os
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import (Future,
                                ThreadPoolExecutor)
from xml.etree import ElementTree
import errno
import time
from threading import Lock

from .api import (ApiResponse,
                  DownloadStatus,
                  DQStatus,
                  ERR_OS_NO_PERMISSION,
                  ERR_URL_EXPIRED,
                  ERR_OS_NO_SPACE,
                  ERR_LIMIT_DOWNLOAD_RATE)
from .assets import (AssetType,
                     AssetData,
                     PREVIEWS)


DOWNLOAD_TEMP_SUFFIX = "dl"

DOWNLOAD_POLL_INTERVAL = 0.25
MAX_DOWNLOAD_RETRIES = 10
MAX_PARALLEL_ASSET_DOWNLOADS = 2
MAX_PARALLEL_DOWNLOADS_PER_ASSET = 8
SIZE_DEFAULT_POOL = 10
MAX_RETRIES_PER_FILE = 3
MAX_RETRIES_PER_ASSET = 2

# This list defines a priority to fallback available formats
# NOTE: This is only for Convention 1 downloads
SUPPORTED_TEX_FORMATS = ["jpg", "png", "tiff", "exr", "hdr"]
MODEL_FILE_EXT = ["fbx", "blend", "max", "c4d", "skp", "ma"]


class DownloadTimer():
    start_time: float
    end_time: float
    duration: float

    def start(self) -> None:
        self.start_time = time.monotonic()

    def end(self) -> float:
        self.end_time = time.monotonic()
        self.duration = self.end_time - self.start_time
        return self.duration


@dataclass
class DynamicFile:
    name: Optional[str]
    contents: Optional[str]


@dataclass
class FileDownload:
    asset_id: int
    url: str
    filename: str
    convention: int
    size_expected: int
    size_downloaded: int = 0
    resolution_size: str = None
    status: DownloadStatus = DownloadStatus.INITIALIZED
    directory: str = ""
    fut: Optional[Future] = None
    duration: float = -1.0  # avoid div by zero, but result stays clearly wrong
    lock: Lock = Lock()
    max_retries: int = MAX_RETRIES_PER_FILE
    retries: int = 0
    error: Optional[str] = None
    cf_ray: Optional[str] = None

    def do_retry(self) -> bool:
        return self.retries < self.max_retries

    def get_path(self, temp: bool = False) -> str:
        directory = self.directory
        return os.path.join(directory, self.get_filename(temp))

    def get_filename(self, temp: bool = False) -> str:
        if temp:
            return self.filename + DOWNLOAD_TEMP_SUFFIX
        else:
            return self.filename

    def set_status_cancelled(self) -> None:
        # do not overwrite final states
        with self.lock:
            is_done = self.status == DownloadStatus.DONE
            has_error = self.status == DownloadStatus.ERROR
            if not is_done and not has_error:
                self.status = DownloadStatus.CANCELLED

    def set_status_ongoing(self) -> bool:
        res = True
        # do not overwrite user cancellation
        with self.lock:
            if self.status != DownloadStatus.CANCELLED:
                self.status = DownloadStatus.ONGOING
            else:
                res = False
        return res

    def set_status_error(self) -> None:
        with self.lock:
            self.status = DownloadStatus.ERROR

    def set_status_done(self) -> None:
        with self.lock:
            self.status = DownloadStatus.DONE


class AssetDownload:
    addon = None  # PoliigonAddon - No typing due to circular import
    data_payload: Dict

    tpe: ThreadPoolExecutor

    asset_data: AssetData = None
    uuid: Optional[str] = None
    download_list: Optional[List[FileDownload]] = None
    dynamic_files_list: Optional[List[DynamicFile]] = None
    size_asset_bytes_expected: int = 0
    size_asset_bytes_downloaded: int = 0

    # Directory (named after the size) to be used for convention 1 assets
    dir_size_target: str = None

    # Status flags
    max_retries: int = MAX_RETRIES_PER_ASSET
    retries: int = 0
    stop_files_retry: bool = False
    all_done: bool = False
    is_cancelled: bool = False
    any_error: bool = False
    res_error: Optional[str] = None
    res_error_message: Optional[str] = None
    error_dl_list: List[FileDownload] = list
    dl_error: Optional[FileDownload] = None

    def __init__(self,
                 addon,  # PoliigonAddon - No typing due to circular import
                 asset_data: AssetData,
                 size: str,
                 dir_target: str,
                 download_lods: bool = False,
                 native_mesh: bool = False,
                 renderer: Optional[str] = None,
                 update_callback: Optional[Callable] = None,
                 get_download_data_callback: Optional[Callable] = None
                 ) -> None:
        self.addon = addon
        self.asset_data = asset_data
        self.size = size

        # TODO(Joao): Add lods list parameter to the class and assign to
        #  self.lods when select download lods feature is available.
        #  Currently if the download is set do download lods, all the lods will
        #  be downloaded. There is no way to download only some given lods;
        self.download_lods = download_lods
        self.lods = None

        self.native_mesh = native_mesh
        self.renderer = renderer

        self.update_callback = update_callback
        self.get_download_data_callback = get_download_data_callback
        self.get_download_data_callback_called = False

        self.dir_target = os.path.join(dir_target, asset_data.asset_name)
        self.download_list = []

        self.convention = self.asset_data.get_convention()
        self.type_data = self.asset_data.get_type_data()
        self.workflow = self.type_data.get_workflow()

        self.identified_previews = 0
        self.previews_reported = False

        self.timer = DownloadTimer()

    def kickoff_download(self) -> bool:
        self.set_data_payload()
        self.create_download_folder()

        self.tpe = ThreadPoolExecutor(max_workers=MAX_PARALLEL_DOWNLOADS_PER_ASSET)

        self.run_asset_download_retries(self.download_asset)
        return self.all_done and not self.is_cancelled

    def download_asset(self) -> None:
        self.get_download_list()

        if self.download_list in [None, []]:
            self.any_error = True
            if self.res_error is not None:
                err = self.res_error
            else:
                err = "Empty download list"

            msg = f"AssetId: {self.asset_data.asset_id} Error: {err}"
            self.asset_data.state.dl.set_error(error_msg=err)
            self.addon.logger_dl.error(msg)

            # Only report to Sentry if the error is not Max Download rate
            if err != ERR_LIMIT_DOWNLOAD_RATE:
                self.addon._api.report_message("download_asset_empty_download_list",
                                               msg,
                                               "error")
            return

        self.download_loop()

    def set_data_payload(self) -> None:
        self.data_payload = {
            "assets": [
                {
                    "id": self.asset_data.asset_id,
                    "name": self.asset_data.asset_name
                }
            ]
        }

        self.data_payload["assets"][0]["sizes"] = [self.size]

        if self.asset_data.asset_type == AssetType.TEXTURE:
            self.set_texture_payload()
        elif self.asset_data.asset_type == AssetType.MODEL:
            self.set_model_payload()
        elif self.asset_data.asset_type == AssetType.HDRI:
            # HDRIs don't require any additional payload. The logic for defining
            # which maps should be downloaded is implemented on the server backend.
            # This change was made to support .hdr files and specify which DCCs
            # they should be downloaded/imported for;
            pass

    def set_texture_payload(self) -> None:
        if self.convention == 0:
            map_codes = self.type_data.get_map_type_code_list(self.workflow)
            self.data_payload["assets"][0]["workflows"] = [self.workflow]
            self.data_payload["assets"][0]["type_codes"] = map_codes
        elif self.convention == 1:
            prefs_available = self.addon.user.map_preferences is not None
            use_prefs = self.addon.user.use_preferences_on_download
            if prefs_available and use_prefs:
                map_descs, _ = self.type_data.get_maps_per_preferences(
                    self.addon.user.map_preferences,
                    filter_extensions=True)
            else:
                map_descs = self.type_data.map_descs[self.workflow]

            map_list = []
            for _map_desc in map_descs:
                file_format = "UNKNOWN"
                for _ff in SUPPORTED_TEX_FORMATS:
                    if _ff in _map_desc.file_formats:
                        file_format = _ff
                        break
                if file_format == "UNKNOWN":
                    map_name = _map_desc.display_name
                    msg = (f"UNKNWOWN file format for download; "
                           f"Asset Id: {self.asset_data.asset_id} Map: {map_name}")
                    self.addon._api.report_message(
                        "download_invalid_format", msg, "error")
                    self.addon.logger_dl.error(msg)

                map_dict = {
                    "type": _map_desc.map_type_code,
                    "format": file_format
                }
                map_list.append(map_dict)
            self.data_payload["assets"][0]["maps"] = map_list

    def set_model_payload(self) -> None:
        if self.download_lods:
            self.lods = self.asset_data.get_type_data().get_lod_list()
            if self.lods not in [[], ["NONE"]]:
                self.data_payload["assets"][0]["lods"] = self.lods
        if self.native_mesh and self.renderer is not None:
            self.data_payload["assets"][0]["softwares"] = [self.addon._api.software_dl_dcc]
            self.data_payload["assets"][0]["renders"] = [self.renderer]
        else:
            self.data_payload["assets"][0]["softwares"] = ["Generic"]

    def create_download_folder(self) -> bool:
        try:
            os.makedirs(self.dir_target, exist_ok=True)
        except PermissionError:
            self.asset_data.state.dl.set_error(error_msg=ERR_OS_NO_PERMISSION)
            self.addon.logger_dl.exception(
                f"{ERR_OS_NO_PERMISSION}: {self.dir_target}")
            return False
        except OSError as e:
            self.asset_data.state.dl.set_error(error_msg=str(e))
            self.addon.logger_dl.exception(f"Download directory: {self.dir_target}")
            return False

        self.addon.logger_dl.debug(f"Download directory: {self.dir_target}")
        self.asset_data.state.dl.set_directory(self.dir_target)

        # For convention 1 it should be saved in a size folder
        if self.size is not None and self.convention == 1:
            self.dir_size_target = os.path.join(self.dir_target, self.size)
            if not os.path.isdir(self.dir_size_target):
                os.makedirs(self.dir_size_target, exist_ok=True)

        return True

    def get_download_list(self) -> None:
        self.timer.start()
        # Getting dl list (FileDownload) and total bytes size
        res = self.addon._api.download_asset_get_urls(self.data_payload)
        if not res.ok:
            self.res_error = res.error
            custom_msg = res.body.get("errors", {}).get("message", [])
            if len(custom_msg) > 0:
                self.res_error_message = custom_msg[0]
            return

        self.build_download_list(res)

        self.addon.logger_dl.info(
            f"=== Requesting URLs took {self.timer.end():.3f} s.")

    def define_download_folder(self, filename: str) -> str:
        if self.convention == 0:
            return self.dir_target

        dl_folder = self.dir_size_target
        base_filename, suffix = os.path.splitext(filename)
        base_filename_low = base_filename.lower()

        last_preview = None
        for _preview in PREVIEWS:
            if base_filename_low.endswith(_preview):
                dl_folder = self.dir_target
                self.identified_previews += 1
                last_preview = filename

        if self.identified_previews > 3 and not self.previews_reported:
            msg = (f"Identifying multiple Preview images for "
                   f"Asset id: {self.asset_data.asset_id} (e.g {last_preview})")
            self.addon._api.report_message(
                "multiple_previews", msg, level="info")
            self.previews_reported = True

        return dl_folder

    @staticmethod
    def get_files_list(res) -> Tuple[List, List]:
        files_dict_list = [_files_dict
                           for _files_dict in res.body.get("payload", [])
                           if "files" in _files_dict.keys()]
        files_list = None
        dynamic_files_list = None
        if len(files_dict_list) > 0:
            files_list = files_dict_list[0].get("files")
            # Dynamic files expected only for textures
            if files_dict_list[0].get("dynamic_files"):
                dynamic_files_list = files_dict_list[0].get("dynamic_files")
        return files_list, dynamic_files_list

    def build_download_list(self, res: ApiResponse) -> None:
        files_list, dynamic_files = self.get_files_list(res)

        self.uuid = res.body.get("uuid", None)
        if self.uuid in [None, ""]:
            self.addon.logger_dl.error("No UUID for download")

        model_exists = False
        filename_model_fbx_source = None
        url_model_fbx_source = None
        size_expected_model_fbx_source = 0
        for url_dict in files_list:
            url = url_dict.get("url")
            filename = url_dict.get("name")
            size_expected = url_dict.get("bytes", 0)
            resolution_size = url_dict.get("resolution", None)

            self.size_asset_bytes_expected += size_expected
            if not url or not filename:
                raise RuntimeError(f"Missing url or filename {url}")
            elif "_SOURCE" in filename:
                if filename.lower().endswith(".fbx"):
                    filename_model_fbx_source = filename
                    url_model_fbx_source = url
                    size_expected_model_fbx_source = size_expected
                continue

            filename_ext = os.path.splitext(filename)[1].lower()
            filename_ext = filename_ext[1:]  # get rid of dot
            if filename_ext.lower() in MODEL_FILE_EXT:
                model_exists = True

            dl = FileDownload(
                asset_id=self.asset_data.asset_id,
                url=url,
                filename=filename,
                convention=self.convention,
                size_expected=size_expected,
                resolution_size=resolution_size,
                directory=self.define_download_folder(filename))
            self.download_list.append(dl)

        # Fallback if "xyz_SOURCE.fbx" is the only model file
        if filename_model_fbx_source is not None and not model_exists:
            dl = FileDownload(asset_id=self.asset_data.asset_id,
                              url=url_model_fbx_source,
                              filename=filename_model_fbx_source,
                              convention=self.convention,
                              size_expected=size_expected_model_fbx_source,
                              directory=self.dir_target)
            self.download_list.append(dl)
            msg = f"Model asset with just SOURCE LOD: {self.asset_data.asset_id}"
            self.addon._api.report_message(
                "model_with_only_source_lod", msg, level="info")

        self.set_dynamic_files(dynamic_files)

    def set_dynamic_files(self,
                          dynamic_files_api: Optional[List[Dict]]
                          ) -> None:
        """Reads dynamic file information from server's API response."""

        if dynamic_files_api is None:
            return

        self.dynamic_files_list = []
        for _dynamic_file_dict in dynamic_files_api:
            name = _dynamic_file_dict.get("name", None)
            contents = _dynamic_file_dict.get("contents", None)
            dynamic_file = DynamicFile(name=name, contents=contents)
            self.dynamic_files_list.append(dynamic_file)

    def download_loop(self) -> None:
        """The actual download loop in download_asset_sync()."""

        self.all_done = False
        self.addon.logger_dl.debug("Download Loop")

        self.asset_data.state.dl.set_progress(0.001)
        if self.asset_data.state.dl.is_cancelled():
            self.is_cancelled = True
            self.cancel_downloads()
            return

        self.schedule_downloads()
        self.download_asset_loop_poll()

        if self.all_done:
            # Consider download failed upon dynamic file error.
            #
            # ATM we will not expose any issues with dynamic file data from server
            # and let the entire download succeed, anyway.
            self.all_done = self.store_dynamic_files(expose_api_error=False)
            self.rename_downloads()

        return

    def track_quality(self) -> None:
        if self.uuid in [None, ""]:
            return

        if self.all_done:
            # User may still have cancelled download (judging by state in
            # asset data), but we suceeded anyway
            self.addon._api.track_download_quality(uuid=self.uuid,
                                                   status=DQStatus.SUCCESS)
        elif self.is_cancelled and not self.any_error:
            self.addon._api.track_download_quality(uuid=self.uuid,
                                                   status=DQStatus.CANCELED,
                                                   error="User cancelled download")
        else:
            file_dl_error = self.dl_error
            if file_dl_error is None:
                return
            msg = (f"Error: {file_dl_error.error}, "
                   f"File: {file_dl_error.url}, CF-ray: {file_dl_error.cf_ray}")
            self.addon._api.track_download_quality(uuid=self.uuid,
                                                   status=DQStatus.FAILED,
                                                   error=msg)

    def schedule_downloads(self,
                           download_list: Optional[List[FileDownload]] = None
                           ) -> None:
        """Submits downloads to thread pool."""

        if download_list is None:
            download_list = self.download_list
        self.addon.logger_dl.debug("Scheduling Downloads")

        download_list.sort(key=lambda dl: dl.size_expected)
        for download in download_list:
            # Andreas: Could also check here, if already DONE and not start
            #          the thread at all.
            #          Yet, I decided to prefer it handled by the thread itself.
            #          In this way the flow is always identical.
            download.status = DownloadStatus.WAITING
            download.retries += 1
            download.fut = self.tpe.submit(self.addon._api.download_asset_file,
                                           download=download)
            self.addon.logger_dl.debug(f"Submitted {download.filename}. "
                                       f"Retry: {download.retries}")
        self.addon.logger_dl.debug("Download Asset Schedule Done")

    def check_download_progress(self) -> None:
        self.addon.logger_dl.debug(self.download_list)
        self.any_error = False
        self.error_dl_list = []
        self.is_cancelled = self.asset_data.state.dl.is_cancelled()

        self.all_done = True
        self.size_asset_bytes_downloaded = 0
        for download in self.download_list:
            self.size_asset_bytes_downloaded += download.size_downloaded

            fut = download.fut
            if not fut.done():
                self.all_done = False
                continue

            res = fut.result()
            exc = fut.exception()
            res_error = res.error
            had_excp = exc is not None
            if not res.ok or had_excp:
                if had_excp:
                    self.addon.logger_dl.error(exc)
                self.any_error = True
                self.all_done = False
                download.error = res_error
                self.asset_data.state.dl.set_error(error_msg=res_error)
                self.error_dl_list.append(download)

        if self.any_error:
            self.process_file_retries()
        elif self.all_done:
            self.addon.logger_dl.debug("All Done :)")

        self.set_progress()

    def download_asset_loop_poll(self) -> None:
        """Used in download_asset_sync to poll results inside download loop."""

        self.addon.logger_dl.debug("Starting Download Poll Loop")
        while not self.all_done and not self.stop_files_retry and not self.is_cancelled:
            time.sleep(DOWNLOAD_POLL_INTERVAL)
            self.check_download_progress()

    def process_file_retries(self) -> None:
        """Manages the retries per file."""

        for dl_error in self.error_dl_list:
            if not dl_error.do_retry():
                self.dl_error = dl_error
                self.stop_files_retry = True
                break

        if not self.is_cancelled and not self.stop_files_retry:
            self.schedule_downloads(self.error_dl_list)
            return

        self.cancel_downloads()

    def cancel_downloads(self) -> None:
        """Cancels all download threads"""

        self.addon.logger_dl.debug("Start cancel")

        for download in self.download_list:
            download.set_status_cancelled()
            if download.fut is not None:
                download.fut.cancel()

        # Wait for threads to actually return
        self.addon.logger_dl.debug("Waiting")
        for download in self.download_list:
            if download.fut is None:
                continue
            if download.fut.cancelled():
                continue
            try:
                download.fut.result(timeout=60)
            except TimeoutError:
                # TODO(Andreas): Now there seems to be some real issue...
                msg = (f"Asset id {self.asset_data.asset_id} download file "
                       "future Timeout error with no result.")
                self.addon._api.report_message("download_file_with_no_result",
                                               msg,
                                               "error")
                raise
            except BaseException:
                msg = (f"Asset id {self.asset_data.asset_id} download file "
                       "exception with no result.")
                self.addon._api.report_message("download_file_with_no_result",
                                               msg,
                                               "error")
                self.addon.logger_dl.exception(f"Unexpected error: {msg}")
                raise

        self.addon.logger_dl.debug("Done")

    def set_progress(self) -> None:
        progress = self.size_asset_bytes_downloaded / max(self.size_asset_bytes_expected, 1)
        self.asset_data.state.dl.set_progress(max(progress, 0.001))
        self.asset_data.state.dl.set_downloaded_bytes(self.size_asset_bytes_expected)

        try:
            if not self.get_download_data_callback_called:
                self.get_download_data_callback()
                self.get_download_data_callback_called = True
        except TypeError:
            pass  # No Download data callback

        try:  # Init progress bar
            self.update_callback()
        except TypeError:
            pass  # No update callback

    def do_retry(self) -> bool:
        first_attempt = self.retries == 0
        if first_attempt:
            return True
        do_retry = self.retries < self.max_retries
        expired_error = False
        if self.dl_error is not None:
            expired_error = self.dl_error.error == ERR_URL_EXPIRED

        # Asset level download only retries in case of Expired URL
        return expired_error and do_retry

    def run_asset_download_retries(self, method: callable) -> None:
        while self.do_retry():
            self.retries += 1
            method()

        self.track_quality()
        self.cancel_downloads()

    def rename_downloads(self) -> Tuple[bool, str]:
        """Renames dowhloaded temp file."""
        self.addon.logger_dl.debug("Start rename")

        error_msg = ""
        all_successful = True
        for download in self.download_list:
            if download.status != DownloadStatus.DONE:
                self.addon.logger_dl.warning(("File status not done despite "
                                              "all files reported done!"))
            path_temp = download.get_path(temp=True)
            temp_exists = os.path.exists(path_temp)
            path_final = download.get_path(temp=False)
            final_exists = os.path.exists(path_final)
            if not temp_exists and final_exists:
                continue

            try:
                os.rename(path_temp, path_final)
            except FileExistsError:
                os.remove(path_temp)
            except FileNotFoundError:
                download.status = DownloadStatus.ERROR
                download.error = f"Missing file: {path_temp}"
                self.addon.logger_dl.error(
                    ("Neither temp download file nor target do exist\n"
                     f"    {path_temp}\n"
                     f"    {path_final}"))
                all_successful = False
            except PermissionError:
                # Note from Andreas:
                # I am not entirely sure, how this can happen (after all we
                # just downloaded the file...).
                # My assumption is, that somehow the download thread (while
                # already being done) did not actually exit, yet, maybe due to
                # some scheduling mishaps and is still keeping a handle to the
                # file. If I am correct, maybe a "sleep(0.1 sec)" and another
                # attempt to rename could get us out of this.
                # But that's of course pretty ugly and we should discuss
                # first, if we want to try something like this or just let
                # the download fail.
                download.status = DownloadStatus.ERROR
                download.error = ("Lacking permission to rename downloaded"
                                  f" file: {path_temp}")
                self.addon.logger_dl.error(
                    (f"No permission to rename download:\n  from: {path_temp}"
                     f"\n  to: {path_final}"))
                all_successful = False

            # Gets the first error found to give feedback for the user
            if error_msg is not None and download.error not in [None, ""]:
                error_msg = download.error

        self.addon.logger_dl.debug(f"Done, succeess = {all_successful}")
        return all_successful, error_msg

    def _check_xml_data(self,
                        xml_s: str,
                        expose_api_error: bool = False
                        ) -> bool:
        """Checks an XML string for correct XML structure."""

        asset_data = self.asset_data
        asset_id = asset_data.asset_id

        xml_ok = False
        try:
            # While we are not really interested in actual contents atm,
            # we parse the XML nevertheless to make sure it is "parseable".
            xml_root = ElementTree.XML(xml_s)
            if xml_root is not None:
                xml_ok = True
        except ElementTree.ParseError as e:
            if expose_api_error:
                asset_data.state.dl.set_error(error_msg="Dynamic file error")
            msg = (f"Could not save dynamic file for {asset_id}, "
                   f"XML parsing issue\n{e}")
            self.addon.logger_dl.exception(msg)
            self.addon._api.report_message("download_df_xml_issue", msg, "error")
        if not xml_ok:
            return False  # NOK reported above in exception

        return True

    def _check_dynamic_file_data(self,
                                 dynamic_file: DynamicFile,
                                 expose_api_error: bool = False
                                 ) -> bool:
        """Checks the dynamic file data (currently expecting XML) received
        from API.
        """

        asset_data = self.asset_data
        asset_id = asset_data.asset_id

        if dynamic_file.name is None:
            if expose_api_error:
                asset_data.state.dl.set_error(error_msg="Dynamic file error")
            msg = (f"Could not save dynamic file for {asset_id}, "
                   "no name provided")
            self.addon.logger_dl.error(msg)
            self.addon._api.report_message("download_df_no_filename", msg, "error")
            return False
        contents = dynamic_file.contents
        if contents is None:
            if expose_api_error:
                asset_data.state.dl.set_error(error_msg="Dynamic file error")
            msg = (f"Could not save dynamic file for {asset_id}, "
                   "no contents provided")
            self.addon.logger_dl.error(msg)
            self.addon._api.report_message("download_df_no_contents", msg, "error")
            return False

        return self._check_xml_data(contents, expose_api_error)

    def _store_single_dynamic_file(self,
                                   dynamic_file: DynamicFile,
                                   expose_api_error: bool = False
                                   ) -> bool:
        """Stores a dynamic file (currently only XML data) to disk."""

        asset_data = self.asset_data
        asset_id = asset_data.asset_id

        result = self._check_dynamic_file_data(dynamic_file, expose_api_error)
        if not result:
            # Here download fails only, if exposure of errors in dynamic_file
            # data from server is desired.
            return not expose_api_error

        # Since we need to store into the correct "size" subfolder and
        # also since MaterialX does have little sense, if there were no other
        # files downloaded, we'll use the path of the first FileDownload
        if len(self.download_list) > 0:
            file_download = self.download_list[0]
            path_file = file_download.get_path()
            dir_asset = os.path.dirname(path_file)
        else:
            # Without any file downloads, all we have here is asset's path:
            dir_asset = self.asset_data.state.dl.get_directory()
        path_dynamic_file = os.path.join(dir_asset, dynamic_file.name)

        try:
            with open(path_dynamic_file, "w") as write_file:
                write_file.write(dynamic_file.contents)
        except OSError as e:
            if e.errno == errno.ENOSPC:
                asset_data.state.dl.set_error(error_msg=ERR_OS_NO_SPACE)
                msg = f"Asset {asset_id}: No space for dynamic file."
                # TODO(Andreas): No logger in PoliigonConnector, yet
                self.addon.logger_dl.exception(msg)
                self.addon._api.report_message("download_df_no_space", msg, "error")
            elif e.errno == errno.EACCES:
                asset_data.state.dl.set_error(
                    error_msg=ERR_OS_NO_PERMISSION)
                msg = f"Asset {asset_id}: No permission to write dynamic file."
                # TODO(Andreas): No logger in PoliigonConnector, yet
                self.addon.logger_dl.exception(msg)
                self.addon._api.report_message("download_df_permission", msg, "error")
            else:
                asset_data.state.dl.set_error(error_msg=str(e))
                msg = (f"Asset {asset_id}: Unexpected error "
                       "upon writing dynamic file.")
                # TODO(Andreas): No logger in PoliigonConnector, yet
                self.addon.logger_dl.logger.exception(msg)
                msg += f"\n{e}"
                self.addon._api.report_message("download_df_os_error", msg, "error")
            # Note: Even if dynamic file data issue above does not get exposed
            #       to user, any failure to write the correct MaterialX data
            #       will still lead to a failed download.
            return False
        return True

    def store_dynamic_files(self,
                            expose_api_error: bool = False
                            ) -> bool:
        """Stores all dynamic files belonging to an asset download to disk."""

        if self.dynamic_files_list is None:
            return True
        if len(self.dynamic_files_list) == 0:
            return True

        # Note: We'll get here only after all asset files got downloaded
        #       successfully. Thus we can store any dynamic files errors in
        #       AssetData's download status (no need to be afraid of
        #       overwriting any other error) to present in UI.
        for _dynamic_file in self.dynamic_files_list:
            result = self._store_single_dynamic_file(_dynamic_file,
                                                     expose_api_error)
            if not result:
                return False
        return True
