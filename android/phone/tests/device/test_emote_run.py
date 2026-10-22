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
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_script_history import pack,unpack
from test_emote_admission_owner import Model as AdmissionModel
from test_emote_lifetime import ScopedModel
from test_emote_sources import RUN
from self_tests.test_emote_admission import POLICY,add_manager,PROBE
from adapters.emote_admission import catalog,KEYS


class Model(AdmissionModel,ScopedModel):
    """Reuse independent OS, world/cache/Script and scoped timer producers."""
    def __init__(self,root):
        super().__init__(root)
        bubble=next(row for row in catalog()['files'] if row['runtimePath']=='system/bubble.js')
        for row in (self.foreign_compilation,self.worker.compiled['compilations'][2]):
            row.update(resourceName=self.roots.root+'/system/bubble.js',**{key:bubble[key] for key in KEYS})
        observe=self.code.mutate
        def script(value):
            observe(value);value['source']['engines'][0]['compiled']['compilations'].append(deepcopy(self.foreign_compilation))
        self.code.mutate=script
    def use_included_source(self):
        if getattr(self,'included_once',False):return
        super().use_included_source();self.included_once=True
    def work_send(self,request):
        super().work_send(request)
        member=dict(instance='f'*32,assigned=True,url=PROBE,assignedEpochMs=14900,loadGeneration=1)
        self.work_value['source']['revision']=2
        self.work_value['source']['workers'].append(dict(membership=member,running=True,stopping=False,finished=False,done=False))


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
            def cleanup():
                self.setup_calls.append('view-cleanup')
                boundary.state['phase']='restoring' if self.setup_fault=='view-cleanup' else 'restored'
                boundary.previous=dict(viewBoundaryOnly=True,phase=boundary.state['phase'])
            boundary.prepare=prepare;boundary.cleanup=cleanup;return boundary
        def scene(*args,**kwargs):
            boundary=SimpleNamespace(state=dict(phase='reserved'))
            def prepare():
                self.assertTrue((m.root/'phone-emote-run.json').exists());self.setup_calls.append('scene')
                boundary.state['phase']='preparing' if self.setup_fault=='scene' else 'active'
            def cleanup():
                self.setup_calls.append('scene-cleanup')
                boundary.state['phase']='releasing' if self.setup_fault=='scene-cleanup' else 'released'
                boundary.previous=dict(sceneBoundaryOnly=True,phase=boundary.state['phase'])
            boundary.prepare=prepare;boundary.cleanup=cleanup;return boundary
        mocks=[patch('overte_phone_emote_run.PhoneEmoteView',side_effect=view),patch('overte_phone_emote_run.PhoneEmoteScene',side_effect=scene)]
        mocks += [patch(module+'.PhoneScriptUI',side_effect=m.tablet) for module in ('overte_phone_emote_inputs','overte_phone_emote_cleanup')]
        for mock in mocks:mock.start();self.addCleanup(mock.stop)

    def owner(self):
        m=self.model
        phase=PhaseFixtureReader(m.client,RUN,'emotes',epoch_ms=lambda:m.epoch,monotonic=lambda:m.clock)
        return PhoneEmoteRun(m,'synthetic-selector',phase,m.root,[1000,750],[20,20,180,60],admission=POLICY,monotonic=lambda:m.clock,sleep=m.sleep)

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

    def test_resource_cleanup_orders_scene_before_view_then_each_role_measures_its_own_quiet_window(self):
        m=self.model;owner=self.prepared();owner.act(m.call('play',dict(name='Crying')));self.cleanup_phase()
        proof=owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(['view','scene','scene-cleanup','view-cleanup'],self.setup_calls)
        self.assertEqual('resources-restored',owner.state['phase']);self.assertEqual({'scene','view'},set(proof))
        main=owner.cleanup_quiet('primary');actor=owner.cleanup_quiet('actor')
        self.assertEqual('primary',main['role']);self.assertEqual('actor',actor['role'])
        left,right=unpack(main['payload'])[0],unpack(actor['payload'])[0]
        self.assertGreaterEqual(left['window']['elapsedMs'],3000);self.assertGreaterEqual(right['window']['elapsedMs'],3000)
        self.assertGreater(right['records'][0]['work']['sequence'],left['records'][-1]['work']['sequence'])
        self.assertTrue((m.root/'phone-emote-primary-lifetime.json').exists());self.assertTrue((m.root/'phone-emote-actor-lifetime.json').exists())
        self.assertIsNotNone(owner.store.read());self.assertTrue((m.root/'phone-emote-cleanup-inputs.json').exists())

    def test_scene_incomplete_cleanup_blocks_view_restoration_and_role_quietness(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));self.cleanup_phase();self.setup_fault='scene-cleanup'
        with self.assertRaises(NativeUIError):owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        self.assertNotIn('view-cleanup',self.setup_calls);self.assertEqual('restoring-resources',unpack(owner.store.read()['payload'])[0]['phase'])
        with self.assertRaises(NativeUIError):owner.cleanup_quiet('primary')
        self.assertEqual([],m.work_commands)

    def test_view_incomplete_cleanup_blocks_resource_completion_and_role_quietness(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));self.cleanup_phase();self.setup_fault='view-cleanup'
        with self.assertRaises(NativeUIError):owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        with self.assertRaises(NativeUIError):owner.cleanup_quiet('actor')
        self.assertEqual([],m.work_commands);self.assertIsNotNone(owner.store.read())

    def test_actual_selected_timer_blocks_quiet_completion_after_resource_acknowledgments(self):
        m=self.model;owner=self.prepared();owner.act(m.call('open'));self.cleanup_phase()
        owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        m.worker.timers.append(dict(handle=8,active=True,singleShot=True,intervalMs=2000,remainingMs=1000,functionScriptId=23))
        next(row for row in m.worker.activity if row['scriptId']==23)['timerRegistrations']+=1
        with self.assertRaises(NativeUIError):owner.cleanup_quiet('primary')
        store=PrivateFeatureState(m.root/'phone-emote-primary-lifetime.json');state=unpack(store.read()['payload'])[0]
        self.assertEqual('ready',state['phase']);self.assertEqual(32,len(state['records']));self.assertIsNone(state['window'])
        self.assertIsNotNone(owner.store.read());self.assertTrue(m.worker.timers)

    def test_legacy_input_run_is_read_without_rewrite_and_upgraded_on_resource_cleanup(self):
        owner=self.prepared();value=owner.store.read();value['emoteRunVersion']=1;value.pop('admissionPolicy');value.pop('imagePolicy')
        state=unpack(value['payload'])[0];state.pop('admissionSha256');state.pop('prepared',None);state.pop('setup');value['payload']=pack([state])
        owner.store.write(value,owner.previous);owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare() # Old input readiness is not approved admission.
        self.assertEqual(value,owner.store.read());self.cleanup_phase()
        owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(6,owner.store.read()['emoteRunVersion']);self.assertEqual('resources-restored',owner.state['phase'])

    def test_legacy_header_cannot_claim_a_new_resource_phase(self):
        owner=self.prepared();self.cleanup_phase();owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        value=owner.store.read();value['emoteRunVersion']=1;value.pop('admissionPolicy');value.pop('imagePolicy')
        state=unpack(value['payload'])[0];state.pop('admissionSha256');state.pop('prepared',None);state.pop('setup');value['payload']=pack([state]);owner.store.write(value,owner.previous)
        with self.assertRaises(NativeUIError):self.owner().cleanup_quiet('primary')
        self.assertIsNotNone(owner.store.read())

    def test_slow_final_phase_read_cannot_redate_a_valid_quiet_window_as_current(self):
        m=self.model;owner=self.prepared();self.cleanup_phase();owner.cleanup_resources(dict(contractVersion=VERSION,runId=RUN))
        active=owner.active;calls=[0]
        def slow(*args,**kwargs):
            result=active(*args,**kwargs);calls[0]+=1
            if calls[0]==2:m.clock+=2
            return result
        with patch.object(owner,'active',side_effect=slow),self.assertRaises(NativeUIError):owner.cleanup_quiet('primary')
        self.assertEqual(2,calls[0]);state=unpack(PrivateFeatureState(m.root/'phone-emote-primary-lifetime.json').read()['payload'])[0]
        self.assertEqual('complete',state['phase']);self.assertIsNotNone(owner.store.read())

    def test_missing_admission_configuration_never_starts_a_new_run(self):
        owner=self.owner();owner.policy=None
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertIsNone(owner.store.read());self.assertEqual([],self.setup_calls)

    def test_unfinished_admission_blocks_view_scene_and_normal_input(self):
        self.model.admission_fault='wrong-domain';owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([],self.setup_calls);self.assertIsNotNone(owner.store.read())
        with self.assertRaises(NativeUIError):owner.act(self.model.call('open'))
        self.assertEqual([],self.model.controls.input_requests)

    def test_missing_or_changed_admission_header_blocks_input_after_prepared_commit(self):
        owner=self.prepared();store=PrivateFeatureState(self.model.root/'phone-emote-primary-admission.json')
        store.discard(store.read());call=self.model.call('play',dict(name='Crying'))
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],self.model.controls.input_requests);self.assertIsNone(self.model.actual_name)

    def test_late_unapproved_compilation_cannot_borrow_initial_admission_to_send_input(self):
        m=self.model;owner=self.prepared();observe=m.code.mutate
        def extra(value):
            observe(value);value['source']['engines'][0]['compiled']['compilations'].append(dict(scriptId=32,
                resourceName=m.roots.root+'/unapproved.js',encoding='utf-16le-code-units',codeUnits=2,sha256='f'*64,compiledEpochMs=m.epoch))
        m.code.mutate=extra
        with self.assertRaises(NativeUIError):owner.act(m.call('play',dict(name='Crying')))
        self.assertEqual([],m.controls.input_requests);self.assertEqual([],m.tablet_inputs);self.assertIsNone(m.actual_name)

    def test_late_foreign_world_cannot_borrow_initial_admission_to_send_input(self):
        m=self.model;owner=self.prepared();m.admission_fault='wrong-domain'
        with self.assertRaises(NativeUIError):owner.act(m.call('play',dict(name='Crying')))
        self.assertEqual([],m.controls.input_requests);self.assertEqual([],m.tablet_inputs);self.assertIsNone(m.actual_name)

    def test_checked_primary_cannot_publish_using_an_unchecked_actor_source(self):
        m=self.model;owner=self.prepared()
        with owner.lock.held():
            owner.load();primary=owner.source();inputs=PhoneEmoteInputs(primary)
            actor=PhoneEmoteSources(m,'synthetic-selector',owner.phase,'actor',owner.lock,artifact_root=m.root,monotonic=lambda:m.clock)
            self.assertIsNone(actor.admission)
            with self.assertRaises(NativeUIError):PhoneEmoteEffects(inputs,current_source=actor)
            self.assertIsNotNone(primary.admission);self.assertIsNone(actor.store.read())

    def test_live_source_policy_cannot_be_removed_in_memory_before_acquisition(self):
        m=self.model;owner=self.prepared()
        with owner.lock.held():
            owner.load();source=owner.source();header=deepcopy(source.previous);before=deepcopy(m.calls)
            source.admission=None
            with self.assertRaises(NativeUIError):source.read()
            self.assertEqual(before,m.calls);self.assertEqual(header,source.store.read())


if __name__=='__main__':unittest.main()
