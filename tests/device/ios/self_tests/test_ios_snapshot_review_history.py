"""Historical capture/review originals without foreground SDK construction.

Actual normal capture/UI/WDA host coordinators create the originals. The new
archive only rereads those files and cannot claim fresh process or UI facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner
from ios.self_tests.test_ios_snapshot_capture_rendered_review import ReviewDomain,RUN,TICKET


class SnapshotReviewHistoryTests(unittest.TestCase):
    def originals(self):
        domain=ReviewDomain(self);domain.prepare()
        with domain.review() as owner:
            result=owner.acquire(TICKET)
            args=(owner.store,owner.lock,deepcopy(owner.binding),RUN,owner.page.fixture_url)
        return domain,result,args

    def test_actual_original_capture_ui_and_png_proof_reopens_without_sdk_native_or_any_write(self):
        domain,result,args=self.originals();pins=domain.originals();commands=deepcopy(domain.capture.commands)
        native=domain.ctx.native.sequence;screens=domain.screen_calls;requests=deepcopy(domain.requests)
        with args[1].held(),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical original write')):
            with patch.object(domain.runtime,'_sources',side_effect=AssertionError('No SDK/source construction')):
                archive=SnapshotCaptureReviewOwner.archive(*args)
                self.assertTrue(archive.historical and archive.page.historical and archive.capture.historical and archive.images.historical)
                self.assertEqual(result,archive.proof());self.assertEqual(result,archive.proof())
        self.assertEqual(pins,domain.originals());self.assertEqual(commands,domain.capture.commands)
        self.assertEqual(native,domain.ctx.native.sequence);self.assertEqual(screens,domain.screen_calls);self.assertEqual(requests,domain.requests)

    def test_historical_owner_and_screen_child_refuse_acquisition_mutation_and_cleanup_before_any_effect(self):
        domain,_result,args=self.originals();pins=domain.originals();native=domain.ctx.native.sequence
        with args[1].held():
            archive=SnapshotCaptureReviewOwner.archive(*args);before=archive.store.read();images=archive.images.store.read()
            calls=(lambda:archive.acquire(TICKET),archive.save,archive.screen,lambda:archive.observation('before','beforeCount'),
                lambda:archive.images.capture(TICKET),archive.images.cleanup,archive.images._write)
            for call in calls:
                with self.assertRaises(NativeUIError):call()
            self.assertEqual(before,archive.store.read());self.assertEqual(images,archive.images.store.read())
        self.assertEqual(pins,domain.originals());self.assertEqual(native,domain.ctx.native.sequence)
        self.assertEqual(1,domain.screen_calls);self.assertEqual(1,domain.capture.capture_count)

    def test_wrong_original_run_binding_or_fixture_cannot_borrow_completed_historical_review(self):
        domain,_result,args=self.originals();pins=domain.originals();native=domain.ctx.native.sequence
        for field,value in ((2,dict(args[2],generation=args[2]['generation']+1)),(3,'b'*32),(4,args[4].replace('/runs/','/foreign/'))):
            changed=list(args);changed[field]=value
            with args[1].held(),self.assertRaises(NativeUIError):SnapshotCaptureReviewOwner.archive(*changed)
        self.assertEqual(pins,domain.originals());self.assertEqual(native,domain.ctx.native.sequence)
        self.assertEqual(1,domain.screen_calls);self.assertEqual(1,domain.capture.capture_count)
