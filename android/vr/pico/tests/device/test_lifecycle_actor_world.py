"""Actual normal World3 envelopes and independent Actor source effects.

Common source/peer checks run unchanged. Required image checkpoint3, native
Qt/SDK/GPU execution, later actions and complete feature closure stay open.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.archive_file import signature
from adapters.pico4.lifecycle_actor_originals import ActorOriginals
from adapters.pico4.lifecycle_actor_storage import decode_snapshot
from adapters.pico4.lifecycle_world_codec import pack,owner_payload
from adapters.script_journey.history import canonical,MAX_RAW
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
import test_lifecycle_actor_operations as operations_fixture


class LifecycleActorWorldTests(unittest.TestCase):
    baseline=operations_fixture.LifecycleActorOperationsTests.baseline
    fields=operations_fixture.LifecycleActorOperationsTests.fields

    def setUp(self):
        self.stage=operations_fixture.composition_fixture.LifecycleActorCompositionTests()
        self.stage.setUp();self.addCleanup(self.stage.doCleanups)
        self.graph=operations_fixture.CanonicalLifecycleOperationGraph(self,self.stage)
        before=self.stage.configuration.read()
        self.stage.configuration.write(dict(before,traceWorldOwnership=True),before);self.stage.start()

    def act(self,index):
        fields=self.fields(index);self.graph.journey.required_lifecycle=self.graph.journey.lifecycle.copy()
        # Mirror the existing Common Engine's lifecycle assertion before the
        # real input. Actual samples still have to prove these native deltas.
        if fields['verb']=='background-resume':
            self.graph.journey.required_lifecycle['backgrounds']+=1
            self.graph.journey.required_lifecycle['activations']+=1
        self.graph.journey.continuity('before',fields['verb']);self.graph.journey.call('act',fields)
        self.graph.journey.continuity('after',fields['verb']);return fields

    def test_actual_common_source_prefix_includes_normal_world_attempt_from_own_native_events(self):
        self.baseline()
        before_back=None
        for index in range(7):
            fields=self.act(index);barrier=self.stage.native.epoch()
            expected=expand(SCENARIOS['lifecycle-input']['steps'][index]['state'],context(self.stage.run))
            self.graph.journey.wait('canonical-source-world-'+str(index+1),fields['ticket'],barrier,expected,['peer'])
            if index==2:
                before_back=(self.graph.world.store.path.read_bytes(),signature(self.graph.world.store.path.stat()))
        self.assertEqual(7,len(self.graph.operations.state['steps']))
        self.assertEqual(1,len(self.graph.world.state['attempts']))
        self.assertEqual('quiet',self.graph.world.state['attempts'][0]['phase'])
        self.assertEqual(3,len(self.stage.editor.transport.envelopes)) # Tablet + World + original physical Back.
        self.assertEqual(1,self.stage.editor.transport.back_count)
        self.assertEqual('retained',self.graph.joined.back.state['phase'])
        self.assertEqual(self.stage.editor.transport.neutral_epoch,
                         self.graph.joined.back.state['neutral']['updatedEpochMs'])
        passive=ActorOriginals(PrivateFeatureState(self.stage.root/'lifecycle-actor-originals.json'))
        self.assertEqual(24,len(passive.root['records']));owned=[]
        for index in range(24):
            group=passive.group(index);root,entries=decode_snapshot(group['staging'])
            self.assertEqual(2,root['actorStagingVersion'])
            for entry in entries:
                if entry['key']=='world-owner':owned.append((index,root,entry['value']))
        self.assertEqual(1,len(owned));index,staging,original=owned[0]
        self.assertEqual(1,self.stage.products.world_history_decodes)
        self.assertEqual(9,index);raw=base64.b64decode(original['rawBase64'],validate=True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),original['sha256'])
        self.assertEqual(before_back[0],raw)
        self.assertEqual(before_back[1],original['physical'])
        self.assertEqual(self.stage.editor.session.profile,original['profile'])
        self.assertEqual(hashlib.sha256(canonical(original['profile'])).hexdigest(),original['profileSha256'])
        self.assertEqual(json.loads(raw)['payload']['bytes'],staging['nestedDecodedBytes'])
        for index,row in enumerate(passive.root['records'][9:],9):
            group=passive.native(row['native'],record=index)
            facts=group['record']['publication']['facts']
            self.assertEqual(1,facts['worldAttempts']);self.assertEqual(0,facts['worldDisplacement'])
            self.assertEqual([],facts['heldInputs']);self.assertEqual(10,group['record']['worldOwnershipActorSequence'])
            if 12<=index<15:
                self.assertEqual('none',facts['editor']);self.assertEqual('',facts['text'])
                self.assertFalse(facts['focused']);self.assertFalse(facts['keyboard'])
                self.assertEqual(0,facts['generation'])
            elif index>=15:
                self.assertEqual('chat',facts['editor']);self.assertEqual(2,facts['generation'])
                self.assertEqual(index<21,facts['focused']);self.assertEqual(index<21,facts['keyboard'])
                self.assertEqual('' if index<18 else self.stage.editor.chat.draft,facts['text'])
        chat=self.graph.operations.children['chat']
        self.assertIs(chat,self.graph.source.chat)
        self.assertIs(chat.joined,self.graph.joined)
        self.assertNotEqual(self.stage.editor.owner.state['originalId'],chat.state['originalId'])
        self.assertEqual('typed',chat.state['phase']);self.assertEqual([],self.stage.editor.chat.sent)
        self.assertEqual([],self.stage.editor.chat.local);self.assertEqual([],self.stage.editor.chat.domain)
        background=self.graph.operations.children['background'];model=self.stage.editor.background
        self.assertIs(background,self.graph.source.background)
        self.assertEqual('released',background.state['phase']);self.assertFalse(model.history.active)
        self.assertTrue(model.history.released)
        self.assertEqual(['lifecycle.background','app.launch'],[row['operation'] for row in model.inputs])
        self.assertEqual(['arm','release'],[row['operation'] for row in model.history.commands if row['operation']!='observe'])
        self.assertEqual([],model.rejected_queries)
        self.assertLessEqual(passive.root['decodedSourceBytes'],MAX_RAW)
        self.assertEqual([['gesture','drive','ui','pending','feature','subject']]*24,self.graph.actor_query_deltas)
        self.assertTrue(all(sample['witness'] is not None for sample in self.graph.journey.samples))
        self.stage.command('exit');self.stage.worker.wait(timeout=10);self.assertEqual(0,self.stage.worker.returncode)
        absent=self.stage.process.require_absent();self.stage.process.final_absence(absent)
        bill=self.stage.last_worker['sourceStorage']
        report=dict(lifecycleActorWorldSourceVersion=1,sourceVersion=2,stagingVersion=2,
            originalNormalActions=7,actorSourceGroups=24,actorSixSourceQueries=144,
            sharedNativeQueries=len(self.stage.native_calls()),primaryNativeQueries=len(self.stage.native_calls())-144,
            originalBackgroundQueries=len(model.history.commands),
            originalWorldHistoryDecodes=self.stage.products.world_history_decodes,
            originalWorldNestedDecodedBytes=staging['nestedDecodedBytes'],
            originalWorldRootBytes=len(raw),originalProfileBytes=len(canonical(original['profile'])),
            actorMainParts=len(passive.root['chunks']),actorMainRootBytes=len(passive.raw),
            actorDecodedSourceBytes=passive.root['decodedSourceBytes'],highwater=bill,
            requiredImageCheckpoint3Proved=False,full16StepEffectsProved=False,
            nativeQtSdkPhysics='existing declared fixture models',actualWorkerExitCode=0)
        PrivateFeatureState(self.stage.root/'lifecycle-actor-world-source-diagnostics.json').write(report,None)
        with self.graph.operations.lock.held():
            self.graph.operations.archive(dict(commonWorldSourceConsumptionVersion=1,
                phases=deepcopy(self.graph.journey.phases),samples=deepcopy(self.graph.journey.samples),
                actorQueryDeltas=deepcopy(self.graph.actor_query_deltas)))
        print('World3 source actual bill: '+canonical(report).decode(),flush=True)
        print('World3 original Parent envelope + independent Actor source graph: '+str(self.stage.root),flush=True)


class LifecycleActorWorldCounters(unittest.TestCase):
    setUp=LifecycleActorWorldTests.setUp
    baseline=LifecycleActorWorldTests.baseline
    fields=LifecycleActorWorldTests.fields
    act=LifecycleActorWorldTests.act

    def primed(self):
        self.baseline()
        for index in range(3):self.act(index)

    def original(self):return ActorOriginals(PrivateFeatureState(self.stage.root/'lifecycle-actor-originals.json'))

    def test_original_own_gesture_must_match_authorized_envelope_not_parent_receipt_count(self):
        self.primed()
        started=next(row for row in self.stage.native.axes.source['events'] if row['kind']=='started')
        stream=json.loads(started['stream']['raw']);stream['acceptedNonce']='f'*64
        raw=json.dumps(stream);started['stream']=dict(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())
        before=len(self.stage.native_calls());self.stage.failed_worker()
        self.assertEqual(['gesture','drive','ui','pending','feature','subject'],self.stage.native_calls()[before:])
        self.assertEqual(1,self.stage.products.world_history_decodes)
        original=self.original();self.assertEqual(3,len(original.root['records']))
        observed=json.loads(original.last('gesture')['original']['raw'])
        actual=next(row for row in observed['source']['events'] if row['kind']=='started')
        self.assertEqual('f'*64,json.loads(actual['stream']['raw'])['acceptedNonce'])
        self.assertEqual(3,len(self.stage.client.observe()['entries']))
        self.assertEqual(2,len(self.stage.editor.transport.envelopes))

    def test_foreign_world_binding_keeps_full_profile_and_raw_before_any_actor_target_query(self):
        self.primed();store=self.graph.world.store;previous=store.read();bad=deepcopy(previous)
        bad['binding']['sessionId']='foreign-original-session';store.write(bad,previous)
        before=deepcopy(self.stage.native_calls());self.stage.failed_worker()
        self.assertEqual(before,self.stage.native_calls());self.assertEqual(1,self.stage.products.world_history_decodes)
        original=self.original();value=original.last('world-owner')
        self.assertEqual(store.path.read_bytes(),base64.b64decode(value['rawBase64'],validate=True))
        self.assertEqual(self.stage.editor.session.profile,value['profile'])
        self.assertEqual(hashlib.sha256(canonical(value['profile'])).hexdigest(),value['profileSha256'])
        self.assertEqual(3,len(original.root['records']));self.assertEqual(3,len(self.stage.client.observe()['entries']))

    def test_nested_ownership_budget_fails_before_history_decode_or_next_actor_target_query(self):
        self.primed();store=self.graph.world.store;previous=store.read();bad=deepcopy(previous)
        bad['payload']['bytes']=MAX_RAW;store.write(bad,previous)
        before=deepcopy(self.stage.native_calls());self.stage.failed_worker()
        self.assertEqual(before,self.stage.native_calls());self.assertEqual(0,self.stage.products.world_history_decodes)
        value=self.original().last('world-owner')
        self.assertEqual(store.path.read_bytes(),base64.b64decode(value['rawBase64'],validate=True))
        self.assertEqual(3,len(self.stage.client.observe()['entries']));self.assertEqual(2,len(self.stage.editor.transport.envelopes))


class LifecycleActorBackChatCounters(unittest.TestCase):
    setUp=LifecycleActorWorldTests.setUp
    baseline=LifecycleActorWorldTests.baseline
    fields=LifecycleActorWorldTests.fields
    act=LifecycleActorWorldTests.act
    primed=LifecycleActorWorldCounters.primed
    original=LifecycleActorWorldCounters.original

    def actual_actor_facts(self):
        self.stage.sample();original=self.original();index=len(original.root['records'])-1
        row=original.root['records'][index]
        return original.native(row['native'],record=index)['record']['publication']['facts']

    def no_replay(self):
        self.assertTrue(self.graph.operations.failed)
        self.assertEqual('issued',self.graph.operations.state['steps'][-1]['phase'])
        native=self.stage.editor;before=(deepcopy(native.os.inputs),deepcopy(native.transport.envelopes))
        request=deepcopy(self.graph.calls[-1][1])
        with self.assertRaises(NativeUIError):
            self.graph.operations.invoke('feature.lifecycle-input.act',request)
        self.assertEqual(before,(native.os.inputs,native.transport.envelopes))

    def test_actual_back_with_lost_ack_is_observed_independently_but_parent_stays_pending(self):
        self.primed();self.stage.editor.transport.fail='back-grant'
        with self.assertRaises(NativeUIError):self.act(3)
        self.assertEqual(1,self.stage.editor.transport.back_count);self.no_replay()
        self.assertEqual('enveloped',self.graph.joined.back.state['phase'])
        facts=self.actual_actor_facts()
        self.assertEqual('none',facts['editor']);self.assertFalse(facts['focused']);self.assertFalse(facts['keyboard'])
        self.assertEqual(0,facts['generation']);self.assertEqual(1,facts['worldAttempts'])
        self.assertEqual(1,self.stage.editor.transport.back_count)

    def test_acknowledged_back_without_actual_home_stays_pending_without_another_press(self):
        self.primed()
        with patch.object(self.stage.editor.native,'retire',return_value=None):
            with self.assertRaises(NativeUIError):self.act(3)
        self.no_replay();self.assertEqual(1,self.stage.editor.transport.back_count)
        facts=self.actual_actor_facts()
        self.assertEqual('create',facts['editor']);self.assertTrue(facts['focused']);self.assertTrue(facts['keyboard'])
        self.assertEqual(1,facts['generation']);self.assertEqual(1,facts['worldAttempts'])

    def test_actual_chat_ime_with_lost_ack_stays_owned_and_cannot_type_twice(self):
        self.primed();self.act(3);self.act(4);self.stage.editor.chat.lose_ack=True
        with self.assertRaises(NativeUIError):self.act(5)
        self.no_replay();self.assertEqual('typing',self.graph.operations.children['chat'].state['phase'])
        self.assertEqual(1,sum(row[0]=='chat.input' and row[1]=='replace' for row in self.stage.editor.chat.calls))
        facts=self.actual_actor_facts()
        self.assertEqual('chat',facts['editor']);self.assertEqual(2,facts['generation'])
        self.assertEqual(self.stage.editor.chat.draft,facts['text']);self.assertTrue(facts['focused'])
        self.assertTrue(facts['keyboard']);self.assertEqual([],self.stage.editor.chat.sent)

    def test_consumed_chat_entry_without_widget_effect_cannot_supply_actor_generation_two(self):
        self.primed();self.act(3);self.stage.editor.chat.ignore_effect=True
        with self.assertRaises(NativeUIError):self.act(4)
        self.no_replay();self.assertEqual('opening',self.graph.operations.children['chat'].state['phase'])
        self.assertEqual(1,sum(row[0]=='chat.entry' for row in self.stage.editor.chat.calls))
        facts=self.actual_actor_facts()
        self.assertEqual('none',facts['editor']);self.assertEqual('',facts['text'])
        self.assertEqual(0,facts['generation']);self.assertFalse(facts['focused']);self.assertFalse(facts['keyboard'])

    def test_actual_chat_factory_reuses_join_binding_without_script_inventory_or_input(self):
        from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
        self.primed();self.act(3)
        target=self.stage.editor;before=len(self.stage.native_calls());inputs=deepcopy(target.os.inputs)
        files={p:p.read_bytes() for p in target.root.rglob('*.json')}
        with patch.object(target.adapter,'_scripts',side_effect=AssertionError('No unrelated Script owner')):
            with target.lock.held():
                owner=target.adapter._lifecycle_chat_editor(target.target,target.run,
                    source_lock=target.lock,joined=self.graph.joined)
            self.assertIs(type(owner),PicoLifecycleChatDraft)
            self.assertIs(owner.joined,self.graph.joined);self.assertIs(owner.lock,target.lock)
            self.assertEqual(target.binding,owner.binding);self.assertIsNone(owner.store.read())
            original=deepcopy(self.graph.world.binding)
            try:
                self.graph.world.binding['sessionId']='foreign-original-runtime'
                with target.lock.held(),self.assertRaises((ValueError,RuntimeError)):
                    target.adapter._lifecycle_chat_editor(target.target,target.run,
                        source_lock=target.lock,joined=self.graph.joined)
            finally:self.graph.world.binding.clear();self.graph.world.binding.update(original)
        self.assertEqual(before,len(self.stage.native_calls()));self.assertEqual(inputs,target.os.inputs)
        self.assertEqual(files,{p:p.read_bytes() for p in target.root.rglob('*.json')})


class LifecycleActorBackgroundCounters(unittest.TestCase):
    setUp=LifecycleActorWorldTests.setUp
    baseline=LifecycleActorWorldTests.baseline
    fields=LifecycleActorWorldTests.fields
    act=LifecycleActorWorldTests.act
    actual_actor_facts=LifecycleActorBackChatCounters.actual_actor_facts
    original=LifecycleActorWorldCounters.original

    def test_actual_background_factory_and_normal_os_history_reuse_original_process(self):
        self.baseline()
        for index in range(7):self.act(index)
        target=self.stage.editor;model=target.background;owner=self.graph.operations.children['background']
        self.assertEqual('released',owner.state['phase']);self.assertIs(owner,self.graph.source.background)
        self.assertEqual(['lifecycle.background','app.launch'],[row['operation'] for row in model.inputs])
        self.assertEqual([target.binding['processIdentity']]*2,[row['pid'] for row in model.inputs])
        self.assertEqual([],model.rejected_queries);self.assertTrue(model.foreground)
        self.assertFalse(model.history.active);self.assertTrue(model.history.released)
        self.assertGreaterEqual(owner.state['quiet'][-1]['hostMonotonic']-owner.state['quiet'][0]['hostMonotonic'],3)
        facts=self.actual_actor_facts()
        self.assertEqual('chat',facts['editor']);self.assertEqual(target.chat.draft,facts['text'])
        self.assertEqual(2,facts['generation']);self.assertFalse(facts['focused']);self.assertFalse(facts['keyboard'])
        files={p:(p.read_bytes(),signature(p.stat())) for p in target.root.rglob('*.json')}
        before=(len(self.stage.native_calls()),len(model.history.commands),deepcopy(model.inputs))
        model.foreground=False
        try:
            with (patch.object(target.adapter,'_script_runtime',side_effect=AssertionError('No Qt during historical reopen')),
                  patch.object(target.adapter,'_native_feature_observer',side_effect=AssertionError('No native query during historical reopen'))):
                cold=target.adapter._lifecycle_background_owner(target.target,target.run,
                    source_lock=target.lock,world=self.graph.world)
            self.assertEqual(owner.state,cold.state);self.assertIsNone(cold.runtime)
        finally:model.foreground=True
        self.assertEqual(before,(len(self.stage.native_calls()),len(model.history.commands),model.inputs))
        self.assertEqual(files,{p:(p.read_bytes(),signature(p.stat())) for p in target.root.rglob('*.json')})


def load_tests(loader,tests,pattern):
    # Keep the original selector's four counters; the independently bounded
    # Back/Chat and Background groups have their own explicit wrappers.
    return unittest.TestSuite([loader.loadTestsFromTestCase(LifecycleActorWorldTests),
                              loader.loadTestsFromTestCase(LifecycleActorWorldCounters)])


if __name__=='__main__':unittest.main()
