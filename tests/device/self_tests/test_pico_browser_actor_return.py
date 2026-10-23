"""Real separate Python observer/Parent; product/GPU/native producers are seams."""
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
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_actor_return import PicoBrowserActorReturn,BrowserActorReturnPending
from adapters.script_journey.lock import ScriptSourceLock
from fixture.chat_observer_process import LinuxChatObserverProcess
from self_tests import test_chat_remote_actor_return as harness

WORKER='''import sys,tempfile
sys.path.insert(0,DEVICE_PATH)
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_actor_graph import PicoBrowserActorExport
from self_tests.test_pico_browser_actor_retirement import PicoBrowserActorRetirementTests
from feature_journeys.phase_fixture import PhaseRetired
class RetainedTemporaryDirectory(tempfile.TemporaryDirectory):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._finalizer.detach()
    def cleanup(self):pass
tempfile.TemporaryDirectory=RetainedTemporaryDirectory
config=PrivateFeatureState(sys.argv[2]).read()
h=PicoBrowserActorRetirementTests();h.setUp();h.baseline();f=h.f
try:f.actor.publish()
except PhaseRetired:pass
else:raise AssertionError('Original inactive exit missing')
export=PicoBrowserActorExport(f.actor.actor_retirement,config['request'])
h.doCleanups()
def forbidden(*args,**kwargs):raise AssertionError('No target query after original export')
f.target._native_feature_observer=forbidden
export.publish_return()
PrivateFeatureState(config['metadata']).write(dict(export=str(export.store.path),
    stores={key:str(value.path) for key,value in export.stores.items()},lock=str(f.actor.lock.path),expected=export.expected),None)
print('ready',flush=True)
for line in sys.stdin:
    if line.strip()=='consume':export.consume_return();print('consumed',flush=True)
    elif line.strip()=='exit':break
    else:raise ValueError('No other fixture command')
'''


class PicoBrowserActorReturnTests(unittest.TestCase):
    def output(self,expected,*,timeout=5):
        self.assertTrue(select.select([self.worker.stdout],[],[],timeout)[0])
        actual=self.worker.stdout.readline()
        if not actual:
            self.worker.wait(timeout=5)
            self.fail('Owned browser fixture exited before '+expected+': '+self.worker.stderr.read(32768).decode('utf-8','replace'))
        self.assertEqual((expected+'\n').encode(),actual)
    command=harness.ChatRemoteActorReturnTests.command
    finish=harness.ChatRemoteActorReturnTests.finish
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);(self.root/'tmp').mkdir(mode=0o700)
        self.entry=self.root/'original-browser-observer.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        self.metadata=PrivateFeatureState(self.root/'original-controller-metadata.json')
        self.config=PrivateFeatureState(self.root/'original-observer-config.json')
        self.config.write(dict(metadata=str(self.metadata.path),request=uuid.uuid4().hex),None);self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(self.root/'tmp'),'OVT_BROWSER_OBSERVER_TEST_OWNER':self.token})
        self.addCleanup(self.finish);self.output('ready',timeout=25)
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        def owned(pid):
            path=Path('/proc')/str(pid)
            try:
                with (path/'environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and path.stat().st_uid==os.geteuid() and raw.split(b'\0').count(
                    ('OVT_BROWSER_OBSERVER_TEST_OWNER='+self.token).encode())==1
            except FileNotFoundError:return False
        self.process=LinuxChatObserverProcess(identity,self.entry,self.config.path,
            hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),hashlib.sha256(self.entry.read_bytes()).hexdigest(),owned)
        self.addCleanup(self.process.close);value=self.metadata.read();self.expected=value['expected']
        self.assertEqual(identity,self.expected['producerHostProcessIdentity'])
        self.stores={key:PrivateFeatureState(path) for key,path in value['stores'].items()}
        self.export=PrivateFeatureState(value['export']);self.lock=ScriptSourceLock(value['lock'])
        self.assertTrue(all(store.path.is_relative_to(self.root/'tmp') for store in [self.export,*self.stores.values()]))
        self.owner=PicoBrowserActorReturn(self.process,self.export,self.stores,self.lock,self.expected,
            PrivateFeatureState(self.export.path.with_name('pico-tablet-web-actor-remote-receipt.json')))
    def consume_and_exit(self):
        self.owner.acknowledge();self.command('consume','consumed');self.command('exit');self.worker.wait(timeout=5)
    def test_actual_original_graph_nonce_consumption_kernel_exit_and_parent_handle_close(self):
        owner=self.owner;self.assertFalse(owner.complete);owner.acknowledge()
        with self.assertRaises(BrowserActorReturnPending):owner.finish()
        self.command('consume','consumed')
        with self.assertRaises(BrowserActorReturnPending):owner.finish()
        self.command('exit');self.worker.wait(timeout=5)
        result=owner.finish();self.assertTrue(owner.complete);self.assertEqual(result,owner.receipt())
        self.assertEqual('complete',result['phase']);self.assertTrue(owner.close_host())
        self.assertTrue(all(store.path.exists() for store in self.stores.values()));self.assertTrue(self.export.path.exists())
        self.assertGreater(len(owner.graph.images),0);self.assertIsNone(getattr(owner.graph,'adapter',None))
    def test_same_bytes_source_chunk_replacement_refuses_before_nonce_and_keeps_every_original(self):
        chunk=self.stores['history'].path.with_name(self.stores['history'].path.name+'.frame-000.json')
        replacement=chunk.with_name('changed-original-chunk.json');replacement.write_bytes(chunk.read_bytes());replacement.chmod(0o600);replacement.replace(chunk)
        with self.assertRaises(NativeUIError):self.owner.acknowledge()
        self.assertFalse(self.owner.complete);self.assertFalse(self.owner.receiver.issued)
        self.assertIsNone(self.owner.receiver.ack_store.read());self.assertTrue(chunk.exists())
    def test_replaced_original_directory_after_file_copy_refuses_without_nonce_or_adoption(self):
        from adapters.pico4 import browser_actor_graph as graph_module
        read=graph_module.original;changed=[]
        def replaced(path,expected=None):
            result=read(path,expected)
            if not changed:
                changed.append(True);directory=self.export.path.parent;retained=directory.with_name(directory.name+'-retained-original-directory')
                directory.rename(retained);directory.mkdir(mode=0o700)
                for child in list(retained.iterdir()):child.rename(directory/child.name)
            return result
        with patch.object(graph_module,'original',side_effect=replaced),self.assertRaises(NativeUIError):self.owner.acknowledge()
        self.assertEqual([True],changed);self.assertFalse(self.owner.receiver.issued);self.assertFalse(self.owner.complete)
        self.assertTrue(all(store.path.exists() for store in self.stores.values()))
    def test_lost_final_receipt_cas_reply_preserves_unqualified_complete_looking_journal(self):
        self.consume_and_exit();write=self.owner.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='complete':raise OSError('Original browser typed publication reply lost')
        self.owner.store.write=lost
        with self.assertRaises(NativeUIError):self.owner.finish()
        self.assertFalse(self.owner.complete);self.assertTrue(self.owner.failed);self.assertEqual('complete',self.owner.store.read()['phase'])
        with self.assertRaises(NativeUIError):self.owner.receipt()
        with self.assertRaises(NativeUIError):self.owner.finish()
        self.assertTrue(all(store.path.exists() for store in self.stores.values()))
    def test_final_receipt_cas_age_with_frozen_monotonic_refuses_complete_looking_root(self):
        from fixture import chat_observer_process as process
        self.consume_and_exit();write=self.owner.store.write;epoch=process.time.time;late=[False]
        def delayed(value,previous):
            write(value,previous)
            if value['phase']=='complete':late[0]=True
        self.owner.store.write=delayed
        with patch.object(process.time,'monotonic',return_value=0),patch.object(process.time,'time',side_effect=lambda:epoch()+(2 if late[0] else 0)):
            with self.assertRaises(NativeUIError):self.owner.finish()
        self.assertTrue(late[0]);self.assertTrue(self.owner.failed);self.assertFalse(self.owner.complete)
        self.assertEqual('complete',self.owner.store.read()['phase'])
        with self.assertRaises(NativeUIError):self.owner.receipt()
        self.assertTrue(all(store.path.exists() for store in self.stores.values()))


if __name__=='__main__':unittest.main()
