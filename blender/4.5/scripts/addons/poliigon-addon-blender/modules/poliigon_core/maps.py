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

from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Optional

from .multilingual import _t


# MAPS_TYPE_NAMES defined at the end of the file (needs MapType defined)


@dataclass()
class MapDescription:
    description: str
    display_name: str


class MapType(IntEnum):
    """Supported texture map types.

    NOTE: When extending, existing values MUST NEVER be changed.
    NOTE 2: Derived from IntEnum for easier "to JSON serialization"
    """

    # Convention 0 values
    DEFAULT = 1
    UNKNOWN = 1

    ALPHA = 2  # Usually associated with a brush
    ALPHAMASKED = 3
    AO = 4
    BUMP = 5
    BUMP16 = 6
    COL = 7
    DIFF = 8
    DISP = 9
    DISP16 = 10
    EMISSIVE = 11
    EMISSION = 11
    ENV = 12  # Environment for an HDRI, typically a .jpg file
    JPG = 12  # Environment for an HDRI, type_code as in ApiResponse
    FUZZ = 13
    GLOSS = 14
    IDMAP = 15
    LIGHT = 16  # Lighting for an HDRI, typically a .exr file
    HDR = 16  # Lighting for an HDRI, type_code as in ApiResponse
    MASK = 17  # Mask here means opacity
    METALNESS = 18
    NRM = 19
    NRM16 = 20
    OVERLAY = 21
    REFL = 22
    ROUGHNESS = 23
    SSS = 24
    TRANSLUCENCY = 25
    TRANSMISSION = 26
    OPACITY = 27
    UNDEF = 28
    # Non convention 0 types (needed for convention conversion)
    NA_ORM = 50
    NA_VERTEXBLEND = 51

    # Legacy maps - used to identify and download - not yet applied to the materials;
    ALBEDO = 52
    OVERLAY16 = 53
    DIRECTION = 54

    # Convention 1, values 100 to 149 (150 and up for convention 1 only maps)
    # NOTE: Value - 100 should match convention 0
    AmbientOcclusion = 104
    BaseColor = 107
    BaseColorOpacity = 103  # realtime only
    BaseColorVertexBlend = 151
    Displacement = 109
    Emission = 111
    Environment = 112  # Map for converting HDRI into Env
    HDRI = 116
    ORM = 150  # packmap where R:AO, G:Roughness, B:Metalness, realtime only
    Metallic = 118
    Normal = 119
    Opacity = 117
    Roughness = 123
    ScatteringColor = 124
    SheenColor = 113
    Translucency = 125
    Transmission = 126

    @classmethod
    def from_type_code(cls, map_type_code: str):
        if map_type_code in MAPS_TYPE_NAMES:
            return cls[map_type_code]

        map_type_code = map_type_code.split("_")[0]
        if map_type_code in MAPS_TYPE_NAMES:
            return cls[map_type_code]

        return cls.UNKNOWN

    def get_convention(self) -> int:
        return self.value // 100

    def get_effective(self):  # -> MapType
        return self.convert_convention(0)

    def convert_convention(self, target_convention: int):  # -> MapType
        convention_in = self.value // 100
        convention_diff = target_convention - convention_in
        return MapType(self.value + (100 * convention_diff))

    def get_description(self) -> Optional[MapDescription]:
        return MAP_DESCRIPTIONS.get(self.get_effective(), None)


MAP_DESCRIPTIONS: Dict = {
    MapType.ALPHAMASKED: MapDescription(
        description=_t(
            "This texture map is identical to the Base Color Map, but with "
            "an added Alpha channel containing the opacity map. This is "
            "included in materials containing empty see-through space such "
            "as sheer fabrics and leaves."),
        display_name=_t("Base Color Opacity")),

    MapType.AO: MapDescription(
        description=_t(
            "Defines the shadows in the crevices of the material. It's combined "
            "with the color map by using a Multiply layer blend operation."),
        display_name=_t("Ambient Occlusion")),

    MapType.COL: MapDescription(
        description=_t(
            "Contains the pure color information of the surface, "
            "devoid of any shadow or reflection."),
        display_name=_t("Base Color")),

    MapType.DISP: MapDescription(
        description=_t(
            "This black and white image defines the height information of the "
            "surface. Light values are raised, dark values are reduced, "
            "mid-grey (0.5) represents the flat mid-point of the surface."),
        display_name=_t("Displacement")),

    MapType.FUZZ: MapDescription(
        description=_t(
            "Defines the fine fuzz of microfibers in cloth-like surfaces. "
            "Included with many fabrics textures. "
            "The sheen color defines only the color."),
        display_name=_t("Sheen Color")),

    MapType.METALNESS: MapDescription(
        description=_t(
            "This black and white image defines which parts are metal "
            "(white) and which are non-metal (black)."),
        display_name=_t("Metallic")),

    MapType.NRM: MapDescription(
        description=_t(
            "This purple-ish image defines the height information, which is faked "
            "by shader (not physically altering the mesh)"),
        display_name=_t("Normal")),

    MapType.ROUGHNESS: MapDescription(
        description=_t(
            "This black and white image defines how sharp or diffuse the "
            "reflections are. Blacker values are glossy, "
            "whiter values are matte."),
        display_name=_t("Roughness")),

    MapType.SSS: MapDescription(
        description=_t(
            "Defines the color of light passing through solid closed manifold "
            "objects like food or fabric. This is included in fabric "
            "and vegetation textures."),
        display_name=_t("Scattering Color")),

    MapType.TRANSLUCENCY: MapDescription(
        description=_t(
            "Defines the color of light penetrating and appearing on the "
            "backside of a flat thinshell meshes. "
            "This is included in fabric and vegetation textures."),
        display_name=_t("Translucency")),

    MapType.TRANSMISSION: MapDescription(
        description=_t(
            "Defines which parts of the texture are refracting light, "
            "and is included in textures like glass or liquids. "
            "The IOR (Index of Refraction) should be set be defined "
            "by you depending on the material."),
        display_name=_t("Transmission")),

    MapType.MASK: MapDescription(
        description=_t(
            "Defines which parts of the texture are opaque, or transparent "
            "(completely invisible, without refraction). "
            "This is included in materials containing empty see-through "
            "space such as sheer fabrics and leaves."),
        display_name=_t("Opacity")),

    MapType.NA_ORM: MapDescription(
        description=_t(
            "This special texture stores the same Ambient Occlusion, Roughness "
            "and Metalness information, but each are stored in the separate Red, "
            "Green and Blue channels respectively. This special map is "
            "typically only used in realtime rendering and game applications."),
        display_name=_t("ORM"))
}

MAPS_TYPE_NAMES = MapType.__members__
