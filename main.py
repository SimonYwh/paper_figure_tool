from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def _qt_message_handler(mode: QtMsgType, _context, message: str):
    low = message.lower()

    # 1) PNG 色彩配置警告（不影响结果）
    if "libpng warning: iccp" in low or "chrm chunk does not match srgb" in low:
        return

    # 2) DirectWrite + Terminal 字体警告（不影响结果）
    if "directwrite: createfontfacefromhdc() failed" in low:
        return
    if 'qfontdef(family="terminal"' in low:
        return

    prefix = {
        QtMsgType.QtDebugMsg: "[QtDebug]",
        QtMsgType.QtInfoMsg: "[QtInfo]",
        QtMsgType.QtWarningMsg: "[QtWarning]",
        QtMsgType.QtCriticalMsg: "[QtCritical]",
        QtMsgType.QtFatalMsg: "[QtFatal]",
    }.get(mode, "[Qt]")

    sys.__stderr__.write(f"{prefix} {message}\n")


def main() -> int:
    # 高分屏（可选，但建议保留）
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    qInstallMessageHandler(_qt_message_handler)

    # Terminal 字体替代，减少 DirectWrite 告警概率
    try:
        QFont.insertSubstitution("Terminal", "Consolas")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("论文组图排版器")
    app.setFont(QFont("Microsoft YaHei UI", 10))

    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())