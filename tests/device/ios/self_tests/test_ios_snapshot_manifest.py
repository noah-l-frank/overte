"""Actual private ownership and HTTP/AFC paths; native filesystem is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import feature_observation
from ios.adapters.snapshot_manifest import SnapshotManifest,absent,manifest,FILE
from ios.self_tests.test_ios_feature_observation import Native as Transport
from self_tests.test_native_feature_observation import Boundary

RUN='a'*32


class Files(Transport):
    lost=False
    def post(self,request,timeout):
        query=self.fixture.set_client_command(json.loads(request.data));self.commands.append(query)
        self.echo=json.dumps(query).encode();self.value=dict(schemaVersion=1,commandId=query['commandId'],operation='list',
            prefix=query['prefix'],processId=42,sampleEpochMs=20000,ok=True,files=[])
        if self.lost:raise NativeUIError('Actual modeled native list returned; HTTP result lost')
        return self
    def execute(self,session,operation,values):
        assert operation=='mobile: pullFile'
        assert values==dict(remotePath='@org.example.client:documents/owned-results/'+FILE)
        self.reads.append(values);return base64.b64encode(json.dumps(self.value).encode()).decode()


class SnapshotManifestTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.root=Path(folder.name);self.root.chmod(0o700)
        self.files=Files();self.feature=self.files.observer();self.native=Boundary()
        self.native.mutate=lambda value:value.update(processId=42)
        self.clock=self.new_clock()
        self.store=PrivateFeatureState(self.root/'ios-snapshot-primary-manifest-0001.json')
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.good=True
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=0,targetFingerprint='c'*64)
        patched=patch.object(feature_observation,'post_request',self.files.post);patched.start();self.addCleanup(patched.stop)
    def owner(self):return SnapshotManifest(self.store,self.lock,self.binding,RUN,'primary',1,self.feature,self.clock,lambda:self.good)
    def new_clock(self):
        reader=NativeFeatureObservation(self.native.send,self.native.original,lambda:20000,self.native.guard,42,ios=True,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        return NativeClockAcquisition(reader,epoch_ms=lambda:20000,monotonic=lambda:self.native.clock)
    def completed(self):
        owner=self.owner();owner.reserve('still-png');owner.send(20000);frame=owner.recover();return owner,frame

    def test_durable_query_before_actual_post_and_independent_native_clock_bracket(self):
        with self.lock.held():
            owner=self.owner();query=owner.reserve('still-png');actual=self.files.post
            def boundary(request,timeout):
                retained=self.owner();self.assertEqual('issued',retained.state['phase']);self.assertEqual(query,retained.state['query'])
                return actual(request,timeout)
            with patch.object(feature_observation,'post_request',boundary):owner.send(20000)
            frame=owner.recover();proof=absent(frame,42,RUN,'still-png')
            self.assertTrue(proof['quietWindowRequired']);self.assertEqual(self.files.value,frame['packet'])
            self.assertNotEqual(frame['clockJoin']['nativeBefore']['requestId'],frame['clockJoin']['nativeAfter']['requestId'])
            self.assertEqual(1,len(self.files.commands));self.assertEqual(frame,self.owner().historical())
            with self.assertRaises(NativeUIError):owner.send(20000)

    def test_unknown_http_return_recovers_only_actual_original_without_reissuing_query(self):
        with self.lock.held():
            owner=self.owner();owner.reserve('still-png');self.files.lost=True
            with self.assertRaises(NativeUIError):owner.send(20000)
            restored=self.owner();self.assertEqual('issued',restored.state['phase'])
            with self.assertRaises(NativeUIError):restored.send(20000)
            restored.recover();self.assertEqual(1,len(self.files.commands))

    def test_wrong_nonce_pid_prefix_error_and_old_clock_never_become_empty_manifest(self):
        for fault in ('nonce','pid','prefix','error','clock','wrong-run'):
            with self.subTest(fault=fault),self.lock.held():
                # Each rejected query has no accepted original file.
                self.store=PrivateFeatureState(self.root/'ios-snapshot-primary-manifest-0001.json')
                if self.store.path.exists():self.store.path.unlink()
                self.clock=self.new_clock()
                owner=self.owner();owner.reserve('still-png');owner.send(20000)
                if fault=='nonce':self.files.value['commandId']='ios-'+'f'*32
                elif fault=='pid':self.files.value['processId']=43
                elif fault=='prefix':self.files.value['prefix']='parity-'+'b'*16+'-still-png'
                elif fault=='error':self.files.value['ok']=False
                elif fault=='clock':self.files.value['sampleEpochMs']=19999
                else:self.files.value['prefix']='parity-'+'f'*16+'-still-jpg'
                with self.assertRaises(NativeUIError):owner.recover()
                self.assertEqual('issued',self.owner().state['phase'])

    def test_source_manifest_rejects_duplicates_paths_bool_sizes_and_excess_total(self):
        with self.lock.held():
            owner,frame=self.completed();query=frame['query'];name=query['prefix']+'-snap_1700000000000_1.png'
            row=dict(name=name,size=1,revision='b'*64,sha256='c'*64)
            for rows in ([row,row],[dict(row,name='../escape.png')],[dict(row,size=True)],[dict(row,size=268435457)]):
                with self.subTest(rows=rows),self.assertRaises((NativeUIError,ValueError)):manifest(dict(frame['packet'],files=rows),query,42)
            with self.assertRaises(NativeUIError):absent(frame,42,RUN,'animated')

    def test_saved_file_return_loss_adopts_same_inode_without_afc_native_or_rewrite(self):
        with self.lock.held():
            owner=self.owner();owner.reserve('still-png');owner.send(20000);storage=owner.storage
            def lost(kind,value):
                storage(kind,value)
                if value['phase']=='saved':raise OSError('saved original return lost')
            owner.storage=lost
            with self.assertRaises(OSError):owner.recover()
            restored=self.owner();path=restored.files().path(restored.state['storage']);before=path.stat()
            def forbidden(*_args,**_kwargs):raise AssertionError('Saved original reread touched native transport')
            self.feature.original=self.clock.finish=forbidden
            restored.recover();self.assertEqual((before.st_ino,before.st_mtime_ns),(path.stat().st_ino,path.stat().st_mtime_ns))
            self.assertEqual(1,len(self.files.commands))

    def test_empty_opened_original_stays_owned_and_blocks_reissue_or_replacement(self):
        with self.lock.held():
            owner=self.owner();owner.reserve('still-png');owner.send(20000);storage=owner.storage
            def interrupted(kind,value):
                storage(kind,value)
                if value['phase']=='opened':raise OSError('interrupted actual write')
            owner.storage=interrupted
            with self.assertRaises(OSError):owner.recover()
            restored=self.owner();path=restored.files().path(restored.state['storage']);inode=path.stat().st_ino
            with self.assertRaises(NativeUIError):restored.recover()
            with self.assertRaises(NativeUIError):restored.send(20000)
            self.assertEqual(b'',path.read_bytes());self.assertEqual(inode,path.stat().st_ino)

    def test_expired_uncertain_query_and_changed_candidate_guard_cannot_read_or_resend(self):
        with self.lock.held():
            owner=self.owner();owner.reserve('still-png');owner.send(20000);self.native.clock=1.5
            with self.assertRaises(NativeUIError):self.owner().recover()
            self.assertEqual([],self.files.reads);self.good=False
            with self.assertRaises(NativeUIError):owner.recover()
            self.assertEqual(1,len(self.files.commands))

    def test_actual_sdk_process_and_slow_final_guard_block_before_post(self):
        with self.lock.held():
            owner=self.owner();owner.reserve('still-png');self.files.pid=43
            with self.assertRaises(NativeUIError):owner.send(20000)
            self.assertEqual([],self.files.commands);self.assertEqual('reserved',owner.state['phase'])
            self.files.pid=42
            def slow():self.native.clock=1.5;return True
            self.feature.before_send=slow
            with self.assertRaises(NativeUIError):owner.send(20000)
            self.assertEqual([],self.files.commands);self.assertEqual('issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):owner.send(20000)

    def test_historical_original_revalidates_actual_inode_and_bytes_without_native_clocks(self):
        with self.lock.held():
            owner,frame=self.completed();restored=self.owner()
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical read touched SDK')
            self.feature.original=self.clock.finish=forbidden;self.good=False
            history=SnapshotManifest.history(self.store,self.lock,self.binding,RUN,'primary',1)
            self.assertIsNone(history.feature);self.assertIsNone(history.clock)
            self.assertEqual(frame,history.historical())
            with self.assertRaises(NativeUIError):history.recover()
            self.assertEqual(frame,restored.historical());path=restored.files().path(restored.files().expand(restored.state['proof']))
            raw=path.read_bytes();replacement=path.with_name('replacement');replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
            with self.assertRaises(NativeUIError):restored.historical()


if __name__=='__main__':unittest.main()
