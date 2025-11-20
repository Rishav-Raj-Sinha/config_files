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

import json
import os
from typing import Dict, List, Optional

import bpy

from .modules.poliigon_core.assets import AssetData
from .modules.poliigon_core.user import UserDownloadPreferences
from .material_import_cycles import CyclesMaterial, RENDERER_CYCLES
from .material_importer_params import MaterialImportParameters
from . import reporting


SUPPORTED_RENDERERS = [RENDERER_CYCLES]


class MaterialImporter():

    def __init__(self, cTB, renderer: str = RENDERER_CYCLES):
        self.cTB = cTB
        self.renderer = None
        self.importer = None
        self.params = None
        self.asset_data = None

        self.set_renderer(renderer)

    def set_renderer(self, renderer: str) -> bool:
        """Sets the renderer to import materials for."""

        if renderer not in IMPORTERS:
            raise RuntimeError(
                f"Unsupported renderer: {renderer}\n"
                f"Supported: {IMPORTERS.keys}")
        self.renderer = renderer
        self.importer = IMPORTERS[renderer]()

    def reset_asset(self) -> None:
        self.asset_data = None

    def convert_dict_to_asset_data(
            self, asset_dict: Dict) -> Optional[AssetData]:
        """Converts a P4B asset data dictionary into an addon-core AssetData
        instance.
        """

        asset_id = asset_dict.get("id", -1)
        if asset_id >= 0:
            # Backdoor import expects negative ID
            asset_id *= -1

        asset_name = asset_dict["name"]

        if len(asset_dict["files"]) == 0:
            raise RuntimeError("Material import for asset without any files")

        # Separate asset files per library directory
        # (if distributed across multiple)
        dirs_libraries = self.cTB.get_library_paths()
        files_per_dir = {}
        asset_files = asset_dict["files"]
        for _idx_dir, _dir in enumerate(dirs_libraries):
            _dir = os.path.normpath(_dir)
            files_per_dir[_idx_dir] = [
                _file
                for _file in asset_files
                if os.path.normpath(_file).startswith(_dir)
            ]
        # Get asset's base directory in each library directory
        dir_asset_per_lib = {}
        for _idx_dir, _files in files_per_dir.items():
            try:
                dir_asset_per_lib[_idx_dir] = os.path.commonpath(_files)
            except ValueError:
                pass  # deliberately ignored
        # Build backdoor file list (per library dir)
        file_list = []
        for _dir_asset in dir_asset_per_lib.values():
            file_list_from_dir = self.cTB._asset_index_mat.file_list_from_directory(
                asset_dir=_dir_asset, ignore_dirs=[])
            file_list.extend(file_list_from_dir)

        if len(file_list) == 0:
            # Backdoor imported asset outside of libraries?
            dir_asset = os.path.commonpath(asset_files)
            file_list_from_dir = self.cTB._asset_index_mat.file_list_from_directory(
                asset_dir=dir_asset, ignore_dirs=[])
            file_list.extend(file_list_from_dir)

        result = self.cTB._asset_index_mat.load_asset_from_list(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_type=asset_dict["type"],
            size=asset_dict["sizes"][0],  # any size will do here
            lod="",  # not in use
            workflow_expected=asset_dict.get("workflows", ["METALNESS"])[0],
            file_list_json=json.dumps(file_list),
            query_string="p4b_mat_import/All Assets",
            convention=asset_dict.get("api_convention", 0)
        )
        if result is False:
            msg = f"Failed to convert to AssetData: {asset_id}"
            reporting.capture_message(
                "build_mat_error_create", msg, "error")
            self.cTB._asset_index_mat.flush(all_assets=True)
            return None

        asset_data = self.cTB._asset_index_mat.get_asset(asset_id)

        self.cTB._asset_index_mat.flush(all_assets=True)
        return asset_data

    def set_parameters(self,
                       reuse_existing: bool,
                       do_apply: bool,
                       workflow: str,
                       lod: str,
                       size: str,
                       size_bg: Optional[str] = None,
                       variant: Optional[str] = None,
                       name_material: Optional[str] = None,
                       name_mesh: Optional[str] = None,
                       ref_objs: List[any] = [],
                       projection: str = "FLAT",
                       use_16bit: bool = True,
                       mode_disp: str = "NORMAL",
                       translate_x: float = 0.0,
                       translate_y: float = 0.0,
                       scale: float = 1.0,
                       global_rotation: float = 0.0,
                       aspect_ratio: float = 1.0,
                       displacement: float = 0.0,
                       keep_unused_tex_nodes: bool = False,
                       map_prefs: Optional[UserDownloadPreferences] = None
                       ) -> None:
        """Sets the parameterts for a material import."""

        if self.asset_data is None:
            raise RuntimeError("No asset set!")

        self.params = MaterialImportParameters(
            asset_data=self.asset_data,
            reuse_existing=reuse_existing,
            do_apply=do_apply,
            workflow=workflow,
            lod=lod,
            size=size,
            size_bg=size_bg,
            variant=variant,
            name_material=name_material,
            name_mesh=name_mesh,
            ref_objs=ref_objs,
            projection=projection,
            use_16bit=use_16bit,
            mode_disp=mode_disp,
            translate_x=translate_x,
            translate_y=translate_y,
            scale=scale,
            global_rotation=global_rotation,
            aspect_ratio=aspect_ratio,
            displacement=displacement,
            keep_unused_tex_nodes=keep_unused_tex_nodes,
            addon_convention=self.cTB.addon_convention,
            map_prefs=map_prefs
        )

    def reset_parameters(self) -> None:
        """Resets all parameters."""

        self.params = None

    def get_existing_material(self) -> Optional[bpy.types.Material]:
        """Returns an already existing material of identical name.

        This is what legacy import in P4B did for Model assets.
        Texture assets were handeled differently via
        find_identical_material().
        """

        if not self.params.reuse_existing:
            return None

        name_mat = self.params.name_material
        if name_mat in bpy.data.materials.keys():
            return bpy.data.materials[name_mat]

        return None

    def import_material(self,
                        *,
                        asset_data: AssetData,
                        do_apply: bool,
                        workflow: str,
                        size: str,
                        size_bg: Optional[str] = None,
                        lod: Optional[str] = None,
                        variant: Optional[str] = None,
                        name_material: Optional[str] = None,
                        name_mesh: Optional[str] = None,
                        ref_objs: Optional[List[any]] = None,
                        projection: str = "FLAT",
                        use_16bit: bool = True,
                        mode_disp: str = "NORMAL",
                        translate_x: float = 0.0,
                        translate_y: float = 0.0,
                        scale: float = 1.0,
                        global_rotation: float = 0.0,
                        aspect_ratio: float = 1.0,
                        displacement: float = 0.0,
                        keep_unused_tex_nodes: bool = False,
                        reuse_existing: bool = True,
                        map_prefs: Optional[UserDownloadPreferences] = None
                        ) -> Optional[bpy.types.Material]:
        """Imports a single material for an asset regardless of type."""

        if asset_data is None:
            return None
        self.asset_data = asset_data

        self.set_parameters(
            reuse_existing=reuse_existing,
            do_apply=do_apply,
            workflow=workflow,
            lod=lod,
            size=size,
            size_bg=size_bg,
            variant=variant,
            name_material=name_material,
            name_mesh=name_mesh,
            ref_objs=ref_objs,
            projection=projection,
            use_16bit=use_16bit,
            mode_disp=mode_disp,
            translate_x=translate_x,
            translate_y=translate_y,
            scale=scale,
            global_rotation=global_rotation,
            aspect_ratio=aspect_ratio,
            displacement=displacement,
            keep_unused_tex_nodes=keep_unused_tex_nodes,
            map_prefs=map_prefs
        )

        # Case for Model import, Texture assets handle material re-use still
        # in operator. TODO(Andreas)
        mat = self.get_existing_material()
        if mat is not None:
            self.reset_parameters()
            self.reset_asset()
            return mat

        mat = self.importer.import_material(self.asset_data, self.params)

        self.reset_parameters()
        self.reset_asset()
        return mat


IMPORTERS = {
    RENDERER_CYCLES: CyclesMaterial
}
