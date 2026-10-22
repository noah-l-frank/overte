"""Explicit Android property/clock seams; no Android OS execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_platform import PhoneSnapshotPlatform,profile


class SnapshotPlatformTests(unittest.TestCase):
    def test_measured_sdk_selects_actual_native_save_branch_without_a_caller_backend(self):
        for sdk,backend in [('26','document-picker'),('28','document-picker'),('29','media-store'),('34','media-store')]:
            with self.subTest(sdk=sdk):
                value=profile(sdk);self.assertEqual(backend,value['saveBackend']);self.assertEqual('not-required',value['savePermission'])
    def test_missing_unknown_or_coerced_os_property_never_defaults_to_media_store(self):
        for value in (None,True,34,'','unknown',' 34','034','34\n','٢٩','25','1001'):
            with self.subTest(value=value),self.assertRaises(NativeUIError):profile(value)
    def test_original_property_changes_are_not_silently_adopted_even_with_same_backend(self):
        sdk=['34'];reader=PhoneSnapshotPlatform(lambda:sdk[0],lambda:True,lambda:20000,monotonic=lambda:0.)
        self.assertEqual(34,reader.read()['source']['sdk']);sdk[0]='35'
        with self.assertRaises(NativeUIError):reader.read()
    def test_ignored_read_lost_binding_and_slow_frozen_wall_clock_are_red(self):
        for fault in ('missing','guard','slow','rewound'):
            clock=[0.];calls=[]
            def read():
                calls.append(True)
                if fault=='slow':clock[0]=1.6
                if fault=='rewound':clock[0]=-1
                return None if fault=='missing' else '34'
            reader=PhoneSnapshotPlatform(read,lambda:fault!='guard',lambda:20000,monotonic=lambda:clock[0])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read()
            self.assertEqual(0 if fault=='guard' else 1,len(calls))
    def test_reader_returns_original_acquisition_times_and_defensive_source_copy(self):
        epochs=iter([20000,20001,20002,20003]);reader=PhoneSnapshotPlatform(lambda:'34',lambda:True,lambda:next(epochs),monotonic=lambda:0.)
        first=reader.read();self.assertEqual((20000,20001),(first['requestedEpochMs'],first['capturedEpochMs']))
        first['source']['sdk']=99;self.assertEqual(34,reader.read()['source']['sdk'])


if __name__=='__main__':unittest.main()
