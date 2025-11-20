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
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty)
import bpy.utils.previews

from ..modules.poliigon_core.multilingual import _t
from ..material_import_utils import find_identical_material
from .utils_operator import fill_size_drop_down
from ..toolbox import get_context
from ..utils import (
    is_cycles,
    is_eevee_next)
from .. import reporting


UV_OPTIONS = [("UV", "UV", "UV"),
              ("MOSAIC", "Mosaic", "Poliigon Mosaic"),
              ("FLAT", "Flat", "Flat"),
              ("BOX", "Box", "Box"),
              ("SPHERE", "Sphere", "Sphere"),
              ("TUBE", "Tube", "Tube")]


def set_op_mat_disp_strength(ops, asset_name: str, mode_disp: str) -> None:
    if asset_name.startswith("Poliigon_"):
        ops.displacement = 0.2
    elif mode_disp == "MICRO":
        ops.displacement = 0.05
    else:
        ops.displacement = 0.0


class POLIIGON_OT_material(Operator):
    bl_idname = "poliigon.poliigon_material"
    bl_label = _t("Poliigon Material Import")
    bl_description = _t("Create Material")
    bl_options = {"GRAB_CURSOR", "BLOCKING", "REGISTER", "INTERNAL", "UNDO"}

    def _get_dispopts(self, context):
        options = [
            ("NORMAL", "Normal Only", "Use the Normal Map for surface details")
        ]

        if is_cycles() or is_eevee_next():
            # Only cycles and 4.2's eevee next support displacement
            options.append(
                ("BUMP",
                 "Bump Only",
                 ("Use the displacement map for surface details without "
                  "displacement"))
            )
            options.append(
                ("DISP",
                 "Displacement and Bump",
                 ("Use the displacement map for surface details and physical "
                  "displacement"))
            )

        if is_cycles():
            # While Eevee next in blender 4.2 could have the above options,
            # below is still only relevnat in cycles.
            options.append(
                ("MICRO",
                 "Adaptive Displacement Only",
                 ("Use the displacement map for physical displacement with "
                  "adaptive geometry subdivisions\n"
                  "Note: This has a high render performance cost!"))
            )
        return options

    def _fill_size_drop_down(self, context):
        return fill_size_drop_down(cTB, self.asset_id)

    def _update_displacement_options(self, context):
        # We can not access self.asset_data, here!
        asset_data = cTB._asset_index.get_asset(self.asset_id)
        if asset_data.local_convention == 1:
            self.displacement = 0.2
        else:
            self.displacement = 0.05

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    size: EnumProperty(
        name=_t("Texture"),  # noqa: F821
        items=_fill_size_drop_down,
        description=_t("Change size of assigned textures.")  # noqa: F722
    )
    mapping: EnumProperty(
        name=_t("Mapping"),  # noqa: F821
        items=UV_OPTIONS,
        default="UV"  # noqa: F821
    )
    scale: FloatProperty(
        name=_t("Scale"),  # noqa: F821
        default=1.0
    )
    if bpy.app.version >= (3, 0):
        mode_disp: EnumProperty(name="Displacement",  # noqa: F821
                                items=_get_dispopts,
                                default=0,  # noqa: F821
                                update=_update_displacement_options)
    else:
        mode_disp: EnumProperty(name="Displacement",  # noqa: F821
                                items=_get_dispopts,
                                update=_update_displacement_options)

    displacement: FloatProperty(
        name=_t("Displacement Strength"),  # noqa: F722
        default=0.0
    )
    use_16bit: BoolProperty(
        name=_t("16-Bit Textures (if any)"),  # noqa: F722
        default=False
    )
    reuse_material: BoolProperty(
        name=_t("Reuse Material"),  # noqa: F722
        default=True
    )
    keep_unused_tex_nodes: BoolProperty(
        name=_t("Keep Additional Texture Nodes"),  # noqa: F722
        default=True
    )
    # TODO(Andreas): Can do_rename be removed, seems not in use at all?
    do_rename: BoolProperty(options={"HIDDEN"})  # noqa: F821
    do_apply: BoolProperty(options={"HIDDEN"}, default=True)  # noqa: F821
    ignore_map_prefs: BoolProperty(options={"HIDDEN"}, default=False)  # noqa: F821

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)

        # Note: During property update handlers (like e.g.
        #       _update_displacement_options()) we can not rely on on these
        #       members to be defined!
        self.asset_data = None
        self.exec_count = 0

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def draw(self, context):
        if self.asset_data is None:
            self.asset_data = cTB._asset_index.get_asset(self.asset_id)

        is_backplate = self.asset_data.is_backplate()

        col = self.layout.column()
        col.prop(self, "size")
        row = col.row()
        row.prop(self, "mapping")
        row.enabled = not is_backplate
        if is_cycles() or is_eevee_next():
            row = col.row()
            row.prop(self, "mode_disp")
            row.enabled = not is_backplate
        if self.mode_disp != "NORMAL" and (is_cycles() or is_eevee_next()):
            row = col.row()
            row.prop(self, "displacement")
            row.enabled = not is_backplate
        row = col.row()
        row.prop(self, "scale")  # TODO(Andreas): implement for backplate?
        row.enabled = not is_backplate
        row = col.row()
        row.prop(self, "use_16bit")
        row.enabled = not is_backplate
        col.prop(self, "reuse_material")
        row = col.row()
        row.prop(self, "keep_unused_tex_nodes")
        row.enabled = not self.reuse_material

    def evaluate_displacement_method_property(self) -> None:
        """Tries to set dislacement method from prefs, if not set already."""

        if self.properties.is_property_set("mode_disp"):
            return

        try:
            self.mode_disp = cTB.prefs.mode_disp
        except TypeError:
            # Could be Eevee active while assigning a displacement value
            self.mode_disp = "NORMAL"
        except AttributeError as e:
            reporting.capture_exception(e)
            self.mode_disp = "NORMAL"

    def determine_objects_needing_subdiv(
            self, context) -> List[bpy.types.Object]:
        """Returns a list of selected objects, which still need a Subdivision
        modifier for microdisplacement.
        """

        if not is_cycles() or self.mode_disp != "MICRO":
            return []

        objs_selected = [_obj for _obj in context.selected_objects]
        objs_add_subdiv = [_obj
                           for _obj in objs_selected
                           if "Subdivision" not in _obj.modifiers]
        if bpy.app.version < (5, 0):
            # Blender 5.0 no longer has feature sets, adaptive is included
            bpy.context.scene.cycles.feature_set = "EXPERIMENTAL"
        return objs_add_subdiv

    def add_subdiv_to_objects(self, obj_list: List[bpy.types.Object]) -> None:
        """Adds a Subdivision modifier to all objects in list."""

        for _obj in obj_list:
            if bpy.app.version < (5, 0):
                # In blender 5.0, there's no special settings for this.
                _obj.cycles.use_adaptive_subdivision = True
            modifier = _obj.modifiers.new("Subdivision", "SUBSURF")
            if modifier is None:
                # TODO(Andreas): Would we want to report failure to create modifier?
                continue
            modifier.subdivision_type = "SIMPLE"
            modifier.levels = 0  # Don't do subdiv in viewport

    def check_material_reuse(self) -> bool:
        """Optionally re-uses an already imported identical material."""

        if not self.reuse_material:
            return False

        identical_mat = find_identical_material(
            self.asset_data,
            self.size,
            self.mapping,
            self.scale,
            self.displacement,
            self.use_16bit,
            self.mode_disp
        )

        if identical_mat is None:
            return False

        # Prevent duplicate materials from being created unintentionally
        # but we probably want to provide an option for that at some point.
        cTB.logger.debug("POLIIGON_OT_material Applying existing material: "
                         f"{identical_mat.name}")
        self.report({"WARNING"}, _t("Applying existing material"))

        result = bpy.ops.poliigon.poliigon_apply(
            "INVOKE_DEFAULT",
            asset_id=self.asset_id,
            name_material=identical_mat.name
        )
        if result == {"CANCELLED"}:
            self.report(
                {"WARNING"}, _t("Could not apply materials to selection"))
        else:
            self.signal_import()
        return True

    def signal_import(self) -> None:
        if self.exec_count == 0:
            cTB.signal_import_asset(asset_id=self.asset_id)
            cTB.set_first_local_asset()
        self.exec_count += 1

    @reporting.handle_operator()
    def execute(self, context):
        self.asset_data = cTB._asset_index.get_asset(self.asset_id)

        # TODO(Andreas): Can do_rename be removed, seems not in use at all?
        if self.do_rename:
            mat = bpy.data.materials[cTB.vActiveMat]
            cTB.vActiveMat = bpy.context.scene.vEditMatName
            mat.name = cTB.vActiveMat
            return {"FINISHED"}

        asset_type_data = self.asset_data.get_type_data()
        asset_name = self.asset_data.asset_name
        asset_type = self.asset_data.asset_type

        workflow = asset_type_data.get_workflow("METALNESS")
        self.size = asset_type_data.get_size(
            self.size,
            local_only=True,
            addon_convention=cTB.addon_convention,
            local_convention=self.asset_data.local_convention
        )

        self.evaluate_displacement_method_property()

        objs_add_disp = self.determine_objects_needing_subdiv(context)

        # TODO(Andreas): Not sure what this was supposed to be good for:
        # msg_error_local = None
        # msg_error_my_assets = None
        # if msg_error_local is not None:
        #     self.report({"ERROR"}, msg_error_local)
        #     return {'CANCELLED'}
        # if msg_error_my_assets is not None:
        #     cTB.print_debug_(
        #         0, "apply_mat_size_not_local", asset_name, self.size)
        #     self.report({"ERROR"}, msg_error_my_assets)
        #     reporting.capture_message("apply_mat_size_not_local", asset_name)
        #     return {"CANCELLED"}

        cTB.logger.debug(f"POLIIGON_OT_material Size: {self.size}")

        did_reuse = self.check_material_reuse()
        if did_reuse:
            self.signal_import()
            return {"FINISHED"}

        tex_maps = asset_type_data.get_maps(
            workflow=workflow,
            size=self.size,
            prefer_16_bit=self.use_16bit,
            variant=None)
        if len(tex_maps) == 0:
            self.report({"WARNING"}, _t("No Textures found."))
            reporting.capture_message("apply_mat_tex_not_found", asset_name)
            return {"CANCELLED"}

        if self.ignore_map_prefs:
            map_prefs = None
        else:
            map_prefs = cTB.user.map_preferences

        mat = cTB.mat_import.import_material(
            asset_data=self.asset_data,
            do_apply=False,
            workflow="METALNESS",
            size=self.size,
            lod="",
            projection=self.mapping,
            use_16bit=self.use_16bit,
            mode_disp=self.mode_disp,
            translate_x=0.0,
            translate_y=0.0,
            scale=self.scale,
            global_rotation=0.0,
            aspect_ratio=1.0,
            displacement=self.displacement,
            keep_unused_tex_nodes=self.keep_unused_tex_nodes,
            reuse_existing=False,  # we already checked for reusable mats before
            map_prefs=map_prefs
        )

        if mat is None:
            reporting.capture_message(
                "could_not_create_mat", asset_name, "error")
            self.report({"ERROR"}, _t("Material could not be created."))
            return {"CANCELLED"}

        self.add_subdiv_to_objects(objs_add_disp)

        cTB.f_GetSceneAssets()

        # TODO(Andreas): check what it is used for
        # TODO(Andreas): Even more strange, op.poliigon_active does the
        #                same again...
        # TODO(Andreas): Even more more strange, op.poliigon_apply then does
        #                this again and also calls op.poliigon_active, again?
        cTB.vActiveType = asset_type.name  # self.vType
        cTB.active_asset_id = self.asset_id
        cTB.vActiveMat = mat.name

        bpy.ops.poliigon.poliigon_active(
            mode="mat", asset_type=cTB.vActiveType, data=cTB.vActiveMat
        )

        self.signal_import()

        if not self.do_apply:
            return {"FINISHED"}

        rtn = bpy.ops.poliigon.poliigon_apply(
            "INVOKE_DEFAULT",
            asset_id=self.asset_id,
            name_material=mat.name
        )
        if rtn == {"CANCELLED"}:
            self.report(
                {"WARNING"}, _t("Could not apply materials to selection"))

        return {"FINISHED"}
