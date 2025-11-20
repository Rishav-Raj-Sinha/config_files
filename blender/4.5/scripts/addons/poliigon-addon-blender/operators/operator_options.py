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

import os
import re
import webbrowser

from bpy.types import Operator
from bpy.props import IntProperty, StringProperty

from ..modules.poliigon_core.assets import AssetType
from ..modules.poliigon_core.multilingual import _t
from ..toolbox import get_context
from ..utils import open_dir
from .. import reporting


class POLIIGON_OT_options(Operator):
    bl_idname = "poliigon.poliigon_asset_options"
    bl_label = ""
    bl_description = _t("Asset Options")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"REGISTER", "INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821
    mode: StringProperty(options={"HIDDEN"})  # noqa: F821
    asset_id: IntProperty(options={"HIDDEN"})  # noqa: F821

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

        asset_data = cTB._asset_index.get_asset(self.asset_id)
        asset_name = asset_data.asset_name
        asset_type_data = asset_data.get_type_data()
        dict_asset_files = {}
        asset_type_data.get_files(dict_asset_files)
        asset_files = list(dict_asset_files.keys())

        if self.mode == "dir":
            directories = sorted(
                list(set([os.path.dirname(_file)
                          for _file in asset_files]))
            )
            for idx_dir in range(len(directories)):
                if asset_name in directories[idx_dir]:
                    directories[idx_dir] = directories[idx_dir].split(
                        asset_name)[0] + asset_name
            directories = sorted(list(set(directories)))

            for _dir in directories:
                open_dir(_dir)

        elif self.mode == "link":
            asset_type = asset_data.asset_type
            url_name = asset_name
            url_name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", url_name)
            url_name = (
                (re.sub(r"(?<=[a-z])(?=[0-9])", " ", url_name))
                .lower()
                .replace(" ", "-")
            )
            if asset_type == AssetType.TEXTURE:
                url = f"https://www.poliigon.com/texture/{url_name}"
            elif asset_type == AssetType.MODEL:
                url = f"https://www.poliigon.com/model/{url_name}"
            webbrowser.open(url)

        return {"FINISHED"}
