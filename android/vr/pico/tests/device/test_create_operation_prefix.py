"""Same CLI Parent across the existing first twelve normal Create actions.

The actual direct child observes its ORIGINAL Model scope only. This does not
supply full Create Actor, permission/voxel/GPU or Common feature acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import time
import unittest
import uuid

from test_create_operation_cli import CreateOperationCliTests
from test_create_journey import RUN,URL
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from adapters.chat_journey.source_chunks import ChatSourceChunks
from feature_journeys.scenarios import SCENARIOS


class CreateOperationPrefixTests(CreateOperationCliTests):
    def peer_record(self,peer,ticket,deadline,*,material=False):
        # Read the actual child's own originals, never a Parent effect packet.
        while time.monotonic()<deadline:
            with ScriptSourceLock(peer/'script-sources.lock').held():
                store=PrivateFeatureState(peer/'create-peer-originals.json');root=store.read()
                if root is not None and root['pending'] is None and root['records']:
                    scope={key:root[key] for key in ('picoCreatePeerSourceVersion','scope','actorBinding','producerHostProcessIdentity')}
                    frames=ChatSourceChunks(store,scope).load(root['chunks'])
                    row=root['records'][-1];phase=frames[row['phase']]['packet']
                    if phase['activations'][-1]['ticket']==ticket and (not material or row['facts']['materialAssignmentBound']):
                        return dict(record=row,phase=phase)
            time.sleep(.01)
        self.fail('Original worker did not acquire this actual phase within original prefix budget')

    def test_same_original_cli_twelve_actions_then_retained_qt_context_refuses_cleanup_without_replay(self):
        started=time.monotonic();deadline=started+120
        self.component('prepare');peer=self.area/'peer';peer.mkdir(mode=0o700)
        witnessed=[];worker=None
        for index,step in enumerate(SCENARIOS['create']['steps'][:12],1):
            self.assertLess(time.monotonic(),deadline)
            self.act(step['verb'],step['inputs'])
            phase=self.authority.journal.phase(RUN,uuid.uuid4().hex);ticket=phase['activations'][-1]['ticket']
            if index==4:
                worker=self.component('peer.start',dict(target='synthetic-second-pico',candidateArguments=['--apk','owned.apk'],
                    fixtureUrl=URL.split('/runs/')[0],actorToken='explicit-model-actor-'+'b'*32,
                    durationSeconds=120,artifactRoot=str(peer)))
            if worker is not None:
                original=self.peer_record(peer,ticket,min(deadline,time.monotonic()+5),material=index==5);facts=original['record']['facts']
                self.assertTrue(facts['independentClient']);self.assertFalse(facts['fullCreateActor']);self.assertFalse(facts['gpuPixelsObserved'])
                if index==4:self.assertTrue(facts['present'] and facts['modelLoaded'])
                if index==5:self.assertTrue(facts['materialAssignmentBound'])
                if index>=7:self.assertFalse(facts['present'])
                witnessed.append(dict(index=index,verb=step['verb'],original=original))
        sample=self.component('sample');self.authority.epoch=sample['sampleAnchor']['nativeEpochMs']
        with self.assertRaisesRegex(RuntimeError,'unresolved'):
            with self.host.create_input_context(RUN,URL,'cleanup',None):
                self.authority.activate(uuid.uuid4().hex,'cleanup',{})
                self.component('cleanup')
        self.assertTrue(self.host.failed)
        errors=b''.join(path.read_bytes() for path in sorted(self.artifacts.glob('stderr-*.bin')))
        self.assertIn(b'Original Create Qt context, listener or delivery remains retained',errors)
        def transport_originals():
            result={}
            for path in self.artifacts.iterdir():
                if path.is_file():
                    info=path.lstat();result[path.name]=(path.read_bytes(),info.st_dev,info.st_ino,info.st_mode,info.st_uid,
                        info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
            return result
        original_transport=transport_originals()
        with self.assertRaisesRegex(RuntimeError,'unresolved'):self.component('cleanup')
        self.assertEqual(original_transport,transport_originals())
        metadata=PrivateFeatureState(self.area/'model-host.json').read();self.assertEqual(1,metadata['factoryCalls'])
        state_root=Path(metadata['stateRoot'])
        owners=list(state_root.glob('normal-create-operation-*.json'))
        self.assertTrue(owners)
        owner=next(PrivateFeatureState(path).read() for path in owners if '.peer-config.' not in path.name)
        self.assertEqual('component-issued',owner['phase']);self.assertEqual('cleanup',owner['pending']['operation'])
        self.assertEqual(list(range(4,13)),[row['index'] for row in witnessed])
        elapsed=time.monotonic()-started;self.assertLess(elapsed,120)
        receipt=dict(componentOnly=True,completeCommonObservation=False,actions=12,peerOriginalModelOnly=True,
            witnessed=witnessed,hostElapsedSeconds=elapsed,cleanupSucceeded=False,retainedQtContext=True,
            replayIssued=False,host=metadata,peer=worker)
        (self.area/'twelve-action-prefix-result.json').write_text(json.dumps(receipt,sort_keys=True))



def load_tests(loader,tests,pattern):
    return unittest.TestSuite([CreateOperationPrefixTests(
        'test_same_original_cli_twelve_actions_then_retained_qt_context_refuses_cleanup_without_replay')])

if __name__=='__main__':unittest.main()
