#!/usr/bin/env python3
"""Actual iOS-owned Qt input core; no UIKit stubs or installed-code claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NormalInput(unittest.TestCase):
    def test_actual_dual_root_pointer_and_editor_events(self):
        major = os.environ.get('OVERTE_NATIVE_QT_MAJOR', '6')
        if major not in {'5', '6'}:
            raise ValueError('OVERTE_NATIVE_QT_MAJOR must be 5 or 6')
        environment, libraries = dict(os.environ), []
        if major == '5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            sdk = Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(sdk),
                PKG_CONFIG_LIBDIR=str(sdk / 'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(sdk / 'usr/lib64'),
                QT_PLUGIN_PATH=str(sdk / 'usr/lib64/qt5/plugins'),
                QML2_IMPORT_PATH=str(sdk / 'usr/lib64/qt5/qml'),
                QML_IMPORT_PATH=str(sdk / 'usr/lib64/qt5/qml'))
            libraries = ['-L' + str(sdk / 'usr/lib64')]
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
            *['Qt' + major + name for name in ('Core', 'Gui', 'Qml', 'Quick', 'Test')]],
            env=environment, text=True))
        with tempfile.TemporaryDirectory(prefix='ios-normal-input-') as directory:
            binary = Path(directory) / 'test'
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-UNDEBUG', '-pthread',
                '-I' + str(ROOT / 'ios/ui'), '-I' + str(ROOT / 'libraries/ui/src'),
                str(ROOT / 'ios/ui/IOSNormalUiInput.cpp'),
                str(ROOT / 'libraries/ui/src/ui/NativeFieldInput.cpp'),
                str(Path(__file__).with_suffix('.cpp')), '-o', str(binary), *libraries, *flags],
                check=True, timeout=60, env=environment)
            runner = environment.get('OVERTE_HOST_TEST_NETWORK_RUNNER')
            isolation = [runner] if runner else ['unshare', '--user', '--map-root-user', '--net']
            # The hosted launcher's sudo boundary resets its environment.
            runtime = {name: environment[name] for name in (
                'LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QML_IMPORT_PATH')
                if name in environment}
            runtime.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                QT_FORCE_STDERR_LOGGING='1')
            subprocess.run([*isolation, 'env',
                *[name + '=' + value for name, value in runtime.items()], str(binary)],
                check=True, timeout=30, env=environment)


if __name__ == '__main__':
    unittest.main(verbosity=2)
