from __future__ import annotations

import os
import sys
import warnings
from typing import Optional

from PIL import Image, ImageFile, ImageOps
from PIL.ImageQt import ImageQt
from PySide6.QtGui import QPixmap

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

ImageFile.LOAD_TRUNCATED_IMAGES = True

# 安全上限：允许加载大图（256MP），但阻止极端尺寸导致 OOM。
# 256MP 覆盖绝大多数科研图像（如 16384×16384），同时防止恶意/损坏文件。
Image.MAX_IMAGE_PIXELS = 256_000_000
try:
    warnings.simplefilter("ignore", Image.DecompressionBombWarning)
except Exception:
    pass

_TIFF_EXTS = {".tif", ".tiff"}
_PHOTOMETRIC_TAG = 262

# ICC 颜色管理：尝试导入 Pillow 内置的 CmsImagePlugin（Pillow >= 10.1）
_HAS_ICC_SUPPORT = False
try:
    from PIL import ImageCms

    _HAS_ICC_SUPPORT = True
except ImportError:
    pass

# sRGB ICC profile 路径（用于目标色彩空间）
_SRGB_PROFILE_PATH: Optional[str] = None
if _HAS_ICC_SUPPORT:
    try:
        from PIL import ImageCms as _ImageCms
        _SRGB_PROFILE_PATH = _ImageCms.createProfile("sRGB")
    except Exception:
        _SRGB_PROFILE_PATH = None


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
        if sys.__stderr__ is not None:
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


# 数值灰度模式：直接存储灰度值，无需调色板
_NUMERIC_GRAYSCALE_MODES = {"1", "L", "I", "F", "I;16", "I;16L", "I;16B", "I;16N"}


def _is_numeric_grayscale_mode(mode: str) -> bool:
    """判断是否为数值灰度模式（直接存储灰度值）。"""
    return mode.upper() in _NUMERIC_GRAYSCALE_MODES


def _is_palette_mode(im: Image.Image) -> bool:
    """判断是否为调色板模式（P 或 PA）。"""
    mode = str(getattr(im, "mode", "")).upper()
    return mode in {"P", "PA"}


def _palette_is_grayscale(im: Image.Image) -> bool:
    """检测调色板图像是否为灰度调色板（所有调色板条目 R==G==B）。

    仅在模式为 P 时调用，用于决定是否走灰度渲染路径。
    """
    mode = str(getattr(im, "mode", "")).upper()
    if mode not in {"P", "PA"}:
        return False

    try:
        palette = im.getpalette()
        if palette is None:
            return False

        # 调色板为 [R0, G0, B0, R1, G1, B1, ...] 格式
        # 检查前 256 个条目（或实际使用的条目）
        num_entries = min(256, len(palette) // 3)
        if num_entries == 0:
            return False

        for i in range(num_entries):
            r, g, b = palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2]
            if r != g or g != b:
                return False

        return True
    except Exception:
        return False


def _is_grayscale_like(im: Image.Image) -> bool:
    """判断图像是否应走灰度渲染路径。

    对于调色板模式（P），仅在调色板本身为灰度时返回 True。
    对于数值灰度模式，直接返回 True。
    """
    mode = str(getattr(im, "mode", "")).upper()

    # 数值灰度模式：直接返回 True
    if _is_numeric_grayscale_mode(mode):
        return True

    # 调色板模式：需要检查调色板是否为灰度
    if _is_palette_mode(im):
        return _palette_is_grayscale(im)

    # 其他模式：通过 bands 判断
    try:
        bands = im.getbands()
        return isinstance(bands, tuple) and len(bands) == 1
    except Exception:
        return False


def _has_alpha_channel(im: Image.Image) -> bool:
    mode = str(getattr(im, "mode", "")).upper()
    if "A" in mode:
        return True

    if mode == "P":
        info = getattr(im, "info", {}) or {}
        return "transparency" in info

    return False


def _has_palette_transparency_bytes(im: Image.Image) -> bool:
    """判断 P/PA 图像的 transparency 是否为 bytes 表达。"""
    mode = str(getattr(im, "mode", "")).upper()
    if mode not in {"P", "PA"}:
        return False

    info = getattr(im, "info", {}) or {}
    transparency = info.get("transparency")
    return isinstance(transparency, (bytes, bytearray))


def _extract_icc_profile(im: Image.Image) -> Optional[bytes]:
    """提取图片内嵌的 ICC profile 数据。"""
    info = getattr(im, "info", {}) or {}
    return info.get("icc_profile")


def _apply_icc_to_srgb(im: Image.Image, path: str) -> Image.Image:
    """将图片从内嵌 ICC profile 转换到 sRGB 色彩空间。

    如果没有 ICC profile 或 Pillow 不支持 ICC，则返回原图。
    """
    if not _HAS_ICC_SUPPORT or _SRGB_PROFILE_PATH is None:
        _dbg(f"icc_skip path={path!r} reason='no_icc_support'")
        return im

    icc_data = _extract_icc_profile(im)
    if not icc_data:
        _dbg(f"icc_skip path={path!r} reason='no_embedded_profile'")
        return im

    try:
        from PIL import ImageCms as _ImageCms
        src_profile = _ImageCms.ImageCmsProfile(icc_data)
        dst_profile = _ImageCms.ImageCmsProfile(_SRGB_PROFILE_PATH)

        # 对于灰度图，跳过 ICC 转换（灰度 ICC 转换需要特殊处理）
        mode = str(getattr(im, "mode", "")).upper()
        if mode in {"L", "1", "I", "F", "I;16", "I;16L", "I;16B", "I;16N"}:
            _dbg(f"icc_skip path={path!r} reason='grayscale_mode' mode={mode!r}")
            return im

        # 对于调色板模式（P），先转换为 RGB 再做 ICC 转换
        if mode in {"P", "PA"}:
            _dbg(f"icc_palette_convert path={path!r} mode={mode!r}")
            if _has_alpha_channel(im):
                rgba = im.convert("RGBA")
                rgb = rgba.convert("RGB")
                alpha = rgba.split()[3]
                converted = _ImageCms.profileToProfile(rgb, src_profile, dst_profile, outputMode="RGB")
                if converted is None:
                    return im
                result = converted.convert("RGBA")
                result.putalpha(alpha)
                _dbg(f"icc_applied path={path!r} mode='P_to_RGBA_with_alpha'")
                return result
            else:
                rgb = im.convert("RGB")
                converted = _ImageCms.profileToProfile(rgb, src_profile, dst_profile, outputMode="RGB")
                if converted is None:
                    return im
                _dbg(f"icc_applied path={path!r} mode='P_to_RGB'")
                return converted
    
        # 对于带 alpha 的图，分离 alpha 通道后处理
        if _has_alpha_channel(im):
            rgba = im.convert("RGBA")
            rgb = rgba.convert("RGB")
            alpha = rgba.split()[3]
            converted = _ImageCms.profileToProfile(rgb, src_profile, dst_profile, outputMode="RGB")
            if converted is None:
                return im
            result = converted.convert("RGBA")
            result.putalpha(alpha)
            _dbg(f"icc_applied path={path!r} mode='RGBA_with_alpha'")
            return result
        # 对于 CMYK 模式，需要特殊处理
        if mode == "CMYK":
            _dbg(f"icc_cmyk_convert path={path!r} mode='CMYK'")
            converted = _ImageCms.profileToProfile(im, src_profile, dst_profile, outputMode="RGB")
            if converted is None:
                return im
            _dbg(f"icc_applied path={path!r} mode='CMYK_to_RGB'")
            return converted
        
        # 对于其他模式（RGB 等）
        converted = _ImageCms.profileToProfile(im, src_profile, dst_profile, outputMode="RGB")
        if converted is None:
            return im
        # 检查转换后是否近纯白（ICC profile 不匹配可能导致此问题）
        extrema = _safe_extrema(converted)
        if extrema is not None:
            # RGB 模式 extrema 为 ((r_min,r_max),(g_min,g_max),(b_min,b_max))
            if isinstance(extrema, (tuple, list)) and len(extrema) > 0:
                first = extrema[0]
                if isinstance(first, (tuple, list)):
                    # 多通道：取所有通道最小值
                    all_min = min(ch[0] for ch in extrema if isinstance(ch, (tuple, list)) and len(ch) >= 2)
                else:
                    all_min = first
                if all_min >= 240:
                    _dbg(f"icc_revert path={path!r} reason='near_white_after_convert' extrema={extrema}")
                    return im
        _dbg(f"icc_applied path={path!r} mode='RGB'")
        return converted

    except Exception as e:
        _dbg(f"icc_failed path={path!r} err={e}")
        return im


def _to_display_l_channel(im: Image.Image) -> Image.Image:
    mode = str(getattr(im, "mode", "")).upper()

    if mode in {"1", "L"}:
        return im.convert("L")

    if mode in {"I", "F", "I;16", "I;16L", "I;16B", "I;16N"}:
        i_img = im.convert("I")
        extrema = _safe_extrema(i_img)
        if not (isinstance(extrema, tuple) and len(extrema) == 2):
            return i_img.convert("L")

        mn = int(extrema[0])  # pyright: ignore[reportArgumentType]
        mx = int(extrema[1])  # pyright: ignore[reportArgumentType]
        if mx <= mn:
            fill_v = max(0, min(255, mn // 256))
            return Image.new("L", i_img.size, color=fill_v)

        # 使用线性映射而非动态拉伸，保持与专业软件一致的显示效果
        # 将 [mn, mx] 映射到 [0, 255]，保持原始数据的相对关系
        scale = 255.0 / float(mx - mn)
        offset = -float(mn) * scale

        # 注意：I 模式（32位整数）不支持 point(lambda)，需用 numpy 或 ImageMath
        # 优先使用 numpy（最可靠），回退到 ImageMath.eval
        if np is not None:
            arr = np.array(i_img, dtype=np.float64)
            arr = arr * scale + offset
            arr = np.clip(arr, 0, 255).astype(np.uint8)
            return Image.fromarray(arr, mode="L")
        else:
            _dbg("numpy not available, falling back to ImageMath")
            try:
                from PIL import ImageMath
                result = ImageMath.eval(
                    "convert(max(0, min(255, im1 * scale1 + offset1)), 'L')",
                    im1=i_img, scale1=float(scale), offset1=float(offset)
                )
                if hasattr(result, "convert"):
                    return result.convert("L")
                return result  # pyright: ignore[reportReturnType]
            except Exception as e:
                _dbg(f"image_math_failed err={e}, falling back to manual")
                # 最终回退：逐像素处理（较慢但可靠）
                _dbg("using manual pixel processing")
                pixels = list(i_img.getdata())  # pyright: ignore[reportArgumentType]
                mapped = [max(0, min(255, int(p * scale + offset))) for p in pixels]
                out = Image.new("L", i_img.size)
                out.putdata(mapped)
                return out

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
            return int(v)  # pyright: ignore[reportArgumentType]
        except Exception:
            continue
    return None


def _is_tiff_white_is_zero(im: Image.Image, path: str) -> bool:
    fmt = str(getattr(im, "format", "")).upper()
    ext = os.path.splitext(path)[1].lower()
    if fmt != "TIFF" and ext not in _TIFF_EXTS:
        return False
    return _extract_photometric_interpretation(im) == 0


def _flatten_to_rgb(im: Image.Image, bg: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    if _has_alpha_channel(im):
        fg = im.convert("RGBA")
        base = Image.new("RGBA", fg.size, (int(bg[0]), int(bg[1]), int(bg[2]), 255))
        base.alpha_composite(fg)
        return base.convert("RGB")
    return im.convert("RGB")


def _is_frame_blank(im: Image.Image, threshold: float = 0.99) -> bool:
    """检测图像帧是否为空白（全白或全黑）。

    使用 histogram（固定 256 个 bin 计数）代替 getdata() 全像素列表，
    内存开销 O(1) 而非 O(width×height)，避免大图 OOM。

    Args:
        im: 要检测的图像
        threshold: 空白阈值，0.99 表示 99% 的像素为白色或黑色时视为空白

    Returns:
        如果图像为空白则返回 True
    """
    try:
        gray = im.convert("L")
        extrema = gray.getextrema()
        if extrema is None:
            return False

        min_val, max_val = extrema  # pyright: ignore[reportGeneralTypeIssues]
        # 快速路径：极值已表明全黑或全白
        if int(max_val) <= 5 or int(min_val) >= 250:  # pyright: ignore[reportArgumentType]
            return True

        # histogram 返回长度 256 的列表，每个元素是对应灰度值的像素计数
        hist = gray.histogram()  # list[int] of length 256
        total = sum(hist)
        if total == 0:
            return True

        # 统计接近白色 (>=250) 或接近黑色 (<=5) 的像素比例
        white_count = sum(hist[250:])
        black_count = sum(hist[:6])

        return (white_count / total >= threshold) or (black_count / total >= threshold)
    except Exception:
        return False


def _select_best_tiff_frame(im: Image.Image, path: str) -> Image.Image:
    """对于多帧 TIFF，自动选择第一个非空帧。

    如果是单帧 TIFF 或非 TIFF 文件，直接返回原图。
    如果所有帧都为空白，返回第一帧。

    Args:
        im: 已打开的 PIL Image 对象
        path: 图片文件路径

    Returns:
        选中的帧图像
    """
    ext = os.path.splitext(path)[1].lower()
    fmt = str(getattr(im, "format", "")).upper()

    # 只处理 TIFF 文件
    if fmt != "TIFF" and ext not in _TIFF_EXTS:
        return im

    try:
        n_frames = getattr(im, "n_frames", 1)
        if n_frames <= 1:
            _dbg(f"tiff_frame_select path={path!r} reason='single_frame'")
            return im

        _dbg(f"tiff_frame_select path={path!r} n_frames={n_frames}")

        # 尝试找到第一个非空帧
        for frame_idx in range(n_frames):
            try:
                im.seek(frame_idx)
                # 复制当前帧以避免后续 seek 影响
                frame = im.copy()

                if not _is_frame_blank(frame):
                    _dbg(f"tiff_frame_select path={path!r} selected_frame={frame_idx}")
                    return frame
            except Exception as e:
                _dbg(f"tiff_frame_select path={path!r} frame={frame_idx} err={e}")
                continue

        # 如果所有帧都为空白，返回第一帧
        _dbg(f"tiff_frame_select path={path!r} reason='all_blank' fallback=0")
        im.seek(0)
        return im.copy()

    except Exception as e:
        _dbg(f"tiff_frame_select path={path!r} err={e}")
        return im


def prepare_image_for_render(im: Image.Image, path: str, transparent_bg: bool = False) -> Image.Image:
    """统一图片渲染前处理：ICC 色彩管理、方向、灰度/16bit、WhiteIsZero、alpha保留或白底压平。

    决策顺序：
    1. EXIF 方向校正
    2. ICC 到 sRGB 色彩管理
    3. 模式识别与分支选择（灰度 vs 彩色）
    4. WhiteIsZero 仅在确认为灰度路径时应用
    5. 透明度保留或白底压平
    """
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

    # 步骤 1: EXIF 方向校正
    try:
        im = ImageOps.exif_transpose(im)
    except Exception as e:
        _dbg(f"exif_transpose_failed path={path!r} err={e}")

    # 步骤 2: ICC 到 sRGB 色彩管理
    im = _apply_icc_to_srgb(im, path)

    # 步骤 3: 模式识别与分支选择
    post_icc_mode = str(getattr(im, "mode", "")).upper()
    is_palette = _is_palette_mode(im)
    white_is_zero = _is_tiff_white_is_zero(im, path)
    gray_like = _is_grayscale_like(im)
    has_alpha = _has_alpha_channel(im)

    # CMYK 模式：转换为 RGB（ICC 转换可能已处理，但确保兜底）
    if post_icc_mode == "CMYK":
        _dbg(f"cmyk_convert path={path!r} action='convert_CMYK_to_RGB'")
        im = im.convert("RGB")
        post_icc_mode = "RGB"
        has_alpha = False

    # Pillow 对 transparency=bytes 的调色板图在转 RGB/L 时会给出告警：
    # "Palette images with Transparency expressed in bytes should be converted to RGBA images"
    # 这里统一前置转 RGBA，后续流程不再触发该告警。
    if is_palette and _has_palette_transparency_bytes(im):
        _dbg(f"palette_transparency_bytes path={path!r} action='convert_P_to_RGBA_first'")
        im = im.convert("RGBA")
        post_icc_mode = str(getattr(im, "mode", "")).upper()
        is_palette = _is_palette_mode(im)
        white_is_zero = _is_tiff_white_is_zero(im, path)
        gray_like = _is_grayscale_like(im)
        has_alpha = _has_alpha_channel(im)

    _dbg(
        "render_decision "
        f"path={path!r} src_mode={src_mode!r} post_icc_mode={post_icc_mode!r} "
        f"is_palette={is_palette} gray_like={gray_like} "
        f"white_is_zero={white_is_zero} has_alpha={has_alpha} "
        f"transparent_bg={bool(transparent_bg)}"
    )

    # 对于调色板模式（P），如果需要走灰度分支，先转换为 L 模式
    # 这样 _to_display_l_channel() 就能正确处理
    if gray_like and is_palette:
        _dbg(f"palette_to_gray path={path!r} action='convert_P_to_L'")
        im = im.convert("L")

    if gray_like:
        l_img = _to_display_l_channel(im)
        action = "gray_linear_scale"
        if white_is_zero:
            l_img = ImageOps.invert(l_img)
            action += "_then_invert"

        rgb = Image.merge("RGB", (l_img, l_img, l_img))
        if transparent_bg:
            out = rgb.convert("RGBA")
            action += "_to_rgba"
        else:
            out = rgb

        _dbg(
            "convert_result "
            f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
            f"out_extrema={_safe_extrema(out)} action={action!r}"
        )
        return out

    # 步骤 4: WhiteIsZero 仅在确认为灰度路径时应用
    # TIFF 的 WhiteIsZero 在非灰度图上并不总是安全可反相，避免误反相。
    if white_is_zero:
        _dbg(f"skip_non_gray_invert path={path!r} reason='white_is_zero_non_gray'")

    # 对于调色板模式（P），先转换为 RGB 以保留颜色信息
    if is_palette:
        _dbg(f"palette_to_rgb path={path!r} action='convert_P_to_RGB'")
        im = im.convert("RGB")

    # 步骤 5: 透明度保留或白底压平
    if transparent_bg:
        out = im.convert("RGBA")
        action = "preserve_alpha_rgba" if has_alpha else "opaque_rgba"
        _dbg(
            "convert_result "
            f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
            f"out_extrema={_safe_extrema(out)} action={action!r}"
        )
        return out

    out = _flatten_to_rgb(im, bg=(255, 255, 255))
    action = "flatten_alpha_to_white_rgb" if has_alpha else "direct_rgb"
    _dbg(
        "convert_result "
        f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
        f"out_extrema={_safe_extrema(out)} action={action!r}"
    )
    return out


def _prepare_rgb_for_display(im: Image.Image, path: str) -> Image.Image:
    out = prepare_image_for_render(im, path=path, transparent_bg=False)
    return out.convert("RGB")


def load_image_thumb_qimage(path: str, max_thumb: int = 2200):
    with Image.open(path) as im:
        _dbg(
            "load_begin "
            f"path={path!r} format={getattr(im, 'format', None)!r} mode={getattr(im, 'mode', None)!r} "
            f"size={getattr(im, 'size', None)} info_keys={sorted(list(getattr(im, 'info', {}).keys()))}"
        )

        # 对于 TIFF 文件，自动选择第一个非空帧
        im = _select_best_tiff_frame(im, path)

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


def prepare_image_for_export(im: Image.Image, path: str, transparent_bg: bool = False) -> Image.Image:
    """保真导出管线：保留原始位深（16-bit 灰度等），ICC 色彩管理，透明通道保留。

    与 prepare_image_for_render() 的区别：
    - 16-bit 灰度（I;16 等）保留为 16-bit I 模式，不映射到 8-bit L
    - 适用于需要保留原始数据精度的导出场景（如 TIFF 16-bit 导出）

    决策顺序：
    1. EXIF 方向校正
    2. ICC 到 sRGB 色彩管理
    3. 模式识别与分支选择（灰度 vs 彩色）
    4. WhiteIsZero 仅在确认为灰度路径时应用
    5. 透明度保留或白底压平
    """
    src_mode = str(getattr(im, "mode", ""))
    src_fmt = str(getattr(im, "format", ""))
    src_size = tuple(getattr(im, "size", (0, 0)))
    src_extrema = _safe_extrema(im)
    photometric = _extract_photometric_interpretation(im)

    _dbg(
        "export_open "
        f"path={path!r} format={src_fmt!r} mode={src_mode!r} size={src_size} "
        f"photometric={photometric} extrema={src_extrema}"
    )

    # 步骤 1: EXIF 方向校正
    try:
        im = ImageOps.exif_transpose(im)
    except Exception as e:
        _dbg(f"export_exif_transpose_failed path={path!r} err={e}")

    # 步骤 2: ICC 到 sRGB 色彩管理
    im = _apply_icc_to_srgb(im, path)

    # 步骤 3: 模式识别与分支选择
    post_icc_mode = str(getattr(im, "mode", "")).upper()
    is_palette = _is_palette_mode(im)
    white_is_zero = _is_tiff_white_is_zero(im, path)
    gray_like = _is_grayscale_like(im)
    has_alpha = _has_alpha_channel(im)

    # CMYK 模式：转换为 RGB（ICC 转换可能已处理，但确保兜底）
    if post_icc_mode == "CMYK":
        _dbg(f"export_cmyk_convert path={path!r} action='convert_CMYK_to_RGB'")
        im = im.convert("RGB")
        post_icc_mode = "RGB"
        has_alpha = False

    # Pillow 对 transparency=bytes 的调色板图在转 RGB/L 时会给出告警：
    # "Palette images with Transparency expressed in bytes should be converted to RGBA images"
    # 这里统一前置转 RGBA，后续流程不再触发该告警。
    if is_palette and _has_palette_transparency_bytes(im):
        _dbg(f"export_palette_transparency_bytes path={path!r} action='convert_P_to_RGBA_first'")
        im = im.convert("RGBA")
        post_icc_mode = str(getattr(im, "mode", "")).upper()
        is_palette = _is_palette_mode(im)
        white_is_zero = _is_tiff_white_is_zero(im, path)
        gray_like = _is_grayscale_like(im)
        has_alpha = _has_alpha_channel(im)

    _dbg(
        "export_render_decision "
        f"path={path!r} src_mode={src_mode!r} post_icc_mode={post_icc_mode!r} "
        f"is_palette={is_palette} gray_like={gray_like} "
        f"white_is_zero={white_is_zero} has_alpha={has_alpha} "
        f"transparent_bg={bool(transparent_bg)}"
    )

    # 对于调色板模式（P），如果需要走灰度分支，先转换为 L 模式
    if gray_like and is_palette:
        _dbg(f"export_palette_to_gray path={path!r} action='convert_P_to_L'")
        im = im.convert("L")

    if gray_like:
        mode = str(getattr(im, "mode", "")).upper()
        # 16-bit 灰度模式：线性拉伸到 [0, 65535] 后保留为 I 模式（32-bit 整数）
        if mode in {"I;16", "I;16L", "I;16B", "I;16N"}:
            i_img = im.convert("I")
            extrema = _safe_extrema(i_img)

            # 与显示管线 _to_display_l_channel 相同的线性拉伸逻辑，
            # 但目标范围为 [0, 65535]（保留 16-bit 精度）而非 [0, 255]
            if isinstance(extrema, tuple) and len(extrema) == 2:
                mn = int(extrema[0])  # pyright: ignore[reportArgumentType]
                mx = int(extrema[1])  # pyright: ignore[reportArgumentType]
                if mx > mn:
                    if np is not None:
                        arr = np.array(i_img, dtype=np.float64)
                        scale = 65535.0 / float(mx - mn)
                        offset = -float(mn) * scale
                        arr = arr * scale + offset
                        arr = np.clip(arr, 0, 65535).astype(np.int32)
                        i_img = Image.fromarray(arr, mode="I")
                        _dbg(f"export_i16_linear_stretch path={path!r} "
                             f"src_range=({mn}, {mx}) action='stretch_to_0_65535'")
                    else:
                        _dbg("numpy not available for export linear stretch, using raw values")

            if white_is_zero:
                # WhiteIsZero：需要反转（I 模式下使用 ImageMath）
                try:
                    from PIL import ImageMath
                    i_img = ImageMath.lambda_eval(
                        lambda d: "65535 - d",
                        d=i_img
                    )
                    if hasattr(i_img, "convert"):
                        i_img = i_img.convert("I")
                    _dbg(f"export_i16_invert path={path!r} action='white_is_zero_invert'")
                except Exception as e:
                    _dbg(f"export_i16_invert_failed path={path!r} err={e}")
                    # 回退：转 L 后反转
                    l_img = i_img.convert("L")
                    l_img = ImageOps.invert(l_img)
                    if transparent_bg:
                        out = l_img.convert("RGBA")
                    else:
                        out = Image.merge("RGB", (l_img, l_img, l_img))
                    return out

            if transparent_bg:
                # I 模式不支持 RGBA，缩放 [0,65535]→[0,255] 后转 RGBA
                if np is not None:
                    arr = np.clip(np.array(i_img, dtype=np.float64) / 257.0, 0, 255).astype(np.uint8)
                    l_img = Image.fromarray(arr, mode="L")
                else:
                    l_img = i_img.convert("L")
                out = l_img.convert("RGBA")
            else:
                # 保留为 I 模式（32-bit 整数，兼容 16-bit 数据）
                out = i_img
            _dbg(
                "export_convert_result "
                f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
                f"out_extrema={_safe_extrema(out)} action='preserve_16bit_gray'"
            )
            return out

        # 8-bit 灰度模式（L, 1, I, F）：映射到 8-bit 显示
        l_img = _to_display_l_channel(im)
        action = "gray_linear_scale"
        if white_is_zero:
            l_img = ImageOps.invert(l_img)
            action += "_then_invert"

        rgb = Image.merge("RGB", (l_img, l_img, l_img))
        if transparent_bg:
            out = rgb.convert("RGBA")
            action += "_to_rgba"
        else:
            out = rgb

        _dbg(
            "export_convert_result "
            f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
            f"out_extrema={_safe_extrema(out)} action={action!r}"
        )
        return out

    # 步骤 4: WhiteIsZero 仅在确认为灰度路径时应用
    if white_is_zero:
        _dbg(f"export_skip_non_gray_invert path={path!r} reason='white_is_zero_non_gray'")

    # 对于调色板模式（P），先转换为 RGB 以保留颜色信息
    if is_palette:
        _dbg(f"export_palette_to_rgb path={path!r} action='convert_P_to_RGB'")
        im = im.convert("RGB")

    # 步骤 5: 透明度保留或白底压平
    if transparent_bg:
        out = im.convert("RGBA")
        action = "preserve_alpha_rgba" if has_alpha else "opaque_rgba"
        _dbg(
            "export_convert_result "
            f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
            f"out_extrema={_safe_extrema(out)} action={action!r}"
        )
        return out

    out = _flatten_to_rgb(im, bg=(255, 255, 255))
    action = "flatten_alpha_to_white_rgb" if has_alpha else "direct_rgb"
    _dbg(
        "export_convert_result "
        f"path={path!r} out_mode={getattr(out, 'mode', None)!r} "
        f"out_extrema={_safe_extrema(out)} action={action!r}"
    )
    return out
