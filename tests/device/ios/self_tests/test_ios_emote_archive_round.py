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
from ios.adapters.emote_archive_round import scope,derived,component_read,validation_batch
from adapters.pure_original_validation import returning_input


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
                first=derived(self.owner,dict(index=1,sha256='a'*64),self.decode);first['actual']=99
                self.assertEqual(dict(actual=7),derived(self.owner,dict(index=1,sha256='a'*64),self.decode));self.assertEqual(1,self.calls)
            with scope(self.value,lock=self.lock,primary_lock=self.lock):
                self.assertEqual(dict(actual=7),derived(self.owner,dict(index=1,sha256='a'*64),self.decode));self.assertEqual(2,self.calls)
                self.owner.historical=False
                derived(self.owner,dict(index=1,sha256='a'*64),self.decode);derived(self.owner,dict(index=1,sha256='a'*64),self.decode)
                self.assertEqual(4,self.calls)

    def test_changed_original_and_new_unaccounted_file_cannot_borrow_prior_decode(self):
        with self.lock.held():
            for fault in ('changed','new-file'):
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                    with scope(self.value,lock=self.lock,primary_lock=self.lock):
                        derived(self.owner,dict(index=1,sha256='a'*64),self.decode)
                        if fault=='changed':self.file.write(dict(actual=8),self.file.read())
                        else:PrivateFeatureState(self.root/'unexpected.json').write(dict(actual=9),None)
                        derived(self.owner,dict(index=1,sha256='a'*64),self.decode)

    def test_current_component_decoder_runs_each_time_but_identical_pure_validation_is_scoped(self):
        self.owner.historical=False;self.owner.root=self.root;calls=[]
        def validate(value):calls.append(value);return value
        def current():
            for _ in range(2):
                derived(self.owner,dict(index=1,sha256='a'*64),self.decode)
                returning_input(validate,dict(original='same'))
            return dict(actual='current decoder returned')
        with self.lock.held():
            self.assertEqual(dict(actual='current decoder returned'),component_read(self.owner,dict(index=1,sha256='a'*64),current))
            self.assertEqual(2,self.calls);self.assertEqual(1,len(calls))
            component_read(self.owner,dict(index=1,sha256='a'*64),current)
            self.assertEqual(4,self.calls);self.assertEqual(2,len(calls))
            returning_input(validate,dict(original='same'));self.assertEqual(3,len(calls))

    def test_current_component_read_cannot_publish_a_result_after_metadata_changes(self):
        self.owner.historical=False;self.owner.root=self.root
        def changed():
            self.file.write(dict(actual=8),self.file.read());return dict(performed=True)
        with self.lock.held(),self.assertRaises(NativeUIError):
            component_read(self.owner,dict(index=1,sha256='a'*64),changed)

    def test_batch_reopens_each_snapshot_and_shares_only_pure_validation(self):
        validations=[]
        def validate(value):validations.append(value);return value
        with self.lock.held(),validation_batch(self.value,lock=self.lock,primary_lock=self.lock):
            for label in ('first-snapshot','second-snapshot'):
                with scope(dict(self.value,snapshot=label),lock=self.lock,primary_lock=self.lock):
                    self.assertEqual(dict(actual=7),derived(self.owner,dict(index=1,sha256='a'*64),self.decode))
                    returning_input(validate,dict(original=7))
            self.assertEqual(2,self.calls);self.assertEqual(1,len(validations))

    def test_batch_cannot_hide_a_change_between_separately_valid_snapshot_reads(self):
        with self.lock.held(),self.assertRaises(NativeUIError):
            with validation_batch(self.value,lock=self.lock,primary_lock=self.lock):
                with scope(dict(self.value,snapshot='first'),lock=self.lock,primary_lock=self.lock):
                    derived(self.owner,dict(index=1,sha256='a'*64),self.decode)
                self.file.write(dict(actual=8),self.file.read())
                with scope(dict(self.value,snapshot='second'),lock=self.lock,primary_lock=self.lock):
                    derived(self.owner,dict(index=1,sha256='a'*64),self.decode)

    def test_cached_reference_keeps_its_closed_literal_grammar(self):
        class ForeignMapping(dict):pass
        reference=dict(index=1,sha256='a'*64)
        with self.lock.held(),scope(self.value,lock=self.lock,primary_lock=self.lock):
            self.assertEqual(dict(actual=7),derived(self.owner,reference,self.decode))
            for wrong in (ForeignMapping(reference),dict(reference,index=True),dict(reference,index=1.),
                          dict(reference,sha256='A'*64),dict(reference,extra=1)):
                with self.subTest(reference=wrong),self.assertRaises(NativeUIError):derived(self.owner,wrong,self.decode)
            self.assertEqual(1,self.calls)


if __name__=='__main__':unittest.main()
