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

# {<node.bl_static_type>: {<socket name used>: <socket name version>}}
SOCKET_NAMES_2_8 = {
    "ADD_SHADER": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "BSDF_PRINCIPLED": {
        "Emission Color": "Emission",
        "Transmission Weight": "Transmission",
    },
    "MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MIX": {
        "A": "Color1",
        "B": "Color2"
    },
    "MIX_RGB": {
        "Factor": "Fac",
        "A": "Color1",
        "B": "Color2",
        "Result": "Color"
    },
    "MIX_SHADER": {
        "A": 1,
        "B": 2,
    },
    "VECT_MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
}
SOCKET_NAMES_3_0 = {
    "ADD_SHADER": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "BSDF_PRINCIPLED": {
        "Emission Color": "Emission",
        "Transmission Weight": "Transmission",
    },
    "MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MIX": {
        "A": "Color1",
        "B": "Color2"
    },
    "MIX_RGB": {
        "Factor": "Fac",
        "A": "Color1",
        "B": "Color2",
        "Result": "Color"
    },
    "MIX_SHADER": {
        "A": 1,  # Code needs allow_index to be True!
        "B": 2,  # Code needs allow_index to be True!
    },
    "VECT_MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
}
SOCKET_NAMES_3_4 = {
    "ADD_SHADER": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "BSDF_PRINCIPLED": {
        "Emission Color": "Emission",
        "Transmission Weight": "Transmission",
    },
    "MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MIX": {
        "A": 6,  # Code needs allow_index to be True!
        "B": 7,  # Code needs allow_index to be True!
        "Result": 2  # Code needs allow_index to be True!
    },
    "MIX_RGB": {
        "Factor": "Fac",
        "A": "Color1",
        "B": "Color2",
        "Result": "Color"
    },
    "MIX_SHADER": {
        "A": 1,  # Code needs allow_index to be True!
        "B": 2,  # Code needs allow_index to be True!
    },
    "VECT_MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
}

SOCKET_NAMES_4_0 = {
    "ADD_SHADER": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MIX_RGB": {
        "Factor": "Fac",
        "A": "Color1",
        "B": "Color2",
        "Result": "Color"
    },
    "MIX_SHADER": {
        "A": 1,  # Code needs allow_index to be True!
        "B": 2,  # Code needs allow_index to be True!
    },
    "VECT_MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
}
SOCKET_NAMES_4_3 = {
    "ADD_SHADER": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
    "MIX_SHADER": {
        "A": 1,  # Code needs allow_index to be True!
        "B": 2,  # Code needs allow_index to be True!
    },
    "VECT_MATH": {
        "A": 0,  # Code needs allow_index to be True!
        "B": 1,  # Code needs allow_index to be True!
    },
}

SOCKET_NAMES = {
    (2, 8): SOCKET_NAMES_2_8,
    (3, 0): SOCKET_NAMES_3_0,
    (3, 4): SOCKET_NAMES_3_4,
    (4, 0): SOCKET_NAMES_4_0,
    (4, 3): SOCKET_NAMES_4_3,
    (999, 999): None  # upper version bound, used during iteration
}


def get_socket_name(node: bpy.types.Node, sock_name: str) -> str:
    """Returns a socket name for the running Blender version."""

    ver_blender = bpy.app.version

    list_versions = list(SOCKET_NAMES.keys())
    zip_versions = zip(list_versions[:-1], list_versions[1:])
    socket_names = None
    for _version_low, _version_high in zip_versions:
        if _version_low <= ver_blender < _version_high:
            socket_names = SOCKET_NAMES[_version_low]
            break

    if socket_names is None:
        print(f"No socket name table found for Blender version {ver_blender}")
        return sock_name

    if node.bl_static_type not in socket_names:
        # Not an error, just a version independent port name
        return sock_name

    socket_names_node = socket_names[node.bl_static_type]

    if sock_name not in socket_names_node:
        # Not an error, just a version independent port name
        return sock_name

    return socket_names_node[sock_name]
