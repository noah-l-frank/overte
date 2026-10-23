"""Actual private native storage/getter composed with durable Pico input owner.

Only the application lifecycle holder and transport delivery are explicit seams.
No AssetClient/upload/model state is synthesized by this fixture.
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
import time
import unittest
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_file_owner import OwnedAssetsFiles
from adapters.pico4.assets_files import NativeAssetsFiles


class AssetsFilesOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-files-owner-');directory=Path(cls.build.name)
        cls.environment=dict(os.environ);major=cls.environment.get('OVERTE_NATIVE_QT_MAJOR','6')
        assert major in ('5','6');library=[]
        if major=='5' and cls.environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(cls.environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            cls.environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            library=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=cls.environment))
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();start=source.index('QVariantMap TestScriptingInterface::featurePicoAssetsFiles(')
        (directory/'AssetsFilesMethod.inc').write_text(source[start:source.index('\n}\n',start)+3])
        cls.binary=directory/'assets-files-test'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE','-pthread',
            '-I'+str(ROOT/'tests/device/native'),'-I'+str(directory),str(HERE/'assets-files-native.cpp'),'-o',str(cls.binary),*library,*flags],
            check=True,timeout=90,env=cls.environment)

    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='pico-assets-private-owner-');self.addCleanup(self.directory.cleanup)
        self.process=subprocess.Popen([str(self.binary),'--testScript','--serve'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=self.environment)
        self.addCleanup(self.close_process)
        self.raw='';self.lost=None;self.operations=[];self.host=0
        self.binding=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='owned-native-fixture',sessionId='assets-test',generation=1,targetFingerprint='3'*64)
        self.store=PrivateFeatureState(Path(self.directory.name)/'assets-owner.json');self.make()
    def close_process(self):
        self.process.stdin.close();self.process.wait(timeout=3);self.process.stdout.close()
    def send(self,value):
        self.operations.append(value['operation']);self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush()
        actual=self.process.stdout.readline();self.assertTrue(actual)
        self.raw='' if self.lost==value['operation'] else actual
    def sleep(self,seconds):self.host+=seconds
    def make(self):
        native=NativeAssetsFiles(self.send,lambda:self.raw,lambda:int(time.time()*1000),lambda:True,self.process.pid,
            monotonic=lambda:self.host,sleep=self.sleep,stage=1)
        self.owner=OwnedAssetsFiles(native,self.store,self.binding,'a'*32,'b'*32,'http://127.0.0.1:12345/feature-fixture/v1/runs/'+'a'*32+'/')
    def test_real_stage_cold_restore_primary_release_retains_originals(self):
        location=self.owner.prepare();self.assertIn('feature-assets-'+'a'*32+'-stage1',location)
        first=self.store.read();self.make();self.assertEqual(self.owner.prepare(),location)
        self.owner.retire_primary();self.make();self.assertTrue(self.owner.retire_primary()['primaryRetired'])
        self.assertTrue(self.owner.release(lambda:True)['retired']);self.assertEqual(self.store.read()['phase'],'retired')
        self.assertEqual(self.operations.count('stage'),1);self.assertEqual(self.operations.count('retire-primary'),1)
        self.assertGreater(len(self.owner.native.history),len(__import__('adapters.script_journey.history',fromlist=['unpack']).unpack(first['originals'])))
    def test_lost_stage_reply_observes_original_lease_without_restage(self):
        self.lost='stage'
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(self.store.read()['phase'],'stage-issuing');self.lost=None;self.make();self.owner.prepare()
        self.assertEqual(self.operations.count('stage'),1);self.owner.release(lambda:True)
    def test_lost_primary_reply_observes_without_second_unlink_intent(self):
        self.owner.prepare();self.lost='retire-primary'
        with self.assertRaises(NativeUIError):self.owner.retire_primary()
        self.lost=None;self.make();self.owner.retire_primary();self.assertEqual(self.operations.count('retire-primary'),1)
        self.owner.release(lambda:True)
    def test_hidden_or_unresolved_consumers_never_authorize_release(self):
        self.owner.prepare();before=list(self.operations)
        with self.assertRaises(NativeUIError):self.owner.release(lambda:False)
        self.assertEqual(self.operations,before);self.assertEqual(self.store.read()['phase'],'ready')
        self.owner.release(lambda:True)
    def test_frozen_native_clock_cannot_hide_host_age_after_original_read(self):
        self.owner.prepare();native=self.owner.native;epoch=int(time.time()*1000);calls=0
        native.clock_ms=lambda:epoch
        def guard():
            nonlocal calls
            calls+=1
            if calls==3:self.host+=2
            return True
        native.guard=guard
        with self.assertRaises(NativeUIError):self.owner.read()
        self.assertEqual(self.store.read()['phase'],'ready')
        self.assertEqual(self.operations.count('stage'),1)

    def test_foreign_context_and_retained_raw_tampering_refuse_cold_adoption(self):
        self.owner.prepare();saved=self.store.read();wrong=dict(self.binding,processIdentity='foreign')
        with self.assertRaises(NativeUIError):OwnedAssetsFiles(self.owner.native,self.store,wrong,'a'*32,'b'*32,'http://127.0.0.1:12345/feature-fixture/v1/runs/'+'a'*32+'/')
        from adapters.script_journey.history import pack,unpack
        frames=unpack(saved['originals']);frames[-1]['raw']=frames[-1]['raw'].replace('"exists":true','"exists":false')
        self.store.write(saved|{'originals':pack(frames)},saved)
        with self.assertRaises(NativeUIError):self.make()


if __name__=='__main__':unittest.main()
