"""Actual projection reads retain detached values, file guards and fallbacks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import sys
import unittest
from unittest.mock import patch
from adapters.original_file_reads import scope
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_snapshot_parts as source
from ios.self_tests.test_ios_world_web_snapshot_parts import WorldWebSnapshotPartsTests


class WorldWebProjectionCopyTests(unittest.TestCase):
    def setUp(self):
        WorldWebSnapshotPartsTests.setUp(self)
        self.parent=self.parts.write(1,self.batch.last)
        self.refs=self.parts.project(self.parent)

    def test_actual_warm_projection_uses_existing_copier_and_never_exposes_parent_aliases(self):
        monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
        monitor.use_tool_id(tool,'world-projection-copy');calls=[];code=source.clone_pair.__code__
        def called(_code,_offset):calls.append(_code)
        monitor.register_callback(tool,monitor.events.PY_START,called)
        monitor.set_local_events(tool,code,monitor.events.PY_START)
        try:
            with self.parts.validation_round():
                first=self.parts.read(self.refs['world']);expected=deepcopy(first)
                first['processId']=999
                self.assertEqual(expected,self.parts.read(self.refs['world']))
                self.assertEqual([code,code],calls)
        finally:
            monitor.set_local_events(tool,code,0)
            monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)

    def test_current_original_read_membership_and_same_byte_inode_checks_still_run(self):
        read=self.parts.read_bytes
        with patch.object(self.parts,'read_bytes',wraps=read) as actual:
            with self.parts.validation_round():
                expected=self.parts.read(self.refs['world']);self.assertEqual(1,actual.call_count)
                with scope(fresh=True) as reads:
                    self.assertEqual(expected,self.parts.read(self.refs['world']))
                    self.assertTrue(set(self.parts.paths(self.parent))<=reads)
                    self.assertEqual(2,actual.call_count)
        path=self.parts.paths(self.parent)[0];raw=path.read_bytes()
        with self.assertRaises(NativeUIError):
            with self.parts.validation_round():
                self.parts.read(self.refs['world'])
                replacement=path.with_suffix('.replacement')
                replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                self.parts.read(self.refs['keys'])

    def test_changed_copier_keeps_one_literal_call_and_the_original_exception(self):
        calls=[];failure=RuntimeError('original projection copier failure')
        def copier(value):calls.append(value);raise failure
        with self.parts.validation_round():
            self.parts.read(self.refs['world'])
            with patch.object(source,'deepcopy',copier):
                with self.assertRaises(RuntimeError) as caught:self.parts.read(self.refs['world'])
            self.assertIs(failure,caught.exception);self.assertEqual(1,len(calls))

    def test_changed_helper_alias_code_or_defaults_runs_only_literal_copy(self):
        def forbidden(*args,**kwargs):raise AssertionError('Changed helper was invoked')
        original=source.clone_pair;code=original.__code__;defaults=original.__defaults__
        with self.parts.validation_round():
            expected=self.parts.read(self.refs['world'])
            with patch.object(source,'clone_pair',forbidden):
                self.assertEqual(expected,self.parts.read(self.refs['world']))
            try:
                original.__code__=forbidden.__code__
                self.assertEqual(expected,self.parts.read(self.refs['world']))
                original.__code__=code;original.__defaults__=(None,)
                self.assertEqual(expected,self.parts.read(self.refs['world']))
            finally:original.__code__=code;original.__defaults__=defaults

    def test_whole_snapshot_two_selected_original_has_independent_detached_return(self):
        from ios.self_tests.world_web_whole_snapshot_fixture import WholeSnapshotNative
        from ios.adapters import world_web_whole_snapshot as whole
        native=WholeSnapshotNative();self.owner.version=5
        query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=whole.ACTION,runId=self.owner.run,fixtureUrl=self.owner.phase.fixture_url)
        native.send(query);parent=self.parts.write(2,native.last);refs=self.parts.project(parent)
        with self.parts.validation_round():
            first=self.parts.read(refs['surfaces']);expected=deepcopy(first)
            first['source']['surfaces'].clear()
            self.assertEqual(expected,self.parts.read(refs['surfaces']))
            self.assertTrue(self.parts.read(refs['surfaces'])['source']['surfaces'])

    def test_exact_graph_alias_cycles_unicode_and_unsupported_copy_hooks_keep_literal_behavior(self):
        shared=['\ud800','\U0001f600',-0.0];value=dict(left=shared,right=shared);value['self']=value
        result=source._detached_original(value)
        self.assertIs(result['left'],result['right']);self.assertIs(result,result['self'])
        self.assertIsNot(value,result);self.assertIsNot(shared,result['left']);self.assertEqual(shared,result['left'])
        calls=[]
        class Foreign:
            def __deepcopy__(self,memo):calls.append(self);return 'literal foreign copy'
        foreign=Foreign();self.assertEqual('literal foreign copy',source._detached_original(foreign));self.assertEqual([foreign],calls)
