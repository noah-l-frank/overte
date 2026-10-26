"""Normal Upload/Cancel composition with retained original capture bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters import snapshot_uploads as source
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_upload_packets import UploadSegments,SnapshotUploadInputs
from ios.adapters.snapshot_source_packet import SnapshotSourceSegments
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests,RUN
from ios.self_tests.snapshot_upload_domain import UploadDomain,fact
from ios.self_tests.snapshot_upload_flow_domain import SnapshotUploadFlowDomain


class SnapshotUploadsRevisionTests(unittest.TestCase):
    def test_literal_one_and_source_two_preserve_actual_native_stat_revision(self):
        old=UploadDomain(self);source.original(old.observe())
        actual=UploadDomain(self,version=2);value=actual.observe();source.original(value)
        stat=actual.path.stat();expected=':'.join(str(value) for value in (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mode,stat.st_nlink,stat.st_mtime_ns//10**9,stat.st_mtime_ns%10**9,stat.st_ctime_ns//10**9,stat.st_ctime_ns%10**9,stat.st_uid))
        self.assertEqual(hashlib.sha256(expected.encode()).hexdigest(),source.file_revision(fact(stat,2)))
        changed=deepcopy(value);del changed['source']['iosSnapshotUploadsSourceVersion']
        with self.assertRaises(NativeUIError):source.original(changed)
        literal=deepcopy(changed)
        for resource in literal['source']['resources']:
            for tree in (resource['firstFile'],resource['fdBefore']['file'],resource['fdAfter']['file']):
                tree.pop('mode',None);tree.pop('uid',None)
        source.original(literal);next_value=actual.observe()
        with self.assertRaises(NativeUIError):source.validate(next_value,dict(schemaVersion=1,commandId=next_value['requestId'],action=source.ACTION,runId=next_value['runId']),42,previous=literal)
        previous=source.file_revision(fact(stat,2));replacement=actual.path.with_name('replacement');replacement.write_bytes(actual.path.read_bytes());replacement.chmod(0o600);os.replace(replacement,actual.path)
        self.assertNotEqual(previous,source.file_revision(fact(actual.path.stat(),2)))


class SnapshotUploadNamespaceTests(unittest.TestCase):
    def test_upload_profile_keeps_legacy_census_and_rejects_substitution_and_actor(self):
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups);intents=[]
        args=(f.root,f.binding,RUN,'primary','inputs',lambda:True,intents.append)
        with f.lock.held():
            old=SnapshotSourceSegments(*args,monotonic=time.monotonic);new=UploadSegments(*args,monotonic=time.monotonic)
            raw=b'actual retained source bytes';tag=hashlib.sha256(raw).hexdigest();original=old.write('raw',tag,raw,1);upload=new.write('raw',tag,raw,1)
            self.assertEqual(raw,old.read(original));self.assertEqual(raw,new.read(upload))
            self.assertTrue(old.store.path(original['chunks'][0]).name.startswith('snapshot-inputs-source-parts-'))
            self.assertTrue(new.store.path(upload['chunks'][0]).name.startswith('upload-native-inputs-parts-'))
            for reader,parent in ((old,upload),(new,original)):
                with self.assertRaises(NativeUIError):reader.read(parent)
            with self.assertRaises(NativeUIError):UploadSegments(f.root,f.binding,RUN,'actor','inputs',lambda:True,intents.append,monotonic=time.monotonic)


class SnapshotUploadOwnerTests(unittest.TestCase):
    def test_actual_normal_upload_joins_exact_capture_file_and_quiet_script_resources(self):
        d=SnapshotUploadFlowDomain(self);d.prepare()
        with d.upload_owner() as owner:
            started=owner.start('a'*32);self.assertTrue(started['nativeUploadObserved']);result=owner.finish()
            self.assertTrue(result['knownObjectsAndBodyFDQuiet']);self.assertTrue(result['authenticatedBackendOriginalRequired'])
            self.assertTrue(result['transportProcessProofRequired']);self.assertTrue(result['nativeScriptSignalReturned'])
            for fault in ('phase','native-tail'):
                changed=deepcopy(owner.previous);state=unpack(changed['payload'])[0]
                if fault=='phase':state['ticket']=state['verb']=state['phaseOriginal']=None
                else:state['nativeTail']=deepcopy(owner.capture.state['nativeTail'])
                changed['payload']=pack([state])
                with self.assertRaises(NativeUIError):owner.load(changed)
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        self.assertEqual(1,d.upload_count);self.assertEqual(d.f.bytes,d.upload.received.getvalue());self.assertTrue(d.f.f.h.path.exists())
        requests=deepcopy(d.commands)
        with lock.held():
            reader=IOSSnapshotUploadOwner.history(store,lock,binding,owner.run,url);self.assertEqual(result,reader.proof())
        self.assertEqual(requests,d.commands)
    def test_normal_cancel_retires_actual_held_upload_without_assuming_server_absence(self):
        d=SnapshotUploadFlowDomain(self);d.auto_complete=False;d.prepare()
        with d.upload_owner() as owner:
            owner.start('a'*32);result=owner.cancel();self.assertEqual('cancelled',result['nativeDecision']['status'])
        self.assertEqual((1,1),(d.upload_count,d.upload_cancel_count));self.assertTrue(result['authenticatedBackendOriginalRequired'])
        self.assertEqual(d.f.bytes,d.upload.received.getvalue())
    def test_lost_normal_upload_return_recovers_original_reception_without_second_input(self):
        d=SnapshotUploadFlowDomain(self);d.prepare();d.lost_upload=True
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        with d.upload_owner() as owner:owner.start('a'*32);owner.finish()
        self.assertEqual(1,d.upload_count)
    def test_actual_live_body_descriptor_blocks_quiet_even_after_all_QObjects_die(self):
        d=SnapshotUploadFlowDomain(self);d.hold_fd=True;d.prepare()
        with d.upload_owner() as owner:
            owner.start('a'*32)
            with self.assertRaises(NativeUIError):owner.finish()
        self.assertEqual(1,d.upload_count);self.assertTrue(d.upload.open_fds)
        d.upload.close_fd(d.upload.fd)
        with d.upload_owner() as owner:self.assertTrue(owner.finish()['knownObjectsAndBodyFDQuiet'])
        self.assertEqual(1,d.upload_count)
    def test_same_bytes_replacement_before_normal_upload_cannot_reanchor_capture_revision(self):
        d=SnapshotUploadFlowDomain(self);d.prepare();path=d.f.f.h.path;other=path.with_name('replacement');other.write_bytes(path.read_bytes());other.chmod(0o600);os.replace(other,path)
        with d.upload_owner() as owner,self.assertRaises(NativeUIError):owner.start('a'*32)
        self.assertEqual(1,d.upload_count)
    def test_child_input_reservation_before_parent_CAS_adopts_exact_WAL_and_sends_once(self):
        d=SnapshotUploadFlowDomain(self);d.prepare();reserve=SnapshotUploadInputs.reserve
        def interrupted(reader,*args,**kwargs):
            reserve(reader,*args,**kwargs);raise OSError('Original child reservation persisted before parent input CAS')
        with d.upload_owner() as owner,patch.object(SnapshotUploadInputs,'reserve',interrupted),self.assertRaises(OSError):owner.start('a'*32)
        self.assertEqual(0,d.upload_count)
        with d.upload_owner() as owner:owner.start('a'*32);owner.finish()
        self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
