# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Nemori Backend
Bundles the FastAPI backend into a single executable
"""

block_cipher = None

# Essential hidden imports for the backend
hiddenimports = [
    # Uvicorn
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
    # Web
    'httptools',
    'websockets',
    'email_validator',
    # Pydantic
    'pydantic',
    'pydantic_settings',
    'pydantic_core',
    # FastAPI/Starlette
    'fastapi',
    'starlette',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    # Async
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
    # HTTP
    'httpx',
    'httpcore',
    # OpenAI
    'openai',
    # LangChain - minimal
    'langchain',
    'langchain.tools',
    'langchain_core',
    'langchain_core.tools',
    'langchain_core.messages',
    'langchain_openai',
    'langgraph',
    'langgraph.prebuilt',
    # ChromaDB
    'chromadb',
    'chromadb.config',
    # Image processing
    'PIL',
    'PIL.Image',
    'imagehash',
    'mss',
    # Utils
    'aiofiles',
    'sqlite3',
    'multipart',
    'python_multipart',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
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
        'IPython',
        'jupyter',
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
