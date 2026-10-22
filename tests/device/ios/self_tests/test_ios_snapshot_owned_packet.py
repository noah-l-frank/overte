"""Actual private originals and recovery across modeled HTTP/AFC/native seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import feature_observation,snapshot_owned_files as source
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket,qualified
from ios.self_tests.test_ios_snapshot_owned_files import Owned,RUN
from ios.self_tests.test_ios_feature_observation import Native as Transport
from self_tests.test_native_feature_observation import Boundary


class SnapshotOwnedPackets(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.model=Owned(self.root);self.model.admit();self.transport=Transport();self.feature=self.transport.observer();self.diag=Boundary()
        def producer(value):
            def clocks(node):
                if type(node) is dict:
                    for key,item in node.items():
                        if key.endswith('EpochMs'):node[key]=self.model.now
                        else:clocks(item)
                elif type(node) is list:
                    for item in node:clocks(item)
            clocks(value);value['processId']=42
        self.diag.mutate=producer;self.lost=False;self.commands=[]
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();self.addCleanup(actual.stop)
        self.transport.execute=self.execute;self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=0,targetFingerprint='c'*64)
    def post(self,request,timeout):
        q=self.transport.fixture.set_client_command(json.loads(request.data));self.commands.append(q);self.transport.echo=json.dumps(q).encode()
        self.transport.value=json.dumps(self.model.read(q),indent=1)+'\n' # Exact original whitespace survives.
        if self.lost:raise NativeUIError('Native source ran but HTTP echo was lost')
        return self.transport
    def execute(self,session,operation,arguments):
        self.assertEqual('mobile: pullFile',operation);self.assertTrue(arguments['remotePath'].endswith('/'+source.FILE))
        return base64.b64encode(self.transport.value.encode()).decode()
    def native(self):
        return NativeFeatureObservation(self.diag.send,self.diag.original,lambda:self.model.now,self.diag.guard,42,ios=True,
            monotonic=lambda:(self.model.now-10000)/1000,sleep=self.diag.sleep)
    def owner(self,index=1):
        return SnapshotOwnedPacket(PrivateFeatureState(self.root/('ios-snapshot-primary-native-owned-'+format(index,'04d')+'.json')),
            self.lock,self.binding,RUN,'primary',index,self.feature,self.native(),lambda:True,
            epoch_ms=lambda:self.model.now,monotonic=lambda:(self.model.now-10000)/1000)
    def history(self,index=1):
        store=PrivateFeatureState(self.root/('ios-snapshot-primary-native-owned-'+format(index,'04d')+'.json'))
        return SnapshotOwnedPacket.history(store,self.lock,self.binding,RUN,'primary',index)
    def captured(self):
        owner=self.owner();owner.reserve();owner.send();return owner,owner.retain()

    def test_actual_query_is_durable_before_native_send_and_preserves_raw_whitespace(self):
        with self.lock.held():
            owner=self.owner();q=owner.reserve();actual=self.post
            def post(request,timeout):
                retained=self.owner();self.assertEqual('issued',retained.state['phase']);self.assertEqual(q,retained.state['query'])
                return actual(request,timeout)
            with patch.object(feature_observation,'post_request',post):owner.send()
            frame=owner.retain();self.assertEqual(self.transport.value,frame['raw']);self.assertTrue(frame['raw'].endswith('\n'))
            qualified(frame,42);self.assertEqual(frame,self.history().historical());self.assertEqual(1,len(self.commands))
            with self.assertRaises(NativeUIError):owner.send()

    def test_lost_http_return_recovers_same_original_without_another_source_query(self):
        with self.lock.held():
            owner=self.owner();owner.reserve();self.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            frame=self.owner().retain();qualified(frame,42);self.assertEqual(1,len(self.commands))
            self.assertEqual(self.transport.value,frame['raw'])

    def test_late_original_is_retained_but_never_retimed_into_fresh_admission(self):
        with self.lock.held():
            owner=self.owner();owner.reserve();owner.send();actual_raw=self.transport.value
            self.model.now+=2000;frame=self.owner().retain();self.assertEqual(actual_raw,frame['raw'])
            self.assertEqual(2002,frame['acquisition']['hostAfterEpochMs']-frame['acquisition']['hostBeforeEpochMs'])
            with self.assertRaises(NativeUIError):qualified(frame,42)
            self.assertEqual(frame,self.history().historical());self.assertEqual(1,len(self.commands))

    def test_complete_opened_original_is_adopted_without_reading_native_or_rewriting_inode(self):
        with self.lock.held():
            owner=self.owner();owner.reserve();owner.send()
            fsync=os.fsync
            def lost(descriptor):
                if 'snapshot-native-owned-frame-' in os.readlink('/proc/self/fd/'+str(descriptor)):
                    raise OSError('Lost completed original frame flush')
                return fsync(descriptor)
            with patch('adapters.original_frame_store.os.fsync',side_effect=lost),self.assertRaises(OSError):owner.retain()
            again=self.owner();ref=deepcopy(again.state['storage']);self.assertEqual('opened',ref['phase'])
            path=again.files().path(ref);before=path.stat();raw=path.read_bytes()
            def forbidden(*_a,**_k):raise AssertionError('Repeated native/AFC call')
            again.feature.original=again.native.read=forbidden;frame=again.retain()
            self.feature.guard=forbidden
            self.assertEqual(before,path.stat());self.assertEqual(raw,path.read_bytes());self.assertEqual(frame,self.history().historical())
            self.assertEqual(1,len(self.commands))

    def test_partial_opened_or_unrecorded_original_is_never_rewritten_or_readopted(self):
        for phase in ('planned','opened'):
            with self.subTest(phase=phase),self.lock.held():
                index=1 if phase=='planned' else 2;owner=self.owner(index);owner.reserve();owner.send();actual=owner.storage
                def lost(kind,ref):
                    actual(kind,ref)
                    if ref['phase']==phase:raise OSError('Interrupted original intent')
                owner.storage=lost
                with self.assertRaises(OSError):owner.retain()
                again=self.owner(index);ref=again.state['storage'];path=again.files().path(ref)
                if phase=='planned':self.assertFalse(path.exists())
                else:self.assertEqual(b'',path.read_bytes())
                with self.assertRaises(NativeUIError):again.retain()
                if phase=='planned':self.assertFalse(path.exists())
                else:self.assertEqual(b'',path.read_bytes())

    def test_missing_wrong_nonce_source_birth_or_changed_original_fails_closed(self):
        with self.lock.held():
            owner,frame=self.captured();value=deepcopy(frame)
            for fault in ('nonce','pid','span-birth','raw-rewrite','native-end'):
                value=deepcopy(frame)
                if fault=='nonce':value['query']['commandId']='ios-'+'f'*32
                elif fault=='pid':value['packet']['processId']=43;value['raw']=json.dumps(value['packet'])
                elif fault=='span-birth':value['acquisition']['nativeAfter']['instance']='f'*32
                elif fault=='raw-rewrite':value['raw']='{}'
                else:value['packet']['clockAfter']['epochMs']+=1;value['raw']=json.dumps(value['packet'])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):qualified(value,42)
            ref=owner.state['storage'];path=owner.files().path(ref);path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):self.owner()

    def test_slow_issued_journal_blocks_native_query_and_saved_history_needs_no_sdk(self):
        with self.lock.held():
            owner=self.owner();owner.reserve();save=owner.save
            def slow():
                save()
                if owner.state['phase']=='issued':self.model.now+=2000
            owner.save=slow
            with self.assertRaises(NativeUIError):owner.send()
            self.assertEqual([],self.commands);self.assertEqual('issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):self.owner().send()


if __name__=='__main__':unittest.main()
