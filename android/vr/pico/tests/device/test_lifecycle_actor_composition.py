"""Canonical normal editor and independent Actor over the same original scope."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import select
from pathlib import Path
import secrets
import sys
import threading
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.fixtures import context
from feature_journeys.server import make_server
from feature_journeys.witness import Client,Journal
from self_tests import test_lifecycle_independent_actor as worker_fixture
from self_tests.pico_lifecycle_canonical_actor_fixture import CanonicalLifecycleTarget,WORKER


class LifecycleActorCompositionTests(unittest.TestCase):
    close_server=worker_fixture.LifecycleIndependentActorTests.close_server
    start=worker_fixture.LifecycleIndependentActorTests.start
    command=worker_fixture.LifecycleIndependentActorTests.command
    close_worker=worker_fixture.LifecycleIndependentActorTests.close_worker
    sample=worker_fixture.LifecycleIndependentActorTests.sample
    native_calls=worker_fixture.LifecycleIndependentActorTests.native_calls
    failed_worker=worker_fixture.LifecycleIndependentActorTests.failed_worker

    def receive(self,event):
        value=worker_fixture.LifecycleIndependentActorTests.receive(self,event)
        if event=='published':self.last_worker=value
        return value

    def setUp(self):
        self.editor=CanonicalLifecycleTarget(self);self.root=self.editor.root;self.native=self.editor.native
        self.run=self.editor.run;self.products=self.editor.products
        reader_token,self.actor_token=secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(reader_token,self.actor_token);self.server.journal=Journal(self.native.epoch)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.close_server)
        self.client=Client('http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1',reader_token)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=self.run):self.client.register('lifecycle-input')
        self.client.activate(uuid.uuid4().hex)
        self.entry=self.root/'lifecycle-original-source-worker.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[5]/'tests/device'))));self.entry.chmod(0o600)
        self.configuration=PrivateFeatureState(self.root/'lifecycle-original-source-worker-config.json')
        self.configuration.write(dict(self.products.configuration(),fixture=self.client.url,actorToken=self.actor_token,
            canonicalFactory=True,sharedCandidate=self.editor.shared_candidate()),None)
        self.worker=self.process=None
        print('Shared canonical Lifecycle originals: '+str(self.root),flush=True)

    def test_same_canonical_binding_and_lock_inode_survive_normal_create_and_type(self):
        self.start();self.assertEqual(self.editor.binding,self.waiting['binding'])
        self.assertEqual(str(self.root),self.waiting['root']);self.assertEqual('none',self.sample()['facts']['editor'])
        self.assertEqual([],self.editor.os.inputs);self.assertEqual([],self.editor.transport.envelopes)
        self.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'))
        self.editor.owner.tablet()
        previous=sys.gettrace();recorded=[]
        def trace(frame,event,error):
            if event=='exception' and frame.f_code.co_filename.endswith('/pico4/navigation.py') and frame.f_code.co_name in ('snapshot','input') and not recorded:
                import traceback
                recorded.append(True);traceback.print_exception(*error,file=sys.stderr)
            return trace
        try:
            sys.settrace(trace);self.editor.owner.open_create()
        finally:sys.settrace(previous)
        self.editor.owner.focus_create()
        opened=self.sample()['facts'];self.assertEqual(('create','',1),tuple(opened[k] for k in ('editor','text','generation')))
        self.client.activate(uuid.uuid4().hex,'type',dict(text=context(self.run)['unicode']))
        self.editor.owner.type_create();typed=self.sample()['facts'];self.assertEqual(context(self.run)['unicode'],typed['text'])
        original=PrivateFeatureState(self.root/'lifecycle-actor-originals.json').read()
        self.assertEqual(self.editor.owner.binding,original['binding']);self.assertEqual(3,len(original['records']))
        self.assertEqual(self.editor.owner.lock.path,self.root/'script-sources.lock')
        with self.editor.lock.held():
            own=os.fstat(self.editor.lock._owner[1]);observed=self.last_worker['sourceLock']
            self.assertEqual((own.st_dev,own.st_ino),(observed['device'],observed['inode']))
            self.assertEqual(str(self.editor.lock.path),observed['path']);self.assertEqual(self.worker.pid,observed['ownerPid'])
            self.assertNotEqual(os.getpid(),observed['ownerPid'])
        self.assertEqual('typed',self.editor.owner.state['phase']);self.assertEqual(1,len(self.editor.transport.envelopes))
        self.assertTrue(all(row['consumed'] is not None for row in self.editor.owner.state['inputs']))
        script_state,_=self.editor.adapter._script_paths(self.editor.target)
        self.assertIsNone(PrivateFeatureState(script_state).read())
        self.command('exit');self.worker.wait(timeout=10);self.assertEqual(0,self.worker.returncode)
        absent=self.process.require_absent();self.process.final_absence(absent)

    def test_actual_parent_lock_blocks_actor_before_source_intent_then_same_inode_continues(self):
        config=self.configuration.read();self.configuration.write(dict(config,traceInitialLock=True),config)
        self.start();before=deepcopy(self.native_calls())
        with self.editor.lock.held():
            self.command('sample');self.receive('lock-attempt')
            self.assertFalse(select.select([self.worker.stdout],[],[],.2)[0])
            self.assertEqual(before,self.native_calls());self.assertIsNone(PrivateFeatureState(self.root/'lifecycle-actor-originals.json').read())
        self.receive('lock-acquired');self.receive('published');self.process.guard()
        self.assertEqual(['gesture','drive','ui','pending','feature','subject'],self.native_calls()[len(before):])
        self.assertEqual([],self.editor.os.inputs);self.assertEqual([],self.editor.transport.envelopes)

    def test_original_candidate_replacement_refuses_before_new_actor_source_or_input(self):
        self.start();self.sample();before=deepcopy(self.native_calls())
        original=self.editor.fixture.fixture.fixture.apk
        saved=original.with_name('candidate-before-replacement.apk');original.rename(saved)
        original.write_bytes(saved.read_bytes()+b'foreign candidate bytes')
        self.failed_worker();self.assertEqual(before,self.native_calls())
        self.assertEqual([],self.editor.os.inputs);self.assertEqual([],self.editor.transport.envelopes)
        self.assertEqual(1,len(PrivateFeatureState(self.root/'lifecycle-actor-originals.json').read()['records']))

    def test_foreign_original_host_session_refuses_before_new_actor_source_or_input(self):
        import json
        self.start();self.sample();before=deepcopy(self.native_calls())
        original=self.editor.session.state_path;saved=original.with_suffix('.before-foreign-session.json')
        original.rename(saved);value=json.loads(saved.read_text());value['processIdentity']='124:401'
        original.write_text(json.dumps(value));original.chmod(0o600)
        self.failed_worker();self.assertEqual(before,self.native_calls())
        self.assertEqual([],self.editor.os.inputs);self.assertEqual([],self.editor.transport.envelopes)

    def test_ignored_canonical_normal_ime_is_empty_and_original_input_is_not_repeated(self):
        self.start();self.sample();self.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'))
        self.editor.owner.tablet();self.editor.owner.open_create();self.editor.owner.focus_create();self.sample()
        self.client.activate(uuid.uuid4().hex,'type',dict(text=context(self.run)['unicode']))
        self.editor.field.ignore={'replace'}
        with self.assertRaises(NativeUIError):self.editor.owner.type_create()
        self.assertEqual('',self.sample()['facts']['text']);before=len(self.editor.os.inputs)
        with self.assertRaises(NativeUIError):self.editor.owner.type_create()
        self.assertEqual(before,len(self.editor.os.inputs));self.assertEqual('typing',self.editor.owner.state['phase'])

    def test_readonly_canonical_factory_profile_leaves_actual_session_data_and_inputs_unchanged(self):
        state=self.editor.session.state_path
        def physical(path):
            info=path.stat();return (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,
                info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        before=state.read_bytes(),physical(state)
        inventory={p.name:p.read_bytes() for p in self.root.glob('session-*')}
        self.start();self.sample()
        self.assertEqual(before,(state.read_bytes(),physical(state)))
        self.assertEqual(inventory,{p.name:p.read_bytes() for p in self.root.glob('session-*')})
        self.assertEqual([],self.editor.transport.envelopes);self.assertEqual([],self.editor.os.inputs)
        self.assertEqual({},self.native.layer)
        original=PrivateFeatureState(self.root/'lifecycle-actor-originals.json').read()
        self.assertEqual('before-input-create-world',original['stage'])


if __name__=='__main__':unittest.main()
