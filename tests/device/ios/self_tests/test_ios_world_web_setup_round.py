"""Actual Source/Observer byte guards for pure Setup retirement methods.

Native producers are declared models. This checks scoped decoder wiring and
entry/exit file identity, not a native cleanup or terminal outcome.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_setup_retirement import _readonly,WorldWebSetupRetirement
from ios.self_tests import test_ios_world_web_observer as fixture


class WorldWebSetupRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebObserverTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.sdk.use_snapshot=True;self.f.sdk.use_whole_snapshot=True
    def context(self):
        f=self.f;source=f.sdk.owner(f.source_store,f.lock);observer=f.observer(source);reference,expected=observer.capture()
        return source,observer,reference,expected,SimpleNamespace(observer=observer)
    def test_existing_source_and_observer_rounds_span_one_pure_method_and_end_normally(self):
        with self.f.held():
            source,observer,reference,expected,owner=self.context();queries=len(self.f.sdk.native.commands)
            @_readonly
            def read(_owner):
                self.assertIsNotNone(source._round);self.assertIsNotNone(observer._round)
                observer.validate_original(reference);return observer.validate_original(reference)
            with patch.object(source,'_decode_frames',wraps=source._decode_frames) as decoded:
                self.assertEqual(expected,read(owner));self.assertEqual(1,decoded.call_count)
            self.assertIsNone(source._round);self.assertIsNone(observer._round);self.assertEqual(queries,len(self.f.sdk.native.commands))
            for name in ('measure','decode','qualification','validate_original'):self.assertTrue(hasattr(getattr(WorldWebSetupRetirement,name),'__wrapped__'))
    def test_equal_byte_replacement_after_last_read_is_refused_before_return(self):
        with self.f.held():
            source,observer,reference,_expected,owner=self.context();frame=source.frame(source.state['records'][-1])
            path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0];queries=len(self.f.sdk.native.commands)
            @_readonly
            def read(_owner):
                observer.validate_original(reference);replacement=path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
                return dict(unqualifiedSentinel='must not escape')
            with self.assertRaises(NativeUIError):read(owner)
            self.assertIsNone(source._round);self.assertIsNone(observer._round);self.assertEqual(queries,len(self.f.sdk.native.commands))


if __name__=='__main__':unittest.main()
