"""One real fixed-shell/byte-stdin/physical return, declared Native producer.

No Qt/native builder/publisher/device executes. Inner six DTOs remain the
existing intentionally unqualified wire model; this scope proves transport.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
import select
import time
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from adapters.normal_ui import NativeUIError
from adapters.chat_journey.archive_file import signature
from adapters.pico4 import emote_source_transaction_command as source
from adapters.pico4.emote_source_transaction_wire import SIDE_LIMIT
from adapters.pico4.emote_source_transaction_profile import PicoEmoteSourceProfile,SLOT
from adapters.pico4.emote_source_transaction_physical import PicoEmoteSourcePhysicalWire
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import canonical
from self_tests import test_pico_emote_source_transaction_wire as original

RETAINED=[]
READINESS=[]
PRODUCER=r'''
import hashlib,json,os,pathlib,sys,time
root=pathlib.Path(sys.argv[1]);body=sys.stdin.buffer.read()
control=root/'files/overte-e2e/android-control-command.json'
end=time.monotonic()+5
while time.monotonic()<end:
 if control.is_file():
  value=json.loads(control.read_text())
  if value.get('commandId')==sys.argv[2]:break
 time.sleep(.005)
else:sys.exit(7)
path=root/'files/overte-e2e/feature-pico-emote-source-transaction.wire'
with path.open('xb') as stream:
 os.chmod(path,0o600);stream.write(body);stream.flush();os.fsync(stream.fileno())
def node(s):return [str(v) for v in (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink)]
info=path.stat();receipt=path.with_name('feature-pico-emote-source-receipt.json')
with receipt.open('xb') as stream:
 os.chmod(receipt,0o600)
 proof=dict(leaf=path.name,maximumFileBytes=int(sys.argv[3]),rootNode=node(path.parent.stat()),sampleNode=node(info),
  sampleStamp=node(info)+[str(info.st_size),str(info.st_mtime_ns),str(info.st_ctime_ns)],bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
 value=dict(picoEmoteSourceReceiptVersion=1,commandId=sys.argv[2],wire=proof,receiptNode=node(os.fstat(stream.fileno())),builderSettled=True)
 stream.write(json.dumps(value,sort_keys=True,separators=(',',':')).encode());stream.flush();os.fsync(stream.fileno())
while True:time.sleep(.05)
'''


class SourceTransactionCommandTests(unittest.TestCase):
    def setUp(self):
        self.children=[];self.calls=0;self.now=1.;self.root=Path(tempfile.mkdtemp(prefix='pico-emote-source-sdk-'))
        self.profile=PicoEmoteSourceProfile();lock=ScriptSourceLock(self.root/'source.lock')
        self.fixture=SimpleNamespace(root=self.root,lock=lock,command=dict(schemaVersion=1,
            action='feature-pico-emote-source-transaction',commandId='1'*32,runId='2'*32,
            originalPolicySha256='3'*64,parentBaselineSha256='4'*64))
        self.fixture.raw=AudioRawArchive(self.root/'source-raw.json',dict(picoEmoteSourceTransactionVersion=1,
            picoEmoteSourcePhysicalVersion=2,sourceProfileSha256=self.profile.sha256,declaredHostModel=True),
            lock,self.profile.resource_identity,self.bill,self.clock)
        self.fixture.literal=original.SourceTransactionWireTests.body(self.fixture)
        self.addCleanup(self.finalize)
        (self.root/'files').mkdir(mode=0o700);(self.root/'files/overte-e2e').mkdir(mode=0o700)

    def clock(self):return self.now
    def guard(self):return True

    def bill(self):
        value=self.profile.extra_bill()
        for path in self.root.rglob('*'):
            if not path.is_file() or path.name.startswith('source-raw.json'):continue
            raw=path.read_bytes();value['parts']+=1;value['storedBytes']+=len(raw);value['decodedBytes']+=len(raw)
        return value

    def finalize(self):
        for child in self.children:
            if child.poll() is None:child.terminate()
            child.wait(timeout=3)
        def inventory():return {str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),physical=original.signature(p.stat()))
            for p in self.root.rglob('*') if p.is_file()}
        before=inventory();self.assertTrue(self.fixture.raw.close_host());after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(root=str(self.root),files=after,actualSDKCommands=self.calls,declaredNativeProducerOnly=True,
            actualRawArchiveCloseCalled=True,processesRemaining=0))

    @staticmethod
    def identity(pid):
        fields=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(') ',1)[1].split()
        return str(pid)+':'+fields[19]

    def producer(self,body):
        child=subprocess.Popen([sys.executable,'-S','-c',PRODUCER,str(self.root),self.fixture.command['commandId'],str(source.FILE_LIMIT)],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.children.append(child);child.stdin.write(body);child.stdin.close();return child

    def acquire(self,identity):
        f=self.fixture;arguments,stdin=source.command(f.command,identity);argv=shlex.split(arguments[1])
        self.assertEqual(['exec-out'],arguments[:1]);self.assertEqual(['run-as','org.overte.pico','sh','-c'],argv[:4])
        token=f.raw.reserve('declared-source-sdk',f.command,source.WIRE_LIMIT,side_bytes=0)
        self.calls+=1
        returned=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.root,input=stdin,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=5,check=False).stdout
        reference=f.raw.retain(token,returned) # BEFORE any physical/JSON parser.
        self.assertEqual(returned,f.raw.literal(reference));return returned,reference

    def exchange(self,value,*,timeout):
        arguments,stdin=source.command(value,self.native_identity);argv=shlex.split(arguments[1]);self.calls+=1
        return subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.root,input=stdin,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=timeout,check=False).stdout

    def seeded_originals(self):
        """Declared producer seed for hostile first-get Node counters only."""
        import json
        root=self.root/'files/overte-e2e';wire=root/'feature-pico-emote-source-transaction.wire'
        wire.write_bytes(self.fixture.literal);wire.chmod(0o600)
        node=lambda info:[str(v) for v in (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink)]
        info=wire.stat();receipt=root/'feature-pico-emote-source-receipt.json'
        with receipt.open('xb') as stream:
            receipt.chmod(0o600)
            proof=dict(leaf=wire.name,maximumFileBytes=source.FILE_LIMIT,rootNode=node(root.stat()),sampleNode=node(info),
                sampleStamp=node(info)+[str(info.st_size),str(info.st_mtime_ns),str(info.st_ctime_ns)],
                bytes=info.st_size,sha256=hashlib.sha256(wire.read_bytes()).hexdigest())
            value=dict(picoEmoteSourceReceiptVersion=1,commandId=self.fixture.command['commandId'],wire=proof,
                receiptNode=node(os.fstat(stream.fileno())),builderSettled=True)
            stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
        return wire,receipt

    def test_one_actual_command_stdin_and_physical_sdk_original_without_body_copy(self):
        f=self.fixture;body=f.literal;child=self.producer(body);identity=self.identity(child.pid)
        with f.lock.held():
            returned,reference=self.acquire(identity)
            proof=source.envelope(returned,f.command['commandId'],identity)
            self.assertEqual(hashlib.sha256(body).hexdigest(),proof.sha256)
            self.assertEqual(len(body),proof.size)
            self.assertEqual(body,memoryview(returned)[proof.offset:proof.offset+proof.size])
            native=original.source.extents(returned,f.command,start=proof.offset,end=proof.offset+proof.size)
            values=original.source.decode_sources(returned,native)
            self.assertEqual(original.source.LABELS,tuple(values))
            self.assertTrue(all(row.offset>=proof.offset for row in native.records))
            self.assertEqual(canonical(f.command),(self.root/'files/overte-e2e/android-control-command.json').read_bytes())
            self.assertEqual(1,self.calls);self.assertEqual(returned,f.raw.literal(reference))
            self.assertIsNone(child.poll())

    def test_exact_span_bounds_refuse_bool_foreign_and_suffix_bytes_without_reclassifying_body(self):
        f=self.fixture;child=self.producer(f.literal);identity=self.identity(child.pid)
        with f.lock.held():
            returned,_reference=self.acquire(identity);proof=source.envelope(returned,f.command['commandId'],identity)
            for start,end in ((True,len(returned)),(proof.offset,False),(-1,len(returned)),
                    (proof.offset,len(returned)+1),(proof.offset,proof.offset),(proof.offset,proof.offset+proof.size+1)):
                with self.assertRaises(NativeUIError):original.source.extents(returned,f.command,start=start,end=end)
            exact=original.source.extents(returned,f.command,start=proof.offset,end=proof.offset+proof.size)
            self.assertEqual(6,len(exact.records));self.assertEqual(1,self.calls)

    def test_preexisting_uncertain_command_pending_refuses_before_control_publication(self):
        f=self.fixture;pending=self.root/'files/overte-e2e/feature-pico-emote-source-request.pending'
        pending.write_bytes(b'actual prior incomplete request\x00');pending.chmod(0o600)
        before=original.signature(pending.stat());raw=pending.read_bytes()
        with f.lock.held():
            returned,_reference=self.acquire(self.identity(os.getpid()))
            self.assertEqual(b'',returned)
            with self.assertRaises(NativeUIError):source.envelope(returned,f.command['commandId'],self.identity(os.getpid()))
            self.assertFalse((pending.parent/'android-control-command.json').exists())
            self.assertEqual(raw,pending.read_bytes());self.assertEqual(before,original.signature(pending.stat()))

    def test_oversized_current_source_prefix_is_retained_and_never_a_complete_envelope(self):
        f=self.fixture
        prefix=f.literal.split(b'\n',2)[:2];head=b'\n'.join(prefix)+b'\n'
        body=head+os.urandom(source.FILE_LIMIT+1-len(head));child=self.producer(body);identity=self.identity(child.pid)
        with f.lock.held():
            returned,reference=self.acquire(identity)
            self.assertLessEqual(len(returned),source.WIRE_LIMIT)
            self.assertEqual(returned,f.raw.literal(reference))
            with self.assertRaises(NativeUIError):source.envelope(returned,f.command['commandId'],identity)
            self.assertEqual(1,self.calls)

    def first_node_swap(self,selected):
        f=self.fixture;paths=self.seeded_originals();path=paths[selected]
        raw=path.read_bytes();inode=path.stat().st_ino;retained=path.with_name('retained-original-'+path.name)
        path.rename(retained);path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(inode,path.stat().st_ino);self.assertEqual(raw,retained.read_bytes())
        with f.lock.held():
            identity=self.identity(os.getpid());returned,reference=self.acquire(identity)
            self.assertEqual(returned,f.raw.literal(reference))
            with self.assertRaises(NativeUIError):source.envelope(returned,f.command['commandId'],identity)
            self.assertEqual(raw,path.read_bytes());self.assertEqual(raw,retained.read_bytes());self.assertEqual(1,self.calls)

    def test_actual_identical_wire_inode_replacement_before_first_get_cannot_join_original_receipt(self):
        self.first_node_swap(0)

    def test_actual_identical_receipt_inode_replacement_before_first_get_cannot_claim_own_original_node(self):
        self.first_node_swap(1)

    def test_actual_physical_reply_owner_reuses_raw_writer_and_keeps_slot_after_retain(self):
        f=self.fixture;child=self.producer(f.literal);self.native_identity=self.identity(child.pid)
        with f.lock.held():
            owner=PicoEmoteSourcePhysicalWire(f.raw,self.exchange,self.guard,self.clock,self.profile,
                role='primary',identity=self.native_identity)
            before=self.profile.extra_bill();reference,proof,values=owner.read(f.command)
            self.assertEqual(before,self.profile.extra_bill());self.assertGreaterEqual(before['storedBytes'],SLOT)
            self.assertEqual([],f.raw.state['pending']);self.assertEqual(1,self.calls)
            self.assertEqual(original.source.LABELS,tuple(values));self.assertGreater(proof.sdk.offset,0)
            self.assertTrue(all(row.offset>=proof.sdk.offset for row in proof.sources.records))
            self.assertIs(owner.archive,f.raw);self.assertEqual('emote-source-txn',f.raw.pages[0]['receipts'][0]['role'])
            self.assertTrue(f.raw.literal(reference).startswith(source.HEADER))

    def test_actual_owned_external_file_exhaustion_refuses_before_sdk_or_control_writer(self):
        from adapters.script_journey.history import MAX_RAW
        f=self.fixture;blob=self.root/'actual-owned-capacity.bin'
        with blob.open('wb') as stream:stream.truncate(MAX_RAW)
        blob.chmod(0o600);self.native_identity=self.identity(os.getpid())
        with f.lock.held():
            owner=PicoEmoteSourcePhysicalWire(f.raw,self.exchange,self.guard,self.clock,self.profile,
                role='primary',identity=self.native_identity)
            with self.assertRaises(NativeUIError):owner.read(f.command)
            self.assertEqual(0,self.calls);self.assertIsNone(owner.reference)
            self.assertFalse((self.root/'files/overte-e2e/android-control-command.json').exists())

    def test_native_receipt_failure_keeps_same_slot_after_raw_retain_and_blocks_new_sdk(self):
        f=self.fixture;wire,_receipt=self.seeded_originals();raw=wire.read_bytes()
        wire.rename(wire.with_name('retained-faulted-original-wire'));wire.write_bytes(raw);wire.chmod(0o600)
        self.native_identity=self.identity(os.getpid())
        with f.lock.held():
            owner=PicoEmoteSourcePhysicalWire(f.raw,self.exchange,self.guard,self.clock,self.profile,
                role='primary',identity=self.native_identity);before=self.profile.extra_bill()
            with self.assertRaises(NativeUIError):owner.read(f.command)
            self.assertTrue(owner.failed);self.assertIsNotNone(owner.reference)
            self.assertEqual([],f.raw.state['pending']);self.assertEqual(before,self.profile.extra_bill())
            self.assertGreaterEqual(before['storedBytes'],SLOT)
            self.assertTrue(f.raw.literal(owner.reference).startswith(source.HEADER));self.assertEqual(1,self.calls)
            with self.assertRaises(NativeUIError):owner.read(f.command)
            self.assertEqual(1,self.calls)

    def test_cold_reply_hook_substitution_refuses_before_sdk(self):
        f=self.fixture;self.native_identity=self.identity(os.getpid())
        with f.lock.held():
            owner=PicoEmoteSourcePhysicalWire(f.raw,self.exchange,self.guard,self.clock,self.profile,
                role='primary',identity=self.native_identity)
            owner.reply_parser=lambda wire,value:({}, {})
            with self.assertRaises(NativeUIError):owner.read(f.command)
            self.assertEqual(0,self.calls);self.assertIsNone(owner.reference)


    def publication_readiness(self,mode):
        f=self.fixture;root=self.root/'files/overte-e2e';marker=root/'feature-pico-emote-capture-pending.json'
        identity=self.identity(os.getpid());args,stdin=source.command(f.command,identity);argv=shlex.split(args[1])
        self.assertEqual(['exec-out'],args[:1]);self.assertEqual(['run-as','org.overte.pico','sh','-c'],argv[:4])
        facts={}
        def marker_snapshot():
            return os.readlink(marker).encode() if mode=='dangling' else marker.read_bytes()
        with f.lock.held():
            # Same existing raw writer and unchanged guaranteed slot BEFORE SDK.
            token=f.raw.reserve('declared-source-sdk',f.command,source.WIRE_LIMIT,side_bytes=0)
            self.calls+=1
            child=subprocess.Popen(['sh','-c',argv[4],*argv[5:]],cwd=self.root,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.children.append(child);child.stdin.write(stdin);child.stdin.close();child.stdin=None
            # No source is published until the actual one command exists.
            control=root/'android-control-command.json';until=time.monotonic()+1
            while time.monotonic()<until:
                if control.is_file() and control.read_bytes()==stdin:break
                time.sleep(.001)
            else:raise RuntimeError('Actual original command was not published')
            target=None
            if mode=='dangling':
                target=root/'never-created-owned-marker-target'
                marker.symlink_to(target.name)
            else:
                with marker.open('xb') as stream:
                    os.chmod(marker,0o600);stream.write(f.command['commandId'].encode()+b'\n' +b'0'*64+b'\n')
                    stream.flush();os.fsync(stream.fileno())
            directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
            try:
                os.fsync(directory)
                marker_stamp=signature(marker.lstat());marker_bytes=marker_snapshot()
                wire,receipt=self.seeded_originals()
                # Record actual facts only. ALL completion/custody assertions
                # are outside SourceLock's exception-normalization context.
                receipt_raw=receipt.read_bytes();receipt_hash=hashlib.sha256(receipt_raw).hexdigest()
                facts['matchingReceiptVisible']=b'"commandId":"'+f.command['commandId'].encode()+b'"' in receipt_raw
                visible,_,_=select.select([child.stdout],[],[],.15)
                facts['stdoutReadyWhileHeld']=bool(visible);facts['childExitWhileHeld']=child.poll()
                facts['markerStampBeforeRelease']=signature(marker.lstat());facts['markerBytesBeforeRelease']=marker_snapshot()
                if mode=='release':
                    os.unlink(marker.name,dir_fd=directory);os.fsync(directory)
                returned,stderr=child.communicate(timeout=5)
                # Exact bytes durable BEFORE physical framing/JSON/outcome checks.
                reference=f.raw.retain(token,returned)
                facts['reopenedLiteral']=f.raw.literal(reference)
                facts['receiptHashAfter']=hashlib.sha256(receipt.read_bytes()).hexdigest()
                facts['actualCommands']=self.calls;facts['actualControl']=control.read_bytes()
                facts['exitCode']=child.returncode;facts['stdout']=returned;facts['stderr']=stderr
                if mode=='release':
                    facts['markerExistsAfter']=marker.exists();facts['markerSymlinkAfter']=marker.is_symlink()
                    if child.returncode==0:
                        proof=source.envelope(returned,f.command['commandId'],identity)
                        facts['originalBodyEqual']=f.literal==memoryview(returned)[proof.offset:proof.offset+proof.size]
                else:
                    facts['markerStampAfter']=signature(marker.lstat());facts['markerBytesAfter']=marker_snapshot()
                    facts['markerLinkAfter']=None if target is None else os.readlink(marker)
            finally:os.close(directory)
        # These are genuine outer test verdicts; no SourceLock/Parent.act can
        # normalize or swallow a failed assertion as an expected runtime refusal.
        self.assertTrue(facts['matchingReceiptVisible'])
        self.assertFalse(facts['stdoutReadyWhileHeld']);self.assertIsNone(facts['childExitWhileHeld'])
        self.assertEqual(marker_stamp,facts['markerStampBeforeRelease']);self.assertEqual(marker_bytes,facts['markerBytesBeforeRelease'])
        self.assertEqual(returned,facts['reopenedLiteral']);self.assertEqual(receipt_hash,facts['receiptHashAfter'])
        self.assertEqual(1,facts['actualCommands']);self.assertEqual(stdin,facts['actualControl'])
        if mode=='release':
            self.assertEqual(0,facts['exitCode']);self.assertTrue(facts['originalBodyEqual'])
            self.assertFalse(facts['markerExistsAfter']);self.assertFalse(facts['markerSymlinkAfter'])
        else:
            self.assertNotEqual(0,facts['exitCode']);self.assertEqual(b'',facts['stdout'])
            self.assertEqual(marker_stamp,facts['markerStampAfter']);self.assertEqual(marker_bytes,facts['markerBytesAfter'])
            if target is not None:self.assertEqual(target.name,facts['markerLinkAfter'])
        proof=dict(mode=mode,zeroStdoutWhileMatchingReceiptAndMarkerVisible=True,
            actualCommands=facts['actualCommands'],exitCode=facts['exitCode'],stdoutBytes=len(returned),
            exactRawRetainedBeforeParser=True,stderrHex=stderr.hex(),
            originalMarkerFullStampPreserved=(mode!='release'),root=str(self.root),
            nativeExecuted=False,currentSourceQualified=False,wholeQualified=False)
        if mode=='dangling':
            proof.update(originalSymlinkPhysical=marker_stamp,terminalSymlinkPhysical=facts['markerStampAfter'],
                originalLinkTarget=target.name,terminalLinkTarget=facts['markerLinkAfter'],markerPath=str(marker))
        READINESS.append(proof)

    def test_visible_receipt_waits_until_actual_marker_unlink_and_directory_fsync(self):
        self.publication_readiness('release')

    def test_visible_receipt_with_retained_marker_refuses_bounded_without_republish(self):
        self.publication_readiness('retained')

    def test_visible_receipt_with_dangling_marker_symlink_refuses_without_republish(self):
        self.publication_readiness('dangling')


if __name__=='__main__':unittest.main()
