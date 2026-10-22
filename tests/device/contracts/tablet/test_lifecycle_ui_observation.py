#!/usr/bin/env python3
"""Compile/passively inspect actual NativeCreate QML, excluding device/VR audio.

Uses the existing optional relocated Qt 5 root without installing dependencies.
Keyboard and TabletRoot hosting are explicit host boundaries; no device runs.
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
with tempfile.TemporaryDirectory(prefix='lifecycle-ui-') as directory:
    binary=Path(directory)/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
        str(Path(__file__).with_name('lifecycle-ui-observation-test.cpp')),'-o',str(binary),*library_paths,*flags],
        check=True,timeout=90,env=environment)
    subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),'--testScript',
        str(ROOT/'scripts/system/create/qml/NativeCreate.qml'),str(ROOT)],check=True,timeout=30,
        env={**environment,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
