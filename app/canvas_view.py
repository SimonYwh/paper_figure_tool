from __future__ import annotations

import os
from typing import List, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCursor,
    QTransform,
)

from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QMenu,
)


def _snap_point(pt: QPointF, grid_size: int) -> QPointF:
    g = max(1, int(grid_size))
    return QPointF(round(pt.x() / g) * g, round(pt.y() / g) * g)


class ImageFrameItem(QGraphicsPixmapItem):
    """画布中的单张子图项（可拖拽、可选择、固定框尺寸，支持90°旋转/翻转/边框）。"""

    def __init__(
        self,
        source_path: str,
        source_size: Tuple[int, int],
        thumb_pixmap: QPixmap,
        canvas_view: "CanvasView",
        fill_mode: str = "fit",
        display_name: str | None = None,
    ):
        super().__init__()
        self.source_path = source_path
        self.source_size = source_size
        self.thumb_pixmap = thumb_pixmap
        self.canvas_view = canvas_view
        self.fill_mode = fill_mode
        base = os.path.basename(source_path) if source_path else ""
        self.display_name = (display_name or base or "未命名素材").strip() or "未命名素材"

        self._frame_w = max(1, thumb_pixmap.width())
        self._frame_h = max(1, thumb_pixmap.height())

        self.rot90_steps = 0
        self.flip_h = False
        self.flip_v = False
        self.border_width = 0
        self.border_color = (0, 0, 0)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.set_frame_size(self._frame_w, self._frame_h)

    def frame_size(self) -> Tuple[int, int]:
        return self._frame_w, self._frame_h

    def set_fill_mode(self, mode: str):
        self.fill_mode = mode if mode in ("fit", "cover") else "fit"
        self.set_frame_size(self._frame_w, self._frame_h)

    def rotate_left(self):
        self.rot90_steps = (self.rot90_steps - 1) % 4
        self.set_frame_size(self._frame_w, self._frame_h)

    def rotate_right(self):
        self.rot90_steps = (self.rot90_steps + 1) % 4
        self.set_frame_size(self._frame_w, self._frame_h)

    def flip_horizontal(self):
        self.flip_h = not self.flip_h
        self.set_frame_size(self._frame_w, self._frame_h)

    def flip_vertical(self):
        self.flip_v = not self.flip_v
        self.set_frame_size(self._frame_w, self._frame_h)

    def reset_transform_ops(self):
        self.rot90_steps = 0
        self.flip_h = False
        self.flip_v = False
        self.set_frame_size(self._frame_w, self._frame_h)

    def set_border(self, width: int, color):
        self.border_width = max(0, int(width))
        if isinstance(color, QColor):
            self.border_color = (color.red(), color.green(), color.blue())
        elif isinstance(color, (tuple, list)) and len(color) >= 3:
            self.border_color = (int(color[0]), int(color[1]), int(color[2]))
        self.update()

    def _processed_thumb(self) -> QPixmap:
        if self.thumb_pixmap.isNull():
            return self.thumb_pixmap

        img = self.thumb_pixmap.toImage()

        if self.flip_h or self.flip_v:
            img = img.mirrored(self.flip_h, self.flip_v)

        steps = int(self.rot90_steps) % 4
        if steps:
            tr = QTransform()
            tr.rotate(-90 * steps)
            img = img.transformed(tr, Qt.TransformationMode.SmoothTransformation)

        return QPixmap.fromImage(img)

    def set_frame_size(self, w: float, h: float) -> None:
        self._frame_w = max(1, int(round(w)))
        self._frame_h = max(1, int(round(h)))

        src_pm = self._processed_thumb()
        if src_pm.isNull():
            empty = QPixmap(self._frame_w, self._frame_h)
            empty.fill(QColor("white"))
            self.setPixmap(empty)
            return

        if self.fill_mode == "cover":
            cover = src_pm.scaled(
                self._frame_w,
                self._frame_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = max(0, (cover.width() - self._frame_w) // 2)
            y = max(0, (cover.height() - self._frame_h) // 2)
            self.setPixmap(cover.copy(x, y, self._frame_w, self._frame_h))
        else:
            fit = src_pm.scaled(
                self._frame_w,
                self._frame_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            canvas = QPixmap(self._frame_w, self._frame_h)
            canvas.fill(QColor("white"))
            p = QPainter(canvas)
            x = (self._frame_w - fit.width()) // 2
            y = (self._frame_h - fit.height()) // 2
            p.drawPixmap(x, y, fit)
            p.end()
            self.setPixmap(canvas)

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.canvas_view
            and self.canvas_view.snap_enabled
            and isinstance(value, QPointF)
        ):
            return _snap_point(value, self.canvas_view.grid_size)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.canvas_view:
            self.canvas_view.notify_modified()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        if self.border_width > 0:
            bw = float(self.border_width)
            r = self.boundingRect().adjusted(bw / 2, bw / 2, -bw / 2, -bw / 2)
            painter.setPen(QPen(QColor(*self.border_color), bw))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())


class LabelItem(QGraphicsItem):
    def __init__(
        self,
        text: str,
        canvas_view: "CanvasView",
        font: QFont | None = None,
        padding: int = 4,
    ):
        super().__init__()
        self.canvas_view = canvas_view
        self.text = text
        self.font_obj = font if font else QFont("Times New Roman", 18, QFont.Weight.Bold)
        self.padding = max(0, int(padding))

        self.text_color = QColor("black")
        self.bg_enabled = False
        self.bg_color = QColor("black")

        self.is_auto_label = False
        self._rect = QRectF()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setZValue(2000)
        self._recalc_rect()

    def _recalc_rect(self):
        fm = QFontMetricsF(self.font_obj)
        tw = fm.horizontalAdvance(self.text)
        th = fm.height()
        w = max(1.0, tw + self.padding * 2)
        h = max(1.0, th + self.padding * 2)
        self._rect = QRectF(0, 0, w, h)

    def boundingRect(self) -> QRectF:
        return self._rect

    def set_text(self, text: str):
        self.prepareGeometryChange()
        self.text = text
        self._recalc_rect()
        self.update()

    def set_font(self, font: QFont):
        self.prepareGeometryChange()
        self.font_obj = QFont(font)
        self._recalc_rect()
        self.update()

    def set_black_bg(self, enabled: bool):
        self.bg_enabled = bool(enabled)
        if enabled:
            self.bg_color = QColor("black")
            self.text_color = QColor("white")
        else:
            self.text_color = QColor("black")
        self.update()

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.canvas_view
            and self.canvas_view.snap_enabled
            and isinstance(value, QPointF)
        ):
            return _snap_point(value, self.canvas_view.grid_size)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.canvas_view:
            self.canvas_view.notify_modified()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.bg_enabled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.bg_color)
            painter.drawRect(self._rect)

        painter.setPen(self.text_color)
        painter.setFont(self.font_obj)
        fm = QFontMetricsF(self.font_obj)
        baseline_y = self.padding + fm.ascent()
        painter.drawText(QPointF(self.padding, baseline_y), self.text)

        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._rect)


class TextBoxItem(QGraphicsTextItem):
    HANDLE_NONE = 0
    HANDLE_LEFT = 1
    HANDLE_TOP = 2
    HANDLE_RIGHT = 3
    HANDLE_BOTTOM = 4
    HANDLE_TOP_LEFT = 5
    HANDLE_TOP_RIGHT = 6
    HANDLE_BOTTOM_LEFT = 7
    HANDLE_BOTTOM_RIGHT = 8

    MODE_NONE = 0
    MODE_MOVE = 1
    MODE_RESIZE = 2

    def __init__(self, text: str, canvas_view: "CanvasView", font: QFont | None = None, width: float = 320):
        super().__init__(text)
        self.canvas_view = canvas_view

        self._min_width = 80.0
        self._min_height = 30.0
        self._handle_size = 8.0

        self._box_w = max(self._min_width, float(width))
        self._box_h = self._min_height

        self._mode = self.MODE_NONE
        self._resize_handle = self.HANDLE_NONE
        self._start_scene_pos = QPointF()
        self._start_item_pos = QPointF()
        self._start_w = self._box_w
        self._start_h = self._box_h

        self._lock_position = False
        self._lock_size = False

        # 文本框样式
        self._text_color = QColor(0, 0, 0)
        self._fill_color = QColor(255, 255, 255)
        self._fill_alpha = 70
        self._border_color = QColor(170, 170, 170)
        self._border_width = 1

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setDefaultTextColor(self._text_color)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setZValue(2600)

        init_font = QFont(font) if isinstance(font, QFont) else QFont("Microsoft YaHei UI", 14)
        super().setFont(init_font)
        super().setTextWidth(self._box_w)
        self._sync_height_to_content(force=True)

        self.document().contentsChanged.connect(self._on_contents_changed)

    # ---------- style ----------
    def set_style(
        self,
        *,
        text_color: QColor | None = None,
        fill_color: QColor | None = None,
        fill_alpha: int | None = None,
        border_color: QColor | None = None,
        border_width: int | None = None,
    ):
        if isinstance(text_color, QColor):
            self._text_color = QColor(text_color)
            self.setDefaultTextColor(self._text_color)

        if isinstance(fill_color, QColor):
            self._fill_color = QColor(fill_color)

        if fill_alpha is not None:
            try:
                a = int(fill_alpha)
            except Exception:
                a = self._fill_alpha
            self._fill_alpha = max(0, min(255, a))

        if isinstance(border_color, QColor):
            self._border_color = QColor(border_color)

        if border_width is not None:
            try:
                w = int(border_width)
            except Exception:
                w = self._border_width
            self._border_width = max(0, w)

        self.update()

    def get_style_dict(self) -> dict:
        return {
            "text_color": QColor(self._text_color),
            "fill_color": QColor(self._fill_color),
            "fill_alpha": int(self._fill_alpha),
            "border_color": QColor(self._border_color),
            "border_width": int(self._border_width),
        }

    # ---------- lock ----------
    def set_position_locked(self, locked: bool):
        self._lock_position = bool(locked)
        self.update()

    def set_size_locked(self, locked: bool):
        self._lock_size = bool(locked)
        if self._lock_size and self._mode == self.MODE_RESIZE:
            self._mode = self.MODE_NONE
            self._resize_handle = self.HANDLE_NONE
        self.update()

    def is_position_locked(self) -> bool:
        return self._lock_position

    def is_size_locked(self) -> bool:
        return self._lock_size

    # ---------- geometry ----------
    def _content_rect(self) -> QRectF:
        return super().boundingRect()

    def _frame_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, self._box_w, self._box_h)

    def boundingRect(self) -> QRectF:
        hs = self._handle_size
        return self._frame_rect().adjusted(-hs, -hs, hs, hs)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def _sync_height_to_content(self, force: bool = False):
        content_h = super().boundingRect().height()
        need_h = max(self._min_height, content_h)
        if force or self._box_h < need_h - 0.1:
            self.prepareGeometryChange()
            self._box_h = need_h

    def _set_box_width(self, w: float):
        w = max(self._min_width, float(w))
        if abs(w - self._box_w) > 0.1:
            self.prepareGeometryChange()
            self._box_w = w
            super().setTextWidth(self._box_w)

    def _set_box_height(self, h: float):
        h = max(self._min_height, float(h))
        if abs(h - self._box_h) > 0.1:
            self.prepareGeometryChange()
            self._box_h = h

    def setFont(self, font: QFont):
        if isinstance(font, bool):
            return
        if not isinstance(font, QFont):
            try:
                font = QFont(font)
            except Exception:
                return
        super().setFont(font)
        self._sync_height_to_content(force=False)
        self.update()

    # ---------- handles ----------
    def _handle_rects(self) -> dict[int, QRectF]:
        r = self._frame_rect()
        hs = self._handle_size
        hh = hs / 2.0
        cx = r.center().x()
        cy = r.center().y()
        return {
            self.HANDLE_TOP_LEFT: QRectF(r.left() - hh, r.top() - hh, hs, hs),
            self.HANDLE_TOP: QRectF(cx - hh, r.top() - hh, hs, hs),
            self.HANDLE_TOP_RIGHT: QRectF(r.right() - hh, r.top() - hh, hs, hs),
            self.HANDLE_RIGHT: QRectF(r.right() - hh, cy - hh, hs, hs),
            self.HANDLE_BOTTOM_RIGHT: QRectF(r.right() - hh, r.bottom() - hh, hs, hs),
            self.HANDLE_BOTTOM: QRectF(cx - hh, r.bottom() - hh, hs, hs),
            self.HANDLE_BOTTOM_LEFT: QRectF(r.left() - hh, r.bottom() - hh, hs, hs),
            self.HANDLE_LEFT: QRectF(r.left() - hh, cy - hh, hs, hs),
        }

    def _edge_hit(self, pos: QPointF) -> int:
        if self._lock_size:
            return self.HANDLE_NONE

        r = self._frame_rect()
        tol = 5.0
        x, y = pos.x(), pos.y()

        on_left = abs(x - r.left()) <= tol and (r.top() - tol <= y <= r.bottom() + tol)
        on_right = abs(x - r.right()) <= tol and (r.top() - tol <= y <= r.bottom() + tol)
        on_top = abs(y - r.top()) <= tol and (r.left() - tol <= x <= r.right() + tol)
        on_bottom = abs(y - r.bottom()) <= tol and (r.left() - tol <= x <= r.right() + tol)

        if on_left and on_top:
            return self.HANDLE_TOP_LEFT
        if on_right and on_top:
            return self.HANDLE_TOP_RIGHT
        if on_left and on_bottom:
            return self.HANDLE_BOTTOM_LEFT
        if on_right and on_bottom:
            return self.HANDLE_BOTTOM_RIGHT
        if on_left:
            return self.HANDLE_LEFT
        if on_right:
            return self.HANDLE_RIGHT
        if on_top:
            return self.HANDLE_TOP
        if on_bottom:
            return self.HANDLE_BOTTOM
        return self.HANDLE_NONE

    def _hit_test_handle(self, pos: QPointF) -> int:
        if self._lock_size:
            return self.HANDLE_NONE
        for h, rr in self._handle_rects().items():
            if rr.contains(pos):
                return h
        return self._edge_hit(pos)

    def _cursor_for_handle(self, h: int):
        if h in (self.HANDLE_LEFT, self.HANDLE_RIGHT):
            return Qt.CursorShape.SizeHorCursor
        if h in (self.HANDLE_TOP, self.HANDLE_BOTTOM):
            return Qt.CursorShape.SizeVerCursor
        if h in (self.HANDLE_TOP_LEFT, self.HANDLE_BOTTOM_RIGHT):
            return Qt.CursorShape.SizeFDiagCursor
        if h in (self.HANDLE_TOP_RIGHT, self.HANDLE_BOTTOM_LEFT):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    def _selected_textboxes(self):
        sc = self.scene()
        if sc is None:
            return [self]
        items = [it for it in sc.selectedItems() if isinstance(it, TextBoxItem)]
        return items if items else [self]

    # ---------- events ----------
    def hoverMoveEvent(self, event):
        if self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction:
            self.setCursor(Qt.CursorShape.IBeamCursor)
            super().hoverMoveEvent(event)
            return

        h = self._hit_test_handle(event.pos())
        self.setCursor(self._cursor_for_handle(h))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        if self._mode == self.MODE_NONE:
            self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._sync_height_to_content(force=False)
        super().focusOutEvent(event)
        if self.canvas_view:
            self.canvas_view.notify_modified()

    def mousePressEvent(self, event):
        if self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.setSelected(True)
            self._start_scene_pos = event.scenePos()
            self._start_item_pos = self.pos()
            self._start_w = self._box_w
            self._start_h = self._box_h

            h = self._hit_test_handle(event.pos())
            if h != self.HANDLE_NONE:
                self._mode = self.MODE_RESIZE
                self._resize_handle = h
                self.setCursor(self._cursor_for_handle(h))
                event.accept()
                return

            if self._frame_rect().contains(event.pos()):
                if not self._lock_position:
                    self._mode = self.MODE_MOVE
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._mode == self.MODE_MOVE:
            d = event.scenePos() - self._start_scene_pos
            new_pos = self._start_item_pos + d
            if self.canvas_view and self.canvas_view.snap_enabled:
                new_pos = _snap_point(new_pos, self.canvas_view.grid_size)
            self.setPos(new_pos)
            event.accept()
            return

        if self._mode == self.MODE_RESIZE:
            d = event.scenePos() - self._start_scene_pos
            dx, dy = d.x(), d.y()
            h = self._resize_handle

            new_x = self._start_item_pos.x()
            new_y = self._start_item_pos.y()

            new_w = self._start_w
            if h in (self.HANDLE_RIGHT, self.HANDLE_TOP_RIGHT, self.HANDLE_BOTTOM_RIGHT):
                new_w = self._start_w + dx
            elif h in (self.HANDLE_LEFT, self.HANDLE_TOP_LEFT, self.HANDLE_BOTTOM_LEFT):
                new_w = self._start_w - dx

            new_w = max(self._min_width, new_w)
            if h in (self.HANDLE_LEFT, self.HANDLE_TOP_LEFT, self.HANDLE_BOTTOM_LEFT):
                new_x = self._start_item_pos.x() + (self._start_w - new_w)

            self._set_box_width(new_w)
            self._sync_height_to_content(force=False)

            min_h = max(self._min_height, self._content_rect().height())
            new_h = self._start_h
            if h in (self.HANDLE_BOTTOM, self.HANDLE_BOTTOM_LEFT, self.HANDLE_BOTTOM_RIGHT):
                new_h = self._start_h + dy
            elif h in (self.HANDLE_TOP, self.HANDLE_TOP_LEFT, self.HANDLE_TOP_RIGHT):
                new_h = self._start_h - dy

            new_h = max(min_h, new_h)
            if h in (self.HANDLE_TOP, self.HANDLE_TOP_LEFT, self.HANDLE_TOP_RIGHT):
                new_y = self._start_item_pos.y() + (self._start_h - new_h)

            self._set_box_height(new_h)
            self.setPos(QPointF(new_x, new_y))
            self.update()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._mode in (self.MODE_MOVE, self.MODE_RESIZE):
            self._mode = self.MODE_NONE
            self._resize_handle = self.HANDLE_NONE
            self._sync_height_to_content(force=False)
            self.unsetCursor()
            event.accept()
            if self.canvas_view:
                self.canvas_view.notify_modified()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        gpos = event.screenPos()
        if hasattr(gpos, "toPoint"):
            gpos = gpos.toPoint()

        changed = False

        if self.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction:
            if not self.isSelected():
                sc = self.scene()
                if sc:
                    for it in sc.selectedItems():
                        if it is not self:
                            it.setSelected(False)
                self.setSelected(True)

            targets = self._selected_textboxes()

            menu = QMenu()
            act_edit = menu.addAction("编辑文本")
            menu.addSeparator()
            act_font = menu.addAction("设置字体和大小...")
            act_size = menu.addAction("仅设置字号...")
            act_style = menu.addAction("设置文本框样式...")
            menu.addSeparator()
            act_front = menu.addAction("置于最上层")
            act_back = menu.addAction("置于最下层")
            menu.addSeparator()

            act_lock_pos = menu.addAction("锁定位置")
            act_lock_pos.setCheckable(True)
            act_lock_pos.setChecked(self._lock_position)

            act_lock_size = menu.addAction("锁定大小")
            act_lock_size.setCheckable(True)
            act_lock_size.setChecked(self._lock_size)

            menu.addSeparator()
            act_copy_all = menu.addAction("复制文本内容")
            act_delete_box = menu.addAction("删除文本框")

            chosen = menu.exec(gpos)
            if chosen is None:
                event.accept()
                return

            if chosen == act_edit:
                self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
                self.setFocus(Qt.FocusReason.MouseFocusReason)

            elif chosen == act_font:
                mw = self.canvas_view.window() if self.canvas_view else None
                if mw and hasattr(mw, "set_selected_textbox_font"):
                    mw.set_selected_textbox_font()

            elif chosen == act_size:
                mw = self.canvas_view.window() if self.canvas_view else None
                if mw and hasattr(mw, "set_selected_textbox_font_size"):
                    mw.set_selected_textbox_font_size()

            elif chosen == act_style:
                mw = self.canvas_view.window() if self.canvas_view else None
                if mw and hasattr(mw, "set_selected_textbox_style"):
                    mw.set_selected_textbox_style()

            elif chosen == act_front:
                sc = self.scene()
                if sc:
                    others = [it.zValue() for it in sc.items() if it not in targets]
                    start = (max(others) + 1) if others else 1
                    for i, it in enumerate(sorted(targets, key=lambda x: x.zValue())):
                        it.setZValue(start + i)
                    changed = True

            elif chosen == act_back:
                sc = self.scene()
                if sc:
                    page = self.canvas_view.page_rect_item if self.canvas_view else None
                    others = [
                        it.zValue() for it in sc.items()
                        if (it not in targets) and (it is not page)
                    ]
                    min_other = min(others) if others else 0
                    base = min_other - len(targets)
                    if page is not None:
                        base = max(base, page.zValue() + 1)
                    for i, it in enumerate(sorted(targets, key=lambda x: x.zValue())):
                        it.setZValue(base + i)
                    changed = True

            elif chosen == act_lock_pos:
                state = act_lock_pos.isChecked()
                for it in targets:
                    it.set_position_locked(state)
                changed = True

            elif chosen == act_lock_size:
                state = act_lock_size.isChecked()
                for it in targets:
                    it.set_size_locked(state)
                changed = True

            elif chosen == act_copy_all:
                QApplication.clipboard().setText(self.toPlainText())

            elif chosen == act_delete_box:
                sc = self.scene()
                if sc:
                    for it in targets:
                        sc.removeItem(it)
                changed = True

            event.accept()
            if changed and self.canvas_view:
                self.canvas_view.notify_modified()
            return

        # 编辑状态菜单
        cursor = self.textCursor()
        clip_text = QApplication.clipboard().text()

        menu = QMenu()
        act_undo = menu.addAction("撤销")
        act_redo = menu.addAction("重做")
        menu.addSeparator()
        act_cut = menu.addAction("剪切")
        act_copy = menu.addAction("复制")
        act_paste = menu.addAction("粘贴")
        act_delete = menu.addAction("删除")
        menu.addSeparator()
        act_select_all = menu.addAction("全选")
        menu.addSeparator()
        act_finish = menu.addAction("结束编辑")

        act_undo.setEnabled(self.document().isUndoAvailable())
        act_redo.setEnabled(self.document().isRedoAvailable())
        has_sel = cursor.hasSelection()
        act_cut.setEnabled(has_sel)
        act_copy.setEnabled(has_sel)
        act_delete.setEnabled(has_sel)
        act_paste.setEnabled(bool(clip_text))

        chosen = menu.exec(gpos)
        if chosen is None:
            event.accept()
            return

        if chosen == act_undo:
            self.document().undo()
            changed = True
        elif chosen == act_redo:
            self.document().redo()
            changed = True
        elif chosen == act_cut:
            QApplication.clipboard().setText(cursor.selectedText())
            cursor.removeSelectedText()
            self.setTextCursor(cursor)
            changed = True
        elif chosen == act_copy:
            QApplication.clipboard().setText(cursor.selectedText())
        elif chosen == act_paste:
            cursor.insertText(QApplication.clipboard().text())
            self.setTextCursor(cursor)
            changed = True
        elif chosen == act_delete:
            cursor.removeSelectedText()
            self.setTextCursor(cursor)
            changed = True
        elif chosen == act_select_all:
            c = self.textCursor()
            c.select(QTextCursor.SelectionType.Document)
            self.setTextCursor(c)
        elif chosen == act_finish:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.clearFocus()

        event.accept()
        if changed and self.canvas_view:
            self.canvas_view.notify_modified()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(value, QPointF):
            if self._lock_position and self._mode != self.MODE_RESIZE:
                return self.pos()

            if self.canvas_view and self.canvas_view.snap_enabled:
                if self._mode in (self.MODE_MOVE, self.MODE_RESIZE):
                    return value
                return _snap_point(value, self.canvas_view.grid_size)

        return super().itemChange(change, value)

    def _on_contents_changed(self):
        self._sync_height_to_content(force=False)
        self.update()

    def paint(self, painter, option, widget=None):
        r = self._frame_rect()

        fill = QColor(self._fill_color)
        fill.setAlpha(max(0, min(255, int(self._fill_alpha))))

        if self._border_width > 0:
            painter.setPen(QPen(QColor(self._border_color), float(self._border_width)))
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(fill)
        painter.drawRect(r)

        painter.save()
        painter.setClipRect(r)
        super().paint(painter, option, widget)
        painter.restore()

        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

            if self.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction and not self._lock_size:
                painter.setPen(QPen(QColor(0, 120, 215), 1))
                painter.setBrush(QColor(255, 255, 255))
                for rr in self._handle_rects().values():
                    painter.drawRect(rr)


class CanvasView(QGraphicsView):
    sceneModified = Signal()
    filesDropped = Signal(list)

    _SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

    def __init__(self, parent=None):
        super().__init__(parent)

        scene = QGraphicsScene(self)
        self.setScene(scene)

        self.page_width_px = 2480
        self.page_height_px = 3508
        self.page_rect_item: QGraphicsRectItem | None = None

        self.grid_size = 20
        self.snap_enabled = True
        self.show_grid = True

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setBackgroundBrush(QColor("#666666"))
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setAcceptDrops(True)

        self.set_canvas_size_px(self.page_width_px, self.page_height_px)

    def notify_modified(self):
        self.sceneModified.emit()

    def set_canvas_size_px(self, width_px: int, height_px: int) -> None:
        self.page_width_px = max(1, int(width_px))
        self.page_height_px = max(1, int(height_px))

        if self.page_rect_item:
            self.scene().removeItem(self.page_rect_item)

        self.page_rect_item = QGraphicsRectItem(0, 0, self.page_width_px, self.page_height_px)
        self.page_rect_item.setPen(QPen(QColor("#BEBEBE"), 1))
        self.page_rect_item.setBrush(QColor("white"))
        self.page_rect_item.setZValue(-1000)
        self.scene().addItem(self.page_rect_item)

        margin = 200
        self.scene().setSceneRect(
            -margin, -margin, self.page_width_px + 2 * margin, self.page_height_px + 2 * margin
        )

    def fit_page(self):
        if self.page_rect_item:
            self.fitInView(self.page_rect_item.rect(), Qt.AspectRatioMode.KeepAspectRatio)

    def page_size_px(self) -> Tuple[int, int]:
        return self.page_width_px, self.page_height_px

    def image_items(self) -> List[ImageFrameItem]:
        items = [it for it in self.scene().items() if isinstance(it, ImageFrameItem)]
        return sorted(items, key=lambda i: (i.sceneBoundingRect().top(), i.sceneBoundingRect().left()))

    def selected_image_items(self) -> List[ImageFrameItem]:
        items = [it for it in self.scene().selectedItems() if isinstance(it, ImageFrameItem)]
        return sorted(items, key=lambda i: (i.sceneBoundingRect().top(), i.sceneBoundingRect().left()))

    def remove_all_images(self):
        for item in self.image_items():
            self.scene().removeItem(item)

    def remove_all_user_items(self):
        for item in list(self.scene().items()):
            if item is self.page_rect_item:
                continue
            self.scene().removeItem(item)

    def select_all_items(self) -> int:
        count = 0
        for item in self.scene().items():
            if item is self.page_rect_item:
                continue
            if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable:
                item.setSelected(True)
                count += 1
        return count

    def delete_selected_items(self) -> int:
        deleted = 0
        for item in list(self.scene().selectedItems()):
            if item is self.page_rect_item:
                continue
            self.scene().removeItem(item)
            deleted += 1
        if deleted > 0:
            self.notify_modified()
        return deleted

    def _is_text_editing_active(self) -> bool:
        focus_item = self.scene().focusItem()
        return (
            isinstance(focus_item, TextBoxItem)
            and focus_item.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
        )

    @classmethod
    def _is_supported_image_path(cls, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in cls._SUPPORTED_EXTS

    @classmethod
    def _extract_supported_paths(cls, mime_data) -> list[str]:
        if mime_data is None or not mime_data.hasUrls():
            return []

        out: list[str] = []
        seen: set[str] = set()
        for u in mime_data.urls():
            if not u.isLocalFile():
                continue
            p = u.toLocalFile().strip()
            if not p or p in seen:
                continue
            if not os.path.isfile(p):
                continue
            if not cls._is_supported_image_path(p):
                continue
            seen.add(p)
            out.append(p)
        return out

    def dragEnterEvent(self, event):
        paths = self._extract_supported_paths(event.mimeData())
        if paths:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        paths = self._extract_supported_paths(event.mimeData())
        if paths:
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        paths = self._extract_supported_paths(event.mimeData())
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        super().drawForeground(painter, rect)
        if not self.show_grid:
            return

        page_rect = QRectF(0, 0, self.page_width_px, self.page_height_px)
        vis = rect.intersected(page_rect)
        if vis.isEmpty():
            return

        g = max(2, self.grid_size)
        painter.setPen(QPen(QColor(235, 235, 235), 0))

        start_x = int(vis.left() // g) * g
        end_x = int(vis.right()) + g
        start_y = int(vis.top() // g) * g
        end_y = int(vis.bottom()) + g

        x = start_x
        while x <= end_x:
            painter.drawLine(x, vis.top(), x, vis.bottom())
            x += g

        y = start_y
        while y <= end_y:
            painter.drawLine(vis.left(), y, vis.right(), y)
            y += g

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseReleaseEvent(self, event):
        # 仅由具体编辑动作触发 notify_modified，避免纯点击/框选释放导致无效历史快照。
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._is_text_editing_active():
            super().keyPressEvent(event)
            return

        if event.matches(QKeySequence.StandardKey.SelectAll):
            self.select_all_items()
            event.accept()
            return

        mw = self.window()
        if event.matches(QKeySequence.StandardKey.Copy):
            if mw and hasattr(mw, "copy_selected_items"):
                mw.copy_selected_items()
                event.accept()
                return
        if event.matches(QKeySequence.StandardKey.Cut):
            if mw and hasattr(mw, "cut_selected_items"):
                mw.cut_selected_items()
                event.accept()
                return
        if event.matches(QKeySequence.StandardKey.Paste):
            if mw and hasattr(mw, "paste_items"):
                mw.paste_items()
                event.accept()
                return

        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_items()
            event.accept()
            return

        super().keyPressEvent(event)