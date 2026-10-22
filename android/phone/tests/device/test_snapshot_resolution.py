"""Explicit package-manager transport boundary; no Android package query runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import shlex
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_resolution import SnapshotChooserResolution,resolved,package_uid,join_grant,RESOLVE

COMPONENT='com.android.intentresolver/com.android.intentresolver.ChooserActivity'


class Boundary:
    def __init__(self):self.clock=0.;self.epoch=20000;self.okay=True;self.calls=[];self.fault=None
    def execute(self,args,*,target,timeout):
        self.calls.append((args,target,timeout));command=shlex.split(args[1])
        value=COMPONENT if tuple(command)==RESOLVE else 'package:com.android.intentresolver uid:10038\n'
        return self.fault(value) if self.fault else value
    def reader(self):return SnapshotChooserResolution(self,'private-synthetic-only',lambda:self.okay,lambda:self.epoch,monotonic=lambda:self.clock)


class SnapshotResolutionTests(unittest.TestCase):
    def test_original_resolution_and_uid_are_read_without_launch_or_input(self):
        b=Boundary();value=b.reader().read();self.assertEqual(COMPONENT,value['component']);self.assertEqual(10038,value['uid'])
        self.assertEqual(3,len(b.calls));self.assertTrue(all(row[0][0]=='shell' for row in b.calls))
        self.assertEqual(tuple(shlex.split(b.calls[0][0][1])),RESOLVE)
        self.assertEqual(value,join_grant(value,dict(chooserComponent=COMPONENT,chooserUid=10038)))
    def test_original_android_brief_metadata_and_relative_activity_are_canonicalized(self):
        self.assertEqual(COMPONENT,resolved('priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\ncom.android.intentresolver/.ChooserActivity\n'))
    def test_older_android_framework_chooser_keeps_actual_package_and_uid(self):
        self.assertEqual('android/com.android.internal.app.ChooserActivity',resolved('android/com.android.internal.app.ChooserActivity'))
        self.assertEqual(1000,package_uid('package:android uid:1000','android'))

    def test_missing_or_multiple_foreign_ambiguous_resolution_and_uid_never_defaults(self):
        for raw in ('','No activity found','android/ResolverActivity',COMPONENT+'\n'+COMPONENT,'malformed\n'+COMPONENT,COMPONENT+'; echo bad'):
            with self.subTest(raw=raw),self.assertRaises(NativeUIError):resolved(raw)
        for raw in ('','package:other.app uid:10038','package:com.android.intentresolver uid:0',
                    'package:com.android.intentresolver uid:10038\npackage:com.android.intentresolver uid:10039','package:com.android.intentresolver uid:root'):
            with self.subTest(raw=raw),self.assertRaises(NativeUIError):package_uid(raw,'com.android.intentresolver')
    def test_actual_native_intent_component_or_uid_mismatch_remains_red(self):
        value=Boundary().reader().read()
        for edit in (dict(chooserComponent='other.app/other.app.Chooser'),dict(chooserUid=10039),dict(chooserUid=True)):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):join_grant(value,dict(chooserComponent=COMPONENT,chooserUid=10038)|edit)
    def test_changed_original_resolution_is_not_adopted_or_used_for_input(self):
        b=Boundary();reader=b.reader();reader.read();b.fault=lambda raw:raw.replace('ChooserActivity','ForeignActivity')
        with self.assertRaises(NativeUIError):reader.read()
        b=Boundary()
        def changed(raw):return raw.replace('ChooserActivity','ForeignActivity') if len(b.calls)==3 else raw
        b.fault=changed
        with self.assertRaises(NativeUIError):b.reader().read()
    def test_foreign_guard_or_frozen_epoch_slow_command_cannot_produce_a_qualified_resolution(self):
        b=Boundary();b.okay=False
        with self.assertRaises(NativeUIError):b.reader().read()
        self.assertEqual([],b.calls)
        b=Boundary()
        def slow(raw):b.clock+=.6;return raw
        b.fault=slow
        with self.assertRaises(NativeUIError):b.reader().read()


if __name__=='__main__':unittest.main()
