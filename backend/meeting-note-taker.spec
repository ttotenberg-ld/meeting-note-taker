# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Meeting Note-Taker backend
# Build with: pyinstaller meeting-note-taker.spec
# Produces a single directory with the backend binary.

import sys
from pathlib import Path

block_cipher = None
backend_dir = Path(SPECPATH)

a = Analysis(
    [str(backend_dir / "main.py")],
    pathex=[str(backend_dir)],
    binaries=[
        # Bundle the AudioTee binary for system audio capture
        (str(backend_dir / "bin" / "audiotee"), "bin"),
    ],
    datas=[],
    hiddenimports=[
        # FastAPI / Uvicorn
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # FastAPI internals
        "fastapi",
        "starlette",
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.cors",
        "anyio._backends._asyncio",
        "multipart",
        "python_multipart",
        # App routers & services
        "routers.recording",
        "routers.calendar",
        "routers.notes",
        "routers.settings",
        "services.audio_capture",
        "services.transcription",
        "services.note_formatter",
        "services.drive_service",
        "services.google_auth",
        "models.schemas",
        # Google APIs
        "google.genai",
        "google.auth",
        "google.oauth2",
        "google.oauth2.credentials",
        "google_auth_oauthlib",
        "google_auth_oauthlib.flow",
        "googleapiclient",
        "googleapiclient.discovery",
        "googleapiclient.http",
        "googleapiclient._helpers",
        "httplib2",
        # Audio
        "pyaudio",
        "numpy",
        # Misc
        "dotenv",
        "pydantic",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="meeting-note-taker-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    target_arch="universal2",  # Apple Silicon + Intel
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="meeting-note-taker-backend",
)
