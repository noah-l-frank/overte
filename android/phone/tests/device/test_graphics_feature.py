"""Composite normal widget, original native/GPU/Java and real private host seams.

The synthetic renderer and transport qualify test logic only, never Android.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
from types import SimpleNamespace
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_scene_loads import NativePhoneSceneLoads
from adapters.native_phone_web_runtime import NativePhoneWebRuntime
from feature_journeys.graphics_resources import GraphicsResources
from feature_journeys.witness import Client,Journal
from feature_journeys.engine import Journey
from overte_phone_graphics import PhoneGraphicsIO
from overte_phone_graphics_fixture import GraphicsFixtureReader,GraphicsRunRetired,GraphicsPhasePending
from overte_phone_graphics_feature import PhoneGraphicsFeature
from overte_phone_script_files import PhoneScriptFileIO
from overte_phone_script_history import unpack
from overte_phone_script_lock import PhoneScriptSourceBusy
from self_tests.test_native_phone_web_runtime import Boundary as WebBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_world_render_evidence import frame_view
from audio_native_boundary import ControlNativeBoundary
from test_graphics_restart import Model as Inputs
from test_graphics_observer import Model as GPU
from test_graphics_effects import POLICY as EFFECT_POLICY
POLICY=deepcopy(EFFECT_POLICY)
POLICY['subject']=[240,150,500,200]
from test_graphics_measurements import RUN,TICKET,URL,FIXTURE


class Composite(Inputs):
    def __init__(self):
        super().__init__();self.actor_enabled=False;self.actor_exited=False;self.actor_error=None
        self.resources=GraphicsResources(URL,clock_ms=self.epoch);self.resources.provision(RUN);self.resources.activate(RUN,TICKET)
        self.journal=Journal(self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('graphics')
        self.journal.activate(RUN,TICKET)
        self.normal_feature_runtime('controlled',read_only=True)
        self.native.source['view']['aspectRatio']=16/9;self.original['view']['aspectRatio']=16/9
        self.controlled.subject_before['source']['view']['aspectRatio']=16/9
        for row in self.controlled.subject_before['source']['entities']:
            if row['type']=='Web':row['sourceUrl']=FIXTURE+'tickets/'+TICKET+'/graphics-marker.v1.html'
        self.gpu=GPU(self.root);self.gpu.binding=self.binding;self.gpu.pid=self.pid;self.gpu.effect_profile()
        self.gpu.epoch=self.epoch;self.gpu.options=self.options;self.gpu.guard=self.guard
        original_capture=self.gpu.send
        def send(key,request):
            assert key in ('capture','tablet')
            if key=='capture':self.render()
            else:
                self.gpu.scene.tablet['scriptInventory']['tabletShown']=self.sdk.panel is not None
            if key=='tablet' and (self.root/'phone-graphics-retirement.json').exists():
                # The final owner has its own durable read-only plan; no new
                # sample/GPU lease is created after provider retirement.
                self.gpu.counters[key]+=1;packet=deepcopy(self.gpu.scene.tablet)
                packet.update(commandId=request['commandId'],sourceSequence=self.gpu.counters[key])
                self.gpu.values[key]=packet
            else:original_capture(key,request)
            packet=self.gpu.values[key]
            packet.update(processId=self.pid,capturedEpochMs=self.epoch(),instance=self.birth)
            if key=='capture':
                packet['requestedEpochMs']=self.epoch()
                source=packet['source'];source.update(recordedEpochMs=self.epoch(),startedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
                source['renderTrace'].update(recordedEpochMs=self.epoch(),begunEpochMs=self.epoch(),completedEpochMs=self.epoch())
            else:packet.update(elapsedMs=round(self.sdk.clock*1000),generation=self.birth)
        self.gpu.send=send
        self.qt_source=ControlNativeBoundary(self.fixture.qt,'phone-graphics-ui')
        self.qt_source.mutate=lambda value:value.update(processId=self.pid,capturedEpochMs=self.epoch(),elapsedMs=round(self.sdk.clock*1000))
        self.web=WebBoundary();self.web.now=self.epoch
        self.web_fault=None;self.ignore_render=None;self.render_haze=False;self.render_mirror=False;self.render_scale=.65
        self.client=Client(URL,'x'*64);self.client.run=RUN;self.client.area='graphics';self.client.closed=False
        self.actor=Client(URL,'y'*64);self.actor.run=RUN;self.actor.area='graphics';self.actor.closed=False
        for role,client in [('primary',self.client),('actor',self.actor)]:
            client.request=lambda *args,role=role,**kwargs:self.request(role,*args,**kwargs)
            client.graphics_status=lambda client=client:self.status(client)
        self.native.edit=self.subject_edit;self.loads.mutate=self.load_edit
        self.gpu.storage.mutate=self.storage_edit;self.gpu.inventory.mutate=self.storage_edit
        self.inputs_sleep=self.fixture.sleep;self.fixture.sleep=self.sleep
    def epoch(self):return 20000+round(self.sdk.clock*1000)
    def options(self):return dict(monotonic=lambda:self.sdk.clock,sleep=self.sleep)
    def guard(self):return self.native.okay and self.foreground and self.running
    def sleep(self,value):
        self.sdk.clock+=value
        if self.actor_enabled and not self.actor_exited:
            self.actor_enabled=False
            try:self.flow('actor').publish()
            except GraphicsRunRetired:self.actor_exited=True
            except (GraphicsPhasePending,PhoneScriptSourceBusy):pass
            except Exception as error:self.actor_error=error;raise
            finally:
                if not self.actor_exited:self.actor_enabled=True
    def status(self,client):
        with patch('feature_journeys.witness.time.time',return_value=self.epoch()/1000):return Client.graphics_status(client)
    def provider(self):return self.status(self.client)
    def request(self,role,path,value=None,method=None,**kwargs):
        if path=='/graphics-provider':return self.resources.ready()|dict(internalErrors=0)
        if path=='/runs/'+RUN+'/graphics':return self.resources.snapshot(RUN,kwargs['graphics_nonce'])
        if path=='/runs/'+RUN+'/phase':return self.journal.phase(RUN,kwargs['phase_nonce'])
        if path=='/runs/'+RUN+'/active':return self.journal.active(RUN)
        if path=='/runs/'+RUN:return self.journal.snapshot(RUN)
        if path=='/runs/'+RUN+'/samples':
            assert role=='actor';return self.journal.publish(RUN,value)
        raise AssertionError('Unexpected composite fixture request')
    def phase(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;self.resources.activate(RUN,ticket);self.journal.activate(RUN,ticket,verb,inputs or {});return ticket
    def activate(self,ticket,verb='baseline',inputs=None):
        self.resources.activate(RUN,ticket);self.journal.activate(RUN,ticket,verb,inputs or {})
    def flow(self,role='primary'):
        client=self.client if role=='primary' else self.actor
        return PhoneGraphicsFeature(self,'controlled',GraphicsFixtureReader(client,RUN,epoch_ms=self.epoch),self.root,POLICY,role=role,**self.options())
    @contextmanager
    def existing_input_session(self,_selector):yield
    def subject_edit(self,value):
        super().subject_edit(value);value.update(requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
    def load_edit(self,value):
        super().load_edit(value);value['capturedEpochMs']=self.epoch()
    def original_native(self,value):
        super().original_native(value);epoch=self.epoch();value.update(requestedEpochMs=epoch,capturedEpochMs=epoch)
        value['animationFence']['requestedEpochMs']=epoch;value['animation']['capturedEpochMs']=epoch;value['animation']['clip']['evaluatedEpochMs']=epoch
    def _native_feature_observer(self,_selector,*,read_only):
        assert read_only;return NativeFeatureObservation(self.features.send,self.features.original,self.epoch,self.guard,self.pid,**self.options())
    def _graphics_subject_observer(self,_selector,*,read_only):
        assert read_only;return NativeGraphicsSubject(self.native.send,self.native.original,self.epoch,self.guard,self.pid,**self.options())
    def _scene_load_observer(self,_selector,*,read_only):
        assert read_only;return NativePhoneSceneLoads(self.loads.send,self.loads.original,self.epoch,self.guard,self.pid,**self.options())
    def _graphics_controls(self,_selector,_intent,*,read_only):
        from types import SimpleNamespace
        assert read_only
        io=PhoneGraphicsIO(self.qt_source.send,lambda:json.dumps(self.qt_source.value),self.epoch,self.guard,self.pid,**self.options())
        return SimpleNamespace(io=io)
    def _script_file_io(self,_selector,*,read_only):
        assert read_only;self.gpu.pid=self.pid
        return self.gpu.reader('tablet',PhoneScriptFileIO)
    def storage_edit(self,value):value.update(processId=self.pid,instance=self.birth,capturedEpochMs=self.epoch())
    def _world_render_capture(self,_selector,*,read_only,role,require_frame_view):
        self.gpu.active_role=role;self.gpu.pid=self.pid;self.gpu.stage=0 if self.pid==31 else 1
        owned=self.gpu._world_render_capture(_selector,read_only=read_only,role=role,require_frame_view=require_frame_view)
        owned.owner.store=self.world_render_store('controlled',role=role);return owned
    def _web_runtime_observer(self,_selector,*,read_only):
        assert read_only
        def send(request):
            self.web.revoked=not self.native.source['entities'];self.web.send(request)
        def edit(value):
            value.update(processId=self.pid,instance='a'*32 if self.pid==31 else '5'*32)
            value['source']['java'].update(processId=self.pid,instance='d'*32 if self.pid==31 else '6'*32)
            if self.web_fault=='callback':value['source']['nativeAfter']['views'][0]['callbacks']=1
            if self.web_fault=='java':value['source']['java']['views'][0].update(sourceOwned=True,documentOwned=True)
        self.web.edit=edit
        return NativePhoneWebRuntime(send,self.web.original,self.epoch,self.guard,self.pid,**self.options())
    def _process_presence(self,_selector,*,read_only):
        assert read_only;boundary=PresenceBoundary(pid=self.pid,epoch_ms=self.epoch);boundary.presence=self.presence
        boundary.edit=lambda value:value.update(instance=self.birth);return boundary.reader()
    def load(self,url):
        super().load(url)
        self.loads.rows[-1].update(startedEpochMs=self.epoch(),updatedEpochMs=self.epoch(),releasedEpochMs=self.epoch())
        if '/feature-fixture/' in url:
            with self.resources.response(RUN,TICKET,request_authority='controlled.invalid',request_scheme='http') as response:
                status,body,nonce,written=response
                written(dict(responseId=nonce,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    def new_process(self):
        super().new_process();self.fixture.qt.instance='8'*32;self.fixture.qt.generation='9'*32
        self.web=WebBoundary();self.web.epoch=self.epoch();self.web.now=self.epoch
        self.gpu.binding=self.binding;self.gpu.scene.capture['instance']=self.birth
    def invoke(self,selector,operation,values):
        if operation=='lifecycle.background':
            self.normal_inputs.append(operation);self.foreground=False;self.lifecycle['backgrounds']+=1;return {'backgrounded':True}
        if operation=='app.launch' and self.running:
            self.normal_inputs.append(operation);self.foreground=True;self.lifecycle['activations']+=1;return {'launched':True}
        return super().invoke(selector,operation,values)
    def render(self):
        # Explicit synthetic product renderer state, observed independently of
        # the ordinary widget/native preference sources. Faults can ignore any
        # setting while widget/native state still changes successfully.
        qt=self.fixture.qt
        if self.ignore_render!='resolution':self.render_scale=qt.resolution
        if self.ignore_render!='haze':self.render_haze=qt.haze
        if self.ignore_render!='mirror':self.render_mirror=qt.mirrors
        capture=self.gpu.scene.capture;capture['instance']=self.birth
        capture['source'].update(sourceExtent=[round(640*self.render_scale),round(360*self.render_scale)],
            sourceViewport=[0,0,round(640*self.render_scale),round(360*self.render_scale)],targetExtent=[640,360])
        capture['source']['renderTrace'].update(recordedView=frame_view(16/9),hazeBatches=2 if self.render_haze else 0,
            hazeDrawCommands=8 if self.render_haze else 0,mirrorBatches=1 if self.render_mirror else 0,mirrorDrawCommands=1 if self.render_mirror else 0)
        self.gpu.paint(self.journal.active(RUN)['ticket'],(30,110,210) if self.render_haze else (230,230,230),self.render_mirror)


class GraphicsFeatureTests(unittest.TestCase):
    def setUp(self):self.m=Composite();self.addCleanup(self.m.close)
    def observe_call(self):return dict(contractVersion=18,runId=RUN,afterSequence=0)
    def registered_adapter(self):
        from test_account_fixture_launch import AccountFixtureLaunchTests
        setup=AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);return setup.f
    def configuration(self):
        policy=self.m.root/'graphics-policy.json';access=self.m.root/'adapter-fixture-access.json'
        for path,value in [(policy,POLICY),(access,dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL,adapterToken='d'*64))]:
            store=PrivateFeatureState(path)
            if store.read() is None:store.write(value,None)
        return dict(OVERTE_PHONE_FEATURE_GRAPHICS='1',OVERTE_E2E_FEATURE_FIXTURE_URL=URL,
            OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),OVERTE_PHONE_GRAPHICS_IMAGE_POLICY=str(policy),OVERTE_DEVICE_ARTIFACT_DIR=str(self.m.root))
    def retirement_ready(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());m.flow('actor').publish()
        m.phase('cleanup');flow.cleanup(dict(contractVersion=18,runId=RUN));m.flow('actor').publish()
        m.resources.retire(RUN);m.journal.close(RUN);m.client.closed=True;m.actor_enabled=True
        return flow
    def call(self,verb,**inputs):
        return dict(contractVersion=18,runId=RUN,fixtureUrl=FIXTURE,ticket=self.m.phase(verb,inputs),verb=verb,inputs=inputs)
    def test_normal_scene_preparation_then_distinct_primary_and_actor_originals(self):
        m=self.m;flow=m.flow();state=flow.prepare();self.assertEqual('baseline',state['phase'])
        value=flow.observe(self.observe_call());self.assertEqual(.65,value['state']['resolution']);self.assertFalse(value['state']['dialog'])
        self.assertEqual(2,value['sequence']);self.assertEqual(2,len(m.destinations));m.flow('actor').publish()
        rows=m.journal.snapshot(RUN)['entries'];self.assertEqual(1,len(rows));self.assertEqual(.65,rows[0]['facts']['resolution'])
        self.assertNotEqual(value['artifacts'][0]['name'],m.flow('actor').store.path.name)

    def test_complete_common_fifteen_step_graphics_journey_uses_normal_inputs_and_independent_originals(self):
        m=self.m;reports=[];registered=self.registered_adapter()
        import test_feature_adapters as bound
        def invoke(operation,call):
            if operation.endswith('.observe'):
                try:m.flow('actor').publish()
                except (GraphicsPhasePending,PhoneScriptSourceBusy):pass
            return registered.adapter.invoke(bound.SELECTOR,operation,call)
        journey=Journey('graphics',RUN,FIXTURE,invoke=invoke,witness=lambda:m.journal.snapshot(RUN),activate=m.activate,
            read_artifact=lambda name:(m.root/name).read_bytes(),image_policy=dict(screen=POLICY),continuity=lambda *_args:None,
            monotonic=lambda:m.sdk.clock,epoch_ms=m.epoch,sleep=m.sleep,report=reports.append)
        from feature_journeys.phase_fixture import PhaseFixtureReader
        # Same nonce-bound original Journal as the composition, on its explicit
        # synthetic clock. Public cleanup still dispatches through the real
        # phase validator and the existing original Graphics owner.
        def phase_reader(client,run,area):
            return PhaseFixtureReader(client,run,area,epoch_ms=m.epoch,monotonic=lambda:m.sdk.clock)
        with patch.dict(os.environ,self.configuration()),patch.object(registered.adapter,'_graphics_feature',side_effect=lambda *_args,**_kwargs:m.flow()), \
             patch.object(registered.adapter,'_feature_fixture_client',return_value=m.client), \
             patch('overte_phone_feature_dispatch.PhaseFixtureReader',side_effect=phase_reader):
            journey.execute()
        self.assertEqual(15,len([row for row in journey.phases if row['phase'][:2].isdigit()]))
        m.resources.retire(RUN);m.journal.close(RUN);m.client.closed=True;m.actor_enabled=True
        self.assertEqual({'performed':True},m.flow().finalize());self.assertTrue(m.actor_exited)
        self.assertTrue(all(store.read() is None for store in m.flow().child_stores().values()))

    def test_whole_fixture_retirement_restores_original_world_and_waits_for_both_independent_quiet_windows(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());m.flow('actor').publish()
        m.phase('cleanup');self.assertEqual({'performed':True},flow.cleanup(dict(contractVersion=18,runId=RUN)))
        m.flow('actor').publish();m.resources.retire(RUN);m.journal.close(RUN);m.client.closed=True;m.actor_enabled=True
        self.assertEqual({'performed':True},flow.finalize());self.assertTrue(m.actor_exited);self.assertIsNone(m.actor_error)
        self.assertFalse(flow.store.path.exists());self.assertFalse(flow.retirement_store.path.exists())
        self.assertTrue(all(store.read() is None for store in flow.child_stores().values()))
        self.assertEqual([],m.native.source['entities']);self.assertEqual(m.original['avatarPose'],m.native.source['avatarPose'])
        self.assertTrue(list(m.root.glob('graphics-'+RUN+'-*.json')))

    def test_ignored_normal_preference_input_stays_owned_and_is_never_replayed(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());flow.act(self.call('open'));m.fixture.qt.fault='resolution'
        call=self.call('set-resolution',value=.5)
        with self.assertRaises(NativeUIError):flow.act(call)
        before=list(m.fixture.qt.actions)
        with self.assertRaises(NativeUIError):m.flow().act(call)
        self.assertEqual(before,m.fixture.qt.actions);self.assertEqual(.65,m.fixture.qt.resolution)
        with m.lock.held():self.assertEqual('acting',m.flow().control()['phase'])
    def test_native_preference_success_without_actual_renderer_resolution_is_measured_and_rejected(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());flow.act(self.call('open'));m.ignore_render='resolution'
        flow.act(self.call('set-resolution',value=.5));value=flow.observe(self.observe_call())
        self.assertEqual(.5,value['state']['resolution']);self.assertEqual(.65,value['state']['renderScale'])
    def test_conflicting_repeated_ticket_cannot_send_a_second_functional_input(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());call=self.call('open');flow.act(call);before=list(m.sdk.inputs)
        with self.assertRaises(NativeUIError):flow.act(call|dict(verb='close'))
        self.assertEqual(before,m.sdk.inputs)
    def test_failed_owner_intent_write_prevents_the_first_normal_feature_input(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());call=self.call('open');before=list(m.sdk.inputs);write=PrivateFeatureState.write
        def failed(store,value,previous):
            if store.path==flow.store.path and unpack(value['payload'])[0]['phase']=='acting':raise OSError('Synthetic missing root input intent')
            return write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',failed),self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual(before,m.sdk.inputs)
    def test_inactive_provider_with_live_java_document_is_red_after_original_entities_disappear(self):
        m=self.m;flow=self.retirement_ready();m.web_fault='java'
        with self.assertRaises(NativeUIError):flow.finalize()
        self.assertEqual([],m.native.source['entities']);self.assertTrue(flow.store.path.exists());self.assertTrue(flow.retirement_store.path.exists())
    def test_missing_independent_actor_cannot_complete_whole_fixture_cleanup(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());m.phase('cleanup');flow.cleanup(dict(contractVersion=18,runId=RUN))
        m.resources.retire(RUN);m.journal.close(RUN);m.client.closed=True
        with self.assertRaises(NativeUIError):flow.finalize()
        self.assertEqual([],m.native.source['entities']);self.assertTrue(flow.store.path.exists())
    def test_lost_archive_write_response_recovers_the_exact_intended_original_without_replaying_navigation(self):
        m=self.m;flow=self.retirement_ready();write=PrivateFeatureState.write;target='graphics-'+RUN+'-preferences.json'
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path.name==target:raise OSError('Synthetic lost archive file response')
            return result
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(NativeUIError):flow.finalize()
        archived=m.root/target;original=archived.read_bytes();inode=archived.stat().st_ino
        self.assertEqual(2,len(m.destinations));self.assertEqual({'performed':True},m.flow().finalize())
        self.assertEqual(original,archived.read_bytes());self.assertEqual(inode,archived.stat().st_ino);self.assertEqual(3,len(m.destinations))
    def test_missing_archive_write_recovers_before_any_new_component_source_changes(self):
        m=self.m;flow=self.retirement_ready();write=PrivateFeatureState.write;target='graphics-'+RUN+'-preferences.json'
        def failed(store,value,previous):
            if store.path.name==target:raise OSError('Synthetic missing archive write')
            return write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',failed),self.assertRaises(NativeUIError):flow.finalize()
        self.assertFalse((m.root/target).exists());self.assertEqual({'performed':True},m.flow().finalize());self.assertEqual(3,len(m.destinations))
    def test_partial_metadata_removal_is_recoverable_without_input_replay(self):
        m=self.m;flow=self.retirement_ready();discard=PrivateFeatureState.discard;target='phone-graphics-primary-0-samples.json'
        def lost(store,value):
            result=discard(store,value)
            if store.path.name==target:raise OSError('Synthetic lost child metadata discard')
            return result
        with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(NativeUIError):flow.finalize()
        destinations=list(m.destinations);self.assertTrue(flow.retirement_store.path.exists())
        self.assertEqual({'performed':True},m.flow().finalize());self.assertEqual(destinations,m.destinations)
    def test_lost_root_discard_response_recovers_from_the_durable_retirement_plan(self):
        m=self.m;flow=self.retirement_ready();discard=PrivateFeatureState.discard
        def lost(store,value):
            result=discard(store,value)
            if store.path==flow.store.path:raise OSError('Synthetic lost root discard response')
            return result
        with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(NativeUIError):flow.finalize()
        self.assertFalse(flow.store.path.exists());self.assertTrue(flow.retirement_store.path.exists());destinations=list(m.destinations)
        self.assertEqual({'performed':True},m.flow().finalize());self.assertEqual(destinations,m.destinations)
    def test_ignored_metadata_discard_never_turns_green(self):
        m=self.m;flow=self.retirement_ready();discard=PrivateFeatureState.discard;target='phone-graphics-primary-0-samples.json'
        def ignored(store,value):
            if store.path.name==target:return
            return discard(store,value)
        with patch.object(PrivateFeatureState,'discard',ignored),self.assertRaises(NativeUIError):flow.finalize()
        self.assertTrue((m.root/target).exists());self.assertEqual({'performed':True},m.flow().finalize())
    def test_reappearing_web_callback_after_partial_discard_requires_new_original_quiet_window(self):
        m=self.m;flow=self.retirement_ready();discard=PrivateFeatureState.discard;target='phone-graphics-primary-0-samples.json'
        def ignored(store,value):
            if store.path.name==target:return
            return discard(store,value)
        with patch.object(PrivateFeatureState,'discard',ignored),self.assertRaises(NativeUIError):flow.finalize()
        m.web_fault='callback'
        with self.assertRaises(NativeUIError):m.flow().finalize()
        self.assertTrue(flow.retirement_store.path.exists());m.web_fault=None;before=m.sdk.clock
        self.assertEqual({'performed':True},m.flow().finalize());self.assertGreaterEqual(m.sdk.clock-before,3)

    def test_registered_entrypoint_requires_explicit_complete_private_graphics_configuration(self):
        import test_feature_adapters as bound
        f=self.registered_adapter();config=self.configuration()
        with patch.dict(os.environ,config),patch.object(f.adapter,'_graphics_feature',return_value=self.m.flow()) as factory:
            capabilities=f.adapter.advertised_capabilities(f.target)
            self.assertTrue(all('feature.graphics.'+kind in capabilities for kind in ('act','observe','cleanup')))
            value=f.adapter.invoke(bound.SELECTOR,'feature.graphics.observe',self.observe_call())
            self.assertEqual(.65,value['state']['resolution']);factory.assert_called_once_with(bound.SELECTOR,RUN)
        with patch.dict(os.environ,config|dict(OVERTE_PHONE_FEATURE_GRAPHICS='0')),patch.object(f.adapter,'_graphics_feature') as factory:
            with self.assertRaisesRegex(ValueError,'PHONE_GRAPHICS_FEATURE_NOT_ENABLED'):
                f.adapter.invoke(bound.SELECTOR,'feature.graphics.observe',self.observe_call())
            factory.assert_not_called()
    def test_missing_or_foreign_private_policy_or_fixture_access_cannot_advertise_complete_graphics(self):
        f=self.registered_adapter();config=self.configuration()
        for edit in [dict(OVERTE_PHONE_FEATURE_GRAPHICS='yes'),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),
            dict(OVERTE_DEVICE_ARTIFACT_DIR=''),dict(OVERTE_PHONE_GRAPHICS_IMAGE_POLICY=''),dict(OVERTE_E2E_FEATURE_FIXTURE_URL=URL+'/foreign')]:
            with self.subTest(edit=edit),patch.dict(os.environ,config|edit),self.assertRaises((ValueError,RuntimeError)):
                f.adapter.advertised_capabilities(f.target)
        policy=Path(config['OVERTE_PHONE_GRAPHICS_IMAGE_POLICY']);store=PrivateFeatureState(policy)
        for changed in [POLICY|dict(source='native-screen'),POLICY|dict(expectedHaze=True),POLICY|dict(subject=POLICY['marker'])]:
            store.write(changed,store.read())
            with self.subTest(policyKind=list(changed)),patch.dict(os.environ,config),self.assertRaises((ValueError,RuntimeError)):
                f.adapter.advertised_capabilities(f.target)
    def test_actor_and_global_cleanup_factories_use_original_pinned_artifacts_without_module_environment(self):
        import test_feature_adapters as bound
        f=self.registered_adapter();self.m.flow().observe(self.observe_call());config=self.configuration()
        with patch.object(f.adapter,'state_path',return_value=self.m.state_path('controlled')),patch.dict(os.environ,
            config|dict(OVERTE_DEVICE_ARTIFACT_DIR='',OVERTE_PHONE_GRAPHICS_IMAGE_POLICY='')):
            recovered=f.adapter._graphics_feature(bound.SELECTOR,RUN,retirement=True)
            self.assertEqual(self.m.root,recovered.artifact_root);self.assertEqual(POLICY,recovered.image_policy)
            self.assertEqual('d'*64,recovered.source.client.token)
        with patch.object(f.adapter,'state_path',return_value=self.m.state_path('controlled')),patch.dict(os.environ,
            dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG='',OVERTE_DEVICE_ARTIFACT_DIR='',OVERTE_PHONE_GRAPHICS_IMAGE_POLICY='')):
            actor=f.adapter._graphics_feature(bound.SELECTOR,RUN,role='actor',client=Client(URL,'y'*64))
            self.assertEqual(self.m.root,actor.artifact_root);self.assertEqual('y'*64,actor.source.client.token)
            with self.assertRaises(ValueError):f.adapter._graphics_feature(bound.SELECTOR,RUN,role='actor')
    def test_global_cleanup_attempts_base_teardown_and_preserves_unfinished_graphics(self):
        import test_feature_adapters as bound
        f=self.registered_adapter();flow=self.m.flow();flow.observe(self.observe_call())
        with (patch.object(f.adapter,'state_path',return_value=self.m.state_path('controlled')),patch.object(f.adapter,'_graphics_feature',return_value=flow),
            patch.object(bound.AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base):
            with self.assertRaisesRegex(ValueError,'PHONE_GRAPHICS_.*CLEANUP_INCOMPLETE'):f.adapter.cleanup(bound.SELECTOR)
            base.assert_called_once();self.assertTrue(flow.store.path.exists())
    def test_global_cleanup_finishes_verified_graphics_before_base_teardown(self):
        import test_feature_adapters as bound
        f=self.registered_adapter();flow=self.retirement_ready()
        with (patch.object(f.adapter,'state_path',return_value=self.m.state_path('controlled')),patch.object(f.adapter,'_graphics_feature',return_value=flow) as factory,
            patch.object(bound.AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base):
            self.assertEqual({'cleaned':True},f.adapter.cleanup(bound.SELECTOR));base.assert_called_once()
            factory.assert_called_once_with(bound.SELECTOR,RUN,retirement=True)
        self.assertFalse(flow.store.path.exists());self.assertFalse(flow.retirement_store.path.exists())
    def test_independent_worker_keeps_running_past_retirement_plan_until_its_actual_world_window(self):
        import script_observer
        m=self.m;flow=self.retirement_ready();m.actor_enabled=False
        def yielded(_value):raise RuntimeError('Synthetic parent yielded after ordinary world restoration')
        flow.sleep=yielded
        with self.assertRaises(RuntimeError):flow.finalize()
        self.assertTrue(flow.retirement_store.path.exists());gpu_before=m.gpu.counters['capture'];inputs=list(m.sdk.inputs)
        made=[]
        def factory(selector,run,*,role,client):
            self.assertEqual(('owned',RUN,'actor','y'*64),(selector,run,role,client.token))
            client.request=lambda *args,**kwargs:m.request('actor',*args,**kwargs)
            client.graphics_status=lambda:m.status(client)
            actor=PhoneGraphicsFeature(m,'controlled',GraphicsFixtureReader(client,RUN,epoch_ms=m.epoch),m.root,POLICY,role=role,**m.options())
            made.append(actor);return actor
        adapter=SimpleNamespace(graphics_feature_store=lambda _:flow.store,graphics_retirement_store=lambda _:flow.retirement_store,_graphics_feature=factory)
        config=dict(area='graphics',target='owned',fixtureUrl=URL,actorToken='y'*64,durationSeconds=30)
        with patch.object(flow,'observe',side_effect=AssertionError('Unexpected primary observation')):
            self.assertEqual(0,script_observer.run(adapter,config,**m.options()))
        self.assertEqual(inputs,m.sdk.inputs);self.assertEqual(gpu_before,m.gpu.counters['capture'])
        with made[0].lock.held():self.assertEqual('retired',made[0].observer().state['phase'])
        self.assertEqual({'performed':True},m.flow().finalize())
    def test_graphics_worker_configuration_is_private_versioned_and_separately_credentialed(self):
        import script_observer
        path=self.m.root/'observer-config.json'
        value=dict(featureObserverVersion=2,area='graphics',target='owned',candidateArguments=['--record','private-placeholder'],
            fixtureUrl=URL,actorToken='y'*64,durationSeconds=30)
        store=PrivateFeatureState(path);store.write(value,None);self.assertEqual(value,script_observer.configuration(path))
        for changed in [value|dict(featureObserverVersion=True),value|dict(readerToken='x'*64),value|dict(area='unknown')]:
            store.write(changed,store.read())
            with self.subTest(changedFields=list(changed)),self.assertRaises(NativeUIError):script_observer.configuration(path)

    def test_changed_component_archive_is_retained_and_cannot_be_adopted_on_retry(self):
        m=self.m;flow=self.retirement_ready();write=PrivateFeatureState.write;target='graphics-'+RUN+'-preferences.json'
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path.name==target:raise OSError('Synthetic lost original archive response')
            return result
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(NativeUIError):flow.finalize()
        archive=PrivateFeatureState(m.root/target);original=archive.read();changed=deepcopy(original)
        changed['foreignArchive']=True;archive.write(changed,original);before=list(m.destinations)
        with self.assertRaises(NativeUIError):m.flow().finalize()
        self.assertEqual(changed,archive.read());self.assertEqual(before,m.destinations)
        self.assertTrue(flow.retirement_store.path.exists())

    def test_changed_owner_artifact_profile_is_refused_before_any_new_input(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());before=list(m.sdk.inputs)
        other=PhoneGraphicsFeature(m,'controlled',flow.source,m.root,POLICY|dict(subject=[1,1,4,4]),
            monotonic=lambda:m.sdk.clock,sleep=m.sleep)
        with self.assertRaises(NativeUIError):other.observe(self.observe_call())
        self.assertEqual(before,m.sdk.inputs);self.assertTrue(flow.store.path.exists())

    def test_interrupted_measurement_still_restores_user_world_but_cannot_retire_green(self):
        m=self.m;flow=m.flow();flow.observe(self.observe_call());m.flow('actor').publish();flow.act(self.call('open'))
        # An explicitly corrupted native result leaves an unqualified source
        # intent. Normal preference/world restoration must still be attempted.
        m.native_fault='cursor'
        with self.assertRaises(NativeUIError):flow.observe(self.observe_call())
        m.native_fault=None;m.phase('cleanup')
        with self.assertRaises(NativeUIError):flow.cleanup(dict(contractVersion=18,runId=RUN))
        m.resources.retire(RUN);m.journal.close(RUN);m.client.closed=True
        with self.assertRaises(NativeUIError):flow.finalize()
        self.assertEqual([],m.native.source['entities']);self.assertEqual(m.original['avatarPose'],m.native.source['avatarPose'])
        self.assertTrue(flow.store.path.exists())


if __name__=='__main__':unittest.main()
