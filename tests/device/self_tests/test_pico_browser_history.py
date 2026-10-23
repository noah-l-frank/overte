"""Retain real coordinator transactions at explicit native/HTTP producer seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_tablet_web_feature as seams


class PicoBrowserHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=seams.PicoTabletWebFeatureTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.flow=self.fixture.flow();self.flow.prepare()
        self.call=dict(contractVersion=VERSION,runId=seams.RUN,afterSequence=0)

    def history(self,flow):
        return flow.source_history(flow.owner())

    def test_original_sources_and_both_actor_publication_events_survive_cold_read_without_query(self):
        sample=self.flow.observe(self.call);actor=self.fixture.flow(actor=True);actor.publish()
        commands=len(self.fixture.original.commands)
        for flow,count in ((self.fixture.flow(),1),(self.fixture.flow(actor=True),3)):
            with flow.lock.held():
                state=flow.role_state();history=self.history(flow);history.matches(state)
                self.assertEqual(count,len(history.rows));self.assertEqual(sample['state'],history.last['sample']['state'])
                self.assertEqual(history.last['phaseBefore']['activations'],history.last['phaseAfter']['activations'])
                self.assertEqual({'nativeBefore','nativeAfter','native','runtime','browser','diagnostic'},
                    set(history.last)&{'nativeBefore','nativeAfter','native','runtime','browser','diagnostic'})
                if count==3:
                    self.assertEqual(['sample','publication-intent','publication-accepted'],[row['event'] for row in history.rows])
                    self.assertEqual({},history.rows[-1]['original']['ack'])
        self.assertEqual(commands,len(self.fixture.original.commands))

    def test_lost_original_source_keeps_reading_intent_and_blocks_cold_query(self):
        with patch.object(self.flow,'sample_native',side_effect=NativeUIError('Original reply lost')):
            with self.assertRaises((ValueError,RuntimeError)):self.flow.observe(self.call)
        with self.flow.lock.held():
            history=self.history(self.flow);self.assertEqual('reading',history.disk['phase'])
        commands=len(self.fixture.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow().observe(self.call)
        self.assertEqual(commands,len(self.fixture.original.commands))

    def test_lost_child_root_cas_retains_complete_orphan_and_cannot_adopt_it(self):
        with self.flow.lock.held():history=self.history(self.flow)
        write=history.store.write
        def lost(value,previous):
            if value['phase']=='ready':raise NativeUIError('Root write lost')
            write(value,previous)
        with patch.object(history.store,'write',side_effect=lost),self.assertRaises((ValueError,RuntimeError)):self.flow.observe(self.call)
        child=history.chunks.store(0);raw=child.path.read_bytes();commands=len(self.fixture.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow().observe(self.call)
        self.assertEqual(raw,child.path.read_bytes());self.assertEqual(commands,len(self.fixture.original.commands))

    def test_missing_historical_root_with_existing_role_cannot_continue_or_resend(self):
        self.flow.observe(self.call)
        with self.flow.lock.held():history=self.history(self.flow)
        history.store.path.unlink();commands=len(self.fixture.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow().observe(self.call)
        self.assertEqual(commands,len(self.fixture.original.commands))

    def test_cached_source_mutation_and_identical_replaced_child_are_refused(self):
        self.flow.observe(self.call)
        with self.flow.lock.held():
            history=self.history(self.flow);history.last['native']['sequence']+=1
            with self.assertRaises((ValueError,RuntimeError)):history.verify()
        cold=self.fixture.flow()
        with cold.lock.held():
            history=self.history(cold);child=history.chunks.store(0).path
            replacement=child.with_name('replacement');replacement.write_bytes(child.read_bytes());replacement.chmod(0o600)
            replacement.replace(child)
            with self.assertRaises((ValueError,RuntimeError)):history.verify()

    def test_historical_validation_rejects_changed_effect_birth_clock_phase_and_actor_receipt(self):
        self.flow.observe(self.call)
        with self.flow.lock.held():
            history=self.history(self.flow);original=deepcopy(history.last)
            def effect(frame):frame['sample']['state']['open']=True
            def birth(frame):frame['nativeAfter']['instance']='9'*32
            def clock(frame):frame['finishedEpoch']+=2000
            def phase(frame):frame['phaseAfter']['activations'][-1]['ticket']='9'*32
            def source(frame):frame['native']['runId']='9'*32
            def service(frame):frame['diagnostic']['complete']=False
            for mutate in (effect,birth,clock,phase,source,service):
                frame=deepcopy(original);mutate(frame)
                with self.subTest(mutate=mutate.__name__),self.assertRaises((ValueError,RuntimeError)):
                    self.flow.validate_original_sample(frame,None)
        actor=self.fixture.flow(actor=True);actor.publish()
        with actor.lock.held():
            history=self.history(actor);row=deepcopy(history.rows[-1]);row['original']['ack']={'accepted':True}
            with self.assertRaises((ValueError,RuntimeError)):history.admit(row)

    def test_history_final_cas_cannot_renew_previous_phase_or_stale_sources(self):
        with self.flow.lock.held():history=self.history(self.flow)
        write=history.store.write
        def late(value,previous):
            write(value,previous)
            if value['phase']=='ready':self.fixture.journal.activate(seams.RUN,'9'*32)
        with patch.object(history.store,'write',side_effect=late),self.assertRaises((ValueError,RuntimeError)):self.flow.observe(self.call)
        self.assertEqual('ready',history.store.read()['phase']);self.assertEqual([],self.fixture.publications)

    def stalled_history(self,*,actor,native):
        flow=self.fixture.flow(actor=actor)
        with flow.lock.held():history=self.history(flow)
        write=history.store.write
        def late(value,previous):
            write(value,previous)
            if value['phase']=='ready' and (not actor or history.publication is not None):
                if native:self.fixture.original.epoch+=2000
                else:self.fixture.original.host+=2
        with patch.object(history.store,'write',side_effect=late),self.assertRaises((ValueError,RuntimeError)):
            if actor:flow.publish()
            else:flow.observe(self.call)
        self.assertEqual([],self.fixture.publications)
        if actor:
            self.assertEqual('issued',history.publication['phase'])
            commands=len(self.fixture.original.commands)
            with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow(actor=True).publish()
            self.assertEqual(commands,len(self.fixture.original.commands))

    def test_final_history_write_host_delay_cannot_return_old_primary_sources(self):
        self.stalled_history(actor=False,native=False)

    def test_final_history_write_native_jump_cannot_return_old_primary_sources(self):
        self.stalled_history(actor=False,native=True)

    def test_actor_history_intent_host_delay_cannot_publish_or_cold_resend(self):
        self.stalled_history(actor=True,native=False)

    def test_actor_history_intent_native_jump_cannot_publish_or_cold_resend(self):
        self.stalled_history(actor=True,native=True)

    def test_lost_publication_reply_retains_original_payload_without_accepted_ack_or_resend(self):
        actor=self.fixture.flow(actor=True);self.fixture.lose_pub=True
        with self.assertRaises((ValueError,RuntimeError)):actor.publish()
        with actor.lock.held():
            history=self.history(actor);self.assertEqual(['sample','publication-intent'],[row['event'] for row in history.rows])
            self.assertIsNone(history.rows[-1]['original']['ack']);history.matches(actor.role_state())
        commands=len(self.fixture.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow(actor=True).publish()
        self.assertEqual(1,len(self.fixture.publications));self.assertEqual(commands,len(self.fixture.original.commands))

    def test_changed_role_result_cannot_be_adopted_as_original_history(self):
        self.flow.observe(self.call)
        with self.flow.lock.held():
            state=self.flow.role_state();state['last']['state']['open']=True
            self.flow.write(self.flow.role_store,self.flow.role,state)
        commands=len(self.fixture.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow().observe(self.call)
        self.assertEqual(commands,len(self.fixture.original.commands))

    def test_immutable_prefix_exposes_only_copies_and_replaced_cached_tuple_refuses(self):
        self.flow.observe(self.call)
        with self.flow.lock.held():
            history=self.history(self.flow);copies=history.rows;copies[0]['original']['native']['sequence']+=1
            history.verify();self.assertNotEqual(copies,history.rows)
            history._rows=history._rows+(b'{}',)
            with self.assertRaises((ValueError,RuntimeError)):history.verify()

    def test_changed_original_after_last_target_guard_cannot_escape_final_file_check(self):
        with self.flow.lock.held():history=self.history(self.flow)
        runtime=self.flow.runtime;changed=[]
        def mutate(owner):
            answer=runtime(owner)
            if history.disk is not None and history.disk['phase']=='ready' and not changed:
                changed.append(True);child=history.chunks.store(0).path
                replacement=child.with_name('late-replacement');replacement.write_bytes(child.read_bytes());replacement.chmod(0o600)
                replacement.replace(child)
            return answer
        with patch.object(self.flow,'runtime',side_effect=mutate),self.assertRaises((ValueError,RuntimeError)):
            self.flow.observe(self.call)
        self.assertEqual([True],changed)

    def test_pending_primary_query_or_actor_publication_blocks_next_normal_input(self):
        with patch.object(self.flow,'sample_native',side_effect=NativeUIError('Original reply lost')):
            with self.assertRaises((ValueError,RuntimeError)):self.flow.observe(self.call)
        self.fixture.journal.activate(seams.RUN,'9'*32)
        call=dict(contractVersion=VERSION,runId=seams.RUN,fixtureUrl=seams.URL,ticket='9'*32,verb='open',inputs={})
        delivered=[];cold=self.fixture.flow()
        with patch.object(cold,'deliver',side_effect=lambda *_:delivered.append(True)),self.assertRaises((ValueError,RuntimeError)):
            cold.act(call)
        self.assertEqual([],delivered)

    def test_lost_actor_publication_blocks_new_primary_input_without_repeating_actor_payload(self):
        self.flow.observe(self.call);self.fixture.lose_pub=True
        with self.assertRaises((ValueError,RuntimeError)):self.fixture.flow(actor=True).publish()
        self.fixture.journal.activate(seams.RUN,'9'*32)
        call=dict(contractVersion=VERSION,runId=seams.RUN,fixtureUrl=seams.URL,ticket='9'*32,verb='open',inputs={})
        delivered=[]
        with patch.object(self.flow,'deliver',side_effect=lambda *_:delivered.append(True)),self.assertRaises((ValueError,RuntimeError)):
            self.flow.act(call)
        self.assertEqual([],delivered);self.assertEqual(1,len(self.fixture.publications))


if __name__=='__main__':unittest.main()
