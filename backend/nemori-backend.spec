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
    'chromadb.api',
    'chromadb.api.client',
    'chromadb.api.rust',
    'chromadb.api.shared_system_client',
    'chromadb.telemetry',
    'chromadb.telemetry.product',
    'chromadb.telemetry.product.posthog',
    'chromadb.db',
    'chromadb.db.impl',
    'chromadb.db.impl.sqlite',
    'chromadb.segment',
    'chromadb.segment.impl',
    'chromadb.segment.impl.manager',
    'chromadb.segment.impl.manager.local',
    'chromadb.segment.impl.metadata',
    'chromadb.segment.impl.metadata.sqlite',
    'chromadb.segment.impl.vector',
    'chromadb.segment.impl.vector.local_hnsw',
    'chromadb.quota',
    'chromadb.quota.simple_quota_enforcer',
    'chromadb.rate_limit',
    'chromadb.rate_limit.simple_rate_limit',
    'posthog',
    'onnxruntime',
    # Image processing
    'PIL',
    'PIL.Image',
    'imagehash',
    'mss',
    # Utils
    'aiofiles',
    'aiosqlite',
    'sqlite3',
    'multipart',
    'python_multipart',
    # Additional dependencies
    'hnswlib',
    '_ssl',
    '_hashlib',
    # Tokenization (OpenAI/LangChain)
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    # Retry/resilience
    'tenacity',
    # Numeric/scientific
    'numpy',
    'scipy',
    'scipy.spatial',
    # Environment
    'dotenv',
    'python_dotenv',
    # SSL/Network
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    # Typing
    'typing_extensions',
    # JSON
    'orjson',
    # LangChain additional
    'langchain.schema',
    'langchain_core.runnables',
    'langchain_core.outputs',
    'langchain_core.callbacks',
    'langchain_core.language_models',
    'langgraph.graph',
    'langgraph.checkpoint',
    # UUID
    'uuid',
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
    [],
    exclude_binaries=True,
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nemori-backend',
)
