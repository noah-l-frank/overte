#!/usr/bin/env python3
"""Execute the complete shared Graphics page/controls with native endpoints replaced.

Real Qt Quick handles layout and input. GPU/native Render/Performance/Settings
are explicit endpoints; native deferred capability is a separate compiled test.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
major=os.environ.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise RuntimeError('Qt major must be 5 or 6')
modules=['Qt'+major+part for part in ('QuickTest','Quick','Qml')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*modules],text=True))
tools=Path(subprocess.check_output(['pkg-config','--variable='+('host_bins' if major=='5' else 'libexecdir'),'Qt'+major+'Core'],text=True).strip())
with tempfile.TemporaryDirectory(prefix='overte-graphics-settings-qml-') as temporary:
 stage=Path(temporary)
 shutil.copytree(ROOT/'scripts/system/settings/qml',stage/'production')
 shutil.copy2(HERE/'tst_graphics_settings.qml',stage)
 subprocess.run([str(tools/'moc'),str(HERE/'graphics-settings-services.cpp'),'-o',str(stage/'graphics-settings-services.moc')],check=True,timeout=30)
 binary=stage/'qml-test'
 libdir=subprocess.check_output(['pkg-config','--variable=libdir','Qt'+major+'Core'],text=True).strip()
 subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG',str(HERE/'graphics-settings-services.cpp'),'-I'+str(stage),'-L'+libdir,'-o',str(binary),*flags],check=True,timeout=60)
 subprocess.run([str(binary),'-input',str(stage/'tst_graphics_settings.qml'),'-import',str(ROOT/'interface/resources/qml'),'-import',str(ROOT/'tests/device/qml/imports')],env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'},check=True,timeout=30)
