"""Ordinary actions execute original IOSWebView and reference JS in live Node."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_input import WorldWebInput,key_actions
from ios.self_tests.world_web_active_source_fixture import ActiveSDK


class WorldWebInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.sdk=ActiveSDK();self.addCleanup(self.sdk.close)
        self.source_store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json');self.store=PrivateFeatureState(self.root/'ios-world-web-inputs.json')
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def owner(self,source):return WorldWebInput(self.store,source,self.sdk.ui(),self.sdk.entity,lambda:True,epoch_ms=self.sdk.epoch,monotonic=lambda:self.sdk.time)
    def test_actual_normal_touch_unicode_replace_clear_and_independent_dom_read(self):
        with self.held():
            source=self.sdk.owner(self.source_store,self.lock);owner=self.owner(source);ticket=self.sdk.ticket
            owner.perform(ticket,'focus','tap','text');owner.perform(ticket,'type','replace','text',text='Überte 🙂')
            frame=source.frame(source.capture('actual-editor'));self.assertEqual(dict(text='Überte 🙂',focused=True),frame['originals']['document']['source']['dom']['editor'])
            owner.perform(ticket,'clear','replace','text',text='');frame=source.frame(source.capture('actual-cleared'))
            self.assertEqual('',frame['originals']['document']['source']['dom']['editor']['text']);self.assertEqual(3,self.sdk.releases)
            fresh=self.owner(self.sdk.owner(self.source_store,self.lock));count=len(self.sdk.posted)
            fresh.perform(ticket,'type','replace','text',text='Überte 🙂');self.assertEqual(count,len(self.sdk.posted))
    def test_unknown_post_remains_owned_and_fresh_reconstruction_never_repeats_it(self):
        with self.held():
            source=self.sdk.owner(self.source_store,self.lock);owner=self.owner(source);self.sdk.lose=True
            with self.assertRaises(OSError):owner.perform(self.sdk.ticket,'lost','tap','text')
            self.assertEqual('issued',owner.state['records'][0]['phase']);self.sdk.lose=False;fresh=self.owner(self.sdk.owner(self.source_store,self.lock))
            with self.assertRaises(NativeUIError):fresh.perform(self.sdk.ticket,'lost','tap','text')
            self.assertEqual(1,len(self.sdk.posted));self.assertEqual(1,self.sdk.releases)
    def test_unfocused_text_and_reserved_webdriver_code_do_not_issue_product_input(self):
        with self.held():
            source=self.sdk.owner(self.source_store,self.lock);owner=self.owner(source)
            with self.assertRaises(NativeUIError):owner.perform(self.sdk.ticket,'unfocused','replace','text',text='should not arrive')
            self.assertEqual([],self.sdk.posted)
        with self.assertRaises(NativeUIError):key_actions('bad\ue003')


if __name__=='__main__':unittest.main()
