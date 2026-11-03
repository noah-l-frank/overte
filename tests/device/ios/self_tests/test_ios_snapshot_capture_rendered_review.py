"""Actual Page/Capture/WDA original owners with declared lower raw producers.

No QML/UIKit/WDA/native SDK is executed. Genuine original files, full capture
completion, Page observations, CAS and OS locks execute without owner patches.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.snapshot_review_runtime import IOSSnapshotReviewRuntime
from ios.self_tests.snapshot_combined_page_domain import CombinedPageDomain,RUN
from ios.self_tests.test_ios_snapshot_rendered_review import original_pattern,screen_pattern

TICKET='f'*32


class ReviewDomain(CombinedPageDomain):
    def __init__(self,case):
        super().__init__(case,count=1,index=0,snapshot_page=0)
        self.f.bytes=original_pattern();self.screen_calls=0;self.lose_screen=False;self.wrong_screen=False;self.swap_preview=False
        observed=self.f.input_native.observed
        def observation():
            value=observed();controls=[row for row in value['controls'] if row['id']=='snapshot.capture']
            roots=[]
            if controls:
                root_id=controls[0]['snapshotRootId'];images=[]
                if self.f.f.h.path.exists():
                    images=[dict(objectIdentity='22222222-2222-4222-8222-222222222222' if not self.swap_preview else '99999999-9999-4999-8999-999999999999',
                        row=0,fileOwned=True,fileName=self.f.f.h.path.name,status=1,visible=True,sourceSize=[128,128],
                        paintedBounds=[64,80,128,128],centerAligned=True,preserveAspectFit=True,unclipped=True,axisAligned=True,
                        systemBlocked=False,window=dict(width=320,height=320,x=0,y=0,devicePixelRatio=1))]
                roots=[dict(rootIdentity=root_id,qmlSource=controls[0]['snapshotQmlSource'],visible=True,
                    capturing=False,processing=False,statusError=False,imageCount=len(images),images=images)]
            value['snapshotReviewInventory']=dict(iosSnapshotReviewInventoryVersion=1,complete=True,roots=roots);return value
        self.f.input_native.observed=observation
        http=self.http
        def wda(method,path,body):
            if path=='/session/'+self.ctx.binding['sessionId']+'/screenshot':
                need(method=='GET' and body is None);self.screen_calls+=1
                if self.lose_screen:raise OSError('Explicit lost WDA PNG return after request delivery')
                return base64.b64encode(screen_pattern(ignored=self.wrong_screen)).decode('ascii')
            prefix='/session/'+self.ctx.binding['sessionId']+'/'
            need(path.startswith(prefix))
            # The unchanged historical route model names its fixture session
            # locally. This producer receives the actual bound session URL and
            # dispatches only to that route model, before any original is saved.
            return http(method,'/session/normal-page-session/'+path[len(prefix):],body)
        self.http=wda
        class Runtime(IOSSnapshotReviewRuntime,type(self.runtime)):
            def _sources(self,selector):
                source=super()._sources(selector)
                source['session']=source['binding']['sessionId']
                return source
        self.runtime=Runtime(self.runtime.adapter)

    def prepare(self):
        with self.owner() as page:return page.capture(TICKET)

    def review(self):
        return self.runtime.rendered_review_owner('primary',RUN,self.capture.client(),
            epoch_ms=self.capture.epoch,monotonic=self.capture.mono,sleep=self.capture.sleep)

    def originals(self):
        result={}
        for path in self.ctx.root.iterdir():
            if path.is_file() and path.name.startswith(('ios-snapshot-combined-page-frame-','snapshot-review-','snapshot-')):
                info=path.lstat();result[path.name]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result


class SnapshotCaptureRenderedReviewTests(unittest.TestCase):
    def test_actual_capture_page_and_independent_screen_join_and_reconstruct_without_reacquisition(self):
        d=ReviewDomain(self);d.prepare()
        with d.review() as review:
            result=review.acquire(TICKET)
            self.assertTrue(result['captureAndRetainedPNGJoined']);self.assertTrue(result['originalPageUIAndWDAJoined'])
            self.assertFalse(result['renderedReview']['originalUIAndScreenOwnershipRequired'])
            self.assertFalse(result['renderedReview']['originalCaptureCompletionRequired'])
            self.assertTrue(result['independentActorSceneRequired'] and result['backgroundResumeReviewRequired']
                and result['pairedCleanupRequired'] and result['wholeFeatureRequired'])
            self.assertEqual(0,max(result['renderedReview']['pixels']['meanChannelDifference']))
        pins=d.originals();commands=deepcopy(d.capture.commands);clicks=deepcopy(d.clicks);native=d.ctx.native.sequence
        with d.review() as review:self.assertEqual(result,review.proof())
        self.assertEqual(1,d.capture.capture_count);self.assertEqual(1,d.screen_calls)
        self.assertEqual(pins,d.originals());self.assertEqual(commands,d.capture.commands);self.assertEqual(clicks,d.clicks)
        self.assertEqual(native,d.ctx.native.sequence)

    def test_wrong_independent_screen_never_becomes_success_and_repeated_join_does_not_repeat_capture(self):
        d=ReviewDomain(self);d.prepare();d.wrong_screen=True
        with d.review() as review,self.assertRaises(NativeUIError):review.acquire(TICKET)
        pins=d.originals()
        with d.review() as review,self.assertRaises(NativeUIError):review.acquire(TICKET)
        self.assertEqual(1,d.capture.capture_count);self.assertEqual(1,d.screen_calls);self.assertEqual(pins,d.originals())

    def test_lost_wda_return_retains_open_inode_and_never_reissues_on_new_parent(self):
        d=ReviewDomain(self);d.prepare();d.lose_screen=True
        with d.review() as review,self.assertRaises(NativeUIError):review.acquire(TICKET)
        d.lose_screen=False;pins=d.originals()
        with d.review() as review:
            rows=unpack(review.images.store.read()['transcript']);self.assertEqual('opened',rows[-1]['phase'])
            self.assertIsNone(rows[-1]['capture'])
            with self.assertRaises(NativeUIError):review.acquire(TICKET)
        self.assertEqual(1,d.screen_calls);self.assertEqual(1,d.capture.capture_count);self.assertEqual(pins,d.originals())

    def test_fully_saved_screen_lost_parent_CAS_is_adopted_without_second_WDA_request(self):
        d=ReviewDomain(self);d.prepare()
        with d.review() as review:
            save=review.save
            def lose():
                if review.state['phase']=='screen-saved':raise OSError('Explicit saved screenshot before parent CAS')
                return save()
            with patch.object(review,'save',side_effect=lose),self.assertRaises(OSError):review.acquire(TICKET)
        pins=d.originals()
        with d.review() as review:result=review.acquire(TICKET)
        self.assertTrue(result['originalPageUIAndWDAJoined']);self.assertEqual(1,d.screen_calls);self.assertEqual(1,d.capture.capture_count)
        self.assertEqual(pins,{name:d.originals()[name] for name in pins})

    def test_new_same_byte_screen_inode_cannot_reuse_completed_review(self):
        d=ReviewDomain(self);d.prepare()
        with d.review() as review:
            review.acquire(TICKET);path=review.images.root/review.images.rows[-1]['name'];raw=path.read_bytes();old=path.lstat().st_ino
        path.rename(path.with_suffix('.retained-original'));path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(old,path.lstat().st_ino)
        with self.assertRaises(NativeUIError):
            with d.review() as review:review.proof()
        self.assertEqual(1,d.screen_calls);self.assertEqual(1,d.capture.capture_count)

    def test_changed_preview_object_after_saved_screen_refuses_without_another_WDA_request(self):
        d=ReviewDomain(self);d.prepare()
        with d.review() as review:
            save=review.save
            def changed():
                result=save()
                if review.state['phase']=='screen-saved':d.swap_preview=True
                return result
            with patch.object(review,'save',side_effect=changed),self.assertRaises(NativeUIError):review.acquire(TICKET)
        self.assertEqual(1,d.screen_calls);self.assertEqual(1,d.capture.capture_count)
