
# pyinstaller --noconsole --onefile launcher.py
# It will bundle the launcher; include app_streamlit.py as data.

# This is a minimal spec template. You can also run the CLI as above without the spec file.

# To use this spec:
#   pyinstaller launcher.spec
# Make sure app_streamlit.py is in the same folder.

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('app_streamlit.py', '.'),],
    hiddenimports=['playwright', 'playwright.sync_api', 'pandas', 'bs4', 'openpyxl', 'streamlit'],
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
    name='LastUpdatedExtractor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # set True for troubleshooting
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

