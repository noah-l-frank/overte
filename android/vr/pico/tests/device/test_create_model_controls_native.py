"""Actual NEW Model QML/control/input; host window/native actor are boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]


class CreateModelControlsNativeTests(unittest.TestCase):
    def test_original_qml_normal_pointer_text_model_callback_and_replay_refusal(self):
        environment=dict(os.environ);libraries=[];major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'))
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
                QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt'+major+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='create-model-controls-') as directory:
            stage=Path(directory);binary=stage/'test'
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
                'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
                'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
                '-I'+str(ROOT/'libraries/ui/src'),str(HERE/'create-model-controls.cpp'),str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),
                '-o',str(binary),*libraries,*flags],check=True,timeout=90,env=environment)
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1')
            for arguments in ([],['--testScript']):
                subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),*arguments,str(ROOT)],check=True,timeout=30,
                    env=environment)
            # Preserve the original QML/input and change only the rejected old
            # hit assumption in an owned header copy. It must fail at the real
            # non-clipping Flickable field, never at a substitute widget.
            native=stage/'tests/device/native';native.mkdir(parents=True)
            header=(ROOT/'tests/device/native/NormalControlUi.h').read_text()
            original='if (opacity<=.01 || (node->clip() && !node->clipRect().contains(local)))'
            self.assertEqual(1,header.count(original))
            (native/'NormalControlUi.h').write_text(header.replace(original,
                'if (opacity<=.01 || !node->contains(local) || (node->clip() && !node->clipRect().contains(local)))'))
            mutant=stage/'old-hit'
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
                '-I'+str(ROOT/'tests/device/native'),'-I'+str(ROOT/'libraries/ui/src'),str(HERE/'create-model-controls.cpp'),
                str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(mutant),*libraries,*flags],check=True,timeout=90,env=environment)
            rejected=subprocess.run(['unshare','--user','--map-root-user','--net',str(mutant),'--testScript',str(ROOT)],
                timeout=30,env=environment,capture_output=True,text=True)
            self.assertNotEqual(0,rejected.returncode)
            self.assertIn('Assertion `NormalControlUi::ownsPoint(search,&window,center)',rejected.stderr)


if __name__=='__main__':unittest.main()
