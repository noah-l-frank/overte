"""Actual host cache/weak operands join original producer packets, not ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_surface_lease import admitted,current,retired
from ios.self_tests.world_web_surfaces_fixture import CacheOriginals
from ios.self_tests.test_ios_world_web_surfaces import ENTITY

RUN='a'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/tickets/'+'b'*32+'/reference.html'


class WorldWebSurfaceLeaseTests(unittest.TestCase):
    def packet(self,cache):
        before=dict(epochMs=cache.now,monotonicMs=cache.now-20000);source=cache.read();cache.now+=1
        return dict(iosWorldWebSurfacesVersion=1,requestId='ios-'+uuid.uuid4().hex,runId=RUN,instance='c'*32,sequence=source['sequence'],
            processId=42,clockDomain='native-main-ios-world-web-surfaces',clockBefore=before,
            clockAfter=dict(epochMs=cache.now,monotonicMs=cache.now-20000),source=source)
    def test_native_renderer_acquisition_is_bound_to_actual_entity_source_root_and_lease(self):
        cache=CacheOriginals();cache.reserve();before=self.packet(cache);barrier=cache.now+1
        renderer=cache.acquire(ENTITY,URL);after=self.packet(cache);owned=admitted(before,after,ENTITY,URL,after_epoch=barrier)
        self.assertEqual(after['source']['leases'][0]['birth'],owned['lease']['birth'])
        self.assertTrue(current(owned,after,live=True)[0]['alive'])
        for entity,url in ((str(uuid.uuid4()),URL),(ENTITY,URL+'?wanted=true')):
            with self.subTest(entity=entity,url=url),self.assertRaises(NativeUIError):admitted(before,after,entity,url,after_epoch=barrier)
        with self.assertRaises(NativeUIError):admitted(before,after,ENTITY,URL,after_epoch=after['clockAfter']['epochMs'])
        self.assertTrue(renderer['surface'])
    def test_cached_root_is_retained_and_queued_lease_copy_blocks_weak_retirement(self):
        cache=CacheOriginals();cache.reserve();before=self.packet(cache);renderer=cache.acquire(ENTITY,URL);active=self.packet(cache)
        owned=admitted(before,active,ENTITY,URL,after_epoch=before['clockAfter']['epochMs']);barrier=cache.now+1;queued=renderer['lease'];cache.release(renderer)
        pending=self.packet(cache)
        with self.assertRaises(NativeUIError):retired(owned,pending,after_epoch=barrier)
        del queued;gc.collect();closed=self.packet(cache);proof=retired(owned,closed,after_epoch=barrier)
        self.assertTrue(proof['surface']['surfaceAlive']);self.assertTrue(proof['surface']['rootAlive']);self.assertTrue(proof['surface']['cached'])
        self.assertNotIn('complete',proof)
        with self.assertRaises(NativeUIError):current(owned,closed,live=True)
    def test_missing_release_forged_root_source_or_foreign_birth_cannot_become_retirement(self):
        cache=CacheOriginals();cache.reserve();before=self.packet(cache);renderer=cache.acquire(ENTITY,URL);active=self.packet(cache)
        owned=admitted(before,active,ENTITY,URL,after_epoch=before['clockAfter']['epochMs']);cache.release(renderer);closed=self.packet(cache)
        for field,replacement in (('rootBirth','b'*32),('rootSource','qrc:/foreign.qml'),('instance','e'*32),('runId','f'*32)):
            bad=deepcopy(owned);bad[field]=replacement
            with self.subTest(field=field),self.assertRaises(NativeUIError):retired(bad,closed,after_epoch=before['clockAfter']['epochMs'])
        bad=deepcopy(closed);bad['source']['events'].pop();bad['source']['eventSequence']-=1
        with self.assertRaises(NativeUIError):retired(owned,bad,after_epoch=before['clockAfter']['epochMs'])


if __name__=='__main__':unittest.main()
