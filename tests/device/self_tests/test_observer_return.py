"""Two original owned stdin processes; opaque payload, no native feature claim."""
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

from adapters.chat_journey.evidence_archive import stamp
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnReceiver
from adapters import observer_return as module
from fixture.chat_observer_process import LinuxChatObserverProcess

WORKER='''import sys
sys.path.insert(0,DEVICE_PATH)
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import ObserverReturnSender,raw_file
from adapters.host_process_identity import host_identity
root=Path(sys.argv[2]).parent
config=PrivateFeatureState(Path(sys.argv[2])).read()
source=PrivateFeatureState(root/'source.json');source.write({'explicitOpaqueFixture':True},None)
raw,physical=raw_file(source)
identity=dict(runId=config['runId'],family='chat-return-model',producerHostProcessIdentity=host_identity(),originalRequestId=config['requestId'])
sender=ObserverReturnSender(PrivateFeatureState(root/'return.json'),PrivateFeatureState(root/'consumption.json'),identity,
    config['payload'].encode(),physical,guard=lambda:raw_file(source)==(raw,physical))
sender.publish();print('ready',flush=True)
for line in sys.stdin:
    if line.strip()=='consume':sender.consume();print('consumed',flush=True)
    elif line.strip()=='fd-counter':
        import os,fcntl
        from unittest.mock import patch
        from adapters import observer_return as original
        from adapters.native_fd_owner import OriginalDescriptor,QUERY
        from adapters.normal_ui import NativeUIError
        foreign=OriginalDescriptor(source.path,os.O_RDONLY|os.O_CLOEXEC)
        pread=os.pread;replaced=[]
        def swap(descriptor,size,offset):
            raw=pread(descriptor,size,offset)
            if not replaced:os.dup2(foreign.fd,descriptor,inheritable=False);replaced.append(descriptor)
            return raw
        refused=False
        with patch.object(os,'pread',side_effect=swap):
            try:original.raw_file(source)
            except NativeUIError:refused=True
        try:retained=fcntl.fcntl(replaced[0],QUERY,foreign.anchor)==1
        except OSError:retained=False
        foreign.require(foreign.fd);foreign.close()
        print(('refused' if refused else 'accepted')+':'+('retained' if retained else 'closed'),flush=True)
    elif line.strip()=='exit':break
    else:raise ValueError('No other fixture action')
'''


class ObserverReturnTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.entry=self.root/'original-observer.py'
        device=str(Path(__file__).resolve().parents[1])
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(device)));self.entry.chmod(0o600)
        self.payload=b'original opaque payload:'+b'x'*20000
        self.run,self.request,self.token=(uuid.uuid4().hex for _ in range(3))
        self.config=PrivateFeatureState(self.root/'config.json')
        self.config.write(dict(runId=self.run,requestId=self.request,payload=self.payload.decode()),None)
        self.store=PrivateFeatureState(self.root/'return.json');self.ack=PrivateFeatureState(self.root/'consumption.json')
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PYTHONDONTWRITEBYTECODE':'1','OVT_CHAT_OBSERVER_TEST_OWNER':self.token})
        self.addCleanup(self.finish);self.output('ready')
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        self.identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        exe_sha=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest()
        entry_sha=hashlib.sha256(self.entry.read_bytes()).hexdigest()
        def owned(pid):
            root=Path('/proc')/str(pid)
            try:
                with (root/'environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and root.stat().st_uid==os.geteuid() and raw.split(b'\0').count(
                    ('OVT_CHAT_OBSERVER_TEST_OWNER='+self.token).encode())==1
            except FileNotFoundError:return False
        self.owner=LinuxChatObserverProcess(self.identity,self.entry,self.config.path,exe_sha,entry_sha,owned)
        self.addCleanup(self.owner.close)
        self.expected=dict(runId=self.run,family='chat-return-model',producerHostProcessIdentity=self.identity,originalRequestId=self.request)

    def output(self,expected):
        self.assertTrue(select.select([self.worker.stdout],[],[],5)[0])
        self.assertEqual((expected+'\n').encode(),self.worker.stdout.readline())

    def command(self,value,reply=None):
        self.worker.stdin.write((value+'\n').encode());self.worker.stdin.flush()
        if reply is not None:self.output(reply)

    def finish(self):
        if self.worker.stdin is not None and not self.worker.stdin.closed:self.worker.stdin.close()
        self.worker.wait(timeout=5)
        for stream in (self.worker.stdout,self.worker.stderr):
            if stream is not None:stream.close()

    def acquire(self):
        source_stamp=stamp((self.root/'source.json').lstat())
        def admit(raw,physical):return type(raw) is bytes and raw==self.payload and physical==source_stamp
        return ObserverReturnReceiver(self.owner,self.store,self.ack,self.expected,admit=admit)

    def exit(self):self.command('exit');self.worker.wait(timeout=5)

    def test_same_file_recycled_literal_read_fd_is_refused_without_closing_foreign_description(self):
        # The worker retains the uncertain original half until actual process
        # finalization. This host never closes the worker's foreign descriptor.
        self.command('fd-counter','refused:retained');self.exit()
        self.assertEqual('ESRCH',self.owner.require_absent()['errorSymbol'])
        self.assertTrue(self.store.path.exists());self.assertIsNone(self.ack.read())

    def test_original_bytes_nonce_echo_and_actual_reaped_kernel_absence(self):
        receiver=self.acquire();self.assertEqual(self.payload,receiver.raw)
        intent=receiver.acknowledge();self.command('consume','consumed')
        self.assertEqual(intent,self.store.read()['consumption'])
        with self.assertRaises(NativeUIError):receiver.receipt()
        self.exit();receipt=receiver.receipt()
        self.assertEqual('ESRCH',receipt['processAbsence']['errorSymbol']);self.assertTrue(receiver.complete)
        self.assertEqual(self.identity,receipt['producerHostProcessIdentity'])
        with self.assertRaises(NativeUIError):receiver.receipt()
        self.assertTrue(self.store.path.exists());self.assertTrue(self.ack.path.exists())

    def test_lost_ack_reply_keeps_original_nonce_and_never_writes_it_again(self):
        receiver=self.acquire();write=PrivateFeatureState.write;writes=[]
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path==self.ack.path:writes.append(value['nonce']);raise OSError('Lost original write reply')
            return result
        with patch.object(PrivateFeatureState,'write',new=lost):
            with self.assertRaises(OSError):receiver.acknowledge()
        self.command('consume','consumed');self.exit();self.assertEqual('ESRCH',receiver.receipt()['processAbsence']['errorSymbol'])
        self.assertEqual([receiver.intent['nonce']],writes)
        with self.assertRaises(NativeUIError):receiver.acknowledge()

    def test_same_bytes_chunk_replacement_before_ack_is_refused_and_retained(self):
        receiver=self.acquire();child=receiver.history.store(0);original=child.read();child.write(original,original)
        with self.assertRaises(NativeUIError):receiver.acknowledge()
        self.assertIsNone(self.ack.read());self.assertTrue(child.path.exists());self.assertIsNone(self.worker.poll())

    def test_consumed_root_same_bytes_replacement_after_live_poll_cannot_be_adopted(self):
        receiver=self.acquire();receiver.acknowledge();self.command('consume','consumed')
        with self.assertRaises(NativeUIError):receiver.receipt()
        original=self.store.read();self.store.write(original,original);self.exit()
        with self.assertRaises(NativeUIError):receiver.receipt()
        self.assertFalse(receiver.complete);self.assertTrue(self.store.path.exists())

    def test_mutated_warm_payload_and_scope_cannot_be_accepted(self):
        receiver=self.acquire();receiver.raw=b'changed'
        with self.assertRaises(NativeUIError):receiver.acknowledge()
        self.assertIsNone(self.ack.read())

    def test_mutated_scope_cannot_admit_different_payload_metadata(self):
        receiver=self.acquire();receiver.scope['family']='other-family'
        with self.assertRaises(NativeUIError):receiver.acknowledge()
        self.assertIsNone(self.ack.read())

    def test_wrong_consumed_nonce_does_not_prove_parent_return_delivery(self):
        receiver=self.acquire();receiver.acknowledge()
        original=self.ack.read();self.ack.write({**original,'nonce':uuid.uuid4().hex},original)
        self.command('consume','consumed');self.exit()
        with self.assertRaises(NativeUIError):receiver.receipt()
        self.assertFalse(receiver.complete);self.assertTrue(self.ack.path.exists())

    def test_identical_child_replaced_between_initial_signature_and_load_is_refused(self):
        load=module.ChatSourceChunks.load;replaced=[]
        def change(history,manifest):
            if history.root.path==self.store.path and not replaced:
                child=history.store(0);value=child.read();child.write(value,value);replaced.append(True)
            return load(history,manifest)
        with patch.object(module.ChatSourceChunks,'load',new=change):
            with self.assertRaises(NativeUIError):self.acquire()
        self.assertEqual([True],replaced);self.assertIsNone(self.ack.read())

    def test_rootless_consumption_chunks_forbid_acknowledgment(self):
        receiver=self.acquire();child=module.ChatSourceChunks(self.ack,{}).store(0)
        child.write(dict(unknownOriginal=True),None)
        with self.assertRaises(NativeUIError):receiver.acknowledge()
        self.assertIsNone(self.ack.read());self.assertTrue(child.path.exists())

    def test_late_receipt_copy_with_frozen_monotonic_does_not_refresh_absence(self):
        from fixture import chat_observer_process as process
        receiver=self.acquire();receiver.acknowledge();self.command('consume','consumed');self.exit()
        copied=module.deepcopy;epoch=process.time.time;late=[False]
        def copy(value):
            result=copied(value)
            if type(value) is dict and value.get('observerReturnReceiptVersion')==1:late[0]=True
            return result
        with patch.object(module,'deepcopy',side_effect=copy),patch.object(process.time,'monotonic',return_value=0),\
            patch.object(process.time,'time',side_effect=lambda:epoch()+(2 if late[0] else 0)):
            with self.assertRaises(NativeUIError):receiver.receipt()
        self.assertTrue(late[0]);self.assertFalse(receiver.complete)

    def test_live_original_owner_cannot_admit_ready_return_after_exit(self):
        self.exit()
        with self.assertRaises(NativeUIError):self.acquire()
        self.assertIsNone(self.ack.read())


if __name__=='__main__':unittest.main()
