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

from typing import List

from bpy.types import Operator
from bpy.props import (
    IntProperty,
    StringProperty)
import bpy.utils.previews
import bmesh


from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


SCALE_UNIT_FACTORS = {
    "KILOMETERS": 1000.0,
    "CENTIMETERS": 1.0 / 100.0,
    "MILLIMETERS": 1.0 / 1000.0,
    "MILES": 1.0 / 0.000621371,
    "FEET": 1.0 / 3.28084,
    "INCHES": 1.0 / 39.3701
}


class POLIIGON_OT_apply(Operator):
    bl_idname = "poliigon.poliigon_apply"
    bl_label = _t("Apply Material :")
    bl_description = _t("Apply Material to Selection")
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821

    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    name_material: StringProperty(options={"HIDDEN"})  # noqa: F821

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)
        self.exec_count = 0

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @staticmethod
    def get_edit_objects(context) -> List[bpy.types.Object]:
        objs_selected = []

        for obj in context.scene.objects:
            if obj.mode != "EDIT":
                continue
            mesh = obj.data
            b_mesh = bmesh.from_edit_mesh(mesh)
            for _face in b_mesh.faces:
                if not _face.select:
                    continue
                objs_selected.append(obj)
                break
        return objs_selected

    @reporting.handle_operator()
    def execute(self, context):
        objs_selected = [_obj for _obj in context.selected_objects]
        if len(objs_selected) == 0:
            objs_selected = self.get_edit_objects(context)

        objs_add_disp = [_obj
                         for _obj in objs_selected
                         if "Subdivision" not in _obj.modifiers]

        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_name = asset_data.asset_name
        asset_type = asset_data.asset_type

        mat = None
        if self.name_material != "":
            mat = bpy.data.materials[self.name_material]

        elif asset_name in cTB.imported_assets["Textures"].keys():
            if len(cTB.imported_assets["Textures"][asset_name]) == 1:
                mat = cTB.imported_assets["Textures"][asset_name][0]
        if mat is None:
            # Unexpected need to download local, should avoid happening.
            reporting.capture_message(
                "triggered_popup_mid_apply", asset_name, level="info")
            return {"CANCELLED"}

        do_subdiv = False
        if cTB.settings["use_disp"] and len(objs_add_disp) > 0:
            if cTB.prefs and cTB.prefs.mode_disp == "MICRO":
                do_subdiv = True

        if do_subdiv or len(objs_selected) > len(objs_add_disp):
            bpy.context.scene.render.engine = "CYCLES"
            if bpy.app.version < (5, 0):
                # Blender 5.0 no longer has feature sets, adaptive is included
                bpy.context.scene.cycles.feature_set = "EXPERIMENTAL"

            for _node in mat.node_tree.nodes:
                if _node.type != "GROUP":
                    continue
                for _input in _node.inputs:
                    if _input.type != "VALUE":
                        continue
                    elif _input.name == "Displacement Strength":
                        _node.inputs[_input.name].default_value = mat.poliigon_props.displacement

        # TODO(Andreas): Not sure, what this was good for.
        #                Seems to have done nothing.
        # faces_all = []
        # for _key in cTB.vActiveFaces.keys():
        #     faces_all += cTB.vActiveFaces[_key]

        valid_objects = 0
        for _obj in objs_selected:
            if hasattr(_obj.data, "materials"):
                valid_objects += 1
            else:
                continue

            if _obj.mode != "EDIT":
                _obj.active_material = mat
            else:
                mats_obj = [_mat.material
                            for _mat in _obj.material_slots
                            if _mat is not None]
                if mat not in mats_obj:
                    _obj.data.materials.append(mat)
                for idx in range(len(_obj.material_slots)):
                    if _obj.material_slots[idx].material != mat:
                        continue
                    _obj.active_material_index = idx
                    bpy.ops.object.material_slot_assign()

            if do_subdiv and _obj in objs_add_disp:
                mod_subdiv = _obj.modifiers.new(
                    name="Subdivision", type="SUBSURF")
                mod_subdiv.subdivision_type = "SIMPLE"
                mod_subdiv.levels = 0  # Don't do subdiv in viewport
                if bpy.app.version < (5, 0):
                    # In blender 5.0, there's no special settings for this.
                    _obj.cycles.use_adaptive_subdivision = True

            # Scale ...........................................................
            # TODO(Andreas): What is this? Did this ever work?
            dimension = "?"
            if dimension != "?":
                scale_mult = bpy.context.scene.unit_settings.scale_length

                unit = bpy.context.scene.unit_settings.length_unit
                scale_mult *= SCALE_UNIT_FACTORS[unit]
                vec_scale = (_obj.scale * scale_mult) / dimension

                nodes_mat = mat.node_tree.nodes
                for _node in nodes_mat:
                    if _node.type != "GROUP":
                        continue
                    for _input in _node.inputs:
                        if _input.type != "VALUE":
                            continue
                        elif _input.name == "Scale":
                            _node.inputs[_input.name].default_value = vec_scale[0]

        cTB.vActiveType = asset_type.name
        cTB.vActiveAsset = asset_name
        cTB.vActiveMat = mat.name
        bpy.ops.poliigon.poliigon_active(
            mode="mat", asset_type=asset_type.name, data=cTB.vActiveMat
        )
        return {"FINISHED"}
