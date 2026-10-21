"""Real restart/scene/preference owners with synthetic original OS/Qt sources.

All subprocess calls are intercepted. No ADB, build, device or service runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
from adapters.graphics_journey.restart import GraphicsRestart
from adapters.graphics_journey.scene import GraphicsScene
from adapters.graphics_journey.preferences import GraphicsPreferences
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.graphics_surface import PicoGraphicsSurface
from adapters.pico4.graphics_source import PicoGraphicsSource
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.files import ScriptFileIO
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import unpack
from adapters.token_script_ui import TokenScriptUI
from adapters.restart_inputs import RestartDeliveryUncertain
from self_tests.test_pico_graphics_preferences import Model as Base,RUN
from self_tests.test_pico_graphics_surface import IDENTITY,HomeSource
from self_tests.test_pico_graphics_restart_framework import new_process
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary
from self_tests.test_native_scene_loads import Boundary as LoadBoundary,row as load_row
from self_tests.test_token_graphics_ui import GraphicsBoundary
from self_tests.test_pico_graphics_source import Boundary as UiBoundary
from adapters.native_scene_loads import resource_hash


class Model(Base):
    def __init__(self):
        super().__init__();(self.root/'artifacts').mkdir(mode=0o700)
        self.pid=31;self.identity='31:1111';self.bound=self.identity;self.native.pid=self.pid
        self.instance='a'*32;self.running=True;self.foreground=True;self.candidate=True;self.old_dead=False
        self.launches=1;self.activations=1;self.backgrounds=0;self.events=[];self.recoveries=0;self.fault=None
        self.tablet_sequence=0;self.tablet=None;self.ui_boundary=UiBoundary();self.ui_edit=None
        configuration=('synthetic-profile',self.root)
        self.original_adapter=SimpleNamespace(pico_configuration=configuration,
            _installation=self.installation,require_controlled_debug_identity=self.controlled_identity,
            require_pico_session_identity=lambda _target:self.bound,invoke=self.invoke,
            _script_runtime=self.runtime,_native_feature_observer=self.native_reader,
            _graphics_subject_observer=self.subject_reader,_scene_load_observer=self.loads_reader,
            _graphics_ui_observer=self.graphics_reader,_process_presence=self.presence,
            _script_restart_recover_binding=self.recover_binding,
            _graphics_surface=lambda target,run,intent,owns,lease,allow:self.surface(target,run,intent,owns,lease,allow),
            adb=SimpleNamespace(command=['forbidden-device-access'],
                foreground_package=lambda _target:'org.overte.pico' if self.running and self.foreground else 'com.picovr.home'))
        self.flow=PicoGraphicsBinding(self.original_adapter)
        self.lock=ScriptSourceLock(self.flow.state_path('owned').with_name('script-sources.lock'))
        self.settings=PrivateFeatureState(self.root/'synthetic-product-settings.json')
    def installation(self,_target):
        if not self.candidate:raise NativeUIError('Synthetic candidate changed')
        return dict(sourceRevision='a'*40,artifactSha256='b'*64)
    def controlled_identity(self,_target):self.installation(_target);return self.identity if self.running else None
    def binding(self):
        return dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity=self.identity,
            sessionId=self.native.bridge,generation=0,targetFingerprint=hashlib.sha256(
                ('owned\0'+str(self.original_adapter.pico_configuration)).encode()).hexdigest())
    def navigation(self):
        return PicoNavigation(self.native,self.root/'navigation.json',IDENTITY,self.identity,'http://controlled.invalid/scene.json',
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def runtime(self,_target):
        self.installation(_target)
        if not self.running or not self.foreground:raise NativeUIError('Synthetic native process unavailable')
        return TokenScriptUI(PicoScriptIO(self.navigation()),monotonic=lambda:self.native.clock,sleep=self.native.sleep),None,self.binding()
    def original_native(self,packet):
        super().original_native(packet);packet.update(processId=self.pid,instance=self.instance)
        packet['lifecycle']=dict(backgrounds=self.backgrounds,activations=self.activations,launches=self.launches)
    def guard(self):
        self.native.guard();self.installation('owned')
        if not self.running or not self.foreground:raise NativeUIError('Synthetic current process unavailable')
        return True
    def native_reader(self,_target):
        return NativeFeatureObservation(self.features.send,self.features.original,lambda:self.native.epoch,self.guard,self.pid,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def subject_reader(self,_target):
        def send(request):
            self.subject.epoch=self.native.epoch
            self.subject.edit=lambda value:value.update(processId=self.pid,instance=self.instance)
            self.subject.send(request)
        return NativeGraphicsSubject(send,self.subject.original,lambda:self.native.epoch,self.guard,self.pid,require_framework=True,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def loads_reader(self,_target):
        from adapters.native_scene_loads import NativeSceneLoads
        def send(request):
            self.loads.epoch=self.native.epoch;self.loads.mutate=lambda value:value.update(processId=self.pid,instance=self.instance)
            self.loads.send(request)
        return NativeSceneLoads(send,self.loads.original,lambda:self.native.epoch,self.guard,self.pid,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def graphics_reader(self,_target):
        boundary=self.ui_boundary;boundary.epoch=self.native.epoch;boundary.clock=self.native.clock
        boundary.shown=self.native.opened;boundary.controls=[];boundary.roots=[]
        def edit(packet):
            packet.update(processId=self.pid,instance=self.instance,graphicsObservationVersion=2,
                composition=dict(compositionVersion=1,complete=False))
            if self.ui_edit:self.ui_edit(packet)
        boundary.edit=edit
        original=SimpleNamespace(adb=SimpleNamespace(write_debug_app_file=boundary.write,read_debug_app_file=boundary.read))
        native=SimpleNamespace(pid=self.pid,guard=self.guard,clock_ms=lambda:self.native.epoch,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        # The actual source transport is exercised; its target is synthetic.
        return PicoGraphicsSource(original,'synthetic',native)
    def script_io(self,_target,*,read_only=False):
        def send(envelope):
            request=envelope['request'];self.tablet_sequence+=1
            self.tablet=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance=self.instance,
                generation='e'*32,sourceSequence=self.tablet_sequence,lastCommandSequence=0,elapsedMs=round(self.native.clock*1000),
                capturedEpochMs=self.native.epoch,processId=self.pid,fileControlsVersion=1,ready=True,controls=[],
                scriptInventory=dict(inventoryVersion=1,complete=True,managers=[],pickers=[],tabletPresent=True,tabletShown=self.native.opened))
        return ScriptFileIO(send,lambda:json.dumps(self.tablet),lambda:self.native.epoch,self.guard,self.pid,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def presence(self,_target):
        boundary=PresenceBoundary(pid=self.pid,epoch_ms=lambda:self.native.epoch)
        boundary.presence='unknown' if self.fault=='unknown-exit' else 'absent' if self.old_dead else 'present'
        boundary.edit=lambda value:value.update(instance=self.instance)
        return boundary.reader()
    def surface(self,target,run,intent,owns,lease,allow):
        ui=TokenScriptUI(PicoScriptIO(self.navigation()),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        def remember(stage,subject,source,control):self.native.intent(stage,subject,source,control);intent(stage,subject,source,control)
        home=HomeSource(self.native)
        return PicoGraphicsSurface(ui,self.subject_reader(target),PicoTabletHome(home,home.stage),run,remember,owns,lease,allow)
    def scene(self):return GraphicsScene(self.flow,'owned',self.client,RUN,self.lock,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def restart(self):
        return GraphicsRestart(self.flow,'owned',self.client,RUN,self.lock,artifact_root=self.root/'artifacts',
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def invoke(self,_target,operation,values):
        self.installation(_target);assert values=={};self.events.append(operation)
        if operation=='app.stop':
            if self.fault=='ignored-stop':return dict(stopped=True)
            self.settings.write(dict(resolution=self.native.graph.resolution,haze=self.native.graph.haze,mirrors=self.native.graph.mirrors),None)
            self.running=False;self.bound=None;self.old_dead=True
            if self.fault=='lost-stop':raise OSError('Synthetic lost applied stop reply')
        elif operation=='app.launch':
            if self.fault=='ignored-launch':return dict(launched=True)
            saved=self.settings.read();self.pid=32;self.identity='32:2222';self.instance='f'*32
            self.running=True;self.foreground=True;self.launches+=1;self.activations+=1
            self.native.pid=self.pid;self.native.bridge='22222222-2222-4222-8222-222222222222'
            self.native.generation='33333333-3333-4333-8333-333333333333'
            self.native.opened=False;self.native.page='home';self.native.focused=False;self.native.graph=GraphicsBoundary(generic=True)
            if self.fault!='lost-settings':
                self.native.graph.resolution=saved['resolution'];self.native.graph.haze=saved['haze'];self.native.graph.mirrors=saved['mirrors']
            source=dict(schemaVersion=1,requestId=uuid.uuid4().hex,runId=RUN,instance='a'*32,sequence=1,
                processId=31,requestedEpochMs=self.native.epoch,capturedEpochMs=self.native.epoch,source=deepcopy(self.original))
            self.original=new_process(source)['source'];self.subject=SubjectBoundary();self.subject.source=deepcopy(self.original)
            self.loads=LoadBoundary();self.loads.rows=[load_row(resourceSha256=resource_hash(self.original['sceneUrl']))]
            self.features.sequence=0;self.ui_boundary=UiBoundary();self.tablet_sequence=0
            self.bound=None if self.fault=='lost-launch' else self.identity
            if self.fault=='lost-launch':raise OSError('Synthetic launch completed before its host binding reply')
        else:raise AssertionError('Unexpected normal restart input')
        return dict(performed=True)
    def recover_binding(self,_target,*,restart_inputs,owner_check,monotonic):
        # The generic native/Pico binding recoverer is independently tested.
        # This SDK boundary verifies this controller's exact original owner
        # callback and simulates only its host-side binding, never a launch.
        self.recoveries+=1;owner_check();assert restart_inputs.read()['phase']=='launch-issued'
        if not self.running:raise NativeUIError('Synthetic launch has no current process')
        self.bound=self.identity
    def query(self,argv,**options):
        assert argv[:8]==['forbidden-device-access','-s','owned','exec-out','run-as','org.overte.pico','/system/bin/ps','-p']
        assert argv[-2:]==['-o','PID'];pid=int(argv[8]);assert pid==31
        if self.fault=='unknown-stop':return subprocess.CompletedProcess(argv,2,b'PID\n',b'permission denied')
        present=not self.old_dead
        return subprocess.CompletedProcess(argv,0 if present else 1,b'PID\n31\n' if present else b'PID\n',b'')


class PicoGraphicsRestartTests(unittest.TestCase):
    def setUp(self):
        self.model=Model();self.addCleanup(self.model.close);self.enterContext(self.model.lock.held())
        self.enterContext(patch('adapters.android_process_query.subprocess.run',side_effect=self.model.query))
        # Use the actual nonce-only Script file source at the existing facade.
        self.model.flow._script_file_io=self.model.script_io
    def ready(self):
        m=self.model;scene=m.scene();scene.prepare();preferences=GraphicsPreferences(scene,monotonic=lambda:m.native.clock,sleep=m.native.sleep)
        preferences.prepare()
        call=dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=m.client.url+'/runs/'+RUN+'/',verb='open',inputs={})
        preferences.act(call);call.update(ticket=uuid.uuid4().hex,verb='set-resolution',inputs=dict(value=.5))
        preferences.act(call)
        call.update(ticket=uuid.uuid4().hex,verb='close',inputs={});preferences.act(call)
        restart=dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=m.client.url+'/runs/'+RUN+'/',verb='restart-app',inputs={})
        return scene,preferences,restart
    def test_normal_stop_launch_rebuilds_the_actual_new_bridge_and_preserves_original_scene_and_preferences(self):
        m=self.model;scene,preferences,call=self.ready();old_scene=deepcopy(scene.previous);old_preferences=deepcopy(preferences.previous)
        owner=m.restart();self.assertEqual(dict(performed=True),owner.act(call))
        self.assertEqual(['app.stop','app.launch'],m.events);self.assertEqual(32,m.pid)
        current=m.scene();self.assertEqual(owner.state['oldScene'],current.state['handoff']['previous'])
        self.assertEqual(unpack(old_scene['payload'])[0]['original'],current.state['original'])
        self.assertNotEqual(current.state['binding']['sessionId'],scene.state['binding']['sessionId'])
        self.assertEqual(2,owner.state['receipt']['graphicsRestartProofVersion'])
        preferences=GraphicsPreferences(current,monotonic=lambda:m.native.clock,sleep=m.native.sleep)
        self.assertEqual(owner.state['oldPreferences'],preferences.state['handoff']['previous'])
        self.assertEqual(unpack(old_preferences['payload'])[0]['original'],preferences.state['original'])
        self.assertEqual(.5,preferences.state['native']['graphics']['requestedResolutionScale'])

    def test_lost_applied_stop_or_launch_never_replays_input_and_recovers_only_original_pending_scope(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='lost-launch';owner=m.restart()
        with self.assertRaises(RestartDeliveryUncertain):owner.act(call)
        self.assertTrue(m.running);self.assertIsNone(m.bound);self.assertEqual('launch-issued',owner.inputs.read()['phase'])
        self.assertEqual(['app.stop','app.launch'],m.events)
        m.fault=None;m.restart().act(call)
        self.assertEqual(m.identity,m.bound);self.assertGreaterEqual(m.recoveries,1)
        self.assertEqual(['app.stop','app.launch'],m.events)

    def test_lost_stop_reply_is_completed_by_original_stopped_query_before_one_launch(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='lost-stop';owner=m.restart()
        with self.assertRaises(RestartDeliveryUncertain):owner.act(call)
        self.assertFalse(m.running);self.assertEqual('stop-issued',owner.inputs.read()['phase'])
        m.fault=None;m.restart().act(call);self.assertEqual(['app.stop','app.launch'],m.events)

    def test_ignored_stop_has_no_launch_or_automatic_stop_replay(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='ignored-stop';owner=m.restart()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(['app.stop'],m.events)
        with self.assertRaises(NativeUIError):m.restart().act(call)
        self.assertEqual(['app.stop'],m.events)

    def test_ignored_launch_keeps_unresolved_launch_intent_without_bootstrapping_a_replacement(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='ignored-launch';owner=m.restart()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertFalse(m.running);self.assertEqual('launch-issued',owner.inputs.read()['phase'])
        with self.assertRaises(NativeUIError):m.restart().act(call)
        self.assertEqual(['app.stop','app.launch'],m.events)

    def test_unknown_original_pid_query_prevents_launch_even_after_an_acknowledged_stop(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='unknown-stop'
        with self.assertRaises(NativeUIError):m.restart().act(call)
        self.assertEqual(['app.stop'],m.events)

    def test_unqualified_native_exit_or_lost_actual_preferences_cannot_transfer_owners(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='unknown-exit';owner=m.restart()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual('prepared',owner.state['phase']);self.assertEqual('observed',owner.inputs.read()['phase'])
        self.assertIsNone(unpack(owner.scene_store.read()['payload'])[0]['handoff'])
        with self.assertRaises(NativeUIError):m.restart().act(call)
        self.assertEqual(['app.stop','app.launch'],m.events)

    def test_lost_persisted_setting_is_reported_from_the_new_native_source_without_repair(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='lost-settings';owner=m.restart()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(.6,m.native.graph.resolution);self.assertEqual('prepared',owner.state['phase'])
        self.assertEqual(['app.stop','app.launch'],m.events)

    def test_partial_owner_transfer_recovers_the_exact_saved_proposal_without_restart_replay(self):
        m=self.model;_scene,_preferences,call=self.ready();owner=m.restart();write=owner.preferences_store.write
        def lost(new,old):raise OSError('Synthetic interrupted preference transfer')
        with patch.object(owner.preferences_store,'write',side_effect=lost),self.assertRaises(OSError):owner.act(call)
        self.assertEqual('proposed',owner.state['phase']);self.assertIsNotNone(m.scene().state['handoff'])
        m.restart().act(call);self.assertEqual(['app.stop','app.launch'],m.events)
        self.assertEqual('applied',m.restart().state['phase'])

    def test_normal_restoration_and_original_final_archives_retire_restart_intent_after_owner_absence(self):
        m=self.model;_scene,_preferences,call=self.ready();owner=m.restart();owner.act(call)
        scene=m.scene();preferences=GraphicsPreferences(scene,monotonic=lambda:m.native.clock,sleep=m.native.sleep)
        preferences.retire();final_preferences=deepcopy(preferences.previous)
        scene.restore();scene.retire();final_scene=deepcopy(scene.previous)
        owner=m.restart();owner.retire(final_scene,final_preferences)
        self.assertIsNone(owner.store.read());self.assertIsNone(owner.inputs.store.read())
        self.assertEqual(.6,m.native.graph.resolution);self.assertEqual(['app.stop','app.launch'],m.events)
        archives=list((m.root/'artifacts').glob('graphics-restart-*.json'))
        self.assertGreaterEqual(len(archives),4)
        self.assertTrue(all(path.stat().st_mode & 0o777==0o600 for path in archives))

    def pending_launch(self):
        m=self.model;_scene,_preferences,call=self.ready();m.fault='lost-launch';owner=m.restart()
        with self.assertRaises(RestartDeliveryUncertain):owner.act(call)
        m.fault=None;return owner,call

    def test_missing_original_archive_prevents_reconstruction_before_any_recovery_input(self):
        m=self.model;owner,_call=self.pending_launch()
        reference=unpack(owner.previous['payload'])[0]['oldScene']
        (m.root/'artifacts'/reference['name']).unlink()
        with self.assertRaises(NativeUIError):m.restart()
        self.assertEqual(0,m.recoveries);self.assertEqual(['app.stop','app.launch'],m.events)
        self.assertIsNotNone(owner.store.read())

    def test_changed_original_archive_cannot_be_accepted_under_the_saved_hash(self):
        m=self.model;owner,_call=self.pending_launch()
        reference=unpack(owner.previous['payload'])[0]['oldPreferences']
        archive=PrivateFeatureState(m.root/'artifacts'/reference['name']);previous=archive.read()
        modified=deepcopy(previous);modified['runId']='foreign-run';archive.write(modified,previous)
        with self.assertRaises(NativeUIError):m.restart()
        self.assertEqual(0,m.recoveries);self.assertEqual(['app.stop','app.launch'],m.events)

    def test_archive_reference_cannot_escape_the_private_immutable_artifact_namespace(self):
        m=self.model;owner,_call=self.pending_launch()
        reference=deepcopy(unpack(owner.previous['payload'])[0]['oldScene'])
        reference['name']='../graphics-scene.json'
        with self.assertRaises(NativeUIError):owner.load_record(reference)
        self.assertEqual(0,m.recoveries)

    def test_changed_mutable_owner_prevents_rebinding_after_a_lost_launch_reply(self):
        m=self.model;owner,call=self.pending_launch()
        old=owner.scene_store.read();modified=deepcopy(old);modified['runId']='foreign-run'
        owner.scene_store.write(modified,old)
        with self.assertRaises(NativeUIError):m.restart().act(call)
        self.assertEqual(0,m.recoveries);self.assertEqual(['app.stop','app.launch'],m.events)

    def test_retained_native_graphics_root_blocks_transfer_without_hiding_or_replaying_it(self):
        m=self.model;_scene,_preferences,call=self.ready()
        def retained(packet):
            packet['graphicsInventory']['roots']=[dict(id='d'*32,profile='graphics-generic-v1',visible=False,
                inCurrentTree=False,callbackRunning=False,callbackItemPresent=False)]
        m.ui_edit=retained;owner=m.restart()
        with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual('observed',owner.state['phase'])
        self.assertIsNone(unpack(owner.scene_store.read()['payload'])[0]['handoff'])
        with self.assertRaises(NativeUIError):m.restart().act(call)
        self.assertEqual(['app.stop','app.launch'],m.events)


if __name__=='__main__':unittest.main()
