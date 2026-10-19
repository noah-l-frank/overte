#!/usr/bin/env python3
"""Actual Snapshot popup/field input through the composed Phone accessibility API."""
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class PhoneSnapshotNativeInput(unittest.TestCase):
    def test_qt5_actual_popup_choices_are_reachable_from_the_owned_native_tree(self):
        self.run_sdk('5')

    def test_qt6_actual_popup_choices_are_reachable_from_the_owned_native_tree(self):
        self.run_sdk('6')

    def run_sdk(self, major):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        sysroot = os.environ.get('OVERTE_TEST_QT5_SYSROOT') if major == '5' else None
        if sysroot:
            sysroot = Path(sysroot)
            env.update(PKG_CONFIG_LIBDIR=str(sysroot / 'usr/lib64/pkgconfig'),
                PKG_CONFIG_SYSROOT_DIR=str(sysroot), LD_LIBRARY_PATH=str(sysroot / 'usr/lib64'),
                LIBRARY_PATH=str(sysroot / 'usr/lib64'), QML2_IMPORT_PATH=str(sysroot / 'usr/lib64/qt5/qml'),
                QT_PLUGIN_PATH=str(sysroot / 'usr/lib64/qt5/plugins'))
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
            *(f'Qt{major}{name}' for name in ('Core', 'Gui', 'Qml', 'Quick', 'Test'))], env=env, text=True))
        with tempfile.TemporaryDirectory(prefix='phone-snapshot-native-ui-') as temporary:
            stage = Path(temporary)
            production = stage / 'production'
            shutil.copytree(ROOT / 'scripts/system/snapshot', production)
            page = production / 'NativeSnapshotReview.qml'
            page.chmod(0o644)
            page.write_text('import TestSnapshot 1.0\n' + page.read_text())
            shutil.copytree(ROOT / 'interface/resources/qml/controls', stage / 'controls')
            boundary = stage / 'TestSnapshot'; boundary.mkdir()
            (boundary / 'qmldir').write_text('module TestSnapshot\nsingleton Snapshot 1.0 Snapshot.qml\n')
            (boundary / 'Snapshot.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject {'
                ' property string format: "png"; function getAvailableSnapshotFormats(){return ["png","jpg","webp"]}'
                ' function getSnapshotFormat(){return format} function setSnapshotFormat(value){format=value}'
                ' function snapshotFileUrl(path){return ""} }\n')
            (stage / 'ReviewHost.qml').write_text('import QtQuick 2.7\nimport "production"\n'
                'Item {width:480; height:900; NativeSnapshotReview {anchors.fill:parent} }\n')
            driver = Path(__file__).with_suffix('.cpp')
            binary = stage / 'test'
            ui = ROOT / 'libraries/ui/src/ui'
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-I', str(ui), str(driver),
                            str(ui / 'PhoneAccessibilityTree.cpp'), '-o', str(binary), *flags],
                           env=env, check=True, timeout=45)
            subprocess.run(['unshare', '--user', '--map-root-user', '--net', str(binary), str(stage)],
                           env=env, check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
