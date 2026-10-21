"""Exact immutable historical byte caching, never current file/source admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from feature_journeys import stereo_graphics_evidence as evidence
from self_tests.test_stereo_graphics_surface_evidence import Source,verify,RUN,TICKET,ROOT


class StereoGraphicsOriginalCacheTests(unittest.TestCase):
    def setUp(self):
        with evidence._ORIGINAL_CACHE_LOCK:
            evidence._ORIGINAL_CACHE.clear();evidence._ORIGINAL_CACHE_BYTES=0
        self.source=Source();self.values=self.source.acquire()
    def analyse(self,values=None,**options):
        raw,body,_sample=self.values if values is None else values
        return evidence.analyse(raw,json.dumps(body,sort_keys=True,separators=(',',':')).encode(),
            RUN,body['ticket'],ROOT,**options)
    def test_exact_original_pair_is_analysed_once_and_cached_results_are_independent_objects(self):
        with patch.object(evidence,'_analyse_uncached',wraps=evidence._analyse_uncached) as original:
            first=self.analyse();expected=first['state']['resolution'];first['state']['resolution']=999
            second=self.analyse();self.assertEqual(expected,second['state']['resolution'])
            self.assertEqual(1,original.call_count)
        self.assertLessEqual(evidence._ORIGINAL_CACHE_BYTES,evidence._ORIGINAL_CACHE_LIMIT)
    def test_changed_png_metadata_or_scope_cannot_reuse_previous_valid_facts(self):
        self.analyse()
        with self.assertRaises(NativeUIError):self.analyse(role='actor')
        raw,body,_sample=self.values;metadata=json.dumps(body).encode()
        with self.assertRaises((NativeUIError,ValueError)):
            evidence.analyse(raw+b'changed',metadata,RUN,TICKET,ROOT)
        body['nativeAfter']['graphics']['hazeSetting']=False
        with self.assertRaises((NativeUIError,ValueError)):self.analyse()
    def test_custom_or_failed_clock_always_executes_the_original_budget_checks(self):
        self.analyse()
        with patch.object(evidence,'_analyse_uncached',wraps=evidence._analyse_uncached) as original:
            self.analyse(monotonic=lambda:0.);self.analyse(monotonic=lambda:0.)
            self.assertEqual(2,original.call_count)
        clock=iter((0.,10.))
        with self.assertRaises(NativeUIError):self.analyse(monotonic=lambda:next(clock,20.))
    def test_memory_and_entry_limits_evict_old_pairs_without_weakening_analysis(self):
        self.analyse();charge=evidence._ORIGINAL_CACHE_BYTES
        with patch.object(evidence,'_ORIGINAL_CACHE_LIMIT',charge*2),patch.object(evidence,'_ORIGINAL_CACHE_ENTRIES',1):
            values=self.source.acquire('e'*32);self.analyse(values)
            self.assertEqual(1,len(evidence._ORIGINAL_CACHE));self.assertLessEqual(evidence._ORIGINAL_CACHE_BYTES,charge*2)
            with patch.object(evidence,'_analyse_uncached',wraps=evidence._analyse_uncached) as original:
                self.analyse();self.assertEqual(1,original.call_count)
    def test_historical_cache_does_not_accept_a_replayed_live_observation(self):
        _value,subject=verify(self.values)
        _value,current=verify(self.values)
        with self.assertRaises((NativeUIError,ValueError)):evidence.advance(subject,current)


if __name__=='__main__':unittest.main()
