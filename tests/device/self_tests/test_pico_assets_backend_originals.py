"""Real original files/PIDs/OFDs; AssetServer packets/native hooks are modeled.

The short stdin worker supplies real kernel/executable ownership only. It is
not an AssetServer, Domain, oven, device service or native compiler.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import need
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_backend_originals import PicoAssetsBackendOriginals,UNRESOLVED
from adapters.pico4.assets_raw_archive import compact
from adapters.script_journey.history import canonical
from fixture.messages_mixer import start_identity
from self_tests.test_pico_assets_raw_archive import RawFixtureOwner

ROOT=Path(__file__).resolve().parents[3]
RUN='a'*32
DOMAIN='11111111-1111-4111-8111-111111111111'
SERVER='22222222-2222-4222-8222-222222222222'


class AssetsBackendOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.fd_before=len(os.listdir('/proc/self/fd'))
        self.root=Path(tempfile.mkdtemp(prefix='pico-assets-backend-originals-'));self.root.chmod(0o700)
        print('Retained modeled backend and real kernel/file originals:',self.root,flush=True)
        self.server=self.root/'server';self.server.mkdir(mode=0o700)
        self.archive=self.root/'archive';self.archive.mkdir(mode=0o700)
        self.owner=RawFixtureOwner(self.archive,version=3)
        env=os.environ.copy();env.update(OVERTE_E2E_PICO_ASSETS_ORIGINALS_ENABLE='1',OVERTE_E2E_PICO_ASSETS_ORIGINALS=str(self.server))
        self.process=subprocess.Popen([sys.executable,'-u','-c','import sys;sys.stdin.buffer.read()','-t','3'],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        self.file=self.server/'assets-bakes.json';self.packet=self.value();self.write(self.packet)
        self.retained=[];self.reader=None;self.uncertain=False

    def value(self):
        now=time.time_ns()//1000000
        return dict(assetsBakeOriginalsVersion=2,instance='b'*32,sequence=1,processId=self.process.pid,
            processStart=start_identity(self.process.pid),domainId=DOMAIN,assetServerId=SERVER,
            capturedEpochMs=now,contextCapturedEpochMs=now,valid=True,jobs=[],mappings=[],blobs=[],pending=0)

    def write(self,value):
        self.file.write_bytes(value if type(value) is bytes else canonical(value));self.file.chmod(0o600)

    def capacity(self):
        self.owner.lock.assert_held()
        if self.owner.raws.active is None:self.owner.raws.reserve('backend',dict(schemaVersion=1,runId=RUN))
        else:self.owner.raws.verify()

    def retain(self,raw):
        literal=self.owner.raws.retain_bytes(raw);index=len(self.owner.state['rawReads'])
        self.owner.state['rawReads'].append(dict(role='backend',rawOriginal=compact(literal)))
        self.owner.raws.clear_intent();self.owner.save();self.owner.raws.delivered(index)
        self.retained.append(literal)

    def make(self,**options):
        executable=hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()
        self.reader=PicoAssetsBackendOriginals(self.server,self.process.pid,executable,
            lambda pid:pid==self.process.pid and self.process.poll() is None,DOMAIN,
            guard=lambda:True,retain=self.retain,capacity=self.capacity,**options)
        return self.reader

    def stop(self):
        if self.process.poll() is None:self.process.stdin.close()
        self.assertEqual(0,self.process.wait(timeout=5))
        if not self.process.stdin.closed:self.process.stdin.close()
        for _ in range(2):
            with self.assertRaises(ProcessLookupError):os.kill(self.process.pid,0)

    def tearDown(self):
        if self.reader is not None:
            closed=self.reader.close_host()
            self.assertEqual(not self.uncertain,closed)
        self.assertTrue(self.owner.raws.close_host());self.stop()
        if self.uncertain:
            (self.root/'unresolved-original-fds.json').write_text(json.dumps(dict(
                reason='actual recycled original file FD retained, foreign alias never closed',
                originalFileFD=self.reader.file.fd,originalAnchorFD=self.reader.file.anchor)))
            self.assertGreater(len(os.listdir('/proc/self/fd')),self.fd_before)
        else:self.assertEqual(self.fd_before,len(os.listdir('/proc/self/fd')))

    def test_original_existing_process_file_bytes_raw_archive_and_advancing_same_inode(self):
        reader=self.make();node=self.file.stat().st_ino
        with self.owner.lock.held():
            first=reader.read(RUN);before=self.owner.raws.literal(self.retained[-1])
            self.packet=self.value();self.packet['sequence']=2;self.write(self.packet)
            second=reader.read(RUN)
            self.assertEqual(1,first['source']['sequence']);self.assertEqual(2,second['source']['sequence'])
            self.assertEqual(node,self.file.stat().st_ino);self.assertEqual(before,self.owner.raws.literal(self.retained[0]))
            self.assertEqual(canonical(self.packet),self.owner.raws.literal(self.retained[1]))
            self.assertEqual(2,len(reader.history));self.assertIsNone(reader.pending)

    def test_malformed_binary_retained_before_decode_and_failed_scope_never_reads_again(self):
        self.write(b'\xff actual invalid UTF8');reader=self.make()
        with self.owner.lock.held():
            with self.assertRaises((UnicodeError,ValueError,NativeUIError)):reader.read(RUN)
            self.assertEqual(b'\xff actual invalid UTF8',self.owner.raws.literal(self.retained[-1]))
            with patch('os.pread',side_effect=AssertionError('No retry getter')):
                with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertTrue(reader.failed);self.assertIn(reader,UNRESOLVED)

    def test_original_frozen_native_clock_slow_capacity_has_zero_actual_file_read(self):
        reader=self.make(clock_ms=lambda:self.packet['capturedEpochMs']);capacity=reader.capacity;reads=[];pread=os.pread
        def late():capacity();time.sleep(1.51)
        reader.capacity=late
        def observed(fd,*args):
            if fd==reader.file.fd:reads.append(fd)
            return pread(fd,*args)
        with self.owner.lock.held(),patch('os.pread',side_effect=observed),self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],reads);self.assertEqual([],self.retained);self.assertIsNotNone(self.owner.disk['pendingRawRead'])

    def test_pending_or_uncertain_native_publication_is_not_a_ready_old_packet(self):
        pending=self.server/'assets-bakes.pending';pending.write_bytes(b'');pending.chmod(0o600)
        reader=self.make();reads=[];pread=os.pread
        def observed(fd,*args):
            if fd==reader.file.fd:reads.append(fd)
            return pread(fd,*args)
        with self.owner.lock.held(),patch('os.pread',side_effect=observed),self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],reads);self.assertFalse(self.retained);self.assertTrue(pending.exists())

    def test_byte_equal_replaced_backend_file_is_refused_before_getter(self):
        reader=self.make();capacity=reader.capacity
        def exchange():
            capacity();raw=self.file.read_bytes();self.file.rename(self.root/'original-backend.json');self.write(raw)
        reader.capacity=exchange
        with self.owner.lock.held(),self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertFalse(self.retained);self.assertEqual(canonical(self.packet),self.file.read_bytes())

    def test_recycled_same_inode_file_description_retained_and_foreign_alias_untouched(self):
        reader=self.make();foreign=OriginalDescriptor(self.file,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            os.dup2(foreign.fd,reader.file.fd);self.uncertain=True
            with self.owner.lock.held(),self.assertRaises(NativeUIError):reader.read(RUN)
            foreign.require(foreign.fd);self.assertFalse(self.retained)
            self.assertFalse(reader.file.close());foreign.require(foreign.fd)
        finally:self.assertTrue(foreign.close())

    def test_foreign_same_inode_holder_cannot_query_or_close_and_originals_stay_retained(self):
        reader=self.make();original=reader.file
        foreign=OriginalDescriptor(self.file,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            reader.file=foreign
            with self.owner.lock.held(),patch('os.pread',side_effect=AssertionError('No foreign getter')):
                with self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertTrue(reader.failed);self.assertIn(reader,UNRESOLVED)
            self.assertFalse(reader.close_host());foreign.require(foreign.fd);original.require(original.fd)
            self.assertFalse(self.retained)
        finally:
            # Test authority still holds both actual originals. No live source
            # continuation/adoption is attempted after its sticky failure.
            reader.file=original;self.assertTrue(foreign.close())

    def test_process_death_after_acquisition_does_not_prevent_raw_durability(self):
        reader=self.make();retain=reader.retain
        def death(raw):self.stop();retain(raw)
        reader.retain=death
        with self.owner.lock.held():
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(canonical(self.packet),self.owner.raws.literal(self.retained[-1]))
        self.assertTrue(reader.failed);self.assertEqual(canonical(self.packet),reader.acquired)

    def test_passive_native_gates_preserve_non_e2e_product_bodies_without_compiling(self):
        expected={
            'AssetServer.h':'23a8b25c06769b4f86b14291694dee569bdd895ed12ab667799c9271f8cfdf8c',
            'AssetServer.cpp':'1dca64c0dadfad84dfd46d6a7cdf62078f0e16daf18ebdbb1d58358878ac260f',
            'BakeAssetTask.h':'e3d23303baee86a353cbcd16b32e00b344f2e0067022a41891a1f99539581a33',
            'BakeAssetTask.cpp':'0e47ac0a350ec114fcd60a0b68e11f90f9a54fe8274c76bb2e98dc324cf1c1f8'}
        for name,digest in expected.items():
            text=(ROOT/'assignment-client/src/assets'/name).read_text();rows=[];depth=0
            for line in text.splitlines(keepends=True):
                if depth:
                    if line.lstrip().startswith(('#if ','#ifdef ','#ifndef ')):depth+=1
                    elif line.lstrip().startswith('#endif'):depth-=1
                elif line.lstrip().startswith('#if ') and 'OVERTE_E2E_FEATURE_TESTS' in line:depth=1
                else:rows.append(line)
            self.assertEqual(0,depth);self.assertEqual(digest,hashlib.sha256((''.join(rows).rstrip()+'\n').encode()).hexdigest())
        header=(ROOT/'tests/device/native/PicoAssetsBakeOriginals.h').read_text()
        self.assertIn('OVERTE_E2E_PICO_ASSETS_ORIGINALS_ENABLE")!="1"',header)
        self.assertIn('PICO_ASSETS_F_DUPFD_QUERY=1027',header)
        self.assertIn('::fcntl(_fd,PICO_ASSETS_F_DUPFD_QUERY,_anchor)!=1',header)
        self.assertIn('assets-bakes.pending',header)
        server=(ROOT/'assignment-client/src/assets/AssetServer.cpp').read_text()
        declaration=(ROOT/'assignment-client/src/assets/AssetServer.h').read_text()
        self.assertIn('QPointer<NodeList> _e2eOriginalNode',declaration)
        self.assertEqual(2,server.count('DependencyManager::get<NodeList>().data()!=_e2eOriginalNode.data()'))
        self.assertNotIn('nodeIdentity',server)
        self.assertNotIn('return left.st_ino==right.st_ino',header)


if __name__=='__main__':unittest.main()
