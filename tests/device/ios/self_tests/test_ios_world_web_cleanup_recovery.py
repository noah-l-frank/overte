"""Repeated role cleanup with real coordinator CAS/files and OS source locks.

Native acquisitions, installed-peer admission and the retirement transport are
explicit boundary models. These tests qualify control flow, not native Scene3
or the separate typed retirement-reader decoder.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_world_web_runtime as fixture
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebCleanupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.peer=BINDING|dict(sessionId='peer',targetFingerprint='a'*64)
        self.addCleanup(patch.stopall)
        patch('ios.adapters.world_web_feature.peer_admission',side_effect=lambda *_args:deepcopy(self.peer)).start()
        settings={key:value for key,value in self.f.settings.items() if key!='primaryTarget'}|dict(actorTarget='actor')
        self.flow=self.f.runtime._world_web_feature('primary','a'*32,role='primary',client=self.f.client,settings=settings)
        self.clock=100.;self.flow.monotonic=lambda:self.clock;self.flow.epoch_ms=lambda:self.clock*1000
        self.flow.sleep=lambda _delay:None;self.samples=[];self.reject=False;self.reads=0
        self.receipt=dict(entry=dict(ticket='c'*32),acquisition=dict(hostAfterMonotonic=99.))
        self.reader_store=self.f.runtime._world_web_store('primary','ios-world-web-primary-peer-retirement.json')
        self.reader_value=dict(explicitRetirementReaderBoundary=True,records=[deepcopy(self.receipt)])
        outer=self
        class ReaderBoundary:
            def __init__(self,store,*_args,**_kwargs):
                self.store=store;self.previous=store.read()
                self.state=dict(records=[] if self.previous is None else deepcopy(self.previous['records']))
            def read(self):
                outer.reads+=1
                need(outer.reads==1)  # No second request for once-only Actor Scene3.
                self.store.write(outer.reader_value,self.previous);self.previous=deepcopy(outer.reader_value)
                self.state=dict(records=deepcopy(outer.reader_value['records']));return deepcopy(outer.receipt)
        patch('ios.adapters.world_web_feature.PhaseRetirementReader',ReaderBoundary).start()
        patch.object(self.f.runtime,'existing_input_session',side_effect=lambda *_args:nullcontext()).start()
        def cleanup(ticket):
            self.flow.lock.assert_held();self.clock+=1
            original=dict(ticket=ticket,acquisition=dict(hostBeforeMonotonic=self.clock),sample=len(self.samples)+1)
            self.samples.append(deepcopy(original));return original
        def validate(original):
            need(not self.reject and original in self.samples);return deepcopy(original)
        self.retirement=SimpleNamespace(cleanup=cleanup,validate_original=validate)
        self.parts=dict(retirement=self.retirement,own=dict(check=lambda:True))
        self.status=dict(verb='cleanup',ticket='c'*32,status=dict(instance='b'*32))
        def ensure():self.flow.load();return self.parts,deepcopy(self.status)
        self.flow.ensure=ensure;self.flow.parts=lambda:self.parts
        self.flow.phase.read=lambda:deepcopy(self.status)
        with self.flow.held():
            self.flow.load();self.flow.state=dict(phase='ready',binding=BINDING,primaryBinding=BINDING,
                phaseInstance='b'*32,initialTicket='c'*32,actorAdmission=dict(explicitAdmissionBoundary=True),
                baseline=None,lease=None,beforeImage=None,images=[],retirement=None);self.flow.save()
        self.call=dict(contractVersion=16,runId=self.flow.run)

    def paired(self):
        self.assertEqual(dict(performed=True),self.flow.cleanup(self.call))
        self.assertEqual('paired',self.flow.state['phase']);self.assertEqual(2,len(self.samples));self.assertEqual(1,self.reads)

    def test_repeat_after_actor_receipt_freshness_expired_acquires_new_local_original_without_new_post_or_read(self):
        self.paired();retained=deepcopy(self.flow.state['retirement']);self.clock+=100
        self.assertEqual(dict(performed=True),self.flow.cleanup(self.call))
        self.assertEqual(3,len(self.samples));self.assertEqual(1,self.reads)
        self.assertEqual(retained['peerReceipt'],self.flow.state['retirement']['peerReceipt'])
        self.assertEqual(retained['readerOriginal'],self.flow.state['retirement']['readerOriginal'])
        self.assertEqual(digest(self.samples[-1]),self.flow.state['retirement']['localSha256'])
        self.assertIsNone(self.flow.lock._owner)

    def test_missing_retained_reader_remains_unresolved_after_fresh_local_cleanup(self):
        self.paired();self.reader_store.discard(self.reader_value)
        with self.assertRaises(NativeUIError):self.flow.cleanup(self.call)
        self.assertEqual(3,len(self.samples));self.assertEqual(1,self.reads)

    def test_changed_reader_or_last_receipt_cannot_replace_the_original_join(self):
        self.paired();changed=deepcopy(self.reader_value);changed['records'][0]['entry']['ticket']='d'*32
        self.reader_store.write(changed,self.reader_value)
        with self.assertRaises(NativeUIError):self.flow.cleanup(self.call)
        self.assertEqual(changed,self.reader_store.read());self.assertEqual(1,self.reads)

    def test_failed_new_local_original_never_returns_historical_success(self):
        self.paired();self.reject=True
        with self.assertRaises(NativeUIError):self.flow.cleanup(self.call)
        self.assertEqual(3,len(self.samples));self.assertEqual(1,self.reads)
        with self.flow.held():
            self.flow.load();self.assertEqual('cleaning',self.flow.state['phase'])
        self.assertIsNone(self.flow.lock._owner)


if __name__=='__main__':unittest.main()
