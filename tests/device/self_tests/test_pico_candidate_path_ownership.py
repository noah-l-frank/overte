"""Real local inode topology and live candidate callbacks; no device or build."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from adapters.pico4.candidate_read_seal import CandidateReadSeal, stamp


class CandidatePathOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='pico-candidate-topology-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parent = self.root / 'original-parent'
        self.parent.mkdir()
        self.path = self.parent / 'original'
        self.path.write_bytes(b'original verified bytes')
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.metadata = {'argument': 'original'}

    def seal(self, path, inventory=None):
        result = CandidateReadSeal(inventory or (lambda: {str(path): self.digest}),
            lambda: dict(self.metadata), {'verified': ['original']})
        self.addCleanup(result.close)
        return result

    def test_parent_symlink_cannot_retain_authority_through_the_same_leaf_inode(self):
        seal = self.seal(self.path)
        before = stamp(self.path.stat())
        moved = self.root / 'moved-parent'
        self.parent.rename(moved)
        self.parent.symlink_to(moved, target_is_directory=True)
        self.assertEqual(before, stamp(self.path.stat()))
        with self.assertRaises(ValueError):
            seal.check()
        self.parent.unlink()
        moved.rename(self.parent)
        with self.assertRaises(ValueError):
            seal.check()

    def test_admitted_alias_is_live_but_cannot_adopt_a_changed_canonical_name(self):
        alias = self.root / 'admitted-alias'
        alias.symlink_to(self.parent, target_is_directory=True)
        path = alias / self.path.name
        seal = self.seal(path)
        self.assertEqual({'verified': ['original']}, seal.check())
        before = stamp(path.stat())
        moved = self.root / 'moved-parent'
        self.parent.rename(moved)
        self.parent.symlink_to(moved, target_is_directory=True)
        self.assertEqual(before, stamp(path.stat()))
        with self.assertRaises(ValueError):
            seal.check()

    def test_inventory_side_effect_cannot_bypass_the_final_metadata_check(self):
        armed = False
        def inventory():
            if armed:
                self.metadata['argument'] = 'changed during inventory'
            return {str(self.path): self.digest}
        seal = self.seal(self.path, inventory)
        armed = True
        with self.assertRaises(ValueError):
            seal.check()
        self.metadata['argument'] = 'original'
        armed = False
        with self.assertRaises(ValueError):
            seal.check()

    def test_unlinked_original_descriptor_does_not_admit_a_new_named_original(self):
        seal = self.seal(self.path)
        descriptor = seal.rows[0][2]
        self.path.unlink()
        self.path.write_bytes(b'original verified bytes')
        self.assertNotEqual(os.fstat(descriptor).st_ino, self.path.stat().st_ino)
        with self.assertRaises(ValueError):
            seal.check()


if __name__ == '__main__':
    unittest.main(verbosity=2)
