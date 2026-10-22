"""Explicit original OS/session/owner seams, no background app command runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_system_context import SnapshotSystemContext,PRIMARY,RECEIVER_COMPONENT
from test_snapshot_resolution import Boundary,COMPONENT

BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:1234',sessionId='original',generation=1,targetFingerprint='c'*64)


class Source:
    def __init__(self):
        self.value=dict(binding=deepcopy(BINDING),foreground=False,running=True,appState=3)
        self.component=COMPONENT;self.clock=0.;self.authorized=True;self.calls=0;self.change=None
        self.reader=SnapshotSystemContext(BINDING,Boundary().reader().read(),self.status,lambda:self.component,lambda:self.authorized,monotonic=lambda:self.clock)
    def status(self):
        self.calls+=1
        if self.change:self.change()
        return deepcopy(self.value)


class SnapshotSystemContextTests(unittest.TestCase):
    def test_original_kernel_process_and_session_can_remain_owned_across_only_expected_os_windows(self):
        for active in (COMPONENT,RECEIVER_COMPONENT):
            source=Source();source.component=active;self.assertTrue(source.reader.guard());self.assertEqual(2,source.calls)
        source=Source();source.component=PRIMARY+'/'+PRIMARY+'.MainActivity';source.value.update(foreground=True,appState=4)
        self.assertTrue(source.reader.guard())
    def test_foreign_ui_or_other_activity_in_same_chooser_package_is_refused(self):
        for active in ('foreign.app/foreign.app.Activity','com.android.intentresolver/com.android.intentresolver.Foreign',
                       PRIMARY+'/'+PRIMARY+'.MainActivity'):
            source=Source();source.component=active
            with self.subTest(component=active),self.assertRaises(NativeUIError):source.reader.guard()
    def test_missing_durable_owner_authority_prevents_any_sdk_or_os_query(self):
        for authority in (False,None,1):
            source=Source();source.authorized=authority
            with self.subTest(authority=authority),self.assertRaises(NativeUIError):source.reader.guard()
            self.assertEqual(0,source.calls)
    def test_changed_source_artifact_kernel_process_session_generation_or_target_is_rejected(self):
        for key in BINDING:
            source=Source();source.value['binding'][key]=2 if key=='generation' else 'd'*40 if key=='sourceRevision' else 'd'*64 if key in ('artifactSha256','targetFingerprint') else '32:1234' if key=='processIdentity' else 'foreign'
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.reader.guard()
    def test_disappearing_process_or_os_transition_during_guard_remains_red(self):
        for fault in ('process','state','authority','slow','rewound'):
            source=Source()
            def mutate():
                if source.calls!=2:return
                if fault=='process':source.value['running']=False
                elif fault=='state':source.value.update(appState=2)
                elif fault=='authority':source.authorized=False
                elif fault=='slow':source.clock=1.6
                else:source.clock=-1
            source.change=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader.guard()


if __name__=='__main__':unittest.main()
