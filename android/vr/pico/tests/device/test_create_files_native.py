"""Compile the isolated Create storage role; no application, target or service."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class CreateFilesNativeTests(unittest.TestCase):
    def test_original_input_export_readback_and_authenticated_resource_release(self):
        major = os.environ.get('OVERTE_NATIVE_QT_MAJOR', '6')
        self.assertIn(major, ('5', '6'))
        environment = dict(os.environ)
        library_paths = []
        if major == '5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix = Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),
                PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            library_paths = ['-L'+str(prefix/'usr/lib64')]
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt'+major+'Core'], text=True, env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-create-original-files-') as directory:
            binary = Path(directory)/'create-files-test'
            source=(HERE.parents[4]/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
            start=source.index('QVariantMap TestScriptingInterface::featureCreateFiles(')
            end=source.index('\n}\n',start)+3
            (Path(directory)/'CreateFilesMethod.inc').write_text(source[start:end])
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-DOVERTE_E2E_FEATURE_TESTS',
                '-I'+str(HERE.parents[4]/'tests/device/native'),
                '-I'+directory,
                str(HERE/'create-files-native.cpp'), '-o', str(binary), *library_paths, *flags],
                check=True, timeout=90, env=environment)
            subprocess.run([str(binary),'--testScript'], check=True, timeout=15, env=environment)


if __name__ == '__main__': unittest.main()
