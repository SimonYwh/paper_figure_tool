"""全局用户预设持久化管理器

使用 QSettings 将结构化预设以 JSON 形式存储到本机配置，
所有项目可复用。
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QSettings

_ORG = "PaperFigureTool"
_APP = "PaperFigureTool"

# QSettings 键名
_KEY_CANVAS_PRESETS = "presets/canvas"
_KEY_NUMBERING_PRESETS = "presets/numbering"
_KEY_LAYOUT_PRESETS = "presets/layout"


def _settings() -> QSettings:
    return QSettings(_ORG, _APP)


def _load_json(key: str) -> list[dict[str, Any]]:
    """从 QSettings 读取 JSON 数组，不存在或解析失败时返回空列表。"""
    s = _settings()
    raw = s.value(key, "[]")
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _save_json(key: str, data: list[dict[str, Any]]) -> None:
    """将 JSON 数组写入 QSettings。"""
    s = _settings()
    s.setValue(key, json.dumps(data, ensure_ascii=False))


# ============================================================
# 画布预设
# ============================================================

def load_canvas_presets() -> list[dict[str, Any]]:
    """返回画布预设列表，每项形如:
    {"name": "我的A3", "width_mm": 297.0, "height_mm": 420.0, "dpi": 300}
    """
    return _load_json(_KEY_CANVAS_PRESETS)


def save_canvas_presets(presets: list[dict[str, Any]]) -> None:
    _save_json(_KEY_CANVAS_PRESETS, presets)


def add_canvas_preset(name: str, width_mm: float, height_mm: float, dpi: int) -> None:
    presets = load_canvas_presets()
    # 覆盖同名
    presets = [p for p in presets if p.get("name") != name]
    presets.append({"name": name, "width_mm": width_mm, "height_mm": height_mm, "dpi": dpi})
    save_canvas_presets(presets)


def delete_canvas_preset(name: str) -> None:
    presets = [p for p in load_canvas_presets() if p.get("name") != name]
    save_canvas_presets(presets)


# ============================================================
# 上次画布设置记忆（跨会话持久化）
# ============================================================

_KEY_LAST_CANVAS = "canvas/last_settings"


def save_last_canvas_settings(width_mm: float, height_mm: float, dpi: int) -> None:
    """保存当前画布设置，下次启动时自动恢复。"""
    s = _settings()
    s.setValue(_KEY_LAST_CANVAS, json.dumps({
        "width_mm": float(width_mm),
        "height_mm": float(height_mm),
        "dpi": int(dpi),
    }, ensure_ascii=False))


def load_last_canvas_settings() -> dict | None:
    """加载上次的画布设置，不存在时返回 None。"""
    s = _settings()
    raw = s.value(_KEY_LAST_CANVAS, "")
    if isinstance(raw, str) and raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# ============================================================
# 编号样式预设
# ============================================================

def load_numbering_presets() -> list[dict[str, Any]]:
    """返回编号样式预设列表，每项形如:
    {"name": "默认", "style": "a, b, c", "font_family": "Times New Roman",
     "font_size": 20, "corner": "左上", "offset_x": 8, "offset_y": 8, "black_bg": false}
    """
    return _load_json(_KEY_NUMBERING_PRESETS)


def save_numbering_presets(presets: list[dict[str, Any]]) -> None:
    _save_json(_KEY_NUMBERING_PRESETS, presets)


def add_numbering_preset(name: str, cfg: dict[str, Any]) -> None:
    presets = load_numbering_presets()
    presets = [p for p in presets if p.get("name") != name]
    entry = {"name": name}
    entry.update(cfg)
    presets.append(entry)
    save_numbering_presets(presets)


def delete_numbering_preset(name: str) -> None:
    presets = [p for p in load_numbering_presets() if p.get("name") != name]
    save_numbering_presets(presets)


# ============================================================
# 排版样式预设
# ============================================================

def load_layout_presets() -> list[dict[str, Any]]:
    """返回排版样式预设列表，每项形如:
    {"name": "2x3", "rows": 2, "cols": 3}
    """
    return _load_json(_KEY_LAYOUT_PRESETS)


def save_layout_presets(presets: list[dict[str, Any]]) -> None:
    _save_json(_KEY_LAYOUT_PRESETS, presets)


def add_layout_preset(name: str, rows: int, cols: int) -> None:
    presets = load_layout_presets()
    presets = [p for p in presets if p.get("name") != name]
    presets.append({"name": name, "rows": rows, "cols": cols})
    save_layout_presets(presets)


def delete_layout_preset(name: str) -> None:
    presets = [p for p in load_layout_presets() if p.get("name") != name]
    save_layout_presets(presets)
