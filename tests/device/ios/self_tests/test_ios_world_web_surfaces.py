"""Actual host cache/weak-object tests; native Qt implementation uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import json
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_surfaces import source,SOURCE_LIMIT
from ios.self_tests.world_web_surfaces_fixture import CacheOriginals

ENTITY='12345678-1234-4234-8234-123456789012'


class WorldWebSurfacesTests(unittest.TestCase):
    def valid(self,packet,previous=None):return source(packet,42,packet['capturedEpochMs'],previous)
    def test_cached_root_survives_renderer_lease_end_and_reacquisition_has_distinct_actual_lease_birth(self):
        cache=CacheOriginals();birth=cache.reserve();baseline=self.valid(cache.read())
        renderer=cache.acquire(ENTITY,'http://controlled.invalid/index.html');active=self.valid(cache.read(),baseline)
        first=active['leases'][0]['birth'];self.assertTrue(active['leases'][0]['alive'])
        cache.release(renderer);gc.collect();closed=self.valid(cache.read(),active)
        self.assertFalse(closed['leases'][0]['alive']);self.assertTrue(closed['surfaces'][0]['rootAlive'])
        self.assertTrue(closed['surfaces'][0]['surfaceAlive']);self.assertTrue(closed['surfaces'][0]['cached'])
        second_renderer=cache.acquire(ENTITY,'http://controlled.invalid/reference.html');second=self.valid(cache.read(),closed)
        self.assertEqual(birth,second['leases'][1]['surfaceBirth']);self.assertNotEqual(first,second['leases'][1]['birth'])
        self.assertFalse(second['leases'][0]['alive']);self.assertTrue(second['leases'][1]['alive']);self.assertTrue(second_renderer['surface'])
    def test_queued_actual_lease_holder_is_live_after_release_then_observed_dead_only_after_last_copy(self):
        cache=CacheOriginals();cache.reserve();renderer=cache.acquire(ENTITY,'http://controlled.invalid/index.html');admitted=self.valid(cache.read())
        queued_original=renderer['lease'];cache.release(renderer);pending=self.valid(cache.read(),admitted)
        self.assertTrue(pending['leases'][0]['alive']);del queued_original;gc.collect();ended=self.valid(cache.read(),pending)
        self.assertFalse(ended['leases'][0]['alive']);self.assertTrue(ended['surfaces'][0]['rootAlive'])
        forged=deepcopy(ended);forged['sequence']+=1;forged['leases'][0]['alive']=True
        with self.assertRaises(NativeUIError):self.valid(forged,ended)
    def test_incomplete_missing_history_reused_birth_and_forged_cache_or_root_fail(self):
        cache=CacheOriginals();cache.reserve();renderer=cache.acquire(ENTITY,'http://controlled.invalid/index.html');active=self.valid(cache.read());cache.release(renderer);current=cache.read()
        edits=(lambda v:v.update(complete=False),lambda v:v['events'].pop(),lambda v:v['surfaces'][0].update(cached=False),
            lambda v:v['surfaces'][0].update(rootBirth='a'*32),lambda v:v['leases'][0].update(surfaceBirth='b'*32),
            lambda v:v['events'][1].update(surfaceBirth='b'*32),lambda v:v.update(instance='c'*32),lambda v:v.update(sequence=True))
        for edit in edits:
            packet=deepcopy(current);edit(packet)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.valid(packet,active)
    def test_native_source_owns_only_weak_product_objects_and_original_lifetime_operations_remain_unmodified(self):
        root=Path(__file__).resolve().parents[4];header=(root/'libraries/ui/src/ui/IOSWebSurfaceOwnership.h').read_text()
        self.assertIn('QWeakPointer<OffscreenQmlSurface> weak',header);self.assertIn('QWeakPointer<int> weak',header)
        self.assertNotIn('toStrongRef(',header);self.assertIn('QPointer<QObject> root',header)
        self.assertNotIn('deleteLater(',header);self.assertNotIn('processEvents(',header)
        trace=(root/'libraries/shared/src/shared/IOSFeatureImageTrace.cpp').read_text()
        self.assertIn('original = {}; // Drop the actual original implicit copy first.',trace)
        self.assertIn('QImage original;',trace)

    def test_actual_serialized_source_overflow_fails_below_declared_object_count_caps(self):
        cache=CacheOriginals()
        for _ in range(100):cache.reserve('qrc:/qml/'+('x'*3000)+'.qml')
        value=cache.read();raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        self.assertLess(len(value['surfaces']),512);self.assertLess(value['eventSequence'],8192)
        self.assertGreater(len(raw),SOURCE_LIMIT)
        with self.assertRaises(NativeUIError):self.valid(value)
        root=Path(__file__).resolve().parents[4];header=(root/'libraries/ui/src/ui/IOSWebSurfaceOwnership.h').read_text()
        self.assertIn('MAX_SOURCE_BYTES=240000',header);self.assertIn('data.complete=false;return {};',header)


if __name__=='__main__':unittest.main()
