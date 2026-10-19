#!/usr/bin/env python3
"""Actual nested iOS Snapshot UI through the composed native input API."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SnapshotInput(unittest.TestCase):
    def test_actual_nested_snapshot_pointer_field_and_popup_ownership(self):
        major = os.environ.get('OVERTE_NATIVE_QT_MAJOR', '6')
        if major not in ('5', '6'):
            raise ValueError('Select Qt5 or Qt6')
        env, libraries = dict(os.environ), []
        if major == '5' and env.get('OVERTE_QT5_HOST_ROOT'):
            sdk = Path(env['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            env.update(PKG_CONFIG_SYSROOT_DIR=str(sdk), PKG_CONFIG_LIBDIR=str(sdk / 'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(sdk / 'usr/lib64'), QT_PLUGIN_PATH=str(sdk / 'usr/lib64/qt5/plugins'),
                QML2_IMPORT_PATH=str(sdk / 'usr/lib64/qt5/qml'), QML_IMPORT_PATH=str(sdk / 'usr/lib64/qt5/qml'))
            libraries = ['-L' + str(sdk / 'usr/lib64')]
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
            *['Qt' + major + name for name in ('Core', 'Gui', 'Qml', 'Quick', 'Test')]], env=env, text=True))
        with tempfile.TemporaryDirectory(prefix='ios-snapshot-input-') as temporary:
            stage = Path(temporary)
            production = stage / 'production'
            shutil.copytree(ROOT / 'scripts/system/snapshot', production)
            page = production / 'NativeSnapshotReview.qml'; page.chmod(0o644)
            page.write_text('import TestSnapshot 1.0\n' + page.read_text())
            shutil.copytree(ROOT / 'interface/resources/qml/controls', stage / 'controls')
            boundary = stage / 'TestSnapshot'; boundary.mkdir()
            (boundary / 'qmldir').write_text('module TestSnapshot\nsingleton Snapshot 1.0 Snapshot.qml\n')
            (boundary / 'Snapshot.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject {'
                ' property string format:"png"; function getAvailableSnapshotFormats(){return ["png","jpg","webp"]}'
                ' function getSnapshotFormat(){return format} function setSnapshotFormat(value){format=value}'
                ' function snapshotFileUrl(path){return ""} }\n')
            (stage / 'ReviewHost.qml').write_text('''import QtQuick 2.7
import QtQuick.Controls 2.3
import "production"
Item { width:480; height:900
    Item { objectName:"nestedTablet"; x:12; y:20; width:456; height:820
        NativeSnapshotReview {anchors.fill:parent}
    }
    TextField {objectName:"PhoneAddressField"; x:0; y:860; width:120; height:40; visible:false}
    ComboBox {id:foreign; objectName:"foreignCombo"; x:0; y:860; width:120; height:40; model:["still","animated"]
        delegate:RadioDelegate { objectName:"snapshotMode.option."+modelData; width:foreign.width;
            text:modelData; checked:foreign.currentIndex===index }
    }
}
''')
            binary = stage / 'test'
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-UNDEBUG', '-pthread',
                '-I' + str(ROOT / 'ios/ui'), '-I' + str(ROOT / 'libraries/ui/src'),
                str(ROOT / 'ios/ui/IOSNormalUiInput.cpp'), str(ROOT / 'libraries/ui/src/ui/NativeFieldInput.cpp'),
                str(Path(__file__).with_suffix('.cpp')), '-o', str(binary), *libraries, *flags],
                env=env, check=True, timeout=60)
            runner = env.get('OVERTE_HOST_TEST_NETWORK_RUNNER')
            isolation = [runner] if runner else ['unshare', '--user', '--map-root-user', '--net']
            subprocess.run([*isolation, str(binary), str(stage)],
                env=env | {'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
                           'QT_FORCE_STDERR_LOGGING': '1'}, check=True, timeout=30)


if __name__ == '__main__':
    unittest.main(verbosity=2)
