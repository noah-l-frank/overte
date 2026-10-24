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
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.avatar_preferences import validate,baseline,continuity
from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import decode,exact
sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_preferences_support import prepare,native_stage


class AvatarPreferencesNativeTests(unittest.TestCase):
    def test_original_lazy_handles_writer_physical_and_bounded_barrier(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');extra=[]
        if major=='5':
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
        else:moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],env=environment,text=True))
        with native_stage('pico-avatar-preferences-') as directory:
            stage=Path(directory);stage.chmod(0o700);cpp=stage/'test.cpp';cpp.write_text(Path(__file__).with_name('avatar-preferences-native.cpp').read_text());binary=stage/'test'
            prepare(stage,ROOT)
            includes=['-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(stage),'-I'+str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True))]
            definitions=['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE']
            subprocess.run([str(moc),*definitions,*includes,str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(stage/'manager.moc.cpp')],check=True,timeout=20,env=environment)
            built=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-include','QIODevice',*definitions,*includes,str(cpp),str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(ROOT/'libraries/shared/src/SettingHelpers.cpp'),str(ROOT/'libraries/shared/src/SharedLogging.cpp'),str(stage/'manager.moc.cpp'),'-o',str(binary),*extra,*flags],capture_output=True,text=True,timeout=60,env=environment)
            (stage/'compile.stdout.txt').write_text(built.stdout);(stage/'compile.stderr.txt').write_text(built.stderr)
            self.assertEqual(0,built.returncode,built.stderr[:10000])
            for runtime in (False,True):
                data=stage/('enabled' if runtime else 'disabled');data.mkdir(mode=0o700)
                result=subprocess.run([str(binary),str(data),*(['--testScript'] if runtime else [])],capture_output=True,text=True,timeout=12,env=environment)
                (stage/('enabled' if runtime else 'disabled')).with_suffix('.stdout.jsonl').write_text(result.stdout)
                (stage/('enabled' if runtime else 'disabled')).with_suffix('.stderr.txt').write_text(result.stderr)
                self.assertEqual(0,result.returncode,result.stdout[-1000:]+result.stderr)
            # The actual native fsync'd intent/result originals are read cold
            # through the existing bounded descriptor owner, then fully reread.
            # No journal Boolean supplies the independently observed restoration.
            journal=[]
            self.assertEqual(9,len(list((stage/'enabled').glob('lazy-cas-*.json'))))
            for index in range(1,10):
                path=stage/'enabled'/('lazy-cas-'+str(index)+'.json')
                original=ClosedOriginalFile(path,0o600,PrivateFeatureState(path)._parent)
                data,stamp=original.read();event=decode(data.decode('utf-8'))
                phase='intent' if index%2 else 'result'
                exact(event,({'avatarLazyHandleCasVersion','transaction','phase','key','original','expected'} if phase=='intent' else
                    {'avatarLazyHandleCasVersion','transaction','phase','restored','verified','after'}))
                self.assertIs(type(event['avatarLazyHandleCasVersion']),int);self.assertEqual(1,event['avatarLazyHandleCasVersion'])
                self.assertEqual(phase,event['phase']);self.assertRegex(event['transaction'],'^[0-9a-f]{32}$')
                if phase=='intent':self.assertEqual('Avatar/pitchSpeed' if index==9 else 'Avatar/scale',event['key'])
                else:
                    self.assertIs(event['restored'],index not in (2,4));self.assertIs(event['verified'],index not in (2,4))
                    self.assertEqual(journal[-1]['transaction'],event['transaction'])
                self.assertEqual((data,stamp),original.read());self.assertTrue(original.close());journal.append(event)
            self.assertEqual(5,len({event['transaction'] for event in journal}))
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(['lazy-original','live-only-conflict','initialized-absent','lazy-cas-restored','lazy-cas-result-lost-restored','saved-scale','writer-only-conflict','physical-conflict','head-pitch-original-key','late-result-discarded','avatar-replacement'],[row['kind'] for row in rows])
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
        # The shared existing Favorite rule must refuse independently valid
        # raw changes too; no forged packet or inconsistent writer supplies it.
        from adapters.pico4.avatar_favorite_effect import unchanged_preferences,original_preferences
        from adapters.normal_ui import NativeUIError
        named={row['kind']:row for row in rows}
        for first,last in (('lazy-original','initialized-absent'),('initialized-absent','saved-scale')):
            before,after=named[first]['packet'],named[last]['packet'];baseline(before);baseline(after)
            self.assertNotEqual(before['source']['snapshot']['cache']['native']['handles'],after['source']['snapshot']['cache']['native']['handles'])
            with self.subTest(original_cached_admission=(first,last)),self.assertRaises(NativeUIError):
                unchanged_preferences(before,after)
            with self.subTest(original_noop_admission=(first,last)),self.assertRaises(NativeUIError):
                original_preferences(before,after)
        before,after=(named[key]['packet'] for key in ('lazy-original','live-only-conflict'))
        a,b=baseline(before),baseline(after)
        self.assertEqual(a['cache']['native']['handles'],b['cache']['native']['handles'])
        self.assertEqual(a['cache']['rows'],b['cache']['rows'])
        self.assertEqual(a['writer']['physical']['fileSha256'],b['writer']['physical']['fileSha256'])
        self.assertNotEqual(a['cache']['native']['live'],b['cache']['native']['live'])
        with self.assertRaises(NativeUIError):original_preferences(before,after)
        for kind in ('lazy-cas-restored','lazy-cas-result-lost-restored'):
            original_preferences(named['lazy-original']['packet'],named[kind]['packet'])
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
