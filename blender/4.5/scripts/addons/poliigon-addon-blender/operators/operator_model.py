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

from typing import Dict, List, Tuple
import os

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)

from ..modules.poliigon_core.assets import (
    AssetData,
    LODS,
    MAP_EXT_LOWER,
    ModelType,
    VARIANTS)
from ..modules.poliigon_core.multilingual import _t
from ..material_import_utils import replace_tex_size
from .utils_operator import fill_size_drop_down
from ..toolbox import get_context
from ..utils import (
    construct_model_name,
    f_Ex,
    f_FExt,
    f_FName)
from .. import reporting


LOD_DESCS = {
    "NONE": _t("med. poly"),
    "LOD0": _t("high poly"),
    "LOD1": _t("med. poly"),
    "LOD2": _t("low poly"),
    "LOD3": _t("lower poly"),
    "LOD4": _t("min. poly"),
}
LOD_NAME = "{0} ({1})"
LOD_DESCRIPTION_FBX = _t("Import the {0} level of detail (LOD) FBX file")

PROP_LIBRARY_LINKED = "poliigon_linked"


class POLIIGON_OT_model(Operator):
    bl_idname = "poliigon.poliigon_model"
    bl_label = _t("Import model")
    bl_description = _t("Import Model")
    bl_options = {"REGISTER", "INTERNAL", "UNDO"}

    def _fill_size_drop_down(self, context):
        return fill_size_drop_down(cTB, self.asset_id)

    def _fill_lod_drop_down(self, context):
        # Get list of locally available sizes
        local_lods = []

        local_lods = cTB._asset_index.check_asset_local_lods(
            self.asset_id, ModelType.FBX)

        items_lod = [
            ("NONE",
             LOD_NAME.format("NONE", LOD_DESCS["NONE"]),
             _t("Import the med. poly level of detail (LOD) .blend file"))
        ]
        for _lod, is_local in local_lods.items():
            if not is_local:
                continue
            # Tuple: (id, name, description[, icon, [enum value]])
            lod_tuple = (_lod,
                         LOD_NAME.format(_lod, LOD_DESCS[_lod]),
                         LOD_DESCRIPTION_FBX.format(LOD_DESCS[_lod]))
            # Note: Usually we rather do a list(set()) afterwards,
            #       but in this case order is important!
            if lod_tuple not in items_lod:
                items_lod.append(lod_tuple)

        return items_lod

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821
    do_use_collection: BoolProperty(
        name=_t("Import as collection"),  # noqa: F722
        description=_t("Instance model from a reusable collection"),  # noqa: F722
        default=False
    )
    do_reuse_materials: BoolProperty(
        name=_t("Reuse materials"),  # noqa: F722
        description=_t("Reuse already imported materials to avoid duplicates"),  # noqa: F722
        default=False)
    do_link_blend: BoolProperty(
        name=_t("Link .blend file"),  # noqa: F722
        description=_t("Link the .blend file instead of appending"),  # noqa: F722
        default=False)
    size: EnumProperty(
        name=_t("Texture"),  # noqa: F821
        items=_fill_size_drop_down,
        description=_t("Change size of assigned textures."))  # noqa: F722
    lod: EnumProperty(
        name=_t("LOD"),  # noqa: F821
        items=_fill_lod_drop_down,
        description=_t("Change LOD of the Model."))  # noqa: F722

    def __init__(self, *args, **kwargs):
        """Runs once per operator call before drawing occurs."""
        super().__init__(*args, **kwargs)

        # Infer the default value on each press from the cached session
        # setting, which will be updated by redo last but not saved to prefs.
        self.do_link_blend = cTB.link_blend_session

        self.blend_exists = False
        self.lod_import = False

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
        prefer_blend = cTB.settings["download_prefer_blend"] and self.blend_exists
        if not self.blend_exists:
            label = _t("No local .blend file :")
            row_link_enabled = False
            row_sizes_enabled = True
        elif not prefer_blend:
            label = _t("Enable preference 'Download + Import .blend' :")
            row_link_enabled = False
            row_sizes_enabled = True
        elif self.lod_import:
            label = _t("Set 'LOD' to 'NONE' to load .blend :")
            row_link_enabled = False
            row_sizes_enabled = True
        else:
            label = None
            row_link_enabled = True
            row_sizes_enabled = not self.do_link_blend

        row = self.layout.row()
        row.prop(self, "lod")
        row.enabled = True

        row = self.layout.row()
        row.prop(self, "size")
        row.enabled = row_sizes_enabled

        self.layout.prop(self, "do_use_collection")

        row = self.layout.row()
        row.prop(self, "do_reuse_materials")
        row.enabled = not (row_link_enabled and self.do_link_blend)

        if label is not None:
            self.layout.label(text=label)

        row = self.layout.row()
        row.prop(self, "do_link_blend")
        row.enabled = row_link_enabled

    @reporting.handle_operator()
    def execute(self, context):
        """Runs at least once before first draw call occurs."""

        self.asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_name = self.asset_data.asset_name

        # Save any updated preference (to link or not), if changed via the
        # redo last menu (without changing the saved preferences value).
        cTB.link_blend_session = self.do_link_blend

        project_files, textures, size, lod = self.get_model_data(
            self.asset_data)

        asset_name = construct_model_name(asset_name, size, lod)
        did_fresh_import = False
        inst = None
        new_objs = []

        # Import the model.
        blend_import = False
        coll_exists = bpy.data.collections.get(asset_name) is not None
        if self.do_use_collection is False or not coll_exists:
            ok, new_objs, blend_import, fbx_fail = self.run_fresh_import(
                context,
                project_files,
                textures,
                size,
                lod)
            if fbx_fail:
                return {'CANCELLED'}
            did_fresh_import = True

        # If imported, perform these steps regardless of collection or not.
        if did_fresh_import:
            empty = self.setup_empty_parent(context, new_objs, asset_name)
            if blend_import and not self.do_use_collection:
                empty.location = bpy.context.scene.cursor.location
        else:
            empty = None

        if self.do_use_collection:
            # Move the objects into a subcollection, and place in scene.
            if did_fresh_import:
                # Always create a new collection if did a fresh import.
                cache_coll = bpy.data.collections.new(asset_name)
                # Ensure all objects are only part of this new collection.
                for _obj in [empty] + new_objs:
                    for _collection in _obj.users_collection:
                        _collection.objects.unlink(_obj)
                    cache_coll.objects.link(_obj)

                # Now add the cache collection to the layer, but unchecked.
                layer_coll = context.view_layer.active_layer_collection
                layer_coll.collection.children.link(cache_coll)
                for _child in layer_coll.children:
                    if _child.collection == cache_coll:
                        _child.exclude = True
            else:
                cache_coll = bpy.data.collections.get(asset_name)

            if cache_coll is None:
                err = _t("Failed to get new collection to instance")
                self.report({"ERROR"}, err)
                return {"CANCELLED"}

            # Now finally add the instance to the scene.
            inst = self.create_instance(context, cache_coll, size, lod)
        else:
            # Make sure the objects imported are all part of the same coll.
            self.append_cleanup(context, empty)

        # Final notifications and reporting.
        cTB.f_GetSceneAssets()

        if blend_import:
            # Fix import info message containing LOD info
            asset_name = construct_model_name(asset_name, size, "")

        if did_fresh_import is True:
            fmt = "blend" if blend_import else "FBX"
            self.report(
                {"INFO"},
                _t("Model Imported ({0}) : {1}").format(fmt, asset_name))
        elif self.do_use_collection and inst is not None:
            self.report(
                {"INFO"}, _t("Instance created : ").format(inst.name))
        else:
            err = _t(
                "Failed to import model correctly: {0}").format(asset_name)
            self.report({"ERROR"}, err)
            err = f"Failed to import model correctly: {asset_name}"
            reporting.capture_message("import-model-failed", err, "error")
            return {"CANCELLED"}

        if self.exec_count == 0:
            cTB.signal_import_asset(asset_id=self.asset_id)
            cTB.set_first_local_asset()
        self.exec_count += 1
        return {"FINISHED"}

    def _filter_lod_fbxs(self,
                         file_list: List[str]
                         ) -> List[str]:
        """Returns a list with all FBX files with LOD tag in filename"""

        all_lod_fbxs = []
        for asset_path in file_list:
            if f_FExt(asset_path) != ".fbx":
                continue
            filename_parts = f_FName(asset_path).split("_")
            for lod_level in LODS:
                if lod_level not in filename_parts:
                    continue
                all_lod_fbxs.append(asset_path)
                break
        return all_lod_fbxs

    def get_model_data(
        self,
        asset_data: AssetData
    ) -> Tuple[List[str], List[str], str, str]:
        """Returns details for Model import from a Model asset."""

        asset_type_data = asset_data.get_type_data()

        # Get the intended material size and LOD import to use.
        size_desired = self.size if self.size is not None else cTB.settings["mres"]
        size = asset_type_data.get_size(
            size_desired,
            local_only=True,
            addon_convention=cTB._asset_index.addon_convention,
            local_convention=asset_data.get_convention(local=True))

        prefer_blend = cTB.settings["download_prefer_blend"]

        lod = self.lod
        if lod == "NONE":
            if not prefer_blend:
                lod = "LOD1"
            else:
                lod = cTB.settings["lod"]
        lod = asset_type_data.get_lod(lod)
        if lod == "NONE":
            lod = None

        files = {}
        asset_type_data.get_files(files)
        files = list(files.keys())
        all_lod_fbxs = self._filter_lod_fbxs(files)

        files_lod_fbx = [
            _file for _file in all_lod_fbxs
            if f_FExt(_file) == ".fbx" and str(lod) in f_FName(_file).split("_")
        ]
        # Most likely redundant, but rather safe than sorry
        files_lod_fbx = list(set(files_lod_fbx))

        files_fbx = []
        files_blend = []
        for _file in files:
            filename_ext = f_FExt(_file)
            is_fbx = filename_ext == ".fbx"
            is_blend = filename_ext == ".blend" and "_LIB.blend" not in _file

            if not is_fbx and not is_blend:
                continue

            if is_fbx and lod is not None and len(files_lod_fbx):
                if _file not in files_lod_fbx:
                    continue

            if is_fbx and lod is None and _file in all_lod_fbxs:
                continue

            if is_fbx:
                files_fbx.append(_file)
            elif is_blend:
                files_blend.append(_file)

            cTB.logger.debug("POLIIGON_OT_model get_model_data "
                             f"{os.path.basename(_file)}")

        self.blend_exists = len(files_blend) > 0
        self.lod_import = lod is not None and self.lod != "NONE"

        if prefer_blend and self.blend_exists and not self.lod_import:
            files_project = files_blend
        elif not prefer_blend and not files_fbx and self.blend_exists:
            # Settings specify to import fbx files, but only blend exists.
            # Needed for asset browser imports and right-click
            # TODO(Patrick): Migrate to using a use_blend operator arg, so it
            # can also be a backdoor option.
            files_project = files_blend
        else:
            files_project = files_fbx

        files_tex = []
        for _file in files:
            if f_FExt(_file) not in MAP_EXT_LOWER:
                continue

            if size not in f_FName(_file).split("_"):
                continue

            if any(
                _lod in f_FName(_file).split("_") for _lod in LODS
            ) and lod not in f_FName(_file).split("_"):
                continue

            files_tex.append(_file)

        return files_project, files_tex, size, lod

    def _load_blend(self, path_proj: str) -> List[bpy.types.Object]:
        """Loads all objects from a .blend file."""

        path_proj_norm = os.path.normpath(path_proj)
        with bpy.data.libraries.load(path_proj_norm,
                                     link=self.do_link_blend
                                     ) as (data_from,
                                           data_to):
            data_to.objects = data_from.objects
        return data_to.objects

    def _cut_identity_counter(self, s: str) -> str:
        """Reduces strings like 'walter.042' to 'walter'"""

        splits = s.rsplit(".", maxsplit=1)
        if len(splits) > 1 and splits[1].isdecimal():
            s = splits[0]
        return s

    def _reuse_materials(
            self, imported_objs: List, imported_mats: List) -> None:
        """Re-uses previously imported materials after a .blend import"""

        if not self.do_reuse_materials or self.do_link_blend:
            return

        # Mark all materials from this import
        PROP_FRESH_IMPORT = "poliigon_fresh_import"
        for mat in imported_mats:
            mat[PROP_FRESH_IMPORT] = True
        # Find any previously imported materials with same name
        # and make the objects use those
        mats_remap = []  # list of tuples (from_mat, to_mat)
        for obj in imported_objs:
            mat_on_obj = obj.active_material
            if mat_on_obj is None:
                continue
            materials = reversed(sorted(list(bpy.data.materials.keys())))
            for name_mat in materials:
                # Unfortunately we seem to have little control,
                # where and when Blender adds counter suffixes for
                # identically named materials.
                # Therefore we compare names without any counter suffix.
                name_on_obj_cmp = self._cut_identity_counter(mat_on_obj.name)
                name_mat_cmp = self._cut_identity_counter(name_mat)
                if name_on_obj_cmp != name_mat_cmp:
                    continue
                mat_reuse = bpy.data.materials[name_mat]
                is_fresh = mat_reuse.get(PROP_FRESH_IMPORT, False)
                if is_fresh:
                    continue
                if (mat_on_obj, mat_reuse) not in mats_remap:
                    mats_remap.append((mat_on_obj, mat_reuse))
                    break
        # Remove previously added marker
        for mat in imported_mats:
            if PROP_FRESH_IMPORT in mat.keys():
                del mat[PROP_FRESH_IMPORT]
        # Finally remap the materials and remove those freshly imported ones
        did_send_sentry = False
        for from_mat, to_mat in mats_remap:
            from_mat.user_remap(to_mat)
            from_mat.user_clear()
            if from_mat in imported_mats:
                imported_mats.remove(from_mat)
            if from_mat.users != 0 and not did_send_sentry:
                msg = ("User count not zero on material replaced by reuse: "
                       f"Asset: {self.asset_id}, Material: {from_mat.name}")
                reporting.capture_message(
                    "import_model_mat_reuse_user_count",
                    msg,
                    "info")
                did_send_sentry = True
                continue
            try:
                bpy.data.materials.remove(from_mat)
            except Exception as e:
                reporting.capture_exception(e)
                self.report({"WARNING"},
                            _t("Failed to remove material after reuse."))

    # TODO(Andreas): replace usage with AssetIndex/AssetData alternative
    @staticmethod
    def f_GetVar(name: str) -> str:
        for _variant in VARIANTS:
            if _variant in name:
                return _variant
        return None

    def _run_fresh_import_blend(
        self,
        context,
        path_proj: str,
        filename_base: str,
        size: str
    ) -> None:
        """Imports from blend files."""

        cTB.logger.debug("POLIIGON_OT_model BLEND IMPORT")
        filename = filename_base + ".blend"

        if self.do_link_blend and filename in bpy.data.libraries.keys():
            lib = bpy.data.libraries[filename]
            if lib[PROP_LIBRARY_LINKED]:
                linked_objs = []
                for obj in bpy.data.objects:
                    if obj.library == lib:
                        linked_objs.append(obj)

                imported_objs = []
                for obj in linked_objs:
                    imported_objs.append(obj.copy())
            else:
                imported_objs = self._load_blend(path_proj)
        else:
            imported_objs = self._load_blend(path_proj)

            if filename in bpy.data.libraries.keys():
                lib = bpy.data.libraries[filename]
                lib[PROP_LIBRARY_LINKED] = self.do_link_blend

        for obj in context.view_layer.objects:
            obj.select_set(False)
        layer = context.view_layer.active_layer_collection
        imported_mats = []
        for obj in imported_objs:
            if obj is None:
                continue
            obj_copy = obj.copy()
            layer.collection.objects.link(obj_copy)
            obj_copy.select_set(True)
            if obj_copy.active_material is None:
                pass
            elif obj_copy.active_material not in imported_mats:
                imported_mats.append(obj_copy.active_material)

        files_dict = {}
        asset_type_data = self.asset_data.get_type_data()
        asset_type_data.get_files(files_dict)
        asset_files = list(files_dict.keys())
        replace_tex_size(
            imported_mats,
            asset_files,
            size,
            self.do_link_blend
        )
        self._reuse_materials(imported_objs, imported_mats)

    def _run_fresh_import_fbx(self, path_proj: str) -> bool:
        """Imports from FBX files."""

        cTB.logger.debug("POLIIGON_OT_model FBX IMPORT")
        if "fbx" not in dir(bpy.ops.import_scene):
            try:
                bpy.ops.preferences.addon_enable(module="io_scene_fbx")
                self.report(
                    {"INFO"},
                    _t("FBX importer addon enabled for import")
                )
            except RuntimeError:
                self.report(
                    {"ERROR"},
                    _t("Built-in FBX importer could not be found, "
                       "check Blender install")
                )
                return False
        try:
            # Note on use_custom_normals parameter:
            # It always defaulted to True. But in Blender 4.0+
            # it started to cause issues.
            # Mateusz sync'ed with Stephen and recommended to turn it
            # off regardless of Blender version.
            bpy.ops.import_scene.fbx(filepath=path_proj,
                                     axis_up="-Z",
                                     use_custom_normals=False)
        except Exception as e:
            self.report({"ERROR"},
                        _t("FBX importer exception:") + str(e))
            return False

        return True

    def _run_fresh_import_create_materials(
        self,
        *,
        path_proj: str,
        filename_base: str,
        imported_proj: List[str],
        files_tex: List[str],
        objs_from_file: List[bpy.types.Object],
        dict_mats_imported: Dict[str, bpy.types.Material],
        size: str,
        lod: str
    ) -> None:
        """Creates materials after successful FBX import."""

        asset_name = self.asset_data.asset_name

        for _mesh in objs_from_file:
            if _mesh.type == "EMPTY":
                continue

            name_mat_imported = ""
            if _mesh.active_material is not None:
                name_mat_imported = _mesh.active_material.name

            # Note: Of course the check if "_mat" is contained could be
            #       written in one line. But I wouldn't consider "_mat"
            #       unlikely in arbitrary filenames. Thus I chose to
            #       explicitly compare for "_mat" at the end and
            #       additionally check if "_mat_" is contained, in order
            #       to at least reduce the chance of false positives a bit.
            name_mat_imported_lower = name_mat_imported.lower()
            name_tex_remastered = ""
            name_tex_on_obj = ""
            ends_remastered = name_mat_imported_lower.endswith("_mat")
            contains_remastered = "_mat_" in name_mat_imported_lower
            if ends_remastered or contains_remastered:
                pos_remastered = name_mat_imported_lower.rfind("_mat", 1)
                name_tex_remastered = name_mat_imported[:pos_remastered]
            else:
                name_tex_on_obj = name_mat_imported.split("_")[0]

            name_mesh_base = _mesh.name.split(".")[0].split("_")[0]

            variant_mesh = self.f_GetVar(_mesh.name)
            variant_name = variant_mesh
            if variant_mesh is None:
                # This is a fallback for models,
                # where the object name does not contain a variant indicator.
                # As None is covered explicitly in the loop below,
                # this should do no harm.
                variant_mesh = "VAR1"
                variant_name = ""

            name_mat = name_mesh_base
            files_tex_filtered = []
            if len(name_tex_remastered) > 0:
                # Remastered textures
                files_tex_filtered = [
                    _file
                    for _file in files_tex
                    if os.path.basename(_file).startswith(
                        name_tex_remastered)
                ]
                name_mat = name_mat_imported
            else:
                for vCheck in [name_mesh_base,
                               filename_base.split("_")[0],
                               asset_name,
                               name_tex_on_obj]:
                    files_tex_filtered = [
                        _file
                        for _file in files_tex
                        if os.path.basename(_file).startswith(vCheck)
                        if self.f_GetVar(f_FName(_file)) in [None,
                                                             variant_mesh]
                    ]
                    name_mat = vCheck
                    if len(files_tex_filtered) > 0:
                        break

            if len(files_tex_filtered) == 0:
                err = f"No Textures found for: {self.asset_id} {_mesh.name}"
                reporting.capture_message(
                    "model_texture_missing", err, "info")
                continue

            name_mat += f"_{size}"

            if size not in name_mat:
                name_mat += f"_{size}"

            if variant_name != "":
                name_mat += f"_{variant_name}"

            # TODO(Andreas): Not sure, why these lines are commented out.
            #                Looks reasonable to me.
            # if name_mat in bpy.data.materials and self.do_reuse_materials:
            #     mat = bpy.data.materials[name_mat]
            # el
            # TODO(Andreas): Not sure, this should also be depending on
            #                self.do_reuse_materials?
            if name_mat in dict_mats_imported.keys():
                # Already built in previous iteration
                mat = dict_mats_imported[name_mat]
            else:
                mat = cTB.mat_import.import_material(
                    asset_data=self.asset_data,
                    do_apply=False,
                    workflow="METALNESS",
                    size=size,
                    size_bg=None,
                    lod=lod,
                    variant=variant_name if variant_name != "" else None,
                    name_material=name_mat,
                    name_mesh=name_mesh_base,
                    ref_objs=None,
                    projection="UV",
                    use_16bit=True,
                    mode_disp="NORMAL",  # We never want model dispalcement
                    translate_x=0.0,
                    translate_y=0.0,
                    scale=1.0,
                    global_rotation=0.0,
                    aspect_ratio=1.0,
                    displacement=0.0,
                    keep_unused_tex_nodes=False,
                    reuse_existing=self.do_reuse_materials
                )
            if mat is None:
                msg = f"{self.asset_id}: Failed to build matrial: {name_mat}"
                reporting.capture_message(
                    "could_not_create_fbx_mat", msg, "error")
                self.report(
                    {"ERROR"}, _t("Material could not be created."))
                imported_proj.remove(path_proj)
                break

            dict_mats_imported[name_mat] = mat

            # This sequence is important!
            # 1) Setting the material slot to None
            # 2) Changing the link mode
            # 3) Assigning our generated material
            # Any other order of these statements will get us into trouble
            # one way or another.
            _mesh.active_material = None
            if len(_mesh.material_slots) > 0:
                _mesh.material_slots[0].link = "OBJECT"
            _mesh.active_material = mat

            if variant_mesh is not None:
                if len(_mesh.material_slots) == 0:
                    _mesh.data.materials.append(mat)
                else:
                    _mesh.material_slots[0].link = "OBJECT"
                    _mesh.material_slots[0].material = mat
                _mesh.material_slots[0].link = "OBJECT"

            # Ensure we can identify the mesh & LOD even on name change.
            # TODO(Andreas): Remove old properties?
            _mesh.poliigon = f"Models;{asset_name}"
            if lod is not None:
                _mesh.poliigon_lod = lod
            self.set_poliigon_props_model(_mesh, lod)

            # Finally try to remove the originally imported materials
            if name_mat_imported not in bpy.data.materials:
                continue
            mat_imported = bpy.data.materials[name_mat_imported]
            if mat_imported.users == 0:
                mat_imported.user_clear()
                bpy.data.materials.remove(mat_imported)

    def run_fresh_import(self,
                         context,
                         project_files: List[str],
                         files_tex: List[str],
                         size: str,
                         lod: str
                         ) -> Tuple[bool,
                                    List[bpy.types.Object],
                                    bool,
                                    bool]:
        """Performs a fresh import of the whole model.

        There can be multiple FBX models, therefore we want to import all of
        them and verify each one was properly imported.

        Return values:
        Tuple[0] - True, if all FBX files have been imported successfully
        Tuple[1] - List of all imported mesh objects
        Tuple[2] - True, if it was a .blend import instead of an FBX import
        Tuple[3] - True, if an error occurred during FBX loading
        """

        asset_name = self.asset_data.asset_name

        meshes_all = []
        dict_mats_imported = {}
        imported_proj = []
        blend_import = False
        for path_proj in project_files:
            filename_base = f_FName(path_proj)

            if not f_Ex(path_proj):
                err = _t("Couldn't load project file: {0} {1}").format(
                    asset_name, path_proj)
                self.report({"ERROR"}, err)
                err = ("Couldn't load project file: "
                       f"{self.asset_id} {path_proj}")
                reporting.capture_message("model_fbx_missing", err, "info")
                continue

            list_objs_before = list(context.scene.objects)

            ext_proj = f_FExt(path_proj)
            if ext_proj == ".blend":
                self._run_fresh_import_blend(
                    context, path_proj, filename_base, size)
                blend_import = True
            else:
                import_ok = self._run_fresh_import_fbx(path_proj)
                if not import_ok:
                    did_full_import = False
                    meshes_all = []
                    blend_import = False
                    fbx_error = True
                    return (did_full_import,
                            meshes_all,
                            blend_import,
                            fbx_error)

            imported_proj.append(path_proj)
            objs_from_file = [_obj for _obj in list(context.scene.objects)
                              if _obj not in list_objs_before]

            meshes_all += objs_from_file

            if ext_proj == ".blend":
                for _mesh in objs_from_file:
                    # Ensure we can identify the mesh & LOD even on name change
                    # TODO(Andreas): Remove old properties?
                    _mesh.poliigon = f"Models;{asset_name}"
                    if lod is not None:
                        _mesh.poliigon_lod = lod
                    self.set_poliigon_props_model(_mesh, lod)
                continue

            self._run_fresh_import_create_materials(
                path_proj=path_proj,
                filename_base=filename_base,
                imported_proj=imported_proj,
                files_tex=files_tex,
                objs_from_file=objs_from_file,
                dict_mats_imported=dict_mats_imported,
                size=size,
                lod=lod)

        # There could have been multiple FBXs, consider fully imported
        # for user-popup reporting if all FBX files imported.
        did_full_import = len(imported_proj) == len(project_files)

        return did_full_import, meshes_all, blend_import, False

    def set_poliigon_props_model(
            self, obj: bpy.types.Object, lod: str) -> None:
        """Sets Poliigon properties on an imported object."""

        obj.poliigon_props.asset_id = self.asset_data.asset_id
        obj.poliigon_props.asset_name = self.asset_data.asset_name
        obj.poliigon_props.asset_type = self.asset_data.asset_type.name
        obj.poliigon_props.size = self.size
        if lod is not None:
            obj.poliigon_props.lod = lod
        obj.poliigon_props.use_collection = self.do_use_collection
        obj.poliigon_props.link_blend = self.do_link_blend

    def object_has_children(self, obj_parent: bpy.types.Object) -> bool:
        """Returns True, if obj_parent has children."""

        for _obj in bpy.data.objects:
            if _obj.parent == obj_parent:
                return True
        return False

    def setup_empty_parent(self,
                           context,
                           new_meshes: List[bpy.types.Object],
                           asset_name: str
                           ) -> bpy.types.Object:
        """Parents newly imported objects to a central empty object."""

        radius = 0
        for _mesh in new_meshes:
            dimensions = _mesh.dimensions
            if dimensions.x > radius:
                radius = dimensions.x
            if dimensions.y > radius:
                radius = dimensions.y

        empty = bpy.data.objects.new(
            name=f"{asset_name}_Empty", object_data=None)
        if self.do_use_collection:
            empty.empty_display_size = 0.01
        else:
            empty.empty_display_size = radius * 0.5

        layer = context.view_layer.active_layer_collection
        layer.collection.objects.link(empty)

        for _mesh in new_meshes.copy():
            if _mesh.type == "EMPTY" and not self.object_has_children(_mesh):
                bpy.data.objects.remove(_mesh, do_unlink=True)
                new_meshes.remove(_mesh)
                continue
            _mesh.parent = empty

        return empty

    def create_instance(
            self, context, coll, size: str, lod: str) -> bpy.types.Object:
        """Creates an instance of an existing collection int he active view."""

        asset_name = self.asset_data.asset_name

        inst_name = construct_model_name(asset_name, size, lod) + "_Instance"
        inst = bpy.data.objects.new(name=inst_name, object_data=None)
        inst.instance_collection = coll
        inst.instance_type = "COLLECTION"
        layer_coll = context.view_layer.active_layer_collection
        layer_coll.collection.objects.link(inst)
        inst.location = context.scene.cursor.location
        inst.empty_display_size = 0.01

        # Set selection and active object.
        for _obj in context.scene.collection.all_objects:
            _obj.select_set(False)
        inst.select_set(True)
        context.view_layer.objects.active = inst
        return inst

    def append_cleanup(self, context, root_empty: bpy.types.Object) -> None:
        """Performs selection and placement cleanup after an import/append."""

        if root_empty is None:
            cTB.logger.error(
                "root_empty was not a valid object, exiting cleanup")
            return

        # Set empty location
        root_empty.location = context.scene.cursor.location

        # Deselect all others in scene (faster than using operator call).
        for _obj in context.scene.collection.all_objects:
            _obj.select_set(False)

        # Make empty active and select it + children.
        root_empty.select_set(True)
        context.view_layer.objects.active = root_empty
        for _obj in root_empty.children:
            _obj.select_set(True)
