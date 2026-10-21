"""Durable frame ownership counterexamples; synthetic GPU only, no compiler."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.completed_frame_lease import CompletedFrameLease
from adapters.native_completed_frame import NativeCompletedFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from self_tests.test_native_completed_frame import Boundary

BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',
             generation=1,targetFingerprint='c'*64)
RUN='d'*32


class GPU(Boundary):
    def __init__(self):
        super().__init__();self.frame=0;self.fixed_frame=False;self.lost_release=False;self.after=None
    def send(self,value):
        if value['operation']=='read':
            self.retired=False;self.frame+=1
        super().send(value)
        if value['operation']=='inspect' and (self.request is None or self.request['requestId']!=value['requestId']):
            self.value['source'].update(retired=False,present=False,callbacks=0,gpuPending=False,metadataBytes=0)
        if self.lost_release and value['operation']=='release':raise OSError('Synthetic lost release response')
    def original(self):
        raw=super().original()
        if self.value is not None:
            self.value['requestId']=self.commands[-1]['requestId']
            if 'source' in self.value and 'renderTrace' in self.value['source']:
                self.value['source']['renderTrace']['frameId']=format(1 if self.fixed_frame else self.frame,'032x')
            raw=json.dumps(self.value)
        return raw
    def owner(self,store,*,binding=BINDING,run=RUN,role='primary'):
        def factory(intent):
            return NativeCompletedFrame(self.send,self.original,self.epoch,lambda:self.okay,42,intent,
                                        monotonic=lambda:self.clock,sleep=self.sleep)
        return CompletedFrameLease(store,binding,run,role,factory,lambda:self.okay,
                                   monotonic=lambda:self.clock,sleep=self.sleep)


class LeaseTests(unittest.TestCase):
    def test_originals_persist_across_reconstruction_and_new_capture_requires_real_drain(self):
        with tempfile.TemporaryDirectory() as root:
            store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();owner=b.owner(store)
            original=owner.capture();self.assertEqual(original,unpack(store.read()['transcript'])[1]['packet'])
            self.assertEqual('inspect',b.commands[0]['operation'])
            with self.assertRaises(NativeUIError):b.owner(store).capture()
            drained=b.owner(store).drain();self.assertEqual(0,drained['source']['callbacks'])
            self.assertIsNone(store.read()['active']);second=b.owner(store).capture()
            self.assertNotEqual(original['requestId'],second['requestId'])
            self.assertNotEqual(original['source']['renderTrace']['frameId'],second['source']['renderTrace']['frameId'])
            b.owner(store).drain();events=unpack(store.read()['transcript'])
            self.assertEqual(original,events[1]['packet']);self.assertEqual(2,sum(e['command']['operation']=='read' for e in events))

    def test_missing_fence_cannot_be_retried_by_reconstructing_owner_or_erased_by_release(self):
        with tempfile.TemporaryDirectory() as root:
            store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();b.no_fence=True
            with self.assertRaises(NativeUIError):b.owner(store).capture()
            for operation in ('capture','drain','capture'):
                with self.assertRaises(NativeUIError):getattr(b.owner(store),operation)()
            self.assertIsNotNone(store.read()['active']);self.assertEqual(1,sum(c['operation']=='read' for c in b.commands))
            self.assertEqual(1,sum(c['operation']=='release' for c in b.commands))
            self.assertIsNone(unpack(store.read()['transcript'])[1]['packet'])

    def test_lost_release_is_inspected_without_resending_it_and_original_ownership_remains(self):
        with tempfile.TemporaryDirectory() as root:
            store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();b.owner(store).capture();b.lost_release=True
            with self.assertRaises(NativeUIError):b.owner(store).drain()
            b.sleep(.2);result=b.owner(store).drain()
            self.assertEqual(0,result['source']['callbacks']);self.assertEqual(1,sum(c['operation']=='release' for c in b.commands))
            self.assertTrue(any(e['command']['operation']=='release' and e['packet'] is None for e in unpack(store.read()['transcript'])))

    def test_failed_intent_stops_delivery(self):
        class FailedStore(PrivateFeatureState):
            def write(self,*_):raise OSError('Synthetic storage failure')
        with tempfile.TemporaryDirectory() as root:
            b=GPU();store=FailedStore(Path(root)/'frames.json')
            with self.assertRaises(NativeUIError):b.owner(store).capture()
            self.assertEqual([],b.commands)

    def test_changed_owner_after_send_is_not_overwritten_or_reported_as_success(self):
        with tempfile.TemporaryDirectory() as root:
            store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();original=b.send
            def changed(value):
                original(value)
                before=store.read();foreign=deepcopy(before);foreign['role']='actor';store.write(foreign,before)
            b.send=changed
            with self.assertRaises(NativeUIError):b.owner(store).capture()
            self.assertEqual(1,len(b.commands));self.assertEqual('actor',store.read()['role'])
            self.assertIsNone(unpack(store.read()['transcript'])[0]['packet'])

    def test_foreign_role_run_candidate_or_pid_cannot_adopt_ownership(self):
        with tempfile.TemporaryDirectory() as root:
            store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();b.owner(store).capture();before=deepcopy(store.read())
            for options in (dict(role='actor'),dict(run='e'*32),dict(binding=BINDING|{'artifactSha256':'f'*64}),
                            dict(binding=BINDING|{'processIdentity':'43'})):
                with self.subTest(options=options),self.assertRaises(NativeUIError):b.owner(store,**options).drain()
            self.assertEqual(before,store.read());self.assertEqual(2,len(b.commands))

    def test_reused_frame_identity_or_regressed_source_is_not_new_evidence(self):
        for failure in ('frame','sequence','instance'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as root:
                store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();b.owner(store).capture();b.owner(store).drain()
                if failure=='frame':b.fixed_frame=True
                elif failure=='sequence':b.sequence=0
                else:b.change=lambda v:v.update(instance='e'*32) if 'source' in v else None
                with self.assertRaises(NativeUIError):b.owner(store).capture()
                self.assertIsNotNone(store.read()['active']);self.assertIsNone(unpack(store.read()['transcript'])[-1]['packet'])

    def test_known_complete_legacy_transcript_remains_readable_but_unbound_lost_legacy_read_does_not(self):
        for complete in (False,True):
            with self.subTest(complete=complete),tempfile.TemporaryDirectory() as root:
                store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();original=b.owner(store).capture()
                before=store.read();legacy=deepcopy(before);events=unpack(legacy['transcript'])[1:]
                if not complete:events[0]['packet']=None
                legacy['transcript']=pack(events);store.write(legacy,before);commands=len(b.commands)
                if complete:self.assertEqual(0,b.owner(store).drain()['source']['callbacks'])
                else:
                    with self.assertRaises(NativeUIError):b.owner(store).drain()
                    self.assertEqual(commands,len(b.commands));self.assertEqual(legacy,store.read())

    def test_lost_read_then_replaced_context_cannot_supply_empty_cleanup_for_original_source(self):
        with tempfile.TemporaryDirectory() as root:
            store=PrivateFeatureState(Path(root)/'frames.json');b=GPU();b.no_fence=True
            with self.assertRaises(NativeUIError):b.owner(store).capture()
            self.assertEqual('inspect',b.commands[0]['operation'])
            b.request=None;b.no_fence=False;b.gpu_pending=b.held=False;b.sequence=0
            b.change=lambda value:value.update(instance='e'*32) if 'source' in value else None
            with self.assertRaises(NativeUIError):b.owner(store).drain()
            self.assertIsNotNone(store.read()['active']);self.assertIsNone(unpack(store.read()['transcript'])[-1]['packet'])


if __name__=='__main__':unittest.main()
