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

import mathutils
import os
from typing import Dict, List, Optional, Tuple

import bpy

from .modules.poliigon_core.assets import (ASSET_TYPE_TO_CATEGORY_NAME,
                                           AssetData,
                                           AssetType,
                                           MapType,
                                           TextureMap)
from .material_import_cycles_port_names import get_socket_name
from .material_importer_params import MaterialImportParameters
from .material_import_utils import (
    create_link,
    create_link_sock_out,
    get_node_by_type,
    set_value)
from . import material_import_utils_nodes as node_utils
from . import reporting
from .utils import copy_simple_property_group


RENDERER_CYCLES = "Cycles"

# TODO(Andreas): Keep name, but have different label? "Simple UV Mapping"
#                Just to look a bit cleaner.
NAME_GROUP_SIMPLE_UV = ".simple_uv_mapping"

# {map_type: (color space, alpha, interpolation)}
# None means default, do not change
MAP_TYPE_TO_CYCLES_IMG_PARAMS = {
    MapType.DEFAULT: ("sRGB", "STRAIGHT", "Linear"),
    MapType.UNKNOWN: ("sRGB", "STRAIGHT", "Linear"),
    MapType.ALPHA: ("Raw", "STRAIGHT", "Linear"),
    MapType.ALPHAMASKED: ("sRGB", "CHANNEL_PACKED", "Linear"),
    MapType.AO: ("Raw", "STRAIGHT", "Linear"),
    MapType.BUMP: ("Raw", "STRAIGHT", "Linear"),
    MapType.BUMP16: ("Raw", "STRAIGHT", "Linear"),
    MapType.COL: ("sRGB", "STRAIGHT", "Linear"),
    MapType.ALBEDO: ("sRGB", "STRAIGHT", "Linear"),
    MapType.DIFF: ("sRGB", "STRAIGHT", "Linear"),
    MapType.DISP: ("Raw", "STRAIGHT", "Cubic"),
    MapType.DISP16: ("Raw", "STRAIGHT", "Cubic"),
    MapType.EMISSIVE: ("sRGB", "STRAIGHT", "Linear"),
    MapType.ENV: ("sRGB", "STRAIGHT", "Linear"),
    MapType.JPG: ("sRGB", "STRAIGHT", "Linear"),
    MapType.FUZZ: ("sRGB", "STRAIGHT", "Linear"),
    MapType.GLOSS: ("Raw", "STRAIGHT", "Linear"),
    MapType.IDMAP: ("Raw", "STRAIGHT", "Linear"),
    MapType.DIRECTION: ("sRGB", "STRAIGHT", "Linear"),
    MapType.LIGHT: ("Raw", "STRAIGHT", "Linear"),
    MapType.HDR: ("Raw", "STRAIGHT", "Linear"),
    MapType.MASK: ("Raw", "STRAIGHT", "Linear"),
    MapType.METALNESS: ("Raw", "STRAIGHT", "Linear"),
    MapType.NRM: ("Raw", "STRAIGHT", "Linear"),
    MapType.NRM16: ("Raw", "STRAIGHT", "Linear"),
    MapType.OVERLAY: ("Raw", "STRAIGHT", "Linear"),
    MapType.OVERLAY16: ("sRGB", "STRAIGHT", "Linear"),
    MapType.REFL: ("sRGB", "STRAIGHT", "Linear"),
    MapType.ROUGHNESS: ("Raw", "STRAIGHT", "Linear"),
    MapType.SSS: ("sRGB", "STRAIGHT", "Linear"),
    MapType.TRANSLUCENCY: ("sRGB", "STRAIGHT", "Linear"),
    MapType.TRANSMISSION: ("Raw", "STRAIGHT", "Linear"),
    MapType.OPACITY: ("Raw", "STRAIGHT", "Linear"),
    MapType.NA_ORM: ("Raw", "STRAIGHT", "Linear"),
}

X_OFFSET_COLUMN_WIDE = 350.0
X_OFFSET_COLUMN_NARROW = 250.0
Y_OFFSET_ROW_TEX = 350.0
Y_GAP = 50.0
W_NODE_WIDE = X_OFFSET_COLUMN_WIDE - 100.0

# This list defines the sort order for texture nodes in Texture node column-
# Purpose is to minimize link crossings and provide a more digestable node
# layout.
TEX_COLUMN_ORDER = [
    MapType.COL,
    MapType.DIFF,
    MapType.ALPHAMASKED,
    MapType.NA_ORM,
    MapType.AO,
    MapType.FUZZ,
    MapType.TRANSLUCENCY,
    MapType.SSS,
    MapType.METALNESS,
    MapType.REFL,
    MapType.ROUGHNESS,
    MapType.GLOSS,
    MapType.EMISSIVE,
    MapType.ALPHA,
    MapType.MASK,
    MapType.OPACITY,
    MapType.NRM16,
    MapType.NRM,
    MapType.DISP16,
    MapType.DISP,
    MapType.BUMP16,
    MapType.BUMP,
    MapType.TRANSMISSION,
    # Currently unused map types
    MapType.OVERLAY,
    MapType.IDMAP,
    # Non-material asset map types
    MapType.ENV,
    MapType.HDR,
    MapType.JPG,
    MapType.LIGHT,
]


VARIANT_TAGS = [f"VAR{idx}" for idx in range(1, 10)]


class CyclesNodesSimpleUVMapping():
    scale_mul: bpy.types.Node = None
    ar_factor: bpy.types.Node = None
    ar_mul: bpy.types.Node = None
    translate_offset: bpy.types.Node = None
    translate_add: bpy.types.Node = None
    rotate_rad: bpy.types.Node = None
    rotate: bpy.types.Node = None


class CyclesNodesTopLevel():
    bsdf_principled: bpy.types.Node = None

    color_mix_ao: bpy.types.Node = None

    displacement: bpy.types.Node = None

    fabric_fresnel: bpy.types.Node = None
    fabric_mix: bpy.types.Node = None

    mat_out: bpy.types.Node = None

    mapping: bpy.types.Node = None
    mosaic: bpy.types.Node = None

    normal: bpy.types.Node = None

    simple_uv_group: bpy.types.Node = None
    simple_uv: CyclesNodesSimpleUVMapping = CyclesNodesSimpleUVMapping()

    specular_invert_gloss: bpy.types.Node = None

    sss_multiply: bpy.types.Node = None

    tex: Dict[MapType, bpy.types.Node] = {}
    tex_alt: Dict[MapType, List[bpy.types.Node]] = {}

    tex_coords: bpy.types.Node = None

    translucency_add_shader: bpy.types.Node = None
    translucency_bsdf_translucent: bpy.types.Node = None
    translucency_bsdf_transparent: bpy.types.Node = None
    translucency_color_invert: bpy.types.Node = None
    translucency_mix_color: bpy.types.Node = None
    translucency_mix_shader: bpy.types.Node = None
    translucency_mix_translucency: bpy.types.Node = None
    translucency_value: bpy.types.Node = None

    transmission_vol_abs: bpy.types.Node = None

    def __init__(self):
        self.simple_uv = CyclesNodesSimpleUVMapping()
        self.tex = {}
        self.tex_alt = {}

    def get_ao_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Ambient Occlusion channel."""

        node_tex_ao = self.tex.get(MapType.AO, None)
        return node_tex_ao

    def get_color_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Color/Diffuse channel."""

        node_tex_color = self.tex.get(MapType.ALPHAMASKED, None)
        if node_tex_color is None:
            node_tex_color = self.tex.get(MapType.COL, None)
        if node_tex_color is None:
            node_tex_color = self.tex.get(MapType.DIFF, None)
        return node_tex_color

    def get_color_effective_output(self,
                                   ignore_translucency: bool = False
                                   ) -> Optional[bpy.types.NodeSocket]:
        """Returns the (potentially mixed) Color/Diffuse output socket."""

        node_color = None
        if not ignore_translucency:
            node_color = self.translucency_mix_color
            name_color_out = "Result"
        if node_color is None:
            node_color = self.color_mix_ao
            name_color_out = "Result"
        if node_color is None:
            node_color = self.get_color_tex_node()
            name_color_out = "Color"
        if node_color is None:
            return None

        name_color_out = get_socket_name(node_color, name_color_out)
        return node_color.outputs[name_color_out]

    def get_displacement_tex_node(
            self, use_16bit: bool) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Displacement channel."""

        node_tex_displacement = None
        if use_16bit:
            node_tex_displacement = self.tex.get(MapType.DISP16, None)
        if node_tex_displacement is None:
            node_tex_displacement = self.tex.get(MapType.DISP, None)
        # TODO(Andreas): Check, if anything else needs to be done to get
        #                bump maps working
        if node_tex_displacement is None and use_16bit:
            node_tex_displacement = self.tex.get(MapType.BUMP16, None)
        if node_tex_displacement is None:
            node_tex_displacement = self.tex.get(MapType.BUMP, None)

        return node_tex_displacement

    def get_emission_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Emission channel."""

        node_tex_emission = self.tex.get(MapType.EMISSIVE, None)
        return node_tex_emission

    def get_fuzz_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Fabric/Fuzz channel."""

        node_tex_fuzz = self.tex.get(MapType.FUZZ, None)
        return node_tex_fuzz

    def get_gloss_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Gloss channel."""

        node_tex_gloss = self.tex.get(MapType.GLOSS, None)
        return node_tex_gloss

    def get_metalness_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Metallness/Metallic channel."""

        node_tex_metalness = self.tex.get(MapType.METALNESS, None)
        return node_tex_metalness

    def get_normal_tex_node(self, use_16bit: bool) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Normal channel."""

        node_tex_normal = None
        if use_16bit:
            node_tex_normal = self.tex.get(MapType.NRM16, None)
        if node_tex_normal is None:
            node_tex_normal = self.tex.get(MapType.NRM, None)
        return node_tex_normal

    def get_opacity_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Alpha/Opacity channel."""

        node_tex_opacity = self.tex.get(MapType.OPACITY, None)
        if node_tex_opacity is None:
            node_tex_opacity = self.tex.get(MapType.ALPHAMASKED, None)
        if node_tex_opacity is None:
            node_tex_opacity = self.tex.get(MapType.ALPHA, None)
        if node_tex_opacity is None:
            node_tex_opacity = self.tex.get(MapType.MASK, None)
        return node_tex_opacity

    def get_opacity_effective_output(self) -> Optional[bpy.types.NodeSocket]:
        """Returns the effective Alpha/Opacity output socket."""

        node_tex_opacity = self.get_opacity_tex_node()
        if node_tex_opacity is None:
            return None

        name_alpha_out = "Color"
        if node_tex_opacity is self.tex.get(MapType.ALPHAMASKED, None):
            name_alpha_out = "Alpha"

        name_alpha_out = get_socket_name(node_tex_opacity, name_alpha_out)
        return node_tex_opacity.outputs[name_alpha_out]

    def get_reflection_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Reflection channel."""

        node_tex_reflection = self.tex.get(MapType.REFL, None)
        return node_tex_reflection

    def get_roughness_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Roughness channel."""

        node_tex_roughness = self.tex.get(MapType.ROUGHNESS, None)
        return node_tex_roughness

    def get_roughness_effective_node(
            self) -> Tuple[Optional[bpy.types.Node], bool]:
        """Returns effective node for Roughness channel (could be gloss)."""

        node_tex_roughness = self.get_roughness_tex_node()
        is_specular = False
        if node_tex_roughness is None:
            node_tex_roughness = self.get_gloss_tex_node()
            is_specular = True
        return node_tex_roughness, is_specular

    def get_sss_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for SSS channel."""

        node_tex_sss = self.tex.get(MapType.SSS, None)
        return node_tex_sss

    def get_transmission_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Transmission channel."""

        node_tex_transmission = self.tex.get(MapType.TRANSMISSION, None)
        return node_tex_transmission

    def get_translucency_tex_node(self) -> Optional[bpy.types.Node]:
        """Returns the 'Image Texture' node for Translucency channel."""

        node_tex_translucency = self.tex.get(MapType.TRANSLUCENCY, None)
        return node_tex_translucency


class CyclesMaterial():

    def __init__(self):
        self.init(asset_data=None, params=None)

    def init(self,
             asset_data: AssetData,
             params: MaterialImportParameters
             ) -> None:
        self.asset_data = asset_data
        self.params = params

        self.tex_maps = None
        self.nodes = CyclesNodesTopLevel()
        self.mat = None

        self.error_missing_colorspace = []

    def _try_to_assign_non_color_space(self, image: bpy.types.Image) -> None:
        """Tries to assign a non-color/raw color space to an image."""

        # Note: Changed order compared to old P4B, since Mateusz's
        #       setups all use Raw
        NON_COLOR_SPACES = ["Raw",
                            "Linear",
                            "Blender Linear",
                            "Non-Color",
                            "Non-Colour Data",
                            "Generic Data",
                            # From docs: https://docs.blender.org/api/current/bpy.types.ColorManagedInputColorspaceSettings.html#bpy.types.ColorManagedInputColorspaceSettings
                            # Nevertheless I doubt, the next two would ever be
                            # regular values
                            "NONE",
                            None
                            ]
        found_color_space = False
        for color_space_name in NON_COLOR_SPACES:
            try:
                image.colorspace_settings.name = color_space_name
            except TypeError:
                continue
            found_color_space = True
            break

        if found_color_space:
            return  # success

        self.error_missing_colorspace.append(image.name)
        colorspace_settings = type(
            image).bl_rna.properties["colorspace_settings"]
        colorspace_properties = colorspace_settings.fixed_type.properties
        spaces_avail = colorspace_properties["name"].enum_items.keys()
        msg = (
            f"No non-color colorspace found - "
            f"image: {image.name}, "
            f"spaces: {spaces_avail}"
        )
        reporting.capture_message(
            "build_mat_error_colorspace", msg, "error")

    def _try_to_assign_color_space(
            self, image: bpy.types.Image, colorspace_desired: str) -> None:
        """Tries to assign a color space to an image."""

        colorspace_settings = type(
            image).bl_rna.properties["colorspace_settings"]
        colorspace_properties = colorspace_settings.fixed_type.properties
        spaces_avail = colorspace_properties["name"].enum_items.keys()

        colorspace_to_use = None
        for _colorspace in spaces_avail:
            if _colorspace == colorspace_desired:
                colorspace_to_use = colorspace_desired
                break

        try:
            if colorspace_to_use is None:
                raise TypeError
            image.colorspace_settings.name = colorspace_to_use
        except TypeError:
            self.error_missing_colorspace.append(image.name)
            msg = (
                f"No {colorspace_desired} colorspace found - "
                f"image: {image.name}, "
                f"spaces: {spaces_avail}"
            )
            reporting.capture_message(
                "build_mat_error_colorspace", msg, "error")

    def configure_tex_node_image(
            self, node: bpy.types.Node, tex_map: TextureMap) -> None:
        """Configures the image referenced by a texture node."""

        path_tex = tex_map.get_path()
        filename_tex = os.path.basename(path_tex)
        name_tex = os.path.splitext(filename_tex)[0]
        if tex_map.size not in name_tex:
            # Convention 1 tex maps have no size in filename,
            # but we need unique image names for consecutive imports with
            # different sizes to work correctly
            name_tex += f"_{tex_map.size}"

        file_format = tex_map.file_format[1:].lower()
        name_tex += f"_{file_format}"

        if name_tex in bpy.data.images.keys():
            image = bpy.data.images[name_tex]
        else:
            path_tex_norm = os.path.normpath(path_tex)
            image = bpy.data.images.load(path_tex_norm)
            image.name = name_tex

        map_type_effective = tex_map.map_type.get_effective()
        colorspace, alpha, interpolation = MAP_TYPE_TO_CYCLES_IMG_PARAMS[
            map_type_effective]
        if colorspace == "Raw":
            self._try_to_assign_non_color_space(image)
        else:
            self._try_to_assign_color_space(image, colorspace)
        image.alpha_mode = alpha
        node.image = image
        node.interpolation = interpolation

    def simple_uv_group_set_defaults(self, node_group: bpy.types.Node) -> None:
        """Sets default values to the paramter node sockets of Poliigon's
        Simple UV Mapping node group.
        """

        set_value(
            node=node_group,
            sock_name="Scale",
            sock_bl_idname_expected="NodeSocketFloat",
            value=self.params.scale)
        if bpy.app.version >= (4, 0):
            # TODO(Andreas): Docs say NodeSocketFloatAngle exists...
            #                We'd like to have a degree slider...
            socket_type_angle = "NodeSocketFloat"
        else:
            socket_type_angle = "NodeSocketFloatAngle"
        set_value(
            node=node_group,
            sock_name="Rotation",
            sock_bl_idname_expected=socket_type_angle,
            value=self.params.global_rotation)
        set_value(
            node=node_group,
            sock_name="Translate X",
            sock_bl_idname_expected="NodeSocketFloat",
            value=self.params.translate_x)
        set_value(
            node=node_group,
            sock_name="Translate Y",
            sock_bl_idname_expected="NodeSocketFloat",
            value=self.params.translate_y)
        set_value(
            node=node_group,
            sock_name="Aspect Ratio",
            sock_bl_idname_expected="NodeSocketFloat",
            value=self.params.aspect_ratio)

    def prepare_simple_uv_group_node(
            self, parent_frame: bpy.types.Node) -> bpy.types.Node:
        node_group = node_utils.create_group_node(
            group=self.mat,
            parent=parent_frame,
            name=NAME_GROUP_SIMPLE_UV,
            width=W_NODE_WIDE
        )
        node_utils.create_node_socket(node_group,
                                      socket_type="NodeSocketVector",
                                      in_out="INPUT",
                                      name="UV")
        node_utils.create_node_socket(node_group,
                                      socket_type="NodeSocketVector",
                                      in_out="OUTPUT",
                                      name="UV")

        node_utils.create_node_socket(node_group,
                                      socket_type="NodeSocketFloat",
                                      in_out="INPUT",
                                      name="Scale")
        if bpy.app.version >= (4, 0):
            # TODO(Andreas): Docs say NodeSocketFloatAngle exists...
            #                We'd like to have a degree slider...
            socket_type_angle = "NodeSocketFloat"
        else:
            socket_type_angle = "NodeSocketFloatAngle"
        node_utils.create_node_socket(node_group,
                                      socket_type=socket_type_angle,
                                      in_out="INPUT",
                                      name="Rotation")
        node_utils.create_node_socket(node_group,
                                      socket_type="NodeSocketFloat",
                                      in_out="INPUT",
                                      name="Translate X")
        node_utils.create_node_socket(node_group,
                                      socket_type="NodeSocketFloat",
                                      in_out="INPUT",
                                      name="Translate Y")
        node_utils.create_node_socket(node_group,
                                      socket_type="NodeSocketFloat",
                                      in_out="INPUT",
                                      name="Aspect Ratio")
        self.simple_uv_group_set_defaults(node_group)

        return node_group

    def reuse_simple_uv_group(
            self, parent_frame: bpy.types.Node) -> bpy.types.Node:
        """Reuses an already created node tree to create a new
        Simple UV Mapping node group.
        """

        if NAME_GROUP_SIMPLE_UV not in bpy.data.node_groups.keys():
            return None

        node_group = node_utils.create_group_node(
            group=self.mat,
            parent=parent_frame,
            node_tree=bpy.data.node_groups[NAME_GROUP_SIMPLE_UV],
            name=NAME_GROUP_SIMPLE_UV,
            width=W_NODE_WIDE
        )
        self.simple_uv_group_set_defaults(node_group)
        self.nodes.simple_uv_group = node_group
        return node_group

    def create_simple_uv_group(
        self,
        parent_frame: Optional[bpy.types.Node] = None
    ) -> bpy.types.Node:
        """Creates Poliigon's Simple UV Mapping node group."""

        node_group = self.reuse_simple_uv_group(parent_frame)
        if node_group is not None:
            return node_group

        node_group = self.prepare_simple_uv_group_node(parent_frame)
        node_group_inputs_internal = get_node_by_type(
            node_group, "NodeGroupInput")
        node_group_outputs_internal = get_node_by_type(
            node_group, "NodeGroupOutput")

        self.nodes.simple_uv_group = node_group

        loc_inputs = node_group_inputs_internal.location
        pos_x = loc_inputs[0] + X_OFFSET_COLUMN_NARROW
        pos_y_row_0 = loc_inputs[1]
        pos_y_row_1 = pos_y_row_0 - Y_OFFSET_ROW_TEX

        scale = [self.params.scale] * 3
        node_scale = node_utils.create_vector_math_node(
            group=node_group,
            parent=None,
            operation="MULTIPLY",
            value2=scale,
            name="Scale (Multiply)",
            location=[pos_x, pos_y_row_0]
        )
        self.nodes.simple_uv.scale_mul = node_scale

        node_aspect = node_utils.create_combine_xyz_node(
            group=node_group,
            parent=None,
            value_x=1.0,
            value_y=self.params.aspect_ratio,
            value_z=1.0,
            name="Aspect Ratio Factor",
            location=[pos_x, pos_y_row_1]
        )
        self.nodes.simple_uv.ar_factor = node_aspect

        pos_x += X_OFFSET_COLUMN_NARROW

        node_aspect_mul = node_utils.create_vector_math_node(
            group=node_group,
            parent=None,
            operation="MULTIPLY",
            name="Aspect Ration (Multiply)",
            location=[pos_x, pos_y_row_0]
        )
        self.nodes.simple_uv.ar_mul = node_aspect_mul

        node_translate = node_utils.create_combine_xyz_node(
            group=node_group,
            parent=None,
            value_x=self.params.translate_x,
            value_y=self.params.translate_y,
            value_z=0.0,
            name="Translation Offset",
            location=[pos_x, pos_y_row_1]
        )
        self.nodes.simple_uv.translate_offset = node_translate

        pos_x += X_OFFSET_COLUMN_NARROW

        node_translate_add = node_utils.create_vector_math_node(
            group=node_group,
            parent=None,
            operation="ADD",
            name="Translation (Add)",
            location=[pos_x, pos_y_row_0]
        )
        self.nodes.simple_uv.translate_add = node_translate_add

        if bpy.app.version >= (4, 0):
            node_rotation_rad = node_utils.create_math_node(
                group=node_group,
                parent=None,
                operation="RADIANS",
                use_clamp=False,
                value1=self.params.global_rotation,
                location=[pos_x, pos_y_row_1]
            )
            self.nodes.simple_uv.rotate_rad = node_rotation_rad

        pos_x += X_OFFSET_COLUMN_NARROW

        node_rotate = node_utils.create_vector_rotate_node(
            group=node_group,
            parent=None,
            location=[pos_x, pos_y_row_0]
        )
        self.nodes.simple_uv.rotate = node_rotate

        pos_x += X_OFFSET_COLUMN_NARROW
        node_group_outputs_internal.location = [pos_x, pos_y_row_0]

        create_link(
            node_tree=node_group.node_tree,
            node_out=node_group_inputs_internal,
            sock_out_name="UV",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_scale,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketVector",
            allow_index=True)  # Vector Math node needs indexes
        create_link(
            node_tree=node_group.node_tree,
            node_out=node_group_inputs_internal,
            sock_out_name="Scale",
            sock_out_bl_idname_expected="NodeSocketFloat",
            node_in=node_scale,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketVector",
            allow_index=True)  # Vector Math node needs indexes)
        create_link(
            node_tree=node_group.node_tree,
            node_out=node_group_inputs_internal,
            sock_out_name="Aspect Ratio",
            sock_out_bl_idname_expected="NodeSocketFloat",
            node_in=node_aspect,
            sock_in_name="Y",
            sock_in_bl_idname_expected="NodeSocketFloat")
        create_link(
            node_tree=node_group.node_tree,
            node_out=node_group_inputs_internal,
            sock_out_name="Translate X",
            sock_out_bl_idname_expected="NodeSocketFloat",
            node_in=node_translate,
            sock_in_name="X",
            sock_in_bl_idname_expected="NodeSocketFloat")
        create_link(
            node_tree=node_group.node_tree,
            node_out=node_group_inputs_internal,
            sock_out_name="Translate Y",
            sock_out_bl_idname_expected="NodeSocketFloat",
            node_in=node_translate,
            sock_in_name="Y",
            sock_in_bl_idname_expected="NodeSocketFloat")
        if bpy.app.version >= (4, 0):
            create_link(
                node_tree=node_group.node_tree,
                node_out=node_group_inputs_internal,
                sock_out_name="Rotation",
                sock_out_bl_idname_expected="NodeSocketFloat",
                node_in=node_rotation_rad,
                sock_in_name="A",
                sock_in_bl_idname_expected="NodeSocketFloat",
                allow_index=True)  # Math node needs indexes

        create_link(
            node_tree=node_group.node_tree,
            node_out=node_scale,
            sock_out_name="Vector",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_aspect_mul,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketVector",
            allow_index=True)  # Vector Math node needs indexes
        create_link(
            node_tree=node_group.node_tree,
            node_out=node_aspect,
            sock_out_name="Vector",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_aspect_mul,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketVector",
            allow_index=True)  # Vector Math node needs indexes

        create_link(
            node_tree=node_group.node_tree,
            node_out=node_aspect_mul,
            sock_out_name="Vector",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_translate_add,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketVector",
            allow_index=True)  # Vector Math node needs indexes
        create_link(
            node_tree=node_group.node_tree,
            node_out=node_translate,
            sock_out_name="Vector",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_translate_add,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketVector",
            allow_index=True)  # Vector Math node needs indexes

        create_link(
            node_tree=node_group.node_tree,
            node_out=node_translate_add,
            sock_out_name="Vector",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_rotate,
            sock_in_name="Vector",
            sock_in_bl_idname_expected="NodeSocketVector")
        if bpy.app.version >= (4, 0):
            create_link(
                node_tree=node_group.node_tree,
                node_out=node_rotation_rad,
                sock_out_name="Value",
                sock_out_bl_idname_expected="NodeSocketFloat",
                node_in=node_rotate,
                sock_in_name="Angle",
                sock_in_bl_idname_expected="NodeSocketFloatAngle")
        else:
            create_link(
                node_tree=node_group.node_tree,
                node_out=node_group_inputs_internal,
                sock_out_name="Rotation",
                sock_out_bl_idname_expected="NodeSocketFloatAngle",  # socke_type_angle
                node_in=node_rotate,
                sock_in_name="Angle",
                sock_in_bl_idname_expected="NodeSocketFloatAngle",
                allow_index=True)  # Math node needs indexes

        create_link(
            node_tree=node_group.node_tree,
            node_out=node_rotate,
            sock_out_name="Vector",
            sock_out_bl_idname_expected="NodeSocketVector",
            node_in=node_group_outputs_internal,
            sock_in_name="UV",
            sock_in_bl_idname_expected="NodeSocketVector")
        return node_group

    def create_tex_node(
        self,
        tex_map: TextureMap,
        group: bpy.types.Node,
        parent: Optional[bpy.types.Node] = None,
        *,
        projection: Optional[str] = "FLAT",
        extension: Optional[str] = "REPEAT",
        location: Optional[mathutils.Vector] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        hide: bool = False
    ) -> bpy.types.Node:
        """Creates an 'Image Texture' node."""

        map_type_effective = tex_map.map_type.get_effective()
        if map_type_effective in self.nodes.tex:
            # If we already have a tex node for this map type,
            # fold all following ones (alternative tex nodes).
            hide = True

        filename_parts = tex_map.filename.split("_")
        variant = [var for var in VARIANT_TAGS if var in filename_parts]
        # For name_node we deliberately use the original map type names,
        # NOT the effective ones!
        if len(variant) > 0:
            name_node = f"{tex_map.map_type.name} ({variant[0]})"
        else:
            name_node = tex_map.map_type.name

        node_tex = node_utils.create_node(
            group=group,
            bl_idname="ShaderNodeTexImage",
            parent=parent,
            name=name_node,
            location=location,
            width=width,
            height=height,
            hide=hide
        )

        if map_type_effective not in self.nodes.tex:
            self.nodes.tex[map_type_effective] = node_tex
        elif map_type_effective in self.nodes.tex_alt:
            self.nodes.tex_alt[map_type_effective].append(node_tex)
        else:
            self.nodes.tex_alt[map_type_effective] = [node_tex]

        self.configure_tex_node_image(node_tex, tex_map)

        if projection is not None:
            if projection in ["UV", "MOSAIC"]:
                node_tex.projection = "FLAT"
            else:
                node_tex.projection = projection
        if extension is not None:
            node_tex.extension = extension
        return node_tex

    def create_texture_nodes(self) -> None:
        """Creates 'Image Texture' nodes for all TextureMaps provided to this
        import.
        """

        params = self.params
        asset_type = self.asset_data.asset_type
        asset_type_data = self.asset_data.get_type_data()

        self.tex_maps = asset_type_data.get_maps(
            workflow=params.workflow,
            size=params.size,
            lod=params.lod,
            prefer_16_bit=params.use_16bit,
            variant=params.variant,
            effective=True,
            map_preferences=params.map_prefs
        )
        if len(self.tex_maps) == 0:
            raise RuntimeError("No textures")

        if asset_type == AssetType.MODEL:
            for name in [params.name_mesh, params.name_material]:
                (has_maps,
                 base_map_name,
                 tex_maps_mesh) = asset_type_data.filter_mesh_maps(
                    asset_maps=self.tex_maps,
                    mesh_name=name,
                    original_material_name=params.name_material
                )
                if not has_maps:
                    continue
                self.tex_maps = tex_maps_mesh

        frame = node_utils.create_frame(
            group=self.mat,
            parent=None,
            name="Textures"
        )

        for _tex_map in self.tex_maps:
            self.create_tex_node(
                tex_map=_tex_map,
                group=self.mat,
                parent=frame,
                projection=params.projection
            )

    def connect_color(self) -> None:
        """Sets up and connects the Color channel."""

        node_tex_ao = self.nodes.get_ao_tex_node()
        node_tex_color = self.nodes.get_color_tex_node()
        if node_tex_color is None and node_tex_ao is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        if node_tex_ao is None:
            create_link(
                node_tree=self.mat.node_tree,
                node_in=node_bsdf,
                sock_in_name="Base Color",
                sock_in_bl_idname_expected="NodeSocketColor",
                node_out=node_tex_color,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor")
            return

        node_mix = node_utils.create_mix_node(
            group=self.mat,
            parent=None,
            data_type="RGBA",
            use_clamp=True,
            clamp_result=False,
            blend_type="MULTIPLY",
            blend_factor=0.0,
            name="COLOR * AO"
        )
        self.nodes.color_mix_ao = node_mix
        # NOTE: Below we need to allow indexed port addressing
        #       (-> allow_index=True),
        #       as the Mix node in Blender 3.4 has no way of addressing the
        #       ports by name (different type ports have identical names). :(
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_color,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_mix,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketColor",
            allow_index=True)
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_ao,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_mix,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketColor",
            allow_index=True)
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_mix,
            sock_out_name="Result",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_bsdf,
            sock_in_name="Base Color",
            sock_in_bl_idname_expected="NodeSocketColor",
            allow_index=True)

    def connect_displacement(self) -> None:
        """Sets up and connects the Displacement channel."""

        node_tex_displacement = self.nodes.get_displacement_tex_node(
            self.params.use_16bit)
        if node_tex_displacement is None:
            return

        if self.params.mode_disp == "BUMP":
            displacement_method = "BUMP"
        elif self.params.mode_disp == "DISP":
            displacement_method = "BOTH"
        elif self.params.mode_disp == "MICRO":
            displacement_method = "DISPLACEMENT"
        else:  # self.params.mode_disp == "NORMAL"
            displacement_method = "BUMP"
        if bpy.app.version >= (4, 1):
            self.mat.displacement_method = displacement_method
        else:
            self.mat.cycles.displacement_method = displacement_method

        node_out = self.nodes.mat_out
        node_displacement = node_utils.create_displacement_node(
            group=self.mat,
            parent=None,
            midlevel=0.5,
            scale=self.params.displacement
        )
        self.nodes.displacement = node_displacement

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_displacement,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_displacement,
            sock_in_name="Height",
            sock_in_bl_idname_expected="NodeSocketFloat")
        if self.params.mode_disp != "NORMAL":
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_displacement,
                sock_out_name="Displacement",
                sock_out_bl_idname_expected="NodeSocketVector",
                node_in=node_out,
                sock_in_name="Displacement",
                sock_in_bl_idname_expected="NodeSocketVector")

    def connect_emission(self) -> None:
        """Sets up and connects the Emission channel."""

        node_tex_emission = self.nodes.get_emission_tex_node()
        if node_tex_emission is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        if bpy.app.version >= (3, 0):
            # There seems no option to set emission strength in Blender < 3.0
            set_value(
                node=node_bsdf,
                sock_name="Emission Strength",
                sock_bl_idname_expected="NodeSocketFloat",
                value=0.0)

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_emission,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_bsdf,
            sock_in_name="Emission Color",
            sock_in_bl_idname_expected="NodeSocketColor")

    def connect_fabric(self) -> None:
        """Sets up and connects the Fabric/Fuzz channel."""

        node_tex_fuzz = self.nodes.get_fuzz_tex_node()
        if node_tex_fuzz is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        if bpy.app.version >= (4, 0):
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_tex_fuzz,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_bsdf,
                sock_in_name="Sheen Tint",
                sock_in_bl_idname_expected="NodeSocketColor")
            set_value(
                node=node_bsdf,
                sock_name="Sheen Weight",
                sock_bl_idname_expected="NodeSocketFloatFactor",
                value=1.0)
            set_value(
                node=node_bsdf,
                sock_name="Sheen Roughness",
                sock_bl_idname_expected="NodeSocketFloatFactor",
                value=0.3)
        else:
            output_color = self.nodes.get_color_effective_output()
            node_fresnel = node_utils.create_fresnel_node(
                group=self.mat,
                parent=None,
                ior=1.150
            )
            self.nodes.fabric_fresnel = node_fresnel

            node_mix = node_utils.create_mix_node(
                group=self.mat,
                parent=None,
                data_type="RGBA",
                use_clamp=True,
                clamp_result=False,
                blend_type="SCREEN",
                blend_factor=0.0
            )
            self.nodes.fabric_mix = node_mix

            if bpy.app.version >= (3, 2):
                bl_idname_expected_fresnel_factor = "NodeSocketFloat"
            else:
                bl_idname_expected_fresnel_factor = "NodeSocketFloatFactor"

            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_fresnel,
                sock_out_name="Fac",
                sock_out_bl_idname_expected=bl_idname_expected_fresnel_factor,
                node_in=node_mix,
                sock_in_name="Factor",
                sock_in_bl_idname_expected="NodeSocketFloatFactor")
            create_link_sock_out(
                node_tree=self.mat.node_tree,
                sock_out=output_color,
                node_in=node_mix,
                sock_in_name="A",
                sock_in_bl_idname_expected="NodeSocketColor")
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_tex_fuzz,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_mix,
                sock_in_name="B",
                sock_in_bl_idname_expected="NodeSocketColor")
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_mix,
                sock_out_name="Result",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_bsdf,
                sock_in_name="Base Color",
                sock_in_bl_idname_expected="NodeSocketColor")

    def connect_metalness(self) -> None:
        """Sets up and connects the Metalness channel.

        This works with Metalness map as well as with Reflection map in case of
        Specular workflow.
        """
        node_tex_metalness = self.nodes.get_metalness_tex_node()
        if node_tex_metalness is None:
            node_tex_metalness = self.nodes.get_reflection_tex_node()
        if node_tex_metalness is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_metalness,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_bsdf,
            sock_in_name="Metallic",
            sock_in_bl_idname_expected="NodeSocketFloatFactor")

    def connect_normal(self) -> None:
        """Sets up and connects the Normal channel."""

        node_tex_normal = self.nodes.get_normal_tex_node(self.params.use_16bit)
        if node_tex_normal is None:
            return

        normal_strength = 1.0

        node_bsdf = self.nodes.bsdf_principled
        node_normal = node_utils.create_normal_node(
            group=self.mat,
            parent=None,
            space="TANGENT",
            strength=normal_strength
        )
        self.nodes.normal = node_normal

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_normal,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_normal,
            sock_in_name="Color",
            sock_in_bl_idname_expected="NodeSocketColor")
        if self.params.mode_disp == "NORMAL":
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_normal,
                sock_out_name="Normal",
                sock_out_bl_idname_expected="NodeSocketVector",
                node_in=node_bsdf,
                sock_in_name="Normal",
                sock_in_bl_idname_expected="NodeSocketVector")

    def connect_opacity(self) -> None:
        """Sets up and connects the Alpha/Opacity channel."""

        output_opacity = self.nodes.get_opacity_effective_output()
        if output_opacity is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        create_link_sock_out(
            node_tree=self.mat.node_tree,
            sock_out=output_opacity,
            node_in=node_bsdf,
            sock_in_name="Alpha",
            sock_in_bl_idname_expected="NodeSocketFloatFactor")

    def connect_roughness(self) -> None:
        """Sets up and connects the Roughness channel.

        This works with Roughness map as well as with Gloss map (implicitly
        introducing the invert node).
        """

        (node_tex_roughness,
         is_specular) = self.nodes.get_roughness_effective_node()
        if node_tex_roughness is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        if not is_specular:
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_tex_roughness,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_bsdf,
                sock_in_name="Roughness",
                sock_in_bl_idname_expected="NodeSocketFloatFactor")
        else:
            node_gloss_invert = node_utils.create_color_invert_node(
                group=self.mat,
                parent=None,
                factor=1.0,
                name="Invert Gloss"
            )
            self.nodes.specular_invert_gloss = node_gloss_invert

            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_tex_roughness,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_gloss_invert,
                sock_in_name="Color",
                sock_in_bl_idname_expected="NodeSocketColor")

            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_gloss_invert,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_bsdf,
                sock_in_name="Roughness",
                sock_in_bl_idname_expected="NodeSocketFloatFactor")

    def connect_sss(self) -> None:
        """Sets up and connects the SSS channel."""

        node_tex_sss = self.nodes.get_sss_tex_node()
        if node_tex_sss is None:
            return

        node_bsdf = self.nodes.bsdf_principled

        if bpy.app.version >= (4, 0):
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_tex_sss,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_bsdf,
                sock_in_name="Subsurface Radius",
                sock_in_bl_idname_expected="NodeSocketVector")

            set_value(
                node=node_bsdf,
                sock_name="Subsurface Weight",
                sock_bl_idname_expected="NodeSocketFloatFactor",
                value=1.0)
            set_value(
                node=node_bsdf,
                sock_name="Subsurface Scale",
                sock_bl_idname_expected="NodeSocketFloatDistance",
                value=0.1)
            node_bsdf.subsurface_method = "RANDOM_WALK"
        else:
            node_math = node_utils.create_math_node(
                group=self.mat,
                parent=None,
                operation="MULTIPLY",
                use_clamp=True,
                value1=None,
                value2=0.3,
                name="SSS Strength (Multiply)"
            )
            self.nodes.sss_multiply = node_math

            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_tex_sss,
                sock_out_name="Color",
                sock_out_bl_idname_expected="NodeSocketColor",
                node_in=node_math,
                sock_in_name="Value",
                sock_in_bl_idname_expected="NodeSocketFloat")
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_math,
                sock_out_name="Value",
                sock_out_bl_idname_expected="NodeSocketFloat",
                node_in=node_bsdf,
                sock_in_name="Subsurface Radius",
                sock_in_bl_idname_expected="NodeSocketVector")

            set_value(
                node=node_bsdf,
                sock_name="Subsurface",
                sock_bl_idname_expected="NodeSocketFloatFactor",
                value=1.0)

            output_color = self.nodes.get_color_effective_output(
                ignore_translucency=True)
            create_link_sock_out(
                node_tree=self.mat.node_tree,
                sock_out=output_color,
                node_in=node_bsdf,
                sock_in_name="Subsurface Color",
                sock_in_bl_idname_expected="NodeSocketColor")

    def connect_translucency(self) -> None:
        """Sets up and connects the Translucency channel."""

        if self.nodes.get_sss_tex_node() is not None:
            # SSS supersedes Translucency and takes priority
            return

        node_tex_translucency = self.nodes.get_translucency_tex_node()
        if node_tex_translucency is None:
            return

        node_bsdf = self.nodes.bsdf_principled
        output_color = self.nodes.get_color_effective_output(
            ignore_translucency=True)
        if output_color is None:
            # TODO(Andreas): Need logger, here!
            print("Translucency workflow without diffuse map???")
        node_normal = self.nodes.normal
        output_opacity = self.nodes.get_opacity_effective_output()

        node_out = self.nodes.mat_out

        node_color_invert = node_utils.create_color_invert_node(
            group=self.mat,
            parent=None,
            factor=1.0,
            name="Inv. Transl."
        )
        self.nodes.translucency_color_invert = node_color_invert

        node_value = node_utils.create_value_node(
            group=self.mat,
            parent=None,
            value=0.350,
            name="Translucency Strength"
        )
        self.nodes.translucency_value = node_value

        node_transparent_bsdf = node_utils.create_transparent_bsdf_node(
            group=self.mat, parent=None)
        self.nodes.translucency_bsdf_transparent = node_transparent_bsdf

        node_translucent_bsdf = node_utils.create_translucent_bsdf_node(
            group=self.mat, parent=None)
        self.nodes.translucency_bsdf_translucent = node_translucent_bsdf

        node_add_shader = node_utils.create_add_shader_node(
            group=self.mat, parent=None)
        self.nodes.translucency_add_shader = node_add_shader

        node_mix_shader = node_utils.create_mix_shader_node(
            group=self.mat, parent=None)
        self.nodes.translucency_mix_shader = node_mix_shader

        node_mix_color = node_utils.create_mix_node(
            group=self.mat,
            parent=None,
            data_type="RGBA",
            use_clamp=True,
            clamp_result=False,
            blend_type="MULTIPLY",
            blend_factor=1.0,
            name="TRANSL. + COLOR (Multiply)"
        )
        self.nodes.translucency_mix_color = node_mix_color

        node_mix_translucency = node_utils.create_mix_node(
            group=self.mat,
            parent=None,
            data_type="RGBA",
            use_clamp=True,
            clamp_result=False,
            blend_type="MULTIPLY",
            blend_factor=1.0,
            name="Transl. Mult."
        )
        self.nodes.translucency_mix_translucency = node_mix_translucency

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_value,
            sock_out_name="Value",
            sock_out_bl_idname_expected="NodeSocketFloat",
            node_in=node_color_invert,
            sock_in_name="Color",
            sock_in_bl_idname_expected="NodeSocketColor")
        create_link_sock_out(
            node_tree=self.mat.node_tree,
            sock_out=output_color,
            node_in=node_mix_color,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketColor")
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_color_invert,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_mix_color,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketColor")
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_mix_color,
            sock_out_name="Result",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_bsdf,
            sock_in_name="Base Color",
            sock_in_bl_idname_expected="NodeSocketColor")
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_translucency,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_mix_translucency,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketColor",
            allow_index=True)  # Mix node needs indexes
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_value,
            sock_out_name="Value",
            sock_out_bl_idname_expected="NodeSocketFloat",
            node_in=node_mix_translucency,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketColor",
            allow_index=True)  # Mix node needs indexes
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_mix_translucency,
            sock_out_name="Result",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_translucent_bsdf,
            sock_in_name="Color",
            sock_in_bl_idname_expected="NodeSocketColor")
        if node_normal is not None:
            create_link(
                node_tree=self.mat.node_tree,
                node_out=node_normal,
                sock_out_name="Normal",
                sock_out_bl_idname_expected="NodeSocketVector",
                node_in=node_translucent_bsdf,
                sock_in_name="Normal",
                sock_in_bl_idname_expected="NodeSocketVector")

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_bsdf,
            sock_out_name="BSDF",
            sock_out_bl_idname_expected="NodeSocketShader",
            node_in=node_add_shader,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketShader",
            allow_index=True)
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_translucent_bsdf,
            sock_out_name="BSDF",
            sock_out_bl_idname_expected="NodeSocketShader",
            node_in=node_add_shader,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketShader",
            allow_index=True)

        if output_opacity is not None:
            create_link_sock_out(
                node_tree=self.mat.node_tree,
                sock_out=output_opacity,
                node_in=node_mix_shader,
                sock_in_name="Fac",
                sock_in_bl_idname_expected="NodeSocketFloatFactor")
        else:
            # Mateusz recommended to use a white value in this case
            set_value(
                node=node_mix_shader,
                sock_name="Fac",
                sock_bl_idname_expected="NodeSocketFloatFactor",
                value=1.0)

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_transparent_bsdf,
            sock_out_name="BSDF",
            sock_out_bl_idname_expected="NodeSocketShader",
            node_in=node_mix_shader,
            sock_in_name="A",
            sock_in_bl_idname_expected="NodeSocketShader")
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_add_shader,
            sock_out_name="Shader",
            sock_out_bl_idname_expected="NodeSocketShader",
            node_in=node_mix_shader,
            sock_in_name="B",
            sock_in_bl_idname_expected="NodeSocketShader")
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_mix_shader,
            sock_out_name="Shader",
            sock_out_bl_idname_expected="NodeSocketShader",
            node_in=node_out,
            sock_in_name="Surface",
            sock_in_bl_idname_expected="NodeSocketShader")

    def connect_transmission(self) -> None:
        """Sets up and connects the Transmission channel."""

        if self.nodes.get_sss_tex_node() is not None:
            # SSS takes priority over Transmission, just in case there are
            # assets having both maps in parallel.
            return

        node_tex_transmission = self.nodes.get_transmission_tex_node()
        if node_tex_transmission is None:
            return

        node_tex_color = self.nodes.get_color_tex_node()
        node_bsdf = self.nodes.bsdf_principled
        # node_out = self.nodes.mat_out
        node_vol_abs = node_utils.create_volume_absorption_node(
            group=self.mat,
            parent=None,
            density=100.0
        )
        self.nodes.transmission_vol_abs = node_vol_abs

        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_color,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_vol_abs,
            sock_in_name="Color",
            sock_in_bl_idname_expected="NodeSocketColor")
        # TODO(SOFT-2638): could show a redo last setting for this connection
        # create_link(
        #     node_tree=self.mat.node_tree,
        #     node_out=node_vol_abs,
        #     sock_out_name="Volume",
        #     sock_out_bl_idname_expected="NodeSocketShader",
        #     node_in=node_out,
        #     sock_in_name="Volume",
        #     sock_in_bl_idname_expected="NodeSocketShader")
        create_link(
            node_tree=self.mat.node_tree,
            node_out=node_tex_transmission,
            sock_out_name="Color",
            sock_out_bl_idname_expected="NodeSocketColor",
            node_in=node_bsdf,
            sock_in_name="Transmission Weight",
            sock_in_bl_idname_expected="NodeSocketFloatFactor")

    def connect_uv(self) -> None:
        """Sets up and connects the nodes for UV mapping."""

        frame = node_utils.create_frame(
            group=self.mat,
            parent=None,
            name="Texture Projection/Mapping"
        )

        node_tex_coord = node_utils.create_texture_coordinate_node(
            group=self.mat, parent=frame)
        self.nodes.tex_coords = node_tex_coord

        projection = self.params.projection

        # Create mapping node based on selected projection/mapping
        if projection == "MOSAIC":
            node_mapping = node_utils.create_mosaic_node(
                group=self.mat,
                parent=frame,
                width=W_NODE_WIDE,
                scale=self.params.scale
            )
            name_uv_out = "UV"
            self.nodes.mosaic = node_mapping

            self.mat.node_tree.links.new(
                node_mapping.inputs["UV"], node_tex_coord.outputs["UV"])
        elif projection == "UV":
            node_mapping = self.create_simple_uv_group(parent_frame=frame)
            name_uv_out = "UV"

            self.mat.node_tree.links.new(
                node_mapping.inputs["UV"], node_tex_coord.outputs["UV"])
        else:
            node_mapping = node_utils.create_mapping_node(
                group=self.mat,
                parent=frame,
                scale=self.params.scale
            )
            name_uv_out = "Vector"
            self.nodes.mapping = node_mapping

            self.mat.node_tree.links.new(
                node_mapping.inputs["Vector"],
                node_tex_coord.outputs["Generated"])

        # Finally connect mapping node to texture UV inputs
        for _node in self.nodes.tex.values():
            self.mat.node_tree.links.new(
                _node.inputs["Vector"], node_mapping.outputs[name_uv_out])

            if _node.name == "COL":
                _node.select = True
                self.mat.node_tree.nodes.active = _node

        for _node_list in self.nodes.tex_alt.values():
            for _node in _node_list:
                self.mat.node_tree.links.new(
                    _node.inputs["Vector"], node_mapping.outputs[name_uv_out])

    def position_node_rel_y(self,
                            node: bpy.types.Node,
                            node_anchor: bpy.types.Node,
                            x: float,
                            y_offset: float = 0.0
                            ) -> bool:
        """Positions a node in the node graph.

        In x-direction position is absolute (usually a column coordinate).
        In y-direction position is relative to node_anchor.
        """

        if node is None:
            return False

        if node_anchor is not None:
            loc_node = node_anchor.location.copy()
        else:
            # Should not happen, but we'll just take the node's
            # original y instead (so, row location is likely wrong
            # from here onward).
            loc_node = node.location

        loc_node[0] = x
        loc_node[1] += y_offset
        node.location = loc_node
        return True

    def position_tex_nodes_in_rows(self, y_top: float) -> None:
        """Positions all 'Image Texture' nodes in node graph in y-direction.

        Basically the 'Image Texture' nodes are positioned in rows in a
        specific order defined by TEX_COLUMN_ORDER.
        """

        y_coord = y_top
        for _map_type in TEX_COLUMN_ORDER:
            if _map_type not in self.nodes.tex:
                continue
            node_tex = self.nodes.tex[_map_type]
            loc_node_tex = node_tex.location
            loc_node_tex[1] = y_coord
            y_coord -= Y_OFFSET_ROW_TEX

            if _map_type not in self.nodes.tex_alt:
                continue

            for _node_tex in self.nodes.tex_alt[_map_type]:
                loc_node_tex = _node_tex.location
                loc_node_tex[1] = y_coord
                y_coord -= 100.0

    def position_tex_nodes_in_column(self, x: float) -> None:
        """Positions all 'Image Texture' nodes in node graph in x-direction."""

        for _map_type, _node_tex in self.nodes.tex.items():
            loc_node_tex = _node_tex.location
            loc_node_tex[0] = x

        for _map_type, _nodes_tex_alt in self.nodes.tex_alt.items():
            for _node_tex in _nodes_tex_alt:
                loc_node_tex = _node_tex.location
                loc_node_tex[0] = x

    def position_nodes(self) -> None:
        """Positions all nodes in node graph."""

        node_out = self.nodes.mat_out
        loc_node_out = node_out.location
        node_bsdf = self.nodes.bsdf_principled

        y_top = loc_node_out[1]

        # First run through texture nodes and position them vertically
        # to be used as row anchor points. The horizontal positioning of these
        # nodes happens at the end, when we know the final horizontal position
        # of the texure column.
        self.position_tex_nodes_in_rows(y_top)

        # We'll layout the columns right to left, starting at material output
        # node.
        # Columns are numbered left to right, beginning at zero. At max there
        # will be 11 columns (including material output node). If a column is
        # not used at all, it collapses into nothingness.
        x_column = loc_node_out[0] - X_OFFSET_COLUMN_NARROW

        # Column 10 is fixed: The material output node

        # Column 9 (only for Translucency)
        column_populated = self.position_node_rel_y(
            self.nodes.translucency_mix_shader, node_out, x=x_column)

        # Column 8 (only for Translucency or Transmission)
        if column_populated:
            x_column -= X_OFFSET_COLUMN_NARROW

        column_populated = self.position_node_rel_y(
            self.nodes.translucency_bsdf_transparent, node_out, x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.translucency_add_shader,
            node_out,
            x=x_column,
            y_offset=-Y_OFFSET_ROW_TEX)

        column_populated |= self.position_node_rel_y(
            self.nodes.transmission_vol_abs,
            node_out,
            x=x_column,
            y_offset=-2 * Y_OFFSET_ROW_TEX)

        # Column 7 (Principled BSDF and optionally Translucency)
        if column_populated:
            x_column -= X_OFFSET_COLUMN_WIDE
        else:
            # If column 8 was not populated (was a narrow one)
            # we need to compensate for the wider column 9
            x_column -= (X_OFFSET_COLUMN_WIDE - X_OFFSET_COLUMN_NARROW)

        column_populated = self.position_node_rel_y(
            node_bsdf, node_out, x=x_column)

        column_populated |= self.position_node_rel_y(
            self.nodes.translucency_bsdf_translucent,
            self.nodes.get_translucency_tex_node(),
            x=x_column)

        # Column 6 (only for Fabrics)
        if column_populated:
            x_column -= X_OFFSET_COLUMN_NARROW

        column_populated = self.position_node_rel_y(
            self.nodes.fabric_mix, node_bsdf, x=x_column)

        # Column 5 (only for Translucency)
        if column_populated:
            x_column -= X_OFFSET_COLUMN_NARROW

        column_populated = self.position_node_rel_y(
            self.nodes.translucency_mix_color,
            self.nodes.get_color_tex_node(),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.translucency_mix_translucency,
            self.nodes.get_translucency_tex_node(),
            x=x_column)

        # Column 4 (only for Translucency)
        if column_populated:
            x_column -= X_OFFSET_COLUMN_NARROW

        self.position_node_rel_y(
            self.nodes.translucency_color_invert,
            self.nodes.get_translucency_tex_node(),
            x=x_column)

        # Column 3
        if column_populated:
            x_column -= X_OFFSET_COLUMN_NARROW

        column_populated = self.position_node_rel_y(
            self.nodes.color_mix_ao,
            self.nodes.get_color_tex_node(),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.displacement,
            self.nodes.get_displacement_tex_node(self.params.use_16bit),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.specular_invert_gloss,
            self.nodes.get_gloss_tex_node(),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.normal,
            self.nodes.get_normal_tex_node(self.params.use_16bit),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.sss_multiply,
            self.nodes.get_sss_tex_node(),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.translucency_value,
            self.nodes.get_translucency_tex_node(),
            x=x_column)
        column_populated |= self.position_node_rel_y(
            self.nodes.fabric_fresnel,
            self.nodes.get_fuzz_tex_node(),
            x=x_column)

        # Column 2 (Static column, Texture nodes)
        if column_populated:
            x_column -= X_OFFSET_COLUMN_WIDE

        self.position_tex_nodes_in_column(x_column)

        # Column 1 (Default mapping node, Mosaic or Simple UV node group)
        x_column -= X_OFFSET_COLUMN_WIDE
        self.position_node_rel_y(
            self.nodes.mapping, self.nodes.get_color_tex_node(), x=x_column)
        self.position_node_rel_y(
            self.nodes.mosaic, self.nodes.get_color_tex_node(), x=x_column)
        self.position_node_rel_y(
            self.nodes.simple_uv_group,
            self.nodes.get_color_tex_node(),
            x=x_column)

        # Column 0 (Texture Coordinate node)
        x_column -= X_OFFSET_COLUMN_NARROW

        self.position_node_rel_y(
            self.nodes.tex_coords, self.nodes.get_color_tex_node(), x=x_column)

    def remove_unused_tex_nodes(self) -> None:
        """Optionally removes any unconnected Texture Image nodes."""

        if self.params.keep_unused_tex_nodes:
            return

        for _map_type, _node in self.nodes.tex.copy().items():
            linked_color_output = len(_node.outputs[0].links) > 0
            linked_alpha_output = len(_node.outputs[1].links) > 0
            if linked_color_output or linked_alpha_output:
                continue
            del self.nodes.tex[_map_type]
            self.mat.node_tree.nodes.remove(_node)

        for _map_type, _node_list in self.nodes.tex_alt.items():
            for _node in _node_list.copy():
                linked_color_output = len(_node.outputs[0].links) > 0
                linked_alpha_output = len(_node.outputs[1].links) > 0
                if linked_color_output or linked_alpha_output:
                    continue

                _node_list.remove(_node)
                self.mat.node_tree.nodes.remove(_node)

    def configure_material(self) -> None:
        """Configures the freshly created material."""

        self.mat.use_nodes = True
        self.mat.blend_method = "HASHED"

    @staticmethod
    def configure_principled_bsdf(node_bsdf: bpy.types.Node) -> None:
        """Configures the 'Principled BSDF' node."""

        node_bsdf.distribution = "GGX"
        if bpy.app.version >= (4, 0):
            node_bsdf.subsurface_method = "RANDOM_WALK_SKIN"
        elif bpy.app.version >= (3, 0):
            node_bsdf.subsurface_method = "RANDOM_WALK_FIXED_RADIUS"
        else:
            node_bsdf.subsurface_method = "RANDOM_WALK"

    def create_material(self) -> bool:
        """Creates a new nodal material."""

        name_mat = self.params.name_material

        mats_before = [mat for mat in bpy.data.materials]
        bpy.data.materials.new(name=name_mat)
        mats_new = [_mat
                    for _mat in bpy.data.materials
                    if _mat not in mats_before
                    ]
        if len(mats_new) == 0:
            msg = "Failed to create nodal material"
            reporting.capture_message(
                "build_mat_error_create", msg, "error")
            return False
        self.mat = mats_new[0]

        self.configure_material()

        self.nodes = CyclesNodesTopLevel()

        node_mat_out = get_node_by_type(self.mat, "ShaderNodeOutputMaterial")
        if node_mat_out is None:
            bpy.data.materials.remove(self.mat)
            self.mat = None
            msg = "Failed to find material output node"
            reporting.capture_message(
                "build_mat_error_create", msg, "error")
            return False
        node_mat_out.select = False
        self.nodes.mat_out = node_mat_out

        node_bsdf = get_node_by_type(self.mat, "ShaderNodeBsdfPrincipled")
        if node_bsdf is None:
            bpy.data.materials.remove(self.mat)
            self.mat = None
            msg = "Failed to find principled BSDF node"
            reporting.capture_message(
                "build_mat_error_create", msg, "error")
            return False
        node_bsdf.select = False
        self.nodes.bsdf_principled = node_bsdf

        self.configure_principled_bsdf(node_bsdf)
        return True

    def set_material_properties(self) -> None:
        """Stores material import parameters as properties into the material,
        so it can be re-used for later imports.
        """

        params = self.params
        asset_data = self.asset_data
        mat = self.mat

        asset_id = asset_data.asset_id
        asset_name = asset_data.asset_name
        # Need to use category name (or rather old P4B's asset type name),
        # here. This is needed to make reusing material work (also in old
        # projects).
        asset_type_name = ASSET_TYPE_TO_CATEGORY_NAME[asset_data.asset_type]

        size = params.size
        projection = params.projection
        use_16bit = params.use_16bit
        mode_disp = params.mode_disp
        scale = params.scale
        displacement = params.displacement

        mat.poliigon = f"{asset_type_name};{asset_name}"

        mat.poliigon_props.asset_name = asset_name
        mat.poliigon_props.asset_id = asset_id
        mat.poliigon_props.asset_type = asset_type_name
        mat.poliigon_props.size = size
        mat.poliigon_props.mapping = projection
        mat.poliigon_props.scale = scale
        mat.poliigon_props.displacement = displacement
        mat.poliigon_props.use_16bit = use_16bit
        mat.poliigon_props.mode_disp = mode_disp

        copy_simple_property_group(
            bpy.context.window_manager.polligon_map_prefs,
            mat.poliigon_props.map_prefs)

    def import_material(self,
                        asset_data: AssetData,
                        params: MaterialImportParameters,
                        remove_unused_tex_nodes: bool = False
                        ) -> Optional[bpy.types.Material]:
        """Executes the actual material import configured in MaterialImporter
        for Blender/Cycles."""

        self.init(asset_data, params)

        result = self.create_material()
        if not result:
            return None

        self.create_texture_nodes()

        self.connect_color()
        self.connect_displacement()
        self.connect_emission()
        self.connect_metalness()
        self.connect_normal()
        self.connect_opacity()
        self.connect_roughness()
        self.connect_sss()
        self.connect_translucency()
        self.connect_transmission()
        self.connect_fabric()  # Do after translucency!

        self.connect_uv()

        self.remove_unused_tex_nodes()

        self.position_nodes()

        self.set_material_properties()
        return self.mat
