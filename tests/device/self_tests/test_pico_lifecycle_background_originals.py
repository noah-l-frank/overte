"""Lossless source scaling and unresolved original child/root boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_originals import LifecycleBackgroundOriginals
from adapters.pico4.lifecycle_back import frame
from adapters.script_journey.history import pack
from self_tests.test_pico_lifecycle_back import BINDING
from self_tests.test_pico_lifecycle_source import RUN


class LifecycleBackgroundOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lifecycle-bg-originals-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.path=self.root/'lifecycle-background-originals.json';self.owner=self.make()
    def make(self):return LifecycleBackgroundOriginals(self.path,RUN,BINDING)
    def test_complete_random_joint_originals_cross_flat_bound_and_reconstruct_exact_original_bytes(self):
        rng=random.Random(654);rows=[frame(json.dumps(dict(sequence=index,explicitSyntheticOriginalJoints=[rng.random() for _ in range(1792)]),indent=1)) for index in range(40)]
        with self.assertRaises(NativeUIError):pack(rows)
        encoded=self.owner.encode(dict(sources=rows,duplicate=rows[0]));manifest=self.owner.manifest
        self.assertEqual(40,len(manifest));self.assertEqual(rows,self.owner.decode(encoded)['sources'])
        cold=self.make();self.assertEqual(manifest,cold.manifest);self.assertEqual(dict(sources=rows,duplicate=rows[0]),cold.decode(encoded))
        self.assertTrue(all(path.stat().st_size<=65536 and path.stat().st_mode&0o777==0o600 for path in self.root.iterdir()))
    def test_missing_rewritten_foreign_and_permission_changed_originals_cannot_become_fresh_sources(self):
        for fault in ('missing','rewritten','foreign','permissions'):
            with self.subTest(fault=fault):
                self.setUp();self.owner.encode([frame('{"original": 1}')]);child=self.owner.history.store(0)
                if fault=='missing':child.path.unlink()
                elif fault=='permissions':child.path.chmod(0o644)
                else:
                    old=child.read();changed=deepcopy(old)
                    if fault=='foreign':changed['scopeSha256']='f'*64
                    else:changed['transcript']=pack([frame('{"original": 2}')])
                    child.write(changed,old)
                with self.assertRaises(NativeUIError):self.owner.verify()
                with self.assertRaises(NativeUIError):self.make()
    def test_lost_child_manifest_write_is_not_adopted_retried_or_removed(self):
        write=self.owner.root.write;calls=0
        def lost(value,previous):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('Explicit lost original manifest persistence')
            return write(value,previous)
        with patch.object(self.owner.root,'write',side_effect=lost),self.assertRaises(OSError):self.owner.encode([frame('{"original":1}')])
        self.assertTrue(self.owner.history.store(0).path.exists())
        with self.assertRaises(NativeUIError):self.owner.verify()
        with self.assertRaises(NativeUIError):self.make()
    def test_deleted_root_and_same_named_foreign_run_do_not_adopt_original_children(self):
        self.owner.encode([frame('{"original":1}')]);self.path.unlink()
        with self.assertRaises(NativeUIError):self.make()
        with self.assertRaises(NativeUIError):LifecycleBackgroundOriginals(self.path,'b'*32,BINDING)
    def test_wrong_reference_hash_and_larger_raw_bound_fail_without_overwrite(self):
        encoded=self.owner.encode([frame('{"original":1}')]);encoded[0]['sha256']='f'*64
        with self.assertRaises(NativeUIError):self.owner.decode(encoded)
        before=self.owner.manifest
        with self.assertRaises(NativeUIError):self.owner.encode([frame('x'*262145)])
        self.assertEqual(before,self.owner.manifest);self.owner.verify()


if __name__=='__main__':unittest.main()
