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

from typing import List, Tuple
import os
import re

from bpy.props import (IntProperty,
                       StringProperty)
from bpy.types import Operator

from ..modules.poliigon_core.assets import SIZES
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_load_asset_size_from_list(Operator):
    # NOTE: This operator is considered internal and therefore not translated

    bl_idname = "poliigon.load_asset_size_from_list"
    bl_label = "Import list of files as an asset"
    bl_description = "Import an asset from a list of files"
    bl_options = {'REGISTER', 'INTERNAL'}

    # Use negative asset IDs for, now,
    # caller to keep track to keep unique within session.
    asset_id: IntProperty(default=-1, options={'SKIP_SAVE'})  # noqa: F821
    asset_name: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_type: StringProperty(options={"HIDDEN"})  # noqa: F821
    file_list_json: StringProperty(options={"HIDDEN"})  # noqa: F821
    size: StringProperty(options={"HIDDEN"})  # noqa: F821
    lod: StringProperty(options={"HIDDEN"})  # noqa: F821
    convention: IntProperty(default=1, options={'SKIP_SAVE'})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    def _validate_properties(self) -> None:
        """Validates received parameters.

        Raise ValueError, if validation failed.
        """

        if self.asset_id >= 0:
            msg = f"Only negative asset IDs allowed, for now (not {self.asset_id})"
            self.report({"ERROR"}, msg)
            raise ValueError(msg)
        if len(self.asset_name) == 0:
            msg = "Please specify an asset name"
            self.report({"ERROR"}, msg)
            raise ValueError(msg)
        if self.asset_type not in ["HDRIS", "Models", "Textures"]:
            msg = (f"Unknown asset type: {self.asset_type}\n"
                   "Known types: HDRIS, Models, Textures")
            self.report({"ERROR"}, msg)
            raise ValueError(msg)
        if len(self.size) > 0:
            try:
                if self.size[-1] == "K":
                    int(self.size[:-1])
                else:
                    int(self.size)
            except ValueError:
                msg = (f"Unknown size string: '{self.size}'\n"
                       "Expected something like: '256', '2K' or '16K'")
                raise ValueError(msg)
        if len(self.lod) > 0 and not self.lod.startswith("LOD"):
            msg = (f"Unknown LOD string format: {self.lod}\n"
                   "Expected something like: 'LOD0'")
            self.report({"ERROR"}, msg)
            raise ValueError(msg)
        if self.convention < 0:
            msg = (f"Invalid asset convention: {self.convention}\n"
                   "Expected values: convention >= 0")
            self.report({"ERROR"}, msg)
            raise ValueError(msg)
        # TODO(Andreas): Any additional validation needed?
        #                E.g. test if file types in file_list_json actually
        #                match file tags?`Like an "xyz.fbx" for COL channel?

    def _derive_properties_from_files(
            self,
            tex_maps: List[str]
    ) -> Tuple[List[str], List[str], List[str]]:
        """Derives workflows, sizes and LODs from filenames."""

        workflows = []
        sizes = []
        lods = []
        for path in tex_maps:
            dir_parent = os.path.basename(os.path.dirname(path))
            filename = os.path.basename(path)
            filename_no_ext, _ = os.path.splitext(filename)
            filename_parts = filename_no_ext.split("_")
            for part in filename_parts:
                match_size = re.search(r"(\d+K)", part)
                match_lod = re.search(r"(LOD\d)", part)

                if part in ["METALNESS", "SPECULAR", "REGULAR"]:
                    workflows.append(part)
                elif match_size is not None:
                    sizes.append(part)
                elif match_lod is not None:
                    lods.append(part)
                elif dir_parent in SIZES:
                    sizes.append(dir_parent)

        workflows = list(set(workflows))
        sizes = list(set(sizes))
        lods = list(set(lods))

        return workflows, sizes, lods

    @reporting.handle_operator()
    def execute(self, context):
        # Deliberately not catching ValueError, here.
        # Scripts using this operator are supposed to fail.
        self._validate_properties()

        cTB._asset_index.load_asset_from_list(
            self.asset_id,
            self.asset_name,
            self.asset_type,
            self.size,
            self.lod,
            "METALNESS",
            self.file_list_json,
            convention=self.convention,
            # "my_assets",
            # -1,
            # 1000000
        )
        return {"FINISHED"}
