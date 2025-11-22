# -*- mode: python -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules

app_name = "AiSphere"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Inclure dossiers et fichiers nécessaires
datas = [
    (os.path.join("frontend", "assets"), "assets"),  # tous les assets
    (os.path.join("models"), "models"),              # modèle GGUF
]

# Modules cachés
hiddenimports = collect_submodules("llama_cpp") + collect_submodules("PyQt6") + collect_submodules("app")

entry_script = os.path.join("app", "gui.py")

block_cipher = None

a = Analysis(
    [entry_script],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=app_name,
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

app = BUNDLE(
    exe,
    name=f"{app_name}.app",
    icon=os.path.join("frontend", "assets", "app.icns"),
)

