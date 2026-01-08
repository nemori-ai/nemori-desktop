# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Nemori Backend
Bundles the FastAPI backend into a single executable
"""

import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect all submodules for packages that need it
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'httptools',
    'websockets',
    'watchfiles',
    'email_validator',
    'pydantic',
    'pydantic_settings',
    'fastapi',
    'starlette',
    'anyio',
    'sniffio',
    'httpx',
    'httpcore',
    'openai',
    'langchain',
    'langchain_core',
    'langchain_openai',
    'langgraph',
    'chromadb',
    'PIL',
    'imagehash',
    'mss',
    'aiofiles',
    'sqlite3',
]

# Add langchain submodules
hiddenimports += collect_submodules('langchain')
hiddenimports += collect_submodules('langchain_core')
hiddenimports += collect_submodules('langchain_openai')
hiddenimports += collect_submodules('langgraph')
hiddenimports += collect_submodules('chromadb')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('pydantic_core')

# Collect data files
datas = []
chromadb_datas, chromadb_binaries, chromadb_hiddenimports = collect_all('chromadb')
datas += chromadb_datas
hiddenimports += chromadb_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=chromadb_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy.testing',
        'pytest',
        'black',
        'isort',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nemori-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
