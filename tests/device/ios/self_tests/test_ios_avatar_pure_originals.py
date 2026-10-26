"""Pure historical DTO reuse never replaces actual frame I/O or live guards.

Codec packets and current/native clocks are explicit test-boundary models.
Call counts use Python profiling of real code, without replacing a validator.
Actual Scene inventory/lock and retained-graph checks are separate qualifications.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.pure_original_validation import scope,AVATAR_PROFILE
from ios.adapters import avatar_state,avatar_renderers
from ios.self_tests.test_ios_avatar_state import packet as state_packet
from ios.self_tests.test_ios_avatar_renderers import packet as renderer_packet


class AvatarPureOriginalTests(unittest.TestCase):
    def packets(self):return ((avatar_state,state_packet()),(avatar_renderers,renderer_packet()))
    def count(self,profile,codec):return sum(row.callcount for row in profile.getstats() if row.code is codec._original.__code__)
    def test_repeated_identical_original_returns_each_callers_input_only_inside_guarded_round(self):
        for codec,packet in self.packets():
            with self.subTest(codec=codec.__name__):
                second=deepcopy(packet);profile=cProfile.Profile()
                with scope(AVATAR_PROFILE,lambda:True):
                    profile.enable()
                    try:
                        self.assertIs(packet,codec.original(packet));self.assertIs(second,codec.original(second))
                    finally:profile.disable()
                self.assertEqual(1,self.count(profile,codec));self.assertIsNot(packet,second)
                outside=cProfile.Profile();outside.enable()
                try:codec.original(packet);codec.original(second)
                finally:outside.disable()
                self.assertEqual(2,self.count(outside,codec))
    def test_changed_literal_packet_revalidates_and_cannot_borrow_a_malformed_success(self):
        for codec,packet in self.packets():
            with self.subTest(codec=codec.__name__),scope(AVATAR_PROFILE,lambda:True):
                codec.original(packet);profile=cProfile.Profile();changed=deepcopy(packet);changed['sequence']+=1
                profile.enable()
                try:self.assertIs(changed,codec.original(changed))
                finally:profile.disable()
                self.assertEqual(1,self.count(profile,codec))
                changed['sequence']=True
                with self.assertRaises(NativeUIError):codec.original(changed)
                class Foreign(dict):pass
                with self.assertRaises(NativeUIError):codec.original(Foreign(packet))
    def test_current_freshness_and_previous_native_prefix_guards_always_execute(self):
        for codec,packet in self.packets():
            query=dict(schemaVersion=1,commandId=packet['requestId'],action=codec.ACTION,runId=packet['runId'])
            with self.subTest(codec=codec.__name__),scope(AVATAR_PROFILE,lambda:True):
                codec.original(packet);codec.original(deepcopy(packet))
                with self.assertRaises(NativeUIError):
                    codec.validate(packet,query,packet['processId'],packet['clockAfter']['epochMs']+10000)
                with self.assertRaises(NativeUIError):codec.validate(packet,query,packet['processId'],previous=packet)
    def test_mutating_the_returned_caller_packet_does_not_restore_a_cached_packet(self):
        for codec,packet in self.packets():
            with self.subTest(codec=codec.__name__),scope(AVATAR_PROFILE,lambda:True):
                original=codec.original(packet);self.assertIs(packet,original);original['sequence']=True
                with self.assertRaises(NativeUIError):codec.original(packet)


if __name__=='__main__':unittest.main()
