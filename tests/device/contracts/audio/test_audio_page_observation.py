#!/usr/bin/env python3
"""Run the actual Audio.qml page and weak observer; no native audio/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import sys
from pathlib import Path
import shlex
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library_paths=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'),
        QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
    library_paths=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*('Qt'+major+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
with tempfile.TemporaryDirectory(prefix='audio-page-') as directory:
    private=Path(directory);private.chmod(0o700)
    # Only original native tablet sounds are replaced. Audio.qml and its
    # original controls/styles and completion/destruction bodies are unchanged.
    tablet=private/'TabletScriptingInterface';tablet.mkdir()
    (tablet/'qmldir').write_text('module TabletScriptingInterface\nsingleton Tablet 1.0 Tablet.qml\nsingleton TabletEnums 1.0 TabletEnums.qml\n')
    (tablet/'Tablet.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject { function playSound(value) {} }\n')
    (tablet/'TabletEnums.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject { enum Sound { ButtonHover, ButtonClick } }\n')
    binary=private/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),str(Path(__file__).with_name('audio-page-observation-test.cpp')),
        '-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    for peak in ('false','true'):
        raw=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(binary),'--testScript',str(ROOT),str(private),peak,'explicit-native-audio-boundary'],
            text=True,timeout=30,env={**environment,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
        sys.path.insert(0,str(ROOT/'tests/device'))
        from adapters.pico4.audio_pages import validate,accept
        previous=None
        for line in raw.splitlines():
            packet=json.loads(line);validate(packet,packet['capturedEpochMs']);previous=accept(previous,packet)
        assert previous is not None
