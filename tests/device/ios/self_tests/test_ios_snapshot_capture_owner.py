"""Normal private capture composition; explicit native/SDK boundary models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_source_packet import SnapshotWorkPacket
from ios.adapters.snapshot_file_work_packet import Frames
from ios.self_tests.snapshot_capture_domain import SnapshotCaptureDomain,RUN


class SnapshotCaptureOwnerTests(unittest.TestCase):
    def setUp(self):self.domain=SnapshotCaptureDomain(self)
    def test_normal_input_decodes_original_private_png_and_reconstruction_never_captures_twice(self):
        d=self.domain
        with d.owner() as owner:
            result=owner.capture('f'*32);self.assertEqual('png',result['image']['format'])
            self.assertEqual(d.f.bytes,owner.history('artifact',owner.state['artifact']).read())
            self.assertTrue(result['sceneFidelityRequired']);self.assertTrue(result['destinationOutcomeRequired'])
            self.assertTrue(result['independentWitnessRequired']);store=owner.store;lock=owner.lock;binding=owner.binding;url=owner.phase.fixture_url
        with d.owner() as owner:self.assertEqual(result,owner.capture('f'*32))
        self.assertEqual(1,d.capture_count);requests=deepcopy(d.commands)
        with lock.held():
            archived=IOSSnapshotCaptureOwner.archive(store,lock,binding,RUN,url)
            self.assertEqual(result,archived.result())
        self.assertEqual(requests,d.commands)
    def test_actual_capture_file_unlink_and_three_second_quiet_preserve_host_original(self):
        d=self.domain
        with d.owner() as owner:
            owner.capture('f'*32);artifact=owner.history('artifact',owner.state['artifact']);path=artifact.path()
            result=owner.cleanup();self.assertTrue(result['hostOriginalRetained']);self.assertTrue(result['pairedCleanupRequired'])
            self.assertTrue(path.exists());self.assertFalse(d.f.f.h.path.exists())
            self.assertEqual(3000,result['fileChannel']['fileChannelQuietMilliseconds'])
        self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))
    def test_lost_normal_capture_result_reconstruction_uses_original_input_reception_without_resend(self):
        d=self.domain;d.lost=True
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.capture('f'*32)
        d.lost=False
        with d.owner() as owner:result=owner.capture('f'*32);self.assertEqual('png',result['image']['format'])
        self.assertEqual(1,d.capture_count)
    def test_ignored_input_cannot_produce_file_success_or_a_second_capture(self):
        d=self.domain;d.ignored=True
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.capture('f'*32)
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.capture('f'*32)
        self.assertEqual(1,d.capture_count);self.assertFalse(d.f.f.h.path.exists())
    def test_native_completion_cannot_hide_corrupt_original_png(self):
        d=self.domain;d.bad_bytes=True
        with d.owner() as owner,self.assertRaises((NativeUIError,ValueError,OSError)):owner.capture('f'*32)
        self.assertEqual(1,d.capture_count);self.assertTrue(d.f.f.h.path.exists())
    def test_retained_native_capture_callback_blocks_capture_and_cleanup_until_real_weak_expiry(self):
        d=self.domain;d.hold=True
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.capture('f'*32)
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertTrue(d.f.f.h.path.exists());self.assertFalse(any(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))
    def test_retained_native_remove_functor_prevents_quiet_without_reissuing_unlink(self):
        d=self.domain
        with d.owner() as owner:owner.capture('f'*32)
        d.keep_remove=True
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertFalse(d.f.f.h.path.exists());d.held_removes.clear();d.keep_remove=False
        with d.owner() as owner:self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        self.assertEqual(1,sum(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))


class SnapshotCaptureRecoveryTests(unittest.TestCase):
    def setUp(self):self.domain=SnapshotCaptureDomain(self)
    def pins(self):
        result={}
        for path in self.domain.ctx.root.iterdir():
            if path.name.startswith('snapshot-') and path.is_file():
                stat=path.stat();result[path.name]=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result
    def adopt_work(self,expected_queries,expected_native,*,extra_native=0):
        d=self.domain;before=self.pins();self.assertTrue(before)
        with d.owner() as owner:
            slot=next(slot for slot in owner.state['slots'] if slot['label']=='work-before');self.assertIsNone(slot['sha256'])
            child=owner.observed('work-before','work');self.assertEqual('retained',child.state['phase']);self.assertIsNotNone(slot['sha256'])
        after=self.pins();self.assertTrue(set(before)<=set(after));self.assertEqual(before,{name:after[name] for name in before})
        if extra_native:
            added=set(after)-set(before);self.assertEqual(1,len(added));self.assertTrue(next(iter(added)).startswith('snapshot-native-work-frame-'))
        else:self.assertEqual(before,after)
        self.assertEqual(expected_queries,d.commands)
        self.assertEqual(expected_native+extra_native,d.ctx.native.sequence);self.assertEqual(0,d.capture_count)
    def test_saved_child_before_parent_digest_CAS_reopens_and_adopts_exact_originals_without_any_send(self):
        d=self.domain
        with d.owner() as owner:
            save=owner.save
            def lost():
                if any(slot['label']=='work-before' and slot['sha256'] is not None for slot in owner.state['slots']):
                    raise OSError('Explicit loss before parent child-digest CAS')
                return save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.capture('f'*32)
            state=unpack(owner.store.read()['payload'])[0]
            self.assertIsNone(next(slot for slot in state['slots'] if slot['label']=='work-before')['sha256'])
        self.adopt_work(deepcopy(d.commands),d.ctx.native.sequence)
    def test_issued_child_with_saved_small_frame_adopts_its_original_proof_without_native_or_file_recreation(self):
        d=self.domain;save=SnapshotWorkPacket.save
        def lost(child):
            if child.state['phase']=='retained':raise OSError('Explicit loss before child retained journal CAS')
            return save(child)
        with d.owner() as owner:
            with patch.object(SnapshotWorkPacket,'save',lost),self.assertRaises(OSError):owner.capture('f'*32)
        self.adopt_work(deepcopy(d.commands),d.ctx.native.sequence)
    def test_complete_raw_parts_before_small_frame_recover_without_second_source_query_or_byte_rewrite(self):
        d=self.domain;write=Frames.write
        def lost(frames,index,value):
            if frames.owner._name=='native-work':raise OSError('Explicit loss before small frame allocation')
            return write(frames,index,value)
        with d.owner() as owner:
            with patch.object(Frames,'write',lost),self.assertRaises(OSError):owner.capture('f'*32)
        # Finishing this existing acquisition needs one actual new independent
        # native clock. It cannot resend the original work query or input.
        self.adopt_work(deepcopy(d.commands),d.ctx.native.sequence,extra_native=1)


if __name__=='__main__':unittest.main()
