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

from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_active(Operator):
    bl_idname = "poliigon.poliigon_active"
    bl_label = ""
    bl_description = _t("Set Active Asset")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_type: StringProperty(options={"HIDDEN"})  # noqa: F821
    data: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @reporting.handle_operator()
    def execute(self, context):
        global cTB

        if self.data == "":
            cTB.vActiveType = None
            cTB.vActiveAsset = None
            cTB.vActiveMat = None
            cTB.vActiveMode = None

        elif self.mode == "asset":
            cTB.vActiveType = self.asset_type
            cTB.vActiveAsset = self.data
            if cTB.vActiveAsset in cTB.imported_assets["Textures"].keys():
                cTB.vActiveMat = cTB.imported_assets["Textures"][cTB.vActiveAsset][0].name
                context.scene.vEditMatName = cTB.vActiveMat
            else:
                cTB.vActiveMat = None
            cTB.vActiveMode = "asset"
            cTB.settings["show_active"] = 1

        elif self.mode == "mat":
            # TODO(Andreas): This seems to be the only case used from this op.
            cTB.vActiveType = self.asset_type
            if "@" in self.data:
                cTB.vActiveAsset, cTB.vActiveMat = self.data.split("@")
            else:
                cTB.vActiveMat = self.data
            cTB.vActiveMode = "asset"

        elif self.mode == "mixer":
            cTB.vActiveType = self.asset_type
            cTB.vActiveAsset = self.data
            context.scene.vEditMatName = cTB.vActiveAsset
            cTB.vActiveMat = self.data
            cTB.vActiveMode = "mixer"
            cTB.settings["show_active"] = 1

        elif self.mode == "mix":
            cTB.vActiveMode = "mixer"
            cTB.vActiveMix = self.data

        elif self.mode == "mixmat":
            cTB.vActiveMode = "mixer"
            cTB.vActiveMixMat = self.data

        elif self.mode == "poliigon":
            cTB.vActiveMode = "poliigon"
            cTB.vActiveAsset = self.data

        elif self.mode == "settings":
            # f_Settings()
            return {"FINISHED"}

        cTB.f_GetActiveData()

        return {"FINISHED"}
