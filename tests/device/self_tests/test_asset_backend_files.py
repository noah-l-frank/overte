"""Private backend collector with real files/inodes and modeled native producer.

The process tests explicitly model /proc contents in temporary directories.
No child, service, compiler, native task, oven or device is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters import asset_backend_files as files
from adapters.normal_ui import NativeUIError
from fixture.asset_backend_process import LinuxAssetsBackendProcess
from test_asset_backend_source import BackendSourceTests,kernel,stamp


class ProcessModel:
    """Declared PID/role/process boundary; actual collector files are real."""
    def __init__(self,backend):
        self.pid=123;self.path=backend.export;self.owner_sha256='b'*64;self.sha256='f'*64;self.process_identity='123:11:'+backend.server;self.root=self.path.stat().st_ino;self.alive=True
    def guard(self):
        if not self.alive or self.path.lstat().st_ino!=self.root:raise NativeUIError('Modeled process unavailable')
        return True


class BackendFilesTests(unittest.TestCase):
    def setUp(self):
        self.backend=BackendSourceTests();self.backend.setUp();self.addCleanup(self.backend.doCleanups);self.b=self.backend
        self.admission,self.query,_=self.b.original();self.run=self.query['runId'];self.process=ProcessModel(self.b)
        self.b.record(self.b.export/files.ADMISSION,files.encode(self.admission));self.journal=self.b.root/'journal';self.journal.mkdir(mode=0o700);self.clock=1000
        self.transport=None;self.published=[];self.open()
    def now(self):self.clock+=1;return self.clock
    def open(self):
        self.transport=files.AssetsBackendFiles(self.process,self.journal,self.run,epoch_ms=self.now,monotonic_ms=self.now);self.addCleanup(self.transport.detach);return self.transport
    def command(self,index=1):return dict(self.query,commandId='assets-'+f'{index:032x}',ticket=f'{index:032x}')
    def write(self,name,raw):
        fd=os.open(self.b.export/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:os.write(fd,raw);os.fsync(fd)
        finally:os.close(fd)
        return dict(file=name,identity=kernel((self.b.export/name).stat()),sha256=hashlib.sha256(raw).hexdigest())
    def publish(self,*,saved=True):
        query=files.source.object_bytes((self.b.export/files.CURRENT).read_bytes(),4096);self.assertNotIn(query['commandId'],self.published);self.published.append(query['commandId'])
        self.write('asset-backend-query-'+query['commandId']+'.json',files.encode(query));before=stamp(self.b.work.t);source=self.b.dataset();self.b.work.t+=1
        packet=dict(assetBackendObservationVersion=1,requestId=query['commandId'],instance=self.admission['instance'],sequence=len(self.published),runId=query['runId'],ticket=query['ticket'],processId=123,
            ownerSha256='b'*64,serverId=self.b.server,domainId=self.b.domain,admissionSha256=self.transport.admission_sha,clockDomain='asset-server-native',clockBefore=before,clockAfter=stamp(self.b.work.t),source=source)
        original=self.write('asset-backend-original-'+query['commandId']+'.json',files.encode(packet))
        receipt=dict(assetBackendSavedVersion=1,instance=packet['instance'],requestId=query['commandId'],processId=123,admissionSha256=packet['admissionSha256'],original=original)
        if saved:self.write('asset-backend-saved-'+query['commandId']+'.json',files.encode(receipt))
        return packet,receipt
    def test_two_actual_queries_reopen_originals_and_never_retime_historical_results(self):
        first=self.command();self.transport.send(first);self.assertIsNone(self.transport.poll());packet,_=self.publish();self.assertEqual(packet,self.transport.poll());self.assertIsNone(self.transport.poll())
        count=len(list(self.journal.iterdir()));self.assertEqual(packet,self.transport.historical());self.assertEqual(count,len(list(self.journal.iterdir())))
        self.transport.detach();self.open();self.assertEqual(packet,self.transport.historical());self.transport.send(self.command(2));next_packet,_=self.publish();self.assertEqual(next_packet,self.transport.poll());self.assertEqual(2,len(self.published))
    def test_lost_postpublication_ack_recovers_original_without_resending_or_new_query(self):
        original=self.transport._append
        def lost(event):
            if event['tag']=='published':raise OSError('modeled lost publication acknowledgement')
            return original(event)
        with patch.object(self.transport,'_append',side_effect=lost),self.assertRaises(OSError):self.transport.send(self.command())
        packet,_=self.publish();self.transport.detach();self.open()
        with self.assertRaises(NativeUIError):self.transport.send(self.command(2))
        self.assertEqual(packet,self.transport.poll());self.assertEqual(1,len(self.published));self.assertIsNone(self.transport.poll())
    def test_failed_prepublication_write_remains_unresolved_and_is_never_retried(self):
        original=self.transport._write
        def fail(root,name,raw):
            if name.startswith('asset-backend-publish-'):raise OSError('modeled denied publication')
            return original(root,name,raw)
        with patch.object(self.transport,'_write',side_effect=fail),self.assertRaises(OSError):self.transport.send(self.command())
        self.assertFalse((self.b.export/files.CURRENT).exists());self.transport.detach();self.open();self.assertIsNone(self.transport.poll())
        with self.assertRaises(NativeUIError):self.transport.send(self.command())
        self.assertEqual([],self.published)
    def test_missing_saved_marker_does_not_adopt_partial_native_original(self):
        self.transport.send(self.command());packet,receipt=self.publish(saved=False);self.assertIsNone(self.transport.poll());self.assertIsNone(self.transport.historical())
        self.write('asset-backend-saved-'+packet['requestId']+'.json',files.encode(receipt));self.assertEqual(packet,self.transport.poll())
    def test_replaced_original_inode_fails_saved_join_even_when_bytes_are_identical(self):
        self.transport.send(self.command());packet,_=self.publish();name='asset-backend-original-'+packet['requestId']+'.json';raw=(self.b.export/name).read_bytes()
        (self.b.export/name).rename(self.b.export/'retained-old-original');self.write(name,raw)
        with self.assertRaises(NativeUIError):self.transport.poll()
    def test_replaced_query_slot_or_recorded_original_cannot_be_adopted(self):
        self.transport.send(self.command());packet,_=self.publish();self.transport.poll();raw=(self.b.export/files.CURRENT).read_bytes();(self.b.export/files.CURRENT).rename(self.b.export/'old-slot');self.write(files.CURRENT,raw)
        with self.assertRaises(NativeUIError):self.transport.send(self.command(2))
        name='asset-backend-original-'+packet['requestId']+'.json';raw=(self.b.export/name).read_bytes();(self.b.export/name).rename(self.b.export/'old-original');self.write(name,raw)
        with self.assertRaises(NativeUIError):self.transport.historical()
    def test_host_journal_alteration_and_process_loss_block_every_new_delivery(self):
        self.process.alive=False
        with self.assertRaises(NativeUIError):self.transport.send(self.command())
        self.process.alive=True;record=next(self.journal.iterdir());record.chmod(0o644)
        with self.assertRaises(NativeUIError):self.transport.send(self.command())
        self.assertFalse((self.b.export/files.CURRENT).exists())
    def test_host_clock_rollback_after_pending_poll_is_not_erased_by_history_replay(self):
        self.transport.send(self.command());self.assertIsNone(self.transport.poll());self.clock=1
        with self.assertRaises(NativeUIError):self.transport.poll()


class KernelProcessBoundary(LinuxAssetsBackendProcess):
    """Temporary /proc model override; production uses the actual fixed /proc."""
    def _process_path(self,leaf=''):return self.proc/leaf


class BackendProcessTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name);self.root.chmod(0o700)
        self.source=self.root/'source';self.source.mkdir(mode=0o700);self.config=self.root/'config';self.config.mkdir(mode=0o700);self.proc=self.root/'proc';self.proc.mkdir(mode=0o700)
        (self.proc/'exe').write_bytes(b'declared executable image');self.sha=hashlib.sha256((self.proc/'exe').read_bytes()).hexdigest();self.token='a'*64;self.owner=hashlib.sha256(self.token.encode()).hexdigest();self.owned=True
        self.start='21';self.role=b'-t\0' + b'3';self.environment=dict(OVERTE_E2E_FIXTURE_PROCESS_OWNER=self.token,XDG_CONFIG_HOME=str(self.config),OVERTE_E2E_ASSETS_SOURCE_ROOT=str(self.source));self.sync()
    def sync(self):
        (self.proc/'stat').write_text('123 (odd comm)) S '+' '.join(['1']*18+[self.start])+'\n');(self.proc/'cmdline').write_bytes(b'assignment-client\0'+self.role+b'\0')
        (self.proc/'environ').write_bytes(b'\0'.join(key.encode()+b'='+value.encode() for key,value in self.environment.items())+b'\0')
    def process(self,**changes):
        result=KernelProcessBoundary.__new__(KernelProcessBoundary);result.proc=self.proc
        arguments=dict(pid=123,directory=self.source,config_home=self.config,executable_sha256=self.sha,owner_sha256=self.owner,owned=lambda _pid:self.owned);arguments.update(changes)
        result.__init__(**arguments);self.addCleanup(result.close);return result
    def test_actual_file_hash_identity_role_owner_and_start_are_bound(self):
        process=self.process();self.assertTrue(process.guard());self.start='22';self.sync()
        with self.assertRaises(NativeUIError):process.guard()
    def test_foreign_owner_role_duplicate_role_and_source_environment_are_rejected(self):
        for role in (b'-t\0' + b'4',b'-t\0' + b'3\0-t4',b'-t\0' + b'3\0--type=4',b'-t\0' + b'3\0--testScript'):
            self.role=role;self.sync()
            with self.subTest(role=role),self.assertRaises(NativeUIError):self.process()
        self.role=b'-t\0' + b'3';self.environment['OVERTE_E2E_ASSETS_SOURCE_ROOT']=str(self.config);self.sync()
        with self.assertRaises(NativeUIError):self.process()
    def test_executable_inode_or_config_root_replacement_loses_binding(self):
        process=self.process();(self.proc/'exe').rename(self.proc/'old-exe');(self.proc/'exe').write_bytes(b'declared executable image')
        with self.assertRaises(NativeUIError):process.guard()
        process.close();process=self.process();self.config.rename(self.root/'old-config');self.config.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):process.guard()
