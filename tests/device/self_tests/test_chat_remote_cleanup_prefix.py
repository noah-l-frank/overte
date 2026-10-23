"""Actual shared cleanup callback/remote host; native and normal-input fixtures are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.remote_cleanup_prefix import ChatRemoteCleanupPrefix,ChatRemoteCleanupSlot
from adapters.chat_journey.remote_actor_return import ChatRemoteActorReturn,ChatRemoteActorPending
from adapters.chat_journey.remote_consumed_sources import ChatRemoteConsumedSources
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.pico4.chat_archive import PicoChatArchivePlan
from adapters.chat_journey.source_chunks import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.engine import Journey
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from self_tests import test_chat_observation_publisher as sources
from adapters.chat_journey.remote_publication import ChatRemotePublication
from self_tests.chat_remote_cleanup_fixture import RemoteActorFixture
from self_tests.chat_cursor_fixture import cleanup


class ChatRemoteCleanupPrefixTests(RemoteActorFixture,unittest.TestCase):
    def setUp(self):
        self.local=sources.ChatObservationPublisherTests();self.local.setUp();self.addCleanup(self.local.doCleanups)
        h=self.local;self.native=h.native;self.directory=h.root;self.slot=ChatRemoteCleanupSlot();self.consumer=None
        self.source=h.flow.w.parent_source;request=self.source.client.request
        def journal_request(path,*args,**kwargs):
            return h.flow.w.journal.snapshot(h.initial.source.run) if path=='/runs/'+h.initial.source.run else request(path,*args,**kwargs)
        self.source.client.request=journal_request
        self.primary=ChatObservationCursor(ChatObservationOwner(self.source,h.flow.flow.initial_roles[0],h.flow.flow.store,
            PrivateFeatureState(self.directory/'remote-primary-initial-observation.json'),stage='initial',monotonic=lambda:self.native.host),
            PrivateFeatureState(self.directory/'remote-primary-cursor.json'))
        self.admission=PrivateFeatureState(self.directory/'actual-remote-parent.json')
        self.parent=dict(picoChatCompositionVersion=6,runId=h.initial.source.run,fixtureUrl=self.source.fixture_url,
            binding=self.primary.scope['binding'],peerBinding=self.primary.scope['peerBinding'],peerOriginBasis='native-configured-metadata-only',
            phase='step-completed',completedSteps=1);self.admission.write(self.parent,None)
        self.stores=dict(actor=PrivateFeatureState(self.directory/'remote-actor.json'),flow=h.flow.flow.store,
            cleanup=PrivateFeatureState(self.directory/'cleanup-admission.json'),publisher=PrivateFeatureState(self.directory/'remote-publisher.json'),
            cursor=PrivateFeatureState(self.directory/'remote-cursor.json'),code=PrivateFeatureState(self.directory/'remote-actor-code.json'))
        for stage in ('initial','active','cleanup'):
            self.stores[stage+'-observation']=PrivateFeatureState(self.directory/('remote-actor-'+stage+'-observation.json'))
            self.stores[stage+'-samples']=PrivateFeatureState(self.directory/(h.flow.flow.scope['baselineTranscripts'][2] if stage=='initial' else
                h.flow.flow.scope['transcripts'][2] if stage=='active' else 'remote-actor-cleanup-samples.json'))
        self.stop_store=PrivateFeatureState(self.directory/'actual-remote-stop.json')
        self.return_stores=dict(stop=self.stop_store,seal=PrivateFeatureState(self.directory/'remote-seal.json'),
            **{'return':PrivateFeatureState(self.directory/'remote-return.json'),'consumption':PrivateFeatureState(self.directory/'remote-consumption.json')})
        locks=self.primary.current.samples.locks
        self.start_actor(h,{**self.stores,**self.return_stores},locks,self.admission)
        self.owner=ChatRemotePublication(self.process,self.source,self.stores,self.expected,locks,
            PrivateFeatureState(self.directory/'actual-remote-publication.json'),peer_epoch_ms=lambda:self.native.epoch,
            guard=lambda:True,monotonic=lambda:self.native.host)
        def no_input(*_args,**_kwargs):raise AssertionError('Direct common wait does not execute missing normal inputs')
        def invoke(operation,fields):
            self.assertEqual('feature.chat.observe',operation)
            return self.primary.read(fields['afterSequence']) if self.consumer is None else self.consumer.observe(fields)
        def received():
            self.command('publish')
            return self.owner.acquire(self.journey.last_actor_sequence)
        self.journey=Journey('chat',self.expected['runId'],self.expected['fixtureUrl'],invoke=invoke,witness=received,
            activate=no_input,read_artifact=no_input,image_policy={},continuity=lambda *_args:None,
            monotonic=lambda:self.native.host,epoch_ms=lambda:self.native.epoch,sleep=self.sleep,report=no_input,
            after_cleanup_baseline=self.slot.callback);self.slot.attach(self.journey)
        self.prefix(SCENARIOS['chat']['baseline'])
        h.flow.next(1);self.parent['completedSteps']=2;self.admission.write(self.parent,self.admission.read());self.command('advance')
        self.primary.select(ChatObservationOwner(self.source,h.flow.roles[0],h.flow.flow.store,
            PrivateFeatureState(self.directory/'remote-primary-active-observation.json'),stage='active',monotonic=lambda:self.native.host))
        self.prefix(SCENARIOS['chat']['steps'][0]['state'])
        primary_cleanup=cleanup(h.h,self.primary);self.parent.update(phase='caches-retired',completedSteps=26)
        self.admission.write(self.parent,self.admission.read());self.command('cleanup');self.primary.select(primary_cleanup)
        self.consumer=ChatRemoteCleanupPrefix(self.primary,self.owner,self.stop_store,
            PrivateFeatureState(self.directory/'actual-remote-cleanup-prefix.json'),guard=lambda:True)
        self.slot.bind(self.consumer);self.ticket=h.flow.w.journal.snapshot(self.expected['runId'])['ticket'];self.barrier=self.native.epoch
        self.cleanup_start=len(self.journey.samples)

    def prefix(self,expected):
        journal=self.local.flow.w.journal.snapshot(self.expected['runId']);ticket=journal['ticket'];barrier=self.native.epoch
        self.journey.wait('actual-prefix-'+str(len(self.journey.phases)),ticket,barrier,
            expand(expected,context(self.expected['runId'])),['peer'],duration=0)

    def sleep(self,seconds):
        self.local.flow.sleep(seconds);self.command('tick',seconds=seconds)

    def wait(self):
        self.journey.wait('cleanup-restored-baseline',self.ticket,self.barrier,deepcopy(SCENARIOS['chat']['baseline']),['peer'],duration=3)

    def test_real_common_baseline_writes_one_consumed_prefix_stop_and_preserves_actual_extra_tail(self):
        self.wait();consumed=self.journey.last_actor_sequence
        self.command('publish');self.command('publish');self.journey.consumed_cleanup(self.ticket,self.barrier,self.cleanup_start)
        self.assertTrue(self.slot.completed);self.assertTrue(self.consumer.completed)
        original=self.stop_store.read();self.assertEqual(consumed,original['consumedSequence'])
        self.assertEqual(digest(self.owner.rows[-1]['publication']['payload']),original['consumedPayloadSha256'])
        self.assertEqual(self.consumer.previous['consumptionSha256'],original['cleanupConsumptionSha256'])
        self.assertFalse(self.consumer.previous['header']['sequenceSucceeded'])
        with self.assertRaises(NativeUIError):self.owner.acquire(consumed)
        self.command('stop');stores={**self.stores,**self.return_stores}
        expected={**self.expected,'stopCommand':original}
        returned=ChatRemoteActorReturn(self.process,stores,expected,PrivateFeatureState(self.directory/'actual-prefix-typed-return.json'))
        self.assertEqual(consumed+2,len(returned.graph.frames['publisher']));returned.acknowledge();self.command('consume')
        with self.assertRaises(ChatRemoteActorPending):returned.finish()
        self.worker.stdin.write(b'{"action":"exit"}\n');self.worker.stdin.flush();self.worker.wait(timeout=5)
        result=returned.finish();self.assertTrue(returned.complete);self.assertEqual('ESRCH',result['result']['processReturn']['processAbsence']['errorSymbol'])
        self.assertEqual(original,self.stop_store.read());self.assertTrue(self.consumer.completed)
        seal=ChatCursorSourceSeal(self.primary,PrivateFeatureState(self.directory/'actual-remote-primary-seal.json'))
        joined=ChatRemoteConsumedSources(self.consumer,returned,seal,PrivateFeatureState(self.directory/'actual-consumed-sources.json'))
        receipt=joined.run();self.assertTrue(joined.completed);self.assertTrue(seal.completed)
        self.assertFalse(receipt['original']['sequenceSucceeded']);self.assertEqual(consumed,receipt['original']['consumedActorSequence'])
        self.assertEqual(consumed+2,receipt['original']['finalActorSequence'])
        self.assertEqual(digest(seal.previous),receipt['primarySealSha256'])
        self.assertEqual(receipt,joined.receipt())
        # Actual immutable catalog acquisition only. Parent path admission is
        # an explicit seam; false direct-wait evidence cannot restart an app.
        plan=PicoChatArchivePlan.__new__(PicoChatArchivePlan);plan.catalog=ChatArchiveCatalog(hold_files=False);plan.archive=None
        self.addCleanup(plan.close_host);plan.target='original-source-catalog'
        plan.state=self.directory/'normal-script-state.json';plan.peer_directory=self.directory/'peer-catalog';plan.peer_directory.mkdir(mode=0o700)
        plan.parent=SimpleNamespace(cache_release=SimpleNamespace(roles=(self.primary.current.samples,)),source=self.source,
            binding=self.expected['binding'],peer=SimpleNamespace(binding=self.expected['peerBinding']))
        plan.adapter=SimpleNamespace(_chat_remote_consumed_sources_store=lambda _target:joined.store,
            _chat_remote_cleanup_prefix_store=lambda _target:self.consumer.store,_chat_remote_publication_store=lambda _target:self.owner.store,
            _chat_remote_actor_return_store=lambda _target:returned.store,_chat_cursor_source_seal_store=lambda _target,**_kw:seal.store)
        metadata=plan.add_remote_consumed_sources(joined);plan.catalog.verify_all()
        self.assertFalse(metadata['chatRemoteSequenceSucceeded'])
        paths={row['store'].path for row in plan.catalog.rows.values()}
        self.assertTrue({store.path for store in {**self.stores,**self.return_stores}.values()}<=paths)
        self.assertTrue({self.owner.store.path,self.consumer.store.path,returned.store.path,joined.store.path,seal.store.path}<=paths)
        self.assertEqual('parent-consumed',plan.catalog.rows['primary/'+self.stores['actor'].path.name]['expected']['phase'])
        self.assertEqual('host-closed',returned.graph.root['phase']);self.assertTrue(all(path.exists() for path in paths))

    def test_last_stop_intent_cas_native_jump_with_frozen_host_prevents_actual_stop_write(self):
        self.wait();write=self.consumer.store.write;writes=[];stop_write=self.stop_store.write
        def actual_stop(value,previous):writes.append(value);return stop_write(value,previous)
        self.stop_store.write=actual_stop
        def delayed(value,previous):
            write(value,previous)
            if value['phase']=='stop-issued':self.native.epoch+=2000
        self.consumer.store.write=delayed
        with self.assertRaises(NativeUIError):
            self.journey.consumed_cleanup(self.ticket,self.barrier,self.cleanup_start)
        self.assertTrue(self.slot.failed);self.assertFalse(self.slot.completed);self.assertFalse(self.consumer.completed)
        self.assertTrue(self.owner.failed);self.assertTrue(self.primary.failed);self.assertEqual([],writes)
        self.assertIsNone(self.stop_store.read());self.assertEqual('stop-issued',self.consumer.store.read()['phase'])
        with self.assertRaises(NativeUIError):self.slot.consume(self.journey.cleanup_consumption)
        self.assertEqual([],writes)

    def test_lost_actual_stop_write_retains_exact_intent_and_never_resends(self):
        self.wait();write=self.stop_store.write;attempts=[]
        def lost(value,previous):
            attempts.append(value);write(value,previous);raise OSError('Original Stop2 write reply lost')
        self.stop_store.write=lost
        with self.assertRaises(NativeUIError):
            self.journey.consumed_cleanup(self.ticket,self.barrier,self.cleanup_start)
        self.assertTrue(self.slot.failed);self.assertFalse(self.slot.completed);self.assertFalse(self.consumer.completed)
        self.assertEqual(1,len(attempts));self.assertEqual(self.consumer.command,self.stop_store.read())
        self.assertEqual('stop-issued',self.consumer.store.read()['phase'])
        with self.assertRaises(NativeUIError):self.consumer.consume(self.journey.cleanup_consumption)
        self.assertEqual(1,len(attempts))

    def test_uncalled_common_hook_and_replaced_parent_root_cannot_query_or_write_stop(self):
        primary_count=len(self.primary.rows);remote_count=len(self.owner.rows)
        current=self.consumer.store.read();self.consumer.store.write(current,current)
        with self.assertRaises(NativeUIError):self.journey.observe(self.ticket,self.barrier)
        self.assertTrue(self.consumer.failed);self.assertEqual(primary_count,len(self.primary.rows));self.assertEqual(remote_count,len(self.owner.rows))
        self.assertIsNone(self.stop_store.read())
        with self.assertRaises(NativeUIError):self.slot.consume(b'{"sequenceSucceeded":true}')
        self.assertTrue(self.slot.failed);self.assertFalse(self.slot.completed);self.assertIsNone(self.stop_store.read())

    def test_unconsumed_real_prefix_cannot_construct_source_return_join(self):
        store=PrivateFeatureState(self.directory/'premature-consumed-sources.json')
        before=len(self.primary.rows),len(self.owner.rows)
        with self.assertRaises(NativeUIError):ChatRemoteConsumedSources(self.consumer,object(),object(),store)
        self.assertIsNone(store.read());self.assertEqual(before,(len(self.primary.rows),len(self.owner.rows)))

if __name__=='__main__':unittest.main()
