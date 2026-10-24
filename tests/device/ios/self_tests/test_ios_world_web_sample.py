"""Actual retained host PNG/GPU receipts with original live page/VM/model inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid
from copy import deepcopy
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_restoration import restored
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
from ios.self_tests.world_web_gpu_fixture import sample

POLICY=dict(source='world-render-target',marker=[537,86,821,157],subject=[286,78,505,99])


class WorldWebSampleTests(unittest.TestCase):
    def test_actual_later_native_inspection_cannot_replace_a_historical_sample_release(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);source,scope,sdk=whole.source,whole.scope,whole.sdk
        before=source.capture('before-owned-load');scope.prepare();scope.admit_rendered();after=source.capture('after-owned-load')
        lease=WorldWebLease(scope,source,before,after)
        active=sample(whole,'ios-'+uuid.uuid4().hex);active.capture(sdk.ticket)
        observed=active.qualify(POLICY,lease.packet()['returned']['returned']['entityId']);archived=deepcopy(active.previous)
        original=deepcopy(active.state);sdk.sleep(.5);active.retire_runtime()
        latest=active.frame_owner.store.read()
        self.assertGreater(latest['absence']['requestedEpochMs'],source.frame(original['after'])['clockJoin']['nativeBefore']['capturedEpochMs'])
        self.assertNotEqual(latest['absence'],original['frameOwnership']['absence'])
        self.assertEqual(observed,active.decode(archived)['qualification'])
        self.assertEqual(archived,active.store.read())
        # The later inspection is valid retirement evidence, but substituting
        # it inside the earlier acquisition must still fail its time bracket.
        replaced=deepcopy(original);replaced['frameOwnership']=latest
        with self.assertRaises(NativeUIError):active.decode(active.envelope(replaced))
        self.assertEqual(observed,active.measure(original))

    def test_fenced_live_original_web_pixels_then_whole_former_surface_restoration(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);source,scope,sdk=whole.source,whole.scope,whole.sdk
        baseline=sample(whole,'ios-'+uuid.uuid4().hex);baseline.capture(sdk.ticket)
        before=source.capture('before-owned-load');scope.prepare();scope.admit_rendered();after=source.capture('after-owned-load');lease=WorldWebLease(scope,source,before,after)
        active=sample(whole,'ios-'+uuid.uuid4().hex);active.capture(sdk.ticket);observed=active.qualify(POLICY,lease.packet()['returned']['returned']['entityId'])
        self.assertEqual(None,observed['image']['subjectChangedFraction']);self.assertEqual('qualified',active.state['phase'])
        scope.cleanup();ended=source.capture('whole-retired-source');barrier=source.frame(ended)['clockJoin']['nativeAfter']['capturedEpochMs']
        current=sample(whole,'ios-'+uuid.uuid4().hex);current.capture(sdk.ticket);proof=restored(baseline,current,lease,after_native=barrier)
        self.assertEqual(0,proof['changedPixels']);self.assertGreater(proof['pixels'],100000)
        self.assertIsNone(sdk.item_weak());self.assertNotEqual(proof['baselineRequest'],proof['currentRequest'])


if __name__=='__main__':unittest.main()
