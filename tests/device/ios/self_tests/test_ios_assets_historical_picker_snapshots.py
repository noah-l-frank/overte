"""Actual historical Picker/Page originals with scope-local interpretation reuse.

The original QML producer supplies one real host-model page attachment. No
native/SDK query, file recovery or complete end is authorized by these reads.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import sys
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import collect,scope as original_read_scope
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata
from ios.adapters.assets_historical_picker_snapshots import historical_picker_snapshots,physical
from ios.adapters.assets_page_lease import OwnedAssetsPageLease
from ios.adapters.assets_page_ownership import skeleton,inspect_page,AssetsPageInventoryContext
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters import assets_controls
from ios.self_tests.assets_shared_page_fixture import Fixture


class AssetsHistoricalPickerSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture(self);self.scope=self.f.begin(1,format(1,'032x'))
        held=self.scope.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.picker=self.f.picker(self.scope);self.picker.open_page()
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Historical snapshot read cannot query or write')
    def files(self):
        return {str(path):(path.stat().st_ino,path.read_bytes()) for root in self.f.h.roots.values() for path in root.rglob('*') if path.is_file()}
    def metadata(self):return RecordingAssetsMetadata(owned=self.f.selected.owned_paths(),selection=self.f.selected)
    def origin(self):return self.f.page.originals.path(self.f.page.originals.expand(self.f.page.state['origin']))
    @contextmanager
    def archived(self):
        view=self.metadata();pickers={1:skeleton(self.scope,view)}
        with historical_picker_snapshots(self.f.episodes,pickers,view) as memo:
            owner=OwnedAssetsPageLease.from_archive(self.f.episodes,self.f.page.store,self.f.page.lock,pickers,snapshot_scope=memo)
            yield owner,pickers[1],memo
    def count_decodes(self,call):
        self.assertIsNone(sys.getprofile());calls=[];code=OwnedAssetsPicker.decode.__code__
        def observe(frame,event,arg):
            if event=='call' and frame.f_code is code:calls.append(1)
        sys.setprofile(observe)
        try:return call(),len(calls)
        finally:sys.setprofile(None)
    def test_same_actual_original_graph_has_fewer_snapshot_interpretations_with_equal_membership_and_literal_default(self):
        before=self.files();view=self.metadata();pickers={1:skeleton(self.scope,view)}
        def literal():return OwnedAssetsPageLease.from_archive(self.f.episodes,self.f.page.store,self.f.page.lock,pickers)
        with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):
            with collect() as literal_reads:(legacy,literal_count)=self.count_decodes(literal)
            def scoped():
                with self.archived() as (owner,picker,memo):
                    self.assertTrue(memo.cache);self.assertIs(owner.snapshot_scope,memo)
                    # Duplicate current/record snapshots are physically reread.
                    for ref in owner.state['records']:owner.read(ref)
                    return owner,memo
            with collect() as current_reads:((current,memo),current_count)=self.count_decodes(scoped)
        self.assertLess(current_count,literal_count);self.assertEqual(legacy.state,current.state)
        self.assertEqual(literal_reads,current_reads);self.assertEqual(before,self.files())
        self.assertFalse(memo.active);self.assertEqual({},memo.cache);self.assertIsNone(current.snapshot_scope)
        self.assertIsNone(legacy.snapshot_scope)
        # The returned owner remains an ordinary literal historical decoder.
        current.read(current.state['origin'])
        with patch('ios.adapters.assets_historical_picker_snapshots.monotonic',side_effect=(0.,6.)):
            with self.assertRaises(NativeUIError):physical(self.origin())
    def test_changed_original_body_between_duplicate_reads_is_not_hidden_by_a_previous_snapshot(self):
        with self.assertRaises(NativeUIError):
            with self.archived() as (owner,picker,memo):
                self.assertTrue(memo.cache);path=self.origin();path.write_bytes(path.read_bytes()+b' ')
                owner.read(owner.state['origin'])
        self.assertFalse(memo.active);self.assertEqual({},memo.cache)
    def test_samebytes_foreign_original_inode_cannot_reuse_the_prior_interpretation(self):
        with self.assertRaises(NativeUIError):
            with self.archived() as (owner,picker,memo):
                path=self.origin();raw=path.read_bytes();path.rename(path.with_name('retained-before-foreign-inode'))
                path.write_bytes(raw);path.chmod(0o600);owner.read(owner.state['origin'])
        self.assertFalse(memo.active);self.assertIsNone(owner.snapshot_scope)
    def test_new_namespace_entry_between_duplicate_reads_retains_unknown_membership_duty(self):
        with self.assertRaises(NativeUIError):
            with self.archived() as (owner,picker,memo):
                orphan=picker.store.path.with_name('assets-page-lease-unknown-original');orphan.write_bytes(b'unknown');orphan.chmod(0o600)
                owner.read(owner.state['origin'])
        self.assertTrue(orphan.exists());self.assertFalse(memo.active)
    def test_mutated_owner_header_or_decoded_context_cannot_inherit_a_prior_snapshot_result(self):
        with self.assertRaises(NativeUIError):
            with self.archived() as (owner,picker,memo):
                with original_read_scope(fresh=True):
                    with self.assertRaises(NativeUIError):owner.read(owner.state['origin'])
                original_run=picker.files.run;picker.files.run='f'*32
                with self.assertRaises(NativeUIError):owner.read(owner.state['origin'])
                picker.files.run=original_run
                value=picker.files.store.read();changed=deepcopy(value);changed['foreign']='changed'
                picker.files.store.write(changed,value);owner.read(owner.state['origin'])
        self.assertFalse(memo.active)
    def test_custom_decode_hook_keeps_dynamic_literal_dispatch_and_no_snapshot_scope(self):
        view=self.metadata();pickers={1:skeleton(self.scope,view)};picker=pickers[1];original=picker.decode;calls=[]
        def second(value):calls.append('second');return original(value)
        def first(value):calls.append('first');picker.decode=second;return original(value)
        picker.decode=first
        with historical_picker_snapshots(self.f.episodes,pickers,view) as memo:
            self.assertIsNone(memo)
            owner=OwnedAssetsPageLease.from_archive(self.f.episodes,self.f.page.store,self.f.page.lock,pickers,snapshot_scope=memo)
        self.assertGreater(len(calls),1);self.assertEqual(['first']+['second']*(len(calls)-1),calls)
        self.assertIsNone(owner.snapshot_scope)

    def test_changed_real_component_suffix_global_refuses_old_snapshot_and_new_namespace_member_uses_literal(self):
        with self.archived() as (owner,picker,memo):
            self.assertTrue(memo.cache);packet=deepcopy(picker.previous)
            with patch.dict(assets_controls.SUFFIXES,{'page':'/foreign/ChangedComponent.qml'}):
                # Same function/code/source bytes; only a real used parser
                # global changed. Literal refuses this original component.
                with self.assertRaises(NativeUIError):picker.decode(packet)
                with self.assertRaises(NativeUIError):owner.decode_picker_snapshot(picker,packet)
                self.assertFalse(memo.enabled);self.assertEqual({},memo.cache)
        with self.archived() as (owner,picker,memo):
            self.assertTrue(memo.cache)
            with patch.object(assets_controls,'added_snapshot_policy_member',object(),create=True):
                (state,count)=self.count_decodes(lambda:owner.decode_picker_snapshot(picker,picker.previous))
                self.assertEqual(1,count);self.assertEqual(picker.state,state)
                self.assertFalse(memo.enabled);self.assertEqual({},memo.cache)


if __name__=='__main__':unittest.main()
