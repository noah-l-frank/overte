"""Exact pure arguments can repeat; file/counter/nonce checks cannot disappear."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as actual_reads
from ios.adapters import tablet_web_native_semantics as semantics,tablet_web_sources as sources
from ios.self_tests.test_ios_tablet_web_sources import packet,query
from ios.self_tests import test_ios_tablet_web_packets as packets_tests


class TabletNativeSemanticTests(unittest.TestCase):
    def test_all_nine_actual_standalone_validators_are_pure_under_selected_scope(self):
        from ios.adapters.tablet_web_packets import COMPONENTS
        from ios.self_tests.tablet_web_history_fixture import frame
        value,_=frame();keys=dict(trace='ledger',dom='document',uikit='touches',emissions='emitter');memo=semantics.TabletNativeSemantics()
        with semantics.scope(memo),patch('builtins.open',side_effect=AssertionError('Native semantic validator performed I/O')),patch('os.open',side_effect=AssertionError('Native semantic validator performed descriptor I/O')):
            for name,module in COMPONENTS.items():
                for _ in range(2):semantics.checked(module,'original',value[keys.get(name,name)])
        self.assertEqual(9,len(memo.entries))
    def test_actual_native_validator_repeats_only_for_identical_all_arguments_and_rejects_new_birth_or_nonce(self):
        first,second=packet(),packet(2);memo=semantics.TabletNativeSemantics()
        with patch.object(sources,'validate',wraps=sources.validate) as validator,semantics.scope(memo):
            semantics.checked(sources,'original',first);count=validator.call_count
            semantics.checked(sources,'original',deepcopy(first));self.assertEqual(count,validator.call_count)
            semantics.checked(sources,'validate',second,query(2),31,first);count=validator.call_count
            semantics.checked(sources,'validate',deepcopy(second),deepcopy(query(2)),31,deepcopy(first));self.assertEqual(count,validator.call_count)
            for fault in ('birth','counter','pid','pid-type','query','bool'):
                changed=deepcopy(second);requested=query(2);pid=31
                if fault=='birth':changed['instance']='0'*32
                elif fault=='counter':changed['sequence']=1
                elif fault=='pid':pid=42
                elif fault=='pid-type':pid=31.0
                elif fault=='query':requested=query(3)
                else:changed['sequence']=True
                for _ in range(2):
                    before=validator.call_count
                    with self.assertRaises(NativeUIError):semantics.checked(sources,'validate',changed,requested,pid,first)
                    self.assertGreater(validator.call_count,before)
    def test_default_noop_nested_context_and_exception_exit_never_share_an_unselected_cache(self):
        memo=semantics.TabletNativeSemantics();body=packet()
        with patch.object(sources,'validate',wraps=sources.validate) as validator:
            semantics.checked(sources,'original',body);semantics.checked(sources,'original',body);self.assertEqual(2,validator.call_count)
            with semantics.scope(memo):
                semantics.checked(sources,'original',body);semantics.checked(sources,'original',body);self.assertEqual(3,validator.call_count)
                with semantics.scope(semantics.TabletNativeSemantics()):semantics.checked(sources,'original',body)
                semantics.checked(sources,'original',body);self.assertEqual(4,validator.call_count)
            semantics.checked(sources,'original',body);self.assertEqual(5,validator.call_count)
            with self.assertRaises(InterruptedError),semantics.scope(memo):raise InterruptedError('Actual selected scope interrupted')
            semantics.checked(sources,'original',body);self.assertEqual(6,validator.call_count)
    def test_exact_argument_byte_and_item_bounds_evict_without_changing_native_limits(self):
        memo=semantics.TabletNativeSemantics();native_limit=sources.LIMIT
        with patch.object(semantics,'MAX_ITEMS',2),semantics.scope(memo):
            for index in range(1,5):semantics.checked(sources,'original',packet(index))
            self.assertEqual(2,len(memo.entries));self.assertLessEqual(memo.bytes,semantics.MAX_BYTES)
        memo=semantics.TabletNativeSemantics()
        with patch.object(semantics,'MAX_BYTES',10),semantics.scope(memo):semantics.checked(sources,'original',packet())
        self.assertEqual(0,memo.bytes);self.assertFalse(memo.entries);self.assertEqual(native_limit,sources.LIMIT)
    def test_real_original_file_read_membership_and_hardlink_rejection_remain_under_native_memo(self):
        fixture=packets_tests.TabletWebPacketsTests('test_actual_queries_and_raw_bytes_reconstruct_with_new_reader_and_unchanged_callbacks')
        fixture.setUp();self.addCleanup(fixture.doCleanups);memo=semantics.TabletNativeSemantics()
        with semantics.scope(memo):
            owner=fixture.owner();owner.capture(fixture.reader())
            with actual_reads(fresh=True) as first:fixture.owner().history()
            with actual_reads(fresh=True) as second:fixture.owner().history()
            self.assertTrue(first);self.assertEqual(first,second)
            ref=owner.originals.expand(owner.state['records'][0]);path=owner.originals.path(ref)
            import os
            os.link(path,fixture.root/'unowned-alias')
            with self.assertRaises(NativeUIError):fixture.owner()
    def test_historical_original_guard_permits_reading_but_cannot_issue_or_write_new_ownership(self):
        fixture=packets_tests.TabletWebPacketsTests('test_actual_queries_and_raw_bytes_reconstruct_with_new_reader_and_unchanged_callbacks')
        fixture.setUp();self.addCleanup(fixture.doCleanups);live=fixture.owner();packet_=live.capture(fixture.reader());before=len(fixture.sends)
        files={path.name:path.read_bytes() for path in fixture.root.iterdir() if path.is_file()}
        def forbidden():raise AssertionError('Historical decoder attempted live guard/SDK access')
        historical=packets_tests.TabletWebPackets(fixture.root,packets_tests.BINDING,packets_tests.RUN,'primary',packets_tests.ROOT,31,'sources',forbidden,historical=True)
        self.assertEqual([packet_],historical.history())
        with self.assertRaises(NativeUIError):historical.capture(fixture.reader())
        with self.assertRaises(NativeUIError):historical.save()
        self.assertEqual(before,len(fixture.sends));self.assertEqual(files,{path.name:path.read_bytes() for path in fixture.root.iterdir() if path.is_file()})


if __name__=='__main__':unittest.main()
