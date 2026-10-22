"""The original API deadline also covers reconstruction and final SDK sends."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import avatar_api_entry as api
from ios.adapters.appium_adapter import WebDriver


class AvatarApiEntryTests(unittest.TestCase):
    def test_nested_operation_keeps_original_deadline_and_failures_stay_terminal(self):
        clock=[1.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            clock[0]=25.9
            with api.scope(lambda:clock[0]):
                clock[0]=26.;api.check()
        api.check()

    def test_canonical_final_candidate_verification_is_inside_the_original_entry_clock(self):
        clock=[0.];calls=[]
        def invoke(_self,selector,operation,values):
            calls.append((selector,operation,values));clock[0]=25.;return {'performed':True}
        entry=api.installed_entry(invoke,monotonic=lambda:clock[0])
        with self.assertRaises(NativeUIError):entry(None,'target','feature.avatar-people.cleanup',{'runId':'a'*32})
        self.assertEqual(1,len(calls))
        self.assertEqual({'performed':True},entry(None,'target','feature.emotes.cleanup',{}))

    def test_last_real_sdk_opener_is_guarded_after_request_serialization(self):
        clock=[0.];sent=[]
        client=WebDriver('http://127.0.0.1:1')
        # Slow request construction reaches the actual last transport guard;
        # no network request may follow the exhausted original API budget.
        import ios.adapters.appium_adapter as webdriver
        original=webdriver.json.dumps
        def slow(*args,**kwargs):
            value=original(*args,**kwargs);clock[0]=25.;return value
        with patch.object(webdriver.json,'dumps',side_effect=slow),patch.object(webdriver,'urlopen',side_effect=lambda *_a,**_k:sent.append(True)),self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            client.call('POST','/session',{})
        self.assertEqual([],sent)

    def test_operation_byte_cache_reuses_only_actual_unchanged_private_originals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);store=PrivateFeatureState(root/'actual-original.json')
            store.write(dict(actualNativeOriginal=1),None);decoded=[]
            def original():decoded.append(True);return store.read()
            with api.scope(lambda:1.):
                cache=api.original_cache('postlogout-parts');key=dict(context='unchanged-original-binding')
                self.assertEqual({'actualNativeOriginal':1},cache.read(key,original));self.assertEqual(2,len(decoded))
                with api.scope(lambda:1.):
                    other=api.original_cache('postlogout-parts');self.assertIs(cache,other)
                    self.assertEqual({'actualNativeOriginal':1},other.read(key,original));self.assertEqual(2,len(decoded))
                raw=store.path.read_bytes();before=store.path.stat();store.path.write_bytes(raw)
                self.assertEqual(before.st_ino,store.path.stat().st_ino)
                with self.assertRaises(NativeUIError):cache.read(key,original)
            self.assertIsNone(api.original_cache('postlogout-parts'))
            with api.scope(lambda:1.):self.assertIsNot(cache,api.original_cache('postlogout-parts'))

    def test_original_cache_admission_keeps_the_existing_failed_operation_deadline(self):
        clock=[1.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            cache=api.original_cache('postlogout-account');clock[0]=26.
            api.original_cache('postlogout-account')
        with api.scope(lambda:clock[0]):self.assertIsNot(cache,api.original_cache('postlogout-account'))
        for kind in ('derived-verdict','login',None):
            with self.assertRaises(NativeUIError):api.original_cache(kind)


if __name__=='__main__':unittest.main()
