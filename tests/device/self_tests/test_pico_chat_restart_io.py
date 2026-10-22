"""Original host cursor/readers/SDK route; device/kernel producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openxr_input.adapter_session import PicoOpenXrAdapterSession
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_chat_profile_current import CurrentBoundary


class RestartBoundary:
    def __init__(self,root):
        self.pico_configuration=('explicit-layer',root);self.profile=dict(package='org.overte.pico',e2e_activity='org.overte.pico/.E2eLauncherActivity')
        self.adb=self;self.target='synthetic-target';self.command=['never-execute-synthetic-adb'];self.identity='123:456';self.running=True
        self.trace=[];self.lost=None;self.effect=True;self.digest='2'*64;self.clock=0.;self.epoch=20000
        self.session=PicoOpenXrAdapterSession(object(),self.target,root);self.session.begin(self.identity)
        self.native=NativeBoundary();self.presence=PresenceBoundary(pid=789,epoch_ms=lambda:self.epoch);self.presence.presence='absent'
        self.current=CurrentBoundary()
        def native(value):
            value.update(processId=789,capturedEpochMs=self.epoch,requestedEpochMs=self.epoch)
            value['animationFence']['requestedEpochMs']=self.epoch;value['animation']['capturedEpochMs']=self.epoch
            value['animation']['clip']['evaluatedEpochMs']=self.epoch
            value['lifecycle'].update(launches=2,activations=2)
        self.native.mutate=native
        self.current.edit=lambda value:value.update(processId=789)
    def binding(self):return dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='123:456',sessionId='old-bridge',generation=0,
        targetFingerprint=hashlib.sha256((self.target+'\0'+str(self.pico_configuration)).encode()).hexdigest())
    def require(self,target):assert target==self.target;self.trace.append('require')
    def _installation(self,target):self.require(target);return dict(sourceRevision='1'*40,artifactSha256=self.digest,schemaVersion=1,installedCandidateVerified=True)
    def pico_input_session(self,target):assert target==self.target;return self.session
    def debug_launcher_arguments(self,target):assert target==self.target;return ()
    def controlled_debug_identity(self,target):self.require(target);return self.identity if self.running else None
    def require_controlled_debug_identity(self,target):
        value=self.controlled_debug_identity(target);assert value is not None;self.session.require_process_identity(value);return value
    def require_pico_session_identity(self,target):
        value=self.controlled_debug_identity(target);self.session.require_process_identity(value);return value
    def require_same_process(self,target,identity,operation):assert self.controlled_debug_identity(target)==identity
    def process_state(self,target,package):assert package=='org.overte.pico';return dict(running=self.running,identity=self.identity if self.running else None)
    def foreground_package(self,target):return 'org.overte.pico'
    def epoch_milliseconds(self,target):return self.epoch
    def shell(self,target,*arguments):
        self.require(target);self.trace.append(('shell',arguments))
        if arguments==('am','force-stop','org.overte.pico'):
            if self.effect:self.running=False
            operation='stop'
        else:
            assert arguments==('am','start','-W','-n',self.profile['e2e_activity'])
            if self.effect:self.running=True;self.identity='789:999'
            operation='launch'
        if operation==self.lost:raise OSError('Original SDK reply lost')
        return ''
    def invoke(self,*_args):raise AssertionError('No facade/bootstrap/repair input')
    def write_control_command(self,target,identity,operation,request):
        assert identity==self.identity and self.running
        if request['action']=='feature-native-observe':self.native.send(request)
        elif request['action']=='feature-process-presence':self.presence.send(request)
        elif request['action']=='feature-chat-profile-current':self.current.epoch=self.epoch;self.current.send(request)
        else:raise AssertionError('Read-only new-process source only')
    def read_debug_app_file(self,target,package,path,attempts):
        if path.endswith('/feature-native-observation.json'):return self.native.original()
        if path.endswith('/feature-process-presence.json'):return self.presence.original()
        if path.endswith('/feature-chat-profile-current.json'):return self.current.original()
        raise AssertionError('Fixed original result filenames only')
    def ps(self,arguments,**kwargs):
        assert arguments==[self.command[0],'-s',self.target,'exec-out','run-as','org.overte.pico','/system/bin/ps','-p','123','-o','PID']
        present=self.running and self.identity.startswith('123:')
        return SimpleNamespace(returncode=0 if present else 1,stdout=b'PID\n123\n' if present else b'PID\n',stderr=b'')


class ChatRestartIOTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pico-chat-restart-io-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.boundary=RestartBoundary(self.root)
        self.io=PicoChatRestartIO(self.boundary,self.boundary.target,self.boundary.binding(),
            monotonic=lambda:self.boundary.clock,sleep=lambda delay:setattr(self.boundary,'clock',self.boundary.clock+delay))
        self.addCleanup(self.io.close_host)
        patcher=patch('adapters.android_process_query.subprocess.run',side_effect=self.boundary.ps);patcher.start();self.addCleanup(patcher.stop)
    def shells(self):return [row for row in self.boundary.trace if type(row) is tuple and row[0]=='shell']
    def stop_and_launch(self):self.io.stop(lambda:None);self.io.launch(lambda:None)

    def test_original_stop_launch_once_leave_cursor_and_observe_new_native_esrch_and_profile_without_binding(self):
        original=self.boundary.session.state_path.read_bytes()
        self.io.stop(lambda:self.boundary.trace.append('stop-admitted'))
        self.assertFalse(self.boundary.running);self.assertEqual(original,self.boundary.session.state_path.read_bytes())
        self.assertEqual(dict(running=False,identity=None),self.io.stopped());self.assertEqual([],self.io.last_process_query['processIds'])
        self.io.launch(lambda:self.boundary.trace.append('launch-admitted'))
        self.assertEqual(original,self.boundary.session.state_path.read_bytes());self.assertEqual(2,len(self.shells()))
        identity,native,presence,current=self.io.unbound_sources();self.assertEqual('789:999',identity)
        self.assertEqual(789,native.read(0)['processId']);self.assertEqual('ESRCH',presence.require_absent(123)['errorSymbol'])
        self.assertEqual(789,current.read('a'*32)['processId']);self.assertEqual(original,self.boundary.session.state_path.read_bytes())
        for callback in (lambda:self.io.stop(lambda:None),lambda:self.io.launch(lambda:None)):
            with self.assertRaises(NativeUIError):callback()
        self.assertEqual(2,len(self.shells()))

    def test_lost_stop_or_launch_reply_never_repeats_and_original_cursor_is_retained(self):
        for operation in ('stop','launch'):
            if operation!='stop':self.setUp()
            original=self.boundary.session.state_path.read_bytes();self.boundary.lost=operation
            if operation=='launch':self.io.stop(lambda:None)
            action=getattr(self.io,operation)
            with self.subTest(operation=operation),self.assertRaises(OSError):action(lambda:None)
            before=len(self.shells())
            with self.assertRaises(NativeUIError):action(lambda:None)
            self.assertEqual(before,len(self.shells()));self.assertEqual(original,self.boundary.session.state_path.read_bytes())
            if operation=='launch':self.assertEqual('789:999',self.io.unbound_sources()[0])

    def test_launch_refuses_live_original_or_uninvited_new_process_without_repair_stop(self):
        for identity in ('123:456','789:999'):
            if identity!='123:456':self.setUp()
            self.boundary.identity=identity;self.boundary.running=True
            with self.subTest(identity=identity),self.assertRaises(NativeUIError):self.io.launch(lambda:None)
            self.assertEqual([],self.shells())

    def test_changed_candidate_or_expired_final_admission_prevents_actual_sdk_stop(self):
        original=self.boundary.session.state_path.read_bytes();self.boundary.digest='f'*64
        with self.assertRaises(NativeUIError):self.io.stop(lambda:None)
        self.assertEqual([],self.shells());self.assertEqual(original,self.boundary.session.state_path.read_bytes())
        self.setUp()
        def expired():raise ValueError('Original parent phase/age expired after CAS')
        with self.assertRaises(ValueError):self.io.stop(expired)
        self.assertEqual([],self.shells());self.assertTrue(self.boundary.running)

    def test_unbound_sources_reject_same_pid_start_and_mutating_commands_without_dispatch(self):
        with self.assertRaises(NativeUIError):self.io.unbound_sources()
        self.stop_and_launch();_identity,native,_presence,_profile=self.io.unbound_sources()
        before=len(self.boundary.native.commands)
        with self.assertRaises(NativeUIError):native.send(dict(schemaVersion=1,commandId='a'*32,action='feature-chat-observe',runId='b'*32,operation='observe'))
        self.assertEqual(before,len(self.boundary.native.commands));self.boundary.digest='f'*64
        with self.assertRaises(NativeUIError):native.read(0)
        self.assertEqual(before,len(self.boundary.native.commands));self.assertEqual(2,len(self.shells()))


if __name__=='__main__':unittest.main()
