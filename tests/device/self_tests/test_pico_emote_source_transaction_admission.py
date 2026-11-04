"""Actual existing Cold/Cycle/Policy/Raw admission; declared SDK/Qt leaves.

No new native collector is executed. This is profile selection, old source
baseline and budget/refusal proof, not SourceTxn/Common28/copy-capacity proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import unittest
from contextlib import ExitStack

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_source_transaction_profile import PicoEmoteSourceProfile,SLOT
from self_tests.pico_emote_cold_factory_fixture import ColdModel

RETAINED=[]


class SourceAdmissionTests(unittest.TestCase):
    def setUp(self):self.model=ColdModel();self.addCleanup(self.finalize)

    def finalize(self):
        m=self.model
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for root in m.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();m.close();after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(roots=[str(root) for root in m.roots],files=after))

    def held(self):
        stack=ExitStack();stack.enter_context(self.model.m.s.lock.held());stack.enter_context(self.model.actor_lock.held());return stack

    def test_actual_profile_is_charged_before_first_sdk_and_policy3_keeps_both_original_epochs(self):
        m=self.model;profile=PicoEmoteSourceProfile();before=[]
        with self.held():
            cycle=m.cold(source_profile=profile)
            self.assertEqual([],m.cold_calls);self.assertEqual(2,cycle.capacity.identity['picoEmoteStreamCapacityVersion'])
            def pre_sdk(role,args):
                original=cycle.originals;raw=original.archive
                self.assertEqual(3,cycle.policy.version);self.assertIs(profile,cycle.capacity.source_profile)
                self.assertEqual(3,raw.scope['picoEmoteStreamOriginalsVersion'])
                self.assertEqual(2,raw.scope['picoEmoteSourcePhysicalVersion'])
                self.assertEqual(profile.sha256,raw.scope['sourceProfileSha256'])
                bill=original.other_bill();required=profile.extra_bill()
                self.assertGreaterEqual(bill['storedBytes'],required['storedBytes'])
                self.assertGreaterEqual(bill['decodedBytes'],required['decodedBytes'])
                self.assertGreaterEqual(required['storedBytes'],SLOT)
                before.append(role)
            m.before_sdk=pre_sdk;cycle.parent.baseline();m.before_sdk=None
            self.assertTrue(before);self.assertEqual({'primary','actor'},set(before))
            self.assertEqual(cycle.parent.state['started'],cycle.policy.started)
            self.assertEqual(cycle.parent.state['started']+120,cycle.policy.deadline)
            self.assertEqual(1,cycle.policy.disk['policies']['primary'].count('"sourceTransactionEnabled":1'))
            self.assertEqual(1,cycle.policy.disk['policies']['actor'].count('"sourceTransactionEnabled":0'))
            self.assertEqual(512,cycle.policy.disk['totalNativeFrameAllowance'])
            self.assertTrue(cycle.parent.source.frames) # Existing real Source2 acquisition, not new Native collector.

    def test_two_role_slots_fail_actual_cold_before_any_sdk_or_source_getter(self):
        m=self.model;profile=PicoEmoteSourceProfile(('primary','actor'))
        with self.held():
            events={role:list(sdk.events) for role,sdk in m.sdks.items()};calls=m.process_calls
            with self.assertRaises((ValueError,NativeUIError)):m.cold(canonical=True,source_profile=profile)
            self.assertEqual(events,{role:list(sdk.events) for role,sdk in m.sdks.items()})
            self.assertEqual(calls,m.process_calls);self.assertEqual([],m.cold_calls)
            self.assertEqual([],m.m.input.inputs);self.assertEqual([],m.m.input.controllers);self.assertIsNone(m.cycle)

    def test_default_none_keeps_original_policy2_scope2_and_no_source_profile(self):
        m=self.model
        with self.held():
            cycle=m.cold();cycle.parent.baseline()
            self.assertIsNone(cycle.capacity.source_profile);self.assertEqual(1,cycle.capacity.identity['picoEmoteStreamCapacityVersion'])
            self.assertEqual(2,cycle.policy.version);self.assertEqual(2,cycle.originals.archive.scope['picoEmoteStreamOriginalsVersion'])
            self.assertNotIn('sourceProfileSha256',cycle.capacity.identity)
            self.assertNotIn('picoEmoteSourcePhysicalVersion',cycle.originals.archive.scope)
            self.assertNotIn('sourceWireFileBytes',cycle.policy.disk['policies']['primary'])


if __name__=='__main__':unittest.main()
