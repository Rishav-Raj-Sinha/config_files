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

from dataclasses import dataclass
import json
import os
from queue import (
    Empty,
    Queue)
import shutil
import sys
from threading import Thread
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from bpy.types import Operator
from bpy.props import StringProperty
import bpy

from ..modules.poliigon_core.assets import (
    AssetData,
    AssetType)
from ..modules.poliigon_core.multilingual import _t
from ..material_import_utils import ASSET_TYPE_TO_IMPORTED_TYPE
from ..constants import ASSET_ID_ALL
from ..toolbox import get_context
from .. import reporting
from .asset_browser_sync_commands import (
    CMD_MARKER_START,
    CMD_MARKER_END,
    SyncCmd,
    SyncAssetBrowserCmd)


@dataclass
class ScriptContext():
    path_cat: Optional[str] = None  # from command line args
    path_categories: Optional[str] = None  # from command line args

    poliigon_categories: Optional[Dict] = None

    listener_running: bool = False
    thd_listener: Optional[Thread] = None

    sender_running: bool = False
    thd_sender: Optional[Thread] = None

    queue_cmd: Optional[Queue] = None
    queue_send: Optional[Queue] = None
    queue_ack: Optional[Queue] = None

    main_running: bool = False


class POLIIGON_OT_sync_client(Operator):
    bl_idname = "poliigon.asset_browser_sync_client"
    bl_label = _t("Sync Client")
    bl_category = "Poliigon"
    bl_description = _t("To be used in client Blender process to work on "
                        "commands sent by host blender.")
    bl_options = {"INTERNAL"}

    path_catalog: StringProperty(options={"HIDDEN"})  # noqa: F821
    path_categories: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @staticmethod
    def _check_command(ctx: ScriptContext,
                       buf: str
                       ) -> Tuple[Optional[SyncAssetBrowserCmd], str]:
        """Returns a valid command, otherwise None.
        Upon detecting a corrupted command, CMD_ERROR gets sent.

        Return value:
        Tuple with two entries:
        Tuple[0]: A valid command or None
        Tuple[1]: Remaining buf after either a valid command got detected or
                  an broken command got removed
        """

        if CMD_MARKER_END not in buf:
            return None, buf

        pos_delimiter = buf.find(CMD_MARKER_END, 1)
        cmd_json = buf[:pos_delimiter]
        buf = buf[pos_delimiter + len(CMD_MARKER_END):]

        if CMD_MARKER_START in cmd_json:
            pos_marker_start = cmd_json.find(CMD_MARKER_START, 1)
            cmd_json = cmd_json[pos_marker_start + len(CMD_MARKER_START):]
        else:
            ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.CMD_ERROR))
            cmd_json = None
        return cmd_json, buf

    @staticmethod
    def _thread_listener(ctx: ScriptContext) -> None:
        """Listens to commands sent by host and checks their integrity.

        In case of error requests a command to be re-send from host via
        CMD_ERROR.
        Valid commands are then sorted into two queues, one for received acks
        (forwarding them to unblock sender), one for job commands (forwarding
        them to main loop).
        """

        cTB.logger_ab.debug("thread_listener")
        ctx.listener_running = True
        buf = ""
        while ctx.listener_running:
            # Wait for messages from host, concatenating received lines
            # into buf
            try:
                buf += sys.stdin.readline()
            except KeyboardInterrupt:
                time.sleep(0.5)
                if ctx.listener_running:
                    continue

            if not ctx.listener_running:
                break

            cmd_json, buf = POLIIGON_OT_sync_client._check_command(ctx, buf)
            if cmd_json is None:
                continue

            try:
                cmd_from_host = SyncAssetBrowserCmd.from_json(cmd_json)
                if cmd_from_host.code == SyncCmd.CMD_ERROR:
                    # Forward ack to thread_sender
                    ctx.queue_ack.put(cmd_from_host)
                else:
                    # Forward job command to main loop
                    ctx.queue_cmd.put(cmd_from_host)
            except Exception:
                ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.CMD_ERROR))
                cTB.logger_ab.exception(f"CMD ERROR {cmd_json}")

        cTB.logger_ab.debug("thread_listener EXIT")
        ctx.thd_listener = None

    @staticmethod
    def _start_listener(ctx: ScriptContext) -> None:
        """Starts thread_listener()"""

        ctx.thd_listener = Thread(
            target=POLIIGON_OT_sync_client._thread_listener,
            args=(ctx, ),
            daemon=True)
        ctx.thd_listener.start()

    @staticmethod
    def _flush_queue_ack(ctx: ScriptContext) -> None:
        """Removes all content from ack queue"""

        while not ctx.queue_ack.empty():
            try:
                ctx.queue_ack.get_nowait()
            except ctx.queue_ack.Empty:
                break

    @staticmethod
    def _shutdown_on_error(ctx: ScriptContext) -> None:
        """Shuts the client down"""

        # The client quits and host will pick up the "client loss" due to
        # timeouts
        ctx.sender_running = False
        ctx.listener_running = False
        ctx.main_running = False
        sys.stdin.close()  # unblock listener

    @staticmethod
    def _thread_sender(ctx: ScriptContext) -> None:
        """Sends commands to host.

        For commands expecting an acknowledge message the thread will then
        block until the ack is received (or possibly resend the command if
        CMD_ERROR is received).
        """

        cTB.logger_ab.debug("thread_sender")
        ctx.sender_running = True
        while ctx.sender_running:
            # Get rid of any unwanted acks from previous commands
            POLIIGON_OT_sync_client._flush_queue_ack(ctx)

            # Wait for something to send
            try:
                cmd_send = ctx.queue_send.get(timeout=1.0)
                ctx.queue_send.task_done()
            except Empty:
                if ctx.sender_running:
                    continue

            if not ctx.sender_running:
                break

            cTB.logger_ab.debug(f"Send: {cmd_send.code.name}")
            cmd_send.send_to_stdio()

            # Depending on sent command code, we are already done
            if cmd_send.code in [SyncCmd.ASSET_OK, SyncCmd.ASSET_ERROR]:
                # ASSET_OK, ASSET_ERROR are fire and forget,
                # just proceed with next command
                continue
            elif cmd_send.code == SyncCmd.EXIT_ACK:
                # EXIT_ACK is fire and forget, we are done here
                ctx.sender_running = False
                break

            # Wait for acknowledge message
            # TODO(Andreas): Currently this low retry count causes issues with
            #                Patrick's library on a NAS and then likely exposes
            #                a bug in timeout handling.
            retries = 3
            while retries > 0 and ctx.sender_running:
                try:
                    cmd_ack = ctx.queue_ack.get(timeout=15.0)
                    ctx.queue_ack.task_done()
                except Empty:
                    cmd_ack = None

                retries -= 1
                if cmd_ack is None:
                    # queue timeout,
                    # unless retries are exhausted continue to wait
                    if retries == 0:
                        # Unlikely we can gracefully recover
                        POLIIGON_OT_sync_client._shutdown_on_error(ctx)
                        break
                elif cmd_ack.code == SyncCmd.CMD_ERROR:
                    # last sent command was not received well -> resend
                    if retries > 0:
                        cmd_send.send_to_stdio()
                    else:
                        # Unlikely we can gracefully recover
                        POLIIGON_OT_sync_client._shutdown_on_error(ctx)
                elif cmd_ack.code == SyncCmd.CMD_DONE:
                    # last sent command was ok, continue with next
                    break

        cTB.logger_ab.debug("thread_sender EXIT")
        ctx.thd_sender = None

    @staticmethod
    def _start_sender(ctx: ScriptContext) -> None:
        """Starts thread_sender()"""

        ctx.thd_sender = Thread(
            target=POLIIGON_OT_sync_client._thread_sender,
            args=(ctx, ),
            daemon=True)
        ctx.thd_sender.start()

    @staticmethod
    def _startup(ctx: ScriptContext) -> None:
        cTB.logger_ab.debug("waiting for asset data...")
        bpy.ops.poliigon.get_local_asset_sync(
            await_startup_poliigon=False,
            await_startup_my_assets=True,
            get_poliigon=False,
            get_my_assets=False,
            abort_ongoing_jobs=False)
        cTB.logger_ab.debug("...done.")

        if not POLIIGON_OT_sync_client._read_poliigon_categories(ctx):
            return False

        ctx.queue_cmd = Queue()
        ctx.queue_send = Queue()
        ctx.queue_ack = Queue()

        POLIIGON_OT_sync_client._start_listener(ctx)
        POLIIGON_OT_sync_client._start_sender(ctx)

        ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.HELLO))
        return True

    @staticmethod
    def _reset_blend():
        """Prepares a fresh blend file for stuff to be imported into."""

        bpy.ops.wm.read_homefile(use_empty=True)

        # To be safe deselect all
        for obj in bpy.data.objects:
            obj.select_set(False)

    @staticmethod
    def _save_blend(path: str) -> bool:
        """Saves the current blend file."""

        # Remove previous file
        # (host will re-process assets only, if force parameter was set)
        if os.path.exists(path):
            os.remove(path)

        path_norm = os.path.normpath(path)
        result = bpy.ops.wm.save_mainfile(filepath=path_norm,
                                          check_existing=False,
                                          exit=False)
        return result == {"FINISHED"}

    @staticmethod
    def _get_unique_uuid(catalog_dict: Dict) -> str:
        """Returns a new, random UUID, which does not already exist
        in catalog.
        """

        uuid_is_unique = False
        while not uuid_is_unique:
            uuid_result = str(uuid4())
            uuid_is_unique = True
            for uuid_existing, _, _ in catalog_dict.values():
                if uuid_result == uuid_existing:
                    uuid_is_unique = False
                    break
        return uuid_result

    # Based on code from:
    # https://blender.stackexchange.com/questions/249316/python-set-asset-library-tags-and-catalogs
    @staticmethod
    def _get_catalog_dict(ctx: ScriptContext) -> Dict:
        """Reads blender's catalogue and returns a dictionary with its content.

        Return value:
        Dict: {catalog tree path: (uuid, catalog tree path, catalog name)}
        """

        if not os.path.exists(ctx.path_cat):
            return {}
        catalogs = {}
        with open(ctx.path_cat, "r") as file_catalogs:
            for line in file_catalogs.readlines():
                if line.startswith(("#", "VERSION", "\n")):
                    continue
                # Each line contains:
                # 'uuid:catalog_tree:catalog_name' + eol ('\n')
                uuid, tree_path, name = line.split(":")
                name = name.split("\n")[0]
                catalogs[tree_path] = (uuid, tree_path, name)
        return catalogs

    @staticmethod
    def _catalog_file_header(version: int = 1):
        """Returns the standard header of a catalog file."""

        header = (
            "# This is an Asset Catalog Definition file for Blender.\n"
            "#\n"
            "# Empty lines and lines starting with `#` will be ignored.\n"
            "# The first non-ignored line should be the version indicator.\n"
            '# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"\n'
            "\n"
            f"VERSION {version}\n"
            "\n")
        return header

    @staticmethod
    def _write_catalog_file(ctx: ScriptContext, catalog_dict: Dict) -> bool:
        """Writes a catalog dict into a new catalog file,
        replacing the old file upon success.
        """

        path_cat_temp = ctx.path_cat + ".TEMP"
        path_cat_bak = ctx.path_cat + ".BAK"
        try:
            # Write into temporary file
            with open(path_cat_temp, "w") as file_catalogs:
                header = POLIIGON_OT_sync_client._catalog_file_header()
                file_catalogs.write(header)
                for _uuid, tree_path, name in catalog_dict.values():
                    file_catalogs.write(f"{_uuid}:{tree_path}:{name}\n")

            # Replace existing catalog file (if any) with above temporary file
            if os.path.exists(ctx.path_cat):
                shutil.move(ctx.path_cat, path_cat_bak)
            shutil.move(path_cat_temp, ctx.path_cat)
            if os.path.exists(path_cat_bak):
                os.remove(path_cat_bak)
        except IsADirectoryError:
            # Should not occur, it's our files
            cTB.logger_ab.exception("IsADirectoryError")
            return False
        except FileNotFoundError:
            # Should not occur, it's being tested above
            cTB.logger_ab.exception("FileNotFoundError")
            return False
        except OSError:
            # Faied to create file
            cTB.logger_ab.exception("OSError")
            return False
        except Exception:
            cTB.logger_ab.exception("Unexpected exception!")
            return False
        return True

    @staticmethod
    def _read_poliigon_categories(ctx: ScriptContext) -> bool:
        """Reads all Poliigon categories into a dict in context."""

        if not os.path.exists(ctx.path_categories):
            cTB.logger_ab.debug("Poliigon categories file missing")
            ctx.poliigon_categories = {"HDRIs": [],
                                       "Models": [],
                                       "Textures": []
                                       }
            return False

        with open(ctx.path_categories, "r") as file_categories:
            try:
                ctx.poliigon_categories = json.load(file_categories)
            except json.JSONDecodeError:
                cTB.logger_ab.debug("Poliigon's category file is corrupt!")
                return False

        ctx.poliigon_categories = ctx.poliigon_categories["poliigon"]
        return True

    @staticmethod
    def _get_unique_category_list(
            ctx: ScriptContext, asset_data: AssetData) -> List[str]:
        """Returns a list of categories matching the first (alphabetically)
        matching branch in Poliigon's category tree."""

        asset_type = asset_data.asset_type
        asset_name = asset_data.asset_name

        asset_type_cat = ASSET_TYPE_TO_IMPORTED_TYPE[asset_type]
        if asset_type_cat not in ctx.poliigon_categories:
            cTB.logger_ab.debug("!!! Asset type not found "
                                f"{asset_name} {asset_type}")
            cTB.logger_ab.debug("   Category types "
                                f"{list(ctx.poliigon_categories.keys())}")
            return [asset_type.name]

        # Have copy, as we are removing some categorie during the process
        asset_categories = asset_data.categories.copy()

        if "free" in asset_categories:
            asset_categories.remove("free")
        if asset_type_cat in asset_categories:
            # It gets prepended anyway in next step
            asset_categories.remove(asset_type_cat)

        category_list = [asset_type_cat]
        for _id_category in asset_categories:
            cat_path = cTB.category_ids.get(_id_category, None)
            if cat_path is None:
                continue
            sub_cats = cat_path.split("/")[2:]  # skip asset type
            if len(sub_cats) == 0:
                continue
            sub_cats = [_cat.replace("-", " ").title() for _cat in sub_cats]
            cat = sub_cats[-1]
            cat_slug = "/" + "/".join(sub_cats)
            if cat_slug not in ctx.poliigon_categories[asset_type_cat]:
                break
            category_list.append(cat)

        return category_list

    @staticmethod
    def _add_catalog(
            ctx: ScriptContext, asset_data: AssetData, entity: Any) -> bool:
        """Assigns a catalog to an entity (object, collection, material,
        world,...).

        If needed, the catalog file will be extended with additional catalogs
        based on the categories of the asset.
        """

        catalog_dict = POLIIGON_OT_sync_client._get_catalog_dict(ctx)
        asset_categories = POLIIGON_OT_sync_client._get_unique_category_list(
            ctx, asset_data)

        # After this loop uuid_result contains the UUID of the leaf catalog
        uuid_result = None
        for idx_cat, category in enumerate(asset_categories):
            category_path = "/".join(asset_categories[:idx_cat + 1])
            if category_path not in catalog_dict:
                uuid_result = POLIIGON_OT_sync_client._get_unique_uuid(
                    catalog_dict)
                catalog_dict[category_path] = (uuid_result,
                                               category_path,
                                               category)
            else:
                uuid_result, _, _ = catalog_dict[category_path]

        if not POLIIGON_OT_sync_client._write_catalog_file(
                ctx, catalog_dict):
            cTB.logger_ab.debug("add_catalog(): Failed to write catalog file")
            return False

        if not uuid_result:
            print("Failed to assign meta, but returning positive to continue")
            return False

        # Finally assign the determined UUID to the entity
        entity.asset_data.catalog_id = uuid_result
        return True

    @staticmethod
    def _assign_asset_tags(
            asset_data: AssetData, entity: Any, params: Dict) -> None:
        """Assigns tags to an entity (object, collection, material, world,...).

        NOTE: This function requires entity.asset_mark() to be called
              beforehand.

        Args:
            asset_data: AssetData
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        asset_name = asset_data.asset_name
        asset_display_name = asset_data.display_name
        asset_type = asset_data.asset_type

        entity.asset_data.tags.new(asset_display_name)
        entity.asset_data.tags.new(asset_name)  # unique name
        entity.asset_data.tags.new("Poliigon")

        category_names = []
        for _id_category in asset_data.categories:
            # TODO(Andreas): maybe we want to filter free?

            cat_path = cTB.category_ids.get(_id_category, None)
            if cat_path is None:
                cTB.logger_ab.error("UNKNOWN CATEGORY_ID: ", _id_category)
                continue

            # [:1] - Skip initial "/" to avoid empty list entry upon split
            cat_names = cat_path[1:].split("/")
            category_names.extend(cat_names)

        category_names = list(set(category_names))
        if len(category_names) == 0:
            asset_type_cat = ASSET_TYPE_TO_IMPORTED_TYPE[asset_type]
            category_names = [asset_type_cat]

        for _category in category_names:
            entity.asset_data.tags.new(_category.title())

        if asset_type == AssetType.HDRI:
            entity.asset_data.tags.new(params["size"])
            entity.asset_data.tags.new(params["size_bg"])
        elif asset_type == AssetType.MODEL:
            entity.asset_data.tags.new(params["size"])
            entity.asset_data.tags.new(params["lod"])
        elif asset_type == AssetType.TEXTURE:
            entity.asset_data.tags.new(params["size"])
        else:
            raise NotImplementedError(f"Unsupported asset type: {asset_type}")

    @staticmethod
    def _assign_asset_preview(
            asset_data: AssetData, entity: Any, params: Dict) -> None:
        """Assigns a preview image to an entity (object, collection, material,
        world,...).

        NOTE: This function requires entity.asset_mark() to be called
              beforehand.

        Args:
            asset_data: AssetData
            entity: Blender's object, collection, material, ...
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        path_thumb = params["thumb"]
        is_path = path_thumb is not None and len(path_thumb) > 2
        if is_path and os.path.exists(path_thumb):
            # From: https://blender.stackexchange.com/questions/6101/poll-failed-context-incorrect-example-bpy-ops-view3d-background-image-add
            # and: https://blender.stackexchange.com/questions/245397/batch-assign-pre-existing-image-files-as-asset-previews

            # equal to: if bpy.app.version >= (3, 2, 0)
            if hasattr(bpy.context, "temp_override"):
                with bpy.context.temp_override(id=entity):
                    bpy.ops.ed.lib_id_load_custom_preview(
                        filepath=path_thumb)
            else:
                bpy.ops.ed.lib_id_load_custom_preview(
                    {"id": entity}, filepath=path_thumb)
        else:
            # TODO(Andreas): Not working as expected
            #                Maybe https://developer.blender.org/T93893 ?
            entity.asset_generate_preview()

    @staticmethod
    def _assign_asset_meta_data(ctx: ScriptContext,
                                asset_data: AssetData,
                                entity: Any,
                                params: Dict) -> bool:
        """Assigns all meta data (e.g. author, tags, preview, catalog...) to an
        entity (object, collection, material, world,...).

        Args:
            ctx: ScriptContext instance created upon script start
            asset_data: AssetData
            entity: Blender's object, collection, material, ...
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        if hasattr(entity, "type"):
            type_label = f", type: {entity.type}"
        elif isinstance(entity, bpy.types.Material):
            type_label = ", type: Material"
        else:
            type_label = ", type: UNKNOWN"
        cTB.logger_ab.debug(f"Marking {entity.name} {type_label}")

        entity.asset_mark()

        entity.asset_data.author = "Poliigon"
        entity.asset_data.description = asset_data.display_name

        try:
            POLIIGON_OT_sync_client._assign_asset_tags(
                asset_data, entity, params)
        except NotImplementedError:
            cTB.logger_ab.exception("Unsupported Asset Type")
            return False
        POLIIGON_OT_sync_client._assign_asset_preview(
            asset_data, entity, params)
        if not POLIIGON_OT_sync_client._add_catalog(ctx, asset_data, entity):
            cTB.logger_ab.debug(
                "assign_asset_meta_data(): Failed to add catalog")
            return False

        return True

    @staticmethod
    def _process_hdri(
            ctx: ScriptContext, asset_data: AssetData, params: Dict) -> bool:
        """Processes an HDRI asset.

        Args:
            ctx: ScriptContext instance created upon script start
            asset_data: An asset data dict passed down from P4B host.
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        if "size" not in params or "thumb" not in params:
            cTB.logger_ab.debug(
                "Missing required parameter (size and/or thumb) to process "
                "HDRI")
            return False

        asset_id = asset_data.asset_id
        asset_name = asset_data.asset_name
        size = params["size"]
        size_bg = params["size_bg"]

        cTB.logger_ab.debug(f"process_hdri {asset_name} {size}")
        try:
            result = bpy.ops.poliigon.poliigon_hdri(
                asset_id=asset_id,
                size=size,
                size_bg=size_bg)
        except Exception:
            cTB.logger_ab.exception("HDRI ERROR")
            return False

        if result != {"FINISHED"}:
            return False

        # Rename world,
        # otherwise the asset would appear as "World" in the Asset Browser.
        world = bpy.context.scene.world
        world.name = asset_name

        if not POLIIGON_OT_sync_client._assign_asset_meta_data(
                ctx, asset_data, world, params):
            return False

        return True

    @staticmethod
    def _process_model(
            ctx: ScriptContext, asset_data: AssetData, params: Dict) -> bool:
        """Processes a Model asset.

        Args:
            ctx: ScriptContext instance created upon script start
            asset_data: AssetData
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        has_size = "size" in params
        has_lod = "lod" in params
        has_thumb = "thumb" in params
        if not has_size or not has_lod or not has_thumb:
            cTB.logger_ab.debug(
                "Missing required parameter (size, lod and/or thumb) to "
                "process Model")
            return False

        asset_id = asset_data.asset_id
        asset_name = asset_data.asset_name

        size = params["size"]
        lod = params["lod"]

        cTB.logger_ab.debug(f"process_model {asset_name} {size} {lod}")

        try:
            result = bpy.ops.poliigon.poliigon_model(
                asset_id=asset_id,
                size=size,
                lod=lod,
                do_use_collection=True,
                do_link_blend=True,
                do_reuse_materials=False)
        except Exception:
            cTB.logger_ab.exception("MODEL ERROR")
            return False

        if result != {"FINISHED"}:
            cTB.logger_ab.error("LOAD FAILURE")
            return False

        # Mark the object instancing our collection
        found = False
        error = False
        for obj in bpy.data.objects:
            if obj.type != "EMPTY":
                continue
            if obj.parent is not None:
                continue
            if not obj.name.startswith(asset_name):
                continue
            if obj.instance_collection is None:
                continue

            if POLIIGON_OT_sync_client._assign_asset_meta_data(
                    ctx, asset_data, obj, params):
                found = True
            else:
                error = True
                break
        return found and not error

    @staticmethod
    def _process_texture(
            ctx: ScriptContext, asset_data: AssetData, params: Dict) -> bool:
        """Processes a Texture asset (including backplates and backdrops).

        Args:
            ctx: ScriptContext instance created upon script start
            asset_data: AssetData
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        if "size" not in params or "thumb" not in params:
            cTB.logger_ab.debug(
                "Missing required parameter (size and/or thumb) to process "
                "Texture")
            return False

        asset_id = asset_data.asset_id
        asset_name = asset_data.asset_name
        size = params["size"]

        cTB.logger_ab.debug(f"process_texture {asset_name} {size}")

        try:
            result = bpy.ops.poliigon.poliigon_material(
                asset_id=asset_id, size=size)
        except Exception:
            cTB.logger_ab.exception("MATERIAL ERROR")
            return False

        if result != {"FINISHED"}:
            cTB.logger_ab.debug(
                f"Operator poliigon_material returned: {result}")
            return False

        found = False
        error = False
        for mat in bpy.data.materials:
            if not mat.name.startswith(asset_name):
                continue

            if POLIIGON_OT_sync_client._assign_asset_meta_data(
                    ctx, asset_data, mat, params):
                found = True
            else:
                error = True
                cTB.logger_ab.debug(
                    f"Failed to assign meta data to material: {mat.name}")
                break

        if not found:
            cTB.logger_ab.debug("Found no entity to mark")

        return found and not error

    @staticmethod
    def _process_asset(
            ctx: ScriptContext, asset_data: AssetData, params: Dict) -> bool:
        """Creates and saves an Asset Browser-marked asset to a new blend file.

        Args:
            ctx: ScriptContext instance created upon script start
            asset_data: AssetData
            params: Populated by host in function
                    asset_browser.py:get_asset_job_parameters()
        """

        if "path_result" not in params:
            cTB.logger_ab.debug("process_asset(): Lacking result path!")
            return False
        path_result = params["path_result"]

        POLIIGON_OT_sync_client._reset_blend()

        asset_name = asset_data.asset_name
        asset_type = asset_data.asset_type

        cTB.logger_ab.debug(f"process_asset() {asset_name}")
        for _param, value in params.items():
            cTB.logger_ab.debug(f"    {_param} {value}")

        if asset_type == AssetType.HDRI:
            result = POLIIGON_OT_sync_client._process_hdri(
                ctx, asset_data, params)
        elif asset_type == AssetType.MODEL:
            result = POLIIGON_OT_sync_client._process_model(
                ctx, asset_data, params)
        elif asset_type == AssetType.TEXTURE:
            result = POLIIGON_OT_sync_client._process_texture(
                ctx, asset_data, params)
        else:
            cTB.logger_ab.debug("process_asset(): Unknown asset type")
            return False

        if result:
            result = POLIIGON_OT_sync_client._save_blend(path_result)
        return result

    @staticmethod
    def _cmd_asset(ctx: ScriptContext, cmd: SyncAssetBrowserCmd) -> None:
        """Handle an ASSET command"""

        asset_id = cmd.data["asset_id"]
        asset_data = cTB._asset_index.get_asset(asset_id)
        if asset_data is None or not asset_data.is_local or not asset_data.is_purchased:
            bpy.ops.poliigon.get_local_asset_sync(
                await_startup_poliigon=False,
                await_startup_my_assets=False,
                get_poliigon=False,
                get_my_assets=True,
                # Andreas: With API V2 rather not search for an asset ID but
                # initiate a My Assets job instead.
                asset_id=ASSET_ID_ALL,
                abort_ongoing_jobs=False)
            asset_data = cTB._asset_index.get_asset(asset_id)

        if asset_data is not None:
            result = POLIIGON_OT_sync_client._process_asset(
                ctx, asset_data, cmd.params)
        else:
            cTB.logger_ab.error(f"process_asset(): No asset data for {asset_id}.")
            result = False

        if result:
            ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.ASSET_OK,
                                                   data=cmd.data))
        else:
            ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.ASSET_ERROR,
                                                   data=cmd.data))
        cTB.logger_ab.debug(f"cmd_asset exit {asset_data.asset_name}")

    @staticmethod
    def _cmd_hello_ok(ctx: ScriptContext, cmd: SyncAssetBrowserCmd) -> None:
        """Handle a HELLO_OK command"""

        cTB.logger_ab.debug("cmd_hello_ok")
        ctx.queue_ack.put(SyncAssetBrowserCmd(code=SyncCmd.CMD_DONE))

    @staticmethod
    def _cmd_still_there(ctx: ScriptContext, cmd: SyncAssetBrowserCmd) -> None:
        """Handle a STILL_THERE command"""

        cTB.logger_ab.debug("cmd_still_there")
        bpy.ops.poliigon.get_local_asset_sync(
            await_startup_poliigon=False,
            await_startup_my_assets=True,
            get_poliigon=False,
            get_my_assets=True,
            abort_ongoing_jobs=False)
        ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.HELLO))

    @staticmethod
    def _cmd_exit(ctx: ScriptContext, cmd: SyncAssetBrowserCmd) -> None:
        """Handle an EXIT command"""

        cTB.logger_ab.debug("cmd_exit")
        # Notify host, we are going to exit
        ctx.queue_send.put(SyncAssetBrowserCmd(code=SyncCmd.EXIT_ACK))
        # Tear down everything
        ctx.listener_running = False
        if ctx.thd_listener is not None:
            ctx.thd_listener.join()
        if ctx.thd_sender is not None:
            ctx.thd_sender.join()
        ctx.main_running = False

    def _init_settings(self) -> None:
        """Changes settings to what is needed by sync client
        (backing up the original settings).
        """

        self.settings_backup = {}
        for _key in ["download_prefer_blend",
                     "download_link_blend"]:
            self.settings_backup[_key] = cTB.settings[_key]

        cTB.settings["download_prefer_blend"] = 1
        cTB.settings["download_link_blend"] = 0

    def _restore_settings(self) -> None:
        """Restores settings from backup."""

        for _key in ["download_prefer_blend",
                     "download_link_blend"]:
            cTB.settings[_key] = self.settings_backup[_key]

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        has_catalog = self.path_catalog is not None
        has_categories = self.path_categories is not None
        if not has_catalog or not has_categories:
            return {"CANCELLED"}

        ctx = ScriptContext(
            path_cat=self.path_catalog,
            path_categories=self.path_categories)

        if not self._startup(ctx):
            return {"CANCELLED"}

        ctx.main_running = True
        while ctx.main_running:
            try:
                cmd_recv = ctx.queue_cmd.get(timeout=1.0)
                ctx.queue_cmd.task_done()
            except Empty:
                continue

            if cmd_recv is None:
                continue

            if cmd_recv.code == SyncCmd.EXIT:
                self._cmd_exit(ctx, cmd_recv)
            elif cmd_recv.code == SyncCmd.ASSET:
                self._init_settings()
                self._cmd_asset(ctx, cmd_recv)
                self._restore_settings()
            elif cmd_recv.code == SyncCmd.STILL_THERE:
                self._cmd_still_there(ctx, cmd_recv)
            elif cmd_recv.code == SyncCmd.HELLO_OK:
                self._cmd_hello_ok(ctx, cmd_recv)

        return {"FINISHED"}
