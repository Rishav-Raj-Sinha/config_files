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

from typing import Optional, Tuple

import bpy

from ..modules.poliigon_core.assets import (
    AssetData,
    ModelType)
from ..modules.poliigon_core.multilingual import _t

from ..constants import SUPPORTED_CONVENTION
from ..utils import construct_model_name


def check_convention(asset_data: AssetData, local: bool = False) -> bool:
    asset_convention = asset_data.get_convention(local=local)

    if asset_convention is None:
        return False
    elif asset_convention > SUPPORTED_CONVENTION:
        return False
    return True


def get_model_op_details(
        cTB, asset_data: AssetData, size: str) -> Tuple[str, str, str]:
    """Get details to use in the ui for a given model and size."""

    asset_type_data = asset_data.get_type_data()
    asset_name = asset_data.asset_name

    default_lod = cTB.settings["lod"]
    downloaded = asset_type_data.get_size_list(
        local_only=True,
        addon_convention=cTB._asset_index.addon_convention,
        local_convention=asset_data.get_convention(local=True))

    lod = asset_type_data.get_lod(default_lod)
    if lod is None:
        lod = "NONE"

    if not asset_type_data.has_mesh(ModelType.FBX):
        lod = "NONE"

    coll_name = construct_model_name(asset_name, size, lod)

    coll = bpy.data.collections.get(coll_name)
    if coll:
        in_scene = True
    else:
        in_scene = False

    label = ""
    tip = ""
    if size in downloaded:
        if in_scene:
            if lod:
                label = _t("{0} {1} (import again)").format(size, lod)
                tip = _t("Import {0} {1} again\n{2}").format(
                    size, lod, asset_name)
            else:
                label = _t("{0} (import again)").format(size)
                tip = _t("Import {0} again\n{1}").format(size, asset_name)
        else:
            if lod:
                label = _t("{0} {1} (import)").format(size, lod)
                tip = _t("Import {0} {1}\n{2}").format(
                    size, lod, asset_name)
            else:
                label = _t("{0} (import)").format(size)
                tip = _t("Import {0}\n{1}").format(size, asset_name)

    return lod, label, tip


def safe_size_apply(cTB,
                    op_ref: bpy.types.OperatorProperties,
                    size_value: str,
                    asset_name: str) -> None:
    """Applies a size value to operator draw with a safe fallback.

    If we try to apply a size which is not recognized as local, it will fail
    and disrupt further drawing. This function mitigates this problem.
    """

    if size_value is None:
        return
    try:
        op_ref.size = size_value
    except TypeError as e:
        # Since this is a UI draw issue, there will be multiple of these
        # these reports, but we have user-level debouncing for a max number
        # per message type.
        msg = f"Failed to assign {size_value} size for {asset_name}: {e}"
        cTB.logger_ui.error(msg)
        # TODO(SOFT-1303): Include in refactor to asset index, disabled
        # overreporting for now.
        # reporting.capture_message("failed_size_op_set", msg, "error")


def check_dpi(cTB, force: bool = True) -> None:
    """Checks the DPI of the screen to adjust the scale accordingly.

    Used to ensure previews remain square and avoid text truncation.
    """

    if not force and cTB.ui_scale_checked:
        return

    prefs = bpy.context.preferences
    cTB.settings["win_scale"] = prefs.system.ui_scale
    cTB.ui_scale_checked = True


def get_ui_scale(cTB) -> float:
    """Utility for fetching the ui scale, used in draw code."""

    check_dpi(cTB)
    return cTB.settings["win_scale"]


def _get_line_width(cTB, line: str) -> int:
    """Returns pixel width of a string."""

    width_line = 15
    for _char in line:
        if _char in "ABCDEFGHKLMNOPQRSTUVWXYZmw":
            width_line += 9
        elif _char in "abcdeghknopqrstuvxyz0123456789":
            width_line += 6
        elif _char in "IJfijl .":
            width_line += 3

    width_line *= get_ui_scale(cTB)
    return width_line


def wrapped_label(cTB,
                  width: int,
                  text: str,
                  container: bpy.types.UILayout,
                  icon: Optional[str] = None,
                  add_padding: bool = False,
                  add_padding_top: bool = False,
                  add_padding_bottom: bool = False,
                  alignment: str = 'LEFT'
                  ) -> None:
    """Text wrap a label based on indicated width."""

    cTB.logger_ui.debug(f"wrapped_label width={width}, text={text}, "
                        f"icon={icon}, add_padding={add_padding}, alignment={alignment}")

    list_words = [_word.replace("!@#", " ") for _word in text.split(" ")]

    row = container.row()
    parent = row.column(align=True)
    parent.alignment = alignment  # Set alignment on the parent column
    parent.scale_y = 0.8  # To make vertical height more natural for text.

    if add_padding or add_padding_top:
        parent.label(text="")

    if icon is not None:
        width -= 25 * get_ui_scale(cTB)

    line = ""
    first = True

    for _word in list_words:
        width_line = _get_line_width(cTB, line + _word + " ")
        if width_line > width:
            if first:
                if icon is None:
                    if alignment == 'LEFT':
                        parent.label(text=line)
                    else:
                        label_row = parent.row()
                        label_row.alignment = alignment
                        label_row.label(text=line)
                else:
                    if alignment == 'LEFT':
                        parent.label(text=line, icon=icon)
                    else:
                        label_row = parent.row()
                        label_row.alignment = alignment
                        label_row.label(text=line, icon=icon)
                first = False

            else:
                if icon is None:
                    if alignment == 'LEFT':
                        parent.label(text=line)
                    else:
                        label_row = parent.row()
                        label_row.alignment = alignment
                        label_row.label(text=line)
                else:
                    if alignment == 'LEFT':
                        parent.label(text=line, icon="BLANK1")
                    else:
                        label_row = parent.row()
                        label_row.alignment = alignment
                        label_row.label(text=line, icon="BLANK1")

            line = _word + " "

        else:
            line += _word + " "

    if line != "":
        if icon is None:
            if alignment == 'LEFT':
                parent.label(text=line)
            else:
                label_row = parent.row()
                label_row.alignment = alignment
                label_row.label(text=line)
        else:
            if first:
                if alignment == 'LEFT':
                    parent.label(text=line, icon=icon)
                else:
                    label_row = parent.row()
                    label_row.alignment = alignment
                    label_row.label(text=line, icon=icon)
            else:
                if alignment == 'LEFT':
                    parent.label(text=line, icon="BLANK1")
                else:
                    label_row = parent.row()
                    label_row.alignment = alignment
                    label_row.label(text=line, icon="BLANK1")

    if add_padding or add_padding_bottom:
        spacer = parent.row()
        spacer.scale_y = 0.3
        spacer.label(text="")


def separator_p4b(
        container: bpy.types.UILayout, *, line: bool = False) -> None:
    if line and bpy.app.version >= (4, 2):
        container.separator(type='LINE')
    else:
        container.separator()
