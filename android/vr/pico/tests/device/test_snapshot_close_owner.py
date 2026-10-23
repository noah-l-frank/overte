"""Normal original checked controls, one controller Close and actual factory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_close_owner import SnapshotCloseOwnerTests,CloseBoundary
from adapters.pico4.script_journey import PicoScriptJourney
import test_normal_scripts as original


class SnapshotCloseFactoryTests(unittest.TestCase):
    def test_actual_factory_preserves_original_parent_and_exact_source_lock_without_input(self):
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        with tempfile.TemporaryDirectory(prefix='snapshot-close-factory-') as directory:
            root=Path(directory);root.chmod(0o700);m=CloseBoundary(root);queries=m.b.queries
            with patch.object(PicoScriptJourney,'state_path',return_value=root/'state.json'):
                owner=h.instance._snapshot_close_owner(h.native.target,m.b.run,m.b.source,m.m.images,parent=m.image,source_lock=m.b.lock)
            self.assertIs(owner.parent,m.image);self.assertIs(owner.lock,m.b.lock);self.assertIs(owner.base,m.base)
            self.assertEqual(queries,m.b.queries);self.assertEqual([],m.commands);self.assertEqual([],m.transport.sent)
            self.assertEqual([],h.native.inputs);self.assertEqual([],h.native.controllers)
            with m.session._lock():
                cursor=m.session._load();cursor['sessionNonce']='f'*32;m.session._save(cursor)
            with patch.object(PicoScriptJourney,'state_path',return_value=root/'state.json'),self.assertRaises(ValueError):
                h.instance._snapshot_close_owner(h.native.target,m.b.run,m.b.source,m.m.images,parent=m.image,source_lock=m.b.lock)
            self.assertEqual([],m.commands);self.assertEqual([],m.transport.sent)

    def test_orphan_close_parent_original_manifest_or_chunk_keeps_base_cleanup_closed(self):
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        root=h.instance._script_journey().state_path(h.native.target).parent
        for name in ('snapshot-close-owner.json','snapshot-close-originals.json','snapshot-close-originals.json.frame-000.json'):
            path=root/name;path.write_text('{}');path.chmod(0o600)
            try:self.assertTrue(h.instance._snapshot_originals_owned(h.native.target))
            finally:path.unlink()


if __name__=='__main__':unittest.main()
