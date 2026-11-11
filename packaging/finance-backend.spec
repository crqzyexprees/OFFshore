# PyInstaller spec: bundles the Python backend into build/sidecar/finance-backend/
# (one-folder mode — starts instantly, unlike one-file which unpacks on every launch).
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = os.path.dirname(SPECPATH)

a = Analysis(
    [os.path.join(SPECPATH, "sidecar_entry.py")],
    pathex=[root],
    datas=[
        # Read at runtime via backend.config.MODEL_DIR (bundle-relative).
        (os.path.join(root, "backend", "models"), "backend/models"),
        *collect_data_files("pdfminer"),
    ],
    # uvicorn picks its loop/protocol implementations by import string.
    hiddenimports=[*collect_submodules("uvicorn"), "backend.api"],
    # uvicorn's optional extras (uvloop, httptools, ...) aren't needed for a local
    # app; exclude them so they're never bundled even if installed.
    excludes=["tkinter", "uvloop", "httptools", "websockets", "watchfiles", "yaml", "dotenv"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="finance-backend",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="finance-backend", upx=False)
