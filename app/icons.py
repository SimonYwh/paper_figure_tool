"""轻量矢量图标库

通过 QPainter 在运行时绘制极简线性图标，避免依赖外部 SVG / 字体文件。
所有图标统一为线性风格，可按主题色着色，保证在任意 DPI 下保持锐利。
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


# 默认线宽与颜色
_DEFAULT_COLOR = "#4E5969"
_DEFAULT_SIZE = 20


def _prepare(size: int):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def _pen(color: str, width: float = 1.6) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


# ============================================================
# 单图标绘制函数：参数 (painter, size, color)
# 坐标系：以 size 为基准的等比绘制，留 ~3px 视觉留白
# ============================================================

def _draw_new(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 文档轮廓 + 折角 + 加号
    path = QPainterPath()
    path.moveTo(s * 0.30, s * 0.18)
    path.lineTo(s * 0.62, s * 0.18)
    path.lineTo(s * 0.78, s * 0.34)
    path.lineTo(s * 0.78, s * 0.82)
    path.lineTo(s * 0.30, s * 0.82)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.62, s * 0.18), QPointF(s * 0.62, s * 0.34))
    p.drawLine(QPointF(s * 0.62, s * 0.34), QPointF(s * 0.78, s * 0.34))
    # 加号
    cx, cy = s * 0.54, s * 0.60
    r = s * 0.10
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))


def _draw_open(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 简洁文件夹
    path = QPainterPath()
    path.moveTo(s * 0.16, s * 0.32)
    path.lineTo(s * 0.40, s * 0.32)
    path.lineTo(s * 0.48, s * 0.42)
    path.lineTo(s * 0.84, s * 0.42)
    path.lineTo(s * 0.84, s * 0.78)
    path.lineTo(s * 0.16, s * 0.78)
    path.closeSubpath()
    p.drawPath(path)


def _draw_save(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    rect = QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64)
    p.drawRoundedRect(rect, s * 0.06, s * 0.06)
    # 顶部缺口
    p.drawLine(QPointF(s * 0.34, s * 0.18), QPointF(s * 0.34, s * 0.34))
    p.drawLine(QPointF(s * 0.34, s * 0.34), QPointF(s * 0.62, s * 0.34))
    p.drawLine(QPointF(s * 0.62, s * 0.34), QPointF(s * 0.62, s * 0.18))
    # 底部小框
    p.drawRect(QRectF(s * 0.30, s * 0.54, s * 0.40, s * 0.22))


def _draw_undo(p: QPainter, s: int, c: str):
    p.setPen(_pen(c, 1.7))
    # 左转弧线 + 箭头
    path = QPainterPath()
    path.arcMoveTo(QRectF(s * 0.20, s * 0.26, s * 0.60, s * 0.50), 200)
    path.arcTo(QRectF(s * 0.20, s * 0.26, s * 0.60, s * 0.50), 200, 130)
    p.drawPath(path)
    # 箭头
    ax, ay = s * 0.24, s * 0.40
    p.drawLine(QPointF(ax, ay), QPointF(ax - s * 0.03, ay + s * 0.14))
    p.drawLine(QPointF(ax, ay), QPointF(ax + s * 0.14, ay + s * 0.03))


def _draw_redo(p: QPainter, s: int, c: str):
    p.setPen(_pen(c, 1.7))
    path = QPainterPath()
    path.arcMoveTo(QRectF(s * 0.20, s * 0.26, s * 0.60, s * 0.50), 340)
    path.arcTo(QRectF(s * 0.20, s * 0.26, s * 0.60, s * 0.50), 340, -130)
    p.drawPath(path)
    ax, ay = s * 0.76, s * 0.40
    p.drawLine(QPointF(ax, ay), QPointF(ax + s * 0.03, ay + s * 0.14))
    p.drawLine(QPointF(ax, ay), QPointF(ax - s * 0.14, ay + s * 0.03))


def _draw_fit(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 四角箭头
    cs = s * 0.16  # corner length
    pad = s * 0.20
    pts = [
        # 左上
        ((pad, pad + cs), (pad, pad), (pad + cs, pad)),
        # 右上
        ((s - pad - cs, pad), (s - pad, pad), (s - pad, pad + cs)),
        # 左下
        ((pad, s - pad - cs), (pad, s - pad), (pad + cs, s - pad)),
        # 右下
        ((s - pad - cs, s - pad), (s - pad, s - pad), (s - pad, s - pad - cs)),
    ]
    for a, b, d in pts:
        p.drawLine(QPointF(*a), QPointF(*b))
        p.drawLine(QPointF(*b), QPointF(*d))


def _draw_export(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 向上箭头 + 底托
    p.drawLine(QPointF(s * 0.50, s * 0.20), QPointF(s * 0.50, s * 0.62))
    p.drawLine(QPointF(s * 0.34, s * 0.36), QPointF(s * 0.50, s * 0.20))
    p.drawLine(QPointF(s * 0.66, s * 0.36), QPointF(s * 0.50, s * 0.20))
    p.drawLine(QPointF(s * 0.20, s * 0.78), QPointF(s * 0.80, s * 0.78))


def _draw_import(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 图片框 + 山 + +
    rect = QRectF(s * 0.18, s * 0.22, s * 0.56, s * 0.50)
    p.drawRoundedRect(rect, s * 0.05, s * 0.05)
    # 山
    p.drawLine(QPointF(s * 0.24, s * 0.62), QPointF(s * 0.40, s * 0.46))
    p.drawLine(QPointF(s * 0.40, s * 0.46), QPointF(s * 0.52, s * 0.58))
    p.drawLine(QPointF(s * 0.52, s * 0.58), QPointF(s * 0.62, s * 0.50))
    p.drawLine(QPointF(s * 0.62, s * 0.50), QPointF(s * 0.70, s * 0.62))
    # 加号
    cx, cy = s * 0.74, s * 0.74
    r = s * 0.10
    p.setPen(_pen(c, 1.8))
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))


def _draw_canvas(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.56), s * 0.05, s * 0.05)
    # 内部留白线
    p.drawLine(QPointF(s * 0.18, s * 0.36), QPointF(s * 0.82, s * 0.36))


def _draw_grid(p: QPainter, s: int, c: str, rows: int, cols: int):
    p.setPen(_pen(c))
    rect = QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64)
    p.drawRoundedRect(rect, s * 0.04, s * 0.04)
    for i in range(1, cols):
        x = rect.left() + rect.width() * i / cols
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
    for i in range(1, rows):
        y = rect.top() + rect.height() * i / rows
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))


def _draw_label(p: QPainter, s: int, c: str):
    p.setPen(_pen(c, 1.7))
    # Aa
    p.drawLine(QPointF(s * 0.22, s * 0.74), QPointF(s * 0.40, s * 0.26))
    p.drawLine(QPointF(s * 0.40, s * 0.26), QPointF(s * 0.58, s * 0.74))
    p.drawLine(QPointF(s * 0.28, s * 0.58), QPointF(s * 0.52, s * 0.58))
    # 小o
    p.drawEllipse(QPointF(s * 0.72, s * 0.66), s * 0.10, s * 0.10)


def _draw_textbox(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.26, s * 0.68, s * 0.48), s * 0.04, s * 0.04)
    # T
    p.drawLine(QPointF(s * 0.32, s * 0.40), QPointF(s * 0.62, s * 0.40))
    p.drawLine(QPointF(s * 0.47, s * 0.40), QPointF(s * 0.47, s * 0.60))


def _draw_align(p: QPainter, s: int, c: str, kind: str):
    p.setPen(_pen(c))
    # 三横条 + 对齐线
    bars = [
        (s * 0.30, s * 0.50),  # width
        (s * 0.20, s * 0.45),
        (s * 0.40, s * 0.55),
    ]
    if kind == "left":
        x0 = s * 0.22
        ys = [s * 0.30, s * 0.50, s * 0.70]
        for y, (w, _h) in zip(ys, bars):
            p.drawRect(QRectF(x0, y - 4, w, 8))
        p.drawLine(QPointF(x0, s * 0.20), QPointF(x0, s * 0.80))
    elif kind == "right":
        x1 = s * 0.78
        ys = [s * 0.30, s * 0.50, s * 0.70]
        for y, (w, _h) in zip(ys, bars):
            p.drawRect(QRectF(x1 - w, y - 4, w, 8))
        p.drawLine(QPointF(x1, s * 0.20), QPointF(x1, s * 0.80))
    elif kind == "hcenter":
        cx = s * 0.50
        ys = [s * 0.30, s * 0.50, s * 0.70]
        for y, (w, _h) in zip(ys, bars):
            p.drawRect(QRectF(cx - w / 2, y - 4, w, 8))
        p.drawLine(QPointF(cx, s * 0.20), QPointF(cx, s * 0.80))
    elif kind == "top":
        y0 = s * 0.22
        xs = [s * 0.30, s * 0.50, s * 0.70]
        for x, (h, _w) in zip(xs, bars):
            p.drawRect(QRectF(x - 4, y0, 8, h))
        p.drawLine(QPointF(s * 0.20, y0), QPointF(s * 0.80, y0))
    elif kind == "bottom":
        y1 = s * 0.78
        xs = [s * 0.30, s * 0.50, s * 0.70]
        for x, (h, _w) in zip(xs, bars):
            p.drawRect(QRectF(x - 4, y1 - h, 8, h))
        p.drawLine(QPointF(s * 0.20, y1), QPointF(s * 0.80, y1))
    elif kind == "vcenter":
        cy = s * 0.50
        xs = [s * 0.30, s * 0.50, s * 0.70]
        for x, (h, _w) in zip(xs, bars):
            p.drawRect(QRectF(x - 4, cy - h / 2, 8, h))
        p.drawLine(QPointF(s * 0.20, cy), QPointF(s * 0.80, cy))


def _draw_trash(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 桶身
    p.drawLine(QPointF(s * 0.30, s * 0.32), QPointF(s * 0.34, s * 0.82))
    p.drawLine(QPointF(s * 0.70, s * 0.32), QPointF(s * 0.66, s * 0.82))
    p.drawLine(QPointF(s * 0.34, s * 0.82), QPointF(s * 0.66, s * 0.82))
    # 盖
    p.drawLine(QPointF(s * 0.20, s * 0.30), QPointF(s * 0.80, s * 0.30))
    # 把手
    p.drawLine(QPointF(s * 0.40, s * 0.20), QPointF(s * 0.60, s * 0.20))
    p.drawLine(QPointF(s * 0.40, s * 0.20), QPointF(s * 0.40, s * 0.30))
    p.drawLine(QPointF(s * 0.60, s * 0.20), QPointF(s * 0.60, s * 0.30))


def _draw_snap(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 网格 + 磁铁
    for i in range(3):
        y = s * (0.24 + i * 0.20)
        p.drawLine(QPointF(s * 0.18, y), QPointF(s * 0.82, y))
    for i in range(3):
        x = s * (0.24 + i * 0.20)
        p.drawLine(QPointF(x, s * 0.18), QPointF(x, s * 0.82))


def _draw_layers(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    # 三层菱形堆叠
    points_top = QPolygonF([
        QPointF(s * 0.50, s * 0.20),
        QPointF(s * 0.82, s * 0.36),
        QPointF(s * 0.50, s * 0.52),
        QPointF(s * 0.18, s * 0.36),
    ])
    p.drawPolygon(points_top)
    p.drawLine(QPointF(s * 0.18, s * 0.50), QPointF(s * 0.50, s * 0.66))
    p.drawLine(QPointF(s * 0.50, s * 0.66), QPointF(s * 0.82, s * 0.50))
    p.drawLine(QPointF(s * 0.18, s * 0.64), QPointF(s * 0.50, s * 0.80))
    p.drawLine(QPointF(s * 0.50, s * 0.80), QPointF(s * 0.82, s * 0.64))


def _draw_history(p: QPainter, s: int, c: str):
    p.setPen(_pen(c, 1.6))
    p.drawArc(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 30 * 16, 300 * 16)
    # 时针指针
    cx, cy = s * 0.50, s * 0.50
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy - s * 0.18))
    p.drawLine(QPointF(cx, cy), QPointF(cx + s * 0.14, cy))
    # 起始小圆
    p.drawEllipse(QPointF(s * 0.74, s * 0.30), 1.4, 1.4)


def _draw_info(p: QPainter, s: int, c: str):
    p.setPen(_pen(c))
    p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.30, s * 0.30)
    p.drawLine(QPointF(s * 0.50, s * 0.46), QPointF(s * 0.50, s * 0.66))
    p.drawEllipse(QPointF(s * 0.50, s * 0.36), 1.2, 1.2)


_DRAWERS = {
    "new": _draw_new,
    "open": _draw_open,
    "save": _draw_save,
    "undo": _draw_undo,
    "redo": _draw_redo,
    "fit": _draw_fit,
    "export": _draw_export,
    "import": _draw_import,
    "canvas": _draw_canvas,
    "label": _draw_label,
    "textbox": _draw_textbox,
    "trash": _draw_trash,
    "snap": _draw_snap,
    "layers": _draw_layers,
    "history": _draw_history,
    "info": _draw_info,
    "align_left": lambda p, s, c: _draw_align(p, s, c, "left"),
    "align_right": lambda p, s, c: _draw_align(p, s, c, "right"),
    "align_hcenter": lambda p, s, c: _draw_align(p, s, c, "hcenter"),
    "align_top": lambda p, s, c: _draw_align(p, s, c, "top"),
    "align_bottom": lambda p, s, c: _draw_align(p, s, c, "bottom"),
    "align_vcenter": lambda p, s, c: _draw_align(p, s, c, "vcenter"),
    "grid_2x2": lambda p, s, c: _draw_grid(p, s, c, 2, 2),
    "grid_2x3": lambda p, s, c: _draw_grid(p, s, c, 2, 3),
    "grid_3x2": lambda p, s, c: _draw_grid(p, s, c, 3, 2),
    "grid_2x4": lambda p, s, c: _draw_grid(p, s, c, 2, 4),
    "grid_4x2": lambda p, s, c: _draw_grid(p, s, c, 4, 2),
    "grid_custom": lambda p, s, c: _draw_grid(p, s, c, 3, 3),
}


@lru_cache(maxsize=256)
def _make_pixmap(name: str, color: str, size: int) -> QPixmap:
    pm, p = _prepare(size)
    drawer = _DRAWERS.get(name)
    if drawer is not None:
        drawer(p, size, color)
    p.end()
    return pm


def make_icon(name: str, color: str = _DEFAULT_COLOR, size: int = _DEFAULT_SIZE) -> QIcon:
    """生成线性矢量图标。

    name: 上方 _DRAWERS 字典中的键
    color: 16 进制颜色，例如 "#4E5969"
    size:  绘制基础像素（QIcon 会按需缩放保持锐利）
    """
    icon = QIcon()
    icon.addPixmap(_make_pixmap(name, color, size))
    # 高 DPI 备份
    icon.addPixmap(_make_pixmap(name, color, size * 2))
    return icon
