"""Exact native-original contracts and actual private namespace isolation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import snapshot_destination as destination,snapshot_photos_source as source
from ios.adapters.snapshot_photos_packets import PhotosSaveSegments,PhotosSaveInputs,PhotosSaveExportsPacket
from ios.adapters.snapshot_source_packet import SnapshotSourceSegments,SnapshotExportsPacket
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.self_tests.snapshot_photos_domain import revision
from ios.self_tests.test_ios_snapshot_destination import completed
from ios.self_tests import test_ios_snapshot_destination as destination_fixture
from ios.self_tests.test_ios_snapshot_inputs import Native,RUN


BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=0,targetFingerprint='c'*64)


class SnapshotPhotosSourceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
    def original(self,raw=None):
        _native,_operation,_exports,value,actual=completed();raw=actual if raw is None else raw
        path=self.root/'original.bytes';path.write_bytes(raw);path.chmod(0o600)
        value.update(iosSnapshotDestinationVersion=2,byteCount=len(raw),sha256=hashlib.sha256(raw).hexdigest(),artifactRevision=revision(path))
        return value,raw
    def chunks(self,original,raw):
        return [dict(snapshotPhotosChunkVersion=1,nonce='ios-'+format(index+1,'032x'),runId=original['runId'],instance=original['instance'],processId=84,
            basename=original['basename'],clockBefore=dict(epochMs=200030+index*2,monotonicMs=37+index*2),clockAfter=dict(epochMs=200031+index*2,monotonicMs=38+index*2),
            revision=original['artifactRevision'],byteCount=len(raw),sha256=original['sha256'],offset=offset,eof=offset+source.CHUNK_BYTES>=len(raw),readerClosed=True,
            data=base64.b64encode(raw[offset:offset+source.CHUNK_BYTES]).decode()) for index,offset in enumerate(range(0,len(raw),source.CHUNK_BYTES))]
    def retirement(self,original):
        value=destination_fixture.SnapshotDestinationTests.deleted(original);raw=json.dumps(value,separators=(',',':')).encode()
        receipt=dict(phase='complete',runId=value['runId'],instance=value['instance'],processId=84,artifactRevision=value['artifactRevision'],
            artifactSha256=value['sha256'],byteCount=value['byteCount'],journalSha256=hashlib.sha256(raw).hexdigest(),
            clockBefore=dict(epochMs=200060,monotonicMs=67),clockAfter=dict(epochMs=200061,monotonicMs=68),
            steps=['original-unlinked','journal-unlinked','run-removed'],readersClosed=True)
        observed=dict(snapshotPhotosRetirementVersion=1,nonce='ios-'+'1'*32,receipt=receipt,clockBefore=dict(epochMs=200062,monotonicMs=69),
            clockAfter=dict(epochMs=200063,monotonicMs=70),runAbsent=True,originalAbsent=True,journalAbsent=True)
        return value,raw,observed

    def test_literal_one_reader_and_literal_two_anchor_keep_distinct_exact_grammars(self):
        _n,_op,_exports,old,_raw=completed();destination.original(old);new,_raw=self.original();destination.original(new)
        for value in (dict(old,artifactRevision='0'*64),{key:item for key,item in new.items() if key!='artifactRevision'},dict(new,iosSnapshotDestinationVersion=True)):
            with self.assertRaises(NativeUIError):destination.original(value)
        changed=deepcopy(new);changed['artifactRevision']='0'*64
        with self.assertRaises(NativeUIError):destination.original(changed,new)
        with self.assertRaises(NativeUIError):source.chunk(self.chunks(new,_raw)[0],'ios-'+format(1,'032x'),0,old,pid=84)

    def test_original_byte_chunks_cross_exact_boundary_without_retiming_or_reencoding(self):
        value,raw=self.original(bytes(range(256))*(source.CHUNK_BYTES//256)+b'final-byte');parts=self.chunks(value,raw)
        self.assertEqual(2,len(parts));self.assertEqual(raw,source.original_bytes(parts,value,84))
        self.assertEqual(source.CHUNK_BYTES,len(base64.b64decode(parts[0]['data'])));self.assertEqual(b'final-byte',base64.b64decode(parts[1]['data']))
        for fault in ('revision','first-offset','repeated-nonce','not-closed','reordered','short-data','different-hash','foreign-clock'):
            changed=deepcopy(parts)
            if fault=='revision':changed[0]['revision']='0'*64
            elif fault=='first-offset':changed[0]['offset']=source.CHUNK_BYTES
            elif fault=='repeated-nonce':changed[1]['nonce']=changed[0]['nonce']
            elif fault=='not-closed':changed[0]['readerClosed']=False
            elif fault=='reordered':changed.reverse()
            elif fault=='short-data':changed[0]['data']=base64.b64encode(b'short').decode()
            elif fault=='different-hash':changed[0]['sha256']='0'*64
            else:changed[0]['clockAfter']['monotonicMs']+=500
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original_bytes(changed,value,84)

    def test_retirement_requires_exact_journal_original_closed_readers_and_full_access_deletion(self):
        original,_raw=self.original();deleted,raw,value=self.retirement(original)
        source.retirement(value,value['nonce'],deleted,raw,pid=84)
        for fault in ('journal-serialization','readers-open','missing-step','absent-ack','limited','asset-present','read-only','empty-queries','revision','boolean-pid'):
            changed=deepcopy(value);native=deepcopy(deleted);actual=raw
            if fault=='journal-serialization':actual=json.dumps(deleted,indent=2).encode()
            elif fault=='readers-open':changed['receipt']['readersClosed']=False
            elif fault=='missing-step':changed['receipt']['steps'].pop()
            elif fault=='absent-ack':changed['runAbsent']=False
            elif fault=='limited':native['queries'][-1].update(authorization=4,assetPresent=None)
            elif fault=='asset-present':native['queries'][-1]['assetPresent']=True
            elif fault=='read-only':native=original
            elif fault=='empty-queries':native['queries']=[]
            elif fault=='revision':changed['receipt']['artifactRevision']='0'*64
            else:changed['receipt']['processId']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.retirement(changed,changed['nonce'],native,actual,pid=84)
        later=deepcopy(value);later.update(nonce='ios-'+'2'*32,clockBefore=dict(epochMs=203063,monotonicMs=3070),clockAfter=dict(epochMs=203064,monotonicMs=3071))
        source.retirement(later,later['nonce'],deleted,raw,pid=84,previous=value)
        later['receipt']['clockAfter']['epochMs']+=1
        with self.assertRaises(NativeUIError):source.retirement(later,later['nonce'],deleted,raw,pid=84,previous=value)

    def test_segment_profiles_reopen_only_their_own_original_namespace(self):
        old=SnapshotSourceSegments(self.root,BINDING,RUN,'primary','exports',lambda:True,lambda _value:True,monotonic=lambda:1)
        new=PhotosSaveSegments(self.root,BINDING,RUN,'primary','exports',lambda:True,lambda _value:True,monotonic=lambda:1)
        raw=b'actual retained raw bytes';tag=hashlib.sha256(raw).hexdigest()
        old_parent=old.write('raw',tag,raw,1);new_parent=new.write('raw',tag,raw,1)
        self.assertEqual(raw,old.read(old_parent));self.assertEqual(raw,new.read(new_parent))
        self.assertEqual('snapshot-exports-source-parts',old.store.namespace);self.assertEqual('photos-save-exports-parts',new.store.namespace)
        for reader,value in ((old,new_parent),(new,old_parent)):
            with self.assertRaises(NativeUIError):reader.read(value)
        forged=deepcopy(new_parent);forged['chunks']=deepcopy(old_parent['chunks'])
        with self.assertRaises(NativeUIError):new.read(forged)
        for subject in ('work','captures','actor'):
            with self.assertRaises(NativeUIError):PhotosSaveSegments(self.root,BINDING,RUN,'primary',subject,lambda:True,lambda _:True,monotonic=lambda:1)

    def test_input_and_packet_default_paths_cannot_adopt_photos_journals(self):
        native=Native();store=PrivateFeatureState(self.root/PhotosSaveInputs.store_name('primary'))
        with self.lock.held():
            new=PhotosSaveInputs(store,self.lock,BINDING,RUN,'primary',native.input(),lambda:True);new.save()
            self.assertIn('photosSaveInputOwnerVersion',store.read());self.assertNotIn('iosSnapshotInputOwnerVersion',store.read())
            PhotosSaveInputs.history(store,self.lock,BINDING,RUN,'primary')
            with self.assertRaises(NativeUIError):SnapshotInputOwner.history(store,self.lock,BINDING,RUN,'primary')
            old_store=PrivateFeatureState(self.root/SnapshotInputOwner.store_name('primary'));old_store.write(store.read(),None)
            with self.assertRaises(NativeUIError):SnapshotInputOwner.history(old_store,self.lock,BINDING,RUN,'primary')
            with self.assertRaises(NativeUIError):new.reserve('snapshot.capture',{})
            for cls,name in ((PhotosSaveExportsPacket,'ios-snapshot-primary-native-exports-0001.json'),(SnapshotExportsPacket,'photos-save-primary-native-exports-0001.json')):
                with self.assertRaises(NativeUIError):cls.history(PrivateFeatureState(self.root/name),self.lock,BINDING,RUN,'primary',1)


if __name__=='__main__':unittest.main()
