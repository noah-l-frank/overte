"""Original iOS Login source with real HTTP/AFC framing and synthetic Qt SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters.login_source import IOSLoginSource,validate
from ios.adapters import normal_input
from ios.self_tests.test_ios_script_ui_source import Boundary as InputBoundary
from ios.self_tests.test_ios_login_controls import Native as LoginNative
from adapters.normal_ui import NativeUIError


class Boundary(InputBoundary):
    def __init__(self):
        super().__init__();self.login=LoginNative();self.change=None
    def observed(self):
        value=super().observed();login=self.login.packet()
        import hashlib
        digest=hashlib.sha256(b'https://owned.invalid').hexdigest()
        value['accountPreferences']=dict(accountPreferenceVersion=1,present=True,valueType='string',valueSha256=digest,
            canonicalOrigin=True,processOverridePresent=True,processOverrideSha256=digest,processOverrideCanonical=True)
        value.update(loginControlsVersion=2,generation=login['generation'],controls=login['controls'])
        if self.change:self.change(value)
        return value
    def reader(self):
        native=self.input()
        return IOSLoginSource(SimpleNamespace(native=native),lambda:20000,lambda:native._check(),42,monotonic=lambda:self.clock)


class IOSLoginSourceTests(unittest.TestCase):
    def test_original_nonce_native_epoch_generation_and_full_receipt_remain_unchanged(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            reader=b.reader();value=reader.capture()
        self.assertEqual(20000,value['capturedEpochMs']);self.assertEqual(b.receipt,value['originalReceipt'])
        self.assertEqual(b.login.generation,value['generation'])
        self.assertEqual(['login.entry'],[row['id'] for row in value['controls']])
        self.assertTrue(value['commandId'].startswith('ios-'));self.assertEqual([],b.login.qt.inputs)

    def test_generic_pending_dialog_preserves_native_request_and_independent_display(self):
        b=Boundary();b.login.qt.dialog=True;b.login.qt.waiting=True;b.login.qt.pending=True
        with patch.object(normal_input,'urlopen',b.post):value=b.reader().capture()
        page=next(row for row in value['controls'] if row['id']=='login.page')
        self.assertEqual('qml-login-v1',page['profile']);self.assertTrue(page['nativePending'])
        self.assertTrue(page['waiting']);self.assertEqual('pending',page['stage'])

    def test_legitimate_new_window_generation_is_retained_with_same_transport_and_advancing_cursors(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            reader=b.reader();first=reader.capture();b.login.generation='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
            second=reader.capture()
        self.assertNotEqual(first['generation'],second['generation']);self.assertEqual(first['instance'],second['instance'])
        self.assertGreater(second['sourceSequence'],first['sourceSequence'])

    def test_old_generation_or_clock_cannot_be_rewritten_in_projected_view(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):value=b.reader().capture()
        for change in (dict(generation='e'*32),dict(capturedEpochMs=21000),dict(sourceSequence=999)):
            with self.assertRaises(NativeUIError):validate(dict(value,**change),value['commandId'],42,20000)

    def test_stale_source_replayed_cursor_missing_generation_or_foreign_process_fails(self):
        for change in (lambda v:v.update(sampleEpochMs=19000),lambda v:v.update(processId=99),
                       lambda v:v.pop('generation'),lambda v:v.update(loginControlsVersion=1)):
            b=Boundary();b.change=change
            with patch.object(normal_input,'urlopen',b.post),self.assertRaises((RuntimeError,ValueError)):
                b.reader().capture()
        b=Boundary();b.change=lambda v:v.update(scriptSourceSequence=1)
        with patch.object(normal_input,'urlopen',b.post):
            reader=b.reader();reader.capture()
            with self.assertRaises(NativeUIError):reader.capture()

    def test_read_only_original_reader_refuses_all_login_input_methods(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            reader=b.reader();reader.read_only=True
            with self.assertRaises(NativeUIError):reader.input('login.entry','activate',token='e'*32)
            with self.assertRaises(NativeUIError):reader.close_view()
        self.assertEqual([],b.requests)

    def test_account_menu_metadata_requires_actual_original_version_and_closed_types(self):
        import hashlib
        b=Boundary()
        def menu(value):
            value['accountMenuControlsVersion']=1
            value['controls']=[dict(id='account.menu-file',token='11111111-2222-4333-8444-555555555555',
                enabled=True,focused=False,frame=dict(x=1,y=1,width=10,height=10),menuSourceVersion=1,sourceType=2,
                labelSha256=hashlib.sha256(b'File').hexdigest())]
        b.change=menu
        with patch.object(normal_input,'urlopen',b.post):
            value=b.input().capture(native_epoch_ms=lambda:20000)
            self.assertEqual('account.menu-file',value['controls'][0]['id'])
            b.change=lambda v:(menu(v),v.update(accountMenuControlsVersion=True))
            with self.assertRaises(NativeUIError):b.input().capture(native_epoch_ms=lambda:20000)


if __name__=='__main__':unittest.main()
