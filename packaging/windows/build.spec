# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Media Downloader

import os
import sys

block_cipher = None

# Paths
project_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
backend_dir = os.path.join(project_root, 'backend')
frontend_dir = os.path.join(project_root, 'frontend')

a = Analysis(
    [os.path.join(SPECPATH, 'app_entry.py')],
    pathex=[backend_dir],
    binaries=[],
    datas=[
        (os.path.join(backend_dir, 'app'), 'app'),
        (frontend_dir, 'frontend'),
    ],
    hiddenimports=[
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
        'app.parsers.douyin',
        'app.parsers.bilibili',
        'app.parsers.xiaohongshu',
        'app.parsers.kuaishou',
        'app.parsers.tiktok',
        'app.parsers.instagram',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MediaDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)
