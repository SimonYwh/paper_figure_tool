from __future__ import annotations

import json
import os

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


from app.canvas_view import CanvasView, ImageFrameItem, LabelItem, TextBoxItem
from app.icons import make_icon
from app.preset_manager import (
    add_canvas_preset,
    add_layout_preset,
    add_numbering_preset,
    delete_canvas_preset,
    delete_layout_preset,
    delete_numbering_preset,
    load_canvas_presets,
    load_layout_presets,
    load_numbering_presets,
)
from app.theme import (
    ACCENT,
    ACTION_BUTTON_STYLE,
    BG_APP,
    BG_PRIMARY,
    BORDER_SUBTLE,
    BRAND_BADGE_STYLE,
    BRAND_TITLE_STYLE,
    CARD_ACTIVE_STYLE,
    CARD_DEFAULT_STYLE,
    DANGER_BUTTON_STYLE,
    HINT_STYLE,
    HISTORY_BUTTON_STYLE,
    HISTORY_LIST_STYLE,
    INFO_CARD_STYLE,
    INFO_STYLE,
    LABEL_STYLE,
    PRIMARY_BUTTON_STYLE,
    RIGHT_PANEL_STYLE,
    SECTION_TITLE_STYLE,
    STEP_BADGE_ACTIVE_STYLE,
    STEP_BADGE_DEFAULT_STYLE,
    STEP_DESC_STYLE,
    STEP_TITLE_STYLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WORKFLOW_PANEL_STYLE,
)
from core.exporter import export_canvas_to_image, export_canvas_to_pdf, export_canvas_to_svg
from core.history_manager import HistoryManager
from core.image_loader import ImageLoader
from core.image_utils import load_image_thumb_qpixmap
from core.layout_engine import apply_grid_layout
from core.models import CanvasSettings
from core.project_io import apply_project_dict, build_project_dict, load_project_file, save_project_file


def _localize_dialog_buttons(btn_box: QDialogButtonBox):
    mappings = [
        (QDialogButtonBox.StandardButton.Ok, "确定"),
        (QDialogButtonBox.StandardButton.Cancel, "取消"),
        (QDialogButtonBox.StandardButton.Save, "保存"),
        (QDialogButtonBox.StandardButton.Discard, "不保存"),
        (QDialogButtonBox.StandardButton.Yes, "是"),
        (QDialogButtonBox.StandardButton.No, "否"),
    ]
    for std_btn, text in mappings:
        btn = btn_box.button(std_btn)
        if btn:
            btn.setText(text)


class CanvasSettingsDialog(QDialog):
    BUILTIN_PRESETS = {
        "A3 竖版 (297×420mm)": (297.0, 420.0),
        "A3 横版 (420×297mm)": (420.0, 297.0),
        "A4 竖版 (210×297mm)": (210.0, 297.0),
        "A4 横版 (297×210mm)": (297.0, 210.0),
        "A5 竖版 (148×210mm)": (148.0, 210.0),
        "A5 横版 (210×148mm)": (210.0, 148.0),
    }

    UNIT_OPTIONS = [
        ("毫米 (mm)", "mm"),
        ("厘米 (cm)", "cm"),
        ("英寸 (in)", "in"),
        ("像素 (px)", "px"),
    ]

    def __init__(self, current: CanvasSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("画布设置")

        self._updating = False
        self._width_mm = float(current.width_mm)
        self._height_mm = float(current.height_mm)

        # 加载用户预设
        self._user_presets = load_canvas_presets()

        self.preset_combo = QComboBox()
        self._refresh_preset_list()

        self.unit_combo = QComboBox()
        for label, code in self.UNIT_OPTIONS:
            self.unit_combo.addItem(label, code)

        self.w_spin = QDoubleSpinBox()
        self.h_spin = QDoubleSpinBox()

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(current.dpi)

        # 预设管理按钮
        self.btn_save_preset = QPushButton("保存为预设")
        self.btn_save_preset.setFixedWidth(100)
        self.btn_delete_preset = QPushButton("删除预设")
        self.btn_delete_preset.setFixedWidth(100)

        preset_btn_layout = QHBoxLayout()
        preset_btn_layout.addWidget(self.preset_combo)
        preset_btn_layout.addWidget(self.btn_save_preset)
        preset_btn_layout.addWidget(self.btn_delete_preset)

        layout = QFormLayout(self)
        layout.addRow("页面预设", preset_btn_layout)
        layout.addRow("单位", self.unit_combo)
        layout.addRow("宽度", self.w_spin)
        layout.addRow("高度", self.h_spin)
        layout.addRow("DPI", self.dpi_spin)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _localize_dialog_buttons(btn_box)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        self.dpi_spin.valueChanged.connect(self._on_dpi_changed)
        self.w_spin.valueChanged.connect(self._on_size_spin_changed)
        self.h_spin.valueChanged.connect(self._on_size_spin_changed)
        self.btn_save_preset.clicked.connect(self._save_current_as_preset)
        self.btn_delete_preset.clicked.connect(self._delete_selected_preset)

        self.unit_combo.setCurrentIndex(0)
        self._apply_spin_ui_by_unit(self.current_unit())
        self._set_spins_from_mm()
        self.preset_combo.setCurrentText(self._guess_preset(self._width_mm, self._height_mm))

    def _refresh_preset_list(self):
        """刷新预设下拉列表，包含内置和用户预设"""
        self._updating = True
        try:
            current_text = self.preset_combo.currentText() if self.preset_combo.count() > 0 else ""
            self.preset_combo.clear()
            # 内置预设
            for name in self.BUILTIN_PRESETS:
                self.preset_combo.addItem(name)
            # 用户预设
            for p in self._user_presets:
                self.preset_combo.addItem(p["name"])
            # 自定义选项
            self.preset_combo.addItem("自定义")
            # 恢复选中
            idx = self.preset_combo.findText(current_text)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        finally:
            self._updating = False

    def _save_current_as_preset(self):
        """将当前尺寸保存为用户预设"""
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：", QLineEdit.EchoMode.Normal, "")
        if not ok or not name.strip():
            return
        name = name.strip()
        add_canvas_preset(name, self._width_mm, self._height_mm, int(self.dpi_spin.value()))
        self._user_presets = load_canvas_presets()
        self._refresh_preset_list()
        self.preset_combo.setCurrentText(name)

    def _delete_selected_preset(self):
        """删除选中的用户预设"""
        name = self.preset_combo.currentText()
        if name in self.BUILTIN_PRESETS or name == "自定义":
            QMessageBox.information(self, "提示", "内置预设不可删除。")
            return
        # 检查是否为用户预设
        is_user = any(p["name"] == name for p in self._user_presets)
        if not is_user:
            return
        delete_canvas_preset(name)
        self._user_presets = load_canvas_presets()
        self._refresh_preset_list()

    @staticmethod
    def _to_mm(v: float, unit: str, dpi: int) -> float:
        if unit == "cm":
            return float(v) * 10.0
        if unit == "in":
            return float(v) * 25.4
        if unit == "px":
            return float(v) / max(1, int(dpi)) * 25.4
        return float(v)

    @staticmethod
    def _from_mm(mm: float, unit: str, dpi: int) -> float:
        if unit == "cm":
            return float(mm) / 10.0
        if unit == "in":
            return float(mm) / 25.4
        if unit == "px":
            return float(mm) / 25.4 * max(1, int(dpi))
        return float(mm)

    def current_unit(self) -> str:
        return str(self.unit_combo.currentData() or "mm")

    def _apply_spin_ui_by_unit(self, unit: str):
        if unit == "px":
            self.w_spin.setDecimals(0)
            self.h_spin.setDecimals(0)
            self.w_spin.setSingleStep(10)
            self.h_spin.setSingleStep(10)
            self.w_spin.setRange(32.0, 40000.0)
            self.h_spin.setRange(32.0, 40000.0)
            self.w_spin.setSuffix(" px")
            self.h_spin.setSuffix(" px")
        elif unit == "cm":
            self.w_spin.setDecimals(2)
            self.h_spin.setDecimals(2)
            self.w_spin.setSingleStep(0.1)
            self.h_spin.setSingleStep(0.1)
            self.w_spin.setRange(1.0, 500.0)
            self.h_spin.setRange(1.0, 500.0)
            self.w_spin.setSuffix(" cm")
            self.h_spin.setSuffix(" cm")
        elif unit == "in":
            self.w_spin.setDecimals(3)
            self.h_spin.setDecimals(3)
            self.w_spin.setSingleStep(0.1)
            self.h_spin.setSingleStep(0.1)
            self.w_spin.setRange(0.5, 200.0)
            self.h_spin.setRange(0.5, 200.0)
            self.w_spin.setSuffix(" in")
            self.h_spin.setSuffix(" in")
        else:
            self.w_spin.setDecimals(1)
            self.h_spin.setDecimals(1)
            self.w_spin.setSingleStep(1.0)
            self.h_spin.setSingleStep(1.0)
            self.w_spin.setRange(10.0, 5000.0)
            self.h_spin.setRange(10.0, 5000.0)
            self.w_spin.setSuffix(" mm")
            self.h_spin.setSuffix(" mm")

    def _set_spins_from_mm(self):
        unit = self.current_unit()
        dpi = int(self.dpi_spin.value())
        self._updating = True
        try:
            self.w_spin.setValue(self._from_mm(self._width_mm, unit, dpi))
            self.h_spin.setValue(self._from_mm(self._height_mm, unit, dpi))
        finally:
            self._updating = False

    def _guess_preset(self, w: float, h: float) -> str:
        # 检查内置预设
        for name, val in self.BUILTIN_PRESETS.items():
            pw, ph = val
            if abs(w - pw) < 0.5 and abs(h - ph) < 0.5:
                return name
        # 检查用户预设
        for p in self._user_presets:
            pw, ph = float(p.get("width_mm", 0)), float(p.get("height_mm", 0))
            if abs(w - pw) < 0.5 and abs(h - ph) < 0.5:
                return p["name"]
        return "自定义"

    def _sync_preset(self):
        guessed = self._guess_preset(self._width_mm, self._height_mm)
        if self.preset_combo.currentText() != guessed:
            self._updating = True
            try:
                self.preset_combo.setCurrentText(guessed)
            finally:
                self._updating = False

    def _on_preset_changed(self, text: str):
        if self._updating:
            return
        # 内置预设
        val = self.BUILTIN_PRESETS.get(text)
        if val is not None:
            self._width_mm, self._height_mm = float(val[0]), float(val[1])
            self._set_spins_from_mm()
            return
        # 用户预设
        for p in self._user_presets:
            if p.get("name") == text:
                self._width_mm = float(p.get("width_mm", 210.0))
                self._height_mm = float(p.get("height_mm", 297.0))
                self.dpi_spin.setValue(int(p.get("dpi", 300)))
                self._set_spins_from_mm()
                return

    def _on_unit_changed(self, _idx: int):
        unit = self.current_unit()
        self._apply_spin_ui_by_unit(unit)
        self._set_spins_from_mm()

    def _on_dpi_changed(self, _value: int):
        if self.current_unit() == "px":
            self._set_spins_from_mm()

    def _on_size_spin_changed(self, _value: float):
        if self._updating:
            return
        unit = self.current_unit()
        dpi = int(self.dpi_spin.value())
        self._width_mm = self._to_mm(float(self.w_spin.value()), unit, dpi)
        self._height_mm = self._to_mm(float(self.h_spin.value()), unit, dpi)
        self._sync_preset()

    def get_settings(self) -> CanvasSettings:
        return CanvasSettings(
            width_mm=float(self._width_mm),
            height_mm=float(self._height_mm),
            dpi=int(self.dpi_spin.value()),
        )


class NumberingDialog(QDialog):
    previewChanged = Signal(dict)
    STYLE_OPTIONS = [
        "a, b, c",
        "a), b), c)",
        "(a), (b), (c)",
        "A, B, C",
        "i, ii, iii",
        "(i), (ii), (iii)",
    ]
    CORNER_OPTIONS = ["左上", "右上", "左下", "右下"]

    def __init__(self, current_cfg: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("一键编号设置")

        # 加载用户预设
        self._user_presets = load_numbering_presets()

        # 预设选择
        self.preset_combo = QComboBox()
        self._refresh_preset_list()

        self.style_combo = QComboBox()
        self.style_combo.addItems(self.STYLE_OPTIONS)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Times New Roman", 20))

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 200)
        self.size_spin.setValue(20)

        self.corner_combo = QComboBox()
        self.corner_combo.addItems(self.CORNER_OPTIONS)

        self.offset_x = QSpinBox()
        self.offset_x.setRange(-2000, 2000)
        self.offset_x.setValue(8)

        self.offset_y = QSpinBox()
        self.offset_y.setRange(-2000, 2000)
        self.offset_y.setValue(8)

        self.black_bg = QCheckBox("黑底白字")
        self.black_bg.setChecked(False)

        # 预设管理按钮
        self.btn_save_preset = QPushButton("保存为预设")
        self.btn_save_preset.setFixedWidth(100)
        self.btn_delete_preset = QPushButton("删除预设")
        self.btn_delete_preset.setFixedWidth(100)

        preset_btn_layout = QHBoxLayout()
        preset_btn_layout.addWidget(self.preset_combo)
        preset_btn_layout.addWidget(self.btn_save_preset)
        preset_btn_layout.addWidget(self.btn_delete_preset)

        layout = QFormLayout(self)
        layout.addRow("预设", preset_btn_layout)
        layout.addRow("样式", self.style_combo)
        layout.addRow("字体", self.font_combo)
        layout.addRow("字号", self.size_spin)
        layout.addRow("位置", self.corner_combo)
        layout.addRow("偏移 X(px)", self.offset_x)
        layout.addRow("偏移 Y(px)", self.offset_y)
        layout.addRow("", self.black_bg)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _localize_dialog_buttons(btn_box)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

        self.style_combo.currentTextChanged.connect(self._emit_preview)
        self.font_combo.currentFontChanged.connect(self._emit_preview)
        self.size_spin.valueChanged.connect(self._emit_preview)
        self.corner_combo.currentTextChanged.connect(self._emit_preview)
        self.offset_x.valueChanged.connect(self._emit_preview)
        self.offset_y.valueChanged.connect(self._emit_preview)
        self.black_bg.toggled.connect(self._emit_preview)
        self.btn_save_preset.clicked.connect(self._save_current_as_preset)
        self.btn_delete_preset.clicked.connect(self._delete_selected_preset)
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)

        if current_cfg:
            if current_cfg.get("style") in self.STYLE_OPTIONS:
                self.style_combo.setCurrentText(current_cfg.get("style"))
            if current_cfg.get("corner") in self.CORNER_OPTIONS:
                self.corner_combo.setCurrentText(current_cfg.get("corner"))
            self.size_spin.setValue(int(current_cfg.get("font_size", 20)))
            self.offset_x.setValue(int(current_cfg.get("offset_x", 8)))
            self.offset_y.setValue(int(current_cfg.get("offset_y", 8)))
            self.black_bg.setChecked(bool(current_cfg.get("black_bg", False)))
            fam = current_cfg.get("font_family")
            if fam:
                self.font_combo.setCurrentFont(QFont(fam))

        QTimer.singleShot(0, self._emit_preview)

    def _refresh_preset_list(self):
        """刷新预设下拉列表"""
        self._preset_updating = True
        try:
            current_text = self.preset_combo.currentText() if self.preset_combo.count() > 0 else ""
            self.preset_combo.clear()
            self.preset_combo.addItem("（无预设）")
            for p in self._user_presets:
                self.preset_combo.addItem(p["name"])
            idx = self.preset_combo.findText(current_text)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        finally:
            self._preset_updating = False

    def _on_preset_selected(self, text: str):
        """应用选中的预设"""
        if getattr(self, "_preset_updating", False):
            return
        for p in self._user_presets:
            if p.get("name") == text:
                if p.get("style") in self.STYLE_OPTIONS:
                    self.style_combo.setCurrentText(p["style"])
                if p.get("corner") in self.CORNER_OPTIONS:
                    self.corner_combo.setCurrentText(p["corner"])
                self.size_spin.setValue(int(p.get("font_size", 20)))
                self.offset_x.setValue(int(p.get("offset_x", 8)))
                self.offset_y.setValue(int(p.get("offset_y", 8)))
                self.black_bg.setChecked(bool(p.get("black_bg", False)))
                fam = p.get("font_family")
                if fam:
                    self.font_combo.setCurrentFont(QFont(fam))
                return

    def _save_current_as_preset(self):
        """将当前设置保存为用户预设"""
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：", QLineEdit.EchoMode.Normal, "")
        if not ok or not name.strip():
            return
        name = name.strip()
        add_numbering_preset(name, self.get_data())
        self._user_presets = load_numbering_presets()
        self._refresh_preset_list()
        self.preset_combo.setCurrentText(name)

    def _delete_selected_preset(self):
        """删除选中的用户预设"""
        name = self.preset_combo.currentText()
        if name == "（无预设）":
            return
        is_user = any(p["name"] == name for p in self._user_presets)
        if not is_user:
            return
        delete_numbering_preset(name)
        self._user_presets = load_numbering_presets()
        self._refresh_preset_list()

    def _emit_preview(self, *_):
        self.previewChanged.emit(self.get_data())

    def get_data(self) -> dict:
        return {
            "style": self.style_combo.currentText(),
            "font_family": self.font_combo.currentFont().family(),
            "font_size": int(self.size_spin.value()),
            "corner": self.corner_combo.currentText(),
            "offset_x": int(self.offset_x.value()),
            "offset_y": int(self.offset_y.value()),
            "black_bg": bool(self.black_bg.isChecked()),
        }


class CustomLayoutDialog(QDialog):
    """一步式自定义排版对话框：同时输入行数和列数，支持保存/加载预设"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义排版")

        # 加载用户预设
        self._user_presets = load_layout_presets()

        # 预设选择
        self.preset_combo = QComboBox()
        self._refresh_preset_list()

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 30)
        self.rows_spin.setValue(2)

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 30)
        self.cols_spin.setValue(2)

        # 预设管理按钮
        self.btn_save_preset = QPushButton("保存为预设")
        self.btn_save_preset.setFixedWidth(100)
        self.btn_delete_preset = QPushButton("删除预设")
        self.btn_delete_preset.setFixedWidth(100)

        preset_btn_layout = QHBoxLayout()
        preset_btn_layout.addWidget(self.preset_combo)
        preset_btn_layout.addWidget(self.btn_save_preset)
        preset_btn_layout.addWidget(self.btn_delete_preset)

        layout = QFormLayout(self)
        layout.addRow("预设", preset_btn_layout)
        layout.addRow("行数", self.rows_spin)
        layout.addRow("列数", self.cols_spin)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _localize_dialog_buttons(btn_box)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

        self.btn_save_preset.clicked.connect(self._save_current_as_preset)
        self.btn_delete_preset.clicked.connect(self._delete_selected_preset)
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)

    def _refresh_preset_list(self):
        self._preset_updating = True
        try:
            current_text = self.preset_combo.currentText() if self.preset_combo.count() > 0 else ""
            self.preset_combo.clear()
            self.preset_combo.addItem("（无预设）")
            for p in self._user_presets:
                self.preset_combo.addItem(p["name"])
            idx = self.preset_combo.findText(current_text)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        finally:
            self._preset_updating = False

    def _on_preset_selected(self, text: str):
        if getattr(self, "_preset_updating", False):
            return
        for p in self._user_presets:
            if p.get("name") == text:
                self.rows_spin.setValue(int(p.get("rows", 2)))
                self.cols_spin.setValue(int(p.get("cols", 2)))
                return

    def _save_current_as_preset(self):
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：", QLineEdit.EchoMode.Normal, "")
        if not ok or not name.strip():
            return
        name = name.strip()
        add_layout_preset(name, self.rows_spin.value(), self.cols_spin.value())
        self._user_presets = load_layout_presets()
        self._refresh_preset_list()
        self.preset_combo.setCurrentText(name)

    def _delete_selected_preset(self):
        name = self.preset_combo.currentText()
        if name == "（无预设）":
            return
        is_user = any(p["name"] == name for p in self._user_presets)
        if not is_user:
            return
        delete_layout_preset(name)
        self._user_presets = load_layout_presets()
        self._refresh_preset_list()

    def get_rows(self) -> int:
        return self.rows_spin.value()

    def get_cols(self) -> int:
        return self.cols_spin.value()


class LabelStyleDialog(QDialog):
    def __init__(self, label_item: LabelItem, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑编号样式")
        self.label_item = label_item

        self.text_edit = QLineEdit(label_item.text)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(label_item.font_obj)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 200)
        self.size_spin.setValue(max(6, label_item.font_obj.pointSize()))

        self.black_bg = QCheckBox("黑底白字")
        self.black_bg.setChecked(bool(label_item.bg_enabled))

        layout = QFormLayout(self)
        layout.addRow("文本", self.text_edit)
        layout.addRow("字体", self.font_combo)
        layout.addRow("字号", self.size_spin)
        layout.addRow("", self.black_bg)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _localize_dialog_buttons(btn_box)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def get_data(self) -> dict:
        t = self.text_edit.text().strip()
        if not t:
            t = self.label_item.text
        return {
            "text": t,
            "font_family": self.font_combo.currentFont().family(),
            "font_size": int(self.size_spin.value()),
            "black_bg": bool(self.black_bg.isChecked()),
        }


class TextBoxFontDialogCN(QDialog):
    def __init__(self, base_font: QFont, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置文本框字体和大小")

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(base_font)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 300)
        size = base_font.pointSize()
        if size <= 0:
            size = 14
        self.size_spin.setValue(size)

        layout = QFormLayout(self)
        layout.addRow("字体：", self.font_combo)
        layout.addRow("字号：", self.size_spin)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _localize_dialog_buttons(btn_box)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def selected_font(self) -> QFont:
        f = QFont(self.font_combo.currentFont())
        f.setPointSize(int(self.size_spin.value()))
        return f


class TextBoxStyleDialog(QDialog):
    def __init__(self, sample: TextBoxItem, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置文本框样式")

        self._text_color = QColor(getattr(sample, "_text_color", sample.defaultTextColor()))
        self._fill_color = QColor(getattr(sample, "_fill_color", QColor(255, 255, 255)))
        self._fill_alpha = int(getattr(sample, "_fill_alpha", 70))
        self._border_color = QColor(getattr(sample, "_border_color", QColor(170, 170, 170)))
        self._border_width = int(getattr(sample, "_border_width", 1))

        self.btn_text_color = QPushButton("选择...")
        self.btn_fill_color = QPushButton("选择...")
        self.btn_border_color = QPushButton("选择...")

        self.spin_fill_alpha = QSpinBox()
        self.spin_fill_alpha.setRange(0, 255)
        self.spin_fill_alpha.setValue(self._fill_alpha)

        self.spin_border_width = QSpinBox()
        self.spin_border_width.setRange(0, 20)
        self.spin_border_width.setValue(self._border_width)

        self.btn_text_color.clicked.connect(self._pick_text_color)
        self.btn_fill_color.clicked.connect(self._pick_fill_color)
        self.btn_border_color.clicked.connect(self._pick_border_color)

        self._refresh_color_buttons()

        layout = QFormLayout(self)
        layout.addRow("文字颜色：", self.btn_text_color)
        layout.addRow("填充颜色：", self.btn_fill_color)
        layout.addRow("填充透明度：", self.spin_fill_alpha)
        layout.addRow("边框颜色：", self.btn_border_color)
        layout.addRow("边框宽度：", self.spin_border_width)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _localize_dialog_buttons(btn_box)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    @staticmethod
    def _btn_style(c: QColor) -> str:
        return (
            "text-align:left; padding-left:6px;"
            f"background-color: rgba({c.red()},{c.green()},{c.blue()},{c.alpha()});"
        )

    def _refresh_color_buttons(self):
        self.btn_text_color.setStyleSheet(self._btn_style(self._text_color))
        self.btn_fill_color.setStyleSheet(self._btn_style(self._fill_color))
        self.btn_border_color.setStyleSheet(self._btn_style(self._border_color))

    def _pick_text_color(self):
        c = QColorDialog.getColor(self._text_color, self, "选择文字颜色")
        if c.isValid():
            self._text_color = c
            self._refresh_color_buttons()

    def _pick_fill_color(self):
        c = QColorDialog.getColor(self._fill_color, self, "选择填充颜色")
        if c.isValid():
            self._fill_color = c
            self._refresh_color_buttons()

    def _pick_border_color(self):
        c = QColorDialog.getColor(self._border_color, self, "选择边框颜色")
        if c.isValid():
            self._border_color = c
            self._refresh_color_buttons()

    def get_data(self) -> dict:
        return {
            "text_color": QColor(self._text_color),
            "fill_color": QColor(self._fill_color),
            "fill_alpha": int(self.spin_fill_alpha.value()),
            "border_color": QColor(self._border_color),
            "border_width": int(self.spin_border_width.value()),
        }


class HoverCard(QFrame):
    """带柔和阴影 + hover 动效的步骤卡片。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("step_card")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(10.0)
        self._shadow.setOffset(0, 1)
        self._shadow.setColor(QColor(15, 23, 42, 18))  # rgba(...,0.07)
        self.setGraphicsEffect(self._shadow)

        self._anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._offset_anim = QPropertyAnimation(self._shadow, b"yOffset", self)
        self._offset_anim.setDuration(180)
        self._offset_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate_to(self, blur: float, offset: float, alpha: int):
        self._anim.stop()
        self._anim.setStartValue(self._shadow.blurRadius())
        self._anim.setEndValue(blur)
        self._anim.start()
        self._offset_anim.stop()
        self._offset_anim.setStartValue(self._shadow.yOffset())
        self._offset_anim.setEndValue(offset)
        self._offset_anim.start()
        col = self._shadow.color()
        col.setAlpha(alpha)
        self._shadow.setColor(col)

    def enterEvent(self, event):
        self._animate_to(22.0, 6.0, 36)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(10.0, 1.0, 18)
        super().leaveEvent(event)


class TextOnlyAction(QAction):
    """无图标版本（用于无需图标的内部动作）。"""
    pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.canvas_settings = CanvasSettings()
        self.default_fill_mode = "fit"
        self.last_numbering_cfg = {
            "style": "(a), (b), (c)",
            "font_family": "Times New Roman",
            "font_size": 20,
            "corner": "左上",
            "offset_x": 8,
            "offset_y": 8,
            "black_bg": False,
        }

        self.current_project_path = ""
        self._is_importing = False
        self._active_import_batches: set[int] = set()
        self._import_batch_done: dict[int, int] = {}
        self._import_batch_total: dict[int, int] = {}
        self._history_block = False
        self._history = HistoryManager(max_steps=120)
        self._last_saved_state_json = ""

        # 图片缩略图缓存（撤销/重做加速）
        self._image_thumb_cache: dict[str, tuple[QPixmap, tuple[int, int]]] = {}

        # 复制/粘贴缓存
        self._clipboard_payload: dict | None = None
        self._paste_serial = 0

        # 属性侧栏状态
        self._property_syncing = False
        self._asset_ref_map: dict[int, ImageFrameItem] = {}

        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(280)
        self._history_timer.timeout.connect(self._commit_history_snapshot)

        self.setWindowTitle("论文组图排版器 (v1.1.1)")
        self.resize(1320, 820)
        self.setMinimumSize(1180, 720)

        # ---- 创建画布 ----
        self.canvas_view = CanvasView(self)
        self.canvas_view.set_canvas_size_px(self.canvas_settings.width_px, self.canvas_settings.height_px)
        self.canvas_view.sceneModified.connect(self._schedule_history_commit)

        # ---- 创建加载器 ----
        self.loader = ImageLoader(max_thumb=2200, parent=self)
        self._bind_loader_signals()

        # ---- 创建动作 ----
        self._create_actions()

        # 不使用顶部菜单栏
        self.menuBar().hide()

        # ---- 构建三栏布局骨架 ----
        self._build_three_panel_layout()

        # ---- 连接信号 ----
        self.canvas_view.filesDropped.connect(self.import_images)
        self.canvas_view.scene().selectionChanged.connect(self._on_scene_selection_changed)
        self.canvas_view.sceneModified.connect(self._on_scene_modified)

        self._refresh_window_title()
        self._refresh_properties_panel()
        self._refresh_history_panel()

        self.statusBar().showMessage("就绪")
        QTimer.singleShot(0, self._init_after_show)

    def _init_after_show(self):
        self.canvas_view.fit_page()
        self._reset_history()

    # ----------------- 历史 / 快照 -----------------
    def _cache_thumb_from_import(self, path: str, pixmap: QPixmap, orig_w: int, orig_h: int):
        key = os.path.normcase(os.path.abspath(path))
        self._image_thumb_cache[key] = (QPixmap(pixmap), (int(orig_w), int(orig_h)))

    def _state_json(self) -> str:
        data = build_project_dict(self.canvas_settings, self.canvas_view)
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    def _apply_project_data(
        self,
        data: dict,
        *,
        base_dir: str | None = None,
        show_missing: bool = True,
        fit_view: bool = True,
    ):
        c = data.get("canvas", {}) if isinstance(data, dict) else {}
        self.canvas_settings = CanvasSettings(
            width_mm=float(c.get("width_mm", 210.0)),
            height_mm=float(c.get("height_mm", 297.0)),
            dpi=int(c.get("dpi", 300)),
        )
        self.canvas_view.set_canvas_size_px(self.canvas_settings.width_px, self.canvas_settings.height_px)

        self.canvas_view.setUpdatesEnabled(False)
        try:
            missing = apply_project_dict(
                data,
                self.canvas_view,
                default_fill_mode=self.default_fill_mode,
                base_dir=base_dir,
                image_cache=self._image_thumb_cache,
            )
        finally:
            self.canvas_view.setUpdatesEnabled(True)
            self.canvas_view.viewport().update()

        if fit_view:
            QTimer.singleShot(0, self.canvas_view.fit_page)

        if show_missing and missing:
            sample = "\n".join(missing[:8])
            more = f"\n... 还有 {len(missing)-8} 个" if len(missing) > 8 else ""
            QMessageBox.warning(
                self,
                "部分图片缺失",
                f"以下图片未找到，已跳过：\n{sample}{more}",
            )

        self._refresh_properties_panel()

    def _load_state_json(self, state_json: str):
        data = json.loads(state_json)
        self._history_block = True
        try:
            self._apply_project_data(data, base_dir=None, show_missing=False, fit_view=False)
        finally:
            self._history_block = False

    def _reset_history(self):
        state = self._state_json()
        self._history.reset(state)
        self._last_saved_state_json = state
        self._update_undo_redo_enabled()

    def _schedule_history_commit(self):
        if self._history_block or self._is_importing:
            return
        self._history_timer.start()

    def _commit_history_snapshot(self):
        if self._history_block or self._is_importing:
            return
        self._history.push(self._state_json())
        self._update_undo_redo_enabled()
        self._refresh_history_panel()

    def _update_undo_redo_enabled(self):
        self.act_undo.setEnabled(self._history.can_undo())
        self.act_redo.setEnabled(self._history.can_redo())

    def undo(self):
        self._history_timer.stop()
        state = self._history.undo()
        if state is None:
            return
        self._load_state_json(state)
        self._update_undo_redo_enabled()
        self._refresh_history_panel()
        self.statusBar().showMessage("已撤销。", 1000)

    def redo(self):
        self._history_timer.stop()
        state = self._history.redo()
        if state is None:
            return
        self._load_state_json(state)
        self._update_undo_redo_enabled()
        self._refresh_history_panel()
        self.statusBar().showMessage("已重做。", 1000)

    # ----------------- 项目 -----------------
    def _refresh_window_title(self):
        name = os.path.basename(self.current_project_path) if self.current_project_path else "未命名.figproj"
        self.setWindowTitle(f"论文组图排版器 (v1.1.1) - {name}")

    def _has_unsaved_changes(self) -> bool:
        try:
            return self._state_json() != self._last_saved_state_json
        except Exception:
            return True

    def _confirm_continue_if_unsaved(self) -> bool:
        if not self._has_unsaved_changes():
            return True

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("未保存更改")
        msg.setText("当前项目有未保存内容，是否先保存？")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Save)

        save_btn = msg.button(QMessageBox.StandardButton.Save)
        discard_btn = msg.button(QMessageBox.StandardButton.Discard)
        cancel_btn = msg.button(QMessageBox.StandardButton.Cancel)
        if save_btn:
            save_btn.setText("保存")
        if discard_btn:
            discard_btn.setText("不保存")
        if cancel_btn:
            cancel_btn.setText("取消")

        ret = QMessageBox.StandardButton(msg.exec())
        if ret == QMessageBox.StandardButton.Save:
            return self.save_project()
        if ret == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _cancel_active_imports(self):
        self._active_import_batches.clear()
        self._import_batch_done.clear()
        self._import_batch_total.clear()
        self._is_importing = False

    def new_project(self):
        if not self._confirm_continue_if_unsaved():
            return
        self._cancel_active_imports()
        self._history_block = True
        try:
            self._image_thumb_cache.clear()
            self.canvas_settings = CanvasSettings()
            self.canvas_view.set_canvas_size_px(self.canvas_settings.width_px, self.canvas_settings.height_px)
            self.canvas_view.remove_all_user_items()
            self.current_project_path = ""
            QTimer.singleShot(0, self.canvas_view.fit_page)
        finally:
            self._history_block = False

        self._refresh_window_title()
        self._reset_history()
        self._refresh_properties_panel()
        self.statusBar().showMessage("已新建项目。", 1500)

    def open_project(self):
        if not self._confirm_continue_if_unsaved():
            return

        self._cancel_active_imports()

        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", "项目文件 (*.figproj)")
        if not path:
            return

        try:
            data = load_project_file(path)
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))
            return

        self._history_block = True
        try:
            self._image_thumb_cache.clear()
            self._apply_project_data(data, base_dir=os.path.dirname(path), show_missing=True, fit_view=True)
            self.current_project_path = path
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))
            return
        finally:
            self._history_block = False

        self._refresh_window_title()
        self._reset_history()
        self.statusBar().showMessage("项目已打开。", 1500)

    def save_project(self) -> bool:
        if not self.current_project_path:
            return self.save_project_as()

        try:
            data = build_project_dict(self.canvas_settings, self.canvas_view)
            save_project_file(self.current_project_path, data)
            self._last_saved_state_json = self._state_json()
            self.statusBar().showMessage(f"已保存：{self.current_project_path}", 2000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return False

    def save_project_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "项目另存为", "", "项目文件 (*.figproj)")
        if not path:
            return False
        if not path.lower().endswith(".figproj"):
            path += ".figproj"

        try:
            data = build_project_dict(self.canvas_settings, self.canvas_view)
            save_project_file(path, data)
            self.current_project_path = path
            self._last_saved_state_json = self._state_json()
            self._refresh_window_title()
            self.statusBar().showMessage(f"已保存：{path}", 2000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return False

    # ----------------- UI/Action -----------------
    def _bind_loader_signals(self):
        self.loader.image_loaded.connect(self._on_image_loaded)
        self.loader.image_failed.connect(self._on_image_failed)
        self.loader.progress.connect(self._on_load_progress)
        self.loader.finished.connect(self._on_load_finished)

    def _create_actions(self):
        self.act_new_project = QAction("新建项目", self)
        self.act_new_project.setShortcut("Ctrl+N")
        self.act_new_project.triggered.connect(self.new_project)

        self.act_open_project = QAction("打开项目...", self)
        self.act_open_project.setShortcut("Ctrl+O")
        self.act_open_project.triggered.connect(self.open_project)

        self.act_save_project = QAction("保存项目", self)
        self.act_save_project.setShortcut("Ctrl+S")
        self.act_save_project.triggered.connect(self.save_project)

        self.act_save_project_as = QAction("项目另存为...", self)
        self.act_save_project_as.triggered.connect(self.save_project_as)

        self.act_undo = QAction("撤销", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self.undo)

        self.act_redo = QAction("重做", self)
        self.act_redo.setShortcut("Ctrl+Y")
        self.act_redo.triggered.connect(self.redo)

        self.act_select_all = QAction("全选", self)
        self.act_select_all.setShortcut("Ctrl+A")
        self.act_select_all.triggered.connect(self.select_all_items)

        self.act_delete = QAction("删除", self)
        self.act_delete.setShortcut("Delete")
        self.act_delete.triggered.connect(self.delete_selected_items)

        self.act_copy = QAction("复制", self)
        self.act_copy.setShortcut("Ctrl+C")
        self.act_copy.triggered.connect(self.copy_selected_items)

        self.act_cut = QAction("剪切", self)
        self.act_cut.setShortcut("Ctrl+X")
        self.act_cut.triggered.connect(self.cut_selected_items)

        self.act_paste = QAction("粘贴", self)
        self.act_paste.setShortcut("Ctrl+V")
        self.act_paste.triggered.connect(self.paste_items)

        self.act_import = QAction("导入图片", self)
        self.act_import.triggered.connect(self.import_images)

        self.act_canvas = QAction("画布设置", self)
        self.act_canvas.triggered.connect(self.set_canvas)

        self.act_layout_2x2 = QAction("2×2 排版", self)
        self.act_layout_2x2.triggered.connect(lambda: self.apply_layout(2, 2))

        self.act_layout_2x3 = QAction("2×3 排版", self)
        self.act_layout_2x3.triggered.connect(lambda: self.apply_layout(2, 3))

        self.act_layout_3x2 = QAction("3×2 排版", self)
        self.act_layout_3x2.triggered.connect(lambda: self.apply_layout(3, 2))

        self.act_layout_2x4 = QAction("2×4 排版", self)
        self.act_layout_2x4.triggered.connect(lambda: self.apply_layout(2, 4))

        self.act_layout_4x2 = QAction("4×2 排版", self)
        self.act_layout_4x2.triggered.connect(lambda: self.apply_layout(4, 2))

        self.act_layout_custom = QAction("自定义排版", self)
        self.act_layout_custom.triggered.connect(self.apply_custom_layout)

        self.act_img_rot_l = QAction("图片左转90°", self)
        self.act_img_rot_l.triggered.connect(self.rotate_selected_images_left)

        self.act_img_rot_r = QAction("图片右转90°", self)
        self.act_img_rot_r.triggered.connect(self.rotate_selected_images_right)

        self.act_img_flip_h = QAction("图片水平翻转", self)
        self.act_img_flip_h.triggered.connect(self.flip_selected_images_h)

        self.act_img_flip_v = QAction("图片垂直翻转", self)
        self.act_img_flip_v.triggered.connect(self.flip_selected_images_v)

        self.act_img_reset = QAction("重置图片变换", self)
        self.act_img_reset.triggered.connect(self.reset_selected_image_transform)

        self.act_img_border = QAction("设置图片边框", self)
        self.act_img_border.triggered.connect(self.set_selected_image_border)

        self.act_auto_label = QAction("一键编号", self)
        self.act_auto_label.triggered.connect(self.add_auto_labels)

        self.act_edit_label = QAction("编辑选中编号", self)
        self.act_edit_label.triggered.connect(self.edit_selected_label_style)

        self.act_add_textbox = QAction("添加文本框", self)
        self.act_add_textbox.triggered.connect(self.add_text_box)

        self.act_textbox_font = QAction("设置文本框字体和大小", self)
        self.act_textbox_font.triggered.connect(self.set_selected_textbox_font)

        self.act_textbox_font_size = QAction("设置文本框字号", self)
        self.act_textbox_font_size.triggered.connect(self.set_selected_textbox_font_size)

        self.act_textbox_style = QAction("设置文本框样式", self)
        self.act_textbox_style.triggered.connect(self.set_selected_textbox_style)

        self.act_align_left = QAction("左对齐", self)
        self.act_align_left.triggered.connect(lambda: self.align_selected("left"))

        self.act_align_hc = QAction("水平居中", self)
        self.act_align_hc.triggered.connect(lambda: self.align_selected("hcenter"))

        self.act_align_right = QAction("右对齐", self)
        self.act_align_right.triggered.connect(lambda: self.align_selected("right"))

        self.act_align_top = QAction("顶对齐", self)
        self.act_align_top.triggered.connect(lambda: self.align_selected("top"))

        self.act_align_vc = QAction("垂直居中", self)
        self.act_align_vc.triggered.connect(lambda: self.align_selected("vcenter"))

        self.act_align_bottom = QAction("底对齐", self)
        self.act_align_bottom.triggered.connect(lambda: self.align_selected("bottom"))

        self.act_dist_h = QAction("水平等距", self)
        self.act_dist_h.triggered.connect(lambda: self.distribute_selected("h"))

        self.act_dist_v = QAction("垂直等距", self)
        self.act_dist_v.triggered.connect(lambda: self.distribute_selected("v"))

        self.act_export = QAction("导出...", self)
        self.act_export.triggered.connect(self.export_image)

        self.act_fit = QAction("适配画布", self)
        self.act_fit.triggered.connect(self.canvas_view.fit_page)

        self.act_snap = QAction("网格吸附", self)
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(self.toggle_snap)

        self.act_clear = QAction("清空", self)
        self.act_clear.triggered.connect(self.clear_all)

        # 为顶部工具栏与流程按钮统一附加图标
        self._attach_action_icons()

    def _attach_action_icons(self):
        """统一为各 QAction 绑定矢量图标，保证视觉一致。"""
        mapping = {
            self.act_new_project: "new",
            self.act_open_project: "open",
            self.act_save_project: "save",
            self.act_save_project_as: "save",
            self.act_undo: "undo",
            self.act_redo: "redo",
            self.act_fit: "fit",
            self.act_export: "export",
            self.act_import: "import",
            self.act_canvas: "canvas",
            self.act_layout_2x2: "grid_2x2",
            self.act_layout_2x3: "grid_2x3",
            self.act_layout_3x2: "grid_3x2",
            self.act_layout_2x4: "grid_2x4",
            self.act_layout_4x2: "grid_4x2",
            self.act_layout_custom: "grid_custom",
            self.act_auto_label: "label",
            self.act_edit_label: "label",
            self.act_add_textbox: "textbox",
            self.act_textbox_font: "textbox",
            self.act_textbox_style: "textbox",
            self.act_align_left: "align_left",
            self.act_align_right: "align_right",
            self.act_align_hc: "align_hcenter",
            self.act_align_top: "align_top",
            self.act_align_bottom: "align_bottom",
            self.act_align_vc: "align_vcenter",
            self.act_clear: "trash",
            self.act_snap: "snap",
            self.act_delete: "trash",
        }
        for act, name in mapping.items():
            try:
                act.setIcon(make_icon(name, color=TEXT_SECONDARY, size=20))
            except Exception:
                pass

    # ================================================================
    # 三栏布局构建
    # ================================================================

    def _build_three_panel_layout(self):
        """构建三栏布局骨架：顶部命令栏 + 左流程导航 + 中画布 + 右属性历史"""
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root.setStyleSheet(f"background-color: {BG_APP};")

        # 顶部简洁命令栏
        self._create_top_toolbar()

        # 主内容区：三栏分割
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setHandleWidth(1)

        # 左侧流程导航
        left_scroll = self._create_left_workflow_panel()
        self._main_splitter.addWidget(left_scroll)

        # 中央画布
        self._main_splitter.addWidget(self.canvas_view)

        # 右侧属性与历史
        right_panel = self._create_right_panel()
        self._main_splitter.addWidget(right_panel)

        # 紧凑分割比例：左 280 : 中弹性 : 右 280
        self._main_splitter.setSizes([280, 760, 280])
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setStretchFactor(2, 0)

        root_layout.addWidget(self._main_splitter)

        self._update_undo_redo_enabled()

    def _create_top_toolbar(self):
        """顶部主命令栏：品牌区 + 项目操作 + 历史 + 视图 + 导出"""
        tb = self.addToolBar("主命令栏")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # 品牌区
        brand = QWidget()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(4, 0, 12, 0)
        brand_layout.setSpacing(8)
        # 品牌方块
        logo = QLabel("◧")
        logo.setStyleSheet(
            f"font-size: 18px; color: {ACCENT}; padding: 0 2px; font-weight: 700;"
        )
        title = QLabel("Paper Figure")
        title.setStyleSheet(BRAND_TITLE_STYLE)
        ver = QLabel("v1.1")
        ver.setStyleSheet(BRAND_BADGE_STYLE)
        brand_layout.addWidget(logo)
        brand_layout.addWidget(title)
        brand_layout.addWidget(ver)
        tb.addWidget(brand)
        tb.addSeparator()

        # 项目操作（精简：只保留高频）
        for act in (self.act_new_project, self.act_open_project, self.act_save_project):
            tb.addAction(act)
        tb.addSeparator()
        # 历史
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        # 视图
        tb.addAction(self.act_fit)

        # 弹簧把"导出"推到右侧
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        tb.addWidget(spacer)

        # 主按钮：导出（强调色），用 QToolButton 配 PRIMARY 样式
        export_btn = QToolButton()
        export_btn.setDefaultAction(self.act_export)
        export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        export_btn.setIcon(make_icon("export", color="#FFFFFF", size=20))
        export_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: {ACCENT};
                color: #FFFFFF;
                border: 1px solid {ACCENT};
                border-radius: 6px;
                padding: 4px 14px;
                min-height: 26px;
                font-weight: 600;
            }}
            QToolButton:hover {{ background: #3A6BD4; border-color: #3A6BD4; }}
            QToolButton:pressed {{ background: #2D5ABE; border-color: #2D5ABE; }}
            """
        )
        tb.addWidget(export_btn)

    def _create_left_workflow_panel(self):
        """创建左侧流程导航面板：步骤化入口，返回 QScrollArea"""
        panel = QWidget()
        panel.setObjectName("workflow_panel")
        panel.setStyleSheet(WORKFLOW_PANEL_STYLE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(20)

        # 标题
        title = QLabel("工作流程")
        title.setStyleSheet(SECTION_TITLE_STYLE)
        layout.addWidget(title)

        # 步骤卡片
        self._workflow_cards: dict[str, QFrame] = {}
        steps = [
            ("step1", "① 导入素材", [
                ("导入图片", self.act_import),
                ("画布设置", self.act_canvas),
            ]),
            ("step2", "② 选择排版", [
                ("2×2", self.act_layout_2x2),
                ("2×3", self.act_layout_2x3),
                ("3×2", self.act_layout_3x2),
                ("2×4", self.act_layout_2x4),
                ("4×2", self.act_layout_4x2),
                ("自定义", self.act_layout_custom),
            ]),
            ("step3", "③ 添加标注", [
                ("一键编号", self.act_auto_label),
                ("编辑编号", self.act_edit_label),
                ("添加文本框", self.act_add_textbox),
            ]),
            ("step4", "④ 精调与导出", [
                ("左对齐", self.act_align_left),
                ("水平居中", self.act_align_hc),
                ("右对齐", self.act_align_right),
                ("顶对齐", self.act_align_top),
                ("垂直居中", self.act_align_vc),
                ("底对齐", self.act_align_bottom),
                ("导出...", self.act_export),
            ]),
        ]

        for step_id, title_text, actions in steps:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet(CARD_DEFAULT_STYLE)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(10)

            step_title = QLabel(title_text)
            step_title.setStyleSheet(STEP_TITLE_STYLE)
            card_layout.addWidget(step_title)

            btn_layout = QGridLayout()
            btn_layout.setSpacing(8)
            for i, (btn_text, action) in enumerate(actions):
                btn = QPushButton(btn_text)
                btn.setDefault(False)
                btn.setAutoDefault(False)
                btn.setStyleSheet(ACTION_BUTTON_STYLE)
                btn.setIcon(action.icon())
                btn.setIconSize(QSize(16, 16))
                btn.clicked.connect(action.trigger)
                btn_layout.addWidget(btn, i // 2, i % 2)
            card_layout.addLayout(btn_layout)

            layout.addWidget(card)
            self._workflow_cards[step_id] = card

        layout.addStretch()

        # 网格吸附开关
        snap_cb = QCheckBox("网格吸附")
        snap_cb.setChecked(True)
        snap_cb.toggled.connect(self.toggle_snap)
        layout.addWidget(snap_cb)

        # 清空按钮
        clear_btn = QPushButton("清空画布")
        clear_btn.setStyleSheet(DANGER_BUTTON_STYLE)
        clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _create_right_panel(self):
        """创建右侧属性与历史面板，返回 QWidget"""
        panel = QWidget()
        panel.setObjectName("right_panel")
        panel.setStyleSheet(RIGHT_PANEL_STYLE)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ---- 上半区：属性卡片 ----
        prop_card = QFrame()
        prop_card.setFrameShape(QFrame.Shape.StyledPanel)
        prop_card.setStyleSheet(CARD_DEFAULT_STYLE)
        prop_card.setObjectName("step_card")
        prop_layout = QVBoxLayout(prop_card)
        prop_layout.setContentsMargins(16, 16, 16, 16)
        prop_layout.setSpacing(10)

        prop_title = QLabel("属性")
        prop_title.setStyleSheet(SECTION_TITLE_STYLE)
        prop_layout.addWidget(prop_title)

        self.prop_canvas_info = QLabel("-")
        self.prop_canvas_info.setWordWrap(True)
        self.prop_canvas_info.setStyleSheet(INFO_STYLE)

        self.prop_selection_info = QLabel("-")
        self.prop_selection_info.setWordWrap(True)
        self.prop_selection_info.setStyleSheet(INFO_STYLE)

        self.prop_asset_list = QListWidget()
        self.prop_asset_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.prop_asset_name = QLineEdit()
        self.prop_asset_name.setPlaceholderText("素材显示名称")
        self.prop_asset_name.setEnabled(False)

        lbl1 = QLabel("画布信息")
        lbl1.setStyleSheet(LABEL_STYLE)
        lbl2 = QLabel("当前选择")
        lbl2.setStyleSheet(LABEL_STYLE)
        lbl3 = QLabel("素材列表")
        lbl3.setStyleSheet(LABEL_STYLE)
        lbl4 = QLabel("素材重命名")
        lbl4.setStyleSheet(LABEL_STYLE)

        prop_layout.addWidget(lbl1)
        prop_layout.addWidget(self.prop_canvas_info)
        prop_layout.addSpacing(10)
        prop_layout.addWidget(lbl2)
        prop_layout.addWidget(self.prop_selection_info)
        prop_layout.addSpacing(10)
        prop_layout.addWidget(lbl3)
        prop_layout.addWidget(self.prop_asset_list, 1)
        prop_layout.addSpacing(10)
        prop_layout.addWidget(lbl4)
        prop_layout.addWidget(self.prop_asset_name)

        layout.addWidget(prop_card, 1)

        # ---- 下半区：历史卡片 ----
        history_card = self._create_history_panel()
        layout.addWidget(history_card, 1)

        # 连接信号
        self.prop_asset_list.currentItemChanged.connect(self._on_asset_list_current_changed)
        self.prop_asset_name.editingFinished.connect(self._on_asset_name_edited)

        return panel

    def _create_history_panel(self):
        """创建历史时间线面板，返回 QFrame（卡片样式）"""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(CARD_DEFAULT_STYLE)
        card.setObjectName("step_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        history_title = QLabel("历史")
        history_title.setStyleSheet(SECTION_TITLE_STYLE)
        layout.addWidget(history_title)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(HISTORY_LIST_STYLE)
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        layout.addWidget(self.history_list)

        # 历史操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        self.btn_undo_hist = QPushButton("← 撤销")
        self.btn_undo_hist.setStyleSheet(HISTORY_BUTTON_STYLE)
        self.btn_undo_hist.clicked.connect(self.undo)
        self.btn_redo_hist = QPushButton("重做 →")
        self.btn_redo_hist.setStyleSheet(HISTORY_BUTTON_STYLE)
        self.btn_redo_hist.clicked.connect(self.redo)
        btn_layout.addWidget(self.btn_undo_hist)
        btn_layout.addWidget(self.btn_redo_hist)
        layout.addLayout(btn_layout)

        return card

    def _refresh_history_panel(self):
        """刷新历史时间线面板"""
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear()
        snapshots = self._history.snapshot_list()
        for snap in snapshots:
            idx = snap["index"]
            is_current = snap["is_current"]
            prefix = "▸ " if is_current else "    "
            label = f"{prefix}初始状态" if idx == 0 else f"{prefix}步骤 {idx}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            if is_current:
                item.setSelected(True)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.history_list.addItem(item)
        # 滚动到当前项
        current_items = self.history_list.findItems("▸ ", Qt.MatchFlag.MatchStartsWith)
        if current_items:
            self.history_list.scrollToItem(current_items[0])

    def _on_history_item_clicked(self, item: QListWidgetItem):
        """点击历史项跳转到该状态"""
        target_idx = item.data(Qt.ItemDataRole.UserRole)
        if target_idx is None:
            return
        current_idx = self._history.current_index()
        if target_idx == current_idx:
            return
        # 通过多次 undo/redo 跳转到目标位置
        self._history_timer.stop()
        self._history_block = True
        try:
            if target_idx < current_idx:
                for _ in range(current_idx - target_idx):
                    state = self._history.undo()
                    if state is None:
                        break
                    self._load_state_json(state)
            else:
                for _ in range(target_idx - current_idx):
                    state = self._history.redo()
                    if state is None:
                        break
                    self._load_state_json(state)
        finally:
            self._history_block = False
        self._update_undo_redo_enabled()
        self._refresh_history_panel()
        self._refresh_properties_panel()

    def _update_workflow_state(self):
        """根据当前画布状态更新工作流步骤卡片的视觉状态"""
        if not hasattr(self, "_workflow_cards"):
            return

        imgs = self.canvas_view.image_items()
        has_images = len(imgs) > 0
        has_content = has_images or any(
            isinstance(it, (LabelItem, TextBoxItem))
            for it in self.canvas_view.scene().items()
        )

        # 步骤1：导入素材 - 始终可用
        self._set_card_state("step1", "active")
        # 步骤2：选择排版 - 需要图片
        self._set_card_state("step2", "active" if has_images else "default")
        # 步骤3：添加标注 - 需要图片
        self._set_card_state("step3", "active" if has_images else "default")
        # 步骤4：精调与导出 - 需要内容
        self._set_card_state("step4", "active" if has_content else "default")

    def _set_card_state(self, step_id: str, state: str):
        """设置步骤卡片的视觉状态"""
        card = self._workflow_cards.get(step_id)
        if card is None:
            return
        if state == "active":
            card.setStyleSheet(CARD_ACTIVE_STYLE)
        else:
            card.setStyleSheet(CARD_DEFAULT_STYLE)

    def _refresh_properties_panel(self):
        if not hasattr(self, "prop_canvas_info"):
            return

        imgs = self.canvas_view.image_items()
        labels = [it for it in self.canvas_view.scene().items() if isinstance(it, LabelItem)]
        text_boxes = [it for it in self.canvas_view.scene().items() if isinstance(it, TextBoxItem)]

        selected = self.canvas_view.scene().selectedItems()
        sel_img = [it for it in selected if isinstance(it, ImageFrameItem)]
        sel_label = [it for it in selected if isinstance(it, LabelItem)]
        sel_text = [it for it in selected if isinstance(it, TextBoxItem)]

        self.prop_canvas_info.setText(
            f"{self.canvas_settings.width_mm:.1f} × {self.canvas_settings.height_mm:.1f} mm"
            f"\n{self.canvas_settings.width_px} × {self.canvas_settings.height_px} px @ {self.canvas_settings.dpi} DPI"
            f"\n图片 {len(imgs)} | 编号 {len(labels)} | 文本框 {len(text_boxes)}"
        )
        self.prop_selection_info.setText(
            f"共 {len(selected)} 项（图片 {len(sel_img)} / 编号 {len(sel_label)} / 文本框 {len(sel_text)}）"
        )

        old_current = self.prop_asset_list.currentItem()
        old_ref = self._asset_ref_map.get(id(old_current)) if old_current else None
        focus_img = sel_img[0] if len(sel_img) == 1 else old_ref
        if focus_img not in imgs:
            focus_img = None

        self._property_syncing = True
        try:
            self.prop_asset_list.clear()
            self._asset_ref_map.clear()

            for idx, img in enumerate(imgs, start=1):
                raw_name = str(getattr(img, "display_name", "") or "").strip()
                if not raw_name:
                    raw_name = os.path.basename(getattr(img, "source_path", "") or "") or f"素材{idx}"
                row = QListWidgetItem(f"{idx}. {raw_name}")
                self.prop_asset_list.addItem(row)
                self._asset_ref_map[id(row)] = img
                if img is focus_img:
                    self.prop_asset_list.setCurrentItem(row)

            if focus_img is not None:
                cur_name = str(getattr(focus_img, "display_name", "") or "").strip()
                if not cur_name:
                    cur_name = os.path.basename(getattr(focus_img, "source_path", "") or "") or "未命名素材"
                self.prop_asset_name.setEnabled(True)
                self.prop_asset_name.setText(cur_name)
            else:
                self.prop_asset_name.setEnabled(False)
                self.prop_asset_name.clear()
        finally:
            self._property_syncing = False

    def _on_scene_selection_changed(self):
        self._refresh_properties_panel()
        self._update_workflow_state()

    def _on_scene_modified(self):
        self._refresh_properties_panel()
        self._update_workflow_state()

    def _on_asset_list_current_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None):
        if self._property_syncing:
            return
        target = self._asset_ref_map.get(id(current)) if current else None
        if target is None:
            return

        self._property_syncing = True
        try:
            for it in self.canvas_view.scene().selectedItems():
                it.setSelected(False)
            target.setSelected(True)
            self.prop_asset_name.setEnabled(True)
            cur_name = str(getattr(target, "display_name", "") or "").strip()
            if not cur_name:
                cur_name = os.path.basename(getattr(target, "source_path", "") or "") or "未命名素材"
            self.prop_asset_name.setText(cur_name)
        finally:
            self._property_syncing = False

    def _on_asset_name_edited(self):
        if self._property_syncing:
            return

        current = self.prop_asset_list.currentItem() if hasattr(self, "prop_asset_list") else None
        target = self._asset_ref_map.get(id(current)) if current else None
        if target is None:
            selected = self.canvas_view.selected_image_items()
            if len(selected) == 1:
                target = selected[0]
        if target is None:
            return

        name = self.prop_asset_name.text().strip() if hasattr(self, "prop_asset_name") else ""
        if not name:
            name = os.path.basename(getattr(target, "source_path", "") or "") or "未命名素材"

        if name == str(getattr(target, "display_name", "") or ""):
            self.prop_asset_name.setText(name)
            return

        target.display_name = name
        self._refresh_properties_panel()
        self.canvas_view.notify_modified()
        self.statusBar().showMessage("素材名称已更新。", 1000)

    def select_all_items(self):
        count = self.canvas_view.select_all_items()
        if count > 0:
            self.statusBar().showMessage(f"已全选 {count} 项。", 900)
            self._refresh_properties_panel()
        return count

    def delete_selected_items(self):
        deleted = self.canvas_view.delete_selected_items()
        if deleted > 0:
            self.statusBar().showMessage(f"已删除 {deleted} 项。", 900)
            self._refresh_properties_panel()
        return deleted

    def _serialize_item_for_clipboard(self, it) -> dict | None:
        if isinstance(it, ImageFrameItem):
            fw, fh = it.frame_size()
            return {
                "type": "image",
                "source_path": str(getattr(it, "source_path", "")),
                "source_size": [
                    int(getattr(it, "source_size", (0, 0))[0]),
                    int(getattr(it, "source_size", (0, 0))[1]),
                ],
                "display_name": str(getattr(it, "display_name", "") or ""),
                "x": float(it.pos().x()),
                "y": float(it.pos().y()),
                "z": float(it.zValue()),
                "frame_w": int(fw),
                "frame_h": int(fh),
                "fill_mode": str(getattr(it, "fill_mode", self.default_fill_mode)),
                "rot90_steps": int(getattr(it, "rot90_steps", 0)) % 4,
                "flip_h": bool(getattr(it, "flip_h", False)),
                "flip_v": bool(getattr(it, "flip_v", False)),
                "border_width": int(getattr(it, "border_width", 0)),
                "border_color": list(getattr(it, "border_color", (0, 0, 0))),
            }

        if isinstance(it, LabelItem):
            font = QFont(it.font_obj)
            size = font.pointSize() if font.pointSize() > 0 else 18
            return {
                "type": "label",
                "text": str(it.text),
                "x": float(it.pos().x()),
                "y": float(it.pos().y()),
                "z": float(it.zValue()),
                "padding": int(getattr(it, "padding", 4)),
                "font_family": font.family(),
                "font_size": int(size),
                "font_weight": int(font.weight()),
                "font_italic": bool(font.italic()),
                "text_color": [it.text_color.red(), it.text_color.green(), it.text_color.blue(), it.text_color.alpha()],
                "bg_enabled": bool(getattr(it, "bg_enabled", False)),
                "bg_color": [it.bg_color.red(), it.bg_color.green(), it.bg_color.blue(), it.bg_color.alpha()],
                "is_auto_label": bool(getattr(it, "is_auto_label", False)),
            }

        if isinstance(it, TextBoxItem):
            font = QFont(it.font())
            size = font.pointSize() if font.pointSize() > 0 else 14
            return {
                "type": "textbox",
                "text": str(it.toPlainText()),
                "x": float(it.pos().x()),
                "y": float(it.pos().y()),
                "z": float(it.zValue()),
                "font_family": font.family(),
                "font_size": int(size),
                "font_weight": int(font.weight()),
                "font_italic": bool(font.italic()),
                "width": float(getattr(it, "_box_w", max(80.0, it.textWidth()))),
                "height": float(getattr(it, "_box_h", it.boundingRect().height())),
                "lock_position": bool(getattr(it, "_lock_position", False)),
                "lock_size": bool(getattr(it, "_lock_size", False)),
                "text_color": [
                    int(getattr(it, "_text_color", QColor(0, 0, 0)).red()),
                    int(getattr(it, "_text_color", QColor(0, 0, 0)).green()),
                    int(getattr(it, "_text_color", QColor(0, 0, 0)).blue()),
                    int(getattr(it, "_text_color", QColor(0, 0, 0)).alpha()),
                ],
                "fill_color": [
                    int(getattr(it, "_fill_color", QColor(255, 255, 255)).red()),
                    int(getattr(it, "_fill_color", QColor(255, 255, 255)).green()),
                    int(getattr(it, "_fill_color", QColor(255, 255, 255)).blue()),
                    int(getattr(it, "_fill_color", QColor(255, 255, 255)).alpha()),
                ],
                "fill_alpha": int(getattr(it, "_fill_alpha", 70)),
                "border_color": [
                    int(getattr(it, "_border_color", QColor(170, 170, 170)).red()),
                    int(getattr(it, "_border_color", QColor(170, 170, 170)).green()),
                    int(getattr(it, "_border_color", QColor(170, 170, 170)).blue()),
                    int(getattr(it, "_border_color", QColor(170, 170, 170)).alpha()),
                ],
                "border_width": int(getattr(it, "_border_width", 1)),
            }

        return None

    def copy_selected_items(self, *, show_message: bool = True):
        page = self.canvas_view.page_rect_item
        selected = [it for it in self.canvas_view.scene().selectedItems() if it is not page]
        if not selected:
            if show_message:
                self.statusBar().showMessage("没有可复制的对象。", 900)
            return 0

        selected = sorted(selected, key=lambda it: (it.zValue(), it.sceneBoundingRect().top(), it.sceneBoundingRect().left()))
        items_data = []
        min_x = None
        min_y = None

        for it in selected:
            obj = self._serialize_item_for_clipboard(it)
            if obj is None:
                continue
            items_data.append(obj)
            x = float(obj.get("x", 0.0))
            y = float(obj.get("y", 0.0))
            min_x = x if min_x is None else min(min_x, x)
            min_y = y if min_y is None else min(min_y, y)

        if not items_data:
            if show_message:
                self.statusBar().showMessage("选中对象不支持复制。", 900)
            return 0

        self._clipboard_payload = {
            "items": items_data,
            "anchor_x": float(min_x if min_x is not None else 0.0),
            "anchor_y": float(min_y if min_y is not None else 0.0),
        }
        self._paste_serial = 0

        if show_message:
            self.statusBar().showMessage(f"已复制 {len(items_data)} 项。", 900)
        return len(items_data)

    def cut_selected_items(self):
        copied = self.copy_selected_items(show_message=False)
        if copied <= 0:
            self.statusBar().showMessage("没有可剪切的对象。", 900)
            return 0

        deleted = self.delete_selected_items()
        if deleted > 0:
            self.statusBar().showMessage(f"已剪切 {deleted} 项。", 900)
        return deleted

    def paste_items(self):
        payload = self._clipboard_payload if isinstance(self._clipboard_payload, dict) else None
        if not payload:
            self.statusBar().showMessage("剪贴板为空。", 900)
            return 0

        items_data = payload.get("items")
        if not isinstance(items_data, list) or not items_data:
            self.statusBar().showMessage("剪贴板内容无效。", 900)
            return 0

        anchor_x = float(payload.get("anchor_x", 0.0))
        anchor_y = float(payload.get("anchor_y", 0.0))

        self._paste_serial += 1
        shift = 24 * self._paste_serial

        scene = self.canvas_view.scene()
        for it in scene.selectedItems():
            it.setSelected(False)

        def _to_color(v, default: QColor):
            if isinstance(v, (list, tuple)) and len(v) >= 3:
                a = int(v[3]) if len(v) >= 4 else 255
                return QColor(int(v[0]), int(v[1]), int(v[2]), a)
            return QColor(default)

        added = 0
        missing_images = []

        for obj in items_data:
            if not isinstance(obj, dict):
                continue
            t = obj.get("type")

            new_item = None
            if t == "image":
                source_path = str(obj.get("source_path", "")).strip()
                if not source_path or (not os.path.exists(source_path)):
                    missing_images.append(source_path or "<空路径>")
                    continue

                key = os.path.normcase(os.path.abspath(source_path))
                cached = self._image_thumb_cache.get(key) if isinstance(self._image_thumb_cache, dict) else None
                pixmap = None
                ow = 0
                oh = 0
                if isinstance(cached, tuple) and len(cached) == 2:
                    pm, sz = cached
                    try:
                        if not pm.isNull():
                            pixmap = QPixmap(pm)
                            ow, oh = int(sz[0]), int(sz[1])
                    except Exception:
                        pixmap = None

                if pixmap is None:
                    try:
                        pixmap, (ow, oh) = load_image_thumb_qpixmap(source_path, max_thumb=2200)
                        self._image_thumb_cache[key] = (QPixmap(pixmap), (int(ow), int(oh)))
                    except Exception:
                        missing_images.append(source_path)
                        continue

                source_size = obj.get("source_size", [ow, oh])
                if not isinstance(source_size, (list, tuple)) or len(source_size) < 2:
                    source_size = [ow, oh]

                new_item = ImageFrameItem(
                    source_path,
                    (int(source_size[0]), int(source_size[1])),
                    pixmap,
                    self.canvas_view,
                    fill_mode=str(obj.get("fill_mode", self.default_fill_mode)),
                    display_name=str(obj.get("display_name", "") or ""),
                )
                new_item.rot90_steps = int(obj.get("rot90_steps", 0)) % 4
                new_item.flip_h = bool(obj.get("flip_h", False))
                new_item.flip_v = bool(obj.get("flip_v", False))
                new_item.set_frame_size(int(obj.get("frame_w", pixmap.width())), int(obj.get("frame_h", pixmap.height())))
                new_item.set_border(int(obj.get("border_width", 0)), _to_color(obj.get("border_color"), QColor(0, 0, 0)))

            elif t == "label":
                font = QFont(
                    str(obj.get("font_family", "Times New Roman")),
                    int(obj.get("font_size", 18)),
                    int(obj.get("font_weight", int(QFont.Weight.Bold))),
                    bool(obj.get("font_italic", False)),
                )
                new_item = LabelItem(
                    str(obj.get("text", "")),
                    self.canvas_view,
                    font=font,
                    padding=int(obj.get("padding", 4)),
                )
                new_item.text_color = _to_color(obj.get("text_color"), QColor(0, 0, 0))
                new_item.bg_color = _to_color(obj.get("bg_color"), QColor(0, 0, 0))
                new_item.bg_enabled = bool(obj.get("bg_enabled", False))
                new_item.is_auto_label = bool(obj.get("is_auto_label", False))
                new_item.update()

            elif t == "textbox":
                font = QFont(
                    str(obj.get("font_family", "Microsoft YaHei UI")),
                    int(obj.get("font_size", 14)),
                    int(obj.get("font_weight", int(QFont.Weight.Normal))),
                    bool(obj.get("font_italic", False)),
                )
                new_item = TextBoxItem(
                    str(obj.get("text", "")),
                    self.canvas_view,
                    font=font,
                    width=float(obj.get("width", 320)),
                )
                if hasattr(new_item, "_set_box_height"):
                    new_item._set_box_height(float(obj.get("height", getattr(new_item, "_box_h", 60))))
                if hasattr(new_item, "_sync_height_to_content"):
                    new_item._sync_height_to_content(force=False)
                if hasattr(new_item, "set_position_locked"):
                    new_item.set_position_locked(bool(obj.get("lock_position", False)))
                if hasattr(new_item, "set_size_locked"):
                    new_item.set_size_locked(bool(obj.get("lock_size", False)))
                if hasattr(new_item, "set_style"):
                    fill_c = _to_color(obj.get("fill_color"), QColor(255, 255, 255))
                    new_item.set_style(
                        text_color=_to_color(obj.get("text_color"), QColor(0, 0, 0)),
                        fill_color=QColor(fill_c.red(), fill_c.green(), fill_c.blue()),
                        fill_alpha=int(obj.get("fill_alpha", 70)),
                        border_color=_to_color(obj.get("border_color"), QColor(170, 170, 170)),
                        border_width=int(obj.get("border_width", 1)),
                    )

            if new_item is None:
                continue

            x = float(obj.get("x", 0.0)) - anchor_x + shift
            y = float(obj.get("y", 0.0)) - anchor_y + shift
            z = float(obj.get("z", 0.0)) + self._paste_serial * 0.01
            new_item.setPos(x, y)
            new_item.setZValue(z)
            scene.addItem(new_item)
            new_item.setSelected(True)
            added += 1

        if added <= 0:
            if missing_images:
                sample = "\n".join(missing_images[:6])
                QMessageBox.warning(self, "粘贴失败", f"以下图片不存在或无法读取：\n{sample}")
            else:
                self.statusBar().showMessage("没有可粘贴的对象。", 900)
            return 0

        self.canvas_view.notify_modified()
        self._refresh_properties_panel()

        if missing_images:
            sample = "\n".join(missing_images[:6])
            more = f"\n... 还有 {len(missing_images)-6} 个" if len(missing_images) > 6 else ""
            QMessageBox.warning(self, "部分素材缺失", f"以下图片未能粘贴：\n{sample}{more}")

        self.statusBar().showMessage(f"已粘贴 {added} 项。", 1000)
        return added

    # ----------------- 导入 -----------------
    def _import_aggregate_progress(self) -> tuple[int, int]:
        done = sum(int(v) for v in self._import_batch_done.values())
        total = sum(int(v) for v in self._import_batch_total.values())
        return done, total

    def import_images(self, paths: list[str] | tuple[str, ...] | bool | None = None):
        if isinstance(paths, bool) or paths is None:
            chosen, _ = QFileDialog.getOpenFileNames(
                self,
                "选择图片",
                "",
                "图片文件 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)",
            )
            paths = chosen
        elif not isinstance(paths, (list, tuple)):
            paths = [str(paths)]

        clean_paths: list[str] = []
        seen: set[str] = set()
        for p in paths:
            p = str(p).strip()
            if not p or p in seen:
                continue
            if not os.path.isfile(p):
                continue
            if hasattr(CanvasView, "_is_supported_image_path") and not CanvasView._is_supported_image_path(p):
                continue
            seen.add(p)
            clean_paths.append(p)

        if not clean_paths:
            return

        batch_id = self.loader.load_files(clean_paths)
        if batch_id is None:
            return

        self._active_import_batches.add(int(batch_id))
        self._import_batch_done[int(batch_id)] = 0
        self._import_batch_total[int(batch_id)] = len(clean_paths)
        self._is_importing = True

        total_batches = len(self._active_import_batches)
        if total_batches == 1:
            self.statusBar().showMessage(f"开始追加加载 {len(clean_paths)} 张图片 ...")
        else:
            self.statusBar().showMessage(
                f"已加入新的导入批次（+{len(clean_paths)} 张），当前并行批次 {total_batches} 个。"
            )

    def _on_image_loaded(self, batch_id: int, path: str, qimage_obj, orig_w: int, orig_h: int):
        if int(batch_id) not in self._active_import_batches:
            return

        pixmap = QPixmap.fromImage(qimage_obj)
        self._cache_thumb_from_import(path, pixmap, orig_w, orig_h)

        item = ImageFrameItem(
            path,
            (orig_w, orig_h),
            pixmap,
            self.canvas_view,
            fill_mode=self.default_fill_mode,
        )

        long_edge = max(1, max(pixmap.width(), pixmap.height()))
        scale = 260 / long_edge
        w = max(80, int(round(pixmap.width() * scale)))
        h = max(80, int(round(pixmap.height() * scale)))
        item.set_frame_size(w, h)

        n = len(self.canvas_view.image_items())
        item.setPos(20 + n * 12, 20 + n * 12)
        self.canvas_view.scene().addItem(item)

    def _on_image_failed(self, batch_id: int, path: str, err: str):
        if int(batch_id) not in self._active_import_batches:
            return
        self.statusBar().showMessage(f"加载失败: {os.path.basename(path)} -> {err}")

    def _on_load_progress(self, batch_id: int, done: int, total: int):
        bid = int(batch_id)
        if bid not in self._active_import_batches:
            return

        self._import_batch_done[bid] = int(done)
        self._import_batch_total[bid] = int(total)

        all_done, all_total = self._import_aggregate_progress()
        self.statusBar().showMessage(
            f"加载中: {all_done}/{all_total}（批次#{bid}: {done}/{total}）"
        )

    def _on_load_finished(self, batch_id: int):
        bid = int(batch_id)
        if bid not in self._active_import_batches:
            return

        self._active_import_batches.discard(bid)
        self._import_batch_done.pop(bid, None)
        self._import_batch_total.pop(bid, None)

        if self._active_import_batches:
            remain = len(self._active_import_batches)
            all_done, all_total = self._import_aggregate_progress()
            self._is_importing = True
            self.statusBar().showMessage(
                f"批次#{bid} 已完成，剩余 {remain} 个批次（{all_done}/{all_total}）。"
            )
            return

        self._is_importing = False
        self.statusBar().showMessage("图片加载完成 ✓  下一步：选择排版模板（如 2×2）", 3000)
        self._refresh_properties_panel()
        self._update_workflow_state()
        self._schedule_history_commit()

    # ----------------- 画布 -----------------
    def set_canvas(self):
        dlg = CanvasSettingsDialog(self.canvas_settings, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.canvas_settings = dlg.get_settings()
        self.canvas_view.set_canvas_size_px(self.canvas_settings.width_px, self.canvas_settings.height_px)
        QTimer.singleShot(0, self.canvas_view.fit_page)
        self.statusBar().showMessage(
            f"画布已更新: {self.canvas_settings.width_mm}×{self.canvas_settings.height_mm} mm @ {self.canvas_settings.dpi} DPI",
            2200,
        )
        self._schedule_history_commit()

    # ----------------- 排版 -----------------
    def _layout_target_items(self):
        items = self.canvas_view.selected_image_items()
        if not items:
            items = self.canvas_view.image_items()
        return items

    def _has_auto_labels(self) -> bool:
        for it in self.canvas_view.scene().items():
            if isinstance(it, LabelItem) and it.is_auto_label:
                return True
        return False

    def apply_layout(self, rows: int, cols: int):
        items = self._layout_target_items()
        if not items:
            QMessageBox.information(self, "提示", "请先导入图片。")
            return

        had_auto = self._has_auto_labels()
        capacity = rows * cols
        use_items = items[:capacity]
        if len(items) > capacity:
            QMessageBox.information(self, "提示", f"当前模板最多排 {capacity} 张，已排前 {capacity} 张。")

        page_w, page_h = self.canvas_view.page_size_px()
        try:
            apply_grid_layout(use_items, page_w, page_h, rows, cols, margin=40, gap=20)
            if had_auto and self.last_numbering_cfg:
                self._create_auto_labels(self.last_numbering_cfg)
            self.statusBar().showMessage(f"已完成 {rows}×{cols} 排版 ✓  下一步：一键编号或直接导出", 3000)
            self._update_workflow_state()
            self._schedule_history_commit()
        except Exception as e:
            QMessageBox.critical(self, "排版失败", str(e))

    def apply_custom_layout(self):
        dlg = CustomLayoutDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_layout(dlg.get_rows(), dlg.get_cols())

    # ----------------- 网格 -----------------
    def toggle_snap(self, checked: bool):
        self.canvas_view.snap_enabled = checked
        self.canvas_view.show_grid = checked
        self.canvas_view.viewport().update()
        self.statusBar().showMessage("网格吸附已开启" if checked else "网格吸附已关闭", 900)

    # ----------------- 对齐/分布 -----------------
    def _movable_selected_items(self):
        out = []
        for it in self.canvas_view.scene().selectedItems():
            if it is self.canvas_view.page_rect_item:
                continue
            if it.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
                out.append(it)
        return out

    def _move_item_by(self, item, dx: float, dy: float):
        item.setPos(item.pos() + QPointF(dx, dy))

    def _batch_without_snap(self, func):
        old = self.canvas_view.snap_enabled
        self.canvas_view.snap_enabled = False
        try:
            func()
        finally:
            self.canvas_view.snap_enabled = old

    def align_selected(self, mode: str):
        items = self._movable_selected_items()
        if len(items) < 2:
            QMessageBox.information(self, "提示", "请至少选择 2 个对象进行对齐。")
            return

        rects = [it.sceneBoundingRect() for it in items]
        left = min(r.left() for r in rects)
        right = max(r.right() for r in rects)
        top = min(r.top() for r in rects)
        bottom = max(r.bottom() for r in rects)
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0

        def _do():
            for it, r in zip(items, rects):
                dx = 0.0
                dy = 0.0
                if mode == "left":
                    dx = left - r.left()
                elif mode == "hcenter":
                    dx = cx - r.center().x()
                elif mode == "right":
                    dx = right - r.right()
                elif mode == "top":
                    dy = top - r.top()
                elif mode == "vcenter":
                    dy = cy - r.center().y()
                elif mode == "bottom":
                    dy = bottom - r.bottom()
                self._move_item_by(it, dx, dy)

        self._batch_without_snap(_do)
        self.statusBar().showMessage("对齐完成。", 900)
        self._schedule_history_commit()

    def distribute_selected(self, mode: str):
        items = self._movable_selected_items()
        if len(items) < 3:
            QMessageBox.information(self, "提示", "请至少选择 3 个对象进行等距分布。")
            return

        def _do_h():
            pairs = sorted([(it, it.sceneBoundingRect()) for it in items], key=lambda x: x[1].left())
            first_left = pairs[0][1].left()
            last_right = pairs[-1][1].right()
            total_w = sum(r.width() for _, r in pairs)
            span = last_right - first_left
            if span <= total_w:
                return
            gap = (span - total_w) / (len(pairs) - 1)
            cursor = first_left
            for it, r in pairs:
                self._move_item_by(it, cursor - r.left(), 0)
                cursor += r.width() + gap

        def _do_v():
            pairs = sorted([(it, it.sceneBoundingRect()) for it in items], key=lambda x: x[1].top())
            first_top = pairs[0][1].top()
            last_bottom = pairs[-1][1].bottom()
            total_h = sum(r.height() for _, r in pairs)
            span = last_bottom - first_top
            if span <= total_h:
                return
            gap = (span - total_h) / (len(pairs) - 1)
            cursor = first_top
            for it, r in pairs:
                self._move_item_by(it, 0, cursor - r.top())
                cursor += r.height() + gap

        if mode == "h":
            self._batch_without_snap(_do_h)
            self.statusBar().showMessage("水平等距完成。", 900)
        else:
            self._batch_without_snap(_do_v)
            self.statusBar().showMessage("垂直等距完成。", 900)
        self._schedule_history_commit()

    # ----------------- 编号 -----------------
    @staticmethod
    def _index_to_alpha(idx: int, upper: bool = False) -> str:
        base = 65 if upper else 97
        s = ""
        n = max(1, idx)
        while n > 0:
            n -= 1
            s = chr(base + (n % 26)) + s
            n //= 26
        return s

    @staticmethod
    def _index_to_roman(idx: int) -> str:
        vals = [
            (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
            (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
            (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
        ]
        n = max(1, idx)
        out = []
        for v, t in vals:
            while n >= v:
                out.append(t)
                n -= v
        return "".join(out)

    def _format_label_text(self, idx: int, style: str) -> str:
        a = self._index_to_alpha(idx, upper=False)
        A = self._index_to_alpha(idx, upper=True)
        r = self._index_to_roman(idx)

        if style == "a, b, c":
            return a
        if style == "a), b), c)":
            return f"{a})"
        if style == "(a), (b), (c)":
            return f"({a})"
        if style == "A, B, C":
            return A
        if style == "i, ii, iii":
            return r
        if style == "(i), (ii), (iii)":
            return f"({r})"
        return a

    def _create_auto_labels(self, cfg: dict):
        scene = self.canvas_view.scene()

        for it in list(scene.items()):
            if isinstance(it, LabelItem) and it.is_auto_label:
                scene.removeItem(it)

        imgs = self.canvas_view.image_items()
        if not imgs:
            return

        font = QFont(cfg.get("font_family", "Times New Roman"), int(cfg.get("font_size", 20)), QFont.Weight.Bold)
        corner = cfg.get("corner", "左上")
        ox = int(cfg.get("offset_x", 8))
        oy = int(cfg.get("offset_y", 8))
        use_black = bool(cfg.get("black_bg", False))

        for i, img in enumerate(imgs, start=1):
            t = self._format_label_text(i, cfg.get("style", "(a), (b), (c)"))
            lb = LabelItem(t, self.canvas_view, font=font, padding=4)
            lb.set_black_bg(use_black)
            lb.is_auto_label = True
            lb.setZValue(3000)
            scene.addItem(lb)

            ir = img.sceneBoundingRect()
            lr = lb.boundingRect()

            if corner == "左上":
                x = ir.left() + ox
                y = ir.top() + oy
            elif corner == "右上":
                x = ir.right() - lr.width() - ox
                y = ir.top() + oy
            elif corner == "左下":
                x = ir.left() + ox
                y = ir.bottom() - lr.height() - oy
            else:
                x = ir.right() - lr.width() - ox
                y = ir.bottom() - lr.height() - oy

            lb.setPos(x, y)

    def add_auto_labels(self):
        if not self.canvas_view.image_items():
            QMessageBox.information(self, "提示", "请先导入图片。")
            return

        state_before_preview = self._state_json()
        dlg = NumberingDialog(self.last_numbering_cfg, self)

        def _on_preview(cfg: dict):
            self._create_auto_labels(cfg)
            self._refresh_properties_panel()

        dlg.previewChanged.connect(_on_preview)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._load_state_json(state_before_preview)
            self._refresh_properties_panel()
            self.statusBar().showMessage("已取消自动编号。", 900)
            return

        cfg = dlg.get_data()
        self.last_numbering_cfg = cfg
        self._create_auto_labels(cfg)
        self._refresh_properties_panel()
        self.statusBar().showMessage("已完成自动编号 ✓  下一步：导出为图片或 PDF", 3000)
        self._schedule_history_commit()

    def edit_selected_label_style(self):
        labels = [it for it in self.canvas_view.scene().selectedItems() if isinstance(it, LabelItem)]
        if len(labels) != 1:
            QMessageBox.information(self, "提示", "请选中 1 个编号后再编辑。")
            return

        lb = labels[0]
        dlg = LabelStyleDialog(lb, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        lb.set_text(data["text"])
        lb.set_font(QFont(data["font_family"], int(data["font_size"]), QFont.Weight.Bold))
        lb.set_black_bg(bool(data["black_bg"]))
        lb.is_auto_label = False
        self.statusBar().showMessage("编号样式已更新。", 1000)
        self._schedule_history_commit()

    # ----------------- 文本框 -----------------
    def add_text_box(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "添加文本框", "文本内容：", "双击文本框可编辑"
        )
        if not ok:
            return
        text = text.strip() or "双击文本框可编辑"

        size, ok = QInputDialog.getInt(self, "文本框字号", "字号：", 14, 6, 300, 1)
        if not ok:
            return

        item = TextBoxItem(text, self.canvas_view, font=QFont("Microsoft YaHei UI", size), width=320)
        item.setZValue(3400)
        self.canvas_view.scene().addItem(item)
        item.setPos(40, 40)
        self.statusBar().showMessage("文本框已添加。", 1000)
        self._schedule_history_commit()

    def _selected_text_boxes(self) -> list[TextBoxItem]:
        return [it for it in self.canvas_view.scene().selectedItems() if isinstance(it, TextBoxItem)]

    def set_selected_textbox_font(self):
        boxes = self._selected_text_boxes()
        if not boxes:
            QMessageBox.information(self, "提示", "请先选中一个或多个文本框。")
            return

        dlg = TextBoxFontDialogCN(QFont(boxes[0].font()), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        chosen = dlg.selected_font()
        for b in boxes:
            b.setFont(QFont(chosen))

        self.statusBar().showMessage(f"已更新 {len(boxes)} 个文本框字体和字号。", 1000)
        self._schedule_history_commit()

    def set_selected_textbox_font_size(self):
        boxes = self._selected_text_boxes()
        if not boxes:
            QMessageBox.information(self, "提示", "请先选中一个或多个文本框。")
            return

        cur = boxes[0].font().pointSize()
        if cur <= 0:
            cur = 14

        size, ok = QInputDialog.getInt(self, "设置文本框字号", "字号：", cur, 6, 300, 1)
        if not ok:
            return

        for b in boxes:
            f = QFont(b.font())
            f.setPointSize(size)
            b.setFont(f)

        self.statusBar().showMessage(f"已将 {len(boxes)} 个文本框字号设为 {size}。", 1000)
        self._schedule_history_commit()

    def set_selected_textbox_style(self):
        boxes = self._selected_text_boxes()
        if not boxes:
            QMessageBox.information(self, "提示", "请先选中一个或多个文本框。")
            return

        dlg = TextBoxStyleDialog(boxes[0], self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        s = dlg.get_data()
        for b in boxes:
            b.set_style(
                text_color=s["text_color"],
                fill_color=s["fill_color"],
                fill_alpha=s["fill_alpha"],
                border_color=s["border_color"],
                border_width=s["border_width"],
            )

        self.statusBar().showMessage(f"已更新 {len(boxes)} 个文本框样式。", 1000)
        self._schedule_history_commit()

    # ----------------- 图片编辑 -----------------
    def _selected_image_items_or_warn(self) -> list[ImageFrameItem]:
        items = self.canvas_view.selected_image_items()
        if not items:
            QMessageBox.information(self, "提示", "请先选中一张或多张图片。")
            return []
        return items

    def rotate_selected_images_left(self):
        items = self._selected_image_items_or_warn()
        if not items:
            return
        for it in items:
            it.rotate_left()
        self.statusBar().showMessage(f"已左转 {len(items)} 张图片。", 900)
        self._schedule_history_commit()

    def rotate_selected_images_right(self):
        items = self._selected_image_items_or_warn()
        if not items:
            return
        for it in items:
            it.rotate_right()
        self.statusBar().showMessage(f"已右转 {len(items)} 张图片。", 900)
        self._schedule_history_commit()

    def flip_selected_images_h(self):
        items = self._selected_image_items_or_warn()
        if not items:
            return
        for it in items:
            it.flip_horizontal()
        self.statusBar().showMessage(f"已水平翻转 {len(items)} 张图片。", 900)
        self._schedule_history_commit()

    def flip_selected_images_v(self):
        items = self._selected_image_items_or_warn()
        if not items:
            return
        for it in items:
            it.flip_vertical()
        self.statusBar().showMessage(f"已垂直翻转 {len(items)} 张图片。", 900)
        self._schedule_history_commit()

    def reset_selected_image_transform(self):
        items = self._selected_image_items_or_warn()
        if not items:
            return
        for it in items:
            it.reset_transform_ops()
        self.statusBar().showMessage(f"已重置 {len(items)} 张图片变换。", 900)
        self._schedule_history_commit()

    def set_selected_image_border(self):
        items = self._selected_image_items_or_warn()
        if not items:
            return

        default_w = int(getattr(items[0], "border_width", 0))
        w, ok = QInputDialog.getInt(
            self,
            "设置图片边框",
            "边框宽度(px，0表示无边框)：",
            default_w,
            0,
            60,
            1,
        )
        if not ok:
            return

        if w == 0:
            for it in items:
                it.set_border(0, getattr(it, "border_color", (0, 0, 0)))
            self.statusBar().showMessage(f"已清除 {len(items)} 张图片边框。", 900)
            self._schedule_history_commit()
            return

        c0 = getattr(items[0], "border_color", (0, 0, 0))
        start_color = QColor(int(c0[0]), int(c0[1]), int(c0[2]))
        color = QColorDialog.getColor(start_color, self, "选择边框颜色")
        if not color.isValid():
            return

        for it in items:
            it.set_border(w, color)

        self.statusBar().showMessage(f"已设置 {len(items)} 张图片边框。", 900)
        self._schedule_history_commit()

    # ----------------- 导出 -----------------
    def _ask_export_transparent_mode(self, ext: str) -> tuple[bool, bool]:
        allow_transparent = ext in (".png", ".tif", ".tiff", ".pdf", ".svg")
        if not allow_transparent:
            return False, True

        mode, ok = QInputDialog.getItem(
            self,
            "导出背景",
            "背景模式：",
            ["白色背景", "透明背景"],
            0,
            False,
        )
        if not ok:
            return False, False
        return (mode == "透明背景"), True

    def export_image(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出",
            "",
            "JPEG (*.jpg *.jpeg);;PNG (*.png);;TIFF (*.tif *.tiff);;PDF (*.pdf);;SVG (*.svg)",
        )
        if not path:
            return

        base = os.path.basename(path).lower()
        if "." not in base:
            if "JPEG" in selected_filter:
                path += ".jpg"
            elif "PNG" in selected_filter:
                path += ".png"
            elif "TIFF" in selected_filter:
                path += ".tif"
            elif "PDF" in selected_filter:
                path += ".pdf"
            else:
                path += ".svg"

        ext = os.path.splitext(path)[1].lower()

        transparent_bg, ok = self._ask_export_transparent_mode(ext)
        if not ok:
            return

        dpi, ok = QInputDialog.getInt(
            self, "导出 DPI", "请输入 DPI", self.canvas_settings.dpi, 72, 1200, 1
        )
        if not ok:
            return

        try:
            if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
                export_canvas_to_image(
                    self.canvas_view,
                    path,
                    dpi=dpi,
                    jpeg_quality=95,
                    transparent_bg=transparent_bg,
                )
            elif ext == ".pdf":
                export_canvas_to_pdf(self.canvas_view, path, dpi=dpi, transparent_bg=transparent_bg)
            elif ext == ".svg":
                export_canvas_to_svg(self.canvas_view, path, dpi=dpi, transparent_bg=transparent_bg)
            else:
                raise ValueError("不支持该格式。请选择 jpg/png/tiff/pdf/svg。")

            QMessageBox.information(self, "导出成功", f"已导出：\n{path}")
            self.statusBar().showMessage("导出完成 ✓  全流程结束", 3000)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def closeEvent(self, event: QCloseEvent):
        if self._confirm_continue_if_unsaved():
            event.accept()
        else:
            event.ignore()

    # ----------------- 清空 -----------------
    def clear_all(self):
        scene_items = [it for it in self.canvas_view.scene().items() if it is not self.canvas_view.page_rect_item]
        if not scene_items:
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("确认清空")
        msg.setText("确定删除画布上的全部内容吗？")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        yes_btn = msg.button(QMessageBox.StandardButton.Yes)
        no_btn = msg.button(QMessageBox.StandardButton.No)
        if yes_btn:
            yes_btn.setText("确定")
        if no_btn:
            no_btn.setText("取消")

        ret = QMessageBox.StandardButton(msg.exec())
        if ret == QMessageBox.StandardButton.Yes:
            self.canvas_view.remove_all_user_items()
            self.statusBar().showMessage("已清空。", 900)
            self._schedule_history_commit()