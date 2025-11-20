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

import os
import subprocess
import time
from typing import List

import bpy


def f_Ex(vPath):
    return os.path.exists(vPath)


def f_FName(vPath):
    return os.path.splitext(os.path.basename(vPath))[0]


def f_FExt(vPath):
    return os.path.splitext(os.path.basename(vPath))[1].lower()


def f_FNameExt(vPath):
    vSplit = list(os.path.splitext(os.path.basename(vPath)))
    vSplit[1] = vSplit[1].lower()
    return vSplit


def f_FSplit(vPath):
    vSplit = list(os.path.splitext(vPath))
    vSplit[1] = vSplit[1].lower()
    return vSplit


def f_MDir(vPath):
    if f_Ex(vPath):
        return

    try:
        os.makedirs(vPath)
    except Exception as e:
        print("Failed to create directory: ", e)


def timer(fn):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()

        result = fn(*args, **kwargs)

        end_time = time.perf_counter()
        duration = round(end_time - start_time, 2)
        if duration > 60:
            msec = str(duration - int(duration)).split('.')[1]
            duration = f"{time.strftime('%M:%S', time.gmtime(duration))}.{msec}"

        print(f"{fn.__name__} : {duration}s")

        return result
    return wrapper


def construct_model_name(asset_name, size, lod):
    """Constructs the model name from the given inputs."""

    if lod:
        model_name = f"{asset_name}_{size}_{lod}"
    else:
        model_name = f"{asset_name}_{size}"
    return model_name


def shorten_label(label: str, max_len: int) -> str:
    """Shortens the given label by replacing the center part with '...'"""

    if len(label) <= max_len:
        return label

    overlen = (len(label) - (max_len - 3)) // 2
    center = len(label) // 2
    return label[:center - overlen] + "..." + label[center + overlen:]


def open_dir(directory: str) -> bool:
    """Attempts to open a directory in a cross-platform way."""

    directory_norm = os.path.normpath(directory)
    did_open = False
    try:
        os.startfile(directory_norm)
        did_open = True
    except Exception:
        # TODO(Andreas): I somehow doubt, the following is really necessary.
        #                Neither P4Max nor P4Cinema jump through such hoops.
        try:
            subprocess.Popen(("open", directory_norm))
            did_open = True
        except Exception:
            try:
                subprocess.Popen(("xdg-open", directory_norm))
                did_open = True
            except Exception:
                pass
    return did_open


def is_cycles() -> bool:
    """Returns True, if Cycles render engine is enabled."""

    return bpy.context.scene.render.engine == "CYCLES"


def is_eevee() -> bool:
    """Returns True, if Eevee render engine is enabled."""

    return bpy.context.scene.render.engine == "BLENDER_EEVEE"


def is_eevee_next() -> bool:
    """Returns True, if Eevee render engine is enabled."""

    # Blender 4.2's Eevee Next supports for example displacement
    # (but not adaptive)
    return bpy.context.scene.render.engine == "BLENDER_EEVEE_NEXT"


def set_colorspace(img: bpy.types.Image, colorspace: str = "") -> None:
    """Sets an image's colorspace.

    It does so in a try statement, because some people might actually
    replace the default colorspace settings, and it literally can't be
    guessed what these people use, even if it will mostly be the filmic addon.
    """
    try:
        if colorspace == "":
            colorspace = guess_colorspace()

        if colorspace == "Non-Color":
            img.colorspace_settings.is_data = True
        else:
            img.colorspace_settings.name = colorspace
    except Exception as e:
        print(f"Colorspace {colorspace} not found: {e}")


def guess_colorspace() -> str:
    display_device = bpy.context.scene.display_settings.display_device
    if display_device == "sRGB":
        return "sRGB"
    if display_device == "ACES":
        return "aces"


def img_to_preview(img: bpy.types.Image, copy_original: bool = False) -> None:
    """Ensures an image's preview is identical to the image."""

    if bpy.app.version[0] >= 3:
        img.preview_ensure()
    if not copy_original:
        return
    if img.preview.image_size != img.size:
        img.preview.image_size = (img.size[0], img.size[1])
        img.preview.image_pixels_float = img.pixels[:]


def remove_alpha(img: bpy.types.Image, color_bg: List[float]) -> None:
    """Replaces transparent parts of an image with a new background color."""

    pixels = list(img.pixels)
    for _idx in range(0, len(pixels), 4):
        idx_alpha = _idx + 3
        alpha = pixels[idx_alpha]
        if alpha < 0.95:
            r = min(color_bg[0] * (1 - alpha) + pixels[_idx] * alpha, 1.0)
            g = min(color_bg[1] * (1 - alpha) + pixels[_idx + 1] * alpha, 1.0)
            b = min(color_bg[2] * (1 - alpha) + pixels[_idx + 2] * alpha, 1.0)

            pixels[_idx:_idx + 3] = [r, g, b]
            pixels[idx_alpha] = 1.0  # no transparency
    img.pixels = pixels
    img.update()


def load_image(
    name: str,
    path: str,
    *,
    hidden: bool = True,
    do_identical_preview: bool = True,
    do_set_colorspace: bool = True,
    do_remove_alpha: bool = False,
    color_bg: List[float] = [0.0, 0.0, 0.0, 0.0],
    force: bool = False
) -> bpy.types.Image:
    """Loads an image from disk.

    Arguments:
    hidden: Mark the image data block as hidden (prepending . to its name)
    do_identical_preview: Copies the original image into image's preview.
    do_set_colorspace: Sets color space of image to sRGB or ACES, if none.
    do_remove_alpha: Replaces transparent parts with a new background color.
    force: Do load the image, even if a data block with that name already
           exists.
    """

    if hidden and not name.startswith("."):
        name = f".{name}"  # hidden
    img = bpy.data.images.get(name)
    if img is not None and not force:
        return img

    img = bpy.data.images.load(path, check_existing=True)
    if img is None:
        return None

    img.name = name
    if do_set_colorspace:
        set_colorspace(img)
    if do_remove_alpha:
        remove_alpha(img, color_bg)
    if do_identical_preview:
        img_to_preview(img, copy_original=True)

    return img


def copy_simple_property_group(
    source: bpy.types.PropertyGroup,
    target: bpy.types.PropertyGroup
) -> None:
    """Copies property values from one PropertyGroup to another.

    From: https://blenderartists.org/t/duplicating-pointerproperty-propertygroup-and-collectionproperty/1419096
    """

    if not hasattr(source, "__annotations__"):
        return
    for prop_name in source.__annotations__.keys():
        try:
            setattr(target, prop_name, getattr(source, prop_name))
        except (AttributeError, TypeError):
            pass


def compare_simple_property_group(
    group_a: bpy.types.PropertyGroup,
    group_b: bpy.types.PropertyGroup
) -> bool:
    """Compares property values of two PropertyGroups and
    returns True if equal.
    """

    if not hasattr(group_a, "__annotations__"):
        return False
    if not hasattr(group_b, "__annotations__"):
        return False

    for prop_name in group_a.__annotations__.keys():
        try:
            val_a = getattr(group_a, prop_name)
            val_b = getattr(group_b, prop_name)
            if val_a != val_b:
                return False
        except (AttributeError, TypeError):
            return False
    return True
