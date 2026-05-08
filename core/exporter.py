from __future__ import annotations

import base64
import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageOps
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from app.canvas_view import ImageFrameItem
from core.image_utils import prepare_image_for_render, prepare_image_for_export, _select_best_tiff_frame

_logger = logging.getLogger(__name__)

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


def _resize_i_mode(im: Image.Image, new_w: int, new_h: int) -> Image.Image:
    """Resize I-mode image via numpy (PIL can't resize I-mode directly). Falls back to L."""
    if np is None:
        return im.convert("L").resize((new_w, new_h), Image.Resampling.LANCZOS)
    arr = np.array(im, dtype=np.float32)
    float_img = Image.fromarray(arr, mode="F")
    resized_float = float_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    arr = np.clip(np.array(resized_float), 0, 65535).astype(np.int32)
    return Image.fromarray(arr, mode="I")


def _cover_resize(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    sw, sh = im.size
    target_ratio = target_w / target_h
    src_ratio = sw / sh

    if src_ratio > target_ratio:
        crop_w = int(round(sh * target_ratio))
        left = (sw - crop_w) // 2
        box = (left, 0, left + crop_w, sh)
    else:
        crop_h = int(round(sw / target_ratio))
        top = (sh - crop_h) // 2
        box = (0, top, sw, top + crop_h)

    if im.mode == "I":
        if np is not None:
            arr = np.array(im, dtype=np.float32)[box[1]:box[3], box[0]:box[2]]
            cropped = Image.fromarray(arr, mode="I")
            return _resize_i_mode(cropped, target_w, target_h)
        im = im.convert("L")

    return im.crop(box).resize((target_w, target_h), Image.Resampling.LANCZOS)


def _fit_resize(im: Image.Image, target_w: int, target_h: int, bg) -> Image.Image:
    if im.mode == "I":
        sw, sh = im.size
        scale = min(target_w / sw, target_h / sh)
        new_w = max(1, int(round(sw * scale)))
        new_h = max(1, int(round(sh * scale)))
        resized = _resize_i_mode(im, new_w, new_h)
        if isinstance(bg, (tuple, list)):
            i_bg = int(0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) * 257
        else:
            i_bg = int(bg) * 257
        tile = Image.new("I", (target_w, target_h), i_bg)
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        tile.paste(resized, (x, y))
        return tile

    mode = "RGBA" if (isinstance(bg, (tuple, list)) and len(bg) >= 4) else "RGB"
    src = im.convert(mode)

    sw, sh = src.size
    scale = min(target_w / sw, target_h / sh)
    new_w = max(1, int(round(sw * scale)))
    new_h = max(1, int(round(sh * scale)))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)

    tile = Image.new(mode, (target_w, target_h), tuple(bg))
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2

    if mode == "RGBA":
        tile.paste(resized, (x, y), resized)
    else:
        tile.paste(resized, (x, y))
    return tile


def _apply_image_item_ops(im: Image.Image, item: ImageFrameItem) -> Image.Image:
    if getattr(item, "flip_h", False):
        im = ImageOps.mirror(im)
    if getattr(item, "flip_v", False):
        im = ImageOps.flip(im)

    steps = int(getattr(item, "rot90_steps", 0)) % 4
    if steps == 1:
        im = im.transpose(Image.Transpose.ROTATE_270)  # 顺时针90
    elif steps == 2:
        im = im.transpose(Image.Transpose.ROTATE_180)
    elif steps == 3:
        im = im.transpose(Image.Transpose.ROTATE_90)

    return im


def _i_to_l(part: Image.Image) -> Image.Image:
    """I mode [0,65535] → L mode [0,255]，正确缩放而非截断。"""
    if np is None:
        return part.convert("L")
    arr = np.clip(np.array(part, dtype=np.float64) / 257.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="L")


def _border_rgb(item: ImageFrameItem) -> tuple[int, int, int]:
    c = getattr(item, "border_color", (0, 0, 0))
    if isinstance(c, (tuple, list)) and len(c) >= 3:
        return (int(c[0]), int(c[1]), int(c[2]))
    return (0, 0, 0)


def _render_overlay_from_scene(canvas_view) -> Image.Image:
    """渲染文本/标签叠加层（隐藏图片本体和页面底色）。"""
    scene = canvas_view.scene()
    page_w, page_h = canvas_view.page_size_px()

    qimg = QImage(page_w, page_h, QImage.Format.Format_ARGB32_Premultiplied)
    qimg.fill(Qt.GlobalColor.transparent)

    hidden = []
    selected = list(scene.selectedItems())
    painter = None

    try:
        for it in scene.items():
            if isinstance(it, ImageFrameItem):
                hidden.append((it, it.isVisible()))
                it.setVisible(False)

        page_item = getattr(canvas_view, "page_rect_item", None)
        if page_item is not None:
            hidden.append((page_item, page_item.isVisible()))
            page_item.setVisible(False)

        for it in selected:
            it.setSelected(False)

        painter = QPainter(qimg)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        src = QRectF(0, 0, page_w, page_h)
        dst = QRectF(0, 0, page_w, page_h)
        scene.render(painter, dst, src)
    finally:
        if painter is not None and painter.isActive():
            painter.end()

        for it, vis in hidden:
            if it.scene() is scene:
                it.setVisible(vis)
        for it in selected:
            if it.scene() is scene:
                it.setSelected(True)

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    qimg.save(buf, "PNG")  # pyright: ignore[reportCallIssue,reportArgumentType]
    ba = buf.data()
    data = bytes(ba)  # pyright: ignore[reportArgumentType]
    buf.close()

    return Image.open(BytesIO(data)).convert("RGBA")


def compose_canvas_image(canvas_view, transparent_bg: bool = False, use_export_pipeline: bool = False) -> Image.Image:
    """合成导出图（图片高质量重采样 + 场景文本叠加）。

    Args:
        canvas_view: 画布视图对象
        transparent_bg: 是否使用透明背景
        use_export_pipeline: 是否使用保真导出管线（保留 16-bit 灰度等）
    """
    page_w, page_h = canvas_view.page_size_px()

    items = canvas_view.image_items()
    items = sorted(items, key=lambda it: (it.zValue(), it.scenePos().y(), it.scenePos().x()))

    # 第一遍：处理所有素材，收集 tile 信息
    tile_entries: list[tuple[Image.Image, int, int, int, int, int, int, int, int, ImageFrameItem]] = []
    failed_items: list[str] = []

    for item in items:
        x = int(round(item.scenePos().x()))
        y = int(round(item.scenePos().y()))
        fw, fh = item.frame_size()
        if fw <= 0 or fh <= 0:
            continue

        try:
            with Image.open(item.source_path) as src_im:
                src_im = _select_best_tiff_frame(src_im, item.source_path)
                if use_export_pipeline:
                    im = prepare_image_for_export(src_im, path=item.source_path, transparent_bg=transparent_bg)
                else:
                    im = prepare_image_for_render(src_im, path=item.source_path, transparent_bg=transparent_bg)
                im = _apply_image_item_ops(im, item)

                mode = getattr(item, "fill_mode", "fit")
                if mode == "cover":
                    tile = _cover_resize(im, fw, fh)
                else:
                    bg = (0, 0, 0, 0) if transparent_bg else (255, 255, 255)
                    tile = _fit_resize(im, fw, fh, bg=bg)

                left = max(0, x)
                top = max(0, y)
                right = min(page_w, x + fw)
                bottom = min(page_h, y + fh)
                if right > left and bottom > top:
                    tile_entries.append((tile, x, y, fw, fh, left, top, right, bottom, item))
        except Exception as exc:
            _logger.warning("导出合成：跳过素材 %s，原因: %s", item.source_path, exc)
            failed_items.append(item.source_path)

    # 判断是否所有素材均为灰度模式（保真导出时保留 16-bit I 模式）
    all_gray_16 = use_export_pipeline and not transparent_bg and tile_entries and all(
        t[0].mode == "I" for t in tile_entries
    )
    all_gray_8 = use_export_pipeline and not transparent_bg and tile_entries and all(
        t[0].mode in {"L", "1"} for t in tile_entries
    )

    # 创建画布
    if transparent_bg:
        out = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))
    elif all_gray_16:
        out = Image.new("I", (page_w, page_h), 65535)
    elif all_gray_8:
        out = Image.new("L", (page_w, page_h), 255)
    else:
        out = Image.new("RGB", (page_w, page_h), "white")

    draw = ImageDraw.Draw(out)

    # 第二遍：粘贴素材到画布
    for tile, x, y, fw, fh, left, top, right, bottom, item in tile_entries:
        src_left = left - x
        src_top = top - y
        src_right = src_left + (right - left)
        src_bottom = src_top + (bottom - top)
        part = tile.crop((src_left, src_top, src_right, src_bottom))

        if part.mode == "I" and out.mode not in ("I", "L"):
            part = _i_to_l(part)

        if out.mode == "RGBA":
            pr = part.convert("RGBA")
            out.paste(pr, (left, top), pr)
        elif out.mode in ("I", "L"):
            part_gray = part.convert(out.mode)
            out.paste(part_gray, (left, top))
        else:
            out.paste(part.convert("RGB"), (left, top))

        bw = int(getattr(item, "border_width", 0))
        if bw > 0:
            col = _border_rgb(item)
            if out.mode == "RGBA":
                col = (col[0], col[1], col[2], 255)
            elif out.mode in ("I", "L"):
                gray_val = int(0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2])
                if out.mode == "I":
                    gray_val = gray_val * 257
                col = gray_val

            x0, y0, x1, y1 = x, y, x + fw - 1, y + fh - 1
            for k in range(bw):
                if x0 + k > x1 - k or y0 + k > y1 - k:
                    break
                draw.rectangle((x0 + k, y0 + k, x1 - k, y1 - k), outline=col)

    if failed_items:
        _logger.warning("导出合成完成，共 %d 个素材加载失败: %s", len(failed_items), failed_items)

    # 灰度画布不叠加文本 overlay（文本需要彩色），直接返回
    if out.mode in ("I", "L"):
        return out

    overlay = _render_overlay_from_scene(canvas_view)

    if out.mode == "RGBA":
        out.alpha_composite(overlay)
        return out

    out_rgba = out.convert("RGBA")
    out_rgba.alpha_composite(overlay)
    return out_rgba.convert("RGB")


def _get_srgb_icc_profile() -> bytes | None:
    """获取 sRGB ICC profile 数据，用于导出时嵌入。"""
    try:
        from PIL import ImageCms
        profile = ImageCms.createProfile("sRGB")
        return ImageCms.ImageCmsProfile(profile).tobytes()
    except Exception:
        return None


def export_canvas_to_image(
    canvas_view,
    output_path: str,
    dpi: int = 300,
    jpeg_quality: int = 95,
    transparent_bg: bool = False,
):
    ext = os.path.splitext(output_path)[1].lower()
    dpi_tuple = (int(dpi), int(dpi))

    # 获取 sRGB ICC profile 用于嵌入导出文件
    icc_profile = _get_srgb_icc_profile()

    # TIFF 导出使用保真管线，保留 16-bit 灰度等原始位深
    if ext in (".tif", ".tiff"):
        out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg, use_export_pipeline=True)
        _export_tiff_16bit(out, output_path, dpi_tuple, icc_profile, transparent_bg)
        return

    # 其他格式使用标准管线（8-bit 显示）
    out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg, use_export_pipeline=False)

    if ext in (".jpg", ".jpeg"):
        # JPEG 不支持透明
        rgb_out = out.convert("RGB")
        save_kwargs = {
            "quality": jpeg_quality,
            "subsampling": 0,
            "dpi": dpi_tuple,
        }
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        rgb_out.save(output_path, "JPEG", **save_kwargs)

    elif ext == ".png":
        img_out = out.convert("RGBA") if transparent_bg else out.convert("RGB")
        save_kwargs = {"compress_level": 3, "dpi": dpi_tuple}
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        img_out.save(output_path, "PNG", **save_kwargs)

    else:
        raise ValueError("暂不支持该导出格式。请选择 jpg/png/tiff。")


def _save_tiff(img: Image.Image, output_path: str, compression: str, dpi_tuple: tuple[int, int], icc_profile: bytes | None):
    save_kwargs: dict = {"compression": compression, "dpi": dpi_tuple}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    img.save(output_path, "TIFF", **save_kwargs)


def _export_tiff_16bit(out: Image.Image, output_path: str, dpi_tuple: tuple[int, int], icc_profile: bytes | None, transparent_bg: bool):
    """导出 TIFF，尝试保留灰度信息与 16-bit 位深，失败则回退到标准 RGB/RGBA 导出。"""
    try:
        if transparent_bg:
            _save_tiff(out.convert("RGBA"), output_path, "tiff_adobe_deflate", dpi_tuple, icc_profile)
        elif out.mode == "I":
            # I 模式（32-bit int，值域 [0, 65535]）→ I;16（16-bit unsigned）保存
            if np is not None:
                arr = np.clip(np.array(out, dtype=np.int32), 0, 65535).astype(np.uint16)
                i16_img = Image.fromarray(arr, mode="I;16")
                _save_tiff(i16_img, output_path, "tiff_lzw", dpi_tuple, icc_profile)
            else:
                _save_tiff(out.convert("L"), output_path, "tiff_lzw", dpi_tuple, icc_profile)
        elif out.mode == "L":
            _save_tiff(out, output_path, "tiff_lzw", dpi_tuple, icc_profile)
        elif out.mode == "RGB":
            if np is not None:
                arr = np.array(out)
                is_gray = np.array_equal(arr[:, :, 0], arr[:, :, 1]) and np.array_equal(arr[:, :, 1], arr[:, :, 2])
            else:
                r, g, b = out.split()
                is_gray = (r.histogram() == g.histogram()) and (g.histogram() == b.histogram())

            img = out.convert("L") if is_gray else out
            _save_tiff(img, output_path, "tiff_lzw", dpi_tuple, icc_profile)
        else:
            _save_tiff(out, output_path, "tiff_lzw", dpi_tuple, icc_profile)
    except Exception as e:
        _logger.warning("TIFF 导出失败，回退到标准导出: %s", e)
        if transparent_bg:
            _save_tiff(out.convert("RGBA"), output_path, "tiff_adobe_deflate", dpi_tuple, icc_profile)
        else:
            _save_tiff(out.convert("RGB"), output_path, "tiff_lzw", dpi_tuple, icc_profile)


def export_canvas_to_pdf(canvas_view, output_path: str, dpi: int = 300, transparent_bg: bool = False):
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas

    out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg)
    page_w, page_h = out.size

    width_pt = page_w / float(dpi) * 72.0
    height_pt = page_h / float(dpi) * 72.0

    buf = BytesIO()
    # 使用 PNG 格式嵌入 PDF，保留 alpha 通道信息
    out.save(buf, "PNG")
    buf.seek(0)

    c = pdf_canvas.Canvas(output_path, pagesize=(width_pt, height_pt))
    c.drawImage(ImageReader(buf), 0, 0, width=width_pt, height=height_pt, mask="auto")
    c.showPage()
    c.save()


def export_canvas_to_svg(canvas_view, output_path: str, dpi: int = 300, transparent_bg: bool = False):
    import svgwrite

    out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg)
    page_w, page_h = out.size
    dpi_tuple = (int(dpi), int(dpi))

    # 嵌入 PNG 图像到 SVG
    png_for_embed = out.convert("RGBA" if transparent_bg else "RGB")
    buf = BytesIO()
    png_for_embed.save(buf, "PNG", compress_level=3, dpi=dpi_tuple)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("ascii")

    # 创建 SVG 文件，使用完整的命名空间声明以提高兼容性
    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{page_w}px", f"{page_h}px"),
        profile="full",
    )

    # 添加必要的命名空间声明
    dwg.attribs["xmlns"] = "http://www.w3.org/2000/svg"
    dwg.attribs["xmlns:xlink"] = "http://www.w3.org/1999/xlink"

    # 设置 viewBox 确保正确的缩放行为
    dwg.viewbox(0, 0, page_w, page_h)

    # 添加背景矩形（非透明模式）
    if not transparent_bg:
        dwg.add(dwg.rect(insert=(0, 0), size=(page_w, page_h), fill="white"))

    # 嵌入图像，使用 xlink:href 以提高旧版查看器兼容性
    img_element = dwg.image(
        href=f"data:image/png;base64,{b64}",
        insert=(0, 0),
        size=(page_w, page_h),
    )
    # 同时设置 xlink:href 属性以提高兼容性
    img_element.attribs["xlink:href"] = f"data:image/png;base64,{b64}"
    dwg.add(img_element)

    dwg.save()
