"""Original capture/OS/resume Page and WDA pixels over lower host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner
from ios.self_tests.snapshot_resume_os_domain import ResumeOSDomain,RESUME,RUN


class SnapshotResumeRenderedReviewTests(unittest.TestCase):
    def review(self,d):
        return d.runtime.rendered_resume_owner('test-only',RUN,d.resume_client(),RESUME,
            epoch_ms=d.capture.epoch,monotonic=d.capture.mono,sleep=d.capture.sleep)

    def test_actual_original_capture_and_os_resume_join_new_wda_pixels_without_repeating_capture_or_os(self):
        d=ResumeOSDomain(self);births=(d.installed.sessions,d.installed.launches)
        with self.review(d) as review:
            result=review.acquire(RESUME)
            self.assertEqual('background-resume-still-png',result['stage'])
            self.assertFalse(result['originalOSBridgeRequired'] or result['renderedResumeRequired'] or result['backgroundResumeReviewRequired'])
            self.assertTrue(result['independentActorSceneRequired'] and result['destinationCompositionRequired']
                and result['pairedCleanupRequired'] and result['wholeFeatureRequired'])
            self.assertTrue(review.images.namespace.startswith('snapshot-resume-review'))
            self.assertEqual(0,max(result['renderedReview']['pixels']['meanChannelDifference']))
            # The older capture-only historical namespace remains valid beside
            # the new resume image; it cannot consume the new parent store.
            old=review.os_bridge.review();self.assertTrue(old.proof()['backgroundResumeReviewRequired'])
            with self.assertRaises(NativeUIError):SnapshotCaptureReviewOwner.archive(review.store,review.lock,review.binding,RUN,review.page.fixture_url)
        originals={p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.name.startswith('snapshot-resume-review-')}
        with self.review(d) as review:self.assertEqual(result,review.acquire(RESUME))
        self.assertEqual(originals,{p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.name.startswith('snapshot-resume-review-')})
        self.assertEqual(1,d.capture.capture_count);self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands))
        self.assertEqual(births,(d.installed.sessions,d.installed.launches))

    def test_wrong_new_wda_pixels_after_real_os_resume_are_rejected_without_another_screen_or_os_send(self):
        d=ResumeOSDomain(self);d.wrong_screen=True
        with self.review(d) as review,self.assertRaises(NativeUIError):review.acquire(RESUME)
        with self.review(d) as review,self.assertRaises(NativeUIError):review.acquire(RESUME)
        self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_lost_new_wda_return_keeps_open_inode_and_cannot_issue_a_second_screen_request(self):
        d=ResumeOSDomain(self);d.lose_screen=True
        with self.review(d) as review,self.assertRaises(NativeUIError):review.acquire(RESUME)
        d.lose_screen=False
        with self.review(d) as review,self.assertRaises(NativeUIError):review.acquire(RESUME)
        self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_saved_after_resume_screen_lost_parent_cas_adopts_original_without_repeating_wda_or_home(self):
        d=ResumeOSDomain(self)
        with self.review(d) as review:
            save=review.save
            def lost():
                if review.state['phase']=='screen-saved':raise OSError('Actual after-resume screen saved before parent CAS')
                return save()
            with patch.object(review,'save',side_effect=lost),self.assertRaises(OSError):review.acquire(RESUME)
        originals={p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.name.startswith('snapshot-resume-review-')}
        with self.review(d) as review:result=review.acquire(RESUME)
        self.assertFalse(result['renderedResumeRequired']);self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands))
        self.assertEqual(originals,{p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.name.startswith('snapshot-resume-review-')})

    def test_same_byte_replacement_screen_inode_cannot_reuse_completed_after_resume_proof(self):
        d=ResumeOSDomain(self)
        with self.review(d) as review:
            review.acquire(RESUME);path=review.images.root/review.images.rows[-1]['name'];raw=path.read_bytes();inode=path.stat().st_ino
        path.rename(path.with_name('retained-original-'+path.name));path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):
            with self.review(d) as review:review.proof()
        self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_additional_native_lifecycle_transition_between_os_proof_and_rendered_review_cannot_be_hidden(self):
        d=ResumeOSDomain(self)
        with d.resumed() as bridge:bridge.act(RESUME)
        # A subsequent actual lower native-producer state, never a rewritten
        # original. Page3 may retain this extra transition, but the rendered
        # parent must reject it against the exact already saved OS bridge.
        d.lifecycle['backgrounds']+=1;d.lifecycle['activations']+=1
        with self.review(d) as review,self.assertRaises(NativeUIError):review.acquire(RESUME)
        self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)
