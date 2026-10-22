"""Actual immutable byte originals and HTTP/AFC, with native file IO modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,snapshot_chunks as chunks
from ios.adapters.snapshot_chunk_owner import SnapshotChunk
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.self_tests import test_ios_snapshot_manifest as fixture


class SnapshotChunkOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.SnapshotManifestTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.prefix='parity-'+fixture.RUN[:16]+'-still-png';self.path=self.f.root/(self.prefix+'-snap_1700000000000_1.png')
        self.path.write_bytes(bytes(range(256))*5000);self.path.chmod(0o600);self.lost=False
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();self.addCleanup(actual.stop)
    def post(self,request,timeout):
        native=self.f.files;query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(query)
        native.echo=json.dumps(query).encode();metadata=self.path.stat() if self.path.exists() else None
        raw=self.path.read_bytes() if metadata is not None else b''
        revision=hashlib.sha256(str((metadata.st_dev,metadata.st_ino,metadata.st_size,metadata.st_mtime_ns,metadata.st_ctime_ns)).encode()).hexdigest() if metadata is not None else None
        row=dict(name=self.path.name,size=len(raw),revision=revision,sha256=hashlib.sha256(raw).hexdigest())
        native.value=dict(schemaVersion=query['schemaVersion'],commandId=query['commandId'],operation=query['operation'],prefix=query['prefix'],
            processId=42,sampleEpochMs=getattr(self,'epoch_ms',lambda:20000)(),ok=True)
        if query['operation']=='list':native.value['files']=[row] if metadata is not None else []
        else:
            self.assertEqual(revision,query['revision']);offset=query['offset'];part=raw[offset:offset+chunks.CHUNK_BYTES]
            native.value['file']=dict(name=row['name'],revision=revision,size=len(raw),offset=offset,eof=offset+len(part)==len(raw),
                data=base64.b64encode(part).decode())
            if self.lost:raise NativeUIError('Actual modeled read completed; original caller return lost')
        return native
    def manifest(self):
        owner=self.f.owner();owner.reserve('still-png');owner.send(20000);owner.recover();return owner
    def owner(self,index=1):
        return SnapshotChunk(PrivateFeatureState(self.f.root/('ios-snapshot-primary-chunk-'+format(index,'04d')+'.json')),
            self.f.lock,self.f.binding,fixture.RUN,'primary',index,self.f.feature,self.f.new_clock(),lambda:True)
    def issued(self):
        manifest=self.manifest();owner=self.owner();owner.reserve_original(manifest,self.path.name,0);owner.send(20000)
        return manifest,owner

    def test_actual_large_original_chunks_have_durable_queries_native_clocks_and_private_originals(self):
        with self.f.lock.held():
            manifest=self.manifest();frames=[]
            for index,offset in enumerate(range(0,self.path.stat().st_size,chunks.CHUNK_BYTES),1):
                owner=self.owner(index);query=owner.reserve_original(manifest,self.path.name,offset)
                self.assertEqual(query,self.owner(index).state['query']);owner.send(20000);frame=owner.recover();frames.append(frame)
                path=owner.files().path(owner.files().expand(owner.state['proof']));self.assertLess(path.stat().st_size,1048576)
                self.assertEqual(0o600,path.stat().st_mode&0o777);self.assertEqual(frame,self.owner(index).historical())
            row=manifest.historical()['packet']['files'][0]
            self.assertEqual(self.path.read_bytes(),chunks.original_bytes(row,self.prefix,[dict(query=f['query'],packet=f['packet']) for f in frames],42))
            self.assertEqual(4,len(self.f.files.commands))

    def test_lost_native_result_is_resolved_from_original_afc_without_resending_chunk(self):
        with self.f.lock.held():
            manifest=self.manifest();owner=self.owner();owner.reserve_original(manifest,self.path.name,0);self.lost=True
            with self.assertRaises(NativeUIError):owner.send(20000)
            restored=self.owner()
            with self.assertRaises(NativeUIError):restored.send(20000)
            restored.recover();self.assertEqual(2,len(self.f.files.commands))
            self.assertEqual('saved',self.owner().state['phase'])

    def test_lost_saved_original_adopts_same_file_without_clock_afc_or_rewrite(self):
        with self.f.lock.held():
            _manifest,owner=self.issued();storage=owner.storage
            def lost(kind,value):
                storage(kind,value)
                if value['phase']=='saved':raise OSError('Original saved file result lost')
            owner.storage=lost
            with self.assertRaises(OSError):owner.recover()
            restored=self.owner();path=restored.files().path(restored.state['storage']);before=path.stat()
            def forbidden(*_args,**_kwargs):raise AssertionError('Original adoption resampled transport')
            self.f.feature.original=restored.clock.finish=forbidden;restored.recover()
            self.assertEqual((before.st_ino,before.st_mtime_ns),(path.stat().st_ino,path.stat().st_mtime_ns));self.assertEqual(2,len(self.f.files.commands))

    def test_interrupted_opened_original_is_not_overwritten_or_replayed(self):
        with self.f.lock.held():
            _manifest,owner=self.issued();storage=owner.storage
            def interrupted(kind,value):
                storage(kind,value)
                if value['phase']=='opened':raise OSError('Original interrupted at open')
            owner.storage=interrupted
            with self.assertRaises(OSError):owner.recover()
            restored=self.owner();path=restored.files().path(restored.state['storage']);inode=path.stat().st_ino
            with self.assertRaises(NativeUIError):restored.recover()
            with self.assertRaises(NativeUIError):restored.send(20000)
            self.assertEqual(b'',path.read_bytes());self.assertEqual(inode,path.stat().st_ino)

    def test_missing_original_row_unaligned_or_past_eof_offsets_never_reserve_or_send(self):
        with self.f.lock.held():
            manifest=self.manifest()
            for name,offset in (('foreign.png',0),(self.path.name,1),(self.path.name,self.path.stat().st_size),(self.path.name,True)):
                with self.subTest(name=name,offset=offset),self.assertRaises(NativeUIError):self.owner().reserve_original(manifest,name,offset)
            self.assertEqual(1,len(self.f.files.commands));self.assertIsNone(self.owner().state)

    def test_historical_chunk_reader_has_no_sdk_and_actual_inode_cannot_be_replaced(self):
        with self.f.lock.held():
            _manifest,owner=self.issued();frame=owner.recover()
            reader=SnapshotChunk.history(owner.store,self.f.lock,self.f.binding,fixture.RUN,'primary',1)
            self.assertIsNone(reader.feature);self.assertIsNone(reader.clock);self.assertEqual(frame,reader.historical())
            with self.assertRaises(NativeUIError):reader.recover()
            path=reader.files().path(reader.files().expand(reader.state['proof']));path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):reader.historical()

    def test_manifest_and_chunk_namespaces_and_query_versions_cannot_be_relabelled(self):
        with self.f.lock.held():
            manifest,owner=self.issued();owner.recover()
            with self.assertRaises(NativeUIError):SnapshotManifest.history(owner.store,self.f.lock,self.f.binding,fixture.RUN,'primary',1)
            with self.assertRaises(NativeUIError):owner.reserve('still-png')
            changed=deepcopy(owner.previous);changed['iosSnapshotManifestOwnerVersion']=changed.pop('iosSnapshotChunkOwnerVersion')
            with self.assertRaises(NativeUIError):owner.load(changed)
            self.assertEqual('saved',manifest.state['phase']);self.assertEqual(2,len(self.f.files.commands))


if __name__=='__main__':unittest.main()
