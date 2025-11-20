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
from bpy.props import StringProperty

from ..modules.poliigon_core.multilingual import _t

from ..modules.poliigon_core.asset_filters import FilterOptions
from ..toolbox import get_context
from .. import reporting


class POLIIGON_OT_asset_filter(Operator):
    bl_idname = "poliigon.asset_filter"
    bl_label = _t(FilterOptions.ALL_ASSETS.map_to_short_value())
    bl_description = _t("Filter Assets")

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    @classmethod
    def poll(cls, context):
        return cTB.all_assets_fetched

    @staticmethod
    def _show_filters_menu(cTB) -> None:
        """Generates the popup menu to display category selection options."""

        @reporting.handle_draw()
        def draw(self, context):
            layout = self.layout
            row = layout.row()
            col = row.column(align=True)

            if cTB.user is None:
                filter_options = FilterOptions.get_list()
            else:
                filter_options = FilterOptions.get_list_for_user(cTB.user)
            for _filter_data in filter_options:
                button_text = _t(_filter_data.map_to_short_value())
                op = col.operator("poliigon.poliigon_setting", text=button_text)
                op.mode = f"asset_filter_{_filter_data.map_to_query()}"
                op.tooltip = _t("Filter {0} Assets").format(button_text)

        bpy.context.window_manager.popup_menu(draw)

    def execute(self, context):
        self._show_filters_menu(cTB)
        return {"FINISHED"}
