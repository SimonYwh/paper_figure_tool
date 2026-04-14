from __future__ import annotations

import os
import sys

from PIL import Image, ImageFile, ImageOps
from PIL.ImageQt import ImageQt
from PySide6.QtGui import QPixmap

ImageFile.LOAD_TRUNCATED_IMAGES = True

_TIFF_EXTS = {".tif", ".tiff"}
_PHOTOMETRIC_TAG = 262


_DEBUG_IMAGE_LOADING = os.environ.get("PFT_DEBUG_IMAGE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_DEBUG_IMAGE_LOG_FILE = os.environ.get("PFT_DEBUG_IMAGE_FILE", "pft_image_debug.log").strip()


def _dbg(message: str) -> None:
    if not _DEBUG_IMAGE_LOADING:
        return

    line = f"[ImageDebug] {message}\n"

    try:
        sys.__stderr__.write(line)
        sys.__stderr__.flush()
    except Exception:
        pass

    if _DEBUG_IMAGE_LOG_FILE:
        try:
            with open(_DEBUG_IMAGE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def _safe_extrema(im: Image.Image):
    try:
        return im.getextrema()
    except Exception:
        return None


def _is_grayscale_like(im: Image.Image) -> bool:
    mode = str(getattr(im, "mode", "")).upper()
    if mode in {"1", "L", "I", "F", "I;16", "I;16L", "I;16B", "I;16N"}:
        return True
    try:
        bands = im.getbands()
        return isinstance(bands, tuple) and len(bands) == 1
    except Exception:
        return False


def _to_display_l_channel(im: Image.Image) -> Image.Image:
    mode = str(getattr(im, "mode", "")).upper()

    if mode in {"1", "L"}:
        return im.convert("L")

    if mode in {"I", "F", "I;16", "I;16L", "I;16B", "I;16N"}:
        i_img = im.convert("I")
        extrema = _safe_extrema(i_img)
        if not (isinstance(extrema, tuple) and len(extrema) == 2):
            return i_img.convert("L")

        mn = int(extrema[0])
        mx = int(extrema[1])
        if mx <= mn:
            fill_v = max(0, min(255, mn // 256))
            return Image.new("L", i_img.size, color=fill_v)

        scale = 255.0 / float(mx - mn)
        offset = -float(mn) * scale
        stretched = i_img.point(lambda x: x * scale + offset)
        return stretched.convert("L")

    return im.convert("L")


def _extract_photometric_interpretation(im: Image.Image) -> int | None:
    values: list[object] = []

    tag_v2 = getattr(im, "tag_v2", None)
    if tag_v2 is not None:
        try:
            values.append(tag_v2.get(_PHOTOMETRIC_TAG))
        except Exception:
            pass

    tag = getattr(im, "tag", None)
    if tag is not None:
        try:
            values.append(tag.get(_PHOTOMETRIC_TAG))
        except Exception:
            pass

    for v in values:
        if isinstance(v, (tuple, list)):
            if not v:
                continue
            v = v[0]
        try:
            return int(v)
        except Exception:
            continue
    return None


def _is_tiff_white_is_zero(im: Image.Image, path: str) -> bool:
    fmt = str(getattr(im, "format", "")).upper()
    ext = os.path.splitext(path)[1].lower()
    if fmt != "TIFF" and ext not in _TIFF_EXTS:
        return False
    return _extract_photometric_interpretation(im) == 0


def _prepare_rgb_for_display(im: Image.Image, path: str) -> Image.Image:
    src_mode = str(getattr(im, "mode", ""))
    src_fmt = str(getattr(im, "format", ""))
    src_size = tuple(getattr(im, "size", (0, 0)))
    src_extrema = _safe_extrema(im)
    photometric = _extract_photometric_interpretation(im)

    _dbg(
        "open "
        f"path={path!r} format={src_fmt!r} mode={src_mode!r} size={src_size} "
        f"photometric={photometric} extrema={src_extrema}"
    )

    try:
        im = ImageOps.exif_transpose(im)
    except Exception as e:
        _dbg(f"exif_transpose_failed path={path!r} err={e}")

    white_is_zero = _is_tiff_white_is_zero(im, path)
    gray_like = _is_grayscale_like(im)
    _dbg(
        f"photometric_decision path={path!r} white_is_zero={white_is_zero} gray_like={gray_like} mode={getattr(im, 'mode', None)!r}"
    )

    if gray_like:
        l_img = _to_display_l_channel(im)
        if white_is_zero:
            l_img = ImageOps.invert(l_img)
            action = "gray_dynamic_scale_then_invert"
        else:
            action = "gray_dynamic_scale"

        out = Image.merge("RGB", (l_img, l_img, l_img))
        _dbg(
            "convert_result "
            f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
            f"out_extrema={_safe_extrema(out)} action={action!r}"
        )
        return out

    if white_is_zero:
        try:
            out = ImageOps.invert(im.convert("RGB"))
            _dbg(
                "convert_result "
                f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
                f"out_extrema={_safe_extrema(out)} action='invert_after_rgb'"
            )
            return out
        except Exception as e:
            _dbg(f"invert_failed path={path!r} err={e}")

    out = im.convert("RGB")
    _dbg(
        "convert_result "
        f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
        f"out_extrema={_safe_extrema(out)} action='direct_rgb'"
    )
    return out


def load_image_thumb_qimage(path: str, max_thumb: int = 2200):
    with Image.open(path) as im:
        _dbg(
            "load_begin "
            f"path={path!r} format={getattr(im, 'format', None)!r} mode={getattr(im, 'mode', None)!r} "
            f"size={getattr(im, 'size', None)} info_keys={sorted(list(getattr(im, 'info', {}).keys()))}"
        )

        try:
            im.draft("RGB", (max_thumb, max_thumb))
            _dbg(
                "after_draft "
                f"path={path!r} mode={getattr(im, 'mode', None)!r} size={getattr(im, 'size', None)}"
            )
        except Exception as e:
            _dbg(f"draft_failed path={path!r} err={e}")

        orig_w, orig_h = im.size
        display_rgb = _prepare_rgb_for_display(im, path)
        display_rgb.thumbnail((max_thumb, max_thumb), Image.Resampling.LANCZOS)
        _dbg(
            "after_thumbnail "
            f"path={path!r} thumb_size={display_rgb.size} thumb_mode={display_rgb.mode!r}"
        )
        qimg = ImageQt(display_rgb).copy()

    return qimg, int(orig_w), int(orig_h)


def load_image_thumb_qpixmap(path: str, max_thumb: int = 2200):
    qimg, ow, oh = load_image_thumb_qimage(path, max_thumb=max_thumb)
    return QPixmap.fromImage(qimg), (int(ow), int(oh))
