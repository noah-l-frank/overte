"""Original generic Graphics source on actual iOS framing, synthetic Qt SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters.graphics_source import IOSGraphicsSource,validate
from ios.adapters import normal_input
from ios.self_tests.test_ios_script_ui_source import Boundary as InputBoundary
from adapters.normal_ui import NativeUIError


class Boundary(InputBoundary):
    def observed(self):
        change=self.edit;self.edit=None
        try:value=super().observed()
        finally:self.edit=change
        value.update(generation=self.instance,loginControlsVersion=2,graphicsControlsVersion=1,featureControlsVersion=1,
            controls=[dict(id='graphics.page',token=self.token,enabled=True,focused=False,inputReady=False,
                viewport='visible',profile='generic-immediate-v1',frame=dict(x=10,y=20,width=100,height=300))])
        if self.edit:self.edit(value)
        return value

    def reader(self,*,read_only=False):
        native=self.input()
        return IOSGraphicsSource(SimpleNamespace(native=native),lambda:20000,lambda:native._check(),42,
            monotonic=lambda:self.clock,read_only=read_only)


class IOSGraphicsSourceTests(unittest.TestCase):
    def test_native_receipt_generic_profile_and_original_clocks_are_retained(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):value=b.reader().capture()
        self.assertEqual(20000,value['capturedEpochMs']);self.assertEqual(b.receipt,value['originalReceipt'])
        self.assertEqual('generic-immediate-v1',value['controls'][0]['profile'])
        self.assertTrue(value['commandId'].startswith('ios-'));self.assertEqual(1,len(b.requests))

    def test_changed_projection_cannot_rewrite_original_profile_epoch_or_source_sequence(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):value=b.reader().capture()
        for fields in (dict(capturedEpochMs=21000),dict(sourceSequence=999),dict(generation='e'*32)):
            with self.assertRaises(NativeUIError):validate(value|fields,value['commandId'],42,20000)
        changed=deepcopy(value);changed['controls'][0]['profile']='phone-immediate-v1'
        with self.assertRaises(NativeUIError):validate(changed,value['commandId'],42,20000)

    def test_stale_foreign_missing_and_replayed_sources_fail_without_new_facts(self):
        for change in (lambda v:v.update(sampleEpochMs=19000),lambda v:v.update(processId=99),
                       lambda v:v.pop('generation'),lambda v:v.update(graphicsControlsVersion=True),
                       lambda v:v['controls'][0].update(profile='phone-immediate-v1')):
            b=Boundary();b.edit=change
            with patch.object(normal_input,'urlopen',b.post),self.assertRaises((RuntimeError,ValueError,KeyError)):
                b.reader().capture()
        b=Boundary();b.edit=lambda v:v.update(scriptSourceSequence=1)
        with patch.object(normal_input,'urlopen',b.post):
            reader=b.reader();reader.capture()
            with self.assertRaises(NativeUIError):reader.capture()
        self.assertEqual(1,reader.sequence)

    def test_read_only_sampler_cannot_activate_scroll_or_set_a_preference(self):
        b=Boundary();reader=b.reader(read_only=True)
        for call in (lambda:reader.activate('graphics.haze',token=b.token),
                     lambda:reader.scroll('graphics.scrollbar','down',token=b.token),
                     lambda:reader.set_value('graphics.resolution',.5,token=b.token)):
            with self.assertRaises(NativeUIError):call()
        self.assertEqual([],b.requests)


if __name__=='__main__':unittest.main()
