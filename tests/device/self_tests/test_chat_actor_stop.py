"""Closed Stop versions; one actual source tail, no claimed external consume."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
import uuid

from adapters.chat_journey.actor_stop import shape,validate,publication_return,validate_publication_return
from adapters.chat_journey.source_chunks import digest
from adapters.normal_ui import NativeUIError


class ChatActorStopGrammarTests(unittest.TestCase):
    def setUp(self):
        self.instance,self.run,self.ticket=(uuid.uuid4().hex for _ in range(3))
        self.rows=[dict(payload=dict(ticket=self.ticket,actorSequence=index+1,facts=dict(explicitGrammarSeam=True))) for index in range(3)]
        self.value=dict(picoChatCursorActorStopVersion=2,commandId=uuid.uuid4().hex,instance=self.instance,runId=self.run,
            ticket=self.ticket,consumedSequence=2,consumedPayloadSha256=digest(self.rows[1]['payload']),cleanupConsumptionSha256='d'*64)

    def check(self,value=None,rows=None):
        return validate(self.value if value is None else value,instance=self.instance,run=self.run,published=self.rows if rows is None else rows)

    def test_v2_pins_actual_requested_prefix_and_keeps_extra_same_phase_publications(self):
        original=deepcopy(self.rows);self.assertEqual(2,self.check());self.assertEqual(original,self.rows)
        self.assertEqual(3,len(self.rows));self.assertEqual(2,self.value['consumedSequence'])

    def test_legacy_v1_still_requires_exact_current_sequence(self):
        old={key:value for key,value in self.value.items() if key not in ('consumedSequence','consumedPayloadSha256','cleanupConsumptionSha256')}
        old.update(picoChatCursorActorStopVersion=1,afterSequence=2)
        with self.assertRaises(NativeUIError):self.check(old)
        old['afterSequence']=3;self.assertEqual(1,self.check(old))

    def test_wrong_prefix_hash_future_sequence_or_foreign_tail_never_becomes_requested_prefix(self):
        for changes in (dict(consumedSequence=4),dict(consumedSequence=0),dict(consumedSequence=True),dict(consumedPayloadSha256='e'*64),
            dict(ticket=uuid.uuid4().hex),dict(instance=uuid.uuid4().hex),dict(runId=uuid.uuid4().hex)):
            with self.subTest(changes=changes),self.assertRaises((NativeUIError,ValueError)):self.check({**self.value,**changes})
        rows=deepcopy(self.rows);rows[2]['payload']['ticket']=uuid.uuid4().hex
        with self.assertRaises(NativeUIError):self.check(rows=rows)
        rows=deepcopy(self.rows);rows[1]['payload']['ticket']=uuid.uuid4().hex
        value={**self.value,'consumedPayloadSha256':digest(rows[1]['payload'])}
        with self.assertRaises(NativeUIError):self.check(value,rows)

    def test_versions_fields_and_raw_hash_types_are_closed(self):
        for changes in (dict(afterSequence=3),dict(consumedPayloadSha256=True),dict(cleanupConsumptionSha256='D'*64),
            dict(picoChatCursorActorStopVersion=True),dict(picoChatCursorActorStopVersion=3),dict(success=True)):
            with self.subTest(changes=changes),self.assertRaises((NativeUIError,ValueError)):shape({**self.value,**changes})

    def test_publication_return_pins_original_roots_stamps_and_builtin_types(self):
        publisher,cursor=dict(phase='ready',chunks=['a']),dict(phase='ready',chunks=['b'])
        stamps=[dict(dev=1,ino=2),dict(dev=3,ino=4)]
        row=dict(sequence=1,payload=self.rows[0]['payload']);rows=[row]
        proof=publication_return(1,row,publisher,cursor,*stamps)
        def check(value):
            validate_publication_return(value,publisher=publisher,cursor=cursor,rows=rows,
                publisher_stamp=stamps[0],cursor_stamp=stamps[1])
        check(proof)
        for changed in ({**proof,'sequence':True},{**proof,'publisherStamp':dict(dev=True,ino=2)},
            {**proof,'publisherStamp':dict(dev=1.0,ino=2)},{**proof,'cursorSha256':'e'*64},
            {**proof,'publisherStamp':('same canonical JSON is not a builtin stamp',)}):
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):check(changed)


class ChatActorStopSourceTests(unittest.TestCase):
    def original(self):
        from self_tests import test_pico_chat_cursor_actor as fixture
        h=fixture.PicoChatCursorActorTests();h.defer_stop_command=True;h.setUp();self.addCleanup(h.doCleanups)
        return h

    def test_pending_input_and_unacquired_source_locks_never_query_foreground_or_quarantine(self):
        from contextlib import contextmanager
        from adapters.script_journey.lock import ScriptSourceBusy
        from feature_journeys.phase_fixture import PhasePending
        h=self.original();actor=h.actor;before=h.h.queries();posts=len(h.h.posts);held=actor.held
        def forbidden(*_args):raise AssertionError('Pending original input cannot query a target/foreground')
        actor.original.native.guard=actor.original.peer.guard=forbidden;actor.adapter._scripts=forbidden
        def phase(value):
            h.parent.update(phase=value,completedSteps=25 if value=='step-issued' else 26)
            h.parent_store.write(h.parent,h.parent_store.read())
        phase('step-issued')
        with self.assertRaises(PhasePending):actor.publish()
        phase('caches-retired')
        def busy():raise ScriptSourceBusy('Original Parent holds source lock')
        actor.held=busy
        with self.assertRaises(PhasePending):actor.publish()
        @contextmanager
        def raced():
            with held():phase('step-issued');yield
        actor.held=raced
        with self.assertRaises(PhasePending):actor.publish()
        self.assertFalse(actor.failed);self.assertFalse(actor.publisher.failed);self.assertFalse(actor.publisher.cursor.failed)
        self.assertEqual(before,h.h.queries());self.assertEqual(posts,len(h.h.posts))

    def test_actual_outer_lock_exit_failure_latches_after_original_publication_return(self):
        from contextlib import contextmanager
        h=self.original();actor=h.actor;held=actor.held;posts=len(h.h.posts)
        @contextmanager
        def lost():
            with held():yield
            raise OSError('Actual outer source lock exit failed')
        actor.held=lost
        with self.assertRaises(NativeUIError):actor.publish()
        self.assertTrue(actor.failed);self.assertTrue(actor.publisher.failed)
        self.assertEqual(posts+1,len(h.h.posts));self.assertEqual(len(actor.publisher.rows),actor.store.read()['returnedPublication']['sequence'])
        before=h.h.queries()
        with self.assertRaises(NativeUIError):actor.publish()
        with self.assertRaises(NativeUIError):actor.stop_once()
        self.assertEqual(before,h.h.queries());self.assertEqual(posts+1,len(h.h.posts))

    def test_final_original_owner_cas_cannot_refresh_frozen_native_age(self):
        h=self.original();actor=h.actor;write=actor.store.write;posts=len(h.h.posts)
        def late(value,previous):
            write(value,previous);h.h.native.epoch+=2000
        actor.store.write=late
        with self.assertRaises(NativeUIError):actor.publish()
        self.assertTrue(actor.failed);self.assertFalse(actor.closed);self.assertEqual(posts+1,len(h.h.posts))
        before=h.h.queries()
        with self.assertRaises(NativeUIError):actor.publish()
        self.assertEqual(before,h.h.queries())

    def test_actual_extra_queries_stay_original_in_seal_after_requested_cleanup_prefix(self):
        from adapters.chat_journey.remote_actor_graph import ChatRemoteActorGraph
        from adapters.chat_journey.evidence_archive import stamp
        # Reuse original source/command setup with no existing Stop intent.
        h=self.original()
        actor=h.actor;minimum=len(actor.publisher.rows);payload=deepcopy(actor.publisher.rows[-1]['payload'])
        self.assertIsNone(actor.stop_store.read());actor.publish();actor.publish()
        command=dict(picoChatCursorActorStopVersion=2,commandId=uuid.uuid4().hex,instance=actor.scope['instance'],
            runId=actor.source.run,ticket=payload['ticket'],consumedSequence=minimum,consumedPayloadSha256=digest(payload),
            cleanupConsumptionSha256=hashlib.sha256(b'explicit external-consumption provenance seam').hexdigest())
        actor.stop_store.write(command,None);before=h.h.queries();posts=len(h.h.posts);result=actor.stop_once()
        self.assertTrue(actor.closed);self.assertEqual(minimum+2,len(actor.publisher.rows));self.assertEqual(command,result['stopCommand'])
        self.assertEqual(minimum+2,actor.seal_receipt['originals'][0]['chunkCount'])
        self.assertEqual(before,h.h.queries());self.assertEqual(posts,len(h.h.posts))
        stores=dict(actor=actor.store,stop=actor.stop_store,seal=actor.seal.store,
            flow=actor.publisher.observation.flow_store,cleanup=actor.publisher.observation.cleanup_store,
            publisher=actor.publisher.store,cursor=actor.publisher.cursor.store,code=actor.publisher.observation.samples.script_source.store)
        for owner in actor.publisher.cursor.owners:
            stores[owner.stage+'-observation']=owner.store;stores[owner.stage+'-samples']=owner.samples.store
        expected={key:deepcopy(result[key]) for key in ('runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance','stopCommand')}
        graph=ChatRemoteActorGraph(actor.store.path.read_bytes(),stamp(actor.store.path.lstat()),stores,expected);self.assertTrue(graph.pending)
        self.assertEqual(minimum+2,len(graph.frames['publisher']));self.assertEqual(2,graph.root['stopCommand']['picoChatCursorActorStopVersion'])


if __name__=='__main__':unittest.main()
