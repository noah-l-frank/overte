"""Same normal Upload owner with explicit combined capture/source custody."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_combined_packets import CombinedWorkSegments
from ios.adapters.snapshot_upload_packets import UploadSegments
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests
from ios.self_tests.snapshot_combined_upload_domain import CombinedUploadDomain,RUN


class SnapshotCombinedUploadNamespaceTests(unittest.TestCase):
    def test_upload_work_parts_cannot_borrow_capture_or_literal_upload_namespace(self):
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups);intents=[]
        with f.lock.held():
            args=(f.root,f.binding,RUN,'primary')
            capture=CombinedWorkSegments(*args,'capture',lambda:True,intents.append,monotonic=time.monotonic)
            upload=CombinedWorkSegments(*args,'upload',lambda:True,intents.append,monotonic=time.monotonic)
            literal=UploadSegments(*args,'work',lambda:True,intents.append,monotonic=time.monotonic)
            raw=b'original combined upload work bytes';tag=hashlib.sha256(raw).hexdigest()
            parents=[reader.write('raw',tag,raw,1) for reader in (capture,upload,literal)]
            for index,reader in enumerate((capture,upload,literal)):
                self.assertEqual(raw,reader.read(parents[index]))
                for foreign,parent in enumerate(parents):
                    if foreign!=index:
                        with self.subTest(reader=index,parent=foreign),self.assertRaises((NativeUIError,OSError)):reader.read(parent)
            self.assertTrue(upload.store.path(parents[1]['chunks'][0]).name.startswith('snapshot-combined-upload-parts-'))


class SnapshotCombinedUploadTests(unittest.TestCase):
    def test_normal_upload_keeps_actual_capture_inode_and_explicit_combined_original_archive(self):
        d=CombinedUploadDomain(self);d.prepare();path=d.f.f.h.path;before=(path.stat().st_ino,path.read_bytes())
        with d.upload_owner() as owner:
            owner.start('a'*32);result=owner.finish()
            self.assertEqual(2,result['snapshotUploadResultVersion']);self.assertEqual('combined',result['workProfile'])
            self.assertTrue(result['frontendHTTPConsumerRequired']);self.assertTrue(result['authenticatedBackendOriginalRequired'])
            self.assertEqual(2,owner.previous['snapshotUploadOwnerVersion'])
            sources=[owner.packet('work',group['work']) for group in owner.state['quiet']]
            self.assertTrue(all(value['source']['workers'][0]['manager']['url']=='qrc:/scripts/defaultScripts.js' for value in sources))
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(d.f.bytes,d.upload.received.getvalue())
        commands=deepcopy(d.commands)
        with lock.held():
            archived=IOSSnapshotUploadOwner.history(store,lock,binding,RUN,url,combined=True);self.assertEqual(result,archived.proof())
            with self.assertRaises(NativeUIError):IOSSnapshotUploadOwner.history(store,lock,binding,RUN,url)
        self.assertEqual(commands,d.commands);self.assertEqual((1,1),(d.capture_count,d.upload_count))

    def test_lost_normal_upload_return_reopens_original_delivery_without_another_upload(self):
        d=CombinedUploadDomain(self);d.prepare();d.lost_upload=True
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        with d.upload_owner() as owner:owner.start('a'*32);result=owner.finish()
        self.assertEqual(2,result['snapshotUploadResultVersion']);self.assertEqual(1,d.upload_count)

    def test_normal_cancel_retires_owned_body_resources_without_claiming_backend_absence(self):
        d=CombinedUploadDomain(self);d.auto_complete=False;d.prepare()
        with d.upload_owner() as owner:
            owner.start('a'*32);result=owner.cancel();self.assertEqual('cancelled',result['nativeDecision']['status'])
        self.assertTrue(result['authenticatedBackendOriginalRequired']);self.assertTrue(result['frontendHTTPConsumerRequired'])
        self.assertEqual((1,1),(d.upload_count,d.upload_cancel_count));self.assertEqual(d.f.bytes,d.upload.received.getvalue())

    def test_combined_upload_requires_explicit_profile_before_any_upload_dispatch(self):
        d=CombinedUploadDomain(self);d.prepare();commands=deepcopy(d.commands)
        with self.assertRaises(NativeUIError),d.upload_owner(combined=False):pass
        self.assertEqual(commands,d.commands);self.assertEqual(0,d.upload_count)

    def test_unowned_combined_original_prefix_refuses_fresh_owner_without_changing_original(self):
        d=CombinedUploadDomain(self);d.prepare();commands=deepcopy(d.commands)
        for prefix in ('upload-combined-work-','snapshot-combined-upload-parts-'):
            path=d.ctx.root/(prefix+'orphan.json');path.write_bytes(b'foreign retained original');path.chmod(0o600)
            before=(path.stat().st_ino,path.read_bytes())
            with self.subTest(prefix=prefix),self.assertRaises(NativeUIError),d.upload_owner():pass
            self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(commands,d.commands)
            self.assertFalse((d.ctx.root/'snapshot-upload-owner.json').exists());path.unlink()
        with d.upload_owner() as owner:self.assertEqual(2,owner.previous['snapshotUploadOwnerVersion'])
        self.assertEqual(0,d.upload_count)

    def test_new_default_manager_cannot_reanchor_original_capture_responsibility(self):
        d=CombinedUploadDomain(self);d.prepare()
        d.work_template['source']['workers'][0]['manager']['instance']='7'*32
        d.work_template['source']['timerSources']['workers'][0]['membership']['instance']='7'*32
        with d.upload_owner() as owner:
            owner.start('a'*32)
            with self.assertRaises(NativeUIError):owner.finish()
            self.assertIsNone(owner.state['result'])
        self.assertEqual(1,d.upload_count)

    def test_actual_open_body_descriptor_still_blocks_combined_quiet_after_QObject_death(self):
        d=CombinedUploadDomain(self);d.hold_fd=True;d.prepare()
        with d.upload_owner() as owner:
            owner.start('a'*32)
            with self.assertRaises(NativeUIError):owner.finish()
        self.assertTrue(d.upload.open_fds);d.upload.close_fd(d.upload.fd)
        with d.upload_owner() as owner:self.assertTrue(owner.finish()['knownObjectsAndBodyFDQuiet'])
        self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
