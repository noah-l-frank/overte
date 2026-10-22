#!/usr/bin/env python3
"""Compile original accepted-request/status/cancel bodies and weak native leases.

Renderer/platform/secondary camera are explicit host boundaries. This runs no
SDK, graphics runtime, physical headset, product build or external service.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent

def body(source,marker):
    start=source.index(marker);opening=source.index('{',start);depth=1;end=opening+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'

environment=dict(os.environ);library=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'))
    library=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
    *('Qt'+major+name for name in ('Core','Gui'))],text=True,env=environment))
variable='host_bins' if major=='5' else 'libexecdir'
moc=Path(subprocess.check_output(['pkg-config','--variable='+variable,'Qt'+major+'Core'],text=True,env=environment).strip())/'moc'
if not moc.is_file() and environment.get('PKG_CONFIG_SYSROOT_DIR'):
    moc=Path(environment['PKG_CONFIG_SYSROOT_DIR'])/str(moc).lstrip('/')
source=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
getter=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
with tempfile.TemporaryDirectory(prefix='snapshot-originals-') as directory:
    stage=Path(directory)
    (stage/'original-snapshot.inc').write_text(''.join(body(source,marker) for marker in (
        'SnapshotCapture Snapshot::beginCapture(', 'void Snapshot::captureStatus(',
        'void Snapshot::cancelCapture(', 'QVariantMap Snapshot::featureSnapshotCaptureOriginals(',
        'QVariantMap Snapshot::featureSnapshotScriptOriginals(')))
    (stage/'original-snapshot-getter.inc').write_text(body(getter,'QVariantMap TestScriptingInterface::featureSnapshotCaptureOriginals(')
        +body(getter,'QVariantMap TestScriptingInterface::featureSnapshotScriptOriginals('))
    subprocess.run([str(moc),str(HERE/'snapshot-originals-test.cpp'),'-o',str(stage/'snapshot-originals-test.moc')],check=True,timeout=30,env=environment)
    runtime=stage/'runtime';runtime.mkdir(mode=0o700)
    environment.update(QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(runtime))
    for pico in (True,False):
        executable=stage/('snapshot-originals-pico' if pico else 'snapshot-originals-other')
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',
            *(['-DANDROID_APP_PICO_INTERFACE'] if pico else []),'-I'+str(ROOT),'-I'+str(stage),
            str(HERE/'snapshot-originals-test.cpp'),'-o',str(executable),*library,*flags],check=True,timeout=60,env=environment)
        for arguments in ([],['--testScript']):subprocess.run([str(executable),*arguments],check=True,timeout=15,env=environment)
print('PASS: original Snapshot callbacks, cancelled queue and weak native request retirement (Qt'+major+')')
