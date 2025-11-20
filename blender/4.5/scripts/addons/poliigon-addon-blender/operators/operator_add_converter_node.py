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

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from ..modules.poliigon_core.multilingual import _t
from ..material_import_utils import load_poliigon_node_group
from ..toolbox import get_context
from .. import reporting


# These need to be global to work in _fill_node_drop_down()
ENUM29 = (
    ("Poliigon_Mixer",
     _t("Principled mixer"),
     _t("Principled mixer node")),
    ("Mosaic_UV_Mapping",
     _t("Mosaic mapping"),
     _t("Poliigon Mosaic mapping node")),
)
ENUM28 = (
    ("Poliigon_Mixer",
     _t("Principled mixer"),
     _t("Principled mixer node")),
)

# Needs to be global,
# as member variable can not be accessed in "items" function of EnumProperty
view_screen_tracked_nodes = False


class POLIIGON_OT_add_converter_node(Operator):
    bl_idname = "poliigon.add_converter_node"
    bl_label = _t("Converter node group")
    bl_description = _t("Adds a material converter node group")
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    def _fill_node_drop_down(self, context):
        """Returns list of available nodes as EnumPropertyItems.
        While the enums are actually static, this function serves as a
        "draw detection" to track view screen.
        """

        # Called during class construction, we can not access a
        # member variable here
        global view_screen_tracked_nodes

        if not view_screen_tracked_nodes:
            cTB.signal_view_screen("blend_node_add")
            view_screen_tracked_nodes = True

        if bpy.app.version >= (2, 90):
            return ENUM29
        else:
            return ENUM28

    node_type: EnumProperty(items=_fill_node_drop_down)

    @reporting.handle_operator(silent=True)
    def execute(self, context):
        if not self.node_type:
            self.report(
                {"Error"}, _t("No node_type specified to add"))
            return {'CANCELLED'}

        if not context.material:
            self.report(
                {"ERROR"}, _t("No active material selected to add nodegroup"))
            return {"CANCELLED"}

        for node in context.material.node_tree.nodes:
            node.select = False

        # TODO(Andreas): Not supposed to stay in legacy importer module
        node_group = load_poliigon_node_group(self.node_type)
        if node_group is None:
            self.report({"ERROR"}, _t("Failed to import nodegroup."))
            return {"CANCELLED"}

        mat = context.material
        node_mosaic = mat.node_tree.nodes.new("ShaderNodeGroup")
        node_mosaic.node_tree = node_group
        node_mosaic.name = node_group.name
        node_mosaic.width = 200
        if not node_mosaic.node_tree:
            self.report({"ERROR"}, _t("Failed to load nodegroup."))
            return {"CANCELLED"}

        # Use this built in modal for moving the added node around
        return bpy.ops.node.translate_attach('INVOKE_DEFAULT')
