"""全局视觉主题 — V3 紧凑现代风

设计原则：
- 单屏装得下：紧凑而不局促
- 简约而不简单：通过留白节奏 + 微动效 + 精致图标传达层次
- 信息层级清晰：标题 > 正文 > 辅助 > 禁用
- 低饱和蓝主色，柔和阴影，避免视觉噪声
- 所有交互件都有 hover/press 反馈
"""

from __future__ import annotations

# ============================================================
# Design Tokens
# ============================================================

# 色彩
BG_APP = "#F0F2F5"
BG_PRIMARY = "#FFFFFF"
BG_SECONDARY = "#F7F8FA"
BG_TERTIARY = "#EEF0F3"
BG_CANVAS = "#E4E7EB"
BG_SIDEBAR = "#F5F6F8"
BG_TOOLBAR = "#FFFFFF"

BORDER_NONE = "transparent"
BORDER_SUBTLE = "#E8EAED"
BORDER_LIGHT = "#DDE0E5"
BORDER_CONTROL = "#CDD1D8"
BORDER_FOCUS = "#5B8DEF"

TEXT_PRIMARY = "#1D2129"
TEXT_SECONDARY = "#4E5969"
TEXT_TERTIARY = "#86909C"
TEXT_DISABLED = "#C9CDD4"
TEXT_ON_ACCENT = "#FFFFFF"

ACCENT = "#4A7FE5"
ACCENT_HOVER = "#3A6BD4"
ACCENT_ACTIVE = "#2D5ABE"
ACCENT_LIGHT_BG = "#EEF3FF"
ACCENT_SUBTLE = "#F5F8FF"

DANGER = "#CB2634"
DANGER_BG = "#FFF0F0"
DANGER_BORDER = "#FFCECE"
DANGER_HOVER = "#A81D29"

SUCCESS = "#0E8A3E"
SUCCESS_BG = "#E8FFEA"

# 字体（更紧凑）
FONT_TITLE = "13px"
FONT_GROUP = "12px"
FONT_BODY = "12px"
FONT_CAPTION = "11px"
FONT_MICRO = "10px"
FONT_TOOLBAR = "12px"
FONT_RIGHT_PANEL = "12px"

# 圆角
RADIUS = "8px"
RADIUS_SM = "6px"
RADIUS_XS = "4px"
RADIUS_PILL = "999px"

# 控件尺寸（更紧凑）
INPUT_HEIGHT = "28px"
BUTTON_HEIGHT = "28px"
INPUT_PADDING = "4px 9px"
BUTTON_PADDING = "5px 14px"


# ============================================================
# 应用级 QSS
# ============================================================

def build_app_stylesheet() -> str:
    return f"""
    /* ---- 全局基础 ---- */
    QWidget {{
        background-color: {BG_APP};
        color: {TEXT_PRIMARY};
        font-size: {FONT_BODY};
        font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    }}

    QLabel {{
        background: transparent;
        padding: 0;
    }}

    /* ---- 输入控件（增强选中可读性） ---- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_SM};
        padding: {INPUT_PADDING};
        min-height: {INPUT_HEIGHT};
        color: {TEXT_PRIMARY};
        selection-background-color: {ACCENT};
        selection-color: {TEXT_ON_ACCENT};
        font-weight: 500;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {BORDER_FOCUS};
        background: {BG_PRIMARY};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
        background: {BG_SECONDARY};
        color: {TEXT_DISABLED};
        border-color: {BORDER_SUBTLE};
    }}
    QLineEdit:hover:!disabled, QSpinBox:hover:!disabled, QDoubleSpinBox:hover:!disabled, QComboBox:hover:!disabled {{
        border-color: {ACCENT};
    }}

    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 3px;
        selection-background-color: {ACCENT_SUBTLE};
        selection-color: {TEXT_PRIMARY};
    }}

    /* ---- 默认按钮 ---- */
    QPushButton {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_SM};
        padding: {BUTTON_PADDING};
        min-height: {BUTTON_HEIGHT};
        color: {TEXT_PRIMARY};
        font-weight: 500;
    }}
    QPushButton:hover:!disabled {{
        background: {BG_SECONDARY};
        border-color: {BORDER_CONTROL};
    }}
    QPushButton:pressed {{
        background: {BG_TERTIARY};
        border-color: {BORDER_CONTROL};
    }}
    QPushButton:disabled {{
        background: {BG_SECONDARY};
        color: {TEXT_DISABLED};
        border-color: {BORDER_SUBTLE};
    }}

    /* ---- 列表 ---- */
    QListWidget {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        outline: none;
        padding: 2px;
    }}
    QListWidget::item {{
        padding: 5px 9px;
        min-height: 20px;
        border-radius: {RADIUS_XS};
        margin: 1px 2px;
    }}
    QListWidget::item:selected {{
        background: {ACCENT_SUBTLE};
        color: {TEXT_PRIMARY};
    }}
    QListWidget::item:hover:!selected {{
        background: {BG_SECONDARY};
    }}

    /* ---- 分组框（无边框版本，依靠间距分层） ---- */
    QGroupBox {{
        font-size: {FONT_GROUP};
        font-weight: 600;
        border: none;
        margin-top: 8px;
        padding-top: 14px;
        padding-bottom: 0px;
        color: {TEXT_PRIMARY};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 4px;
        padding: 0 4px;
        color: {TEXT_PRIMARY};
    }}

    /* ---- 顶部主工具栏 ---- */
    QToolBar {{
        background: {BG_TOOLBAR};
        border-bottom: 1px solid {BORDER_SUBTLE};
        spacing: 4px;
        padding: 4px 10px;
        font-size: {FONT_TOOLBAR};
    }}
    QToolBar QToolButton {{
        font-size: {FONT_TOOLBAR};
        padding: 4px 10px;
        min-height: 26px;
        border-radius: {RADIUS_SM};
        color: {TEXT_SECONDARY};
        border: 1px solid transparent;
    }}
    QToolBar QToolButton:hover {{
        background: {ACCENT_LIGHT_BG};
        color: {ACCENT};
    }}
    QToolBar QToolButton:pressed {{
        background: {ACCENT_SUBTLE};
    }}
    QToolBar QToolButton:disabled {{
        color: {TEXT_DISABLED};
    }}
    QToolBar::separator {{
        width: 1px;
        background: {BORDER_SUBTLE};
        margin: 6px 6px;
    }}

    /* ---- 状态栏 ---- */
    QStatusBar {{
        background: {BG_PRIMARY};
        border-top: 1px solid {BORDER_SUBTLE};
        color: {TEXT_TERTIARY};
        font-size: {FONT_BODY};
        padding: 1px 10px;
    }}
    QStatusBar::item {{ border: none; }}

    /* ---- 菜单 ---- */
    QMenuBar {{ background: {BG_PRIMARY}; border-bottom: 1px solid {BORDER_SUBTLE}; padding: 2px 4px; }}
    QMenuBar::item {{ padding: 4px 10px; border-radius: {RADIUS_SM}; color: {TEXT_SECONDARY}; }}
    QMenuBar::item:selected {{ background: {ACCENT_SUBTLE}; color: {ACCENT}; }}
    QMenu {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 4px 0;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        min-height: 24px;
        border-radius: {RADIUS_XS};
        margin: 1px 4px;
        color: {TEXT_PRIMARY};
    }}
    QMenu::item:selected {{ background: {ACCENT_SUBTLE}; color: {ACCENT}; }}
    QMenu::separator {{ height: 1px; background: {BORDER_SUBTLE}; margin: 4px 10px; }}

    /* ---- 滚动条 ---- */
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {BORDER_LIGHT}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {TEXT_TERTIARY}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {BORDER_LIGHT}; border-radius: 4px; min-width: 30px; }}
    QScrollBar::handle:horizontal:hover {{ background: {TEXT_TERTIARY}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QDialog {{ background: {BG_PRIMARY}; }}
    QDialogButtonBox QPushButton {{ min-width: 76px; }}
    QMessageBox {{ background: {BG_PRIMARY}; }}

    /* ---- 复选框 ---- */
    QCheckBox {{ spacing: 6px; color: {TEXT_PRIMARY}; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1.4px solid {BORDER_CONTROL};
        border-radius: 4px;
        background: {BG_PRIMARY};
    }}
    QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
    QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}

    /* ---- 分割器 ---- */
    QSplitter::handle {{ background: {BORDER_SUBTLE}; }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    /* ---- 选项卡 ---- */
    QTabWidget::pane {{
        border: none;
        background: transparent;
        top: -1px;
    }}
    QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
    QTabBar::tab {{
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 7px 14px;
        margin-right: 2px;
        color: {TEXT_TERTIARY};
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        border-bottom: 2px solid {ACCENT};
        color: {ACCENT};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{ color: {TEXT_SECONDARY}; }}

    /* ---- 进度条 ---- */
    QProgressBar {{
        background: {BG_TERTIARY};
        border: none;
        border-radius: 3px;
        height: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

    /* ---- 工具提示 ---- */
    QToolTip {{
        background: {TEXT_PRIMARY};
        color: {TEXT_ON_ACCENT};
        border: none;
        border-radius: {RADIUS_XS};
        padding: 4px 8px;
        font-size: {FONT_CAPTION};
    }}
    """


# ============================================================
# 组件级样式片段
# ============================================================

WORKFLOW_PANEL_STYLE = f"""
    QWidget#workflow_panel {{
        background: {BG_APP};
    }}
"""

RIGHT_PANEL_STYLE = f"""
    QWidget#right_panel {{
        background: {BG_APP};
        font-size: {FONT_RIGHT_PANEL};
    }}
    QWidget#right_panel QLabel {{
        font-size: {FONT_RIGHT_PANEL};
    }}
    QWidget#right_panel QGroupBox {{
        font-size: {FONT_GROUP};
    }}
"""

# 步骤卡片：默认 / 激活
CARD_DEFAULT_STYLE = f"""
    QFrame#step_card {{
        background: {BG_SECONDARY};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS};
    }}
    QFrame#step_card:hover {{
        border-color: {BORDER_CONTROL};
    }}
"""

CARD_ACTIVE_STYLE = f"""
    QFrame#step_card {{
        background: {ACCENT_LIGHT_BG};
        border: 1px solid {ACCENT};
        border-radius: {RADIUS};
    }}
"""

# 文字
SECTION_TITLE_STYLE = f"font-size: {FONT_TITLE}; font-weight: 700; color: {TEXT_PRIMARY}; letter-spacing: 0.3px;"
STEP_TITLE_STYLE = f"font-size: {FONT_GROUP}; font-weight: 600; color: {TEXT_PRIMARY};"
STEP_DESC_STYLE = f"font-size: {FONT_CAPTION}; color: {TEXT_TERTIARY};"
LABEL_STYLE = f"font-size: {FONT_MICRO}; font-weight: 700; color: {TEXT_TERTIARY}; letter-spacing: 0.6px;"
INFO_STYLE = f"font-size: {FONT_BODY}; color: {TEXT_SECONDARY};"
HINT_STYLE = f"font-size: {FONT_CAPTION}; color: {TEXT_TERTIARY};"

# 步骤序号徽章 — 圆形小球
def step_badge_style(active: bool = False) -> str:
    bg = ACCENT if active else BG_TERTIARY
    fg = TEXT_ON_ACCENT if active else TEXT_TERTIARY
    return f"""
        QLabel {{
            background: {bg};
            color: {fg};
            font-size: {FONT_CAPTION};
            font-weight: 700;
            border-radius: 9px;
            min-width: 18px; max-width: 18px;
            min-height: 18px; max-height: 18px;
            qproperty-alignment: AlignCenter;
        }}
    """

STEP_BADGE_DEFAULT_STYLE = step_badge_style(False)
STEP_BADGE_ACTIVE_STYLE = step_badge_style(True)

# 紧凑的步骤内动作按钮（带图标）
ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_SM};
        padding: 5px 8px;
        font-size: {FONT_BODY};
        color: {TEXT_SECONDARY};
        font-weight: 500;
        text-align: left;
        min-height: 26px;
    }}
    QPushButton:hover {{
        background: {ACCENT_LIGHT_BG};
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    QPushButton:pressed {{
        background: {ACCENT_SUBTLE};
        color: {ACCENT_ACTIVE};
        border-color: {ACCENT};
    }}
"""

# 主操作按钮（蓝色实心）
PRIMARY_BUTTON_STYLE = f"""
    QPushButton {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
        border-radius: {RADIUS_SM};
        padding: 5px 14px;
        font-size: {FONT_BODY};
        color: {TEXT_ON_ACCENT};
        font-weight: 600;
        min-height: 28px;
    }}
    QPushButton:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
    QPushButton:pressed {{ background: {ACCENT_ACTIVE}; border-color: {ACCENT_ACTIVE}; }}
    QPushButton:disabled {{ background: {BORDER_LIGHT}; border-color: {BORDER_LIGHT}; color: {TEXT_DISABLED}; }}
"""

# 危险按钮
DANGER_BUTTON_STYLE = f"""
    QPushButton {{
        background: {BG_PRIMARY};
        border: 1px solid {DANGER_BORDER};
        border-radius: {RADIUS_SM};
        padding: 5px 12px;
        font-size: {FONT_BODY};
        color: {DANGER};
        font-weight: 500;
        min-height: 26px;
    }}
    QPushButton:hover {{
        background: {DANGER_BG};
        border-color: {DANGER};
    }}
    QPushButton:pressed {{
        background: {DANGER};
        color: {TEXT_ON_ACCENT};
        border-color: {DANGER};
    }}
"""

# 历史按钮
HISTORY_BUTTON_STYLE = f"""
    QPushButton {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_LIGHT};
        border-radius: {RADIUS_SM};
        padding: 4px 10px;
        font-size: {FONT_BODY};
        color: {TEXT_SECONDARY};
        font-weight: 500;
        min-height: 26px;
    }}
    QPushButton:hover {{
        background: {ACCENT_LIGHT_BG};
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    QPushButton:pressed {{
        background: {ACCENT};
        color: {TEXT_ON_ACCENT};
    }}
"""

# 历史列表
HISTORY_LIST_STYLE = f"""
    QListWidget {{
        font-size: {FONT_BODY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        background: {BG_PRIMARY};
        padding: 2px;
    }}
    QListWidget::item {{
        padding: 4px 9px;
        min-height: 20px;
        border-radius: {RADIUS_XS};
        margin: 1px 2px;
        color: {TEXT_SECONDARY};
    }}
    QListWidget::item:selected {{
        background: {ACCENT_SUBTLE};
        color: {ACCENT};
        font-weight: 600;
    }}
    QListWidget::item:hover:!selected {{
        background: {BG_SECONDARY};
        color: {TEXT_PRIMARY};
    }}
"""

# 信息卡片（属性面板内的小型信息块）
INFO_CARD_STYLE = f"""
    QFrame#info_card {{
        background: {BG_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
    }}
"""

# 顶部品牌标题
BRAND_TITLE_STYLE = f"""
    font-size: 14px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.5px;
    padding: 0 6px;
"""

BRAND_BADGE_STYLE = f"""
    QLabel {{
        background: {ACCENT_LIGHT_BG};
        color: {ACCENT};
        font-size: 10px;
        font-weight: 700;
        border-radius: 4px;
        padding: 2px 6px;
    }}
"""
