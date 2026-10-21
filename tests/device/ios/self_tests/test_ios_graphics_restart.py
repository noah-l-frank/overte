"""Original iOS restart ownership on real host transports, synthetic SDK/kernel."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from feature_journeys.scenarios import VERSION
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_restart import IOSGraphicsRestart
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.graphics_samples import IOSGraphicsSamples
from ios.self_tests.test_ios_graphics_samples import SamplesHarness,POLICY
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET
from self_tests.test_native_scene_loads import Boundary as LoadsSDK
from self_tests.test_native_process_presence import Boundary as PresenceSDK


class RestartHarness(SamplesHarness):
    def setUp(self):
        super().setUp();self.inputs=[];self.dead=set();self.fault='';self.binding_phase='bound';self.recovered=0
        self.adapter.existing_input_session=lambda _:nullcontext()
        self.adapter._graphics_samples=lambda selector,client,run,role,stage,lock,root,policy:IOSGraphicsSamples(
            self.adapter,selector,client,run,role,stage,lock,root,policy,epoch_ms=self.sdk.host_epoch,monotonic=lambda:self.sdk.clock)
        self.bridge=object.__new__(IOSGraphicsRuntime);self.bridge.state_path=self.adapter.state_path
        self.adapter.graphics_restart_owners=self.bridge.graphics_restart_owners
        self.adapter._graphics_restart_input=self.bridge._graphics_restart_input
        self.adapter._graphics_restart_stopped=self.bridge._graphics_restart_stopped
        self.adapter._graphics_recover_launch=self.bridge._graphics_recover_launch
        def invoke(_selector,operation,values):
            need(self.base._operation is None and values=={});self.inputs.append(operation)
            if operation=='app.stop':
                self.binding_phase='retiring'
                if self.fault!='ignored-stop':
                    self.dead.add(self.sdk.pid);self.sdk.running=self.sdk.foreground=False
                if self.fault=='lost-stop':raise OSError('Synthetic lost original terminate return')
                need(not self.sdk.running);self.binding_phase='retired';return dict(stopped=True)
            need(operation=='app.launch' and not self.sdk.running);self.binding_phase='preparing'
            self.sdk.pid+=1;self.sdk.running=self.sdk.foreground=True
            self.sdk.birth='a'*32 if self.fault=='reused-birth' else 'b'*32;self.sdk.loads_birth='d'*32
            self.sdk.native_lifecycle['launches']+=0 if self.fault=='missing-counter' else 1
            self.sdk.native_lifecycle['activations']+=1
            self.sdk.core.sequence=self.sdk.subject.sequence=self.sdk.sequence=0
            self.sdk.instance='11111111-2222-3333-4444-'+str(self.sdk.pid).zfill(12)
            self.sdk.loads=LoadsSDK();self.sdk.scene_rows=[];self.sdk.stage='closed';self.sdk.feet=[0.,0.,0.]
            self.sdk.camera='look at';self.sdk.boom=3.25;self.sdk.initial(self.origin+'/baseline.json');self.gpu.birth='e'*32
            if self.fault=='reset-settings':self.sdk.model.resolution=.6
            if self.fault=='old-alive':self.dead.clear()
            if self.fault=='lost-launch':raise OSError('Synthetic lost original launch return')
            self.binding_phase='bound';return dict(launched=True)
        test=self
        class Gate:
            def record(self):return dict(phase=test.binding_phase)
            def finish_retirement(self):need(not test.sdk.running);test.binding_phase='retired'
            def retired_absence(self):need(not test.sdk.running and test.binding_phase=='retired')
        def recover(_selector,*,inputs):
            need(self.binding_phase=='preparing' and self.sdk.running and self.sdk.foreground
                 and inputs.read()['oldNative']['pid'] in self.dead)
            self.recovered+=1;self.binding_phase='bound'
        self.base=SimpleNamespace(_operation='feature.graphics.act',invoke=invoke,_candidate_guard=lambda **_:None,
            _binding_store=lambda _:SimpleNamespace(read=lambda:dict(phase=self.binding_phase)),_recover_script_restart_launch=recover,
            _script_restart_session=lambda _,**__: (None,dict(sessionId='owned-session'),self.sdk.target),
            _binding=lambda *_:Gate(),reset_launch_state=lambda *_:None)
        self.bridge.adapter=self.base
        original=self.adapter.normal_feature_runtime
        def runtime(*args,**kwargs):
            need(self.binding_phase=='bound');value=list(original(*args,**kwargs))
            if self.sdk.pid!=42 and self.fault=='foreign-candidate':value[2]['artifactSha256']='f'*64
            return tuple(value)
        self.adapter.normal_feature_runtime=runtime
        def presence(*_,**__):
            boundary=PresenceSDK(pid=self.sdk.pid,epoch_ms=self.sdk.epoch)
            def edit(value):
                value['instance']=self.sdk.birth
                if value['queryProcessId'] in self.dead:value.update(presence='absent',nativeResult=-1,nativeError=3,errorSymbol='ESRCH')
            boundary.edit=edit;return boundary.reader(ios=True)
        self.adapter._process_presence=presence

    def prepare(self):
        scene=self.scene();scene.prepare();preferences=IOSGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
        preferences.prepare()
        preferences.act(dict(contractVersion=VERSION,runId=RUN,ticket='1'*32,verb='open',inputs={},fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
        preferences.act(dict(contractVersion=VERSION,runId=RUN,ticket='2'*32,verb='set-resolution',inputs=dict(value=.5),fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
        preferences.act(dict(contractVersion=VERSION,runId=RUN,ticket='3'*32,verb='close',inputs={},fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
        for role in ('primary','actor'):self.samples(role).read(TICKET,self.sdk.host_epoch())
        self.client.activate('8'*32,'restart-app',{})
        return self.restart()
    def restart(self):return IOSGraphicsRestart(self.adapter,'owned',self.client,RUN,self.lock,self.root/'pixels',POLICY,
        monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def call(self):return dict(contractVersion=VERSION,runId=RUN,ticket='8'*32,verb='restart-app',inputs={},fixtureUrl=self.client.url+'/runs/'+RUN+'/')


class RestartTests(RestartHarness,unittest.TestCase):
    def test_normal_restart_drains_both_roles_proves_old_pid_death_and_rebuilds_scene_with_original_preferences(self):
        with self.lock.held():
            restart=self.prepare();self.assertEqual({'performed':True},restart.act(self.call()))
            self.assertEqual(['app.stop','app.launch'],self.inputs);self.assertEqual(43,self.sdk.pid)
            self.assertEqual('applied',restart.state['phase']);self.assertEqual('ESRCH',restart.state['receipt']['exit']['errorSymbol'])
            self.assertEqual(.5,self.sdk.model.resolution);self.assertEqual(7,len(self.sdk.scene_rows))
            self.assertEqual('first person look at',self.sdk.camera)
            self.assertTrue(all(not proof['source']['callbacks'] for role in restart.state['oldDrain'] for proof in role['proofs']))
            self.restart().act(self.call());self.assertEqual(['app.stop','app.launch'],self.inputs)
            scene=self.scene();prefs=IOSGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
            prefs.cleanup();scene.restore();self.assertEqual(.6,self.sdk.model.resolution);self.assertEqual([4.,0.,2.],self.sdk.feet)
            self.assertEqual('feature.graphics.act',self.base._operation)

    def test_lost_stop_is_recovered_while_stopped_without_a_second_terminate(self):
        with self.lock.held():
            restart=self.prepare();self.fault='lost-stop'
            with self.assertRaises(NativeUIError):restart.act(self.call())
            self.assertFalse(self.sdk.running);self.fault='';self.restart().act(self.call())
            self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_lost_launch_adopts_actual_new_process_without_a_second_launch(self):
        with self.lock.held():
            restart=self.prepare();self.fault='lost-launch'
            with self.assertRaises(NativeUIError):restart.act(self.call())
            self.assertTrue(self.sdk.running);self.assertEqual('preparing',self.binding_phase)
            self.fault='';self.restart().act(self.call());self.assertEqual(1,self.recovered)
            self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_ignored_stop_never_launches_or_repeats_terminate(self):
        with self.lock.held():
            restart=self.prepare();self.fault='ignored-stop'
            with self.assertRaises(NativeUIError):restart.act(self.call())
            with self.assertRaises(NativeUIError):self.restart().act(self.call())
            self.assertEqual(['app.stop'],self.inputs)

    def assert_failed_transfer(self,fault):
        with self.lock.held():
            restart=self.prepare();self.fault=fault
            with self.assertRaises(NativeUIError):restart.act(self.call())
            self.assertEqual('prepared',restart.state['phase'])
            self.assertIsNone(unpack_scene(restart.scene_store.read())['handoff'])

    def test_live_old_pid_cannot_transfer_scene(self):self.assert_failed_transfer('old-alive')
    def test_reused_native_birth_cannot_transfer_scene(self):self.assert_failed_transfer('reused-birth')
    def test_missing_original_launch_increment_cannot_transfer_scene(self):self.assert_failed_transfer('missing-counter')
    def test_changed_candidate_cannot_transfer_scene(self):self.assert_failed_transfer('foreign-candidate')
    def test_reset_graphics_preferences_cannot_transfer_scene(self):self.assert_failed_transfer('reset-settings')

    def test_partial_scene_preference_cas_transfer_recovers_without_repeating_restart(self):
        with self.lock.held():
            restart=self.prepare()
            with patch.object(restart.preferences_store,'write',side_effect=OSError('Synthetic lost preference CAS')),self.assertRaises(OSError):restart.act(self.call())
            self.assertEqual('proposed',restart.state['phase'])
            self.assertIsNotNone(unpack_scene(restart.scene_store.read())['handoff'])
            self.assertIsNone(unpack_scene(restart.preferences_store.read())['handoff'])
            self.restart().act(self.call());self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_failed_restart_intent_persistence_prevents_stop(self):
        with self.lock.held():
            restart=self.prepare()
            with patch.object(restart.store,'write',side_effect=OSError('Synthetic failed restart intent')),self.assertRaises(OSError):restart.act(self.call())
            self.assertEqual([],self.inputs);self.assertTrue(self.sdk.running)

    def test_changed_proposed_native_packet_is_not_adopted_as_an_original_handoff(self):
        with self.lock.held():
            restart=self.prepare()
            with patch.object(restart,'apply',side_effect=NativeUIError('Synthetic held CAS proposal')),self.assertRaises(NativeUIError):restart.act(self.call())
            value=deepcopy(restart.previous);state=unpack(value['payload'])[0]
            proposed=state['proposedPreferences'];preferences=unpack(proposed['payload'])[0]
            preferences['native']['requestId']='ios-'+'f'*32;preferences['native']['sequence']+=1
            preferences['native']['graphics']['applicationResolutionScale']=.7
            proposed['payload']=pack([preferences]);value['payload']=pack([state]);restart.store.write(value,restart.previous)
            with self.assertRaises(NativeUIError):self.restart()
            self.assertEqual(['app.stop','app.launch'],self.inputs)


def unpack_scene(value):
    from adapters.script_feature.history import unpack
    return unpack(value['payload'])[0]


if __name__=='__main__':unittest.main()
