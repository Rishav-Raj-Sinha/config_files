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

from bpy.types import Operator
from bpy.props import StringProperty
import bpy.utils.previews
import bmesh

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_select(Operator):
    bl_idname = "poliigon.poliigon_select"
    bl_label = ""
    bl_description = _t("Select Model")
    bl_options = {"REGISTER", "INTERNAL", "UNDO"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    data: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def select_faces(self, context) -> None:
        """Selects all faces which have imported material assigned."""

        self.deselect(context)

        obj = context.active_object
        idx_mat = int(self.data)
        # #### vMat = obj.material_slots[i].material

        bpy.ops.object.mode_set(mode="EDIT")

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        for _face in bm.faces:
            _face.select = 0

        obj.active_material_index = idx_mat
        bpy.ops.object.material_slot_select()

    def select_object(self, context) -> None:
        """Selects an object by name."""

        self.deselect(context)
        obj = context.scene.objects[self.data]
        try:
            obj.select_set(True)
        except RuntimeError:
            pass  # Might not be in view layer

    def select_sets(self, context) -> None:
        """TODO(Andreas): Really not sure what this is.
        What does it do? And for what purpose?
        """

        parts_data = self.data.split("@")
        self.deselect(context)
        try:
            context.scene.objects[parts_data[1]].select_set(1)
        except RuntimeError:
            pass  # Might not be in view layer

    def select_model(self, context) -> None:
        """Selects all objects belonging to an imported Model asset."""

        if not context.mode == "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        self.deselect(context)
        objs_to_select = []

        key = self.data
        for obj in context.scene.objects:
            split = obj.name.rsplit("_")[0]

            # For instance collections
            if split == key and obj.instance_type == "COLLECTION":
                objs_to_select.append(obj)
            # For empty parents
            ref_key = key + "_empty"
            if obj.name.lower().startswith(ref_key.lower()):
                objs_to_select.append(obj)
            # For the objects within the empty tree
            if key in obj.poliigon.split(";")[-1]:
                objs_to_select.append(obj)

        for _obj in objs_to_select:
            try:
                _obj.select_set(True)
            except RuntimeError:
                pass  # Might not be in view layer

    def select_objects_by_texture(self, context) -> None:
        """Selects all objects which have a given Texture asset assigned."""

        mat = bpy.data.materials[self.data]
        objs = [_obj
                for _obj in context.scene.objects
                if _obj.active_material == mat]

        if len(objs) == 1:
            self.deselect(context)
            try:
                objs[0].select_set(True)
            except RuntimeError:
                pass  # Might not be in view layer

        else:
            # TODO(Andreas): Looks like this branch is never used.
            #                This operator seems to be only used in "model"
            #                mode.
            #                For sure the name access on our object list is a
            #                bug.
            reporting.capture_message(
                "reached_legacy_f_DropdownSelect", objs.name)
            return {"FINISHED"}

    @reporting.handle_operator()
    def execute(self, context):
        # TODO(Andreas): addon seems to use "mode == model", only
        if self.mode == "faces":
            self.select_faces(context)
        elif self.mode == "object":
            self.select_object(context)
        # TODO(Andreas): Seems odd to have this one data comparison in between
        #                the mode ones...
        elif "@" in self.data:
            self.select_sets(context)
        elif self.mode == "model":
            self.select_model(context)
        elif self.mode == "mat_objs":
            self.select_objects_by_texture(context)

        return {"FINISHED"}

    def deselect(self, context):
        """Deselects objects in a lower api, faster, context-invaraint way."""
        for obj in context.scene.collection.all_objects:
            try:
                obj.select_set(False)
            except RuntimeError:
                pass  # Might not be in view layer
