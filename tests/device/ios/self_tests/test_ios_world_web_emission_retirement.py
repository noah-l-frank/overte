"""Actual host weak queue holders, with explicit Qt/native boundary models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_emission_retirement import drained
from ios.self_tests.test_ios_web_script_emissions import Emitter


class WorldWebEmissionRetirementTests(unittest.TestCase):
    def test_actual_pending_copy_blocks_until_its_real_weak_expiry_without_fabricated_callback_return(self):
        native=Emitter();call=native.api(surface='world');row,life=native.queue(call,route='world-surface');native.leave(call)
        with self.assertRaises(NativeUIError):drained(native.snapshot(),call['target'],native.buttons.manager,native.buttons.code)
        del life;gc.collect();value=native.snapshot()
        self.assertIsNone(value['queues'][0]['entered']);self.assertIsNone(value['queues'][0]['returned'])
        self.assertEqual([call['id']],drained(value,call['target'],native.buttons.manager,native.buttons.code))

    def test_unknown_caller_does_not_inherit_vm_but_actual_owned_entity_queue_still_must_drain(self):
        native=Emitter();call=native.api(surface='world',qualified=False);row,life=native.queue(call,route='world-surface');native.leave(call)
        with self.assertRaises(NativeUIError):drained(native.snapshot(),call['target'],native.buttons.manager,native.buttons.code)
        del life;gc.collect();value=native.snapshot();self.assertIsNone(value['calls'][0]['caller'])
        self.assertEqual([call['id']],drained(value,call['target'],native.buttons.manager,native.buttons.code))

    def test_unknown_world_queue_and_actual_unreturned_api_remain_owned(self):
        native=Emitter();row,life=native.queue(None,route='world-surface')
        with self.assertRaises(NativeUIError):drained(native.snapshot(),None,native.buttons.manager,native.buttons.code)
        del life;gc.collect();self.assertEqual([],drained(native.snapshot(),None,native.buttons.manager,native.buttons.code))
        call=native.api(surface='world');native.leave(call,exception=True)
        with self.assertRaises(NativeUIError):drained(native.snapshot(),call['target'],native.buttons.manager,native.buttons.code)


if __name__=='__main__':unittest.main()
