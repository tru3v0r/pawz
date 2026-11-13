# -*- mode: python ; coding: utf-8 -*-
# Only what pawz uses is shipped: Qt Core/Gui/Widgets/Svg and the SDL part of
# pygame that reads controllers. The startup smoke test (scripts/test-build-windows.ps1)
# catches a library removed by mistake.
import re
from pathlib import PurePath

datas = [('src/pawz/ui/assets', 'pawz/ui/assets'), ('src/pawz/data', 'pawz/data')]
hiddenimports = ['comtypes.client', 'comtypes.gen.UIAutomationClient', 'pygame._sdl2.controller']
excludes = [
    'tkinter', '_tkinter', 'pygame.examples', 'pygame.tests', 'pygame.docs',
    'pygame.mixer', 'pygame.mixer_music', 'pygame.font', 'pygame.ftfont', 'pygame.freetype',
    'pygame.midi', 'pygame.camera', 'pygame.sndarray', 'pygame.surfarray',
    'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtPdf',
    'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'numpy', 'setuptools', 'pip', '_ssl', 'ssl',
]
# Languages the interface targets: Qt's own translations of standard dialogs are kept.
QT_LANGUAGES = ('ar', 'de', 'es', 'fr', 'id', 'ja', 'ko', 'pt', 'ru', 'vi', 'zh_CN')
UNUSED_FILES = re.compile(
    r'(opengl32sw|d3dcompiler_\d+|qt6(quick|qml|pdf|opengl|network|virtualkeyboard)\w*'
    r'|sdl2_(mixer|ttf|image)|freetype|libjpeg|libmodplug|libogg|libopus\w*|libpng\d*'
    r'|libtiff|libwebp|portmidi|libcrypto|libssl)[-\d]*\.(dll|pyd)$', re.IGNORECASE)
KEPT_PLUGINS = {'platforms/qwindows.dll', 'imageformats/qsvg.dll', 'iconengines/qsvgicon.dll',
                'styles/qmodernwindowsstyle.dll'}


def wanted(destination):
    path = PurePath(destination.replace('\\', '/'))
    parts = path.parts
    if UNUSED_FILES.search(path.name):
        return False
    if 'plugins' in parts and parts[:1] == ('PySide6',):
        return '/'.join(parts[parts.index('plugins') + 1:]) in KEPT_PLUGINS
    if 'translations' in parts and parts[:1] == ('PySide6',):
        match = re.fullmatch(r'qtbase_(\w+)\.qm', path.name)
        return bool(match) and match.group(1).startswith(QT_LANGUAGES)
    return True


a = Analysis(
    ['src/pawz/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
a.binaries = [entry for entry in a.binaries if wanted(entry[0])]
a.datas = [entry for entry in a.datas if wanted(entry[0])]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pawz',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src/pawz/ui/assets/logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pawz',
)
