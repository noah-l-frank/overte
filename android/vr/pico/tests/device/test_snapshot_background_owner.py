"""Original Snapshot OS handoff and quiet; native/SDK producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_background_owner import SnapshotBackgroundOwnerTests,Boundary
from adapters.pico4.script_journey import PicoScriptJourney
import test_normal_scripts as original


class SnapshotBackgroundFactoryTests(unittest.TestCase):
    def test_actual_factory_cold_reopen_keeps_parent_lock_and_never_constructs_live_qt(self):
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        with tempfile.TemporaryDirectory(prefix='snapshot-bg-factory-') as directory:
            root=Path(directory);root.chmod(0o700);b=Boundary(root)
            with patch.object(PicoScriptJourney,'state_path',return_value=root/'normal-script-state.json'),\
                    patch.object(h.instance,'_snapshot_save_owner',side_effect=AssertionError('Cold BG must not build Qt Parent')),\
                    patch.object(h.instance,'_native_feature_observer',side_effect=AssertionError('Cold BG must not construct native reader')):
                owner=h.instance._snapshot_background_owner(h.native.target,b.run,b.source,source_lock=b.lock)
            self.assertIs(owner.lock,b.lock);self.assertEqual(b.binding,owner.binding);self.assertIsNone(owner.state)
            self.assertEqual(0,b.queries);self.assertEqual([],b.calls)

    def test_original_background_orphan_journal_manifest_or_chunk_blocks_base_cleanup(self):
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        store=h.instance._script_journey().state_path(h.native.target)
        for name in ('snapshot-background-owner.json','snapshot-background-originals.json','snapshot-background-originals.json.frame-000.json'):
            path=store.with_name(name);path.write_text('{}');path.chmod(0o600)
            try:self.assertTrue(h.instance._snapshot_originals_owned(h.native.target))
            finally:path.unlink()


if __name__=='__main__':unittest.main()
