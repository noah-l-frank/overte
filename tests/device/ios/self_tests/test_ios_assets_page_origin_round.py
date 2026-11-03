"""Actual QML/current quiet frames and immutable originals, no native/device run.

Faults alter original bytes/inodes, current frames and synchronous scope
membership separately. No expected target state is used as an observation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import collect
from ios.adapters.assets_page_identity_round import PageIdentityRound
from ios.adapters.assets_page_picker import _window_eligible
from ios.self_tests.assets_shared_page_fixture import Fixture


class AssetsPageOriginRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture(self);self.scope=self.f.begin(1,format(1,'032x'));held=self.scope.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.picker=self.f.picker(self.scope);self.picker.open_page();self.picker.open_picker();self.picker.choose_primary();self.picker.cancel_owned();self.picker.retire_inputs()
        self.parent=self.f.page;self.window=self.picker.state['cleanupWindow'];self.state=self.picker.state
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Pure origin window cannot query/send/write')
    def origin_path(self):return self.parent.originals.path(self.parent.originals.expand(self.parent.state['origin']))
    def files(self):return {str(p):(p.stat().st_ino,p.read_bytes()) for root in self.f.h.roots.values() for p in root.rglob('*') if p.is_file()}
    def current(self):
        request=self.window['requests'][0];entry=next(row for row in self.picker.files.state['originals'] if row['query']['commandId']==request)
        return dict(inventory=deepcopy(entry['packet']['source']['ui']))
    def test_existing_full_window_reads_real_origin_and_current_frames_without_query_write_or_persistent_scope(self):
        self.assertTrue(_window_eligible(self.picker));before=self.files();fields=set(self.picker.__dict__)
        with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden),collect() as reads:
            frames=self.picker._window_validate(self.window,self.state,complete=True)
            self.assertEqual(self.window['requests'],[frame['requestId'] for frame in frames]);self.assertIn(self.origin_path(),reads)
            again=self.picker._window_validate(self.window,self.state,complete=True);self.assertEqual(frames,again)
        self.assertEqual(before,self.files());self.assertEqual(fields,set(self.picker.__dict__))
        with PageIdentityRound(self.picker,_window_eligible) as scope:self.assertTrue(scope.page(self.current(),self.state)['alive'])
        self.assertIsNone(scope.origin)
        with self.assertRaises(NativeUIError):scope.page(self.current(),self.state)
    def test_each_actual_current_frame_still_requires_exact_alive_visible_page_and_matching_model(self):
        with PageIdentityRound(self.picker,_window_eligible) as scope:
            current=self.current();self.assertTrue(scope.page(current,self.state)['alive'])
            for field,value in (('visible',False),('alive',False),('modelId','11111111-1111-4111-8111-111111111111')):
                changed=deepcopy(current);page=next(row for row in changed['inventory']['roots'] if row['rootId']==self.state['page']);page[field]=value
                with self.subTest(field=field),self.assertRaises(NativeUIError):scope.page(changed,self.state)
    def test_original_body_corruption_before_next_scope_is_never_hidden_by_a_previous_success(self):
        self.picker._window_validate(self.window,self.state,complete=True);path=self.origin_path();raw=path.read_bytes();path.write_bytes(raw+b' ')
        with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):
            with self.assertRaises(NativeUIError):self.picker._window_validate(self.window,self.state,complete=True)
    def test_samebytes_foreign_origin_inode_during_scope_refuses_on_exit_and_cannot_be_reused(self):
        path=self.origin_path();raw=path.read_bytes()
        with self.assertRaises(NativeUIError):
            with PageIdentityRound(self.picker,_window_eligible) as scope:
                scope.page(self.current(),self.state);path.rename(path.with_name('retained-origin-before-foreign-inode'));path.write_bytes(raw);path.chmod(0o600)
        self.assertFalse(scope.active);self.assertIsNone(scope.origin)
        with self.assertRaises(NativeUIError):self.picker._window_validate(self.window,self.state,complete=True)
    def test_namespace_orphan_or_metadata_mutation_during_scope_refuses_without_qualifying_membership(self):
        orphan=self.parent.store.path.with_name('assets-page-lease-unknown-window-source')
        with self.assertRaises(NativeUIError):
            with PageIdentityRound(self.picker,_window_eligible) as scope:
                scope.page(self.current(),self.state);orphan.write_bytes(b'unknown owned-looking source');orphan.chmod(0o600)
        orphan.unlink();value=self.parent.store.read();changed=deepcopy(value);changed['unowned']='foreign'
        with self.assertRaises(NativeUIError):
            with PageIdentityRound(self.picker,_window_eligible) as scope:
                scope.page(self.current(),self.state);self.parent.store.write(changed,value)
        self.assertFalse(scope.active);self.assertIsNone(scope.origin)
    def test_changed_cleanup_hook_uses_literal_callback_and_mutation_of_scoped_origin_is_rejected(self):
        original=self.picker.cleanup_page;calls=[]
        def second(current,state):calls.append('second');return original(current,state)
        def first(current,state):
            calls.append('first');self.picker.cleanup_page=second;return original(current,state)
        with patch.object(self.picker,'cleanup_page',side_effect=first):
            self.assertFalse(_window_eligible(self.picker));frames=self.picker._window_validate(self.window,self.state,complete=True)
            self.assertGreaterEqual(len(frames),2);self.assertEqual(['first']+['second']*(len(frames)-1),calls)
        with self.assertRaises(NativeUIError):
            with PageIdentityRound(self.picker,_window_eligible) as scope:
                scope.origin['visible']=False;scope.page(self.current(),self.state)
        self.assertFalse(scope.active);self.assertIsNone(scope.origin)


if __name__=='__main__':unittest.main()
