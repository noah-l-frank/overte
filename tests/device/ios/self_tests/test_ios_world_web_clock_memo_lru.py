"""Bounded pure reuse policy; actual raw owners remain authoritative models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
from pathlib import Path
from types import MethodType
import unittest,weakref
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters import original_marker_clock_queries as literal
from ios.adapters import world_web_clock_validation as memo
from ios.self_tests.test_ios_world_web_source_clock_query_memo import WorldWebSourceClockQueryMemoTests
from ios.self_tests.test_ios_world_web_sample_clocks import WorldWebSampleClockTests


class ClockMemoLRUTests(unittest.TestCase):
    def setUp(self):self.fixture=WorldWebSampleClockTests()
    original=WorldWebSourceClockQueryMemoTests.original
    original_calls=WorldWebSourceClockQueryMemoTests.original_calls
    def variant(self,rows,index,*,large=False):
        value=deepcopy(rows)
        # JSON whitespace is raw input identity, never a retimed native fact.
        # Its valid native payload still comes from the original host producer.
        padding=(min(120000,literal.LIMIT-len(value[0]['raws'][0])-1024) if large else 0)+index
        self.assertGreaterEqual(padding,0)
        value[0]['raws'][0]=' '*padding+value[0]['raws'][0]
        return value
    def checked(self):
        cache=memo._ACTIVE.get();self.assertLessEqual(cache['bytes'],8*1024*1024)
        self.assertLessEqual(len(cache['entries']),512)
        self.assertEqual(len(cache['entries']),len(cache['costs']))
        self.assertEqual(cache['bytes'],sum(cache['costs'].values()))
        return cache

    def test_real_byte_saturation_admits_and_reuses_gpu_after_source_prefill(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                for index in range(80):memo.source_queries(self.variant(rows,index,large=True),sdk.pid)
                cache=self.checked();self.assertLess(len(cache['entries']),80)
                value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(1,calls)
                again,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(value,again);self.assertEqual(0,calls)
                self.checked()

    def test_real_entry_saturation_keeps512_without_increasing_either_limit(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);rows=deepcopy(rows[:1]);rows[0]['raws']=['{}']
            with memo.scope():
                for index in range(513):self.assertIsNone(memo.source_queries(self.variant(rows,index),sdk.pid,strict=False))
                self.assertEqual(512,len(self.checked()['entries']))
                value,calls=self.original_calls(lambda:memo.source_queries(self.variant(rows,512),sdk.pid,strict=False))
                self.assertIsNone(value);self.assertEqual(0,calls)
                _value,calls=self.original_calls(lambda:memo.source_queries(self.variant(rows,0),sdk.pid,strict=False));self.assertEqual(1,calls)
                self.checked()

    def test_recently_used_old_entry_survives_while_untouched_neighbor_is_evicted(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);rows=deepcopy(rows[:1]);rows[0]['raws']=['{}']
            with memo.scope():
                for index in range(512):memo.source_queries(self.variant(rows,index),sdk.pid,strict=False)
                _value,calls=self.original_calls(lambda:memo.source_queries(self.variant(rows,0),sdk.pid,strict=False));self.assertEqual(0,calls)
                memo.source_queries(self.variant(rows,512),sdk.pid,strict=False)
                _value,calls=self.original_calls(lambda:memo.source_queries(self.variant(rows,0),sdk.pid,strict=False));self.assertEqual(0,calls)
                _value,calls=self.original_calls(lambda:memo.source_queries(self.variant(rows,1),sdk.pid,strict=False));self.assertEqual(1,calls)
                self.checked()

    def test_oversized_rejected_input_never_flushes_a_valid_warm_entry(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid);before=dict(self.checked()['costs'])
                changed=deepcopy(rows);changed[0]['raws'][0]=' '*(8*1024*1024+1)+changed[0]['raws'][0]
                with self.assertRaises(NativeUIError):memo.source_queries(changed,sdk.pid)
                self.assertEqual(before,self.checked()['costs'])
                value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(0,calls)

    def test_detached_missing_cost_ledger_cannot_adopt_or_mutate_cached_results(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid);cache=self.checked();old=dict(cache['entries']);cache['costs']={}
                value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                self.assertEqual(old,cache['entries']);self.assertEqual({},cache['costs'])
                _value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(1,calls)
                self.assertEqual(old,cache['entries'])
                opaque_calls=[]
                class OpaqueKey:
                    def __hash__(self):opaque_calls.append('hash');return 7
                    def __eq__(self,other):opaque_calls.append('equality');raise AssertionError('Opaque policy key compared')
                    def __repr__(self):opaque_calls.append('repr');raise AssertionError('Opaque policy key formatted')
                key=OpaqueKey();cache.update(entries={key:expected},costs={key:1},bytes=1)
                opaque_calls.clear()
                value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                _value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(1,calls)
                self.assertEqual([],opaque_calls)

    def test_mixed_domains_lru_never_exports_an_alias_to_source_or_gpu_payload(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                source_value=memo.source_queries(rows,sdk.pid);gpu=memo.queries(rows,sdk.pid)
                source_value['processId']=999;gpu['animation'].clear()
                actual=memo.source_queries(rows,sdk.pid);again=memo.queries(rows,sdk.pid)
                self.assertEqual(sdk.pid,actual['processId']);self.assertEqual(actual,again)
                self.checked()

    def test_replaced_policy_helpers_fall_back_before_any_foreign_callable(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid)
                for name in ('_memo_key','_memo_state','_memo_get','_memo_store','_memo_valid','_memo_enabled'):
                    with self.subTest(helper=name),patch.object(memo,name,side_effect=AssertionError('Foreign policy executed')) as foreign:
                        value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                        value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                        foreign.assert_not_called()
                with patch.object(memo,'_MEMO_FUNCTIONS',()):
                    value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                    value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)

    def test_same_function_foreign_bound_receiver_is_not_a_policy_epoch(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);actual=memo._memo_get
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid)
                with patch.object(memo,'_memo_get',MethodType(actual,object())):
                    value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                    value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)

    def test_replaced_iteration_builtins_refuse_without_opaque_invocation(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid)
                for name in ('iter','next','all','bytes'):
                    with self.subTest(alias=name),patch.object(memo,name,create=True,side_effect=AssertionError('Opaque policy alias executed')) as foreign:
                        value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                        value,calls=self.original_calls(lambda:memo.queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                        foreign.assert_not_called()

    def test_actual_original_root_membership_still_refuses_after_warm_policy(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);source.capture('lru-membership')
            mutable=PrivateFeatureState(source.store.path.with_name('lru-absent-input.json'))
            with memo.scope(),self.assertRaises(NativeUIError),source.input_round(mutable):
                memo.source_queries(rows,sdk.pid)
                orphan=source.store.path.parent/'unowned-lru-original.json';orphan.write_text('{}');orphan.chmod(0o600)
                source.guard_originals()
            self.assertIsNone(source._round)

    def test_actual_same_byte_original_inode_still_refuses_with_mixed_cache_domains(self):
        with self.fixture.owners() as (sdk,source,make):
            owner,rows=self.original(source,make)
            with memo.scope():
                memo.source_queries(rows,sdk.pid);memo.queries(rows,sdk.pid)
                reference=owner.state['entries'][0]['raws'][0];path=owner.frames.path(owner.frames.expand(reference))
                raw=path.read_bytes();inode=path.stat().st_ino;replacement=path.with_suffix('.replacement')
                replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                self.assertEqual(raw,path.read_bytes());self.assertNotEqual(inode,path.stat().st_ino)
                before=len(sdk.native.commands)
                with self.assertRaises(NativeUIError):owner.last()
                self.assertEqual(before,len(sdk.native.commands))

    def test_rejected_opaque_input_is_not_retained_or_touched_by_policy(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);calls=[]
            class Product:
                def __deepcopy__(self,memo):calls.append('copy');raise AssertionError('Opaque product copied')
                def __repr__(self):calls.append('repr');raise AssertionError('Opaque product repr')
            product=Product();reference=weakref.ref(product);changed=deepcopy(rows);changed[0]['raws'].append(product)
            with memo.scope():
                memo.source_queries(rows,sdk.pid)
                with self.assertRaises(NativeUIError):memo.source_queries(changed,sdk.pid)
                del product,changed;gc.collect();self.assertIsNone(reference());self.assertEqual([],calls)
                self.checked()


if __name__=='__main__':unittest.main()
