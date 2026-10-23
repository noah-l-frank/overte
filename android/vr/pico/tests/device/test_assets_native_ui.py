"""Actual Pico observer/input, original Assets QML and real file helper.

Asset Server/entity and keyboard-device endpoints are declared host seams.
This compiles selected original bodies, not Interface or an actual oven/server.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
from test_create_polyvox_controls_native import pointer_source,original


class AssetsNativeUITests(unittest.TestCase):
    def test_actual_pico_asset_browser_bundle_upload_and_unavailable_selection(self):
        environment=dict(os.environ);prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt5'+module for module in ('Core','Gui','Qml','Quick','Test','Widgets'))],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-assets-native-ui-') as directory:
            stage=Path(directory);pointer_source(stage);imports=stage/'imports/controlsUit';imports.mkdir(parents=True)
            (imports/'qmldir').write_text('module controlsUit\nTouchUiMetrics 1.0 TouchUiMetrics.qml\nKeyboard 1.0 Keyboard.qml\n')
            (imports/'TouchUiMetrics.qml').write_text('import QtQml 2.7\nQtObject {property bool systemImeAvailable:false}\n')
            (imports/'Keyboard.qml').write_text('import QtQuick 2.7\nItem {property bool raised:false;property bool numeric:false;property bool password:false;property real keyboardWidth:640;property real raisedHeight:200}\n')
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
                'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
                'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
            native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
            self.assertIn('#include "../../../../../../tests/device/native/NormalAssetsControls.h"',native)
            bodies='\n'.join(original(native,signature) for signature in ('QString token()', 'bool visible(', 'bool enabled(',
                'QString controlId(', 'bool integer(', 'bool exactKeys('))
            bodies+='\nNavigationUi::NavigationUi() : _bridgeId(token()), _generation(token()) { _clock.start(); }\n'
            bodies+='\n'+original(native,'QJsonObject NavigationUi::observe(')+'\n'+original(native,'QJsonObject NavigationUi::apply(')
            (stage/'actual-assets-navigation.inc').write_text('namespace overte::pico::e2e {\n'+bodies+'\n}\n')
            bundle=stage/('feature-assets-'+'a'*32)/'gltf-bundle';(bundle/'mesh').mkdir(parents=True);(bundle/'textures').mkdir()
            for name,data in (('main.gltf',b'actual main bytes'),('mesh/triangle.bin',b'actual mesh bytes'),('textures/checker.png',b'actual texture bytes')):(bundle/name).write_bytes(data)
            subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),str(ROOT/'libraries/ui/src/FileDialogHelper.h'),'-o',str(stage/'helper-moc.cpp')],check=True,timeout=20,env=environment)
            binary=stage/'test'
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-fmax-errors=3','-DOVERTE_E2E_FEATURE_TESTS',
                '-I'+str(stage),'-I'+str(HERE),'-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src'),
                '-I'+str(ROOT/'libraries/script-engine/src'),'-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
                str(HERE/'assets-controls-native.cpp'),str(ROOT/'libraries/ui/src/FileDialogHelper.cpp'),
                str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),str(stage/'helper-moc.cpp'),'-o',str(binary),
                '-L'+str(prefix/'usr/lib64'),*flags],check=True,timeout=90,env=environment)
            args=[str(binary),str(stage/'imports'),str(ROOT/'interface/resources/qml/hifi/dialogs/TabletAssetServer.qml'),str(bundle),str(stage/'originals.json'),str(ROOT)]
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_LOGGING_RULES='*.warning=true',QT_FORCE_STDERR_LOGGING='1')
            for gate in ([],['--testScript']):
                subprocess.run(['unshare','--user','--map-root-user','--net',*args,*gate],check=True,timeout=30,env=environment)
            from adapters.pico4.navigation import validate_snapshot
            from adapters.pico4.assets_ui import project
            originals=json.loads((stage/'originals.json').read_text());self.assertGreater(len(originals),50)
            for value in originals:
                validate_snapshot(value,value['processId'],value['updatedEpochMs']);project(value)


if __name__=='__main__':unittest.main()
