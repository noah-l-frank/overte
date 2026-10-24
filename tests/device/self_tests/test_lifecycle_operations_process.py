"""Same normal primary graph, original SDK/FD restart and actual G1 sources.

OS/native/Qt/physics producers remain explicit models. No independent Actor,
image, execute or public feature claim is supplied by this private diagnostic.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.pending_commit_owner import NativePendingCommitOwner
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from adapters.pico4.lifecycle_process_observation import PicoLifecycleProcessObservation
from adapters.pico4.lifecycle_restart_runtime import PicoLifecycleRestartRuntime
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context
from self_tests import test_pico_lifecycle_editor as editor_fixture
from self_tests import test_pico_lifecycle_restore as restore_fixture
from self_tests import test_pico_lifecycle_operations as operations_fixture
from self_tests.test_pico_chat_restart_io import RestartBoundary
from self_tests.test_pending_commit_owner import Boundary as PendingBoundary


class LifecycleOperationsProcessTests(unittest.TestCase):
    fields=operations_fixture.LifecycleOperationsTests.fields
    run_seven=operations_fixture.LifecycleOperationsBackgroundTests.run_seven
    coordinator_attach_roles={'chat','background','pending','close'}

    def at_prefix(self,probe):
        outer=self;original_make=editor_fixture.LifecycleEditorTests.make
        class SDK(RestartBoundary):
            def __init__(self,editor):
                self.editor=editor;self.pico_configuration=('explicit-lifecycle-layer',editor.root)
                self.profile=dict(package='org.overte.pico',e2e_activity='org.overte.pico/.E2eLauncherActivity')
                self.adb=self;self.target='synthetic-lifecycle-target';self.command=['never-execute-synthetic-adb']
                self.identity=editor.binding['processIdentity'];self.running=True;self.session=editor.session
                self.trace=[];self.lost=None;self.effect=True;self.helper=None
                self.installed={key:editor.binding[key] for key in ('sourceRevision','artifactSha256')}
            @property
            def clock(self):return self.editor.native.clock
            @property
            def epoch(self):return self.editor.native.epoch()
            def _installation(self,target):self.require(target);return self.installed|dict(schemaVersion=1,installedCandidateVerified=True)
            def shell(self,target,*arguments):
                self.require(target);self.trace.append(('shell',arguments))
                if arguments==('am','force-stop','org.overte.pico'):
                    self.running=False;self.editor.native.alive=False;operation='stop'
                else:
                    outer.assertEqual(('am','start','-W','-n',self.profile['e2e_activity']),arguments)
                    self.helper.new_process(inputs=False);restore_fixture.disconnected(self.helper.new_domain_boundary)
                    self.helper.new_native.drive.source['sceneUrl']=self.scene
                    self.running=True;self.identity='124:500';operation='launch'
                    self.native,self.presence=self.helper.new_feature,self.helper.presence_boundary
                    original=self.native.mutate
                    actual=self.helper.process.inputs.read()['oldNative']['lifecycle']
                    # One actual modeled SDK start increments the producer's
                    # retained lifecycle state before any new source query.
                    self.lifecycle=dict(backgrounds=actual['backgrounds'],activations=actual['activations']+1,launches=actual['launches']+1)
                    def started(value):original(value);value['lifecycle'].update(self.lifecycle)
                    self.native.mutate=started
                if operation==self.lost:raise OSError('Actual original SDK reply lost')
                return ''
            def write_control_command(self,target,identity,operation,request):
                outer.assertTrue(self.running);outer.assertEqual(self.identity,identity)
                if request['action']=='feature-native-observe':self.native.send(request)
                elif request['action']=='feature-process-presence':self.presence.send(request)
                else:raise AssertionError('No Chat profile query or mutation is permitted')
            def read_debug_app_file(self,target,package,path,attempts):
                outer.assertEqual('org.overte.pico',package);outer.assertEqual(1,attempts)
                if path.endswith('/feature-native-observation.json'):return self.native.original()
                if path.endswith('/feature-process-presence.json'):return self.presence.original()
                raise AssertionError('Only original native/presence result files before transfer')
        def make(editor):
            if getattr(editor,'owner',None) is None:
                self.sdk=SDK(editor)
                editor.binding=editor.binding|dict(targetFingerprint=hashlib.sha256(
                    (self.sdk.target+'\0'+str(self.sdk.pico_configuration)).encode()).hexdigest())
            return original_make(editor)
        with patch.object(editor_fixture.LifecycleEditorTests,'make',make),patch('adapters.android_process_query.subprocess.run',side_effect=lambda *args,**kwargs:self.sdk.ps(*args,**kwargs)):
            return operations_fixture.LifecycleOperationsTests.at_prefix(self,probe)

    def after_actions(self,case,waiter,children):
        self.sdk.helper=case.fixture.helper;self.sdk.scene=case.fixture.configured_scene
        process=self.source.restore.process
        binding=deepcopy(self.source.binding)|dict(processIdentity='124:500',sessionId='new-original-bridge',generation=2)
        def restart(operations):
            io=PicoChatRestartIO(self.sdk,self.sdk.target,self.source.binding,monotonic=lambda:self.native.clock,sleep=self.sdk.helper.sleep)
            self.addCleanup(io.close_host)
            return PicoLifecycleRestartRuntime(operations,io,self.source.native,lambda:self.sdk.helper.observe(binding))
        def successor(operations,handoff):
            boundary=PendingBoundary();boundary.epoch=self.sdk.helper.new_native.epoch
            original=boundary.original
            def raw():
                import json
                value=json.loads(original());value.update(processId=124,instance='1'*32);value['current']=dict(status='none')
                return json.dumps(value)
            pending=NativePendingCommitOwner(boundary.send,raw,boundary.epoch,lambda:self.sdk.running,124,
                monotonic=lambda:self.native.clock,sleep=self.sdk.helper.sleep)
            return PicoLifecycleProcessObservation(operations,operations.runtime,pending,
                self.source.store.path.with_name('lifecycle-primary-process-observation.json'))
        self.operations.factories.update(restart=restart,cleanup_source=successor)
        world_before=len(self.source.world.state['frames']);old_sequence=waiter.journey.sequence
        self.assertEqual((126,71),(world_before,old_sequence))
        self.journal.activate(self.source.run,__import__('uuid').uuid4().hex,'cleanup')
        waiter.journey.required_lifecycle=None
        fault=getattr(self,'process_fault',None);triggered=[]
        if fault in ('lost-stop','lost-launch'):self.sdk.lost=fault.removeprefix('lost-')
        if fault in ('phase-stop','phase-launch'):
            write=process.inputs.store.write
            def changed(value,previous):
                write(value,previous)
                if value['phase']==fault.removeprefix('phase-')+'-issued' and not triggered:
                    triggered.append(True);self.journal.activate(self.source.run,__import__('uuid').uuid4().hex,'cleanup')
            process.inputs.store.write=changed
        held=self.source.lock.held;depth=[0]
        @contextmanager
        def exit_fault():
            with held():
                depth[0]+=1
                try:yield
                finally:depth[0]-=1
            if depth[0]==0 and self.operations.state['cleanup'] is not None and self.operations.state['cleanup']['phase']=='returned' and not triggered:
                triggered.append(True)
                if fault=='memo':process._final_delivery=dict(process._final_delivery)
                elif fault=='clock':
                    source=process._final_delivery['source'];clock=source.clock_ms
                    source.clock_ms=lambda:clock()+2000
                elif fault=='outer-exit':
                    path=self.operations.store.path;replacement=path.with_name('known-test-operations-replacement.json')
                    replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        if fault:
            with patch.object(self.source.lock,'held',exit_fault if fault in ('memo','clock','outer-exit') else held):
                with self.assertRaises(NativeUIError):waiter.journey.call('cleanup',{})
            shells=[item for item in self.sdk.trace if type(item) is tuple and item[0]=='shell']
            expected={'lost-stop':1,'lost-launch':2,'phase-stop':0,'phase-launch':1,'memo':2,'clock':2,'outer-exit':2}[fault]
            self.assertEqual(expected,len(shells));self.assertTrue(self.operations.failed)
            self.assertEqual(126,len(self.source.world.state['frames']));self.assertEqual(71,waiter.journey.sequence)
            before=len(shells)
            with self.assertRaises(NativeUIError):waiter.journey.call('cleanup',{})
            self.assertEqual(before,len([item for item in self.sdk.trace if type(item) is tuple and item[0]=='shell']))
            if fault in ('phase-stop','phase-launch','memo','clock','outer-exit'):self.assertEqual([True],triggered)
            return
        waiter.journey.call('cleanup',{})
        self.assertIs(process._final_delivery,self.operations.runtime.memo)
        self.assertIs(process._final_delivery['readers'],self.operations.runtime.readers)
        self.assertEqual(126,len(self.source.world.state['frames']))
        self.assertTrue(2<=len(process.state['next']['frames'])<=64)
        self.assertEqual(71,waiter.journey.sequence)
        value=waiter.journey.call('observe',dict(afterSequence=71))
        self.assertEqual(72,value['sequence'])
        self.assertEqual((0,2,1),(value['state']['generation'],value['state']['worldAttempts'],value['state']['staleAttempts']))
        self.assertEqual(126,len(self.source.world.state['frames']))
        shells=[item for item in self.sdk.trace if type(item) is tuple and item[0]=='shell']
        self.assertEqual(2,len(shells));self.assertFalse(value['resources'])

    def test_same_normal_sixteen_actions_original_restart_handoff_and_first_fresh_sequence72(self):self.run_seven(actions=16)

    def test_lost_actual_stop_reply_retains_intent_and_never_resends(self):self.process_fault='lost-stop';self.run_seven(actions=16)
    def test_lost_actual_launch_reply_retains_intent_and_never_resends(self):self.process_fault='lost-launch';self.run_seven(actions=16)
    def test_phase_changes_after_original_stop_intent_cas_prevents_sdk(self):self.process_fault='phase-stop';self.run_seven(actions=16)
    def test_phase_changes_after_original_launch_intent_cas_prevents_sdk(self):self.process_fault='phase-launch';self.run_seven(actions=16)
    def test_actual_outer_exit_foreign_process_memo_cannot_return_cleanup_ack(self):self.process_fault='memo';self.run_seven(actions=16)
    def test_actual_outer_exit_native_jump_with_frozen_host_cannot_return_cleanup_ack(self):self.process_fault='clock';self.run_seven(actions=16)
    def test_actual_outer_exit_same_bytes_replaced_operations_root_cannot_return_cleanup_ack(self):self.process_fault='outer-exit';self.run_seven(actions=16)


if __name__=='__main__':unittest.main()
