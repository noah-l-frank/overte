"""Two actual native reader processes; protocol/NodeList remain host endpoints."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from test_assets_read_native import compile_source,ROOT
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.assets_mapping_pair import IndependentAssetsMappings
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey import lock as lock_module
from adapters.script_journey.history import pack
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
RUN='b'*32


class PhaseClient(Client):
    def __init__(self,journal):super().__init__('http://127.0.0.1:1/feature-fixture/v1','h'*32);self.journal=journal
    def request(self,path,value=None,method=None,*,phase_nonce=None,**options):
        assert path=='/runs/'+RUN+'/phase' and value is None and phase_nonce is not None
        return self.journal.phase(RUN,phase_nonce)


class Actor:
    def __init__(self,binary,environment,path):
        self.lock=ScriptSourceLock(path/'script-sources.lock');self.raw='';self.commands=[];self.received=[]
        self.process=subprocess.Popen([str(binary),'--testScript','--serve','--independent-host-actor'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,env=environment)
        self.source=PicoAssetsSource(self.send,lambda:self.raw,lambda:int(time.time()*1000),self.guard,self.process.pid)
    def guard(self):self.lock.assert_held();assert self.process.poll() is None
    def send(self,request):
        self.guard();self.commands.append(deepcopy(request));self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
        assert select.select([self.process.stdout],[],[],5)[0];self.raw=self.process.stdout.readline();assert self.raw
        self.received.append(dict(command=deepcopy(request),raw=self.raw,sha256=hashlib.sha256(self.raw.encode()).hexdigest()))
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=3);self.process.stdout.close();assert self.process.returncode==0


class AssetsMappingPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-pair-build-');cls.binary,cls.environment=compile_source(cls.build.name)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='pico-assets-pair-');self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name);self.actors=[]
        for name in ('primary','independent'):
            path=self.path/name;path.mkdir(mode=0o700);actor=Actor(self.binary,self.environment,path);self.actors.append(actor);self.addCleanup(actor.close)
        self.journal=Journal()
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,self.journal.register('assets'))
        self.journal.activate(RUN,'1'*32,'inspect-baking-unavailable',{})
        self.phase=PhaseFixtureReader(PhaseClient(self.journal),RUN,'assets')
        self.pair=IndependentAssetsMappings(*(actor.source for actor in self.actors),*(actor.lock for actor in self.actors),self.phase)
        self.addCleanup(self.preserve)
    def preserve(self,suffix=''):
        destination=os.environ.get('OVERTE_ASSETS_PAIR_EVIDENCE')
        if destination is None:return
        value=dict(assetsPairHostEvidenceVersion=1,artifactSha256=hashlib.sha256(Path(self.binary).read_bytes()).hexdigest(),
            pairedOriginals=pack(self.pair.history),sourceOriginals=[dict(processId=actor.process.pid,
                originals=pack(actor.source.history),transportOriginals=pack(actor.received),pending=deepcopy(actor.source.pending)) for actor in self.actors],phaseOriginal=deepcopy(self.phase.previous))
        PrivateFeatureState(Path(destination).resolve(strict=True)/(self._testMethodName+suffix+'.json')).write(value,None)
    def test_actual_independent_process_originals_full_inventory_and_fresh_phase(self):
        result=self.pair.capture();first=deepcopy(self.pair.history)
        a,b=(json.loads(result[key]['raw']) for key in ('primary','independent'))
        self.assertEqual({actor.process.pid for actor in self.actors},{a['processId'],b['processId']});self.assertNotEqual(a['instance'],b['instance'])
        self.assertEqual(a['source']['mappings'],b['source']['mappings']);self.assertEqual(3,len(a['source']['mappings']))
        self.assertTrue(any(row['path'].startswith('/.baked/') for row in a['source']['mappings']))
        self.assertNotEqual(a['source']['sessionId'],b['source']['sessionId']);self.pair.capture();self.assertEqual(first,self.pair.history[:1])
        self.assertTrue(all(len(actor.commands)==2 for actor in self.actors))
    def test_primary_raw_cannot_supply_the_other_actual_process_observation(self):
        primary,independent=self.actors;send=independent.send
        def replay(command):send(command);value=json.loads(primary.raw);value['requestId']=command['commandId'];independent.raw=json.dumps(value)
        independent.source.send=replay
        with self.assertRaises(NativeUIError):self.pair.capture()
        self.assertEqual([],self.pair.history);self.assertEqual(1,len(primary.source.history));self.assertIsNotNone(independent.source.pending)
    def test_fixture_phase_advance_during_independent_read_refuses_pair_publication(self):
        independent=self.actors[1];send=independent.send
        def advance(command):send(command);self.journal.activate(RUN,'2'*32,'close',{})
        independent.source.send=advance
        with self.assertRaises(NativeUIError):self.pair.capture()
        self.assertEqual([],self.pair.history);self.assertTrue(all(len(actor.source.history)==1 for actor in self.actors))
    def test_same_original_process_is_refused_before_any_request(self):
        actor=self.actors[0]
        with self.assertRaises(NativeUIError):IndependentAssetsMappings(actor.source,actor.source,actor.lock,self.actors[1].lock,self.phase)
        self.assertTrue(all(not actor.commands for actor in self.actors))
    def test_real_outer_lock_close_delay_or_failure_retains_sources_and_latches_attempt(self):
        for mode in ('delay','native-jump','failure'):
            with self.subTest(mode=mode):
                if mode!='delay':
                    self.actors=[]
                    for role in ('primary','independent'):
                        path=self.path/(mode+'-'+role);path.mkdir(mode=0o700);actor=Actor(self.binary,self.environment,path)
                        self.actors.append(actor);self.addCleanup(actor.close)
                    self.phase=PhaseFixtureReader(PhaseClient(self.journal),RUN,'assets')
                    self.pair=IndependentAssetsMappings(*(actor.source for actor in self.actors),*(actor.lock for actor in self.actors),self.phase)
                pair=self.pair;outer=pair.locks[0];descriptor=[None];offset=[0];native_offset=[0];closed=[]
                native_epoch=int(time.time()*1000);monotonic=time.monotonic;host=monotonic();guard=self.actors[0].source.guard
                def tracked():
                    guard();descriptor[0]=outer._owner[1]
                self.actors[0].source.guard=tracked
                for actor in self.actors:
                    actor.source.clock_ms=lambda:native_epoch+native_offset[0]
                    actor.source.monotonic=(lambda:host) if mode=='native-jump' else (lambda:monotonic()+offset[0])
                self.phase.monotonic=(lambda:host) if mode=='native-jump' else (lambda:monotonic()+offset[0])
                close=lock_module.os.close
                def actual_close(value):
                    close(value)
                    if value==descriptor[0]:
                        closed.append(value)
                        if mode=='failure':raise OSError('Explicit outer original close failure')
                        if mode=='native-jump':native_offset[0]+=2000
                        else:offset[0]+=2
                original_seal=pair.seal;original_sources=pair.source_seals
                with patch.object(lock_module.os,'close',side_effect=actual_close),self.assertRaises((NativeUIError,OSError)):
                    pair.capture()
                self.assertEqual(1,len(closed));self.assertTrue(pair.failed);self.assertEqual([],pair.history)
                self.assertIs(original_seal,pair.seal);self.assertIs(original_sources,pair.source_seals)
                self.assertTrue(all(len(actor.source.history)==1 for actor in self.actors));self.assertTrue(all(lock._owner is None for lock in pair.locks))
                commands=[len(actor.commands) for actor in self.actors]
                with self.assertRaises(NativeUIError):pair.capture()
                self.assertEqual(commands,[len(actor.commands) for actor in self.actors]);self.preserve('-'+mode)


if __name__=='__main__':unittest.main()
