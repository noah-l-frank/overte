#!/usr/bin/env python3
"""Compile original normal field controls and NativeFieldInput with real Qt.

Native PathUtils configuration and the visible window are explicit host
boundaries. Actual NativeCreate.qml and native IME dispatch remain original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
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
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
        QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
    library_paths=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
    *('Qt'+major+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
with tempfile.TemporaryDirectory(prefix='lifecycle-controls-') as directory:
    stage=Path(directory);binary=stage/'test'
    (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
        'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
        'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
        '-I'+str(ROOT/'libraries/ui/src'),str(Path(__file__).with_name('lifecycle-controls-test.cpp')),
        str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(binary),*library_paths,*flags],
        check=True,timeout=90,env=environment)
    for arguments in ([],['--testScript']):
        subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),*arguments,str(ROOT)],check=True,timeout=30,
            env={**environment,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
    print('PASS Qt'+major+': actual NativeCreate normal field/IME/Unicode and weak source tokens; runtime gate checked; no device or complete Pico translation-unit claim')
