"""Historical-only prefix reuse counters; synthetic packets, no device proof."""
from contextlib import contextmanager
from copy import deepcopy
import sys

from adapters.normal_ui import NativeUIError
from adapters.pure_original_validation import PROFILE,scope
from ios.adapters import graphics_history as current
from ios.self_tests.test_ios_graphics_history import NativePrefixTests,original
from self_tests.test_native_feature_observation import Boundary


@contextmanager
def actual_body_starts():
    monitor=sys.monitoring;code=current._follow_native.__code__
    free=[tool for tool in (2,5,4,3,1,0)if monitor.get_tool(tool)is None]
    assert free and sys.getprofile()is None and sys.gettrace()is None
    tool=free[0];name='emote-graphics-prefix-actual-body-counter';calls=[]
    def observed(actual,offset):
        assert actual is code;calls.append(actual)
    monitor.use_tool_id(tool,name)
    try:
        monitor.register_callback(tool,monitor.events.PY_START,observed)
        monitor.set_local_events(tool,code,monitor.events.PY_START)
        yield calls
    finally:
        assert monitor.get_tool(tool)==name
        monitor.set_local_events(tool,code,0)
        monitor.register_callback(tool,monitor.events.PY_START,None)
        monitor.free_tool_id(tool)
        assert monitor.get_tool(tool)is None


class EmoteGraphicsPrefixPureScopeTests(NativePrefixTests):
    # The two existing NativePrefixTests bodies remain inherited unchanged.
    def packets(self):
        boundary=Boundary();boundary.mutate=original
        reader=boundary.reader(ios=True,native_clock_bound=True)
        before=reader.read(0);after=reader.read(reader.sequence)
        return boundary,before,after

    def test_actual_body_reuse_requires_explicit_scope_and_never_escapes_it(self):
        boundary,before,after=self.packets();saved=deepcopy((before,after));commands=len(boundary.commands);guards=[]
        with actual_body_starts()as calls:
            self.assertIsNone(current.follow_native(before,after))
            self.assertIsNone(current.follow_native(before,after));self.assertEqual(2,len(calls))
            with scope(PROFILE,lambda:guards.append('actual-modeled-inventory-guard')):
                self.assertIsNone(current.follow_native(before,after))
                self.assertIsNone(current.follow_native(deepcopy(before),deepcopy(after)))
                self.assertEqual(3,len(calls))
            self.assertIsNone(current.follow_native(before,after));self.assertEqual(4,len(calls))
        self.assertEqual(2,len(guards));self.assertEqual(commands,len(boundary.commands));self.assertEqual(saved,(before,after))

    def test_warm_success_cannot_admit_changed_history_identity_or_foreign_types(self):
        boundary,before,after=self.packets();saved=deepcopy((before,after));commands=len(boundary.commands)
        class ForeignMapping(dict):pass
        with actual_body_starts()as calls,scope(PROFILE,lambda:True):
            self.assertIsNone(current.follow_native(before,after));self.assertIsNone(current.follow_native(before,after))
            self.assertEqual(1,len(calls))
            for fault in ('account','voice','animation','rewrite','sequence','birth','nonce','tuple','mapping-subclass'):
                wrong=deepcopy(after)
                if fault=='account':wrong['account'].pop('observation')
                elif fault=='voice':wrong['audio'].pop('recordedVoice')
                elif fault=='animation':wrong['animation']={}
                elif fault=='rewrite':wrong['audio']['recordedVoice']['events'][0]['publishedEpochMs']-=1
                elif fault=='sequence':wrong['sequence']=before['sequence']
                elif fault=='birth':wrong['instance']='f'*32
                elif fault=='nonce':wrong['requestId']=before['requestId']
                elif fault=='tuple':wrong['animation']['history']['frames']=tuple(wrong['animation']['history']['frames'])
                else:wrong=ForeignMapping(wrong)
                count=len(calls)
                for attempt in (1,2):
                    with self.subTest(fault=fault,attempt=attempt),self.assertRaises(NativeUIError):current.follow_native(before,wrong)
                    self.assertEqual(count+attempt,len(calls))
            self.assertIsNone(current.follow_native(before,after));self.assertEqual(19,len(calls))
        self.assertEqual(commands,len(boundary.commands));self.assertEqual(saved,(before,after))

    def test_failed_inventory_entry_or_exit_never_qualifies_a_cached_success(self):
        boundary,before,after=self.packets();commands=len(boundary.commands);valid=[True]
        with actual_body_starts()as calls:
            with self.assertRaises(NativeUIError):
                with scope(PROFILE,lambda:False):self.fail('False inventory entered scope')
            self.assertEqual([],calls)
            with self.assertRaises(NativeUIError):
                with scope(PROFILE,lambda:valid[0]):
                    self.assertIsNone(current.follow_native(before,after))
                    self.assertIsNone(current.follow_native(before,after));self.assertEqual(1,len(calls))
                    valid[0]=False
            self.assertIsNone(current.follow_native(before,after));self.assertEqual(2,len(calls))
        self.assertEqual(commands,len(boundary.commands))
