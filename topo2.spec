# -*- mode: python ; coding: utf-8 -*-

from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

# Different builds never overwrite the runtime used by an existing executable.
root = Path(SPECPATH)
digest = sha256((root / 'uv.lock').read_bytes())
for source in sorted((root / 'src' / 'topo_v2').glob('*.py')):
    digest.update(source.name.encode())
    digest.update(source.read_bytes())
runtime = '_topo2_runtime_' + version('topo-context-engine') + '_' + digest.hexdigest()[:12]


a = Analysis(
    ['src/topo_v2/__main__.py'],
    pathex=[],
    binaries=[],
    datas=copy_metadata('topo-context-engine'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='topo2',
    exclude_binaries=True,
    contents_directory=runtime,
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


bundle = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='topo2',
)
