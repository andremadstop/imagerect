import platform
from pathlib import Path

APP_VERSION = "0.2.0"
block_cipher = None
root = Path(SPECPATH)
icon_path = None
if platform.system() == "Windows":
    icon_path = "assets/icon.ico"
elif platform.system() == "Darwin":
    icon_path = "assets/icon.icns"

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=[],
    datas=[
        ("assets/icon.png", "assets"),
        ("tests/sample_data/synthetic_reference.dxf", "tests/sample_data"),
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtOpenGL",
        "cv2",
        "numpy",
        "ezdxf",
        "trimesh",
        "pye57",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ImageRect",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
)
