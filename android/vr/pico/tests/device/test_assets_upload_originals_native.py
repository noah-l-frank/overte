"""Compile the passive original upload collector; no server or actual upload."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
class AssetsUploadOriginalsNativeTests(unittest.TestCase):
    def test_every_call_and_actual_qobject_connection_capture_retirement(self):
        environment=dict(os.environ);prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-assets-upload-originals-') as directory:
            binary=Path(directory)/'test'
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
                '-I'+str(HERE.parents[4]/'tests/device/native'),str(HERE/'assets-upload-originals-native.cpp'),'-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],check=True,timeout=90,env=environment)
            for gate in ([],['--testScript']):subprocess.run([str(binary),*gate],check=True,timeout=5,env=environment)
if __name__=='__main__':unittest.main()
