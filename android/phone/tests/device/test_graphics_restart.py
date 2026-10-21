"""Actual restart coordinator/one-send engine with synthetic SDK, OS and native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.normal_ui import NativeUIError
from adapters.native_phone_scene_loads import resource_hash
from overte_phone_graphics_restart import PhoneGraphicsRestart
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_phone_scene_loads import row as load_row
import test_graphics_restart_scope as scope_fixture

RUN=scope_fixture.RUN


class Model(scope_fixture.Model):
    def __init__(self):
        super().__init__();self.running=True;self.presence='absent';self.foreign_preferences=False;self.kernel=None
    def new_process(self):
        self.pid=41;self.birth='e'*32;self.load_birth='f'*32;self.binding['processIdentity']='41:77'
        self.running=self.foreground=True;self.lifecycle['launches']+=1;self.lifecycle['activations']+=1
        self.features.sequence=self.native.sequence=self.loads.sequence=0
        self.native.source=deepcopy(self.original);self.loads.generation=1
        self.loads.rows=[load_row(resourceSha256=resource_hash(self.original['sceneUrl']))]
        if self.foreign_preferences:self.fixture.qt.resolution=.6
    def invoke(self,_selector,operation,values):
        assert values=={};self.normal_inputs.append(operation)
        if self.ignore!=operation:
            if operation=='app.stop':self.running=self.foreground=False;self.lifecycle['backgrounds']+=1
            elif operation=='app.launch':
                assert not self.running;self.new_process()
            else:raise AssertionError('Unexpected synthetic process input')
        if self.lose==operation:raise RuntimeError('Synthetic lost process input response')
        return {'stopped':True} if operation=='app.stop' else {'launched':True}
    def _graphics_restart_stopped(self,_selector,binding):
        assert binding['processIdentity']=='31:14'
        return dict(running=self.running,identity=self.binding['processIdentity'] if self.running else None)
    def _process_presence(self,_selector,*,read_only):
        assert read_only;source=PresenceBoundary(pid=self.pid);source.presence=self.presence
        source.edit=lambda packet:packet.update(instance=self.birth);self.kernel=source;return source.reader()
    def restart(self):
        return PhoneGraphicsRestart(self,'controlled',self.client,RUN,self.lock,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)


class GraphicsRestartTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def call(self):
        return dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,
            fixtureUrl=self.model.client.url+'/runs/'+RUN+'/',verb='restart-app',inputs={})
    def ready(self):
        m=self.model;scene=m.factory();scene.prepare();preferences=m.preferences(scene);preferences.prepare()
        def call(verb,**inputs):return self.call()|dict(verb=verb,inputs=inputs,ticket=uuid.uuid4().hex)
        preferences.act(call('open'));preferences.act(call('set-resolution',value=.5))
        preferences.act(call('set-haze',enabled=True));preferences.act(call('close'));return m.restart()
    def final_archives(self):
        m=self.model;scene=m.factory();preferences=m.preferences(scene);preferences.retire();scene.restore();scene.retire()
        return deepcopy(scene.previous),deepcopy(preferences.previous)
    def retire(self,restart):restart.retire(*self.final_archives())

    def test_normal_explicit_restart_uses_original_kernel_lifecycle_and_cas_before_reentry(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call();self.assertEqual({'performed':True},restart.act(call))
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.assertEqual('applied',restart.state['phase'])
            self.assertEqual('absent',restart.state['receipt']['exit']['presence']);self.assertEqual(41,m.pid)
            self.assertEqual(.5,m.fixture.qt.resolution);self.assertTrue(m.fixture.qt.haze);self.assertEqual(4,len(m.destinations))
            self.retire(restart);self.assertEqual(.65,m.fixture.qt.resolution);self.assertFalse(m.fixture.qt.haze)
            self.assertFalse(restart.store.path.exists());self.assertFalse(restart.inputs.store.path.exists())

    def test_lost_stop_response_recovers_without_second_stop_or_session_repair(self):
        m=self.model;m.lose='app.stop'
        with m.lock.held():
            restart=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):restart.act(call)
            self.assertFalse(m.running);m.lose='';restart=m.restart();restart.act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_lost_launch_response_recovers_from_new_native_and_old_pid_absence_without_replay(self):
        m=self.model;m.lose='app.launch'
        with m.lock.held():
            restart=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):restart.act(call)
            self.assertTrue(m.running);m.lose='';restart=m.restart();restart.act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_ignored_stop_remains_owned_and_cannot_launch_or_repeat_stop(self):
        m=self.model;m.ignore='app.stop'
        with m.lock.held():
            restart=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):restart.act(call)
            m.ignore=''
            with self.assertRaises(NativeUIError):m.restart().act(call)
            self.assertEqual(['app.stop'],m.normal_inputs);self.assertTrue(restart.store.path.exists())

    def test_ignored_launch_remains_owned_without_automatic_second_launch(self):
        m=self.model;m.ignore='app.launch'
        with m.lock.held():
            restart=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):restart.act(call)
            m.ignore=''
            with self.assertRaises(NativeUIError):m.restart().act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.assertFalse(m.running)

    def test_permission_unknown_cannot_admit_new_scope_then_actual_absence_can_resume_without_input(self):
        m=self.model;m.presence='unknown'
        with m.lock.held():
            restart=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):restart.act(call)
            self.assertEqual('prepared',restart.state['phase']);self.assertEqual(2,len(m.destinations))
            m.presence='absent';restart=m.restart();restart.act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_restart_ack_with_lost_native_preferences_cannot_create_scope_proposals(self):
        m=self.model;m.foreign_preferences=True
        with m.lock.held():
            restart=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):restart.act(call)
            self.assertEqual('prepared',restart.state['phase']);self.assertEqual(2,len(m.destinations))
            with self.assertRaises(NativeUIError):m.restart().act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs)

    def test_partial_cas_write_recovers_from_exact_old_or_proposed_values_without_restarting(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call()
            with patch.object(restart.preferences_store,'write',side_effect=OSError('Synthetic interrupted preference transfer')),self.assertRaises(OSError):restart.act(call)
            self.assertEqual('proposed',restart.state['phase']);self.assertEqual(restart.state['proposedScene'],restart.scene_store.read())
            self.assertEqual(2,len(m.destinations));restart=m.restart();restart.act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_lost_cas_write_response_does_not_overwrite_or_redeliver_already_applied_scope(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call();original=restart.preferences_store.write
            def lost(*args):original(*args);raise OSError('Synthetic lost successful transfer response')
            with patch.object(restart.preferences_store,'write',side_effect=lost),self.assertRaises(OSError):restart.act(call)
            self.assertEqual(restart.state['proposedPreferences'],restart.preferences_store.read())
            restart=m.restart();restart.act(call);self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_ignored_cas_write_is_not_applied_and_later_recovery_uses_actual_readback(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call()
            with patch.object(restart.preferences_store,'write',return_value=None),self.assertRaises(NativeUIError):restart.act(call)
            self.assertEqual('proposed',restart.state['phase']);self.assertEqual(restart.state['oldPreferences'],restart.preferences_store.read())
            restart=m.restart();restart.act(call);self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_foreign_partial_scope_is_preserved_and_never_overwritten_as_a_proposal(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call()
            with patch.object(restart.preferences_store,'write',side_effect=OSError('Synthetic transfer interruption')),self.assertRaises(OSError):restart.act(call)
            value=restart.scene_store.read();restart.scene_store.write({'foreign':True},value);before=len(m.sdk.inputs)
            with self.assertRaises(NativeUIError):m.restart().act(call)
            self.assertEqual({'foreign':True},restart.scene_store.read());self.assertEqual(before,len(m.sdk.inputs))

    def test_repeated_restart_ticket_only_reacquires_originals_and_never_repeats_navigation(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call();restart.act(call);before=list(m.sdk.inputs)
            restart=m.restart();restart.act(call);self.assertEqual(before,m.sdk.inputs)
            with self.assertRaises(NativeUIError):restart.act(self.call())
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_failed_pre_stop_owner_write_prevents_any_process_input_and_can_recover_prepared_plan(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call()
            with patch.object(restart.store,'write',side_effect=OSError('Synthetic lost restart scope intent')),self.assertRaises(OSError):restart.act(call)
            self.assertEqual([],m.normal_inputs);self.assertEqual('prepared',restart.inputs.read()['phase'])
            restart=m.restart();restart.act(call);self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_unretired_gpu_scope_prevents_any_stop_input(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();store=m.world_render_store('controlled',role='actor');store.write({'unresolved':True},None)
            with self.assertRaises(NativeUIError):restart.act(self.call())
            self.assertEqual([],m.normal_inputs);self.assertEqual({'unresolved':True},store.read())

    def test_missing_new_subject_result_stays_observed_then_recovers_without_process_input_replay(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();call=self.call();base=m.invoke
            def missing(*args):
                result=base(*args)
                if args[1]=='app.launch':m.native.ignored=True
                return result
            with patch.object(m,'invoke',side_effect=missing),self.assertRaises(NativeUIError):restart.act(call)
            self.assertEqual('observed',restart.state['phase']);self.assertEqual(2,len(m.destinations))
            m.native.ignored=False;restart=m.restart();restart.act(call)
            self.assertEqual(['app.stop','app.launch'],m.normal_inputs);self.retire(restart)

    def test_retirement_rejects_missing_final_archives_and_ignored_input_or_owner_discard(self):
        m=self.model
        with m.lock.held():
            restart=self.ready();restart.act(self.call());scene_value,preferences_value=self.final_archives()
            with self.assertRaises(NativeUIError):restart.retire()
            with patch.object(restart.inputs.store,'discard',return_value=None),self.assertRaises(NativeUIError):restart.retire(scene_value,preferences_value)
            self.assertTrue(restart.inputs.store.path.exists());restart=m.restart()
            with patch.object(restart.store,'discard',return_value=None),self.assertRaises(NativeUIError):restart.retire()
            self.assertTrue(restart.store.path.exists());m.restart().retire()
