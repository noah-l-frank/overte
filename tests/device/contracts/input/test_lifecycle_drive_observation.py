#!/usr/bin/env python3
"""Compile original passive serializer with explicit avatar/physics value seams."""
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
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    library_paths=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
glm=[]
if environment.get('OVERTE_HOST_GLM_INCLUDE'):glm=['-I'+str(Path(environment['OVERTE_HOST_GLM_INCLUDE']).resolve(strict=True))]
with tempfile.TemporaryDirectory(prefix='lifecycle-drive-') as directory:
    binary=Path(directory)/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),*glm,
        str(Path(__file__).with_name('lifecycle-drive-observation-test.cpp')),'-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    for arguments in ([],['--testScript']):subprocess.run([str(binary),*arguments],check=True,timeout=10,env=environment)
