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

from ..modules.poliigon_core.api_remote_control_params import (
    CATEGORY_ALL,
    CATEGORY_FREE,
    KEY_TAB_ONLINE)
from ..modules.poliigon_core.assets import (
    AssetType,
    ASSET_TYPE_TO_CATEGORY_NAME)
from ..modules.poliigon_core.multilingual import _t
from .utils_dlg import get_ui_scale


# TODO(Andreas): This will be an exciting module in terms of multilingual
# TODO(Andreas): Would like to refactor this module


# @timer
def build_categories(cTB):
    cTB.logger_ui.debug("build_categories")

    categories_selected = []
    categories = []
    subcategories = []
    if cTB.vAssetType != CATEGORY_ALL:
        for _asset_type in cTB.vCategories["poliigon"].keys():
            if cTB.vAssetType in [CATEGORY_ALL, _asset_type]:
                categories += cTB.vCategories["poliigon"][_asset_type].keys()
        categories = sorted(list(set(categories)))

        if len(categories) > 0:
            category = ""
            categories_selected = []
            for _idx_sel in range(1, len(cTB.vActiveCat)):
                category += "/" + cTB.vActiveCat[_idx_sel]
                categories_selected.append(category)

            subcategories = [
                _cat.split("/")[-1]
                for _cat in categories
                if _cat.startswith(category) and _cat != category
            ]
            if len(subcategories) > 0:
                categories_selected.append("sub")

    col_categories = cTB.vBase.column()

    width_factor = len(categories_selected) + 1
    if cTB.width_draw_ui >= max(width_factor, 2) * 160 * get_ui_scale(cTB):
        row_categories = col_categories.row()
    else:
        row_categories = col_categories

    row_sub_cat = row_categories.row(align=True)

    type_hdri = "HDRIS"  # TODO(SOFT-2733): Cleanup HDRIS mapping
    type_model = ASSET_TYPE_TO_CATEGORY_NAME[AssetType.MODEL]
    type_tex = ASSET_TYPE_TO_CATEGORY_NAME[AssetType.TEXTURE]
    list_types = [CATEGORY_ALL, type_tex, type_model, type_hdri]
    area = cTB.settings["area"]
    if area == KEY_TAB_ONLINE:
        list_types.append(CATEGORY_FREE)

    if cTB.vAssetType == CATEGORY_ALL:
        lbl_button_cat = _t("Select Category")
    else:
        lbl_button_cat = cTB.vAssetType
    op = row_sub_cat.operator(
        "poliigon.poliigon_category", text=lbl_button_cat, icon="TRIA_DOWN"
    )
    op.data = "0@" + "@".join(list_types)

    if len(categories_selected) == 0:
        col_categories.separator()
        return

    for _idx_sel, _cat_sel in enumerate(categories_selected):
        row_sub_cat = row_categories.row(align=True)

        if _idx_sel == 0:
            selected_categories = [
                _cat.split("/")[-1]
                for _cat in categories
                if len(_cat.split("/")) == 2
            ]
        elif _cat_sel == "sub":
            selected_categories = subcategories
        else:
            cat_parent = "/".join(_cat_sel.split("/")[:-1])
            selected_categories = [
                _cat.split("/")[-1]
                for _cat in categories
                if _cat.startswith(cat_parent) and _cat != cat_parent
            ]

        selected_categories = sorted(list(set(selected_categories)))

        lbl_button = _cat_sel.split("/")[-1]
        if _cat_sel == "sub":
            lbl_button = "All " + cTB.vActiveCat[-1]

        selected_categories.insert(0, "All " + cTB.vActiveCat[_idx_sel])
        data_op = f"{_idx_sel + 1}@{'@'.join(selected_categories)}"
        op = row_sub_cat.operator(
            "poliigon.poliigon_category", text=lbl_button, icon="TRIA_DOWN"
        )
        op.data = data_op

    col_categories.separator()
