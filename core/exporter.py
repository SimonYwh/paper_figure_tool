from __future__ import annotations

import base64
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageOps
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from app.canvas_view import ImageFrameItem


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

    return im.crop(box).resize((target_w, target_h), Image.Resampling.LANCZOS)


def _fit_resize(im: Image.Image, target_w: int, target_h: int, bg) -> Image.Image:
    mode = "RGBA" if (isinstance(bg, (tuple, list)) and len(bg) >= 4) else "RGB"
    src = im.convert(mode)

    sw, sh = src.size
    scale = min(target_w / sw, target_h / sh)
    new_w = max(1, int(round(sw * scale)))
    new_h = max(1, int(round(sh * scale)))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)

    tile = Image.new(mode, (target_w, target_h), bg)
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
    qimg.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()

    return Image.open(BytesIO(data)).convert("RGBA")


def compose_canvas_image(canvas_view, transparent_bg: bool = False) -> Image.Image:
    """合成导出图（图片高质量重采样 + 场景文本叠加）。"""
    page_w, page_h = canvas_view.page_size_px()

    if transparent_bg:
        out = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))
    else:
        out = Image.new("RGB", (page_w, page_h), "white")

    draw = ImageDraw.Draw(out)

    items = canvas_view.image_items()
    items = sorted(items, key=lambda it: (it.zValue(), it.scenePos().y(), it.scenePos().x()))

    for item in items:
        x = int(round(item.scenePos().x()))
        y = int(round(item.scenePos().y()))
        fw, fh = item.frame_size()
        if fw <= 0 or fh <= 0:
            continue

        with Image.open(item.source_path) as im:
            im = ImageOps.exif_transpose(im)
            im = im.convert("RGBA" if transparent_bg else "RGB")
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
        if right <= left or bottom <= top:
            continue

        src_left = left - x
        src_top = top - y
        src_right = src_left + (right - left)
        src_bottom = src_top + (bottom - top)

        part = tile.crop((src_left, src_top, src_right, src_bottom))

        if out.mode == "RGBA":
            pr = part.convert("RGBA")
            out.paste(pr, (left, top), pr)
        else:
            out.paste(part.convert("RGB"), (left, top))

        bw = int(getattr(item, "border_width", 0))
        if bw > 0:
            col = _border_rgb(item)
            if out.mode == "RGBA":
                col = (col[0], col[1], col[2], 255)

            x0, y0, x1, y1 = x, y, x + fw - 1, y + fh - 1
            for k in range(bw):
                if x0 + k > x1 - k or y0 + k > y1 - k:
                    break
                draw.rectangle((x0 + k, y0 + k, x1 - k, y1 - k), outline=col)

    overlay = _render_overlay_from_scene(canvas_view)

    if out.mode == "RGBA":
        out.alpha_composite(overlay)
        return out

    out_rgba = out.convert("RGBA")
    out_rgba.alpha_composite(overlay)
    return out_rgba.convert("RGB")


def export_canvas_to_image(
    canvas_view,
    output_path: str,
    dpi: int = 300,
    jpeg_quality: int = 95,
    transparent_bg: bool = False,
):
    out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg)

    ext = os.path.splitext(output_path)[1].lower()
    dpi_tuple = (int(dpi), int(dpi))

    if ext in (".jpg", ".jpeg"):
        # JPEG 不支持透明
        out.convert("RGB").save(output_path, "JPEG", quality=jpeg_quality, subsampling=0, dpi=dpi_tuple)

    elif ext == ".png":
        if transparent_bg:
            out.convert("RGBA").save(output_path, "PNG", compress_level=3, dpi=dpi_tuple)
        else:
            out.convert("RGB").save(output_path, "PNG", compress_level=3, dpi=dpi_tuple)

    elif ext in (".tif", ".tiff"):
        if transparent_bg:
            out.convert("RGBA").save(output_path, "TIFF", compression="tiff_adobe_deflate", dpi=dpi_tuple)
        else:
            out.convert("RGB").save(output_path, "TIFF", compression="tiff_lzw", dpi=dpi_tuple)

    else:
        raise ValueError("暂不支持该导出格式。请选择 jpg/png/tiff。")


def export_canvas_to_pdf(canvas_view, output_path: str, dpi: int = 300, transparent_bg: bool = False):
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas

    out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg)
    page_w, page_h = out.size

    width_pt = page_w / float(dpi) * 72.0
    height_pt = page_h / float(dpi) * 72.0

    buf = BytesIO()
    out.save(buf, "PNG")  # PNG 可带 alpha
    buf.seek(0)

    c = pdf_canvas.Canvas(output_path, pagesize=(width_pt, height_pt))
    c.drawImage(ImageReader(buf), 0, 0, width=width_pt, height=height_pt, mask="auto")
    c.showPage()
    c.save()


def export_canvas_to_svg(canvas_view, output_path: str, dpi: int = 300, transparent_bg: bool = False):
    import svgwrite

    out = compose_canvas_image(canvas_view, transparent_bg=transparent_bg)
    page_w, page_h = out.size

    buf = BytesIO()
    out.save(buf, "PNG")
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("ascii")

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{page_w}px", f"{page_h}px"),
        profile="full",
    )
    dwg.add(
        dwg.image(
            href=f"data:image/png;base64,{b64}",
            insert=(0, 0),
            size=(page_w, page_h),
        )
    )
    dwg.save()