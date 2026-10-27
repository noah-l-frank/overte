"""Same normal capture owner, closed combined profile and original recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_combined_packets import CombinedCaptureWorkPacket,CombinedWorkSegments
from ios.adapters.snapshot_source_packet import SnapshotSourceSegments
from ios.self_tests.snapshot_combined_capture_domain import CombinedCaptureDomain,RUN
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests


class SnapshotCombinedCaptureNamespaceTests(unittest.TestCase):
    def test_literal_source_namespaces_cannot_adopt_combined_bytes_or_foreign_role_subject(self):
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups);intents=[]
        with f.lock.held():
            args=(f.root,f.binding,RUN,'primary')
            old=SnapshotSourceSegments(*args,'work',lambda:True,intents.append,monotonic=time.monotonic)
            new=CombinedWorkSegments(*args,'capture',lambda:True,intents.append,monotonic=time.monotonic)
            raw=b'unchanged combined work raw bytes';tag=hashlib.sha256(raw).hexdigest()
            original=old.write('raw',tag,raw,1);combined=new.write('raw',tag,raw,1)
            self.assertEqual(raw,old.read(original));self.assertEqual(raw,new.read(combined))
            self.assertTrue(old.store.path(original['chunks'][0]).name.startswith('snapshot-work-source-parts-'))
            self.assertTrue(new.store.path(combined['chunks'][0]).name.startswith('snapshot-combined-capture-parts-'))
            for reader,parent in ((old,combined),(new,original)):
                with self.subTest(reader=type(reader).__name__),self.assertRaises(NativeUIError):reader.read(parent)
            for role,subject in (('actor','capture'),('primary','unknown'),('primary','work')):
                with self.subTest(role=role,subject=subject),self.assertRaises(NativeUIError):
                    CombinedWorkSegments(f.root,f.binding,RUN,role,subject,lambda:True,intents.append,monotonic=time.monotonic)


class SnapshotCombinedCaptureTests(unittest.TestCase):
    def setUp(self):self.d=CombinedCaptureDomain(self)
    def test_normal_capture_keeps_actual_combined_manager_and_original_file_without_replay(self):
        d=self.d
        with d.owner() as owner:
            result=owner.capture('f'*32);self.assertEqual(2,result['iosSnapshotDecodedCaptureVersion'])
            self.assertEqual(2,result['capture']['iosSnapshotCompletedCaptureVersion']);self.assertEqual('combined',result['workProfile'])
            baseline=owner.history('work',owner.state['baseline']['work'])
            self.assertIs(type(baseline),CombinedCaptureWorkPacket)
            self.assertEqual('qrc:/scripts/defaultScripts.js',baseline.historical()['packet']['source']['workers'][0]['manager']['url'])
            self.assertEqual(d.f.bytes,owner.history('artifact',owner.state['artifact']).read())
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.phase.fixture_url
        commands=deepcopy(d.commands)
        with d.owner() as owner:self.assertEqual(result,owner.capture('f'*32))
        with lock.held():
            archived=IOSSnapshotCaptureOwner.archive(store,lock,binding,RUN,url,combined=True)
            self.assertEqual(result,archived.result())
            with self.assertRaises(NativeUIError):
                IOSSnapshotUploadOwner(d.runtime,'primary',RUN,lock,d.runtime._sources('primary'),archived,owner.phase,
                    epoch_ms=d.epoch,monotonic=d.mono,sleep=d.sleep)
        self.assertEqual(commands,d.commands);self.assertEqual(1,d.capture_count)
    def test_lost_normal_capture_delivery_reopens_exact_input_and_never_dispatches_again(self):
        d=self.d;d.lost=True
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.capture('f'*32)
        d.lost=False
        with d.owner() as owner:self.assertEqual('png',owner.capture('f'*32)['image']['format'])
        self.assertEqual(1,d.capture_count)
    def test_normal_cleanup_unlinks_owned_capture_and_keeps_original_after_model_quiet(self):
        d=self.d
        with d.owner() as owner:
            owner.capture('f'*32);original=owner.history('artifact',owner.state['artifact']).path()
            result=owner.cleanup();self.assertTrue(result['hostOriginalRetained']);self.assertTrue(result['pairedCleanupRequired'])
            self.assertTrue(original.exists());self.assertFalse(d.f.f.h.path.exists())
            self.assertEqual(3000,result['fileChannel']['fileChannelQuietMilliseconds'])
        self.assertEqual(1,d.capture_count);self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))
    def test_native_complete_cannot_replace_corrupt_original_png_in_combined_profile(self):
        d=self.d;d.bad_bytes=True
        with d.owner() as owner,self.assertRaises((NativeUIError,ValueError,OSError)):owner.capture('f'*32)
        self.assertEqual(1,d.capture_count);self.assertTrue(d.f.f.h.path.exists())
    def test_combined_parent_cannot_be_reopened_as_literal_separate_profile(self):
        d=self.d
        with d.owner() as owner:owner.prepare('f'*32);store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.phase.fixture_url
        commands=deepcopy(d.commands)
        with self.assertRaises(NativeUIError),d.owner(combined=False):pass
        with lock.held(),self.assertRaises(NativeUIError):IOSSnapshotCaptureOwner.archive(store,lock,binding,RUN,url)
        self.assertEqual(commands,d.commands);self.assertEqual(0,d.capture_count)
    def test_saved_combined_child_before_parent_digest_recovery_keeps_original_bytes_and_query(self):
        d=self.d
        with d.owner() as owner:
            save=owner.save
            def lost():
                if any(slot['label']=='work-before' and slot['sha256'] is not None for slot in owner.state['slots']):raise OSError('Declared loss before combined parent CAS')
                return save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.prepare('f'*32)
        commands=deepcopy(d.commands);native=d.ctx.native.sequence
        pins={path.name:(path.stat().st_ino,path.read_bytes()) for path in d.ctx.root.iterdir() if path.name.startswith(('snapshot-native-combined-work-','snapshot-combined-capture-parts-'))}
        self.assertTrue(pins)
        with d.owner() as owner:
            child=owner.observed('work-before','work');self.assertEqual('retained',child.state['phase'])
        self.assertEqual(commands,d.commands);self.assertEqual(native,d.ctx.native.sequence)
        self.assertEqual(pins,{name:((d.ctx.root/name).stat().st_ino,(d.ctx.root/name).read_bytes()) for name in pins})


if __name__=='__main__':unittest.main()
