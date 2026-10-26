"""Actual source/archive files and original byte chunks; native/OS modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random
import tempfile
import unittest
from PIL import Image
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_share_original as share,snapshot_share_chunks as source
from ios.adapters.snapshot_share_archive_runtime import IOSSnapshotShareArchiveRuntime
from ios.self_tests.snapshot_photos_domain import revision
from ios.self_tests.snapshot_share_admission_domain import ShareAdmissionDomain
from ios.self_tests.test_ios_snapshot_share_original import received,imported
from ios.self_tests.snapshot_companion_domain import RUN


def root_identity(path):
    value=path.stat();fields=value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid
    return hashlib.sha256(':'.join(map(str,fields)).encode()).hexdigest()


class SnapshotShareChunkTests(unittest.TestCase):
    def original(self,large=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        group=root/'group';archive=root/'archive';group.mkdir(mode=0o700);archive.mkdir(mode=0o700)
        _native,_operation,_exports,record,raw=received()
        if large:
            stream=BytesIO();Image.frombytes('RGB',(512,512),random.Random(42).randbytes(512*512*3)).save(stream,format='PNG');raw=stream.getvalue()
        path=group/'original.bytes';path.write_bytes(raw);path.chmod(0o600)
        record.update(iosSnapshotShareOriginalVersion=2,byteCount=len(raw),sha256=hashlib.sha256(raw).hexdigest(),artifactRevision=revision(path),rootIdentity=root_identity(group))
        transfer,_metadata,finished=imported(record,raw);metadata=json.dumps(finished,indent=1).encode();copy=archive/'original.bytes';copy.write_bytes(path.read_bytes());copy.chmod(0o600)
        transfer.update(iosSnapshotShareImportVersion=2,originalMetadataSha256=hashlib.sha256(metadata).hexdigest(),basename=record['basename'],artifactRevision=revision(copy),
            archiveRootIdentity=root_identity(archive),sourceArtifactRevision=record['artifactRevision'],groupRootIdentity=record['rootIdentity'])
        return transfer,metadata,raw,path,copy
    def parts(self,transfer,path):
        output=[]
        for index,offset in enumerate(range(0,transfer['byteCount'],source.CHUNK_BYTES)):
            before=path.stat()
            with path.open('rb') as file:file.seek(offset);raw=file.read(source.CHUNK_BYTES)
            after=path.stat();self.assertEqual((before.st_dev,before.st_ino,before.st_size),(after.st_dev,after.st_ino,after.st_size))
            output.append(dict(snapshotShareChunkVersion=1,nonce='ios-'+format(index+1,'032x'),runId=transfer['runId'],instance=transfer['instance'],processId=85,
                basename=transfer['basename'],clockDomain='native-share-archive',clockBefore=dict(epochMs=200020+index*2,monotonicMs=27+index*2),
                clockAfter=dict(epochMs=200021+index*2,monotonicMs=28+index*2),revision=revision(path),byteCount=transfer['byteCount'],sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                offset=offset,eof=offset+len(raw)==transfer['byteCount'],readerClosed=True,data=base64.b64encode(raw).decode()))
        return output
    def scope(self):return dict(pid=85,bundle_id='org.example.snapshot',receiver_bundle_id='org.example.snapshot.receiver')

    def test_initial_source_and_archive_anchors_keep_exact_bytes_and_separate_original_clocks(self):
        transfer,metadata,raw,_path,copy=self.original(large=True);original=share.imported_original(transfer,metadata,raw,**self.scope())
        parts=self.parts(transfer,copy);self.assertEqual(2,len(parts));self.assertEqual(raw,source.original_bytes(parts,transfer,metadata,**self.scope()))
        self.assertEqual(raw,copy.read_bytes());self.assertNotEqual(transfer['clockAfter']['monotonicMs'],original['createdClock']['monotonicMs'])
        self.assertEqual('PNG',Image.open(BytesIO(raw)).format)

    def test_literal_one_and_two_grammars_remain_exact_and_old_import_cannot_authorize_chunks(self):
        transfer,metadata,raw,_path,copy=self.original();original=json.loads(metadata)
        _n,_o,_e,old,_raw=received();old_transfer,old_metadata,_f=imported(old,_raw)
        share.original(old);share.imported_original(old_transfer,old_metadata,_raw,**self.scope())
        for value in (dict(old,artifactRevision='0'*64),{key:item for key,item in original.items() if key!='artifactRevision'},dict(original,iosSnapshotShareOriginalVersion=True)):
            with self.assertRaises(NativeUIError):share.original(value)
        for value in (dict(old_transfer,artifactRevision='0'*64),{key:item for key,item in transfer.items() if key!='sourceArtifactRevision'}):
            with self.assertRaises(NativeUIError):share.imported_original(value,metadata,raw,**self.scope())
        with self.assertRaises(NativeUIError):source.original_bytes(self.parts(transfer,copy),old_transfer,old_metadata,**self.scope())
        changed=deepcopy(original);changed['rootIdentity']='0'*64
        with self.assertRaises(NativeUIError):share.original(changed,original)
        changed=deepcopy(original);changed['artifactRevision']='0'*64
        with self.assertRaises(NativeUIError):share.original(changed,original)

    def test_changed_source_or_archive_identity_same_bytes_cannot_replace_original_anchors(self):
        transfer,metadata,raw,path,copy=self.original()
        replacement=copy.with_name('replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(copy)
        self.assertEqual(raw,copy.read_bytes())
        with self.assertRaises(NativeUIError):source.original_bytes(self.parts(transfer,copy),transfer,metadata,**self.scope())
        for key in ('sourceArtifactRevision','groupRootIdentity'):
            changed=deepcopy(transfer);changed[key]='0'*64
            with self.subTest(key=key),self.assertRaises(NativeUIError):share.imported_original(changed,metadata,raw,**self.scope())

    def test_chunks_reject_unclosed_readers_reused_nonces_changed_offsets_bytes_and_clocks(self):
        transfer,metadata,_raw,_path,copy=self.original(large=True);parts=self.parts(transfer,copy)
        for fault in ('closed','nonce','offset','bytes','eof','clock','process','revision'):
            changed=deepcopy(parts)
            if fault=='closed':changed[0]['readerClosed']=False
            elif fault=='nonce':changed[1]['nonce']=changed[0]['nonce']
            elif fault=='offset':changed[0]['offset']=source.CHUNK_BYTES
            elif fault=='bytes':changed[0]['data']=base64.b64encode(b'changed').decode()
            elif fault=='eof':changed[0]['eof']=True
            elif fault=='clock':changed[0]['clockAfter']['monotonicMs']+=500
            elif fault=='process':changed[0]['processId']=42
            else:changed[0]['revision']='0'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original_bytes(changed,transfer,metadata,**self.scope())

    def test_real_admission_bound_archive_runtime_reads_closed_AFC_paths_and_rejects_unknown_scope(self):
        d=ShareAdmissionDomain(self)
        with d.owner() as owner:
            owner.admit('d'*32);store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        transfer,metadata,_raw,_path,_copy=self.original();output=d.documents/('snapshot-share-'+RUN);output.mkdir();(output/'original-extension.json').write_bytes(metadata)
        actual=d.execute
        def execute(session,operation,query):
            if operation=='mobile: pullFile' and query['remotePath'].endswith('/original-extension.json'):
                d.sdk.append((session,operation,deepcopy(query)));return base64.b64encode((output/'original-extension.json').read_bytes()).decode()
            return actual(session,operation,query)
        d.execute=execute
        with lock.held():
            runtime=IOSSnapshotShareArchiveRuntime(d,d.session,d.target,d.scope,d.ipa,lambda:True,admission_store=store,lock=lock,run=RUN,fixture_url=url,epoch_ms=d.epoch,monotonic=d.mono,sleep=lambda _:None)
            self.assertEqual(metadata,runtime.original_path('snapshot-share-'+RUN+'/original-extension.json',262144));before=len(d.sdk)
            for name,limit in (('../original.bytes',100),('snapshot-share-'+RUN+'/original.bytes',100),('snapshot-share-chunk.json',True),('snapshot-share-'+RUN+'/import-original.json',720896)):
                with self.subTest(name=name),self.assertRaises(NativeUIError):runtime.original_path(name,limit)
            self.assertEqual(before,len(d.sdk));d.source='0'*32
            with self.assertRaises(NativeUIError):runtime.original_path('snapshot-share-'+RUN+'/original-extension.json',262144)


if __name__=='__main__':unittest.main()
