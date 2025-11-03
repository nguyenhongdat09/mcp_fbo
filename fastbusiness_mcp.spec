# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec file for FastBusiness MCP Server
Build standalone executable that doesn't expose source code
"""

block_cipher = None

# Collect all data files that need to be included
datas = [
    ('knowledge_base', 'knowledge_base'),  # YAML knowledge base files
    ('data', 'data'),                      # LMDB database files
    ('config.yaml', '.'),                  # Config file
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # MCP dependencies
    'mcp',
    'mcp.server',
    'mcp.server.stdio',
    'mcp.types',

    # Standard libraries used
    'yaml',
    'lmdb',
    're',
    'pathlib',
    'logging',
    'asyncio',
    'json',
    'tempfile',
    'shutil',

    # Our modules
    'fastbusiness_mcp',
    'fastbusiness_mcp.server',
    'fastbusiness_mcp.tools',
    'fastbusiness_mcp.tools.generate_field_from_lmdb',
    'fastbusiness_mcp.tools.generate_sql_for_fields',
    'fastbusiness_mcp.tools.code_assistant_tool',
    'fastbusiness_mcp.tools.xml_handler_tool',
    'fastbusiness_mcp.knowledge_base',
    'fastbusiness_mcp.knowledge_base.engine',
    'fastbusiness_mcp.knowledge_base.context_detector',
    'fastbusiness_mcp.knowledge_base.code_generator',
    'fastbusiness_mcp.utils',
    'fastbusiness_mcp.utils.logger',
    'fastbusiness_mcp.utils.file_utils',
]

# Analysis - collect all files and dependencies
a = Analysis(
    ['fastbusiness_mcp/server.py'],  # Entry point
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ - Python ZIP archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE - Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fastbusiness_mcp',
    debug=False,                      # Set to True for debugging
    bootloader_ignore_signals=False,
    strip=False,                      # Strip symbols (set True to reduce size)
    upx=True,                        # Compress with UPX (set False if you don't have UPX)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,                     # Console app - REQUIRED for MCP stdio protocol
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                        # Add 'icon.ico' if you have an icon
)
