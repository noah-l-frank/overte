"""Actual factory/cache mechanics on explicit empty owner metadata models.

No Native/Qt/SDK facts, current-state result or terminal qualification is supplied.
Existing physical file/lock/codec/cache and production factory functions execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import record,scope
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive,IOSEmoteCallbackLiveFeature
from ios.adapters.emote_callback_scene import IOSEmoteCallbackKeyedRetirement
from ios.adapters.emote_callback_terminal import IOSEmoteCallbackTerminal
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_terminal import IOSEmoteTerminal


class CallbackWindowCacheFactoryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.enterContext(self.lock.held())
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,sessionId='factory-model',generation=0,targetFingerprint='c'*64,processIdentity='42')
        self.run='d'*32;self.calls=0;Image.preinit()

    def owner_model(self,kind):
        # Exact production owner type, explicit EMPTY metadata model only.
        # Its constructor/current/input path is not represented as native proof.
        owner=object.__new__(kind);owner.historical=False;owner.root=self.root;owner.binding=dict(self.binding)
        owner.primary_binding=dict(self.binding);owner.run=self.run;owner.role='primary';owner.lock=owner.primary_lock=self.lock
        owner.fixture_url='http://127.0.0.1/feature-fixture/v1/runs/'+self.run+'/'
        owner.phase_instance='e'*32;owner.policy=dict(source='world-render-target');owner.store=PrivateFeatureState(self.root/'empty-factory-owner.json')
        return owner

    def test_actual_callback_factory_keeps_same_flow_history_across_readers_and_foreign_flow_cannot_borrow_it(self):
        flow=object.__new__(IOSEmoteCallbackLiveFeature)
        first=IOSEmoteCallbackTerminal.make_live(flow,self.owner_model(IOSEmoteCallbackKeyedRetirement))
        self.assertIs(type(first),IOSEmoteCallbackLive);history=flow._callback_live_historical_rows
        self.assertIs(first._historical_rows,history);self.assertTrue(history.literal(),repr(history.unsupported_members()))
        file=self.root/'actual-factory-historical-row.json';file.write_bytes(b'{"mechanism":"original physical row"}');file.chmod(0o600)
        reference=dict(index=1,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        def parse():self.calls+=1;record(file);return json.loads(file.read_text())
        with scope(fresh=True) as cold:original=history.read(first,reference,parse)
        self.assertEqual(2,self.calls)
        second=IOSEmoteCallbackTerminal.make_live(flow,self.owner_model(IOSEmoteCallbackKeyedRetirement))
        self.assertIsNot(first,second);self.assertIs(second._historical_rows,history)
        with scope(fresh=True) as warm:again=history.read(second,reference,parse)
        self.assertEqual(original,again);self.assertEqual(cold,warm);self.assertEqual(2,self.calls)
        foreign=object.__new__(IOSEmoteCallbackLiveFeature)
        other=IOSEmoteCallbackTerminal.make_live(foreign,self.owner_model(IOSEmoteCallbackKeyedRetirement))
        self.assertIsNot(history,other._historical_rows)
        with self.assertRaises(NativeUIError):history.read(other,reference,parse)
        self.assertEqual(2,self.calls);self.assertEqual({},other._historical_rows.cache.rows)
        self.assertEqual(original,other._historical_rows.read(other,reference,parse));self.assertEqual(4,self.calls)
        self.assertEqual(1,len(history.cache.rows));self.assertEqual(1,len(other._historical_rows.cache.rows))

    def test_actual_default_factory_retains_legacy_live1_and_never_calls_callback_flow_factory(self):
        class LiteralOnlyFlow:
            def live_owner(self,_owner):raise AssertionError('Legacy factory invoked Callback flow cache')
        terminal=object.__new__(IOSEmoteTerminal)
        live=terminal.make_live(LiteralOnlyFlow(),self.owner_model(IOSEmoteRootedKeyedRetirement))
        self.assertIs(type(live),IOSEmoteRootedLive);self.assertEqual(1,live.FORMAT_VERSION)
        self.assertFalse(hasattr(live,'_historical_rows'));self.assertIsNone(live.previous)
        self.assertEqual(dict(records=[],pending=None),live.state)
        self.assertEqual(1,live.envelope(live.state)['iosEmoteRootedLiveVersion'])
        self.assertFalse(any(self.root.glob('emote-rooted-live-frame-*')))
