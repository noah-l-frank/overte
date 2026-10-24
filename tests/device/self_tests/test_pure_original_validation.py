"""Pure-history reuse preserves literal types, bounds and parent identity."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_animation_history import validate
from adapters.native_feature_observation import validate as native
from adapters.normal_ui import NativeUIError
from adapters.pure_original_validation import scope,inherited_scope,returning_input,PROFILE
from self_tests.test_native_animation_history import AnimationHistoryTests
from ios.adapters.emote_native_prefix import follow


class PureOriginalValidationTests(unittest.TestCase):
    def source(self):
        source,reader=AnimationHistoryTests().source()
        return reader.read(0,require_animation_history=True)

    def test_explicit_nested_reuse_does_not_change_default_scope_isolation_or_escape(self):
        calls=[];guards=[];value=dict(original=7)
        def validate(value):calls.append(value);return value
        with scope(PROFILE,lambda:guards.append('outer')):
            returning_input(validate,value)
            with inherited_scope(PROFILE,lambda:guards.append('inner')):returning_input(validate,deepcopy(value))
            self.assertEqual(1,len(calls))
            with scope(PROFILE,lambda:None):returning_input(validate,value)
            self.assertEqual(2,len(calls));returning_input(validate,value);self.assertEqual(2,len(calls))
        returning_input(validate,value);self.assertEqual(3,len(calls))
        self.assertEqual(['outer','inner','inner','outer'],guards)

    def test_nested_failed_inventory_and_foreign_profile_cannot_borrow_a_success(self):
        packet=self.source();valid=[True]
        with scope(PROFILE,lambda:None):
            validate(packet['animation']['history'],packet['animation'],packet['capturedEpochMs'])
            with self.assertRaises(NativeUIError):
                with inherited_scope('foreign-profile',lambda:True):self.fail('Foreign scope entered')
            with self.assertRaises(NativeUIError):
                with inherited_scope(PROFILE,lambda:False):self.fail('Failed scope entered')
            with self.assertRaises(NativeUIError):
                with inherited_scope(PROFILE,lambda:valid[0]):
                    validate(packet['animation']['history'],packet['animation'],packet['capturedEpochMs']);valid[0]=False
            with inherited_scope(PROFILE,lambda:True):
                with self.assertRaises(NativeUIError):validate(packet['animation']['history'],packet['animation'],1)

    def test_an_explicitly_failed_inventory_guard_cannot_enable_or_complete_reuse(self):
        with self.assertRaises(NativeUIError):
            with scope(PROFILE,lambda:False):self.fail('A false original inventory enabled reuse')
        packet=self.source();valid=[True]
        with self.assertRaises(NativeUIError):
            with scope(PROFILE,lambda:valid[0]):
                validate(packet['animation']['history'],packet['animation'],packet['capturedEpochMs']);valid[0]=False

    def test_cached_history_cannot_accept_changed_epoch_tuple_or_mapping_subclass(self):
        packet=self.source();animation=packet['animation'];history=animation['history']
        class ForeignMapping(dict):pass
        class ForeignList(list):pass
        guards=[]
        with scope(PROFILE,lambda:guards.append(True)):
            self.assertIs(history,validate(history,animation,packet['capturedEpochMs']))
            self.assertIs(history,validate(history,animation,packet['capturedEpochMs']))
            for fault in ('tuple','list-subclass','mapping-subclass','epoch','animation-epoch','mutated-frame'):
                wrong=deepcopy(history);a=deepcopy(animation);epoch=packet['capturedEpochMs']
                if fault=='tuple':wrong['frames']=tuple(wrong['frames'])
                elif fault=='list-subclass':wrong['frames']=ForeignList(wrong['frames'])
                elif fault=='mapping-subclass':wrong['frames'][0]=ForeignMapping(wrong['frames'][0])
                elif fault=='epoch':epoch=1
                elif fault=='animation-epoch':a['capturedEpochMs']=1
                else:wrong['frames'][0]['joints'][0]['pose'][0]=9
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(wrong,a,epoch)
            with self.assertRaises(NativeUIError):native(packet,packet['requestId'],packet['processId']+1,packet['capturedEpochMs'])
        self.assertEqual(2,len(guards))

    def test_cached_original_pair_still_rejects_nonadvancing_or_retimed_native_prefix(self):
        source,reader=AnimationHistoryTests().source()
        before=reader.read(0,require_animation_history=True)
        after=reader.read(before['sequence'],require_animation_history=True)
        with scope(PROFILE,lambda:None):
            self.assertIsNone(follow(before,after));self.assertIsNone(follow(before,after))
            for fault in ('sequence','epoch','tuple'):
                wrong=deepcopy(after)
                if fault=='sequence':wrong['sequence']=before['sequence']
                elif fault=='epoch':wrong['requestedEpochMs']=before['capturedEpochMs']-1
                else:wrong['animation']['history']['frames']=tuple(wrong['animation']['history']['frames'])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):follow(before,wrong)


if __name__=='__main__':unittest.main()
