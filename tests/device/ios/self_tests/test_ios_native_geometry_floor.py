"""Optional original UIKit BEFORE floor never supplies a current clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.native_geometry import OriginalGeometry


class NativeGeometryFloorTests(unittest.TestCase):
    def reader(self,*,slow=False):
        self.now=20000;self.mono=0.;self.clocks=[];self.posts=[]
        def clock():
            self.now+=1;self.clocks.append(self.now)
            if slow and len(self.clocks)==2:self.mono=2.
            return self.now
        def send(query):self.posts.append(query)
        def original():
            return json.dumps(dict(schemaVersion=1,commandId=self.posts[-1]['commandId'],observation=dict(schemaVersion=1,sampleEpochMs=20001,
                sampleSequence=1,nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20,
                    keyboardVisible=False,imeInsetBottom=0),window=dict(width=1024,height=728))))
        return OriginalGeometry(send,original,clock,lambda:True,monotonic=lambda:self.mono)
    def test_default_has_three_new_clock_queries_and_explicit_original_floor_keeps_two_new_terminal_queries(self):
        first=self.reader();value=first.capture();self.assertEqual([20001,20002,20003],self.clocks)
        reader=self.reader();value=reader.capture(native_before_floor=20000)
        self.assertEqual([20001,20002],self.clocks);self.assertEqual(1,len(self.posts));self.assertEqual(20001,value['observation']['sampleEpochMs'])
        self.assertEqual(value,reader.last)
    def test_invalid_or_preceding_last_original_floor_refuses_before_native_send(self):
        for floor in (True,False,0,-1,20000.,'20000'):
            reader=self.reader()
            with self.subTest(floor=floor),self.assertRaises(NativeUIError):reader.capture(native_before_floor=floor)
            self.assertEqual([],self.posts);self.assertEqual([],self.clocks)
        reader=self.reader();reader.epoch=20002
        with self.assertRaises(NativeUIError):reader.capture(native_before_floor=20001)
        self.assertEqual([],self.posts)
    def test_slow_second_terminal_clock_and_future_floor_cannot_retime_receipt_or_become_success(self):
        reader=self.reader(slow=True)
        with self.assertRaises(NativeUIError):reader.capture(native_before_floor=20000)
        self.assertEqual(2,len(self.clocks));self.assertIsNone(reader.last)
        reader=self.reader()
        with self.assertRaises(NativeUIError):reader.capture(native_before_floor=30000)
        self.assertIsNone(reader.last)


if __name__=='__main__':unittest.main()
