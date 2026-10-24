"""A real newly produced inactive source is final-only; no active fact relabeling."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK
from ios.adapters.world_web_observer import WorldWebObserver


class WorldWebFinalSourceTests(unittest.TestCase):
    def test_inactive_original_retains_old_prefix_and_is_never_active_observer_input(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);root.chmod(0o700)
        sdk=SDK();sdk.use_snapshot=True;sdk.stimulus=dict(verb='cleanup',inputs={})
        lock=ScriptSourceLock(root/'script-feature-sources.lock')
        with lock.held():
            store=PrivateFeatureState(root/'ios-world-web-primary-sources.json');source=sdk.owner(store,lock);before=source.capture('cleanup-original');old=source.frame(before)
            sdk.fixture_active=False;sdk.retired_epoch=sdk.phase_epoch()
            with self.assertRaises(NativeUIError):source.capture('ordinary-after-fixture-death')
            with self.assertRaises(NativeUIError):source.capture('final-fence')
            final=source.capture('final-fence',retired=True);current=source.frame(final)
            self.assertFalse(current['phaseBefore']['active']);self.assertFalse(current['phaseAfter']['active']);self.assertEqual(old,source.frame(before))
            self.assertGreater(current['clockJoin']['nativeBefore']['sequence'],old['clockJoin']['nativeAfter']['sequence'])
            rebuilt=sdk.owner(store,lock,historical=True);self.assertEqual(current,rebuilt.frame(final))
            observer=WorldWebObserver(PrivateFeatureState(root/'ios-world-web-primary-observer.json'),source,
                dict(primary='https://controlled.invalid',foreign='https://foreign.invalid'),lambda:True)
            entry=dict(sequence=1,ticket=sdk.ticket,source=final,peer=None,lease=None,scope=None,sample=None)
            with self.assertRaises(NativeUIError):observer.derive(entry)
    def test_inactive_noncleanup_and_active_final_fence_are_rejected_before_native_queries(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);root.chmod(0o700)
        sdk=SDK();sdk.use_snapshot=True;lock=ScriptSourceLock(root/'script-feature-sources.lock')
        with lock.held():
            source=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock)
            with self.assertRaises(NativeUIError):source.capture('final-fence',retired=True)
            self.assertEqual({},sdk.queries)
            sdk.fixture_active=False;sdk.retired_epoch=sdk.phase_epoch()
            with self.assertRaises(NativeUIError):source.capture('final-fence',retired=True)
            self.assertEqual({},sdk.queries)


if __name__=='__main__':unittest.main()
