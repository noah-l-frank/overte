"""Original return PNG+retirement and actual Pico factory; GPU/SDK are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_return_image import SnapshotReturnImageTests,ReturnBoundary
from adapters.pico4.script_journey import PicoScriptJourney
import test_normal_scripts as original


class SnapshotReturnImageFactoryTests(unittest.TestCase):
    def test_actual_factory_preserves_parent_lock_and_original_two_eye_capture_transport(self):
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        with tempfile.TemporaryDirectory(prefix='snapshot-return-factory-') as directory:
            root=Path(directory);root.chmod(0o700);m=ReturnBoundary(root);calls=[]
            def capture(target,**options):
                self.assertEqual(h.native.target,target);self.assertEqual(dict(read_only=True,role='primary',require_frame_view=True,source_lock=m.b.lock),options)
                calls.append('shared-original-world-render');return m.factory()
            with patch.object(PicoScriptJourney,'state_path',return_value=root/'state.json'),patch.object(h.instance,'_world_render_capture',side_effect=capture):
                owner=h.instance._snapshot_return_image(h.native.target,m.b.run,m.b.source,m.images,parent=m.bg,source_lock=m.b.lock)
                self.assertIs(owner.parent,m.bg);self.assertIs(owner.lock,m.b.lock);self.assertEqual([],calls)
                result=owner.acquire()
            self.assertTrue(result['originalStereoReturnPng']);self.assertEqual(['shared-original-world-render'],calls);self.assertIsNone(m.actual.owner.store.read())
            self.assertEqual([],list(m.native_root.iterdir()));self.assertEqual([],h.native.inputs);self.assertEqual([],h.native.controllers)

    def test_orphan_return_image_parent_manifest_or_chunk_blocks_base_cleanup(self):
        h=original.PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        root=h.instance._script_journey().state_path(h.native.target).parent
        for role in ('primary','actor'):
            for suffix in ('.json','-originals.json','-originals.json.frame-000.json'):
                path=root/('snapshot-return-image-'+role+suffix);path.write_text('{}');path.chmod(0o600)
                try:self.assertTrue(h.instance._snapshot_originals_owned(h.native.target))
                finally:path.unlink()


if __name__=='__main__':unittest.main()
