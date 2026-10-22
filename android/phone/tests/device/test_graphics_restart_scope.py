"""Synthetic original old/new processes; real private scene/preference CAS handoff."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_scene_loads import NativePhoneSceneLoads,resource_hash
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_graphics_scene import PhoneGraphicsScene
from overte_phone_graphics_preferences import PhoneGraphicsPreferences
from overte_phone_graphics_restart_proof import validate as restart_proof
from overte_phone_script_history import pack,unpack
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_phone_scene_loads import row as load_row
import test_graphics_background as background_fixture

RUN=background_fixture.preferences_fixture.RUN


class Model(background_fixture.Model):
    def __init__(self):
        super().__init__();self.binding=None;self.pid=31;self.birth='a'*32;self.load_birth='a'*32
        self.native.edit=self.subject_edit;self.loads.mutate=self.load_edit
    def subject_edit(self,value):
        value.update(processId=self.pid,instance=self.birth);value['source']['view']['mode']=self.sdk.mode
    def load_edit(self,value):value.update(processId=self.pid,instance=self.load_birth)
    def original_native(self,value):super().original_native(value);value.update(processId=self.pid,instance=self.birth)
    def normal_feature_runtime(self,selector,*,read_only):
        ui,observer,binding,guard,installed=super().normal_feature_runtime(selector,read_only=read_only)
        if self.binding is None:self.binding=deepcopy(binding)
        return ui,observer,deepcopy(self.binding),guard,installed
    def _graphics_subject_observer(self,_selector,*,read_only):
        assert read_only
        return NativeGraphicsSubject(self.native.send,self.native.original,lambda:20000,lambda:self.native.okay and self.foreground,
            self.pid,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def _native_feature_observer(self,_selector,*,read_only):
        assert read_only
        return NativeFeatureObservation(self.features.send,self.features.original,lambda:20000,lambda:self.native.okay and self.foreground,
            self.pid,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def _scene_load_observer(self,_selector,*,read_only):
        assert read_only
        return NativePhoneSceneLoads(self.loads.send,self.loads.original,lambda:20000,lambda:self.native.okay and self.foreground,
            self.pid,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def world_render_store(self,_selector,*,role):
        assert role in ('primary','actor')
        return PrivateFeatureState(self.root/('phone-world-render-'+('actor-' if role=='actor' else '')+'owner.json'))
    def prepare_restart_sources(self,scene,preferences):
        before=preferences.source();old_binding=deepcopy(self.binding)
        old_scene,old_preferences=deepcopy(scene.previous),deepcopy(preferences.previous)
        self.pid=41;self.birth='e'*32;self.load_birth='f'*32;self.binding['processIdentity']='41:77'
        self.lifecycle['launches']+=1;self.lifecycle['activations']+=1
        self.features.sequence=self.native.sequence=self.loads.sequence=0
        self.native.source=deepcopy(self.original);self.loads.generation=1
        self.loads.rows=[load_row(resourceSha256=resource_hash(self.original['sceneUrl']))]
        native=self._native_feature_observer('controlled',read_only=True).read(0)
        presence=PresenceBoundary(pid=41);presence.presence='absent';presence.edit=lambda packet:packet.update(instance=self.birth)
        exit=presence.reader().require_absent(31)
        projection=lambda packet:dict(pid=packet['processId'],instance=packet['instance'],lifecycle=deepcopy(packet['lifecycle']))
        plan=dict(restartInputVersion=1,componentOnly=False,oldBinding=old_binding,oldNative=projection(before),phase='observed',
            newBinding=deepcopy(self.binding),newNative=projection(native),ownerFiles=[str(scene.store.path),
                *[str(self.world_render_store('controlled',role=role).path) for role in ('primary','actor')]],scriptHandoff=None)
        receipt=dict(input=plan,oldNative=before,native=native,exit=exit)
        subject=self._graphics_subject_observer('controlled',read_only=True).read(RUN,require_avatar=True)
        loads=self._scene_load_observer('controlled',read_only=True).read(RUN)
        return old_scene,old_preferences,receipt,subject,loads
    def proposals(self,scene,preferences):
        old_scene,old_preferences,receipt,subject,loads=self.prepare_restart_sources(scene,preferences)
        return (PhoneGraphicsScene.restart_record(old_scene,receipt,subject,loads),
            PhoneGraphicsPreferences.restart_record(old_preferences,receipt),receipt)


class GraphicsRestartScopeTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def call(self,verb,**inputs):
        return dict(contractVersion=18,runId=RUN,ticket=uuid.uuid4().hex,
            fixtureUrl=self.model.client.url+'/runs/'+RUN+'/',verb=verb,inputs=inputs)
    def ready(self):
        m=self.model;scene=m.factory();scene.prepare();preferences=m.preferences(scene);preferences.prepare()
        old_call=self.call('open');preferences.act(old_call)
        preferences.act(self.call('set-resolution',value=.5));preferences.act(self.call('set-haze',enabled=True))
        preferences.act(self.call('close'));return scene,preferences,old_call
    def apply(self,scene,preferences,scene_value,preferences_value):
        scene.store.write(scene_value,scene.previous);preferences.store.write(preferences_value,preferences.previous)
        new_scene=self.model.factory();new_scene.prepare();new_preferences=self.model.preferences(new_scene);new_preferences.prepare()
        return new_scene,new_preferences

    def test_new_process_preserves_initial_originals_and_restores_user_scene_with_new_independent_proof(self):
        m=self.model
        with m.lock.held():
            scene,preferences,old_call=self.ready();original=deepcopy(preferences.state['original']);original_scene=deepcopy(scene.state['original'])
            scene_value,preferences_value,receipt=m.proposals(scene,preferences)
            self.assertEqual(receipt,restart_proof(receipt));new_scene,new_preferences=self.apply(scene,preferences,scene_value,preferences_value)
            self.assertEqual(original,new_preferences.state['original']);self.assertEqual(original_scene,new_scene.state['original'])
            self.assertEqual(31,original['processId']);self.assertEqual(41,new_preferences.state['native']['processId'])
            self.assertEqual(.5,m.fixture.qt.resolution);self.assertTrue(m.fixture.qt.haze)
            before=len(m.sdk.inputs)
            with self.assertRaises(NativeUIError):new_preferences.act(old_call)
            self.assertEqual(before,len(m.sdk.inputs))
            new_preferences.act(self.call('open'));new_preferences.act(self.call('restore-original'));new_preferences.act(self.call('close'))
            self.assertEqual(.65,m.fixture.qt.resolution);self.assertFalse(m.fixture.qt.haze)
            new_preferences.retire();new_scene.restore();new_scene.retire()
            self.assertFalse(new_scene.store.path.exists());self.assertFalse(new_preferences.store.path.exists())

    def test_old_live_objects_cannot_send_input_or_restore_over_new_process_records(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();scene_value,preferences_value,_receipt=m.proposals(scene,preferences)
            new_scene,new_preferences=self.apply(scene,preferences,scene_value,preferences_value);before=len(m.sdk.inputs)
            with self.assertRaises(NativeUIError):preferences.act(self.call('open'))
            with self.assertRaises(NativeUIError):scene.restore()
            self.assertEqual(before,len(m.sdk.inputs));new_preferences.retire();new_scene.restore();new_scene.retire()

    def test_permission_unknown_wrong_old_pid_changed_candidate_and_nonpersisted_preferences_are_not_restart_proof(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();_s,_p,receipt=m.proposals(scene,preferences)
            for fault in ('unknown','query','candidate','preference','launch','same-birth'):
                changed=deepcopy(receipt)
                if fault=='unknown':changed['exit'].update(presence='unknown',nativeError=1,errorSymbol='EPERM')
                elif fault=='query':changed['exit']['queryProcessId']=29
                elif fault=='candidate':changed['input']['newBinding']['artifactSha256']='0'*64
                elif fault=='preference':changed['native']['graphics']['requestedResolutionScale']=.6
                elif fault=='launch':changed['input']['newNative']['lifecycle']['launches']=1
                else:changed['input']['newNative']['instance']=changed['input']['oldNative']['instance']
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):restart_proof(changed)

    def test_missing_original_archive_or_foreign_new_subject_cannot_become_a_scope_transfer(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();scene_value,_preferences_value,_receipt=m.proposals(scene,preferences)
            for fault in ('old-subject','old-load','missing-archive','foreign-run','live-uuid'):
                changed=deepcopy(scene_value);state=unpack(changed['payload'])[0]
                if fault=='old-subject':state['handoff']['subject']['instance']='a'*32
                elif fault=='old-load':state['handoff']['loads']['instance']='a'*32
                elif fault=='missing-archive':state['handoff']['previous']=None
                elif fault=='foreign-run':changed['runId']='0'*32
                else:
                    entity=deepcopy(m.controlled.subject_before['source']['entities'][0])
                    source=state['handoff']['subject']['source'];source['entities'].append(entity);source['absentIds'].remove(entity['id'])
                changed['payload']=pack([state]);before=len(m.sdk.inputs)
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,TypeError)):scene.decode(changed)
                self.assertEqual(before,len(m.sdk.inputs))

    def test_old_pending_ui_or_uncertain_preference_action_cannot_transfer_ownership(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();old_scene,old_preferences,receipt,subject,loads=m.prepare_restart_sources(scene,preferences)
            bad_scene=deepcopy(old_scene);state=unpack(bad_scene['payload'])[0];state['leases']['address']=True;bad_scene['payload']=pack([state])
            with self.assertRaises(NativeUIError):PhoneGraphicsScene.restart_record(bad_scene,receipt,subject,loads)
            bad_preferences=deepcopy(old_preferences);state=unpack(bad_preferences['payload'])[0];state['phase']='issued';bad_preferences['payload']=pack([state])
            with self.assertRaises(NativeUIError):PhoneGraphicsPreferences.restart_record(bad_preferences,receipt)

    def test_scene_and_preference_transfer_cannot_borrow_different_restart_receipts(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();scene_value,preferences_value,_receipt=m.proposals(scene,preferences)
            scene.store.write(scene_value,scene.previous);new_scene=m.factory();new_scene.prepare()
            changed=deepcopy(preferences_value);state=unpack(changed['payload'])[0];state['handoff']['receipt']['exit']['sequence']+=1
            changed['payload']=pack([state]);preferences.store.write(changed,preferences.previous)
            before=len(m.sdk.inputs)
            with self.assertRaises(NativeUIError):m.preferences(new_scene)
            self.assertEqual(before,len(m.sdk.inputs))

    def test_legacy_v1_journals_are_refused_without_silent_original_or_scope_migration(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready()
            changed=deepcopy(scene.previous);changed['graphicsSceneVersion']=1
            with self.assertRaises(NativeUIError):scene.decode(changed)
            changed=deepcopy(preferences.previous);changed['graphicsPreferencesVersion']=1
            with self.assertRaises(NativeUIError):preferences.decode(changed)

    def test_new_legacy_camera_mode_is_changed_only_through_the_normal_view_menu(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();scene_value,preferences_value,_receipt=m.proposals(scene,preferences);m.sdk.mode='first person'
            new_scene,new_preferences=self.apply(scene,preferences,scene_value,preferences_value)
            self.assertIn(('', 'First Person'),m.sdk.inputs);self.assertEqual('first person look at',m.sdk.mode)
            self.assertEqual('observed',new_scene.state['actions'][0]['phase'])
            new_preferences.retire();new_scene.restore();new_scene.retire()

    def test_an_old_original_cannot_be_relabelled_as_a_new_process_observation(self):
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();scene_value,preferences_value,_receipt=m.proposals(scene,preferences)
            scene.store.write(scene_value,scene.previous);new_scene=m.factory();new_scene.prepare()
            changed=deepcopy(preferences_value);state=unpack(changed['payload'])[0];state['original']['processId']=41
            changed['payload']=pack([state]);preferences.store.write(changed,preferences.previous);before=len(m.sdk.inputs)
            with self.assertRaises(NativeUIError):m.preferences(new_scene)
            self.assertEqual(before,len(m.sdk.inputs))

    def test_historical_archives_need_no_sdk_and_cannot_grant_a_second_scope_transfer(self):
        from unittest.mock import patch
        m=self.model
        with m.lock.held():
            scene,preferences,_call=self.ready();scene_value,preferences_value,receipt=m.proposals(scene,preferences)
            proposed=scene.decode(scene_value)
            with patch.object(m,'normal_feature_runtime',side_effect=AssertionError('Archive tried current source admission')):
                actual=PhoneGraphicsScene.archive(scene_value,adapter=m,selector='controlled',client=m.client,run=RUN)
                prior=PhoneGraphicsPreferences.archive(preferences_value,scene=scene,expected_binding=receipt['input']['newBinding'],scene_handoff=proposed['handoff'])
            self.assertEqual(proposed,actual);self.assertEqual(31,prior['original']['processId'])
            new_scene,new_preferences=self.apply(scene,preferences,scene_value,preferences_value)
            with self.assertRaises(NativeUIError):PhoneGraphicsScene.restart_record(new_scene.previous,receipt,
                new_scene.state['handoff']['subject'],new_scene.state['handoff']['loads'])
            new_preferences.retire();new_scene.restore();new_scene.retire()
