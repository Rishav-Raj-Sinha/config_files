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

from threading import Event

from bpy.types import Operator
from bpy.props import StringProperty

from ..modules.poliigon_core.api_remote_control import ApiJob
from ..preferences_map_prefs_util import update_map_prefs_properties
from ..toolbox import get_context
from ..toolbox_settings import save_settings
from .. import reporting


class POLIIGON_OT_reset_map_prefs(Operator):
    bl_idname = "poliigon.reset_map_prefs"
    bl_label = ""
    bl_options = {"INTERNAL"}

    tooltip: StringProperty(options={"HIDDEN"})  # noqa: F821

    @staticmethod
    def init_context(addon_version: str) -> None:
        """Called from operators.py to init global addon context."""

        global cTB
        cTB = get_context(addon_version)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip

    def _callback_done(self, job: ApiJob) -> None:
        self.event.set()

    @reporting.handle_operator(silent=True)
    def execute(self, context):

        self.event = Event()

        cTB.api_rc.add_job_get_download_prefs(
            callback_cancel=None,
            callback_progress=None,
            callback_done=self._callback_done,
            force=True)

        self.event.wait(10.0)

        update_map_prefs_properties(cTB)
        save_settings(cTB)

        return {'FINISHED'}
