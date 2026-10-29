"""Actual immutable originals remain checked across an operation-local hit."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as original_scope
from ios.adapters import tablet_web_child_rotation as closed
from ios.adapters import tablet_web_rotation_fence as fence
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope
from ios.self_tests import test_ios_tablet_web_aggregate_root as fixture


class TabletParentGuardCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.TabletOwnedAggregateRootTests.setUpClass()
    def setUp(self):
        self.f=fixture.TabletOwnedAggregateRootTests();self.addCleanup(self.f.doCleanups)
        self.f.setUp();self.cache=TabletRecordCache()
        with scope(self.cache):self.owner=self.f.open()

    def test_same_scope_reuses_actual_immutable_proof_and_restores_exact_original_membership(self):
        monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
        monitor.use_tool_id(tool,'tablet-actual-parent-decoder');seen=[];code=closed.decode.__code__
        def call(_code,_offset):seen.append(_code)
        monitor.register_callback(tool,monitor.events.PY_START,call);monitor.set_local_events(tool,code,monitor.events.PY_START)
        try:
            calls=list(self.f.boundary.calls)
            with original_scope(fresh=True) as literal:self.owner._parent_guard()
            self.assertEqual(2,len(seen));seen.clear()
            with scope(self.cache),original_scope(fresh=True) as cached:self.owner._parent_guard()
            self.assertEqual([],seen);self.assertEqual(literal,cached)
            self.assertTrue(set(self.f.canonical_paths)<=cached)
            self.assertEqual(calls,self.f.boundary.calls);self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))
            # Two ordinary nine-query appends change the current root/child
            # WALs, while this Source3 proof still belongs to this same scope.
            with scope(self.cache):
                first_parts,first_row=self.f.capture(self.owner)
                second_parts,second_row=self.f.capture(self.owner)
                self.assertEqual([],seen)
                current=self.f.historical()
                # The new real owner must still initially validate its own
                # Source3 capsule, before it can borrow the immutable proof.
                self.assertEqual([code],seen);seen.clear()
                self.assertEqual(first_parts,current.frame_at(self.owner.state['records'][0])[1])
                self.assertEqual(second_parts,current.frame_at(self.owner.state['records'][1])[1])
            self.assertEqual((2,3),(first_row['index'],second_row['index']))
            self.assertEqual(calls+list(fixture.ORDER)*2,self.f.boundary.calls)
            self.assertEqual([],seen);self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))
        finally:
            monitor.set_local_events(tool,code,0);monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)

    def test_same_bytes_new_canonical_child_inode_refuses_warm_proof_without_requery(self):
        path=self.f.source.children['dom'].store.path;raw=path.read_bytes();before=path.stat();calls=list(self.f.boundary.calls)
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);outside=Path(tmp.name);outside.chmod(0o700)
        retained=outside/'original-child';os.replace(path,retained)
        with path.open('xb') as stream:stream.write(raw)
        path.chmod(0o600)
        self.assertEqual(raw,retained.read_bytes());self.assertEqual(before.st_ino,retained.stat().st_ino)
        self.assertNotEqual(before.st_ino,path.stat().st_ino)
        with scope(self.cache),self.assertRaises(NativeUIError):self.owner._parent_guard()
        self.assertEqual(calls,self.f.boundary.calls)

    def test_same_inode_changed_canonical_bytes_refuse_warm_proof_without_requery(self):
        path=self.f.source.children['dom'].store.path;before=path.stat();raw=path.read_bytes();calls=list(self.f.boundary.calls)
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);outside=Path(tmp.name);outside.chmod(0o700)
        retained=outside/'original-child-bytes';retained.write_bytes(raw);retained.chmod(0o600)
        path.write_bytes(raw[:-1]+(b' ' if raw[-1:]!=b' ' else b'\n'))
        self.assertEqual(before.st_ino,path.stat().st_ino)
        self.assertEqual(raw,retained.read_bytes())
        with scope(self.cache),self.assertRaises(NativeUIError):self.owner._parent_guard()
        self.assertEqual(calls,self.f.boundary.calls)

    def test_active_child_and_root_wal_checks_stay_outside_immutable_parent_hit(self):
        calls=list(self.f.boundary.calls);child=self.owner.children['dom'];before=child.store.read()
        changed=deepcopy(before);changed['pending']=dict(unclaimed=True);child.store.write(changed,before)
        with scope(self.cache):
            self.assertTrue(self.owner._parent_guard())
            with self.assertRaises(NativeUIError):child._bound()
        self.assertEqual(calls,self.f.boundary.calls)
        # Restore only our deliberately changed current WAL via its normal CAS,
        # then independently change the active root WAL under the same proof.
        child.store.write(before,changed);root=self.owner.store.read();other=deepcopy(root);other['pending']=dict(unclaimed=True)
        self.owner.store.write(other,root)
        with scope(self.cache):
            self.assertTrue(self.owner._parent_guard())
            with self.assertRaises(NativeUIError):self.owner.bound()
        self.assertEqual(calls,self.f.boundary.calls)

    def test_changed_expected_memory_and_parser_code_cannot_borrow_old_proof(self):
        calls=list(self.f.boundary.calls);expected=deepcopy(self.owner.expected)
        self.owner.expected['binding']['generation']+=1
        try:
            with scope(self.cache),self.assertRaises(NativeUIError):self.owner._parent_guard()
        finally:self.owner.expected=expected
        parser=fence._legacy;code=parser.__code__;defaults=parser.__defaults__
        def reject(raw,expected):raise NativeUIError('Actual changed parser')
        try:
            parser.__code__=reject.__code__
            with scope(self.cache),self.assertRaisesRegex(NativeUIError,'Actual changed parser'):self.owner._parent_guard()
        finally:
            parser.__code__=code;parser.__defaults__=defaults
            self.assertIs(parser.__code__,code);self.assertIs(parser.__defaults__,defaults)
        class OpaqueOrder:
            def __iter__(self):raise AssertionError('Metadata must not iterate an opaque codec policy')
        # The original literal decoder asks len(ORDER), which raises TypeError
        # for this object. Metadata must fall through before any __iter__ call.
        with patch.object(closed,'ORDER',OpaqueOrder()),scope(self.cache),self.assertRaises(TypeError):
            self.owner._parent_guard()
        self.assertEqual(calls,self.f.boundary.calls);self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))
