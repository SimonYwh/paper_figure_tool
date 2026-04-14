from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from PySide6.QtGui import QColor, QFont

from app.canvas_view import ImageFrameItem, LabelItem, TextBoxItem
from core.image_utils import load_image_thumb_qpixmap
from core.models import CanvasSettings


def _font_to_dict(font: QFont) -> dict:
    return {
        "family": font.family(),
        "point_size": int(font.pointSize() if font.pointSize() > 0 else 14),
        "bold": bool(font.bold()),
        "italic": bool(font.italic()),
        "weight": int(font.weight()),
    }


def _coerce_qfont_weight(v) -> QFont.Weight:
    if isinstance(v, QFont.Weight):
        return v
    try:
        iv = int(v)
    except Exception:
        return QFont.Weight.Normal

    # Qt6 直接值（100~900）
    try:
        return QFont.Weight(iv)
    except Exception:
        pass

    # 兼容旧值（0~99）
    if 0 <= iv <= 99:
        iv = int(round(iv * 10))

    weights = [
        QFont.Weight.Thin,
        QFont.Weight.ExtraLight,
        QFont.Weight.Light,
        QFont.Weight.Normal,
        QFont.Weight.Medium,
        QFont.Weight.DemiBold,
        QFont.Weight.Bold,
        QFont.Weight.ExtraBold,
        QFont.Weight.Black,
    ]
    return min(weights, key=lambda w: abs(int(w) - iv))


def _font_from_dict(d: dict | None, fallback: QFont) -> QFont:
    f = QFont(fallback)
    if not isinstance(d, dict):
        return f

    fam = d.get("family")
    if fam:
        f.setFamily(str(fam))

    ps = int(d.get("point_size", f.pointSize() if f.pointSize() > 0 else 14))
    f.setPointSize(max(1, ps))

    f.setItalic(bool(d.get("italic", f.italic())))

    wt_raw = d.get("weight", int(f.weight()))
    f.setWeight(_coerce_qfont_weight(wt_raw))

    if "bold" in d:
        if bool(d.get("bold", False)):
            if int(f.weight()) < int(QFont.Weight.Bold):
                f.setWeight(QFont.Weight.Bold)
        else:
            if int(f.weight()) > int(QFont.Weight.Normal):
                f.setWeight(QFont.Weight.Normal)

    return f


def _color_to_list(c: Any) -> list[int]:
    if isinstance(c, QColor):
        return [c.red(), c.green(), c.blue(), c.alpha()]
    if isinstance(c, (tuple, list)) and len(c) >= 3:
        a = int(c[3]) if len(c) >= 4 else 255
        return [int(c[0]), int(c[1]), int(c[2]), a]
    return [0, 0, 0, 255]


def _list_to_qcolor(v: Any, default: QColor = QColor(0, 0, 0)) -> QColor:
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        a = int(v[3]) if len(v) >= 4 else 255
        return QColor(int(v[0]), int(v[1]), int(v[2]), a)
    return QColor(default)


def _load_thumb_pixmap(path: str, max_thumb: int = 2200):
    return load_image_thumb_qpixmap(path, max_thumb=max_thumb)


def _cache_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _get_thumb_with_cache(path: str, max_thumb: int = 2200, image_cache: dict | None = None):
    key = _cache_key(path)
    if isinstance(image_cache, dict):
        v = image_cache.get(key)
        if isinstance(v, tuple) and len(v) == 2:
            pm, sz = v
            try:
                if not pm.isNull():
                    return pm, sz
            except Exception:
                pass

    pm, sz = _load_thumb_pixmap(path, max_thumb=max_thumb)
    if isinstance(image_cache, dict):
        image_cache[key] = (pm, sz)
    return pm, sz


def build_project_dict(canvas_settings: CanvasSettings, canvas_view) -> dict:
    scene = canvas_view.scene()
    page = canvas_view.page_rect_item

    data = {
        "version": "0.4.2",
        "canvas": {
            "width_mm": float(canvas_settings.width_mm),
            "height_mm": float(canvas_settings.height_mm),
            "dpi": int(canvas_settings.dpi),
        },
        "items": [],
    }

    items = [it for it in scene.items() if it is not page]
    items = sorted(items, key=lambda it: (it.zValue(), it.sceneBoundingRect().top(), it.sceneBoundingRect().left()))

    for it in items:
        if isinstance(it, ImageFrameItem):
            fw, fh = it.frame_size()
            data["items"].append(
                {
                    "type": "image",
                    "source_path": str(it.source_path),
                    "display_name": str(getattr(it, "display_name", "") or ""),
                    "x": float(it.pos().x()),
                    "y": float(it.pos().y()),
                    "z": float(it.zValue()),
                    "frame_w": int(fw),
                    "frame_h": int(fh),
                    "fill_mode": str(getattr(it, "fill_mode", "fit")),
                    "rot90_steps": int(getattr(it, "rot90_steps", 0)) % 4,
                    "flip_h": bool(getattr(it, "flip_h", False)),
                    "flip_v": bool(getattr(it, "flip_v", False)),
                    "border_width": int(getattr(it, "border_width", 0)),
                    "border_color": _color_to_list(getattr(it, "border_color", (0, 0, 0))),
                }
            )

        elif isinstance(it, LabelItem):
            data["items"].append(
                {
                    "type": "label",
                    "text": str(it.text),
                    "x": float(it.pos().x()),
                    "y": float(it.pos().y()),
                    "z": float(it.zValue()),
                    "padding": int(getattr(it, "padding", 4)),
                    "font": _font_to_dict(it.font_obj),
                    "text_color": _color_to_list(getattr(it, "text_color", QColor(0, 0, 0))),
                    "bg_enabled": bool(getattr(it, "bg_enabled", False)),
                    "bg_color": _color_to_list(getattr(it, "bg_color", QColor(0, 0, 0))),
                    "is_auto_label": bool(getattr(it, "is_auto_label", False)),
                }
            )

        elif isinstance(it, TextBoxItem):
            data["items"].append(
                {
                    "type": "textbox",
                    "text": str(it.toPlainText()),
                    "x": float(it.pos().x()),
                    "y": float(it.pos().y()),
                    "z": float(it.zValue()),
                    "font": _font_to_dict(it.font()),
                    "width": float(getattr(it, "_box_w", max(80.0, it.textWidth()))),
                    "height": float(getattr(it, "_box_h", it.boundingRect().height())),
                    "lock_position": bool(getattr(it, "_lock_position", False)),
                    "lock_size": bool(getattr(it, "_lock_size", False)),
                    "text_color": _color_to_list(getattr(it, "_text_color", it.defaultTextColor())),
                    "fill_color": _color_to_list(getattr(it, "_fill_color", QColor(255, 255, 255))),
                    "fill_alpha": int(getattr(it, "_fill_alpha", 70)),
                    "border_color": _color_to_list(getattr(it, "_border_color", QColor(170, 170, 170))),
                    "border_width": int(getattr(it, "_border_width", 1)),
                }
            )

    return data


def apply_project_dict(
    data: dict,
    canvas_view,
    *,
    default_fill_mode: str = "fit",
    max_thumb: int = 2200,
    base_dir: str | None = None,
    image_cache: dict | None = None,
):
    scene = canvas_view.scene()
    page = canvas_view.page_rect_item

    for it in list(scene.items()):
        if it is page:
            continue
        scene.removeItem(it)

    items = data.get("items", [])
    if not isinstance(items, list):
        return []

    missing_paths = []

    for obj in items:
        if not isinstance(obj, dict):
            continue
        t = obj.get("type", "")

        if t == "image":
            raw_path = str(obj.get("source_path", "")).strip()
            if not raw_path:
                continue

            path = raw_path
            if not os.path.isabs(path) and base_dir:
                path = os.path.normpath(os.path.join(base_dir, path))

            if not os.path.exists(path):
                missing_paths.append(raw_path)
                continue

            try:
                pixmap, (ow, oh) = _get_thumb_with_cache(path, max_thumb=max_thumb, image_cache=image_cache)
            except Exception:
                missing_paths.append(raw_path)
                continue

            fill_mode = str(obj.get("fill_mode", default_fill_mode))
            if fill_mode not in ("fit", "cover"):
                fill_mode = default_fill_mode

            display_name = str(obj.get("display_name", "") or "").strip()
            item = ImageFrameItem(
                path,
                (ow, oh),
                pixmap,
                canvas_view,
                fill_mode=fill_mode,
                display_name=display_name,
            )
            item.rot90_steps = int(obj.get("rot90_steps", 0)) % 4
            item.flip_h = bool(obj.get("flip_h", False))
            item.flip_v = bool(obj.get("flip_v", False))

            fw = int(obj.get("frame_w", max(1, pixmap.width())))
            fh = int(obj.get("frame_h", max(1, pixmap.height())))
            item.set_frame_size(fw, fh)

            bw = int(obj.get("border_width", 0))
            bc = obj.get("border_color", [0, 0, 0, 255])
            c = _list_to_qcolor(bc, QColor(0, 0, 0))
            item.set_border(bw, c)

            item.setPos(float(obj.get("x", 0)), float(obj.get("y", 0)))
            item.setZValue(float(obj.get("z", 0)))
            scene.addItem(item)

        elif t == "label":
            font = _font_from_dict(obj.get("font"), QFont("Times New Roman", 18, QFont.Weight.Bold))
            lb = LabelItem(str(obj.get("text", "")), canvas_view, font=font, padding=int(obj.get("padding", 4)))

            bg_enabled = bool(obj.get("bg_enabled", False))
            lb.set_black_bg(bg_enabled)
            if not bg_enabled:
                lb.text_color = _list_to_qcolor(obj.get("text_color"), QColor(0, 0, 0))
                lb.bg_color = _list_to_qcolor(obj.get("bg_color"), QColor(0, 0, 0))

            lb.is_auto_label = bool(obj.get("is_auto_label", False))
            lb.setPos(float(obj.get("x", 0)), float(obj.get("y", 0)))
            lb.setZValue(float(obj.get("z", 3000)))
            scene.addItem(lb)

        elif t == "textbox":
            font = _font_from_dict(obj.get("font"), QFont("Microsoft YaHei UI", 14))
            tb = TextBoxItem(
                str(obj.get("text", "")),
                canvas_view,
                font=font,
                width=float(obj.get("width", 320)),
            )

            h = float(obj.get("height", getattr(tb, "_box_h", 60)))
            if hasattr(tb, "_set_box_height"):
                tb._set_box_height(h)
            if hasattr(tb, "_sync_height_to_content"):
                tb._sync_height_to_content(force=False)

            if hasattr(tb, "set_position_locked"):
                tb.set_position_locked(bool(obj.get("lock_position", False)))
            if hasattr(tb, "set_size_locked"):
                tb.set_size_locked(bool(obj.get("lock_size", False)))

            fill_c = _list_to_qcolor(obj.get("fill_color"), QColor(255, 255, 255))
            fill_alpha = obj.get("fill_alpha", fill_c.alpha())
            if hasattr(tb, "set_style"):
                tb.set_style(
                    text_color=_list_to_qcolor(obj.get("text_color"), QColor(0, 0, 0)),
                    fill_color=QColor(fill_c.red(), fill_c.green(), fill_c.blue()),
                    fill_alpha=int(fill_alpha),
                    border_color=_list_to_qcolor(obj.get("border_color"), QColor(170, 170, 170)),
                    border_width=int(obj.get("border_width", 1)),
                )

            tb.setPos(float(obj.get("x", 0)), float(obj.get("y", 0)))
            tb.setZValue(float(obj.get("z", 3400)))
            scene.addItem(tb)

    return missing_paths


def save_project_file(path: str, data: dict):
    target_path = os.path.abspath(path)
    parent_dir = os.path.dirname(target_path) or "."
    os.makedirs(parent_dir, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(prefix=".figproj-", suffix=".tmp", dir=parent_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


def load_project_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("项目文件格式错误。")
    return data