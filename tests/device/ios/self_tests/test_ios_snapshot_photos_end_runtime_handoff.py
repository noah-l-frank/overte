"""Actual runtime PageReturn→existing Photos End; native/SDK remain models.

These prospective cases are UNRUN. No whole/native or End2 timing claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_runtime import IOSSnapshotShareRuntime
from ios.self_tests import test_ios_snapshot_page_return as return_test
from ios.self_tests.snapshot_photos_end_domain import PhotosEndFlow,PhotosEndReturnFlow,selected_public_policy
from ios.self_tests.snapshot_share_domain import REAL_TIME,REAL_MONOTONIC,REAL_SLEEP,SYSTEM_UI
from ios.self_tests.snapshot_companion_domain import RUN
from ios.self_tests.retained_host_roots import retain_owned_root


def photos_config(domain):
    owner=domain.photos;helper=owner.helper
    return dict(client=helper,sessionStore=helper.session,target=helper.target,binding=owner.helper_binding,
        artifactPath=helper.ipa,admissionStore=owner.admission_store)


def end_request(domain):
    return dict(profile='combined-photos-return-v2',photos=photos_config(domain),
        domainPolicy=selected_public_policy(domain.public_selection))


def runtime_end(domain):
    request=end_request(domain)
    return domain.runtime.photos_end_owner('primary',RUN,domain.client(),request['photos'],domain.archive_config(),
        SYSTEM_UI,request['domainPolicy'],primary_bundle=domain.primary.target['appId'],profile=request['profile'],
        epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC,sleep=REAL_SLEEP)


class SnapshotPhotosEndRuntimeHandoffTests(unittest.TestCase):
    def test_missing_or_unknown_profile_refuses_before_runtime_sources_or_helpers(self):
        runtime=object.__new__(IOSSnapshotShareRuntime)
        def forbidden(*_args,**_kwargs):raise AssertionError('Closed profile cannot acquire any source')
        runtime._sources=forbidden
        for profile in (None,True,'combined','combined-photos-return-v1'):
            with self.subTest(profile=profile),self.assertRaises(NativeUIError):
                with runtime.photos_end_owner('primary',RUN,None,None,None,None,None,
                        primary_bundle='org.example.client',profile=profile):pass

    def test_normal_return_hands_off_actual_delivered_stop_loss_then_same_runtime_recovers_without_replay(self):
        with patch.object(return_test,'PageReturnFlow',PhotosEndReturnFlow):
            domain,host=return_test.SnapshotPageReturnOwnerTests.prepared(self)
        helper=domain.photos.helper;original=(host.stat().st_ino,host.read_bytes())
        helper.lose_stop=True;restored=None
        with self.assertRaisesRegex(NativeUIError,'lost Photos Stop'):
            with domain.return_owner(photos_end=end_request(domain)) as owner:restored=owner.restore()
        self.assertTrue(restored['restoration']['originalRouteRestored'])
        self.assertTrue(restored['mainProcessStillOwned']);self.assertTrue(restored['primarySDKRetirementRequired'])
        self.assertEqual((1,0),(helper.stop_calls,helper.delete_calls))
        self.assertEqual((1,1),(domain.page.clicks.count('tablet.home'),domain.page.clicks.count('tablet.close')))
        commands=deepcopy(domain.main.commands);clicks=deepcopy(domain.page.clicks)
        with runtime_end(domain) as ended:
            self.assertTrue(ended.state['stopIssued']);self.assertFalse(ended.state['processReady'])
            result=ended.finalize()
            self.assertEqual(2,result['snapshotPhotosEndedVersion'])
            self.assertTrue(result['originalPhotosSDK404']);self.assertTrue(result['mainProcessStillOwned'])
            self.assertTrue(result['sourceMainSDKWitnessRetirementRequired']);self.assertTrue(result['wholeFeatureRequired'])
        self.assertEqual((1,1),(helper.stop_calls,helper.delete_calls));self.assertIsNone(helper.session.read())
        self.assertEqual(commands,domain.main.commands);self.assertEqual(clicks,domain.page.clicks)
        self.assertEqual(original,(host.stat().st_ino,host.read_bytes()));self.assertTrue(domain.main_foreground)
        self.assertEqual((1,1,1,1),(domain.photos.save_count,helper.read_count,helper.delete_count,helper.retire_count))

    def test_lost_end_parent_cannot_adopt_actual_unfinished_process_responsibility_or_query_helper(self):
        flow=PhotosEndFlow(self);domain=flow.domain;helper=domain.photos.helper
        helper.ignore_stop=True;helper.lose_stop=True
        with runtime_end(domain) as owner:
            with self.assertRaisesRegex(NativeUIError,'lost Photos Stop'):owner.finalize()
            parent=owner.store.path
        with runtime_end(domain) as reopened:
            self.assertTrue(reopened.state['stopIssued'])
            self.assertFalse(reopened.process().advance())
            process=reopened.process_path();self.assertIsNotNone(PrivateFeatureState(process).read())
        external=tempfile.TemporaryDirectory(prefix='photos-runtime-lost-parent-');self.addCleanup(external.cleanup)
        root=retain_owned_root(external,expected_root=Path(external.name));saved=root/'actual-end-owner.original.json'
        parent.rename(saved);self.assertFalse(parent.exists());self.assertTrue(saved.exists())
        retained=(process.stat().st_ino,process.read_bytes());before=deepcopy((helper.requests,helper.sdk))
        with self.assertRaises(NativeUIError) as raised:
            with runtime_end(domain):self.fail('A lost parent cannot adopt actual process originals')
        self.assertNotIn('budget',str(raised.exception).lower())
        self.assertEqual(before,(helper.requests,helper.sdk));self.assertEqual((1,0),(helper.stop_calls,helper.delete_calls))
        self.assertFalse(parent.exists());self.assertTrue(helper.sdk_alive)
        self.assertEqual(retained,(process.stat().st_ino,process.read_bytes()))
        self.assertTrue(flow.host.exists());self.assertTrue(domain.main_foreground)


if __name__=='__main__':unittest.main()
