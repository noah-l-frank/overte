"""Actual Settings Manager/worker, authenticated Create files and fixed-key CAS."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.create_browse_setting import source
from test_create_callbacks_native import function


class CreateBrowseSettingNativeTests(unittest.TestCase):
    def test_original_manager_preserves_absence_type_and_refuses_foreign_or_cached_changes(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'))
        libraries=[];moc=shutil.which('moc'+major) or shutil.which('moc')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            libraries=['-L'+str(prefix/'usr/lib64')];moc=str(prefix/'usr/lib64/qt5/bin/moc')
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-create-browse-setting-') as directory:
            stage=Path(directory);stage.chmod(0o700)
            (stage/'OriginalCreateBrowseSetting.inc').write_text(function((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featureCreateBrowseSetting('))
            interface=(ROOT/'libraries/shared/src/SettingInterface.cpp').read_text()
            (stage/'OriginalSettingInterface.inc').write_text('\n'.join(function(interface,'    void Interface::'+name+'(') for name in ('init','deinit','maybeInit','save','load')))
            (stage/'OriginalPreviousBrowse.inc').write_text(function((ROOT/'interface/src/scripting/WindowScriptingInterface.cpp').read_text(),'QString WindowScriptingInterface::getPreviousBrowseLocation('))
            definitions=['-DOVERTE_E2E_FEATURE_TESTS=1','-DANDROID_APP_PICO_INTERFACE=1']
            include=['-I'+directory,'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'tests/device/native')]
            if environment.get('OVERTE_TEST_GLM_INCLUDE'):include.append('-I'+str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)))
            subprocess.run([moc,*definitions,*include,str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(stage/'moc_SettingManager.cpp')],check=True,timeout=20,env=environment)
            binary=stage/'browse-setting-test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread',*definitions,*include,str(HERE/'create-browse-setting-native.cpp'),
                str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(stage/'moc_SettingManager.cpp'),'-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary),directory],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),directory,'--testScript'],text=True,timeout=10,env=environment)
            packets=[json.loads(line) for line in output.splitlines()];self.assertEqual(4,len(packets))
            for packet in packets:source(packet,2**53-1)
            self.assertFalse(packets[0]['original']['present']);self.assertFalse(packets[0]['current']['present']);self.assertTrue(packets[0]['restored'])
            self.assertTrue(packets[1]['restoreAttempted']);self.assertFalse(packets[1]['restored']);self.assertEqual('/foreign/current-location',packets[1]['current']['stringValue'])
            self.assertFalse(packets[3]['claims']);self.assertEqual(1,len(packets[3]['reads']));self.assertTrue(packets[3]['restored']);self.assertFalse(packets[3]['released'])
            self.assertNotEqual(packets[3]['original'],packets[3]['writer']['raw'])
            self.assertEqual('QByteArray',packets[2]['original']['typeName']);self.assertEqual(packets[2]['original'],packets[2]['current'])


if __name__=='__main__':unittest.main()
