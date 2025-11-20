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

from ..modules.poliigon_core.multilingual import _t


def append_poliigon_groups_node_add(self, context) -> None:
    """Appending to add node menu, for Poliigon node groups"""

    self.layout.menu('POLIIGON_MT_add_node_groups')


class POLIIGON_MT_add_node_groups(bpy.types.Menu):
    """Menu for the Poliigon Shader node groups"""

    bl_space_type = 'NODE_EDITOR'
    bl_label = _t("Poliigon Node Groups")

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        if bpy.app.version >= (2, 90):
            col.operator("poliigon.add_converter_node",
                         text=_t("Mosaic")
                         ).node_type = "Mosaic_UV_Mapping"
        col.operator("poliigon.add_converter_node",
                     text=_t("PBR mixer")
                     ).node_type = "Poliigon_Mixer"

        col.separator()
