"""Original lazy Avatar Handles, full Manager/worker and independent JSON rows.

The application registry and avatar/model live getters are explicit actors;
this compiles complete original observer bodies and actual Handle declarations
and initializer keys, not the complete Interface binary or a physical Pico run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.avatar_preferences import validate,baseline,continuity


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class AvatarPreferencesNativeTests(unittest.TestCase):
    def test_original_lazy_handles_writer_physical_and_bounded_barrier(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');extra=[]
        if major=='5':
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
        else:moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],env=environment,text=True))
        interface=(ROOT/'libraries/shared/src/SettingInterface.cpp').read_text()
        code='\n'.join(function(interface,'    void Interface::'+name+'(') for name in ('init','deinit','maybeInit','save','load'))
        code+='\n'+function(interface,'    AvatarPreferenceMutation::AvatarPreferenceMutation(')
        code+='\n'+next(line for line in interface.splitlines() if 'AvatarPreferenceMutation::~AvatarPreferenceMutation()' in line)
        code+='\n'+function(interface,'    QVariantMap Interface::e2ePreferenceInterface(')
        avatar=(ROOT/'interface/src/avatar/MyAvatar.cpp').read_text();header=(ROOT/'interface/src/avatar/MyAvatar.h').read_text()
        fields=header[header.index('    Setting::Handle<QString> _dominantHandSetting;'):header.index('    // AvatarEntities stuff:')]
        initializers=avatar[avatar.index('    _dominantHandSetting('):avatar.index('    _clientTraitsHandler.reset')]
        # The original constructor prefix ends with a body brace; the rest of
        # that constructor belongs to the declared avatar/resource actor.
        initializers=initializers[:initializers.rindex(' {')]
        with tempfile.TemporaryDirectory(prefix='pico-avatar-preferences-') as directory:
            stage=Path(directory);stage.chmod(0o700);cpp=stage/'test.cpp';cpp.write_text(Path(__file__).with_name('avatar-preferences-native.cpp').read_text());binary=stage/'test'
            (stage/'actual-setting-interface.inc').write_text(code)
            (stage/'actual-avatar-handles.inc').write_text(fields)
            (stage/'actual-avatar-preferences.inc').write_text('MyAvatar::MyAvatar():\n'+initializers+' {}\n'+function(avatar,'QVariantMap MyAvatar::e2ePreferenceHandles('))
            (stage/'actual-getter.inc').write_text(function((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featurePicoAvatarPreferences('))
            includes=['-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(stage),'-I'+str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True))]
            definitions=['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE']
            subprocess.run([str(moc),*definitions,*includes,str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(stage/'manager.moc.cpp')],check=True,timeout=20,env=environment)
            built=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-include','QIODevice',*definitions,*includes,str(cpp),str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(ROOT/'libraries/shared/src/SettingHelpers.cpp'),str(ROOT/'libraries/shared/src/SharedLogging.cpp'),str(stage/'manager.moc.cpp'),'-o',str(binary),*extra,*flags],capture_output=True,text=True,timeout=60,env=environment)
            self.assertEqual(0,built.returncode,built.stderr[:10000])
            for runtime in (False,True):
                data=stage/('enabled' if runtime else 'disabled');data.mkdir(mode=0o700)
                result=subprocess.run([str(binary),str(data),*(['--testScript'] if runtime else [])],capture_output=True,text=True,timeout=12,env=environment)
                self.assertEqual(0,result.returncode,result.stdout[-1000:]+result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(['lazy-original','initialized-absent','saved-scale','writer-only-conflict','physical-conflict','head-pitch-original-key','late-result-discarded','avatar-replacement'],[row['kind'] for row in rows])
        previous=None
        for row in rows:
            packet=row['packet'];validate(packet,row['request'],packet['processId'],packet['capturedEpochMs'])
            if row['kind']=='avatar-replacement':
                with self.assertRaises(RuntimeError):continuity(previous,packet)
            else:continuity(previous,packet)
            if row['kind'] in ('writer-only-conflict','physical-conflict'):
                with self.assertRaises(RuntimeError):baseline(packet)
            else:
                with self.subTest(original_baseline=row['kind']):baseline(packet)
            previous=packet
        original=rows[0]
        for path,bad in ((('picoAvatarPreferencesVersion',),True),(('snapshot','writer','matchesPhysical'),False),
                (('snapshot','cacheMatchesWriter'),False),(('snapshot','writer','physical','capturedEpochMs'),original['packet']['requestedEpochMs']-1),
                (('snapshot','cache','native','handles','handles','headPitch','key'),'Avatar'),
                (('snapshot','cache','native','handles','handles','scale','value','sha256'),'0'*64)):
            changed=deepcopy(original['packet']);subject=changed['source']
            for key in path[:-1]:subject=subject[key]
            subject[path[-1]]=bad
            with self.subTest(original_field=path),self.assertRaises(RuntimeError):validate(changed,original['request'],changed['processId'],changed['capturedEpochMs'])

if __name__=='__main__':unittest.main()
