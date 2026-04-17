from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    ["cli/main.py"],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "click",
        "typer",
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
    name="ImageRect-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
