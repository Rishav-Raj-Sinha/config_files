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
from typing import List, Optional

import bpy

from .modules.poliigon_core.assets import (AssetData,
                                           AssetType)
from .modules.poliigon_core.user import UserDownloadPreferences


@dataclass
class MaterialImportParameters():
    name_material: str
    reuse_existing: bool
    do_apply: bool
    workflow: str
    lod: str
    size: str
    size_bg: Optional[str]
    variant: Optional[str]
    is_preview: bool
    is_backplate: bool
    is_model_import: bool
    name_mesh: str
    ref_objs: List[any]
    projection: str
    use_16bit: bool
    mode_disp: str
    translate_x: float
    translate_y: float
    scale: float
    global_rotation: float
    aspect_ratio: float
    displacement: float
    keep_unused_tex_nodes: bool
    map_prefs: UserDownloadPreferences

    def __init__(self,
                 asset_data: AssetData,
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
                 addon_convention: int = 0,
                 map_prefs: Optional[UserDownloadPreferences] = None
                 ):
        asset_type_data = asset_data.get_type_data()
        local_convention = asset_data.get_convention(local=True)

        is_preview = size == "WM"
        is_backplate = asset_data.is_backplate()
        is_model_import = asset_data.asset_type == AssetType.MODEL
        if name_material is None:
            name_material = asset_data.get_material_name(size, variant)

        # Validate size and get closest locally available
        if size == "PREVIEW":
            size = "WM"

        size = asset_type_data.get_size(
            size=size,
            incl_watermarked=is_preview,
            local_only=True,
            addon_convention=addon_convention,
            local_convention=local_convention
        )
        # Validate workflow or get locally available
        workflow = asset_type_data.get_workflow(
            workflow=workflow,
            get_local=True
        )
        # Restrict displacement/normal mode based on render engine
        if bpy.context.scene.render.engine == "BLENDER_EEVEE":
            mode_disp = "NORMAL"

        if local_convention < 1:
            map_prefs = None

        self.name_material = name_material
        self.reuse_existing = reuse_existing
        self.do_apply = do_apply
        self.workflow = workflow
        self.lod = lod
        self.size = size
        self.size_bg = size_bg
        self.variant = variant
        self.is_preview = is_preview
        self.is_model_import = is_model_import
        self.is_backplate = is_backplate
        self.name_mesh = name_mesh
        self.ref_objs = ref_objs
        self.projection = projection
        self.use_16bit = use_16bit
        self.mode_disp = mode_disp
        self.translate_x = translate_x
        self.translate_y = translate_y
        self.scale = scale
        self.global_rotation = global_rotation
        self.aspect_ratio = aspect_ratio
        self.displacement = displacement
        self.keep_unused_tex_nodes = keep_unused_tex_nodes
        self.map_prefs = map_prefs
