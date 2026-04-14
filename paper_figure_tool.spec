# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from importlib.util import find_spec
from PyInstaller.utils.hooks import collect_all

# 兼容 __file__ 不存在
if "SPECPATH" in globals():
    project_dir = Path(SPECPATH).resolve()
elif "__file__" in globals():
    project_dir = Path(__file__).resolve().parent
else:
    project_dir = Path.cwd().resolve()

datas = []
binaries = []
hiddenimports = [
    "PIL.ImageQt",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

def add_package(pkg_name, required=False):
    if find_spec(pkg_name) is None:
        if required:
            raise SystemExit(
                f"[打包失败] 当前环境找不到必须依赖: {pkg_name}\n"
                f"请先安装后重试，例如：python -m pip install {pkg_name}"
            )
        print(f"[spec] 可选依赖未安装，跳过: {pkg_name}")
        return

    d, b, h = collect_all(pkg_name)
    datas.extend(d)
    binaries.extend(b)
    hiddenimports.extend(h)

# 必须依赖（没有就直接终止，避免生成“能打包但运行报错”的 exe）
add_package("PySide6", required=True)
add_package("shiboken6", required=True)

# 可选依赖（用于 PDF/SVG 导出）
add_package("reportlab", required=False)
add_package("svgwrite", required=False)

# 可选资源目录
assets_dir = project_dir / "assets"
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

# 可选图标
icon_file = assets_dir / "app.ico"
icon_path = str(icon_file) if icon_file.exists() else None

# 去重
hiddenimports = list(dict.fromkeys(hiddenimports))

a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="paper_figure_tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="paper_figure_tool",
)