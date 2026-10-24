"""Historical memo cannot hide changed files or cache current responsibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_archive_round import scope,derived


class ArchiveRoundTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.root.chmod(0o700);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.value=dict(artifactRoot=str(self.root),stateRoot=str(self.root))
        self.file=PrivateFeatureState(self.root/'original.json');self.file.write(dict(actual=7),None)
        self.owner=SimpleNamespace(historical=True,lock=self.lock,primary_lock=self.lock,store=self.file,
            envelope=lambda state:dict(testOriginalContext=1))
        self.calls=0

    def decode(self):self.calls+=1;return self.file.read()

    def test_same_actual_historical_record_reuses_only_inside_one_unchanged_round(self):
        with self.lock.held():
            with scope(self.value,lock=self.lock,primary_lock=self.lock):
                first=derived(self.owner,dict(index=1),self.decode);first['actual']=99
                self.assertEqual(dict(actual=7),derived(self.owner,dict(index=1),self.decode));self.assertEqual(1,self.calls)
            with scope(self.value,lock=self.lock,primary_lock=self.lock):
                self.assertEqual(dict(actual=7),derived(self.owner,dict(index=1),self.decode));self.assertEqual(2,self.calls)
                self.owner.historical=False
                derived(self.owner,dict(index=1),self.decode);derived(self.owner,dict(index=1),self.decode)
                self.assertEqual(4,self.calls)

    def test_changed_original_and_new_unaccounted_file_cannot_borrow_prior_decode(self):
        with self.lock.held():
            for fault in ('changed','new-file'):
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                    with scope(self.value,lock=self.lock,primary_lock=self.lock):
                        derived(self.owner,dict(index=1),self.decode)
                        if fault=='changed':self.file.write(dict(actual=8),self.file.read())
                        else:PrivateFeatureState(self.root/'unexpected.json').write(dict(actual=9),None)
                        derived(self.owner,dict(index=1),self.decode)


if __name__=='__main__':unittest.main()
