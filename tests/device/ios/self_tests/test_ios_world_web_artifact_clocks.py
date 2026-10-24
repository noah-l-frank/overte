"""GPU publication preserves distinct original host and native clocks.

The existing composed host fixture supplies actual retained PNG/owner files;
its SDK, native clocks and renderer remain explicit device-free models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.test_ios_world_web_sample import POLICY
from ios.self_tests.world_web_gpu_fixture import sample
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebArtifactClockTests(unittest.TestCase):
    def test_original_host_boundary_and_native_capture_survive_publication_and_replay(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close)
        source,scope,sdk=whole.source,whole.scope,whole.sdk
        before=source.capture('before-image-owned-load')
        scope.prepare();scope.admit_rendered();after=source.capture('after-image-owned-load')
        lease=WorldWebLease(scope,source,before,after)
        captured=sample(whole,'ios-'+uuid.uuid4().hex)
        observer=WorldWebObserver(PrivateFeatureState(scope.root/'ios-world-web-primary-observer.json'),
            source,sdk.origins,lambda:True,lease=lease,sample_resolver=lambda request:captured if request==captured.request else None)
        original,observed=observer.capture(sample=captured,policy=POLICY)
        gpu_original=deepcopy(captured.state['frameOwnership'])
        native_epoch=gpu_original['frame']['capturedEpochMs']
        acquisition_start=source.frame(captured.state['before'])['clockJoin']['hostBeforeEpochMs']
        # This fixture deliberately separates host and native epoch origins
        # by 70 seconds. Public freshness cannot compare those raw epochs.
        self.assertGreater(abs(acquisition_start-native_epoch),1500)
        self.assertEqual(acquisition_start,observed['public']['artifacts'][0]['capturedEpochMs'])
        self.assertEqual(acquisition_start,observed['public']['capturedEpochMs'])
        self.assertEqual(observed,observer.validate_original(original))
        self.assertEqual(gpu_original,captured.state['frameOwnership'])
        self.assertEqual(native_epoch,captured.state['qualification']['nativeEpochMs'])


if __name__=='__main__':unittest.main()
