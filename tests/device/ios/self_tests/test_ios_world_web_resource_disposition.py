"""Synthetic native holder model; actual QImage/C++ source remains uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_resource_disposition import disposition,unchanged
from ios.self_tests.test_ios_web_closures import ClosureBoundary,RUN,URL


class WorldWebResourceDispositionTests(unittest.TestCase):
    def originals(self):
        native=ClosureBoundary();native.version=5;reader=native.reader();admitted=reader.read(RUN,URL)
        native.retired=1;native.resources['policy-grant']=dict(created=1,retired=1,pending=0)
        return native,reader,admitted

    def test_cached_qsg_node_and_original_bitmap_remain_owned_after_real_callback_and_grant_ends(self):
        native,reader,admitted=self.originals();current=reader.read(RUN,URL);result=disposition(current,admitted)
        self.assertEqual('held',result['mode'])
        self.assertEqual(1,result['contexts'][0]['resources']['scenegraph-node']['pending'])
        self.assertEqual(1,result['contexts'][0]['resources']['native-bitmap']['pending'])
        self.assertEqual(current['contexts'],result['contexts']);result['contexts'].clear()
        self.assertTrue(disposition(current,admitted)['contexts'])
        # Source-only instrumentation cannot clear a cached original QImage or
        # its conservative QSG source union. Only the modeled original holder
        # destruction changes counters, never this consumer or a Stop ACK.
        following=reader.read(RUN,URL);self.assertTrue(unchanged(current,following))
        self.assertEqual('held',disposition(following,admitted)['mode'])
        for kind in native.resources:native.resources[kind]=dict(created=1,retired=1,pending=0)
        released=reader.read(RUN,URL);self.assertEqual('released',disposition(released,admitted)['mode'])
        with self.assertRaises(NativeUIError):unchanged(current,released)

    def test_callback_pending_policy_grant_or_missing_actual_resource_admission_cannot_be_quiet(self):
        for fault in ('callback','grant','admission','complete','foreign'):
            native,reader,admitted=self.originals()
            if fault=='callback':native.retired=0
            elif fault=='grant':native.resources['policy-grant']=dict(created=1,retired=0,pending=1)
            elif fault=='admission':admitted['contexts'][0]['resources']['offscreen-image']=dict(created=0,retired=0,pending=0)
            current=reader.read(RUN,URL)
            if fault=='complete':current['complete']=False
            elif fault=='foreign':current['instance']='a'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):disposition(current,admitted)

    def test_partial_source_is_not_full_resource_admission_or_process_retirement(self):
        native,reader,admitted=self.originals();admitted['contexts']=[];current=reader.read(RUN,URL)
        self.assertEqual('held',disposition(current,admitted,partial=True)['mode'])
        with self.assertRaises(NativeUIError):disposition(current,admitted)
        self.assertNotIn('complete',disposition(current,admitted,partial=True))


if __name__=='__main__':unittest.main()
