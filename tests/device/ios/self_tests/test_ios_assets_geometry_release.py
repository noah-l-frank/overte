"""Original weak-consumer/quiet predicates, without native or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_geometry_release as release
from ios.self_tests.test_ios_assets_geometry_consumers import AssetsGeometryConsumersTests
from ios.self_tests.test_ios_assets_model_origin import RUN


class AssetsGeometryReleaseFactsTests(unittest.TestCase):
    def pair(self):
        b=AssetsGeometryConsumersTests().prepare();reader=b.reader();before=reader.read(RUN)
        b.row.update(resourceAlive=False,resourceObjectAlive=False,readerAlive=False,parsedModelAlive=False)
        b.state['history']['geometries'][0].update(alive=False,destructionObserved=dict(epochMs=b.epoch+10,monotonicMs=10))
        after=reader.read(RUN)
        lineage=dict(processId=42,readerId=b.row['id'],sha256=b.row['sha256'],bytes=b.row['bytes'])
        return b,before,after,lineage
    def test_actual_dead_known_geometry_and_original_consumers_stay_separate_from_whole_retirement(self):
        _,before,after,lineage=self.pair();original=deepcopy(after)
        facts=release.original_consumers(before,after,lineage)
        self.assertTrue(facts['originalConsumersGone']);self.assertFalse(facts['resourceRetirementAvailable'])
        self.assertEqual(original,after)
    def test_any_actual_cached_qobject_hfm_lease_reader_or_geometry_still_blocks_the_scoped_fact(self):
        for key in ('resourceAlive','resourceObjectAlive','readerAlive','parsedModelAlive','geometry'):
            b,before,after,lineage=self.pair()
            if key=='geometry':after['source']['history']['geometries'][0].update(alive=True,destructionObserved=None)
            else:after['source']['history']['downloads'][0][key]=True
            self.assertFalse(release.original_consumers(before,after,lineage)['originalConsumersGone'])
    def test_body_or_reader_substitution_is_not_the_same_original_owned_consumer(self):
        for key,value in (('readerId','f'*32),('sha256','e'*64),('bytes',1),('processId',43)):
            _,before,after,lineage=self.pair();lineage[key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):release.original_consumers(before,after,lineage)
    def test_quiet_excludes_acquisition_spans_in_host_native_and_original_registry_clocks(self):
        def frame(before,after,native_before,native_after,registry,domain_before,domain_after):
            return dict(clockJoin=dict(hostBeforeMonotonic=before,hostAfterMonotonic=after,
                hostBeforeEpochMs=100000+before*1000,hostAfterEpochMs=100000+after*1000,
                nativeBefore=dict(capturedEpochMs=native_before),nativeAfter=dict(capturedEpochMs=native_after)),
                originals=dict(origin=dict(source=dict(history=dict(clock=dict(monotonicMs=registry)))),
                    domain=dict(clockBefore=dict(monotonicMs=domain_before),clockAfter=dict(monotonicMs=domain_after))))
        first=frame(0,1.4,20000,21400,500,100,1500)
        last=frame(3.4,4.8,23400,24800,3900,3500,4900)
        self.assertFalse(release.quiet(first,last))
        last=frame(4.4,5,24400,25000,4500,4500,5100);self.assertTrue(release.quiet(first,last))
        for part in ('host','native','registry','domain'):
            changed=deepcopy(last)
            if part=='host':changed['clockJoin']['hostBeforeMonotonic']=4.3
            elif part=='native':changed['clockJoin']['nativeBefore']['capturedEpochMs']=24399
            elif part=='registry':changed['originals']['origin']['source']['history']['clock']['monotonicMs']=3499
            else:changed['originals']['domain']['clockBefore']['monotonicMs']=4499
            with self.subTest(part=part):self.assertFalse(release.quiet(first,changed))
    def test_wrong_parent_or_unbound_helper_cannot_observe_or_qualify_retirement(self):
        with self.assertRaises(NativeUIError):release.compose(object(),object(),[])
