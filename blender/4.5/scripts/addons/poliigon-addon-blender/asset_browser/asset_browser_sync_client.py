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

"""Standalone blender startup script used to generate asset blend files.

General Asset Browser links:
Asset Catalogs: https://wiki.blender.org/wiki/Source/Architecture/Asset_System/Catalogs
Asset Operators: https://docs.blender.org/api/current/bpy.ops.asset.html
AssetMetaData: https://docs.blender.org/api/current/bpy.types.AssetMetaData.html#bpy.types.AssetMetaData
Catalogs and save: https://blender.stackexchange.com/questions/284833/get-asset-browser-catalogs-in-case-of-unsaved-changes

Operator overriding:
https://blender.stackexchange.com/questions/248274/a-comprehensive-list-of-operator-overrides
https://blender.stackexchange.com/questions/129989/override-context-for-operator-called-from-panel
https://blender.stackexchange.com/questions/182713/how-to-use-context-override-on-the-disable-and-keep-transform-operator
https://blender.stackexchange.com/questions/273474/how-to-override-context-to-launch-ops-commands-in-text-editor-3-2
https://blender.stackexchange.com/questions/875/proper-bpy-ops-context-setup-in-a-plugin

Asset browser related, not much use in here:
https://blender.stackexchange.com/questions/262284/how-do-i-access-the-list-of-selected-assets-from-an-event-in-python
https://blender.stackexchange.com/questions/261213/get-the-source-path-of-the-assets-in-asset-browser-using-python
"""

import argparse
import os
import sys

import bpy

from typing import Tuple
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.poliigon_core.multilingual import _t  # noqa: E402
from constants import ADDON_NAME  # noqa: E402


DEBUG_CLIENT = False


def print_debug(*args, file=sys.stdout) -> None:
    """Use for printing in client script"""

    if not DEBUG_CLIENT:
        return
    print("          C:", *args, file=file)


def command_line_args() -> Tuple[str, str]:
    """Parses command line args."""

    path_catalog = None
    path_categories = None

    # Skip Blender's own command line args
    argv = sys.argv
    try:
        idx_arg = argv.index("--") + 1
    except ValueError:
        idx_arg = None
    if idx_arg is None or idx_arg >= len(argv):
        return None, None

    argv = argv[idx_arg:]

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-pcf", "--poliigon_cat_file",
                            help=_t("Path to catalog file"),
                            required=True)
        parser.add_argument("-pc", "--poliigon_categories",
                            help=_t("Path to file with Poliigon categories"),
                            required=True)
        args = parser.parse_args(argv)
    except Exception as e:
        print_debug(e)

    if args.poliigon_cat_file:
        path_catalog = args.poliigon_cat_file
    else:
        print_debug(
            "Lacking path to Blender cat file in commandline arguments!")
        return None, None

    if args.poliigon_categories:
        path_categories = args.poliigon_categories
    else:
        print_debug(
            "Lacking path to Poliigon categories file in commandline "
            "arguments!")
        return None, None

    return path_catalog, path_categories


def main():
    print_debug("Hello Blender host, I am the client")

    path_catalog, path_categories = command_line_args()
    has_catalog = path_catalog is not None
    has_categories = path_categories is not None
    if not has_catalog or not has_categories:
        print_debug("Missing catalog or categories path.")
        return

    bpy.ops.preferences.addon_enable(module=ADDON_NAME)

    bpy.ops.poliigon.asset_browser_sync_client(
        path_catalog=path_catalog, path_categories=path_categories)

    print_debug("Subprocess exit")


if __name__ == "__main__":
    main()
