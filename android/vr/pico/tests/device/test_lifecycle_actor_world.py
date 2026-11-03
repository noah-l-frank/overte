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

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
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
        self.graph.journey.continuity('before',fields['verb']);self.graph.journey.call('act',fields)
        self.graph.journey.continuity('after',fields['verb']);return fields

    def test_actual_common_source_prefix_includes_normal_world_attempt_from_own_native_events(self):
        self.baseline()
        for index in range(3):
            fields=self.act(index);barrier=self.stage.native.epoch()
            expected=expand(SCENARIOS['lifecycle-input']['steps'][index]['state'],context(self.stage.run))
            self.graph.journey.wait('canonical-source-world-'+str(index+1),fields['ticket'],barrier,expected,['peer'])
        self.assertEqual(3,len(self.graph.operations.state['steps']))
        self.assertEqual(1,len(self.graph.world.state['attempts']))
        self.assertEqual('quiet',self.graph.world.state['attempts'][0]['phase'])
        self.assertEqual(2,len(self.stage.editor.transport.envelopes)) # Tablet + original normal World input.
        passive=ActorOriginals(PrivateFeatureState(self.stage.root/'lifecycle-actor-originals.json'))
        self.assertEqual(12,len(passive.root['records']));owned=[]
        for index in range(12):
            group=passive.group(index);root,entries=decode_snapshot(group['staging'])
            self.assertEqual(2,root['actorStagingVersion'])
            for entry in entries:
                if entry['key']=='world-owner':owned.append((index,root,entry['value']))
        self.assertEqual(1,len(owned));index,staging,original=owned[0]
        self.assertEqual(1,self.stage.products.world_history_decodes)
        self.assertEqual(9,index);raw=base64.b64decode(original['rawBase64'],validate=True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),original['sha256'])
        self.assertEqual(self.graph.world.store.path.read_bytes(),raw)
        self.assertEqual(signature(self.graph.world.store.path.stat()),original['physical'])
        self.assertEqual(self.stage.editor.session.profile,original['profile'])
        self.assertEqual(hashlib.sha256(canonical(original['profile'])).hexdigest(),original['profileSha256'])
        self.assertEqual(json.loads(raw)['payload']['bytes'],staging['nestedDecodedBytes'])
        for index,row in enumerate(passive.root['records'][9:],9):
            group=passive.native(row['native'],record=index)
            facts=group['record']['publication']['facts']
            self.assertEqual(1,facts['worldAttempts']);self.assertEqual(0,facts['worldDisplacement'])
            self.assertEqual([],facts['heldInputs']);self.assertEqual(10,group['record']['worldOwnershipActorSequence'])
        self.assertLessEqual(passive.root['decodedSourceBytes'],MAX_RAW)
        self.assertEqual([['gesture','drive','ui','pending','feature','subject']]*12,self.graph.actor_query_deltas)
        self.assertTrue(all(sample['witness'] is not None for sample in self.graph.journey.samples))
        self.stage.command('exit');self.stage.worker.wait(timeout=10);self.assertEqual(0,self.stage.worker.returncode)
        absent=self.stage.process.require_absent();self.stage.process.final_absence(absent)
        bill=self.stage.last_worker['sourceStorage']
        report=dict(lifecycleActorWorldSourceVersion=1,sourceVersion=2,stagingVersion=2,
            originalNormalActions=3,actorSourceGroups=12,actorSixSourceQueries=72,
            sharedNativeQueries=len(self.stage.native_calls()),primaryNativeQueries=len(self.stage.native_calls())-72,
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


if __name__=='__main__':unittest.main()
