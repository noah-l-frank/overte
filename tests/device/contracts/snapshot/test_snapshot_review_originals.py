#!/usr/bin/env python3
"""Original Review QML/context source on a real host QQuickWindow; no device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.snapshot_review import validate

environment=dict(os.environ);library=[];major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
        QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
    library=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
    *('Qt'+major+name for name in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
variable='host_bins' if major=='5' else 'libexecdir'
moc=Path(subprocess.check_output(['pkg-config','--variable='+variable,'Qt'+major+'Core'],text=True,env=environment).strip())/'moc'
if not moc.is_file() and environment.get('PKG_CONFIG_SYSROOT_DIR'):
    moc=Path(environment['PKG_CONFIG_SYSROOT_DIR'])/str(moc).lstrip('/')
with tempfile.TemporaryDirectory(prefix='snapshot-review-originals-') as directory:
    stage=Path(directory);runtime=stage/'runtime';runtime.mkdir(mode=0o700)
    source=Path(__file__).with_name('snapshot-review-originals-test.cpp')
    subprocess.run([str(moc),str(source),'-o',str(stage/'snapshot-review-originals-test.moc')],check=True,timeout=30,env=environment)
    executable=stage/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',
        '-I'+str(ROOT),'-I'+str(stage),str(source),'-o',str(executable),*library,*flags],check=True,timeout=60,env=environment)
    environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime))
    for options in ([],['--testScript']):
        result=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(executable),
            str(ROOT/'scripts/system/snapshot/NativeSnapshotReview.qml'),str(ROOT),*options],text=True,timeout=20,env=environment)
        if options:
            value=json.loads(result);validate(value)
            assert value['present'] and not value['review']['visible'] and value['review']['capturing']
print('PASS: actual Snapshot Review QML, pointer and original hidden/context source (Qt'+major+')')
