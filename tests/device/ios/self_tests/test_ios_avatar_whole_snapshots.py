"""Large exact whole metadata stays outside bounded journals and keeps inodes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import secrets
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.avatar_whole_snapshots import AvatarWholeSnapshots
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarWholeSnapshotsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.store=PrivateFeatureState(self.root/'whole-test.json');self.entries=[];self.transitions=[];self.fail=None
    def save(self):
        self.transitions.append(deepcopy(self.entries[-1]))
        if self.fail==('before',self.entries[-1]['phase']):raise OSError('Lost metadata save before return')
        self.store.write(dict(payload=pack([dict(snapshots=self.entries)])),self.store.read())
        if self.fail==('after',self.entries[-1]['phase']):raise OSError('Lost durable metadata return')
    def owner(self):return AvatarWholeSnapshots(self.root,BINDING,'a'*32,'primary',lambda:self.entries,lambda:True,self.save)
    def rebuild(self):self.entries=unpack(self.store.read()['payload'])[0]['snapshots'];self.fail=None;return self.owner()

    def test_actual_large_snapshot_has_a_small_journal_and_same_private_inode(self):
        value=dict(originalOwnerData=secrets.token_hex(100000))
        with self.assertRaises(NativeUIError):pack([value])
        owner=self.owner();reference=owner.retain(value)
        self.assertEqual(['planned','opened','saved'],[row['phase'] for row in self.transitions]);self.assertLess(self.store.path.stat().st_size,65536)
        self.assertEqual(value,owner.read(reference));self.assertEqual(reference,self.rebuild().retain(value));self.assertEqual(3,len(self.transitions))
        path=owner.originals.path(self.entries[0]);self.assertEqual(0o600,path.stat().st_mode&0o777);self.assertGreater(path.stat().st_size,200000)

    def test_lost_saved_return_adopts_the_exact_original_without_a_new_write(self):
        value=dict(actualOwner='unchanged');self.fail=('after','saved');owner=self.owner()
        with self.assertRaises(OSError):owner.retain(value)
        prior=len(self.transitions);rebuilt=self.rebuild();reference=rebuilt.retain(value)
        self.assertEqual(prior,len(self.transitions));self.assertEqual(1,reference['index']);self.assertEqual(value,rebuilt.read(reference))

    def test_complete_opened_original_is_read_without_promoting_the_old_write_phase(self):
        value=dict(actualOwner='unchanged');self.fail=('before','saved');owner=self.owner()
        with self.assertRaises(OSError):owner.retain(value)
        rebuilt=self.rebuild();before=self.store.path.read_bytes();reference=rebuilt.retain(value)
        self.assertEqual(1,reference['index']);self.assertEqual('opened',self.entries[0]['phase']);self.assertEqual(before,self.store.path.read_bytes())
        self.assertEqual(value,rebuilt.read(reference))

    def test_unwritten_owned_inode_remains_separate_and_replacement_refuses_reconstruction(self):
        value=dict(actualOwner='future');self.fail=('after','opened');owner=self.owner()
        with self.assertRaises(OSError):owner.retain(value)
        original=deepcopy(self.entries[0]);path=owner.originals.path(original);inode=path.stat().st_ino;self.assertEqual(b'',path.read_bytes())
        rebuilt=self.rebuild();reference=rebuilt.retain(value);self.assertEqual(2,reference['index']);self.assertEqual(inode,path.stat().st_ino)
        path.unlink();path.write_bytes(b'');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.rebuild().retain(value)


if __name__=='__main__':unittest.main()
