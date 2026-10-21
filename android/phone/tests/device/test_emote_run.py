"""Real run/input/source ownership with explicit synthetic setup boundaries.

View/scene native proof internals have their own original-boundary tests. Here
only their setup completion boundary is doubled. No device/product claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_namespaces import PhoneEmoteNamespaces
from overte_phone_emote_run import PhoneEmoteRun
from overte_phone_script_history import pack,unpack
from test_emote_background import Model
from test_emote_sources import RUN


class EmoteRunTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-run-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name));m=self.model;m.use_included_source();m.widgets.tablet=False
        self.setup_calls=[];self.setup_fault=None
        def view(*args,**kwargs):
            boundary=SimpleNamespace(binding=deepcopy(m.binding),state=dict(phase='reserved'))
            def prepare():
                self.assertTrue((m.root/'phone-emote-run.json').exists());self.setup_calls.append('view')
                boundary.state['phase']='preparing' if self.setup_fault=='view' else 'active'
            boundary.prepare=prepare;return boundary
        def scene(*args,**kwargs):
            boundary=SimpleNamespace(state=dict(phase='reserved'))
            def prepare():
                self.assertTrue((m.root/'phone-emote-run.json').exists());self.setup_calls.append('scene')
                boundary.state['phase']='preparing' if self.setup_fault=='scene' else 'active'
            boundary.prepare=prepare;return boundary
        mocks=[patch('overte_phone_emote_run.PhoneEmoteView',side_effect=view),patch('overte_phone_emote_run.PhoneEmoteScene',side_effect=scene)]
        mocks += [patch(module+'.PhoneScriptUI',side_effect=m.tablet) for module in ('overte_phone_emote_inputs','overte_phone_emote_cleanup')]
        for mock in mocks:mock.start();self.addCleanup(mock.stop)

    def owner(self):
        m=self.model
        phase=PhaseFixtureReader(m.client,RUN,'emotes',epoch_ms=lambda:m.epoch,monotonic=lambda:m.clock)
        return PhoneEmoteRun(m,'synthetic-selector',phase,m.root,[1000,750],[20,20,180,60],monotonic=lambda:m.clock,sleep=m.sleep)

    def prepared(self):
        owner=self.owner();owner.prepare();return owner

    def cleanup_phase(self):self.model.journal.activate(RUN,'a'*32,'cleanup',{})

    def test_parent_owns_before_setup_and_real_normal_input_and_cleanup_compose_without_fake_effects(self):
        m=self.model;owner=self.prepared();self.assertEqual(['view','scene'],self.setup_calls)
        call=m.call('play',dict(name='Crying'));self.assertEqual({'performed':True},owner.act(call))
        self.assertEqual('Crying',m.actual_name);self.cleanup_phase()
        proof=owner.cleanup_inputs(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual('inputs-restored',owner.state['phase']);self.assertIsNone(m.actual_name);self.assertFalse(m.widgets.tablet)
        self.assertEqual(1,proof['emoteCleanupInputsVersion']);self.assertIsNotNone(owner.store.read())
        self.assertNotIn('state',proof);self.assertNotIn('cleaned',proof)
        self.assertTrue((m.root/'phone-emote-namespaces.json').exists());self.assertTrue((m.root/'phone-emote-inputs.json').exists())
        with owner.lock.held():self.assertEqual('acknowledged',PhoneEmoteInputs(owner.source()).state['current']['phase'])

    def test_duplicate_handled_action_sends_no_more_normal_input(self):
        m=self.model;owner=self.prepared();call=m.call('play',dict(name='Crying'));owner.act(call)
        before=deepcopy((m.controls.input_requests,m.tablet_inputs));owner=self.owner();owner.act(call)
        self.assertEqual(before,(m.controls.input_requests,m.tablet_inputs));self.assertEqual('active',owner.state['phase'])

    def test_missing_baseline_owner_cannot_prepare_after_a_normal_activation(self):
        m=self.model;owner=self.owner();call=m.call('open')
        with self.assertRaises(NativeUIError):owner.prepare()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],self.setup_calls);self.assertEqual([],m.controls.input_requests);self.assertIsNone(owner.store.read())

    def test_orphaned_component_ownership_cannot_be_adopted_by_new_run(self):
        m=self.model;store=PrivateFeatureState(m.root/'phone-emote-view.json');store.write(dict(unresolved=True),None)
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual(dict(unresolved=True),store.read());self.assertEqual([],self.setup_calls)

    def failed_setup(self,fault):
        self.setup_fault=fault;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual('preparing',unpack(owner.store.read()['payload'])[0]['phase'])
        self.assertEqual([],self.model.controls.input_requests)
        self.setup_fault=None;owner=self.owner();owner.prepare();self.assertEqual('prepared',owner.state['phase'])

    def test_ignored_view_completion_keeps_preparing_parent_and_blocks_scene_inputs(self):
        self.failed_setup('view');self.assertEqual(['view','view','scene'],self.setup_calls)

    def test_ignored_scene_completion_keeps_preparing_parent_and_blocks_inputs(self):self.failed_setup('scene')

    def test_ignored_parent_prepare_commit_cannot_request_sources_or_mutate_setup(self):
        m=self.model;owner=self.owner();calls=deepcopy(m.calls)
        with patch.object(owner.store,'write',return_value=None),self.assertRaises(NativeUIError):owner.prepare()
        self.assertTrue(all(call=='phase-read' for call in m.calls[len(calls):]));self.assertEqual([],self.setup_calls);self.assertTrue(owner.failed)

    def test_ignored_parent_action_intent_commit_cannot_send_input(self):
        m=self.model;owner=self.prepared();before=deepcopy(m.controls.input_requests);call=m.call('play',dict(name='Crying'))
        with patch.object(owner.store,'write',return_value=None),self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(before,m.controls.input_requests);self.assertTrue(owner.failed)

    def test_primary_and_actor_acquire_distinct_originals(self):
        m=self.model;owner=self.prepared();primary=owner.acquire('primary');actor=owner.acquire('actor')
        self.assertGreater(actor['group']['native']['sequence'],primary['group']['native']['sequence'])
        self.assertNotEqual(primary['widgets']['sourceSequence'],actor['widgets']['sourceSequence'])
        self.assertEqual([],m.controls.input_requests);self.assertTrue((m.root/'phone-emote-actor-sources.json').exists())

    def test_namespace_switch_freezes_each_role_then_binds_the_next_actual_input(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));call=m.call('play',dict(name='Crying'))
        owner.request_switch(call);owner.acknowledge_switch('primary');before=deepcopy(m.controls.input_requests)
        with self.assertRaises(NativeUIError):owner.advance_switch()
        self.assertEqual(before,m.controls.input_requests);owner.acknowledge_switch('actor')
        self.assertEqual(1,owner.advance_switch());self.assertEqual('acting',owner.state['phase'])
        owner.act(call);self.assertEqual('Crying',m.actual_name)
        self.assertTrue((m.root/'phone-emote-primary-sources.json').exists());self.assertTrue((m.root/'phone-emote-primary-sources-segment-1.json').exists())
        self.assertTrue((m.root/'phone-emote-inputs-segment-1.json').exists())

    def test_lost_parent_switch_commit_observes_child_transition_without_advancing_twice(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));call=m.call('play',dict(name='Crying'))
        owner.request_switch(call);owner.acknowledge_switch('primary');owner.acknowledge_switch('actor')
        write=owner.store.write
        def fail(value,previous):
            if unpack(value['payload'])[0]['segment']==1:raise NativeUIError('Synthetic parent transition failure')
            write(value,previous)
        with patch.object(owner.store,'write',side_effect=fail),self.assertRaises(NativeUIError):owner.advance_switch()
        owner=self.owner();self.assertEqual(1,owner.advance_switch())
        with owner.lock.held():lease=PhoneEmoteNamespaces(owner.source());self.assertEqual(1,lease.state['current']);self.assertEqual(1,len(lease.state['closed']))
        owner.act(call);self.assertEqual('Crying',m.actual_name)

    def test_cleanup_reconciles_committed_child_switch_without_sending_reserved_input(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));call=m.call('play',dict(name='Crying'))
        owner.request_switch(call);owner.acknowledge_switch('primary');owner.acknowledge_switch('actor')
        with patch.object(owner.store,'write',side_effect=NativeUIError('Synthetic parent commit failure')),self.assertRaises(NativeUIError):owner.advance_switch()
        before=deepcopy(m.controls.input_requests);self.cleanup_phase();owner=self.owner();owner.cleanup_inputs(dict(contractVersion=VERSION,runId=RUN))
        self.assertFalse(any(row['controlId']=='emote.play.Crying' for row in m.controls.input_requests));self.assertEqual(1,owner.state['segment'])
        self.assertFalse(m.widgets.tablet);self.assertEqual('inputs-restored',owner.state['phase'])

    def test_pending_primary_freeze_is_released_by_real_cleanup_without_an_actor_ack(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));call=m.call('play',dict(name='Crying'))
        owner.request_switch(call);owner.acknowledge_switch('primary');self.cleanup_phase()
        owner.cleanup_inputs(dict(contractVersion=VERSION,runId=RUN))
        with owner.lock.held():lease=PhoneEmoteNamespaces(owner.source());self.assertIsNone(lease.state['cleanup']['pending']['roles']['actor'])
        self.assertEqual('inputs-restored',owner.state['phase']);self.assertIsNone(m.actual_name)

    def test_background_cleanup_recovers_actual_foreground_before_native_sources(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));call=m.call('background-resume');m.lose='lifecycle.background'
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertFalse(m.foreground);self.cleanup_phase();m.lose='';owner=self.owner()
        owner.cleanup_inputs(dict(contractVersion=VERSION,runId=RUN))
        self.assertTrue(m.foreground);self.assertEqual(0,m.background_native_accesses)
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual('inputs-restored',owner.state['phase'])

    def test_foreign_candidate_or_changed_configuration_cannot_reconstruct_this_run(self):
        m=self.model;owner=self.prepared();m.binding['artifactSha256']='f'*64
        with self.assertRaises(NativeUIError):owner.acquire('primary')
        bad=self.owner();bad.extent=[2000,1500]
        with self.assertRaises(NativeUIError):bad.prepare()
        self.assertEqual([],m.controls.input_requests)

    def test_ignored_native_playback_remains_an_input_ack_without_synthetic_effect_results(self):
        m=self.model;owner=self.prepared();m.ignore_native=True
        result=owner.act(m.call('play',dict(name='Crying')))
        self.assertEqual({'performed':True},result);self.assertIsNone(m.actual_name)
        original=owner.acquire('primary');self.assertFalse(original['group']['native']['animation']['overrideActive'])
        self.assertNotIn('state',result);self.assertNotIn('facts',result)

    def test_lost_normal_qt_return_is_owned_by_parent_and_cleanup_without_a_second_play(self):
        m=self.model;owner=self.prepared();send=m.controls.send
        def lost(value):
            send(value)
            if value['request']['action']=='activate' and value['request']['controlId']=='emote.play.Crying':
                raise NativeUIError('Synthetic consumed normal return lost')
        m.controls.send=lost;call=m.call('play',dict(name='Crying'))
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual('acting',unpack(owner.store.read()['payload'])[0]['phase'])
        m.controls.send=send;self.cleanup_phase();owner=self.owner();owner.cleanup_inputs(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(['override','restore'],[event['kind'] for event in m.events])
        self.assertEqual(2,len([row for row in m.controls.input_requests if row['controlId']=='emote.play.Crying']))
        with owner.lock.held():self.assertEqual('issuing',PhoneEmoteInputs(owner.source()).state['current']['phase'])

    def test_lost_parent_action_commit_does_not_repeat_the_acknowledged_child_input(self):
        m=self.model;owner=self.prepared();write=owner.store.write;call=m.call('play',dict(name='Crying'))
        def failed(value,previous):
            if unpack(value['payload'])[0]['phase']=='active':raise NativeUIError('Synthetic parent ACK commit failed')
            write(value,previous)
        with patch.object(owner.store,'write',side_effect=failed),self.assertRaises(NativeUIError):owner.act(call)
        before=deepcopy(m.controls.input_requests);owner=self.owner();owner.act(call)
        self.assertEqual(before,m.controls.input_requests);self.assertEqual('active',owner.state['phase'])

    def test_phase_change_after_view_preparation_blocks_scene_setup_and_parent_completion(self):
        m=self.model;owner=self.owner();factory=owner.view
        def view():
            value=factory();prepare=value.prepare
            def changed():prepare();m.call('open')
            value.prepare=changed;return value
        with patch.object(owner,'view',side_effect=view),self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual(['view'],self.setup_calls);self.assertEqual('preparing',unpack(owner.store.read()['payload'])[0]['phase'])
        self.assertEqual([],m.controls.input_requests)

    def test_later_baseline_cannot_adopt_a_new_run_or_complete_old_setup(self):
        m=self.model;m.journal.activate(RUN,'b'*32,'baseline',{});owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([],self.setup_calls);self.assertIsNone(owner.store.read())


if __name__=='__main__':unittest.main()
