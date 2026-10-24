"""Pure query reuse retains real raw-file ownership and input distinctions.

SDK/native producers are explicit host models. These tests do not establish
real native freshness; inode-bound carriers are actually stored and reopened.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_clock_validation as validation
from ios.self_tests.test_ios_world_web_sample_clocks import WorldWebSampleClockTests


class WorldWebClockValidationTests(unittest.TestCase):
    def setUp(self):self.fixture=WorldWebSampleClockTests()

    def original(self,source,make):
        owner=make()
        with owner.owned():source.native.read(source.native.sequence)
        return owner,owner.rows(owner.state)

    def test_equal_pure_queries_reuse_only_inside_scope_and_results_do_not_alias(self):
        with self.fixture.owners() as (sdk,source,make):
            owner,rows=self.original(source,make)
            with patch.object(validation,'original_queries',wraps=validation.original_queries) as decoded:
                first=validation.queries(rows,sdk.pid);validation.queries(rows,sdk.pid)
                self.assertEqual(2,decoded.call_count)
                with validation.scope():
                    self.assertEqual(first,validation.queries(rows,sdk.pid))
                    returned=validation.queries(rows,sdk.pid);returned['processId']=999
                    with validation.scope():self.assertEqual(first,validation.queries(rows,sdk.pid))
                    self.assertEqual(3,decoded.call_count)
                self.assertEqual(first,validation.queries(rows,sdk.pid));self.assertEqual(4,decoded.call_count)

    def test_foreign_pid_nonce_and_changed_original_cannot_hit_an_earlier_success(self):
        with self.fixture.owners() as (sdk,source,make):
            owner,rows=self.original(source,make)
            with validation.scope():
                self.assertEqual(sdk.pid,validation.queries(rows,sdk.pid)['processId'])
                with self.assertRaises(NativeUIError):validation.queries(rows,sdk.pid+1)
                changed=deepcopy(rows);changed[0]['query']['commandId']='ios-'+'1'*32
                self.assertIsNone(validation.queries(changed,sdk.pid))
                changed=deepcopy(rows)
                import json
                packet=json.loads(changed[0]['raws'][0]);packet['processId']=sdk.pid+1
                changed[0]['raws'][0]=json.dumps(packet)
                with self.assertRaises(NativeUIError):validation.queries(changed,sdk.pid)
                self.assertEqual(sdk.pid,validation.queries(rows,sdk.pid)['processId'])

    def test_a_warm_pure_query_never_substitutes_for_actual_same_byte_inode_read(self):
        with self.fixture.owners() as (sdk,source,make):
            owner,rows=self.original(source,make)
            with validation.scope():
                actual=owner.last();self.assertEqual(sdk.pid,actual['processId'])
                reference=owner.state['entries'][0]['raws'][0]
                path=owner.frames.path(owner.frames.expand(reference));replacement=path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
                sent=len(sdk.native.commands)
                with self.assertRaises(NativeUIError):owner.last()
                self.assertEqual(sent,len(sdk.native.commands))

    def test_bounded_capacity_keeps_original_validation_when_no_entry_fits(self):
        with self.fixture.owners() as (sdk,source,make):
            owner,rows=self.original(source,make)
            with patch.object(validation,'MAX_BYTES',1),validation.scope(),patch.object(
                    validation,'original_queries',wraps=validation.original_queries) as decoded:
                first=validation.queries(rows,sdk.pid)
                self.assertEqual(first,validation.queries(rows,sdk.pid));self.assertEqual(2,decoded.call_count)
                self.assertEqual({},validation._ACTIVE.get()['entries'])
            with patch.object(validation,'MAX_ENTRIES',0),validation.scope(),patch.object(
                    validation,'original_queries',wraps=validation.original_queries) as decoded:
                first=validation.queries(rows,sdk.pid)
                self.assertEqual(first,validation.queries(rows,sdk.pid));self.assertEqual(2,decoded.call_count)
                self.assertEqual(0,validation._ACTIVE.get()['bytes'])

    def test_exception_exit_cannot_leave_a_reusable_query_scope(self):
        with self.fixture.owners() as (sdk,source,make):
            owner,rows=self.original(source,make)
            with patch.object(validation,'original_queries',wraps=validation.original_queries) as decoded:
                with self.assertRaises(OSError):
                    with validation.scope():
                        validation.queries(rows,sdk.pid);raise OSError('Controlled proof interruption')
                self.assertIsNone(validation._ACTIVE.get())
                with validation.scope():validation.queries(rows,sdk.pid)
                self.assertEqual(2,decoded.call_count)


if __name__=='__main__':unittest.main()
