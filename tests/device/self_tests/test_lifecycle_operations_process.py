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
            self.g1_pending_boundary=boundary
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
        cleanup_barrier=self.sdk.epoch
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
        if getattr(self,'cleanup_quiet',False):
            from adapters.normal_feature_state import PrivateFeatureState
            current=self.operations.cleanup_source
            original_process=deepcopy(process.state);original_cursor=self.source.world.session.state_path.read_bytes()
            waiter.journey.call('cleanup',{})
            self.assertEqual(original_process,process.state)
            self.assertEqual(original_cursor,self.source.world.session.state_path.read_bytes())
            self.assertEqual(2,len([item for item in self.sdk.trace if type(item) is tuple and item[0]=='shell']))
            first=len(current.disk['records']);self.assertEqual(0,first)
            def continuity(*_args):
                actual=self.sdk.require_controlled_debug_identity(self.sdk.target)
                self.assertEqual(current.binding['processIdentity'],actual)
            waiter.journey.continuity=continuity
            waiter.journey.sleep=self.sdk.helper.sleep
            waiter.journey.epoch_ms=lambda:self.sdk.epoch
            expected=expand(SCENARIOS['lifecycle-input']['baseline'],context(self.source.run))
            for key in ('worldAttempts','staleAttempts'):expected[key]=current.boundary['state'][key]
            activation=self.journal.runs[self.source.run]['phaseActivations'][-1]
            span=getattr(self,'cleanup_span',None)
            if span:
                # Actual producer latency only: never rewrite accepted packet
                # capture times. The .2499s schedule belongs solely to this
                # counter, not the unchanged normal .25s Common wait.
                sleep=self.sdk.helper.sleep;ui_calls=[];drive_calls=[]
                if span=='ui':
                    capture=current.acquisition.avatar.capture
                    def slower_first_drive(*args,**kwargs):
                        value=capture(*args,**kwargs);drive_calls.append(True)
                        if len(drive_calls)==1:sleep(.0012)
                        return value
                    current.acquisition.avatar.capture=slower_first_drive
                    capture_ui=current.acquisition.source.capture
                    def slower_last_ui(*args,**kwargs):
                        value=capture_ui(*args,**kwargs);ui_calls.append(True)
                        if len(ui_calls)==13:sleep(.0014)
                        return value
                    current.acquisition.source.capture=slower_last_ui
                else:
                    send=self.g1_pending_boundary.send
                    def slower_first_pending(request):
                        if not self.g1_pending_boundary.commands:sleep(.0013)
                        return send(request)
                    current.pending.send=slower_first_pending
                for index in range(13):
                    waiter.journey.observe(activation['ticket'],cleanup_barrier)
                    if index<12:sleep(.2499)
                from adapters.chat_journey import source_bundles
                import json
                axes={key:[] for key in ('ui','gesture','drive','pending','native','presence','domain','host')}
                for row in current.disk['records']:
                    original,_=source_bundles.original(current.history,current.disk['chunks'],current.disk['bundles'],row['originals']['world'])
                    for key in ('ui','gesture','drive'):axes[key].append(json.loads(original['world'][key]['raw'])['capturedEpochMs'])
                    axes['host'].append(original['world']['hostMonotonic'])
                    for key in ('pending','native','presence','domain'):
                        original,_=source_bundles.original(current.history,current.disk['chunks'],current.disk['bundles'],row['originals'][key])
                        axes[key].append(json.loads(original[key]['raw'])['capturedEpochMs'])
                spans={key:values[-1]-values[0] for key,values in axes.items()}
                PrivateFeatureState(current.store.path.with_name('lifecycle-quiet-capture-spans.json')).write(dict(
                    kind='actual-source-counter',axes=axes,spans=spans,scheduledNativeQueries=13),None)
                print('Actual fresh original source spans: '+str(spans),flush=True)
                self.assertGreaterEqual(spans['drive'],3000);self.assertGreaterEqual(spans['host'],3)
                self.assertLess(spans[span if span=='ui' else 'pending'],3000)
                with self.assertRaises(NativeUIError):current.quiet_originals(first)
                self.assertTrue(current.failed);self.assertEqual(original_process,process.state)
                self.assertEqual(126,len(self.source.world.state['frames']));self.assertEqual(71,len(self.source.disk['records']))
                return
            fault=getattr(self,'cleanup_quiet_fault',None)
            if fault=='pending':
                born=self.sdk.helper.new_native.clock
                def late_callback(value):
                    if self.sdk.helper.new_native.clock-born>=2.75:value['resources']['archivedEvents']=1
                self.g1_pending_boundary.edit=late_callback
            elif fault=='presence':self.sdk.helper.presence_boundary.presence='present'
            # The standard wait executes unchanged, without peer/artifact
            # authority. Its real returned results advance the real cursor.
            if fault in ('pending','presence'):
                with self.assertRaises(NativeUIError):
                    waiter.journey.wait('cleanup-restored-baseline',activation['ticket'],cleanup_barrier,expected,[],duration=3.)
                from adapters.chat_journey import source_bundles
                import json
                slot='pending' if fault=='pending' else 'presence'
                packet,_=source_bundles.original(current.history,current.disk['chunks'],current.disk['bundles'],current.disk['pending'][slot])
                self.assertIsNotNone(current.disk['pending'][slot]);self.assertTrue(current.failed)
                if fault=='pending':
                    self.assertEqual(1,json.loads(packet['pending']['raw'])['resources']['archivedEvents'])
                    self.assertIsNone(current.disk['pending']['native']);self.assertGreater(len(current.disk['records']),3)
                else:
                    self.assertEqual('present',json.loads(packet['presence']['raw'])['presence'])
                    self.assertIsNone(current.disk['pending']['domain']);self.assertEqual([],current.disk['records'])
                before=(len(self.sdk.helper.new_native.ui.commands),len(self.g1_pending_boundary.commands),len(self.sdk.helper.new_feature.commands))
                with self.assertRaises(NativeUIError):waiter.journey.call('observe',dict(afterSequence=71+len(current.disk['records'])))
                self.assertEqual(before,(len(self.sdk.helper.new_native.ui.commands),len(self.g1_pending_boundary.commands),len(self.sdk.helper.new_feature.commands)))
                self.assertEqual(original_process,process.state);self.assertEqual(126,len(self.source.world.state['frames']))
                self.assertEqual(2,len([item for item in self.sdk.trace if type(item) is tuple and item[0]=='shell']))
                return
            actual=waiter.journey.wait('cleanup-restored-baseline',activation['ticket'],cleanup_barrier,expected,[],duration=3.)
            if fault=='outer-exit':
                held=current.lock.held;depth=[0];triggered=[];clock=current.readers[0].clock_ms
                @contextmanager
                def native_jump_after_exit():
                    with held():
                        depth[0]+=1
                        try:yield
                        finally:depth[0]-=1
                    if depth[0]==0 and not triggered:
                        triggered.append(True);current.readers[0].clock_ms=lambda:clock()+2000
                with patch.object(current.lock,'held',native_jump_after_exit):
                    with self.assertRaises(NativeUIError):current.quiet_originals(first)
                self.assertEqual([True],triggered);self.assertTrue(current.failed)
                self.assertEqual(original_process,process.state);self.assertEqual(126,len(self.source.world.state['frames']))
                self.assertEqual(2,len([item for item in self.sdk.trace if type(item) is tuple and item[0]=='shell']))
                return
            proof=current.quiet_originals(first)
            self.assertEqual(71+proof['advancingSamples'],waiter.journey.sequence)
            self.assertEqual(waiter.journey.sequence,actual['sequence'])
            self.assertEqual(proof['advancingSamples'],len(current.disk['records']))
            self.assertGreaterEqual(proof['nativeMilliseconds'],3000);self.assertGreaterEqual(proof['hostSeconds'],3)
            self.assertEqual(original_process,process.state);self.assertEqual(126,len(self.source.world.state['frames']))
            self.assertEqual(71,len(self.source.disk['records']))
            files=[current.store.path,*sorted(current.store.path.parent.glob(current.store.path.name+'.frame-*.json'))]
            diagnostic=dict(scope='private-primary-only-new-process-quiet',proof=proof,processRows=len(process.state['next']['frames']),
                oldWorldRows=126,oldReadonlyRows=71,newReadonlyRows=len(current.disk['records']),
                childParts=len(current.history.identities),containerRawBytes=current.history.raw_bytes,
                logicalOriginalBytes=sum(row['bytes'] for row in current.disk['bundles']),
                actualStoredFileBytes=sum(path.stat().st_size for path in files),fileCount=len(files),
                samples=deepcopy(waiter.journey.samples[-proof['advancingSamples']:]),phase=deepcopy(waiter.journey.phases[-1]))
            PrivateFeatureState(current.store.path.with_name('lifecycle-primary-process-quiet-diagnostics.json')).write(diagnostic,None)
            print('Actual same-graph new-process quiet bill: '+str({key:value for key,value in diagnostic.items() if key not in ('samples','phase')}),flush=True)
            return
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
    def test_same_normal_graph_twice_cleanup_and_fresh_g1_primary_quiet_window(self):self.cleanup_quiet=True;self.run_seven(actions=16)
    def test_late_actual_pending_archive_prevents_g1_three_second_quiet(self):self.cleanup_quiet=True;self.cleanup_quiet_fault='pending';self.run_seven(actions=16)
    def test_present_original_pid_reply_is_retained_before_domain_query_or_quiet(self):self.cleanup_quiet=True;self.cleanup_quiet_fault='presence';self.run_seven(actions=16)
    def test_real_quiet_outer_exit_native_jump_cannot_return_window_proof(self):self.cleanup_quiet=True;self.cleanup_quiet_fault='outer-exit';self.run_seven(actions=16)
    def test_ui_capture_span_below_three_seconds_cannot_use_drive_and_host_span(self):self.cleanup_quiet=True;self.cleanup_span='ui';self.run_seven(actions=16)
    def test_pending_capture_span_below_three_seconds_cannot_use_drive_and_host_span(self):self.cleanup_quiet=True;self.cleanup_span='pending';self.run_seven(actions=16)


if __name__=='__main__':unittest.main()
