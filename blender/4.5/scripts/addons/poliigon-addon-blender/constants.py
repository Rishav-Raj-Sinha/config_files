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


ADDON_NAME = "poliigon-addon-blender"

SUPPORTED_CONVENTION = 1

URLS_BLENDER = {
    "survey": "https://poliigon.com/survey-blender?usp=pp_url&entry.124129559={}",
    "p4b": "https://poliigon.com/blender",
    "changelog": "https://help.poliigon.com/en/articles/6342599-poliigon-blender-addon",
    "terms_policy": "https://help.poliigon.com/en/articles/10567243-terms-policy-documents",
    "help": "https://help.poliigon.com/en/articles/6342599-poliigon-blender-addon"
}

ICONS = [  # tuples: (name, filename, type)
    ("ICON_poliigon", "poliigon_logo.png", "IMAGE"),
    ("ICON_asset_balance", "asset_balance.png", "IMAGE"),
    ("GET_preview", "get_preview.png", "IMAGE"),
    ("NO_preview", "icon_nopreview.png", "IMAGE"),
    ("ICON_dots", "icon_dots.png", "IMAGE"),
    ("ICON_plan_upgrade_check", "icon_plan_upgrade_check.png", "IMAGE"),
    ("ICON_plan_upgrade_info", "icon_plan_upgrade_info.png", "IMAGE"),
    ("ICON_plan_upgrade_unlimited", "icon_plan_upgrade_unlimited.png", "IMAGE"),
    ("ICON_subscription_paused", "subscription_paused.png", "IMAGE"),
    ("LOGO_unlimited", "logo_unlimited.png", "IMAGE"),
    ("ICON_local", "icon_local.png", "IMAGE"),
    ("LOGO_downloads_recent", "icon_downloads_recent.png", "IMAGE"),
    ("ICON_new_asset", "new_asset.png", "IMAGE"),
    ("ICON_free_asset", "free_asset.png", "IMAGE"),
    ("ICON_checkmark_verified", "checkmark_verified.png", "IMAGE")
]

# TODO(Andreas): Not quite sure, why we do not need these in addon-core,
#                nor why these are different from SIZES
HDRI_RESOLUTIONS = ["1K", "2K", "3K", "4K", "6K", "8K", "16K"]


# Default asset ID 1000000 means fetch all IDs.
# 1000000 to be expected outside of valid range.
# Did not use -1 to leave the negative ID range for side imports.
ASSET_ID_ALL = 1000000

# -6 on label width:
# Needed to reduce a bit to avoid truncation on OSX 1x and 2x screens.
POPUP_WIDTH = 250
POPUP_WIDTH_LABEL = POPUP_WIDTH - 6
POPUP_WIDTH_NARROW = 200
POPUP_WIDTH_LABEL_NARROW = POPUP_WIDTH_NARROW - 6
POPUP_WIDTH_WIDE = 400
POPUP_WIDTH_LABEL_WIDE = POPUP_WIDTH_WIDE - 6
