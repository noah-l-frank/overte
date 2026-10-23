"""Actual separate Actor host/Parent, native/Parent graph producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
import uuid

from adapters.chat_journey.remote_actor_return import ChatRemoteActorReturn,ChatRemoteActorPending
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from unittest.mock import patch
from fixture.chat_observer_process import LinuxChatObserverProcess

WORKER='''import sys,tempfile
sys.path.insert(0,DEVICE_PATH)
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from self_tests import test_pico_chat_cursor_actor as fixture
# Preserve only this owned fixture's sources until the actual Parent archives
# or removes its own TemporaryDirectory after real kernel process absence.
class RetainedTemporaryDirectory(tempfile.TemporaryDirectory):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._finalizer.detach()
    def cleanup(self):pass
tempfile.TemporaryDirectory=RetainedTemporaryDirectory
config=PrivateFeatureState(sys.argv[2]).read()
h=fixture.PicoChatCursorActorTests();h.setUp();actor=h.actor
actor.stop_once()
def forbidden():raise AssertionError('No native guard after original host closure')
actor.original.native.guard=forbidden
actor.publish_return()
stores=dict(actor=actor.store,stop=actor.stop_store,seal=actor.seal.store,
    flow=actor.publisher.observation.flow_store,cleanup=actor.publisher.observation.cleanup_store,
    publisher=actor.publisher.store,cursor=actor.publisher.cursor.store,
    code=actor.publisher.observation.samples.script_source.store,
    **{'return':actor.return_store,'consumption':actor.consumption_store})
for owner in actor.publisher.cursor.owners:
    stores[owner.stage+'-observation']=owner.store;stores[owner.stage+'-samples']=owner.samples.store
expected={key:actor.previous[key] for key in ('runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance','stopCommand')}
PrivateFeatureState(config['metadata']).write(dict(stores={key:str(value.path) for key,value in stores.items()},expected=expected),None)
print('ready',flush=True)
for line in sys.stdin:
    if line.strip()=='consume':actor.consume_return();print('consumed',flush=True)
    elif line.strip()=='exit':break
    else:raise ValueError('No other fixture command')
'''


class ChatRemoteActorReturnTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);(self.root/'tmp').mkdir(mode=0o700)
        self.entry=self.root/'original-graph-observer.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        self.metadata=PrivateFeatureState(self.root/'original-controller-metadata.json')
        self.config=PrivateFeatureState(self.root/'original-observer-config.json')
        self.config.write(dict(metadata=str(self.metadata.path)),None);self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(self.root/'tmp'),'OVT_CHAT_OBSERVER_TEST_OWNER':self.token})
        self.addCleanup(self.finish);self.output('ready',timeout=20)
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        exe_sha=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest()
        entry_sha=hashlib.sha256(self.entry.read_bytes()).hexdigest()
        def owned(pid):
            root=Path('/proc')/str(pid)
            try:
                with (root/'environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and root.stat().st_uid==os.geteuid() and raw.split(b'\0').count(
                    ('OVT_CHAT_OBSERVER_TEST_OWNER='+self.token).encode())==1
            except FileNotFoundError:return False
        self.process=LinuxChatObserverProcess(identity,self.entry,self.config.path,exe_sha,entry_sha,owned)
        self.addCleanup(self.process.close)
        metadata=self.metadata.read();self.expected=metadata['expected']
        self.assertEqual(identity,self.expected['hostProcessIdentity'])
        self.stores={key:PrivateFeatureState(value) for key,value in metadata['stores'].items()}
        self.assertTrue(all(value.path.is_relative_to(self.root/'tmp') for value in self.stores.values()))
        result=PrivateFeatureState(self.stores['actor'].path.with_name('actual-remote-actor-return.json'))
        self.owner=ChatRemoteActorReturn(self.process,self.stores,self.expected,result)

    def output(self,expected,*,timeout=5):
        self.assertTrue(select.select([self.worker.stdout],[],[],timeout)[0])
        self.assertEqual((expected+'\n').encode(),self.worker.stdout.readline())

    def command(self,value,reply=None):
        self.worker.stdin.write((value+'\n').encode());self.worker.stdin.flush()
        if reply is not None:self.output(reply)

    def finish(self):
        if self.worker.stdin is not None and not self.worker.stdin.closed:self.worker.stdin.close()
        self.worker.wait(timeout=20)
        for stream in (self.worker.stdout,self.worker.stderr):
            if stream is not None:stream.close()

    def test_original_typed_graph_nonce_controlled_successor_real_exit_and_parent_ofds(self):
        owner=self.owner;original=owner.graph.raw;owner.acknowledge()
        with self.assertRaises(ChatRemoteActorPending):owner.finish()
        self.assertFalse(owner.failed);self.assertFalse(owner.complete);self.command('consume','consumed')
        with self.assertRaises(ChatRemoteActorPending):owner.finish()
        self.assertIsNotNone(owner.graph.successor);self.assertFalse(owner.failed);self.assertTrue(owner.graph.pending)
        self.command('exit');self.worker.wait(timeout=5);self.assertEqual(0,self.worker.returncode)
        result=owner.finish();self.assertTrue(owner.complete);self.assertFalse(owner.graph.pending)
        self.assertEqual('complete',result['phase']);self.assertEqual(result,owner.store.read())
        self.assertEqual('ESRCH',result['result']['processReturn']['processAbsence']['errorSymbol'])
        self.assertEqual(original,owner.graph.raw);self.assertEqual('parent-consumed',owner.stores['actor'].read()['phase'])
        self.assertEqual(result,owner.receipt());self.assertTrue(all(value.path.exists() for value in self.stores.values()))
        self.assertTrue(owner.close_host());self.assertTrue(self.process.fd_owner.closed);self.assertTrue(self.process.entry_owner.closed)


    def consume_and_exit(self):
        self.owner.acknowledge();self.command('consume','consumed')
        with self.assertRaises(ChatRemoteActorPending):self.owner.finish()
        self.command('exit');self.worker.wait(timeout=5)

    def test_lost_final_typed_cas_keeps_closed_looking_root_unqualified_without_replay(self):
        owner=self.owner;self.consume_and_exit();write=owner.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='complete':raise OSError('Original typed final publication reply lost')
        owner.store.write=lost
        with self.assertRaises(NativeUIError):owner.finish()
        self.assertTrue(owner.failed);self.assertFalse(owner.complete);self.assertEqual('complete',owner.store.read()['phase'])
        with self.assertRaises(NativeUIError):owner.finish()
        with self.assertRaises(NativeUIError):owner.receipt()
        with self.assertRaises(NativeUIError):ChatRemoteActorReturn(self.process,self.stores,self.expected,owner.store)
        self.assertTrue(owner.store.path.exists());self.assertTrue(all(value.path.exists() for value in self.stores.values()))

    def test_frozen_monotonic_and_two_second_final_metadata_cas_cannot_return_fresh_absence(self):
        from fixture import chat_observer_process as process
        owner=self.owner;self.consume_and_exit();write=owner.store.write;epoch=process.time.time;late=[False]
        def delayed(value,previous):
            write(value,previous)
            if value['phase']=='complete':late[0]=True
        owner.store.write=delayed
        with patch.object(process.time,'monotonic',return_value=0),patch.object(process.time,'time',side_effect=lambda:epoch()+(2 if late[0] else 0)):
            with self.assertRaises(NativeUIError):owner.finish()
        self.assertTrue(late[0]);self.assertTrue(owner.failed);self.assertFalse(owner.complete)
        self.assertEqual('complete',owner.store.read()['phase']);self.assertTrue(owner.graph.pending)

    def test_identical_controlled_successor_replacement_after_live_poll_is_retained_and_refused(self):
        owner=self.owner;owner.acknowledge();self.command('consume','consumed')
        with self.assertRaises(ChatRemoteActorPending):owner.finish()
        store=self.stores['actor'];value=store.read();store.write(value,value)
        self.command('exit');self.worker.wait(timeout=5)
        with self.assertRaises(NativeUIError):owner.finish()
        self.assertTrue(owner.failed);self.assertFalse(owner.complete);self.assertTrue(store.path.exists())


if __name__=='__main__':unittest.main()
