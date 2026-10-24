"""Original readonly Actor process before and after one normal Create input.

Real process/HTTP/stream/source/file ownership. Native/Qt/SDK/physics remain the
same original editor fixture's declared model producers, not an Actor simulator.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets
import select
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from adapters.host_process_identity import host_identity
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.server import make_server
from feature_journeys.witness import Client,Journal
from fixture.chat_observer_process import LinuxChatObserverProcess
from self_tests import test_pico_lifecycle_editor as editor_fixture
from self_tests.test_pending_commit_owner import Boundary as PendingBoundary
from self_tests import test_pico_lifecycle_process as process_fixture
from self_tests.pico_lifecycle_actor_fixture import LifecycleProducts,WORKER
from self_tests.pico_lifecycle_actor_fixture import IndependentLifecycleSources


class LifecycleIndependentActorTests(unittest.TestCase):
    def setUp(self):
        original=editor_fixture.tempfile.TemporaryDirectory
        def retained(*args,**kwargs):
            temporary=original(*args,**kwargs)
            if kwargs.get('prefix')=='lifecycle-editor-':
                temporary._finalizer.detach();temporary.cleanup=lambda:None
                print('Independent Actor originals retained at construction: '+temporary.name,flush=True)
            return temporary
        self.editor=editor_fixture.LifecycleEditorTests()
        with patch.object(editor_fixture.tempfile,'TemporaryDirectory',retained):self.editor.setUp()
        self.addCleanup(self.editor.doCleanups)
        self.root=self.editor.root;self.native=self.editor.native;self.run=self.editor.owner.run
        holder=SimpleNamespace(native=self.native,sleep=self.native.sleep)
        feature,_reader=process_fixture.LifecycleProcessTests.features(holder,self.native,123,'a'*32,1)
        pending=PendingBoundary();pending.epoch=self.native.epoch
        def raw():
            value=json.loads(pending.original())
            if not any(row['kind']=='scripts' and row['current'] for row in self.native.ui.rows):value['current']=dict(status='none')
            return json.dumps(value)
        case=SimpleNamespace(editor=self.editor,observer=SimpleNamespace(run=self.run),native_producer=feature,
            boundary=pending,reader=SimpleNamespace(original=raw))
        self.products=LifecycleProducts(case);self.addCleanup(self.products.close)
        reader_token,actor_token=secrets.token_hex(32),secrets.token_hex(32)
        self.actor_token=actor_token
        self.server=make_server(reader_token,actor_token);self.server.journal=Journal(self.native.epoch)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.close_server)
        self.client=Client('http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1',reader_token)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=self.run):self.assertEqual(self.run,self.client.register('lifecycle-input')[0])
        self.client.activate(uuid.uuid4().hex)
        self.entry=self.root/'lifecycle-original-source-worker.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        self.configuration=PrivateFeatureState(self.root/'lifecycle-original-source-worker-config.json')
        self.configuration.write(dict(self.products.configuration(),fixture=self.client.url,actorToken=actor_token),None)
        self.worker=None;self.process=None

    def close_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())

    def receive(self,event):
        self.assertTrue(select.select([self.worker.stdout],[],[],10)[0],event+' not received')
        raw=self.worker.stdout.readline();self.assertTrue(raw,'Actor ended before '+event)
        value=json.loads(raw);self.assertEqual(event,value['event']);return value

    def start(self):
        self.marker=secrets.token_hex(32)
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.configuration.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PYTHONDONTWRITEBYTECODE':'1','OVT_LIFECYCLE_SOURCE_OWNER':self.marker})
        self.addCleanup(self.close_worker)
        waiting=self.receive('waiting');self.assertNotEqual(host_identity(),waiting['host'])
        def owned(pid):
            if pid!=self.worker.pid or self.worker.poll() is not None:return False
            return ('OVT_LIFECYCLE_SOURCE_OWNER='+self.marker).encode() in (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0')
        self.process=LinuxChatObserverProcess(waiting['host'],self.entry,self.configuration.path,
            hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),hashlib.sha256(self.entry.read_bytes()).hexdigest(),owned)

    def command(self,operation):
        self.worker.stdin.write(json.dumps(dict(operation=operation)).encode()+b'\n');self.worker.stdin.flush()

    def close_worker(self):
        if self.worker.poll() is None:
            try:self.command('exit');self.worker.wait(timeout=10)
            except Exception:
                self.worker.terminate();self.worker.wait(timeout=5)
        raw=self.worker.stderr.read(65537);self.assertLessEqual(len(raw),65536)
        PrivateFeatureState(self.root/'lifecycle-actor-worker-exit-diagnostics.json').write(
            dict(exitCode=self.worker.returncode,stderr=raw.decode('utf-8')),None)
        for stream in (self.worker.stdin,self.worker.stdout,self.worker.stderr):stream.close()
        if self.process is not None:self.process.close()

    def sample(self):
        self.process.guard();self.command('sample');value=self.receive('published');self.process.guard()
        latest=self.client.observe()['entries'][-1]
        self.assertEqual(value['sequence'],latest['actorSequence']);return latest

    def test_actual_independent_baseline_then_normal_create_publishes_own_originals(self):
        self.start();baseline=self.sample();self.assertEqual('none',baseline['facts']['editor'])
        self.assertEqual(0,baseline['facts']['generation']);self.assertEqual([],self.editor.transport.envelopes)
        for _ in range(2):self.native.sleep(.25);self.sample()
        self.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'))
        self.editor.focused() # Existing original tablet/open/focus owners.
        observed=self.sample();self.assertEqual('create',observed['facts']['editor'])
        self.assertEqual(1,observed['facts']['generation']);self.assertTrue(observed['facts']['focused'])
        self.assertTrue(observed['facts']['keyboard']);self.assertEqual('',observed['facts']['text'])
        self.assertEqual([],observed['facts']['heldInputs']);self.assertEqual(0,observed['facts']['worldAttempts'])
        for _ in range(2):self.native.sleep(.25);self.sample()
        original=PrivateFeatureState(self.root/'lifecycle-actor-originals.json').read()
        self.assertEqual(6,len(original['records']));self.assertEqual('delivered',original['publication']['phase'])
        self.assertEqual(self.process.process_identity,original['producerHostProcessIdentity'])
        self.assertEqual(host_identity(),original['parentHostProcessIdentity'])
        self.assertFalse((self.root/'lifecycle-world-owner.json').exists())
        self.assertEqual(6,self.products.calls.count('subject'));self.assertEqual(6,self.products.calls.count('ui'))
        self.assertEqual(6,self.products.calls.count('feature'));self.assertEqual(6,self.products.calls.count('pending'))
        self.command('exit');self.worker.wait(timeout=10);self.assertEqual(0,self.worker.returncode)
        absent=self.process.require_absent();self.process.final_absence(absent)
        print('Actual independent Actor: six fresh full-source publications; original normal Create; original kernel return',flush=True)

    def native_calls(self):return [name for name in self.products.calls if name in ('ui','gesture','drive','pending','feature','subject')]

    def failed_worker(self,operation='sample'):
        self.command(operation);self.worker.wait(timeout=10);self.assertNotEqual(0,self.worker.returncode)
        return PrivateFeatureState(self.root/'lifecycle-actor-originals.json').read()

    def test_missing_initial_phase_readiness_refuses_before_native_query_or_normal_input(self):
        self.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'))
        self.start();original=self.failed_worker()
        self.assertEqual([],self.native_calls());self.assertEqual([],original['records'])
        self.assertEqual([],self.editor.transport.envelopes);self.assertIsNone(original['pending'])
        self.assertEqual([],self.client.observe()['entries'])

    def test_original_ui_cursor_regression_refuses_before_another_actual_native_query(self):
        self.start();self.sample();before=deepcopy(self.native_calls())
        original=self.failed_worker('sample-regress-ui')
        self.assertEqual(before,self.native_calls());self.assertEqual(1,len(original['records']))
        self.assertIsNone(original['pending']);self.assertEqual(1,len(self.client.observe()['entries']))

    def test_independent_subject_disagrees_with_original_drive_after_actual_target_progress(self):
        self.products.move_before_subject=True;self.start();original=self.failed_worker()
        self.assertEqual(['gesture','drive','ui','pending','feature','subject'],self.native_calls())
        self.assertIsNotNone(original['pending']['subject']);self.assertEqual([],original['records'])
        self.assertEqual([],self.client.observe()['entries']);self.assertEqual([],self.editor.transport.envelopes)

    def test_landed_publication_lost_reply_retains_issued_scope_and_blocks_next_query(self):
        self.start();self.sample();original=self.failed_worker('sample-lost-reply')
        self.assertEqual(12,len(self.native_calls()));self.assertEqual(2,len(original['records']))
        self.assertEqual('issued',original['publication']['phase']);self.assertEqual(2,len(self.client.observe()['entries']))
        self.assertEqual([],self.editor.transport.envelopes)

    def test_same_host_caller_cannot_construct_independent_source_before_native_access(self):
        transport=IndependentLifecycleSources(self.configuration.read());self.addCleanup(transport.close)
        with self.assertRaises(NativeUIError):transport.source(Client(self.client.url,self.actor_token))
        self.assertEqual([],self.native_calls());self.assertFalse((self.root/'lifecycle-actor-originals.json').exists())

    def test_same_bytes_new_root_after_real_outer_exit_cannot_publish_original_record(self):
        self.start();original=self.failed_worker('sample-replace-root-exit')
        self.assertEqual(6,len(self.native_calls()));self.assertEqual(1,len(original['records']))
        self.assertIsNone(original['pending']);self.assertIsNone(original['publication'])
        self.assertEqual([],self.client.observe()['entries']);self.assertEqual([],self.editor.transport.envelopes)

    def test_actual_ui_producer_failure_keeps_complete_prior_gesture_and_drive_originals(self):
        self.products.fail_ui=True;self.start();original=self.failed_worker()
        self.assertEqual(['gesture','drive','ui'],self.native_calls());self.assertEqual([],original['records'])
        self.assertIn('gesture',original['pending']);self.assertIn('drive',original['pending'])
        from adapters.chat_journey import source_bundles
        from adapters.chat_journey.source_chunks import ChatSourceChunks
        keys=('picoLifecycleActorSourceVersion','runId','binding','role','stage','producerHostProcessIdentity',
            'parentHostProcessIdentity','fixtureUrl')
        history=ChatSourceChunks(PrivateFeatureState(self.root/'lifecycle-actor-originals.json'),{key:original[key] for key in keys})
        history.load(original['chunks'])
        for key,raw in (('gesture',self.native.axes.read()),('drive',self.native.drive.read())):
            bundle,_bytes=source_bundles.original(history,original['chunks'],original['bundles'],original['pending'][key])
            self.assertEqual(raw,bundle['original']['raw'])
            self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),bundle['original']['sha256'])
        self.assertEqual([],self.client.observe()['entries']);self.assertEqual([],self.editor.transport.envelopes)

    def test_original_known_gesture_frame_cannot_borrow_new_capture_after_late_publication_cas(self):
        self.native.sleep(.2);self.products.hold_gesture_publication=True
        self.start();original=self.failed_worker('sample-late-publication')
        self.assertEqual(1.4,self.products.publication_host_work)
        self.assertEqual(6,len(self.native_calls()));self.assertEqual(1,len(original['records']))
        self.assertEqual('issued',original['publication']['phase']);self.assertIsNotNone(original['publication']['fixture'])
        self.assertEqual([],self.client.observe()['entries']);self.assertEqual([],self.editor.transport.envelopes)

    def unavailable_original(self,channel,key):
        self.products.unavailable=channel;self.start();original=self.failed_worker()
        ordered=['gesture','drive','ui','pending','feature','subject']
        self.assertEqual(ordered[:ordered.index(channel)+1],self.native_calls())
        self.assertEqual(1,len(self.products.unavailable_producer.commands))
        self.assertEqual([],original['records']);self.assertIsNotNone(original['pending'][key])
        from adapters.chat_journey import source_bundles
        from adapters.chat_journey.source_chunks import ChatSourceChunks
        scope=('picoLifecycleActorSourceVersion','runId','binding','role','stage','producerHostProcessIdentity',
            'parentHostProcessIdentity','fixtureUrl')
        history=ChatSourceChunks(PrivateFeatureState(self.root/'lifecycle-actor-originals.json'),{name:original[name] for name in scope})
        history.load(original['chunks'])
        bundle,_=source_bundles.original(history,original['chunks'],original['bundles'],original['pending'][key])
        self.assertEqual('{}',bundle[key]['raw']);self.assertEqual(hashlib.sha256(b'{}').hexdigest(),bundle[key]['sha256'])
        self.assertEqual(self.products.unavailable_producer.commands[0],bundle['request'])
        self.assertEqual([],self.client.observe()['entries']);self.assertEqual([],self.editor.transport.envelopes)

    def test_actual_unavailable_pending_response_is_retained_before_reader_refusal(self):
        self.unavailable_original('pending','pending')

    def test_actual_unavailable_native_response_is_retained_before_reader_refusal(self):
        self.unavailable_original('feature','native')

    def test_actual_unavailable_subject_response_is_retained_before_reader_refusal(self):
        self.unavailable_original('subject','subject')


if __name__=='__main__':unittest.main()
