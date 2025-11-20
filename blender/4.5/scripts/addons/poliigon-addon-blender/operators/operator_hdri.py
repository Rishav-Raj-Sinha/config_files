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

from typing import List, Optional, Tuple
import mathutils
import os
import re
from math import pi

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
import bpy.utils.previews

from ..modules.poliigon_core.assets import AssetData
from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_hdri(Operator):
    bl_idname = "poliigon.poliigon_hdri"
    bl_label = _t("HDRI Import")
    bl_description = _t("Import HDRI")
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "INTERNAL", "UNDO"}

    def _fill_light_size_drop_down(
            self, context) -> List[Tuple[str, str, str]]:
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_type_data = asset_data.get_type_data()

        # Get list of locally available sizes
        asset_files = {}
        asset_type_data.get_files(asset_files)
        asset_files = list(asset_files.keys())

        # Populate dropdown items
        local_exr_sizes = []
        for path_asset in asset_files:
            filename = os.path.basename(path_asset)
            if not filename.endswith(".exr"):
                continue
            match_object = re.search(r"_(\d+K)[_\.]", filename)
            if match_object:
                local_exr_sizes.append(match_object.group(1))
        # Sort by comparing integer size without "K"
        local_exr_sizes.sort(key=lambda s: int(s[:-1]))
        items_size = []
        for size in local_exr_sizes:
            # Tuple: (id, name, description, icon, enum value)
            items_size.append((size, f"{size} EXR", f"{size} EXR"))
        return items_size

    def _fill_bg_size_drop_down(self, context) -> List[Tuple[str, str, str]]:
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_type_data = asset_data.get_type_data()

        # Get list of locally available sizes
        asset_files = {}
        asset_type_data.get_files(asset_files)
        asset_files = list(asset_files.keys())

        # Populate dropdown items
        local_exr_sizes = []
        local_jpg_sizes = []
        for path_asset in asset_files:
            filename = os.path.basename(path_asset)
            is_exr = filename.endswith(".exr")
            is_jpg = filename.lower().endswith(".jpg")
            is_jpg &= "_JPG" in filename
            if not is_exr and not is_jpg:
                continue
            match_object = re.search(r"_(\d+K)[_\.]", filename)
            if not match_object:
                continue
            local_size = match_object.group(1)
            if is_exr:
                local_exr_sizes.append(f"{local_size}_EXR")
            elif is_jpg:
                local_jpg_sizes.append(f"{local_size}_JPG")

        local_sizes = local_exr_sizes + local_jpg_sizes
        # Sort by comparing integer size without "K_JPG" or "K_EXR"
        local_sizes.sort(key=lambda s: int(s[:-5]))
        items_size = []
        for size in local_sizes:
            # Tuple: (id, name, description, icon, enum value)
            label = size.replace("_", " ")
            items_size.append((size, label, label))
        return items_size

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    # If do_apply is set True, the sizes are ignored and set internally
    do_apply: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821
    size: EnumProperty(
        name=_t("Light Texture"),  # noqa F722
        items=_fill_light_size_drop_down,
        description=_t("Change size of light texture."))  # noqa F722
    # This is not a pure size, but is a string like "4K_JPG"
    size_bg: EnumProperty(
        name=_t("Background Texture"),  # noqa F722
        items=_fill_bg_size_drop_down,
        description=_t("Change size of background texture."))  # noqa F722
    hdr_strength: FloatProperty(
        name=_t("HDR Strength"),  # noqa F722
        description=_t("Strength of Light and Background textures"),  # noqa F722
        soft_min=0.0,
        step=10,
        default=1.0)
    rotation: FloatProperty(
        name=_t("Z-Rotation"),  # noqa: F821
        description=_t("Z-Rotation"),  # noqa: F821
        unit="ROTATION",  # noqa: F821
        soft_min=-2.0 * pi,
        soft_max=2.0 * pi,
        # precision needed here, otherwise Redo Last and node show different values
        precision=3,
        step=10,
        default=0.0)

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)
        self.exec_count = 0
        self.node_output_world = None
        self.node_tex_coord = None
        self.node_mapping = None
        self.node_tex_env_light = None
        self.node_background_light = None
        self.node_tex_env_bg = None
        self.node_background_bg = None
        self.node_mix_shader = None
        self.node_light_path = None

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @staticmethod
    def get_imported_hdri(asset_id: int) -> Optional[bpy.types.Image]:
        """Returns the imported HDRI image (if any)."""

        img_hdri = None
        for _img in bpy.data.images:
            try:
                asset_id_img = _img.poliigon_props.asset_id
                if asset_id_img != asset_id:
                    continue
                img_hdri = _img
                break
            except BaseException:
                # skip non-Poliigon images (no props)
                continue
        return img_hdri

    @reporting.handle_operator()
    def execute(self, context):
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_type_data = asset_data.get_type_data()

        asset_name = asset_data.asset_name
        local_convention = asset_data.get_convention(local=True)
        addon_convention = cTB.addon_convention

        name_light = f"{asset_name}_Light"
        name_bg = f"{asset_name}_Background"

        try:
            if "_" not in self.size_bg:
                raise ValueError
            size_bg_eff, filetype_bg = self.size_bg.split("_")
        except Exception:
            msg = ("POLIIGON_OT_hdri: Wrong size_bg format "
                   f"({self.size_bg}), expected '4K_JPG' or '1K_EXR'")
            raise ValueError(msg)

        cTB.logger.debug("POLIIGON_OT_hdri "
                         f"{asset_name}, {name_light}, {name_bg}")

        existing = self.get_imported_hdri(self.asset_id)

        # Whenever an HDR is loaded, it fully replaces the prior loaded
        # images/resolutions. Thus, if we are "applying" an already imported
        # one, we don't need to worry about resolution selection.

        if not self.do_apply or not existing:
            # Remove existing images to force loading this resolution.
            if name_light in bpy.data.images.keys():
                bpy.data.images.remove(bpy.data.images[name_light])

            if name_bg in bpy.data.images.keys():
                bpy.data.images.remove(bpy.data.images[name_bg])
        elif self.do_apply:
            if name_light in bpy.data.images.keys():
                path_light = bpy.data.images[name_light].filepath
                filename = os.path.basename(path_light)
                match_object = re.search(r"_(\d+K)[_\.]", filename)
                size_light = match_object.group(1) if match_object else cTB.settings["hdri"]
                self.size = size_light
            if name_bg in bpy.data.images.keys():
                path_bg = bpy.data.images[name_bg].filepath
                filename = os.path.basename(path_bg)
                file_type = "JPG" if "_JPG" in filename else "EXR"
                match_object = re.search(r"_(\d+K)[_\.]", filename)
                # TODO(Andreas): should next line use cTB.settings["hdribg"] ?
                size_bg = match_object.group(1) if match_object else cTB.settings["hdri"]
                self.size_bg = f"{size_bg}_{file_type}"
                size_bg_eff = size_bg
                filetype_bg = file_type

        light_exists = name_light in bpy.data.images.keys()
        bg_exists = name_bg in bpy.data.images.keys()
        if not light_exists or not bg_exists:
            if not self.size or self.do_apply:
                # Edge case that shouldn't occur as the resolution should be
                # explicitly set, or just applying a local tex already,
                # but fallback if needed.
                self.size = cTB.settings["hdri"]

            size_light = asset_type_data.get_size(
                self.size,
                local_only=True,
                addon_convention=addon_convention,
                local_convention=local_convention)

            files = {}
            asset_type_data.get_files(files)
            files = list(files.keys())

            files_tex_exr = [_file for _file in files
                             if size_light in os.path.basename(_file) and _file.lower().endswith(".exr")]

            if len(files_tex_exr) == 0:
                # TODO(Andreas): Shouldn't be needed anymore with AssetIndex
                # cTB.f_GetLocalAssets()  # Refresh local assets data structure.
                msg = (f"Unable to locate image {name_light} with size {size_light}, "
                       f"try downloading {asset_name} again.")
                reporting.capture_message(
                    "failed_load_light_hdri", msg, "error")
                msg = _t(
                    "Unable to locate image {0} with size {1}, try downloading {2} again."
                ).format(name_light, size_light, asset_name)
                self.report({"ERROR"}, msg)
                return {"CANCELLED"}
            file_tex_light = files_tex_exr[0]

            if filetype_bg == "JPG":
                size_bg = asset_type_data.get_size(
                    size_bg_eff,
                    local_only=True,
                    addon_convention=addon_convention,
                    local_convention=local_convention)

                files_tex_jpg = [_file for _file in files
                                 if size_bg in os.path.basename(_file) and _file.lower().endswith(".jpg")]

                if len(files_tex_jpg) == 0:
                    # TODO(Andreas): Shouldn't be needed anymore with AssetIndex
                    # cTB.f_GetLocalAssets()  # Refresh local assets data structure.
                    msg = (f"Unable to locate image {name_bg} with size {size_bg} (JPG), "
                           f"try downloading {asset_name} again.")
                    reporting.capture_message(
                        "failed_load_bg_jpg", msg, "error")
                    msg = _t(
                        "Unable to locate image {0} with size {1} (JPG), try downloading {2} again."
                    ).format(name_bg, size_bg, asset_name)
                    self.report({"ERROR"}, msg)
                    return {"CANCELLED"}
                file_tex_bg = files_tex_jpg[0]
            elif size_light != size_bg_eff:
                size_bg = size_bg_eff
                files_tex_exr = [_file for _file in files
                                 if size_bg_eff in os.path.basename(_file) and _file.lower().endswith(".exr")]
                if len(files_tex_exr) == 0:
                    # TODO(Andreas): Shouldn't be needed anymore with AssetIndex
                    # cTB.f_GetLocalAssets()  # Refresh local assets data structure.
                    msg = (f"Unable to locate image {name_bg} with size {size_bg} (EXR), "
                           f"try downloading {asset_name} again")
                    reporting.capture_message(
                        "failed_load_bg_hdri", msg, "error")
                    msg = _t(
                        "Unable to locate image {0} with size {1} (EXR), try downloading {2} again"
                    ).format(name_bg, size_bg, asset_name)
                    self.report({"ERROR"}, msg)
                    return {"CANCELLED"}
                file_tex_bg = files_tex_exr[0]
            else:
                size_bg = size_light
                file_tex_bg = file_tex_light

        # Reset apply for Redo Last menu to work properly
        self.do_apply = False

        # Check if same texture is used for both lighting and background
        use_simple_layout = file_tex_bg == file_tex_light
        # Use same name for both light and background only when using same file (simple layout)
        if use_simple_layout:
            name_bg = name_light
        # ...............................................................................................

        if use_simple_layout:
            self._simple_layout(name_light,
                                file_tex_light,
                                asset_data)
        else:
            self._complex_layout(name_light,
                                 file_tex_light,
                                 name_bg,
                                 file_tex_bg,
                                 asset_data)

        self.set_poliigon_props_world(context, asset_data)

        cTB.f_GetSceneAssets()

        if self.exec_count == 0:
            cTB.signal_import_asset(asset_id=self.asset_id)
            cTB.set_first_local_asset()
        self.exec_count += 1
        self.report({"INFO"}, _t("HDRI Imported : {0}").format(asset_name))
        return {"FINISHED"}

    def _get_poliigon_hdri_nodes(self, nodes_world) -> dict:
        """Identify existing Poliigon HDRI nodes by their labels and types.

        Returns a dictionary mapping node roles to existing nodes, or None if not found.
        This allows us to preserve user-authored nodes while only replacing Poliigon ones.
        """
        poliigon_nodes = {
            'tex_coord': None,
            'mapping': None,
            'tex_env_light': None,
            'tex_env_bg': None,
            'background_light': None,
            'background_bg': None,
            'mix_shader': None,
            'light_path': None,
            'output_world': None
        }

        for node in nodes_world:
            try:
                # Skip invalid nodes
                if not hasattr(node, 'type') or not hasattr(node, 'label'):
                    continue

                if node.type == "TEX_COORD" and node.label == "Mapping":
                    poliigon_nodes['tex_coord'] = node
                elif node.type == "MAPPING" and node.label == "Mapping":
                    poliigon_nodes['mapping'] = node
                elif node.type == "TEX_ENVIRONMENT":
                    if node.label == "Lighting":
                        poliigon_nodes['tex_env_light'] = node
                    elif node.label == "Background":
                        poliigon_nodes['tex_env_bg'] = node
                elif node.type == "BACKGROUND":
                    if node.label == "Lighting":
                        poliigon_nodes['background_light'] = node
                    elif node.label == "Background":
                        poliigon_nodes['background_bg'] = node
                    elif poliigon_nodes['background_light'] is None:
                        # If background_light isn't assigned yet, assign the
                        # first one we identify. This avoids clutter in the
                        # default blender world layout by reusing both nodes.
                        poliigon_nodes['background_light'] = node
                elif node.type == "MIX_SHADER":
                    # Mix shader nodes created by Poliigon typically don't have custom labels
                    # but we only want to replace if it's connected to our setup
                    if self._is_poliigon_mix_shader(node):
                        poliigon_nodes['mix_shader'] = node
                elif node.type == "LIGHT_PATH":
                    # Similar to mix shader - identify by connection pattern
                    if self._is_poliigon_light_path(node):
                        poliigon_nodes['light_path'] = node
                elif node.type == "OUTPUT_WORLD":
                    poliigon_nodes['output_world'] = node
            except Exception as e:
                # Skip problematic nodes instead of crashing
                cTB.logger.warning(f"Skipping problematic node during identification: {str(e)}")
                continue

        return poliigon_nodes

    def _is_poliigon_mix_shader(self, node) -> bool:
        """Check if a MixShader node is part of the Poliigon HDRI setup."""
        try:
            # Validate node has required attributes
            if not hasattr(node, 'inputs') or len(node.inputs) < 3:
                return False

            # Check if it's connected to background nodes with Poliigon labels
            input_1 = node.inputs[1]
            input_2 = node.inputs[2]

            if hasattr(input_1, 'is_linked') and input_1.is_linked:
                if hasattr(input_1, 'links') and input_1.links:
                    linked_node = input_1.links[0].from_node
                    if (hasattr(linked_node, 'type') and linked_node.type == "BACKGROUND" and
                            hasattr(linked_node, 'label') and linked_node.label == "Lighting"):
                        return True

            if hasattr(input_2, 'is_linked') and input_2.is_linked:
                if hasattr(input_2, 'links') and input_2.links:
                    linked_node = input_2.links[0].from_node
                    if (hasattr(linked_node, 'type') and linked_node.type == "BACKGROUND" and
                            hasattr(linked_node, 'label') and linked_node.label == "Background"):
                        return True
        except Exception:
            pass
        return False

    def _is_poliigon_light_path(self, node) -> bool:
        """Check if a LightPath node is part of the Poliigon HDRI setup."""
        try:
            # Validate node has required attributes
            if not hasattr(node, 'outputs'):
                return False

            # Check if it's connected to a mix shader that's part of Poliigon setup
            for output in node.outputs:
                if hasattr(output, 'is_linked') and output.is_linked:
                    if hasattr(output, 'links'):
                        for link in output.links:
                            if hasattr(link, 'to_node'):
                                linked_node = link.to_node
                                if (hasattr(linked_node, 'type') and linked_node.type == "MIX_SHADER" and
                                        self._is_poliigon_mix_shader(linked_node)):
                                    return True
        except Exception:
            pass
        return False

    def _remove_poliigon_nodes(self, nodes_world, poliigon_nodes: dict) -> None:
        """Safely remove only the identified Poliigon HDRI nodes."""
        nodes_to_remove = []

        for node_role, node in poliigon_nodes.items():
            if node is not None and node_role != 'output_world':  # Never remove output_world
                nodes_to_remove.append(node)

        # Remove nodes in a separate loop to avoid modifying collection during iteration
        for node in nodes_to_remove:
            try:
                # Additional validation before removal
                if hasattr(node, 'name') and node.name in nodes_world:
                    nodes_world.remove(node)
            except Exception as e:
                cTB.logger.warning(f"Failed to remove node {getattr(node, 'name', 'unnamed')}: {str(e)}")
                continue

    def _create_or_reuse_output_world(self, nodes_world, poliigon_nodes: dict) -> object:
        """Create or reuse the output world node."""
        output_world = poliigon_nodes.get('output_world')

        # Validate that the existing output world is still valid
        if output_world is not None:
            try:
                # Test if the node is still accessible and valid
                _ = output_world.type
                _ = output_world.location
                return output_world
            except Exception:
                # Node is corrupted or no longer accessible
                cTB.logger.warning("Existing output world node is corrupted, creating new one")
                output_world = None

        if output_world is None:
            # Create new output world node
            output_world = nodes_world.new("ShaderNodeOutputWorld")
            output_world.location = mathutils.Vector((250, 225.0))

        return output_world

    def _validate_node_setup(self) -> bool:
        """Validate that all required nodes were created successfully."""
        required_nodes = ['node_output_world', 'node_tex_coord', 'node_mapping', 'node_tex_env_light', 'node_background_light']

        for node_attr in required_nodes:
            if not hasattr(self, node_attr) or getattr(self, node_attr) is None:
                cTB.logger.error(f"Required node {node_attr} was not created")
                return False

        return True

    def _simple_layout(self,
                       name_light: str,
                       file_tex_light: str,
                       asset_data: AssetData
                       ) -> None:
        if not bpy.context.scene.world:
            bpy.ops.world.new()
            bpy.context.scene.world = bpy.data.worlds[-1]
        bpy.context.scene.world.use_nodes = True
        nodes_world = bpy.context.scene.world.node_tree.nodes
        links_world = bpy.context.scene.world.node_tree.links

        # Use improved selective node management
        try:
            poliigon_nodes = self._get_poliigon_hdri_nodes(nodes_world)
            self._remove_poliigon_nodes(nodes_world, poliigon_nodes)
            self.node_output_world = self._create_or_reuse_output_world(nodes_world, poliigon_nodes)
        except Exception as e:
            cTB.logger.error(f"Failed during node identification/removal: {str(e)}")
            # Fallback to more aggressive approach if needed
            self.node_output_world = None
            for node in nodes_world:
                if node.type == "OUTPUT_WORLD":
                    self.node_output_world = node
                    break
            if self.node_output_world is None:
                self.node_output_world = nodes_world.new("ShaderNodeOutputWorld")
        self.node_output_world.location = mathutils.Vector((320, 300))

        # Create new Poliigon nodes
        try:
            self.node_tex_coord = nodes_world.new("ShaderNodeTexCoord")
            self.node_tex_coord.label = "Mapping"
            self.node_tex_coord.location = mathutils.Vector((-720, 300))

            self.node_mapping = nodes_world.new("ShaderNodeMapping")
            self.node_mapping.label = "Mapping"
            self.node_mapping.location = mathutils.Vector((-470, 300))

            self.node_tex_env_light = nodes_world.new("ShaderNodeTexEnvironment")
            self.node_tex_env_light.label = "Lighting"
            self.node_tex_env_light.location = mathutils.Vector((-220, 300))

            self.node_background_light = nodes_world.new("ShaderNodeBackground")
            self.node_background_light.label = "Lighting"
            self.node_background_light.location = mathutils.Vector((120, 300))

            # Validate node creation
            if not self._validate_node_setup():
                raise Exception("Failed to create required nodes")

        except Exception as e:
            cTB.logger.error(f"Failed to create nodes in simple layout: {str(e)}")
            raise

        # Create connections with error handling
        try:
            links_world.new(self.node_tex_coord.outputs["Generated"], self.node_mapping.inputs["Vector"])
            links_world.new(self.node_mapping.outputs["Vector"], self.node_tex_env_light.inputs["Vector"])
            links_world.new(self.node_tex_env_light.outputs["Color"], self.node_background_light.inputs["Color"])
            links_world.new(self.node_background_light.outputs[0], self.node_output_world.inputs["Surface"])
        except Exception as e:
            cTB.logger.error(f"Failed to create node links in simple layout: {str(e)}")
            raise

        # Load images
        try:
            if name_light in bpy.data.images.keys():
                img_light = bpy.data.images[name_light]
            else:
                file_tex_light_norm = os.path.normpath(file_tex_light)
                img_light = bpy.data.images.load(file_tex_light_norm)
                img_light.name = name_light
                img_light.poliigon = "HDRIs;" + asset_data.asset_name
                self.set_poliigon_props_image(img_light, asset_data)
        except Exception as e:
            cTB.logger.error(f"Failed to load images in simple layout: {str(e)}")
            raise

        # Set node properties
        try:
            if "Rotation" in self.node_mapping.inputs:
                self.node_mapping.inputs["Rotation"].default_value[2] = self.rotation
            else:
                self.node_mapping.rotation[2] = self.rotation
            self.node_tex_env_light.image = img_light
            self.node_background_light.inputs["Strength"].default_value = self.hdr_strength
        except Exception as e:
            cTB.logger.error(f"Failed to set node properties in simple layout: {str(e)}")
            raise

    def _complex_layout(self,
                        name_light: str,
                        file_tex_light: str,
                        name_bg: str,
                        file_tex_bg: str,
                        asset_data: AssetData
                        ) -> None:
        if not bpy.context.scene.world:
            bpy.ops.world.new()
            bpy.context.scene.world = bpy.data.worlds[-1]
        bpy.context.scene.world.use_nodes = True
        nodes_world = bpy.context.scene.world.node_tree.nodes
        links_world = bpy.context.scene.world.node_tree.links

        # Use improved selective node management
        try:
            poliigon_nodes = self._get_poliigon_hdri_nodes(nodes_world)
            self._remove_poliigon_nodes(nodes_world, poliigon_nodes)
            self.node_output_world = self._create_or_reuse_output_world(nodes_world, poliigon_nodes)
        except Exception as e:
            cTB.logger.error(f"Failed during node identification/removal: {str(e)}")
            # Fallback to more aggressive approach if needed
            self.node_output_world = None
            for node in nodes_world:
                if node.type == "OUTPUT_WORLD":
                    self.node_output_world = node
                    break
            if self.node_output_world is None:
                self.node_output_world = nodes_world.new("ShaderNodeOutputWorld")
        self.node_output_world.location = mathutils.Vector((250, 225.0))

        # Create all required nodes
        try:
            self.node_tex_coord = nodes_world.new("ShaderNodeTexCoord")
            self.node_tex_coord.label = "Mapping"
            self.node_tex_coord.location = mathutils.Vector((-950, 225))

            self.node_mapping = nodes_world.new("ShaderNodeMapping")
            self.node_mapping.label = "Mapping"
            self.node_mapping.location = mathutils.Vector((-750, 225))

            self.node_tex_env_light = nodes_world.new("ShaderNodeTexEnvironment")
            self.node_tex_env_light.label = "Lighting"
            self.node_tex_env_light.location = mathutils.Vector((-550, 350))

            self.node_tex_env_bg = nodes_world.new("ShaderNodeTexEnvironment")
            self.node_tex_env_bg.label = "Background"
            self.node_tex_env_bg.location = mathutils.Vector((-550, 100))

            self.node_background_light = nodes_world.new("ShaderNodeBackground")
            self.node_background_light.label = "Lighting"
            self.node_background_light.location = mathutils.Vector((-250, 100))

            self.node_background_bg = nodes_world.new("ShaderNodeBackground")
            self.node_background_bg.label = "Background"
            self.node_background_bg.location = mathutils.Vector((-250, -50))

            self.node_mix_shader = nodes_world.new("ShaderNodeMixShader")
            self.node_mix_shader.location = mathutils.Vector((0, 225))

            self.node_light_path = nodes_world.new("ShaderNodeLightPath")
            self.node_light_path.location = mathutils.Vector((-250, 440))

            # Validate critical nodes for complex layout
            critical_nodes = ['node_output_world', 'node_tex_coord', 'node_mapping',
                              'node_tex_env_light', 'node_background_light', 'node_tex_env_bg',
                              'node_background_bg', 'node_mix_shader', 'node_light_path']
            for node_attr in critical_nodes:
                if not hasattr(self, node_attr) or getattr(self, node_attr) is None:
                    raise Exception(f"Required node {node_attr} was not created")

        except Exception as e:
            cTB.logger.error(f"Failed to create nodes in complex layout: {str(e)}")
            raise

        # Create all links after ensuring nodes exist
        try:
            links_world.new(self.node_tex_coord.outputs["Generated"], self.node_mapping.inputs["Vector"])
            links_world.new(self.node_mapping.outputs["Vector"], self.node_tex_env_light.inputs["Vector"])
            links_world.new(self.node_tex_env_light.outputs["Color"], self.node_background_light.inputs["Color"])
            links_world.new(self.node_background_light.outputs[0], self.node_mix_shader.inputs[1])
            links_world.new(self.node_mapping.outputs["Vector"], self.node_tex_env_bg.inputs["Vector"])
            links_world.new(self.node_tex_env_bg.outputs["Color"], self.node_background_bg.inputs["Color"])
            links_world.new(self.node_background_bg.outputs[0], self.node_mix_shader.inputs[2])
            links_world.new(self.node_light_path.outputs[0], self.node_mix_shader.inputs[0])
            links_world.new(self.node_mix_shader.outputs[0], self.node_output_world.inputs[0])
        except Exception as e:
            cTB.logger.error(f"Failed to create node links: {str(e)}")
            raise

        # Load images safely
        try:
            # Load light image
            if name_light in bpy.data.images.keys():
                img_light = bpy.data.images[name_light]
            else:
                file_tex_light_norm = os.path.normpath(file_tex_light)
                img_light = bpy.data.images.load(file_tex_light_norm)
                img_light.name = name_light
                img_light.poliigon = "HDRIs;" + asset_data.asset_name
                self.set_poliigon_props_image(img_light, asset_data)

            # Load background image
            if name_bg in bpy.data.images.keys():
                img_bg = bpy.data.images[name_bg]
            else:
                file_tex_bg_norm = os.path.normpath(file_tex_bg)
                img_bg = bpy.data.images.load(file_tex_bg_norm)
                img_bg.name = name_bg
                self.set_poliigon_props_image(img_bg, asset_data)

            # Set node properties safely
            if "Rotation" in self.node_mapping.inputs:
                self.node_mapping.inputs["Rotation"].default_value[2] = self.rotation
            else:
                self.node_mapping.rotation[2] = self.rotation

            self.node_tex_env_light.image = img_light
            self.node_background_light.inputs["Strength"].default_value = self.hdr_strength

            self.node_tex_env_bg.image = img_bg
            self.node_background_bg.inputs["Strength"].default_value = self.hdr_strength

        except Exception as e:
            cTB.logger.error(f"Failed to load or setup images: {str(e)}")
            raise

    def set_poliigon_props_image(
            self, img: bpy.types.Image, asset_data: AssetData) -> None:
        """Sets Poliigon property of an imported image."""

        img.poliigon_props.asset_name = asset_data.asset_name
        img.poliigon_props.asset_id = self.asset_id
        img.poliigon_props.asset_type = asset_data.asset_type.name
        img.poliigon_props.size = self.size
        img.poliigon_props.size_bg = self.size_bg
        img.poliigon_props.hdr_strength = self.hdr_strength
        img.poliigon_props.rotation = self.rotation

    def set_poliigon_props_world(self, context, asset_data: AssetData) -> None:
        """Sets Poliigon property of world."""

        context_world = context.scene.world
        context_world.poliigon_props.asset_name = asset_data.asset_name
        context_world.poliigon_props.asset_id = self.asset_id
        context_world.poliigon_props.asset_type = asset_data.asset_type.name
        context_world.poliigon_props.size = self.size
        context_world.poliigon_props.size_bg = self.size_bg
        context_world.poliigon_props.hdr_strength = self.hdr_strength
        context_world.poliigon_props.rotation = self.rotation
