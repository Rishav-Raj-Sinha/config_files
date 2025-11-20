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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Dict, List, Optional, Sequence, Tuple, Union, Any
import os

from .maps import MapType
from .multilingual import _m, _t

# API_TYPE_TO_ASSET_TYPE defined at the end of the file (needs AssetType defined)
LODS = [f"LOD{i}" for i in range(5)]
PREVIEWS = ["_atlas",
            "_sphere",
            "_cylinder",
            "_fabric",
            "_preview1",
            "_preview2",
            "_preview3",
            "_preview01",
            "_preview02",
            "_preview03",
            "_flat",
            "_cube",
            "_grid",
            ]
PREVIEW_EXTS_LOWER = [".jpg", ".jpeg", ".png"]
MAP_EXT_LOWER = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".hdr", ".webp", ".psd"]
SIZES = ["256", "512"] + [f"{idx+1}K" for idx in range(18)] + ["HIRES", "WM"]
VARIANTS = [f"VAR{idx}" for idx in range(1, 10)]
WORKFLOWS = ["REGULAR", "METALNESS", "SPECULAR"]


class ModelType(IntEnum):
    """Supported formats for Models.

    NOTE: When extending, existing values MUST NEVER be changed.
    NOTE 2: Derived from IntEnum for easier "to JSON serialization"
    """

    FBX = 1
    BLEND = 2
    MAX = 3
    C4D = 4
    OBJ = 5  # BOB extension


class AssetType(IntEnum):
    """Supported asset types.

    NOTE: When extending, existing values MUST NEVER be changed.
    NOTE 2: Derived from IntEnum for easier "to JSON serialization"
    """

    UNSUPPORTED = 1
    BRUSH = 2
    HDRI = 3
    MODEL = 4
    TEXTURE = 5
    SUBSTANCE = 6  # still unsupported
    ALL = 999

    @classmethod
    def type_from_api(cls, api_type_name: str) -> int:
        if api_type_name not in CATEGORY_NAME_TO_ASSET_TYPE:
            return cls.UNSUPPORTED
        return CATEGORY_NAME_TO_ASSET_TYPE[api_type_name]


class CreationMethodId(IntEnum):
    PHOTOSCANNED = 0
    PROCEDURAL = 1
    PHOTOMETRIC = 3
    HYBRID = 4

    @classmethod
    def from_string(cls, method_string: str):
        method_string = method_string.upper()
        if method_string in cls.__members__:
            return cls[method_string]
        return None


@dataclass()
class CreationMethodData:
    method: str
    description: str


CREATION_METHODS = {
    CreationMethodId.PHOTOSCANNED: CreationMethodData(
        method=_t("Photogrammetry Capture"),
        description=_t("This texture is a photoscan of a real world surface. "
                       "Typically created from hundreds of photographs to reconstruct "
                       "an accurate surface appearance.")
    ),
    CreationMethodId.PROCEDURAL: CreationMethodData(
        method=_t("Procedural"),
        description=_t("This texture is a handmade representation of a real world "
                       "surface. Typically created from multiple reference photos "
                       "and artistically reconstructed in Substance Designer.")
    ),
    CreationMethodId.PHOTOMETRIC: CreationMethodData(
        method=_t("Photometric Stereo Capture"),
        description=_t("This texture is a photoscan of a real world surface. "
                       "Captured from multiple photographs of a surface under "
                       "different light positions to reconstruct accurate "
                       "surface height details.")
    ),
    CreationMethodId.HYBRID: CreationMethodData(
        method=_t("Hybrid"),
        description=_t("This texture combines photogrammetry and procedural "
                       "detail. Typically the primary surface detail is a "
                       "photogrammetry capture and secondary details are added "
                       "procedurally.")
    ),
}


CATEGORY_NAME_TO_ASSET_TYPE = {
    "All Assets": None,
    "Brushes": AssetType.BRUSH,
    "HDRIS": AssetType.HDRI,
    "Models": AssetType.MODEL,
    "Substances": AssetType.SUBSTANCE,
    "Textures": AssetType.TEXTURE,
    # "Free" needs special treatment.
    # It is rather a virtual category than an asset type.
    # It has to ever only appear in our AssetIndex cache keys.
    # Neither must it be sent to server, nor will it ever be
    # received from server.
    # See APIRC's ApiJobParamsGetAssets._map_categories_local_to_api()
    # to see how it is used during "get assets" job to create special query
    # cache entries for free assets (which are neither an asset type or
    # a category themselves).
    # And see AssetIndex._query_key_to_tuple(), how it is mapped to actual
    # query keys.
    "Free": "Free"  # Can not import CATEGORY_FREE, here (circular import)
}


@dataclass
class AssetThumbnail():
    filename: str
    base_url: str
    index: int
    time: datetime  # TODO(Andreas): This seems rather float!
    type: str

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        # TODO(Andreas): If time really was a datetime (see above),
        #                something like this would be needed:
        # if "time" not in d:
        #     raise KeyError("time")
        # d["time"] = create datetime from value

        new = cls(**d)
        return new


# NOT a data class
# Reason: this way it does not get saved with the asset index.
class AssetStateDownload():
    """Stores asset download related state information."""

    in_progress: bool = False
    cancelled: bool = False
    any_error: bool = False
    directory: Optional[str] = None
    progress: float = 0.001
    downloaded_bytes: int = 1
    recently_downloaded: bool = False
    # Always parse the first error found in the download process
    error: Optional[str] = None

    def start(self) -> None:
        """To be called when a download begins."""

        self.in_progress = True
        self.cancelled = False
        self.any_error = False
        self.error = None
        self.directory = None
        self.progress = 0.001
        self.downloaded_bytes = 1

    def end(self) -> None:
        """To be called after a download has ended (regardless of result)."""

        self.in_progress = False
        self.cancelled = False
        self.progress = 0.001
        # Do not touch self.any_error!

    def is_in_progress(self) -> bool:
        """Returns True, if a download is currently in progress."""

        return self.in_progress

    def cancel(self, reset: bool = False) -> None:
        """Cancels a download."""

        self.cancelled = not reset

    def is_cancelled(self) -> bool:
        """Returns True, if the download is supposoed to be cancelled."""

        return self.cancelled

    def set_error(
            self, error_msg: Optional[str] = None, reset: bool = False) -> None:
        """To be called if any kind of error occured during download."""

        self.any_error = not reset
        if self.error is None and error_msg is not None:
            self.error = error_msg

    def has_error(self) -> bool:
        """Returns True, if any error occurred during download."""

        return self.any_error

    def set_directory(self, directory: str) -> None:
        """Sets current download directory."""

        self.directory = directory

    def get_directory(self) -> Optional[str]:
        """Returns current download directory."""

        return self.directory

    def set_progress(self, progress: float) -> None:
        """Sets current download progress in percent [0.0-1.0]."""

        self.progress = min(max(0.001, progress), 1.0)

    def get_progress(self) -> float:
        """Returns current download progress, guaranteed non-zero."""

        return self.progress

    def set_downloaded_bytes(self, downloaded_bytes: int) -> None:
        """Sets currently downloaded bytes."""

        self.downloaded_bytes = max(1, downloaded_bytes)

    def get_downloaded_bytes(self) -> int:
        """Returns currently downloaded bytes, guaranteed non-zero."""

        return self.downloaded_bytes

    def set_recently_downloaded(self, recently_downloaded: bool) -> None:
        """Marks the asset as recently, successfully downloaded."""

        self.recently_downloaded = recently_downloaded

    def get_recently_downloaded(self) -> bool:
        """Returns True, if the asset got successfully downloaded, recently."""

        return self.recently_downloaded


# NOT a data class
# Reason: this way it does not get saved with the asset index.
class AssetStatePurchase():
    """Stores asset purchase related state information."""

    in_progress: bool = False
    any_error: bool = False
    # Always parse the first error found in the purchase process
    error: Optional[str] = None

    def start(self) -> None:
        """To be called when a purchase begins."""

        self.in_progress = True

    def end(self) -> None:
        """To be called after a purchase has ended (regardless of result)."""

        self.in_progress = False

    def is_in_progress(self) -> bool:
        """Returns True, if a purchase is currently in progress."""

        return self.in_progress

    def set_error(
            self, error_msg: Optional[str] = None, reset: bool = False) -> None:
        """To be called if any kind of error occured during purchase."""

        self.any_error = not reset
        if self.error is None and error_msg is not None:
            self.error = error_msg

    def has_error(self) -> bool:
        """Returns True, if any error occurred during purchase."""

        return self.any_error


class AssetState():
    """The volatile status of an asset during addon operation.
    E.g. download status in .dl

    Note: Upon saving and reloading AssetIndex from disk information contained
          in here will reset. State does _not_ get stored to disk.
    """

    has_error: bool = False
    error: Optional[Exception] = None

    # TODO(Andreas): Vanish into nothingness upon saving the asset index (works
    #                already, kind of).
    #                Create new instance upon load.

    def __init__(self):
        self.purchase = AssetStatePurchase()
        self.dl = AssetStateDownload()

    def has_any_error(self) -> bool:
        """Returns True, if any of the state classes signals an error."""

        has_dl_error = self.dl.has_error()
        has_purchase_error = self.purchase.has_error()
        return self.has_error or has_dl_error or has_purchase_error

    def get_any_error(
        self,
        force_string: bool = False
    ) -> Optional[Union[str, Exception]]:
        """Returns any error inside of state with following priority:
        Asset error -> Purchase error -> Download error
        """

        error = None
        if self.has_error:
            error = self.error
        elif self.purchase.has_error():
            error = self.purchase.error
        elif self.dl.has_error():
            error = self.dl.error

        if force_string and error is not None:
            error = str(error)
        return error


class AssetDataRuntime():
    """Stores additional asset data, which will only be valid during runtime.
    Content of this class will not be loaded from disk.
    """

    size_current: Optional[str] = None
    thumb_downloading: bool = False
    in_asset_browser: bool = False
    # Special BOB extension marking Texture assets as Image or Image Set
    is_polydex_image: bool = False
    is_polydex_stack: bool = False

    def store_current_size(self, size: Optional[str]) -> None:
        """Can be used to store a size, e.g. to change the size used for the
        import button.
        """

        self.size_current = size

    def get_current_size(self) -> Optional[str]:
        """Returns a previously stored size."""

        return self.size_current

    # TODO(Andreas): Currently added for use in P4BAC
    #                Not sure, yet, if I want to keep it here.
    #                Could also have a new AssetState class, like state_dcc.
    def set_thumb_downloading(self, *, is_downloading: bool) -> None:
        self.thumb_downloading = is_downloading

    def get_thumb_downloading(self) -> bool:
        return self.thumb_downloading

    # TODO(Andreas): Currently added for use in P4BAC
    #                Not sure, yet, if I want to keep it here.
    #                Could also have a new AssetState class, like state_dcc.
    def set_in_asset_browser(self, *, in_asset_browser: bool = True) -> None:
        self.in_asset_browser = in_asset_browser

    def is_in_asset_browser(self) -> bool:
        return self.in_asset_browser

    def set_is_polydex_image(self, *, is_polydex_image: bool = True) -> None:
        self.is_polydex_image = is_polydex_image

    def get_is_polydex_image(self) -> bool:
        return self.is_polydex_image

    def set_is_polydex_stack(self, *, is_polydex_stack: bool = True) -> None:
        self.is_polydex_stack = is_polydex_stack

    def get_is_polydex_stack(self) -> bool:
        return self.is_polydex_stack


# TODO(Andreas): Add a workflow enum
# TODO(Andreas): Add a LOD enum

def _cond_set(new, old):
    return new if new is not None else old


def find_closest_size(size: str,
                      size_list: List[str]
                      ) -> Optional[str]:
    """Tries to find an alternative size.
    The distance inside the SIZES list is used as metric of proximity.
    """

    if len(size_list) == 0:
        return None

    idx_size_wanted = SIZES.index(size)
    dist_min = len(SIZES)
    size_best_fit = None
    for idx_size, size_test in enumerate(SIZES):
        dist = abs(idx_size_wanted - idx_size)
        if size_test in size_list and dist < dist_min:
            dist_min = dist
            size_best_fit = size_test
    return size_best_fit


def sort_size_key(size):
    try:
        if size.endswith("K"):
            size = size[:-1]
            return int(size) * 1000
        return int(size)
    except ValueError:
        # Any value off the format "2K", "4K"
        # Highest texture size is 18000, 20000 to force end of the list
        if "WM" in size:
            return 20000
        elif "HIRES" in size:
            return 21000
        else:
            return 22000


class BaseAsset:
    """Function prototypes common to all asset types."""

    def update(self, type_data_new, purge_maps: bool = False) -> None:
        """Updates asset's data

        Args:
            type_data_new: Type Any of Brush, Hdri, Model or Texture
            purge_maps: If True any existing map entries will be thrown away
        """

        raise NotImplementedError

    def get_maps_per_preferences(self,
                                 map_preferences: Any,
                                 filter_extensions: bool = False):
        raise NotImplementedError

    def all_expected_maps_local(self, map_preferences: Any, size: str) -> bool:
        raise NotImplementedError


class BaseTex(BaseAsset):
    """Function prototypes common to all image based asset types."""

    def get_workflow_list(self, get_local: bool = False) -> List[str]:
        """Returns a list of all available workflows"""

        raise NotImplementedError

    def get_workflow(self, workflow: str, get_local: bool = False) -> str:
        """Verifies workflow is available or returns fallback"""

        raise NotImplementedError

    def get_size_list(self,
                      incl_watermarked: bool = False,
                      local_only: bool = False,
                      addon_convention: Optional[int] = None,
                      local_convention: Optional[int] = None,
                      map_preferences: Optional[Any] = None  # User MapPreferences
                      ) -> List[str]:
        """Returns list of all available sizes.

        Arguments:
        incl_watermarked: Set to True to have size WM considered
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!
        map_preferences: User map preferences, used for TEXTURES and if local_only;
        """

        raise NotImplementedError

    def get_size(self,
                 size: str,
                 incl_watermarked: bool = False,
                 local_only: bool = False,
                 addon_convention: Optional[int] = None,
                 local_convention: Optional[int] = None
                 ) -> str:
        """Verifies size is available, otherwise returns closest one.

        Arguments:
        size: The size to check for
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!

        Raises:
        KeyError: If no size was found at all.
        ValueError: If local_only is True with addon_convention being None.
        """

        raise NotImplementedError

    def get_variant_list(self) -> List[str]:
        """Returns a list of all available variants"""

        raise NotImplementedError

    def get_watermark_preview_url_list(self) -> Optional[List[str]]:
        """Returns a list of URLs needed for watermarked material assignment"""

        raise NotImplementedError

    def get_map_type_list(
            self, workflow: str, effective: bool = True) -> List[MapType]:
        """Returns a list of MapType needed for a workflow.

        Raises: KeyError, if workflow not found.
        """
        raise NotImplementedError

    def get_maps(self,
                 workflow: str = "REGULAR",
                 size: str = "1K",
                 lod: Optional[str] = None,
                 prefer_16_bit: bool = False,
                 suffix_list: List[str] = MAP_EXT_LOWER,
                 variant: Optional[str] = None,
                 effective: bool = True,
                 map_preferences: Any = None  # User MapPreferences
                 ) -> List:
        """Returns a list of Texture needed for workflow and size

        Return value: Type List[TextureMap]

        Raises: KeyError, if workflow not found.
        """

        raise NotImplementedError


@dataclass
class TextureMap:
    """Container object for a texture map.
    This class represents actual files on disc.
    Instances of this class exist only,
    if the respective files have been downloaded and found.
    """

    directory: str = ""
    filename: str = ""
    file_format: str = ""
    lod: Optional[str] = None
    map_type: MapType = MapType.UNKNOWN
    size: str = "1K"  # Short string, e.g., "1K"
    variant: Optional[str] = None

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "map_type" not in d:
            raise KeyError("map_type")
        new = cls(**d)
        new.map_type = MapType(new.map_type)
        return new

    def __eq__(self, other) -> bool:
        """Equality operator

        Args:
            other: Type TextureMap

        NOTE: The result does not imply identity!!!
              Instead two TextureMaps are considered equal,
              if they are used in the same "slot".
              map_type, size and variant need to match,
              but filename does NOT need to match.
              Reason is the use of this comparison during
              updating AssetData.
        """

        return self._key_tuple() == other._key_tuple()

    def _key_tuple(self) -> Tuple:
        """Merges relevant members into a Tuple"""

        return (self.map_type, self.size, self.variant, self.lod, self.file_format)

    def get_path(self):
        return os.path.join(self.directory, self.filename)

    def copy(self):
        """Creates a copy of the TextureMap instance"""
        return TextureMap(
            directory=self.directory,
            filename=self.filename,
            file_format=self.file_format,
            lod=self.lod,
            map_type=self.map_type,
            size=self.size,
            variant=self.variant,
        )


@dataclass
class TextureMapDesc:
    """Container object for a texture map description.
    Instances of this class get created after an asset has been queried.
    """

    display_name: str  # Beauty name for UI display
    filename_preview: str
    map_type_code: str  # "type_code" field as retrieved from the API
    file_formats: List[str]
    sizes: List[str]  # List of sizes, e.g., ["1K", "2K"]
    variants: List[str]  # List of variants, e.g. ["VAR1", "VAR2"]

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "map_type_code" not in d:
            raise KeyError("map_type_code")
        new = cls(**d)
        return new

    def __eq__(self, other) -> bool:
        # order of comparisons: "importance" of keys
        if self.map_type_code != other.map_type_code:
            return False
        if self.sizes != other.sizes:
            return False
        if self.variants != other.variants:
            return False
        if self.display_name != other.display_name:
            return False
        if self.filename_preview != other.filename_preview:
            return False
        return True

    def get_map_type(self, effective: bool = True) -> MapType:
        map_type = MapType.from_type_code(self.map_type_code)
        return map_type.get_effective() if effective else map_type

    def copy(self):
        return TextureMapDesc(display_name=self.display_name,
                              filename_preview=self.filename_preview,
                              map_type_code=self.map_type_code,
                              file_formats=self.file_formats,
                              sizes=self.sizes,
                              variants=self.variants)


@dataclass
class Texture(BaseTex):
    """Container object for a Texture."""

    # Texture options for display in UI
    # sizes, variants and lods are sets of all contained in an asset.
    # It is NOT guaranteed, all of them exist in all channels/workflows.
    lods: Optional[Sequence[str]] = None  # List of lods, e.g. ["LOD1", "LOD3"]
    map_descs: Optional[Dict[str, List[TextureMapDesc]]] = None  # {workfl. : [TextureMapsDesc]}
    maps: Optional[Dict[str, Sequence[TextureMap]]] = field(default_factory=dict)  # {workfl. : [TextureMaps]}
    sizes: Optional[Sequence[str]] = None  # List of sizes, e.g., ["1K", "2K"]
    variants: Optional[Sequence[str]] = None  # List of variants, e.g. ["VAR1", "VAR2"]
    watermarked_urls: Optional[Sequence[str]] = None
    # Width (x) and Height (y) of the real world dimension of the texture
    real_world_dimension: Optional[Tuple[int, int]] = None
    creation_method: Optional[CreationMethodId] = None

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "map_descs" not in d:
            raise KeyError("map_descs")
        if "maps" not in d:
            raise KeyError("maps")

        # Replace sub-dicts describing our class instances
        # with actual class instances
        tex_maps_desc_dict = d["map_descs"]
        if tex_maps_desc_dict is not None:
            for workflow, tex_map_desc_list in tex_maps_desc_dict.items():
                for idx_map_desc, tex_map_desc in enumerate(tex_map_desc_list):
                    tex_map_desc_list[idx_map_desc] = TextureMapDesc._from_dict(tex_map_desc)

        tex_maps_dict = d["maps"]
        if tex_maps_dict is not None:
            for workflow, tex_map_list in tex_maps_dict.items():
                for idx_map, tex_map in enumerate(tex_map_list):
                    tex_map_list[idx_map] = TextureMap._from_dict(tex_map)

        new = cls(**d)
        return new

    def _map_key_dict(self, workflow: str) -> Dict:
        """Returns a dictionary with all texture maps of a given workflow,
        index by key_tuples (see TextureMap)."""
        return {tex_map._key_tuple():
                tex_map for tex_map in self.maps[workflow]
                }

    def _update_new_sizes(self, type_data_new) -> None:
        if type_data_new.sizes is None or len(type_data_new.sizes) == 0:
            return
        if self.sizes is None:
            self.sizes = []
        for _size in type_data_new.sizes:
            if _size not in self.sizes:
                self.sizes.append(_size)
        # TODO(Andreas): Need sorting?
        #                Actually this should happen only with size WM,
        #                which is fine at the end

    def _get_map_desc_by_type(self,
                              map_type: MapType,
                              extension: str,
                              filter_extensions: bool = False,
                              workflow: str = "METALNESS"
                              ) -> List[TextureMapDesc]:
        asset_map_list = []
        for _map_desc in self.map_descs[workflow]:
            _map_desc = _map_desc.copy()
            _type = _map_desc.get_map_type(effective=True)
            ext_low = extension.lower()
            if _type == map_type and ext_low in _map_desc.file_formats:
                if filter_extensions:
                    _map_desc.file_formats = [ext_low]
                asset_map_list.append(_map_desc)

        return asset_map_list

    @staticmethod
    def _convention_0_filter_maps(tex_map_dict: Dict[MapType, List[TextureMap]],
                                  prefer_16_bit: bool = False
                                  ) -> Dict[MapType, List[TextureMap]]:
        # Decide between 8-Bit and 16-Bit, if both are available
        if MapType.BUMP in tex_map_dict and MapType.BUMP16 in tex_map_dict:
            if prefer_16_bit:
                del tex_map_dict[MapType.BUMP]
            else:
                del tex_map_dict[MapType.BUMP16]
        if MapType.DISP in tex_map_dict and MapType.DISP16 in tex_map_dict:
            if prefer_16_bit:
                del tex_map_dict[MapType.DISP]
            else:
                del tex_map_dict[MapType.DISP16]
        if MapType.NRM in tex_map_dict and MapType.NRM16 in tex_map_dict:
            if prefer_16_bit:
                del tex_map_dict[MapType.NRM]
            else:
                del tex_map_dict[MapType.NRM16]

        # TODO(Joao): Implement this in the dccs side once all the map
        #  management is being done there;
        # If ALBEDO map is found, we replace the COL list with the ALBEDO maps;
        # To be compatible with the addons, we have to keep using the MapType.COL
        # as key;
        albedo_list = tex_map_dict.get(MapType.ALBEDO, [])
        if len(albedo_list) > 0:
            tex_map_dict[MapType.COL] = []
            for albedo_map in albedo_list:
                albedo_map = albedo_map.copy()
                albedo_map.map_type = MapType.COL
                tex_map_dict[MapType.COL].append(albedo_map)

        return tex_map_dict

    def update(self, type_data_new, purge_maps: bool = False) -> None:
        """Updates Texture data

        Args:
            type_data_new: Type Texture, the instance to update from
            purge_maps: If True any existing map entries will be thrown away
        """

        if type_data_new is None:
            return

        if purge_maps:
            self.maps = {}

        self.map_descs = _cond_set(type_data_new.map_descs, self.map_descs)
        self._update_new_sizes(type_data_new)
        self.variants = _cond_set(type_data_new.variants, self.variants)
        self.lods = _cond_set(type_data_new.lods, self.lods)
        self.watermarked_urls = _cond_set(type_data_new.watermarked_urls,
                                          self.watermarked_urls)

        for workflow, tex_maps_new in type_data_new.maps.items():
            if workflow not in self.maps:
                self.maps[workflow] = tex_maps_new
                continue

            tex_map_dict = self._map_key_dict(workflow)
            for tex_map_new in tex_maps_new:
                key = tex_map_new._key_tuple()
                if key in tex_map_dict:
                    tex_map_dict[key].directory = tex_map_new.directory
                    tex_map_dict[key].filename = tex_map_new.filename
                else:
                    self.maps[workflow].append(tex_map_new)

    def is_local(self,
                 workflow: str = "REGULAR",
                 size: str = "1K",
                 prefer_16_bit: bool = False,
                 do_filecheck: bool = False) -> bool:
        """Checks if the texture files are local"""

        if workflow not in self.maps:
            return False

        map_types = self.get_map_types(workflow, prefer_16_bit, effective=True)
        tex_maps = self.get_maps(workflow, size, prefer_16_bit, effective=True)
        for tex_map in tex_maps:
            try:
                map_types.remove(tex_map.map_type)
            except ValueError:
                # deliberately surpressed
                # e.g. variants lead to type occurring multiple times
                pass
        # TODO(Andreas): if do_filecheck
        return len(map_types) == 0

    def get_workflow_list(self, get_local: bool = False) -> List[str]:
        """Returns list of all available workflows"""
        if get_local and self.maps is not None:
            get_from_dict = self.maps
        else:
            get_from_dict = self.map_descs
        return list(get_from_dict.keys())

    def get_workflow(self,
                     workflow: str = "REGULAR",
                     get_local: bool = False) -> Optional[str]:
        """Verifies workflow is available or returns fallback"""
        if get_local and self.maps is not None:
            get_from_dict = self.maps
        else:
            get_from_dict = self.map_descs

        if workflow in get_from_dict:
            return workflow
        elif "METALNESS" in get_from_dict:
            return "METALNESS"
        elif "SPECULAR" in get_from_dict:
            return "SPECULAR"
        elif "REGULAR" in get_from_dict:
            return "REGULAR"
        elif len(get_from_dict) >= 1:
            return list(get_from_dict.keys())[0]
        else:
            return None

    def get_size_list(self,
                      incl_watermarked: bool = False,
                      local_only: bool = False,
                      addon_convention: Optional[int] = None,
                      local_convention: Optional[int] = None,
                      map_preferences: Optional[Any] = None  # User MapPreferences
                      ) -> List[str]:
        """Returns list of all available sizes.

        Arguments:
        incl_watermarked: Set to True to have size WM considered
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: Allowed to be None, anytime.
        map_preferences: User map preferences, used for TEXTURES and if local_only;
        """

        if local_only:
            if addon_convention is None:
                raise ValueError("Called with local_only, but no addon convention")

            if local_convention is not None:
                convention_min = min(local_convention, addon_convention)
            else:
                convention_min = addon_convention
            sizes = set()
            for workflow in self.maps:
                for tex_map in self.maps[workflow]:
                    prefs_local = True
                    if map_preferences is not None and local_convention >= 1:
                        prefs_local = self.all_expected_maps_local(map_preferences,
                                                                   tex_map.size)
                    if tex_map.map_type.get_convention() <= convention_min and prefs_local:
                        sizes.add(tex_map.size)
        else:
            sizes = self.sizes.copy()

        sizes = sorted(list(sizes), key=sort_size_key)

        if not incl_watermarked and "WM" in sizes:
            sizes.remove("WM")

        return sizes

    def get_size(self,
                 size: str,
                 incl_watermarked: bool = False,
                 local_only: bool = False,
                 addon_convention: Optional[int] = None,
                 local_convention: Optional[int] = None
                 ) -> str:
        """Verifies size is available, otherwise returns closest one.

        Arguments:
        size: The size to check for
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!

        Raises:
        KeyError: If no size was found at all.
        ValueError: If local_only is True with addon_convention being None.
        """

        size_list = self.get_size_list(incl_watermarked=incl_watermarked,
                                       local_only=local_only,
                                       addon_convention=addon_convention,
                                       local_convention=local_convention)
        if size == "WM":
            return size
        elif size in size_list:
            return size

        size_best_fit = find_closest_size(size, size_list)
        if size_best_fit is None:
            raise KeyError(f"No suitable size found (request: {size})")
        return size_best_fit

    def get_variant_list(self) -> List[str]:
        """Returns list of all available variants"""

        return self.variants

    def get_lod_list(self) -> List[str]:
        """Returns list of all available LODs"""

        return self.lods

    def get_watermark_preview_url_list(self) -> Optional[List[str]]:
        """Returns list of URLs needed for watermarked material assignment"""

        return self.watermarked_urls

    def get_map_type_list(self,
                          workflow: str = "REGULAR",
                          effective: bool = True
                          ) -> List[MapType]:
        """Returns list of MapType needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        if workflow not in self.map_descs:
            raise KeyError(f"Workflow not found: {workflow}")

        map_descs = self.map_descs[workflow]
        return [
            map_desc.get_map_type(effective)
            for map_desc in map_descs
        ]

    def get_map_type_code_list(self, workflow: str = "REGULAR") -> List[str]:
        """Returns list of type_code needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        if workflow not in self.map_descs:
            raise KeyError(f"Workflow not found: {workflow}")

        map_descs = self.map_descs[workflow]

        # No UNKNOWN map should get here - they are filtered on the map_descs constructor ()
        return [map_desc.map_type_code for map_desc in map_descs
                if MapType.from_type_code(map_desc.map_type_code) != MapType.UNKNOWN]

    def get_maps_per_preferences(self,
                                 map_preferences: Any,
                                 filter_extensions: bool = False
                                 ) -> Tuple[List[TextureMapDesc], Dict[MapType, str]]:
        map_desc_per_prefs = []
        map_format_dict = {}
        for _map in map_preferences.texture_maps:
            if not _map.enabled:
                continue

            map_desc = self._get_map_desc_by_type(_map.map_type.get_effective(),
                                                  _map.selected,
                                                  filter_extensions=filter_extensions)
            if len(map_desc) == 0:
                continue

            map_desc_per_prefs.append(map_desc[0])
            map_format_dict[_map.map_type.get_effective()] = _map.selected
        return map_desc_per_prefs, map_format_dict

    def all_expected_maps_local(self, map_preferences: Any, size: str) -> bool:
        if map_preferences is None:
            return False

        _, map_types = self.get_maps_per_preferences(map_preferences)
        local_maps = self.get_maps("METALNESS",
                                   size,
                                   effective=True,
                                   map_preferences=map_preferences)
        return len(local_maps) == len(map_types.keys())

    def get_maps(self,
                 workflow: str = "REGULAR",
                 size: str = "1K",
                 lod: Optional[str] = None,
                 prefer_16_bit: bool = False,
                 suffix_list: List[str] = MAP_EXT_LOWER,
                 variant: Optional[str] = None,
                 effective: bool = True,
                 map_preferences: Any = None  # User MapPreferences
                 ) -> List[TextureMap]:
        """Returns list of Texture needed for workflow, size and map preferences."""

        if workflow not in self.maps:
            return []

        # "NONE" is the default value for backdoor import
        get_lod = lod not in [None, "NONE"]
        get_variant = variant is not None

        # TODO(Andreas): Use result of call below to check for any missing maps
        #                and then check for file alternatives.
        #                This change got put on hold after discussion with Patrick.
        # self.get_asset_map_type_list(asset_id,  # aaargh, we do not have this here :(
        #                              workflow=workflow,
        #                              prefer_16_bit=prefer_16_bit)

        tex_map_dict = {}  # {MapType : [TextureMap]}

        map_type_list = None
        if map_preferences is not None:
            _, map_type_list = self.get_maps_per_preferences(map_preferences)

        for tex_map in self.maps[workflow]:
            # TODO(Andreas): deliver fallback size maps in case map is not found
            if tex_map.size != size:
                continue
            # TODO(Andreas): deliver alternative lod, if not found?
            tex_has_lod = tex_map.lod is not None and tex_map.lod != "NONE"
            if get_lod and tex_has_lod and tex_map.lod != lod:
                continue

            tex_has_variant = tex_map.variant is not None
            if get_variant and tex_has_variant and tex_map.variant != variant:
                continue

            _map_type = tex_map.map_type.get_effective() if effective else tex_map.map_type

            if map_type_list is not None:
                if _map_type not in map_type_list.keys():
                    continue

                if not map_type_list[_map_type] in tex_map.file_format:
                    continue

            tex_map_dict[_map_type] = tex_map_dict.get(_map_type, []) + [tex_map]

        if map_type_list is None:
            tex_map_dict = self._convention_0_filter_maps(tex_map_dict,
                                                          prefer_16_bit)

        tex_maps = []
        # Get rid of multiple files for the same texture (e.g. .png and .psd)
        for map_type, tex_map_list in tex_map_dict.items():
            if len(tex_map_list) == 1:
                tex_map = tex_map_list[0]

                if len(suffix_list) == 1:
                    _, suffix = os.path.splitext(tex_map.filename)
                    if suffix == suffix_list[0]:
                        tex_maps.append(tex_map)
                else:
                    tex_maps.append(tex_map)
                continue
            found = False
            for suffix_preferred in suffix_list:
                for tex_map in tex_map_list:
                    _, suffix = os.path.splitext(tex_map.filename)
                    if suffix == suffix_preferred:
                        tex_maps.append(tex_map)
                        found = True
            if not found:
                tex_maps.append(tex_map_list[0])
                print(f"Multiple texture files per MapType ({map_type.name}), but none with preferred suffix!")

        return tex_maps

    def get_files(self, files_dict: Dict, effective: bool = True) -> None:
        """Adds all registered texture files to files_dict.
        {filename: attribute string}"""

        for workflow, tex_map_list in self.maps.items():
            for tex_map in tex_map_list:
                path = tex_map.get_path()
                map_type = tex_map.map_type.get_effective() if effective else tex_map.map_type
                tex_attr = f"{workflow}, {map_type.name}, {tex_map.size}"
                if tex_map.lod is not None:
                    tex_attr += f", {tex_map.lod}"
                if tex_map.variant is not None:
                    tex_attr += f", {tex_map.variant}"
                files_dict[path] = tex_attr

    def flush_local(self):
        """Resets all information about local files."""

        self.maps = {}

    def get_directory(self) -> Optional[str]:
        """Returns the directory of the asset. With current implementation,
        this is the directory of the first mesh (Model assets) or first
        texture (other asset types) found in asset's data.
        """

        if len(self.maps) == 0:
            return None

        for workflow in self.maps:
            for tex_map in self.maps[workflow]:
                if tex_map.size == "WM":
                    # WM previews are never in asset directory
                    continue
                return tex_map.directory

        return None


@dataclass
class Hdri(BaseTex):
    """Container object for an HDRI."""

    bg: Texture = None  # Background texture with single map of type JPG
    light: Texture = None  # Light texture with single map of type HDR

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "bg" not in d:
            raise KeyError("bg")
        if "light" not in d:
            raise KeyError("light")

        bg = Texture._from_dict(d["bg"])
        light = Texture._from_dict(d["light"])
        return cls(bg, light)

    def update(self, type_data_new, purge_maps: bool = False) -> None:
        """Updates Hdri data

        Args:
            type_data_new: Type Hdri, the instance to update from
            purge_maps: If True any existing map entries will be thrown away
        """

        if type_data_new is None:
            return
        self.bg.update(type_data_new.bg, purge_maps)
        self.light.update(type_data_new.light, purge_maps)

    def get_workflow_list(self, get_local: bool = False) -> List[str]:
        """Returns list of all available workflows"""

        # Currently assuming workflows are identical for light + bg
        return self.light.get_workflow_list(get_local=get_local)

    def get_workflow(
            self,
            workflow: str = "REGULAR",
            get_local: bool = False) -> Optional[str]:
        """Verifies workflow is available or returns fallback"""

        # Currently assuming workflows are identical for light + bg
        return self.light.get_workflow(workflow, get_local=get_local)

    def get_size_list(self,
                      incl_watermarked: bool = False,
                      local_only: bool = False,
                      addon_convention: Optional[int] = None,
                      local_convention: Optional[int] = None,
                      map_preferences: Optional[Any] = None  # User MapPreferences
                      ) -> List[str]:
        """Returns list of all available sizes.

        Arguments:
        incl_watermarked: Set to True to have size WM considered
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!
        map_preferences: User map preferences, used for TEXTURES and if local_only;
        """

        size_list = self.light.get_size_list(
            incl_watermarked, local_only, addon_convention, local_convention)
        size_list_bg = self.bg.get_size_list(
            incl_watermarked, local_only, addon_convention, local_convention)
        size_list.extend(size_list_bg)
        size_list = list(set(size_list))
        size_list = sorted(size_list, key=sort_size_key)
        return size_list

    def get_size(self,
                 size: str,
                 incl_watermarked: bool = False,
                 local_only: bool = False,
                 addon_convention: Optional[int] = None,
                 local_convention: Optional[int] = None
                 ) -> str:
        """Verifies size is available, otherwise returns closest one.

        Arguments:
        size: The size to check for
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!

        Raises:
        KeyError: If no size was found at all.
        ValueError: If local_only is True with addon_convention being None.
        """

        # Currently assuming sizes are identical for light + bg
        return self.bg.get_size(size,
                                incl_watermarked,
                                local_only,
                                addon_convention,
                                local_convention)

    def get_variant_list(self) -> List[str]:
        """Returns list of all available variants"""

        # Currently assuming variants are identical for light + bg
        return self.bg.get_variant_list()

    def get_watermark_preview_url_list(self) -> Optional[List[str]]:
        """Returns list of URLs needed for watermarked material assignment"""

        return self.bg.get_watermark_preview_url_list()

    def get_map_type_list(self, workflow: str = "REGULAR", effective: bool = True) -> List[MapType]:
        """Returns list of MapType needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        map_types = self.bg.get_map_type_list(effective=effective)
        map_types.extend(self.light.get_map_type_list(effective=effective))
        return map_types

    def get_map_type_code_list(self, workflow: str = "REGULAR") -> List[str]:
        """Returns list of type_code needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        map_codes = self.bg.get_map_type_code_list()
        map_codes.extend(self.light.get_map_type_code_list())
        return map_codes

    def get_maps(self,
                 workflow: str = "REGULAR",
                 size: str = "1K",
                 lod: Optional[str] = None,
                 prefer_16_bit: bool = False,
                 suffix_list: List[str] = MAP_EXT_LOWER,
                 variant: Optional[str] = None,
                 effective: bool = True,
                 map_preferences: Any = None  # User MapPreferences
                 ) -> List[TextureMap]:
        """Returns list of Texture needed for workflow and size.

        Raises: KeyError, if workflow not found.
        """

        tex_maps = self.bg.get_maps(
            workflow,
            size,
            lod,
            prefer_16_bit,
            suffix_list=suffix_list,
            variant=variant,
            effective=effective)
        tex_maps.extend(self.light.get_maps(
            workflow,
            size,
            lod,
            prefer_16_bit,
            suffix_list=suffix_list,
            variant=variant,
            effective=effective))
        return tex_maps

    def get_files(self, files_dict: Dict) -> None:
        """Adds all registered texture files to dict_files.
        {filename: attribute string}"""

        self.bg.get_files(files_dict)
        self.light.get_files(files_dict)

    def flush_local(self):
        """Resets all information about local files."""

        try:
            self.bg.flush_local()
        except AttributeError:
            pass  # no backgound texture
        try:
            self.light.flush_local()
        except AttributeError:
            pass  # no light texture

    def get_directory(self) -> Optional[str]:
        """Returns the directory of the asset. With current implementation,
        this is the the directory of the first mesh (Model assets) or first
        texture (other asset types) found in asset's data.
        """

        if self.light is None:
            return None

        return self.light.get_directory()


@dataclass
class Brush(BaseTex):
    """Container object for a Brush."""

    alpha: Texture  # Texture with single map of type ALPHA

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "alpha" not in d:
            raise KeyError("alpha")

        alpha = Texture._from_dict(d["alpha"])
        return cls(alpha)

    def update(self, type_data_new, purge_maps: bool = False) -> None:
        """Updates Brush data

        Args:
            type_data_new: Type Brush, the instance to update from
            purge_maps: If True any existing map entries will be thrown away
        """

        if type_data_new is None:
            return
        self.alpha.update(type_data_new.alpha, purge_maps)

    def get_workflow_list(self, get_local: bool = False) -> List[str]:
        """Returns list of all available workflows"""

        return self.alpha.get_workflow_list(get_local=get_local)

    def get_workflow(self,
                     workflow: str = "REGULAR",
                     get_local: bool = False) -> Optional[str]:
        """Verifies workflow is available or returns fallback"""

        return self.alpha.get_workflow(workflow, get_local=get_local)

    def get_size_list(self,
                      incl_watermarked: bool = False,
                      local_only: bool = False,
                      addon_convention: Optional[int] = None,
                      local_convention: Optional[int] = None,
                      map_preferences: Optional[Any] = None  # User MapPreferences
                      ) -> List[str]:
        """Returns list of all available sizes.

        Arguments:
        incl_watermarked: Set to True to have size WM considered
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!
        map_preferences: User map preferences, used for TEXTURES and if local_only;
        """

        return self.alpha.get_size_list(
            incl_watermarked, local_only, addon_convention, local_convention)

    def get_size(self,
                 size: str,
                 incl_watermarked: bool = False,
                 local_only: bool = False,
                 addon_convention: Optional[int] = None,
                 local_convention: Optional[int] = None
                 ) -> str:
        """Verifies size is available, otherwise returns closest one.

        Arguments:
        size: The size to check for
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!

        Raises:
        KeyError: If no size was found at all.
        ValueError: If local_only is True with addon_convention being None.
        """

        return self.alpha.get_size(size,
                                   incl_watermarked,
                                   local_only,
                                   addon_convention,
                                   local_convention)

    def get_variant_list(self) -> List[str]:
        """Returns list of all available variants"""

        return self.alpha.get_variant_list()

    def get_watermark_preview_url_list(self) -> Optional[List[str]]:
        """Returns list of URLs needed for watermarked material assignment"""

        return self.alpha.get_watermark_preview_url_list()

    def get_map_type_list(self, workflow="REGULAR", effective: bool = True) -> List[MapType]:
        """Returns list of MapType needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        return self.alpha.get_map_type_list(effective=effective)

    def get_maps(self,
                 workflow: str = "REGULAR",
                 size: str = "1K",
                 lod: Optional[str] = None,
                 prefer_16_bit: bool = False,
                 variant: Optional[str] = None,
                 effective: bool = True,
                 map_preferences: Any = None  # User MapPreferences
                 ) -> List[TextureMap]:
        """Returns list of Texture needed for workflow and size.

        Raises: KeyError, if workflow not found.
        """

        return self.alpha.get_maps(
            workflow,
            size,
            lod,
            prefer_16_bit,
            variant=variant,
            effective=effective)

    def get_files(self, files_dict: Dict) -> None:
        """Adds all registered texture files to dict_files.
        {filename: attribute string}"""

        self.alpha.get_files(files_dict)

    def flush_local(self):
        """Resets all information about local files."""

        try:
            self.alpha.flush_local()
        except AttributeError:
            pass  # no alpha texture

    def get_directory(self) -> Optional[str]:
        """Returns the directory of the asset. With current implementation,
        this is the the directory of the first mesh (Model assets) or first
        texture (other asset types) found in asset's data.
        """

        if self.alpha is None:
            return None

        return self.alpha.get_directory()


@dataclass
class ModelMesh:
    """Container object for a Model file.
    This class represents actual files on disc.
    Instances of this class exist only,
    if the respective files have been downloaded and found.
    """

    directory: str
    filename: str
    lod: str
    model_type: ModelType

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "model_type" not in d:
            raise KeyError("model_type")
        new = cls(**d)
        new.model_type = ModelType(new.model_type)
        return new

    def get_path(self):
        return os.path.join(self.directory, self.filename)


@dataclass
class Model(BaseAsset):
    """Container object for a Model."""

    # lods: List of lods, e.g., ["LOD0", "LOD2"]
    # Will be None, if "has_lods" is false,
    # otherwise empty list until populated.
    lods: Optional[Sequence[str]] = None
    meshes: Optional[Sequence[ModelMesh]] = None
    sizes: Optional[Sequence[str]] = None  # List of sizes, e.g., ["1K", "2K"]
    size_default: Optional[str] = None  # reported in included_resolution
    texture: Optional[Texture] = None
    variants: Optional[Sequence[str]] = None  # List of variants, e.g. ["VAR1", "VAR2"]

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "meshes" not in d:
            raise KeyError("meshes")
        if "texture" not in d:
            raise KeyError("texture")

        # Replace sub-dicts describing our class instances
        # with actual class instances
        mesh_list = d["meshes"]
        if mesh_list is not None:
            for idx_model, mesh_dict in enumerate(mesh_list):
                mesh_list[idx_model] = ModelMesh._from_dict(mesh_dict)

        tex_dict = d["texture"]
        if tex_dict is not None:
            d["texture"] = Texture._from_dict(tex_dict)

        new = cls(**d)
        return new

    def update(self, type_data_new, purge_maps: bool = False) -> None:
        """Updates Model data

        Args:
            type_data_new: Type Model, the instance to update from
            purge_maps: If True any existing map entries will be thrown away
        """

        if type_data_new is None:
            return
        self.meshes = _cond_set(type_data_new.meshes, self.meshes)
        self.lods = _cond_set(type_data_new.lods, self.lods)
        if self.lods is None or len(self.lods) == 0:
            self.lods = ["NONE"]
        self.sizes = _cond_set(type_data_new.sizes, self.sizes)
        self.variants = _cond_set(type_data_new.variants, self.variants)
        if self.texture is None:
            self.texture = type_data_new.texture
        else:
            self.texture.update(type_data_new.texture, purge_maps)

    def get_workflow_list(self, get_local: bool = True) -> List[str]:
        """Returns list of all available workflows"""

        if self.texture is None:
            return []
        # Model has no TextureMapDescs in Texture
        return list(self.texture.get_workflow_list(get_local=get_local))

    def get_workflow(self,
                     workflow: str = "REGULAR",
                     get_local: bool = False) -> Optional[str]:
        """Verifies workflow is available or returns fallback"""

        if self.texture is None:
            return None
        return self.texture.get_workflow(workflow, get_local=get_local)

    def get_size_list(self,
                      incl_watermarked: bool = False,
                      local_only: bool = False,
                      addon_convention: Optional[int] = None,
                      local_convention: Optional[int] = None,
                      map_preferences: Optional[Any] = None  # User MapPreferences
                      ) -> List[str]:
        """Returns list of all available sizes.

        Arguments:
        incl_watermarked: Set to True to have size WM considered
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!
        map_preferences: User map preferences, used for TEXTURES and if local_only;
        """

        incl_watermarked = False  # No watermarked textures for Models
        if local_only:
            if self.texture is None:
                return []
            return self.texture.get_size_list(
                incl_watermarked, local_only, addon_convention, local_convention)
        else:
            return self.sizes

    def get_size(self,
                 size: str,
                 incl_watermarked: bool = False,
                 local_only: bool = False,
                 addon_convention: Optional[int] = None,
                 local_convention: Optional[int] = None
                 ) -> str:
        """Verifies size is available, otherwise returns closest one.

        Arguments:
        size: The size to check for
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!
        local_convention: May only be None, if local_only is False!

        Raises:
        KeyError: If no size was found at all.
        ValueError: If local_only is True with addon_convention being None.
        """

        if self.texture is not None:
            return self.texture.get_size(size,
                                         incl_watermarked,
                                         local_only,
                                         addon_convention,
                                         local_convention)

        # Not local
        size = find_closest_size(size, self.sizes)
        return size

    def get_variant_list(self) -> List[str]:
        """Returns list of all available variants"""
        if self.texture is None:
            return []
        return self.texture.get_variant_list()

    def get_watermark_preview_url_list(self) -> Optional[List[str]]:
        """Returns list of URLs needed for watermarked material assignment"""

        if self.texture is None:
            return []
        return self.texture.get_watermark_preview_url_list()

    def get_map_type_list(self, workflow: str = "", effective: bool = True) -> List[MapType]:
        """Returns list of MapType needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        if self.texture is None:
            return []
        return self.texture.get_map_type_list(workflow, effective=effective)

    def filter_mesh_maps(
            self,
            asset_maps: List[TextureMap],
            mesh_name: str,
            original_material_name: str = ""
    ) -> Tuple[bool, str, List[TextureMap]]:
        """Filters the maps in asset map list to get the corresponding map
        set for a given mesh (FBX Importing).

        NOTE: Currently filtering by placeholder material name and,
        if not material found, by the mesh name.

        TODO(Joao): add filter for variants"""

        mesh_maps = []

        name_mat_imported_lower = original_material_name.lower()
        ends_remastered = name_mat_imported_lower.endswith("_mat")
        contains_remastered = "_mat_" in name_mat_imported_lower

        # if "_mat" in the original fbx material, consider remastered asset
        if ends_remastered or contains_remastered:
            pos_remastered = name_mat_imported_lower.rfind("_mat", 1)
            base_map_name = original_material_name[:pos_remastered]
        else:
            base_map_name = mesh_name.split("_")[0]

        for _tex in asset_maps:
            if base_map_name.lower() in _tex.filename.lower():
                mesh_maps.append(_tex)

        if len(mesh_maps) == 0:
            return False, base_map_name, asset_maps

        return True, base_map_name, mesh_maps

    def get_map_type_code_list(self, workflow: str = "REGULAR") -> List[str]:
        """Returns list of type_code needed for a workflow.

        Raises: KeyError, if workflow not found.
        """

        map_codes = self.texture.get_map_type_code_list(workflow)
        return map_codes

    def get_maps(self,
                 workflow: str = "REGULAR",
                 size: str = "1K",
                 lod: Optional[str] = None,
                 prefer_16_bit: bool = False,
                 suffix_list: List[str] = MAP_EXT_LOWER,
                 variant: Optional[str] = None,
                 effective: bool = True,
                 map_preferences: Any = None  # User MapPreferences
                 ) -> List[TextureMap]:
        """Returns list of Texture needed for workflow and size.

        Raises: KeyError, if workflow not found.
        """

        if self.texture is None:
            return []
        return self.texture.get_maps(
            workflow,
            size,
            lod,
            prefer_16_bit,
            suffix_list=suffix_list,
            variant=variant,
            effective=effective)

    def get_lod_list(self) -> List[str]:
        """Returns list of all available LODs"""

        return self.lods

    def find_closest_lod(self, lod: str) -> Optional[str]:
        """Tries to find an alternative LOD.
        The distance inside the LODS list is used as metric of proximity.
        """

        if lod == "NONE":
            lod = "LOD1"
        idx_lod_wanted = LODS.index(lod)
        dist_min = len(LODS)
        lod_best_fit = None
        for idx_lod, lod_test in enumerate(LODS):
            dist = abs(idx_lod_wanted - idx_lod)
            if lod_test in self.lods and dist < dist_min:
                dist_min = dist
                lod_best_fit = lod_test
        if lod_best_fit is None:
            return self.lods[0]
        return lod_best_fit

    def get_lod(self, lod: str) -> Optional[str]:
        """Verifies LOD is available, otherwise returns the next available."""

        if lod in self.lods:
            return lod
        lod_best_fit = self.find_closest_lod(lod)
        return lod_best_fit

    def get_native_mesh(self, software_ext: str, renderer: str) -> List:
        """Returns native meshes of the given DCC extension and Renderer."""

        if self.meshes is None:
            return []

        meshes = []
        for mesh in self.meshes:
            filename, file_ext = os.path.splitext(mesh.filename)
            match_renderer = renderer.lower() in filename.lower()
            match_ext = file_ext.lower() == software_ext.lower()

            if not match_ext or not match_renderer:
                continue

            meshes.append(mesh)

        return meshes

    def has_mesh(self,
                 model_type: Optional[ModelType],
                 native_only: bool = False,
                 renderer: Optional[str] = None
                 ) -> bool:
        """Returns True, if a mesh file exists."""

        if self.meshes is None:
            return False

        for mesh in self.meshes:
            has_desired = mesh.model_type == model_type
            if has_desired and model_type != ModelType.FBX and renderer is not None:
                has_desired = renderer.lower() in mesh.filename.lower()
            has_fbx = not native_only and mesh.model_type == ModelType.FBX
            if has_desired or has_fbx:
                return True
        return False

    def get_mesh(self,
                 lod: str = "LOD1",
                 model_type: Optional[ModelType] = None
                 ) -> List[ModelMesh]:
        """Returns meshes with the given LOD."""

        if self.meshes is None:
            return []

        if lod is None:
            lod = "LOD1"
        meshes = []
        for mesh in self.meshes:
            if model_type is not None and mesh.model_type != model_type:
                continue
            if mesh.lod != lod:
                continue
            meshes.append(mesh)
        return meshes

    def get_files(self, files_dict: Dict) -> None:
        """Adds all registered files (textures and meshes) to dict_files.
        {filename: attribute string}"""

        for mesh in self.meshes:
            path = mesh.get_path()
            mesh_attr = f"{mesh.model_type.name}"
            if mesh.lod is not None:
                mesh_attr += f", {mesh.lod}"
            files_dict[path] = mesh_attr

        self.texture.get_files(files_dict)

    def flush_local(self):
        """Resets all information about local files."""

        self.meshes = None
        try:
            self.texture.flush_local()
        except AttributeError:
            pass  # no texture

    def get_directory(self) -> Optional[str]:
        """Returns the directory of the asset. With current implementation,
        this is the the directory of the first mesh (Model assets) or first
        texture (other asset types) found in asset's data.
        """

        if len(self.meshes) == 0:
            return None

        return self.meshes[0].directory


@dataclass
class AssetData:
    """Container object for an asset."""

    asset_id: int
    asset_type: AssetType
    # asset_name: e.g. for filenames, key "asset_name" in ApiResponse
    asset_name: str
    # display_name: Beauty name for UI display, key "name" in ApiResponse
    display_name: Optional[str] = None
    old_asset_names: Optional[List[str]] = None
    categories: Optional[Sequence[str]] = None
    url: Optional[str] = None
    slug: Optional[str] = None
    credits: Optional[int] = None  # key "credit" in ApiResponse
    # preview: Optional[str] = None
    thumb_urls: Optional[Sequence[str]] = None

    local_directories: Optional[List[str]] = None

    cloudflare_thumb_urls: Optional[Sequence[AssetThumbnail]] = None

    published_at: Optional[str] = None
    # is_local: None until proven true or false.
    # Indicates locality only for at least one "flavour".
    is_local: Optional[bool] = None
    # UTC, seconds since epoch
    downloaded_at: Optional[int] = None
    # is_purchased: None until proven true or false.
    is_purchased: Optional[bool] = None
    # is_recent_downloaded: None until proven true or false
    # (new flag after implementing recent downloads filter in addon-first)
    is_recent_downloaded: Optional[bool] = None
    # UTC, seconds since epoch
    purchased_at: Optional[int] = None
    # render_custom_schema: Filled with what ever meta data
    # ApiResponse contains for this key.
    # TODO(Joao): Remove Render Custom Schema from this class.
    #  Render custom schema was removed from asset dict api, specifications
    #  key was added here as substitute - to discuss if we should keep both;
    render_custom_schema: Optional[Dict] = None
    specifications: Optional[Dict] = None

    api_convention: Optional[int] = None
    local_convention: Optional[int] = None

    # Treat below as a "one of",
    # where only set if the given asset type is assigned.
    # Best retrieved via get_type_data().
    brush: Optional[Brush] = None
    hdri: Optional[Hdri] = None
    model: Optional[Model] = None
    texture: Optional[Texture] = None

    # Not preserved, when loaded from disk
    state: AssetState = field(default_factory=lambda: AssetState())
    runtime: AssetDataRuntime = field(default_factory=lambda: AssetDataRuntime())

    @classmethod
    def _from_dict(cls, d: Dict):
        """Alternate constructor,
        used after loading AssetIndex from JSON to reconstruct class.
        """

        if "asset_type" not in d:
            raise KeyError("asset_type")

        new = cls(**d)
        # TODO(Andreas): Load new AssetThumbnail class
        new.asset_type = AssetType(new.asset_type)
        if new.brush is not None:
            new.brush = Brush._from_dict(new.brush)
        elif new.hdri is not None:
            new.hdri = Hdri._from_dict(new.hdri)
        elif new.model is not None:
            new.model = Model._from_dict(new.model)
        elif new.texture is not None:
            new.texture = Texture._from_dict(new.texture)

        cf_thumb_urls = []
        for _dict in new.cloudflare_thumb_urls:
            cf_thumb_urls.append(AssetThumbnail._from_dict(_dict))
        new.cloudflare_thumb_urls = cf_thumb_urls

        new.state = AssetState()
        new.runtime = AssetDataRuntime()

        return new

    def get_type_data(self) -> Union[Texture, Hdri, Brush, Model]:
        """Returns either brush, hdri, model or
        texture based on asset's type.
        """

        if self.asset_type == AssetType.BRUSH:
            return self.brush
        elif self.asset_type == AssetType.HDRI:
            return self.hdri
        elif self.asset_type == AssetType.MODEL:
            return self.model
        elif self.asset_type == AssetType.SUBSTANCE:
            raise NotImplementedError
        elif self.asset_type == AssetType.TEXTURE:
            return self.texture
        elif self.asset_type == AssetType.UNSUPPORTED:
            raise NotImplementedError
        else:
            raise TypeError

    def get_display_details_data(self) -> Dict[str, str]:
        data_dict = {}
        if self.asset_type == AssetType.TEXTURE:
            texture = self.get_type_data()
            dimensions = texture.real_world_dimension
            if dimensions is not None:
                unit = "cm"
                x = dimensions[0]
                y = dimensions[1]
                if x > 99 or y > 99:
                    unit = "m"
                    x = dimensions[0] / 100
                    y = dimensions[1] / 100

                data_dict[_t("Physical Size")] = f"{str(x)} x {str(y)}{unit}"
            data_dict[_t("Resolutions")] = ", ".join(texture.sizes)

            map_names = []
            for _map in list(texture.map_descs.values())[0]:
                description = MapType.from_type_code(_map.map_type_code).get_description()
                if description is None:
                    map_name_str = _map.display_name
                else:
                    map_name_str = description.display_name
                map_names.append(map_name_str)
            data_dict[_t("Maps")] = ", ".join(map_names)
            if texture.creation_method is not None:
                method_str = CREATION_METHODS.get(texture.creation_method).method
                data_dict[_t("Creation Method")] = method_str

        elif self.asset_type == AssetType.MODEL:
            specs = self.specifications
            tech_data = specs if specs is not None else {}
            lod_tri_count = tech_data.get("lods", {})

            meshes = tech_data.get("meshes", None)
            source_tri_count = lod_tri_count.get("SOURCE", None)
            dimensions = tech_data.get("physical_size_cm", {})
            incl_res = self.render_custom_schema.get("included_resolution")

            # TODO(Joao): The following lines are for mark dimensions strings
            #  to be translated;
            height_str = _m("Height (cm)")  # noqa
            width_str = _m("Width (cm)")  # noqa
            depth_str = _m("Depth (cm)")  # noqa

            for key, value in dimensions.items():
                key_title = _t(key.title())
                data_dict[f"{key_title} (cm)"] = value

            if meshes is not None:
                data_dict[_t("Mesh Count")] = meshes
            if source_tri_count is not None:
                data_dict[_t("Source Polygon Count")] = source_tri_count
            if incl_res is not None:
                data_dict[_t("Included Resolution")] = incl_res
        elif self.asset_type == AssetType.HDRI:
            hdr = self.get_type_data()
            data_dict[_t("Resolutions")] = ", ".join(hdr.light.sizes)
        return data_dict

    def append_local_dir(self, directory: str) -> None:
        if self.local_directories is None:
            self.local_directories = [directory]
        elif directory not in self.local_directories:
            self.local_directories.append(directory)

    def get_local_directories(self,
                              sort_last_str: Optional[str] = None,
                              get_all: bool = False,
                              max_dirs: int = 3
                              ) -> Optional[List[str]]:
        if get_all:
            max_dirs = len(self.local_directories)

        if sort_last_str is None:
            return self.local_directories[0:max_dirs]

        # Finds the directory to be set in the end and append it last
        # (e.g. for setting primary lib in the end to be the last one opened)
        final_dir = None
        sorted_list = []
        for _dir in self.local_directories:
            if sort_last_str in _dir:
                final_dir = _dir
            else:
                sorted_list.append(_dir)
        if final_dir is not None:
            sorted_list = sorted_list[0:(max_dirs - 1)]
            sorted_list.append(final_dir)

        return sorted_list[0:max_dirs]

    def update(self, asset_data_new, purge_maps: bool = False) -> None:
        """Updates asset data from another asset data,
        which may only be partially filled.

        Args:
        asset_data_new: Type AssetData, the instance to update from
        purge_maps: If True any existing map entries will be thrown away
        """

        self.display_name = _cond_set(asset_data_new.display_name,
                                      self.display_name)
        self.old_asset_names = _cond_set(asset_data_new.old_asset_names,
                                         self.old_asset_names)
        # self.asset_id is not meant to be changed
        # self.type is not meant to be changed
        # self.asset_name is not meant to be changed   # TODO(Andreas): I wonder, if this is still true, since we have old_asset_names...
        # self.convention is not meant to be changed
        self.local_convention = _cond_set(asset_data_new.local_convention,
                                          self.local_convention)
        self.categories = _cond_set(asset_data_new.categories, self.categories)
        self.url = _cond_set(asset_data_new.url, self.url)
        self.slug = _cond_set(asset_data_new.slug, self.slug)
        self.published_at = _cond_set(asset_data_new.published_at,
                                      self.published_at)
        self.thumb_urls = _cond_set(asset_data_new.thumb_urls,
                                    self.thumb_urls)
        self.is_local = _cond_set(asset_data_new.is_local, self.is_local)
        self.downloaded_at = _cond_set(asset_data_new.downloaded_at,
                                       self.downloaded_at)
        self.is_purchased = _cond_set(asset_data_new.is_purchased,
                                      self.is_purchased)
        self.purchased_at = _cond_set(asset_data_new.purchased_at,
                                      self.purchased_at)
        self.render_custom_schema = _cond_set(
            asset_data_new.render_custom_schema, self.render_custom_schema)
        self.specifications = _cond_set(asset_data_new.specifications,
                                        self.specifications)

        self.get_type_data().update(asset_data_new.get_type_data(), purge_maps)

    def flush_state(self):
        """Reset all Download and Purchase states."""
        self.state = AssetState()

    def flush_local(self):
        """Resets all information about local files."""

        self.is_local = False
        self.get_type_data().flush_local()

    def _convert_timestamp(self, ts: Optional[str]) -> str:
        """Returns formatted time from timestamp in timezone UTC."""

        if ts is None:
            return str(ts)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        time_formatted = dt.isoformat()
        return time_formatted

    def get_purchase_time(self) -> str:
        """Returns time of purchase as string."""

        return self._convert_timestamp(self.purchased_at)

    def get_download_time(self) -> str:
        """Returns time of download as string."""

        return self._convert_timestamp(self.downloaded_at)

    def is_backplate(self) -> bool:
        """Returns True, if the asset is a backplate/backdrop."""

        if self.asset_type != AssetType.TEXTURE:
            return False
        asset_name_low = self.asset_name.lower()
        return any(
            asset_name_low.startswith(vS) for vS in ["backdrop", "backplate"])

    def get_current_size(self,
                         size_pref: str,
                         local_only: bool,
                         addon_convention: Optional[int] = None
                         ) -> str:
        """Returns a (optionally) stored size.

        For example to use for the main import button after download of a
        non-default size. If no stored size is available, the closest size
        (based on availability and locality) will be returned.

        Arguments:
        size_pref: The size set by user in preferences
        local_only: Set to True to only get locally available sizes
        addon_convention: May only be None, if local_only is False!

        Raises:
        ValueError: If local_only is True with addon_convention being None.
        """

        size_current = self.runtime.get_current_size()
        size = size_current if size_current is not None else size_pref

        asset_type_data = self.get_type_data()
        if asset_type_data is not None:
            size = asset_type_data.get_size(size,
                                            False,
                                            local_only,
                                            addon_convention,
                                            self.get_convention(local=True))

        return size

    def get_directory(self) -> Optional[str]:
        """Returns the directory of the asset. With current implementation,
        this is the the directory of the first mesh (Model assets) or first
        texture (other asset types) found in asset's data.
        """

        asset_type_data = self.get_type_data()
        if asset_type_data is None:
            return None
        return asset_type_data.get_directory()

    def get_asset_directory(self) -> Optional[str]:
        dir_asset = self.get_directory()
        # So far, this is a path for a texture. Fine for convention 0, where
        # everything is in a single directory. But for convention 1 these are
        # located in size subfolders.
        if self.api_convention == 1 and dir_asset is not None:
            dir_asset = os.path.dirname(dir_asset)
        return dir_asset

    def get_convention(self, local: bool = False) -> Optional[int]:
        """Returns the convention of the asset."""

        if local:
            return self.local_convention  # may be none, if no local files
        else:
            return self.api_convention  # should never be None

    def get_material_name(self,
                          size: str,
                          variant: Optional[str] = None,
                          renderer: Optional[str] = None) -> str:
        """Returns a suggested material name for a given size and optional
        renderer.
        """

        name_mat = self.asset_name
        if size not in name_mat:
            name_mat += f"_{size}"
        if variant is not None:
            name_mat += f"_{variant}"
        if renderer is not None:
            name_mat += f"_{renderer}"
        return name_mat

    def create_dummy_type_data(
            self, asset_type: Optional[AssetType] = None) -> None:
        """Creates a dummy type data. For example to be used in case we run
        into an exception during evaluation of server side asset data and thus
        can't build complete data structures.
        """

        if self.get_type_data() is not None:
            return
        if asset_type is None:
            asset_type = self.asset_type

        tex_dummy = Texture(maps={}, map_descs={}, sizes=["1K"])
        if asset_type == AssetType.BRUSH:
            self.brush = Brush(alpha=tex_dummy)
        elif asset_type == AssetType.HDRI:
            tex_dummy_2 = Texture(maps={}, map_descs={}, sizes=["1K"])
            self.hdri = Hdri(light=tex_dummy, bg=tex_dummy_2)
        elif asset_type == AssetType.MODEL:
            self.model = Model(texture=tex_dummy)
        elif asset_type == AssetType.TEXTURE:
            self.texture = tex_dummy

    def is_new(self) -> bool:
        """Returns True if the asset was published within the last 30 days.

        Returns:
            bool: True if the asset is new (< 30 days old), False otherwise
        """
        if not self.published_at:
            return False
        days_threshold = 30
        # Convert timestamp to datetime object
        published_datetime = datetime.fromtimestamp(self.published_at, tz=timezone.utc)
        days_old = (datetime.now(timezone.utc) - published_datetime).days
        return days_old <= days_threshold


# Currently constants are defined here at the end,
# as some require above classes to be defined.
API_TYPE_TO_ASSET_TYPE = {"Brushes": AssetType.BRUSH,
                          "HDRS": AssetType.HDRI,
                          "Models": AssetType.MODEL,
                          "Substances": AssetType.SUBSTANCE,
                          "Textures": AssetType.TEXTURE,
                          "Unsupported": AssetType.UNSUPPORTED
                          }

ASSET_TYPE_TO_CATEGORY_NAME = {AssetType.BRUSH: "Brushes",
                               AssetType.HDRI: "HDRIs",
                               AssetType.MODEL: "Models",
                               AssetType.SUBSTANCE: "Substances",
                               AssetType.TEXTURE: "Textures",
                               AssetType.UNSUPPORTED: "Unsupported",
                               }

ASSET_TYPE_TO_URL_PATH = {AssetType.BRUSH: "brush",
                          AssetType.HDRI: "hdr",
                          AssetType.MODEL: "model",
                          AssetType.SUBSTANCE: "substance",
                          AssetType.TEXTURE: "texture",
                          AssetType.UNSUPPORTED: "unsupported",
                          }
