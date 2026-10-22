"""Real archive/CAS/phase/RestartInputs; native source production is a seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive,completed_archive
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_archive import ChatArchiveReleaseSource,ChatArchiveUnlinkFence
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from self_tests import test_restart_inputs as restart_seams

RUN='a'*32


class ChatArchiveUnlinkFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.host=1.;self.epoch=20000;self.acquisitions=0;self.phases=[]
        self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('chat')
        self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        client=Client('http://controlled.test/feature-fixture/v1','r'*64)
        def request(path,value=None,method=None,**kwargs):
            result=self.journal.phase(RUN,kwargs['phase_nonce']);self.phases.append(deepcopy(result));return result
        client.request=request
        phase=PhaseFixtureReader(client,RUN,'chat',epoch_ms=lambda:self.epoch,monotonic=lambda:self.host)
        expected=phase.read()['status']
        def reader(**changes):return SimpleNamespace(guard=lambda:True,instance='1'*32,sequence=1,**changes)
        primary=reader(clock_ms=lambda:self.epoch,source=dict(draft=False),captured=self.epoch)
        self.code=SimpleNamespace(roots=reader(last=dict(sequence=1)),scripts=reader(engines={}))
        self.role=SimpleNamespace(primary=primary,view=reader(captured=self.epoch),lifecycle=reader(),script_source=self.code)
        native=reader(lifecycle=dict(activations=2,backgrounds=0,launches=2))
        self.app=SimpleNamespace(now=lambda:self.host,run_id=RUN,sources=(None,native,reader(last={}),reader(last={})))
        self.guard=ChatArchiveReleaseSource.__new__(ChatArchiveReleaseSource)
        self.guard.app,self.guard.role,self.guard.phase,self.guard.expected=self.app,self.role,phase,expected
        self.guard.fresh_phase_final=True;self.guard.last=self.guard.started=None;self.guard.files_absent=lambda:None
        p=patch.object(ChatArchiveReleaseSource,'__call__',self.capture);p.start();self.addCleanup(p.stop)
        self.fence=ChatArchiveUnlinkFence(self.guard)
        self.catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(self.catalog.close_host)
        self.ledger=PrivateFeatureState(self.root/'retirement.json');self.archive=None

    def capture(self,original=None):
        if original is not None:self.guard.current_phase(original);return original
        self.acquisitions+=1;self.guard.started=self.host
        self.code.roots.last=dict(sequence=2*self.acquisitions)
        proof={key:dict(capturedEpochMs=self.epoch) for key in ('primary','view','native','absence','profile')}
        proof['profile'].update(settings=dict(capturedEpochMs=self.epoch),view=dict(capturedEpochMs=self.epoch))
        proof['compiledChat']=dict(before=dict(requestedEpochMs=self.epoch),after=dict(sequence=2*self.acquisitions))
        proof['phase']=self.guard.phase.read(self.guard.expected)['status']
        self.guard.last=deepcopy(proof);self.guard.final(proof);return deepcopy(proof)

    def make(self,count=2,*,indexed=False):
        for index in range(count):
            store=PrivateFeatureState(self.root/f'original-{index:03d}.json');store.write(dict(consumed=index),None)
            self.catalog.add('primary/'+store.path.name,store,store.read())
        def inventory(expected):self.assertEqual(expected,{path for path in self.root.iterdir() if path.name.startswith('original-')})
        self.archive=ChatEvidenceArchive(self.catalog,self.root/'archive',self.ledger,dict(runId=RUN),self.guard,inventory,unlink_fence=self.fence,indexed_verify=indexed)
        self.addCleanup(self.archive.close_host)
        self.addCleanup(lambda:self.archive.directory.chmod(0o700) if self.archive.directory.exists() else None)
        return self.archive

    def test_seventeen_original_unlinks_share_bounded_frames_but_each_has_new_original_phase(self):
        archive=self.make(17);result=archive.retire();cold=completed_archive(archive.directory)
        self.assertEqual(3,result['chatEvidenceArchiveVersion']);self.assertEqual('original-source-16-unlinks-250ms',cold['unlinkPolicy'])
        self.assertEqual(5,self.acquisitions);self.assertEqual(17,len(archive.deleted));self.assertIsNone(self.ledger.read())
        requests=[row['requestId'] for row in self.phases];self.assertEqual(len(requests),len(set(requests)))
        self.assertGreaterEqual(len(requests),17+5);self.assertTrue(archive.complete)

    def test_slow_final_unlink_cas_with_either_frozen_clock_refuses_without_source_refresh_or_unlink(self):
        for native in (False,True):
            with self.subTest(native=native):
                self.setUp();archive=self.make();write=self.ledger.write
                def slow(value,previous):
                    write(value,previous)
                    if value['phase']=='unlink-issued':
                        if native:self.epoch+=2000
                        else:self.host+=2
                self.ledger.write=slow
                with self.assertRaises(NativeUIError):archive.retire()
                self.assertEqual(3,self.acquisitions);self.assertEqual([],archive.deleted)
                self.assertEqual('unlink-issued',self.ledger.read()['phase']);self.assertEqual(2,len(self.catalog.rows))
                self.assertTrue(all(row['store'].path.exists() for row in self.catalog.rows.values()))
                with self.assertRaises(NativeUIError):archive.retire()

    def test_changed_or_retired_actual_phase_after_unlink_intent_keeps_all_originals(self):
        for retired in (False,True):
            with self.subTest(retired=retired):
                self.setUp();archive=self.make();write=self.ledger.write
                def change(value,previous):
                    write(value,previous)
                    if value['phase']=='unlink-issued':
                        if retired:
                            row=self.journal.runs.pop(RUN);row['retiredEpochMs']=self.epoch;self.journal.retired_phases[RUN]=row
                        else:self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
                self.ledger.write=change
                with self.assertRaises((ValueError,NativeUIError)):archive.retire()
                self.assertEqual(3,self.acquisitions);self.assertEqual([],archive.deleted);self.assertTrue(self.fence.failed)
                self.assertTrue(all(row['store'].path.exists() for row in self.catalog.rows.values()))

    def test_mutated_selected_native_packet_or_accepted_reader_cannot_be_freshened_by_http(self):
        for packet in (False,True):
            with self.subTest(packet=packet):
                self.setUp();archive=self.make();write=self.ledger.write
                def mutate(value,previous):
                    write(value,previous)
                    if value['phase']=='unlink-issued':
                        if packet:self.guard.last['primary']['capturedEpochMs']+=1
                        else:self.role.primary.source['draft']=True
                self.ledger.write=mutate
                with self.assertRaises(NativeUIError):archive.retire()
                self.assertEqual(3,self.acquisitions);self.assertEqual([],archive.deleted)

    def test_expired_preintent_window_may_query_again_but_pending_intent_cannot(self):
        token=self.fence.prepare();self.fence.check(token);self.fence.complete(token)
        self.epoch+=251;token=self.fence.prepare();self.assertEqual(2,self.acquisitions)
        self.epoch+=251
        with self.assertRaises(NativeUIError):self.fence.check(token)
        self.assertEqual(2,self.acquisitions)
        with self.assertRaises(NativeUIError):self.fence.prepare()

    def test_last_original_guard_mutation_or_frozen_host_clock_jump_refuses_pending_unlink(self):
        for mutation in (False,True):
            with self.subTest(mutation=mutation):
                self.setUp();token=self.fence.prepare();original=self.role.primary.guard
                def late():
                    if mutation:self.role.primary.source['draft']=True
                    else:self.epoch+=2000
                    return original()
                self.role.primary.guard=late
                with self.assertRaises(NativeUIError):self.fence.check(token)
                self.assertEqual(1,self.acquisitions);self.assertTrue(self.fence.failed)

    def test_slow_final_file_check_after_intent_cannot_refresh_or_unlink_the_original(self):
        archive=self.make();verify=self.catalog.verify
        def slow(row):
            verify(row)
            if self.ledger.read() and self.ledger.read()['phase']=='unlink-issued':self.epoch+=2000
        self.catalog.verify=slow
        with self.assertRaises(NativeUIError):archive.retire()
        self.assertEqual(3,self.acquisitions);self.assertEqual([],archive.deleted)
        self.assertTrue(all(row['store'].path.exists() for row in self.catalog.rows.values()))

    def test_reuse_window_does_not_restart_the_original_full_acquisition_deadline(self):
        capture=self.capture
        def slow(_guard,original=None):
            result=capture(original)
            if original is None:self.epoch+=1400;self.host+=1.4
            return result
        with patch.object(ChatArchiveReleaseSource,'__call__',slow):token=self.fence.prepare()
        self.epoch+=200;self.host+=.2
        with self.assertRaises(NativeUIError):self.fence.check(token)
        self.assertEqual(1,self.acquisitions);self.assertTrue(self.fence.failed)

    def test_phase_change_after_inner_restart_observation_cas_prevents_actual_intent_discard(self):
        restart=restart_seams.RestartInputTests();restart.setUp();self.addCleanup(restart.doCleanups)
        restart.inputs();restart.flow().observe(restart_seams.NEW,restart.new_source)
        store=restart.store
        # Move no journal: this catalog uses the original RestartInputs parent.
        self.catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(self.catalog.close_host)
        self.catalog.add('primary/'+store.path.name,store,store.read())
        self.ledger=PrivateFeatureState(store.path.parent/'retirement.json');directory=store.path.parent/'archive'
        self.catalog.rows['primary/'+store.path.name]['retire']=lambda check:restart.flow().retire(restart_seams.NEW,restart.new_source,before_discard=check)
        write=store.write
        def change(value,previous):
            write(value,previous);self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        store.write=change
        archive=ChatEvidenceArchive(self.catalog,directory,self.ledger,dict(runId=RUN),self.guard,
            lambda expected:self.assertEqual(expected,{store.path} if store.path.exists() else set()),unlink_fence=self.fence)
        self.addCleanup(archive.close_host)
        with self.assertRaises((ValueError,NativeUIError)):archive.retire()
        self.assertEqual('observed',store.read()['phase']);self.assertEqual([],archive.deleted)
        self.assertEqual('unlink-issued',self.ledger.read()['phase']);self.assertEqual(['stop','launch'],restart.calls)

    def test_final_marker_cas_cannot_hide_new_cleanup_phase_after_all_original_unlinks(self):
        archive=self.make();write=self.ledger.write
        def change(value,previous):
            write(value,previous)
            if value['phase']=='complete':self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        self.ledger.write=change
        with self.assertRaises((ValueError,NativeUIError)):archive.retire()
        self.assertEqual('complete',self.ledger.read()['phase']);self.assertFalse(archive.complete)


if __name__=='__main__':unittest.main()
