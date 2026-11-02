"""Actual production main/factory/loop in a distinct owned model worker.

SDK, Native producers, replica, renderer, provider and time are explicit models;
file/OFD/program/nonce/child-exit ownership is real. No build/device/service.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import select
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid

sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
import test_create_peer_source as source_tests
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnReceiver,state as physical_state
from adapters.pico4.create_peer_parent import admit_return
from adapters.pico4.create_peer_source import FAMILY
from adapters.pico4.feature_observer import configuration
from adapters.pico4.create_peer_actor import READY
from fixture.chat_observer_process import LinuxChatObserverProcess
from adapters.script_journey.lock import ScriptSourceLock


class CreatePeerCliTests(unittest.TestCase):
    def setUp(self):
        self.base=source_tests.CreatePeerSourceTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.primary,self.directory,self.scope=self.base.primary,self.base.directory,self.base.scope
        self.worker=None;self.owner=None;self.addCleanup(self.finish)
        self.entry=Path(__file__).with_name('create_peer_cli_host.py')
        owner=self.primary.root.source_store('peer');_value,raw,physical=physical_state(owner)
        self.config=PrivateFeatureState(self.directory/'cli-config.json')
        self.value=dict(picoFeatureObserverVersion=5,area='create',target='synthetic-second-pico',candidateArguments=['--apk','owned.apk'],
            fixtureUrl=self.scope['fixtureUrl'].split('/runs/')[0],actorToken='explicit-model-actor-'+'b'*32,durationSeconds=30,
            artifactRoot=str(self.directory),peerOwner=str(owner.path),peerOwnerSha256=hashlib.sha256(raw).hexdigest(),peerOwnerStamp=physical,
            runId=self.scope['runId'],originalRequestId=self.scope['requestId'],
            workerExecutableSha256=hashlib.sha256(Path('/proc/self/exe').read_bytes()).hexdigest(),
            workerEntrySha256=hashlib.sha256(self.entry.read_bytes()).hexdigest())
        self.config.write(self.value,None)

    def wait_for(self,read,condition):
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            value=read()
            if condition(value):return value
            event=os.waitid(os.P_PID,self.worker.pid,os.WEXITED|os.WNOWAIT|os.WNOHANG)
            if event is not None:
                self.worker.wait(timeout=5);self.fail('Original model worker exited: '+self.worker.stderr.read().decode())
            time.sleep(.01)
        self.fail('Original model worker observation timed out')

    def start(self):
        self.assertEqual(self.value,configuration(self.config.path));self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OVT_CREATE_PEER_CLI_TEST_OWNER=self.token))
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        def owned(pid):
            root=Path('/proc')/str(pid)
            try:
                with (root/'environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and root.stat().st_uid==os.geteuid() and raw.split(b'\0').count(('OVT_CREATE_PEER_CLI_TEST_OWNER='+self.token).encode())==1
            except FileNotFoundError:return False
        self.owner=LinuxChatObserverProcess(identity,self.entry,self.config.path,self.value['workerExecutableSha256'],self.value['workerEntrySha256'],owned)
        self.process=identity

    def original(self):
        with ScriptSourceLock(self.directory/'script-sources.lock').held():
            return PrivateFeatureState(self.directory/'create-peer-originals.json').read()
    def terminal(self):return PrivateFeatureState(self.directory/'create-peer-worker.json').read()
    def observed(self):
        return self.wait_for(self.original,lambda value:value is not None and bool(value['records']) and value['records'][-1]['facts']['present'])

    def return_ready(self):
        with self.primary.root.peer_input_boundary(self.config.path,self.owner):self.base.begin_cleanup()
        store=PrivateFeatureState(self.directory/'return.json')
        self.ready_notification();self.assertEqual('ready',store.read()['phase'])
        expected=dict(runId=self.scope['runId'],family=FAMILY,producerHostProcessIdentity=self.process,originalRequestId=self.scope['requestId'])
        return ObserverReturnReceiver(self.owner,store,PrivateFeatureState(self.directory/'consumption.json'),expected,
            admit=lambda raw,physical:admit_return(raw,physical,self.scope))

    def ready_notification(self):
        self.assertTrue(select.select([self.worker.stdout],[],[],25)[0],'Original publication notification missing')
        line=self.worker.stdout.readline()
        if not line:
            self.worker.wait(timeout=5);self.fail('Original producer refused before publication: '+self.worker.stderr.read().decode())
        self.assertEqual((READY+'\n').encode(),line)

    def exited_without_reap(self):
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            event=os.waitid(os.P_PID,self.worker.pid,os.WEXITED|os.WNOWAIT|os.WNOHANG)
            if event is not None:return event
            time.sleep(.01)
        self.fail('Original owned model worker did not exit')

    def finish(self):
        if self.worker is not None:
            # Tests arrange an actual normal exit or a refused producer. Never
            # start repair/input or claim a returned event from fixture teardown.
            self.worker.wait(timeout=35)
            for stream in (self.worker.stdout,self.worker.stderr):
                if stream is not None and not stream.closed:stream.close()
        if self.owner is not None:self.assertTrue(self.owner.close())

    def test_actual_cli_main_factory_native_sources_nonce_kernel_exit_and_original_parent_cleanup(self):
        self.start();self.observed();inputs=len(self.primary.b.inputs)
        receiver=self.return_ready();receiver.acknowledge();event=self.exited_without_reap();self.assertEqual(0,event.si_status)
        receipt=self.primary.root.accept_peer_return(receiver);self.owner=None
        self.assertEqual(FAMILY,receipt['family']);self.assertEqual(2,self.primary.root.peer_state()['createPeerParentVersion'])
        self.primary.make();self.primary.root.invoke('cleanup');self.assertIsNone(self.primary.root.store.read())
        self.assertGreater(len(self.primary.b.inputs),inputs)
        calls=PrivateFeatureState(self.directory/'factory-calls.json').read()['calls']
        self.assertEqual(['candidate-describe-only','runtime-read','native-reader','entity-reader','resource-reader'],calls)
        self.assertEqual('closed',self.terminal()['phase']);self.assertEqual(2,json.loads(receiver.raw)['createPeerReturnVersion'])

    def test_after_original_echo_failure_keeps_issued_parent_and_failed_worker(self):
        self.base.update(afterEchoFailure=True);self.start();self.observed();receiver=self.return_ready();receiver.acknowledge()
        self.assertEqual(2,self.exited_without_reap().si_status)
        self.assertEqual('consumed',receiver.store.read()['phase']);self.assertEqual('failed',self.terminal()['phase'])
        inputs=len(self.primary.b.inputs)
        with self.assertRaises(NativeUIError):self.primary.root.accept_peer_return(receiver)
        self.assertEqual('issued',self.primary.root.peer_state()['phase']);self.assertEqual(inputs,len(self.primary.b.inputs))

    def test_after_original_echo_expiry_never_renews_original_deadline(self):
        self.base.update(afterEchoExpired=True);self.start();self.observed();receiver=self.return_ready();before=self.terminal()
        receiver.acknowledge();self.assertEqual(2,self.exited_without_reap().si_status)
        after=self.terminal();self.assertEqual('consumed',receiver.store.read()['phase']);self.assertEqual('failed',after['phase'])
        self.assertEqual(before['startedMonotonic'],after['startedMonotonic']);self.assertEqual(before['deadlineMonotonic'],after['deadlineMonotonic'])
        with self.assertRaises(NativeUIError):self.primary.root.accept_peer_return(receiver)
        self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_consumed_echo_closed_looking_marker_and_pid_absence_do_not_replace_kernel_zero_exit(self):
        self.base.update(afterEchoFailure=True,closedLookingFailure=True);self.start();self.observed();receiver=self.return_ready();receiver.acknowledge()
        self.assertEqual(2,self.exited_without_reap().si_status);self.assertEqual('closed',self.terminal()['phase'])
        with self.assertRaises(NativeUIError):self.primary.root.accept_peer_return(receiver)
        self.assertEqual(512,self.primary.root._peer_worker_wait[1][1]);self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_strict_cli5_configuration_refuses_foreign_scope_alias_and_old_version(self):
        self.assertEqual(self.value,configuration(self.config.path))
        for changes in (dict(picoFeatureObserverVersion=4),dict(originalRequestId='f'*32),dict(peerOwnerSha256='f'*64),dict(readerToken='x'*64)):
            before=self.config.read();self.config.write(self.value|changes,before)
            with self.assertRaises((NativeUIError,ValueError)):configuration(self.config.path)
        before=self.config.read();alias=self.directory/'alias.json';alias.symlink_to(Path(self.value['peerOwner']))
        self.config.write(self.value|dict(peerOwner=str(alias)),before)
        with self.assertRaises(NativeUIError):configuration(self.config.path)

    def test_replaced_original_config_fails_and_new_process_cannot_adopt_issued_claim(self):
        self.start();self.observed();self.config.write(self.value,self.config.read())
        self.assertEqual(2,self.exited_without_reap().si_status);self.worker.wait(timeout=5)
        self.assertEqual('failed',self.terminal()['phase']);self.assertEqual('issued',self.primary.root.peer_state()['phase'])
        before=(self.directory/'create-peer-originals.json').read_bytes();calls=PrivateFeatureState(self.directory/'factory-calls.json').read()
        result=subprocess.run([sys.executable,str(self.entry),'--config',str(self.config.path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=10)
        self.assertEqual(2,result.returncode);self.assertEqual(before,(self.directory/'create-peer-originals.json').read_bytes())
        self.assertEqual(calls,PrivateFeatureState(self.directory/'factory-calls.json').read());self.assertFalse((self.directory/'return.json').exists())

    def test_external_sibling_launch_cannot_claim_original_persistent_parent_authority(self):
        command=[sys.executable,'-c','import subprocess,sys;sys.exit(subprocess.run(sys.argv[1:]).returncode)',
            sys.executable,str(self.entry),'--config',str(self.config.path)]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=10)
        self.assertEqual(2,result.returncode);self.assertFalse((self.directory/'factory-calls.json').exists())
        self.assertFalse((self.directory/'create-peer-originals.json').exists());self.assertEqual('issued',self.primary.root.peer_state()['phase'])

    def test_original_input_boundary_waits_without_query_or_deadline_renewal(self):
        self.start();self.observed();worker=self.terminal()
        with self.primary.root.peer_input_boundary(self.config.path,self.owner):
            store=PrivateFeatureState(self.directory/'create-peer-originals.json');before=store.read()
            # Exercise the real five-second source-lock contention path before
            # any new query. This does not shorten/replace a quiet window.
            time.sleep(5.3);self.assertEqual(before,store.read())
            self.base.begin_cleanup()
        returned=PrivateFeatureState(self.directory/'return.json')
        self.ready_notification();self.assertEqual('ready',returned.read()['phase'])
        expected=dict(runId=self.scope['runId'],family=FAMILY,producerHostProcessIdentity=self.process,originalRequestId=self.scope['requestId'])
        receiver=ObserverReturnReceiver(self.owner,returned,PrivateFeatureState(self.directory/'consumption.json'),expected,
            admit=lambda raw,physical:admit_return(raw,physical,self.scope))
        receiver.acknowledge();self.assertEqual(0,self.exited_without_reap().si_status)
        self.primary.root.accept_peer_return(receiver);self.owner=None
        self.assertEqual(worker['startedMonotonic'],self.terminal()['startedMonotonic'])
        self.assertEqual(worker['deadlineMonotonic'],self.terminal()['deadlineMonotonic'])


if __name__=='__main__':unittest.main()
