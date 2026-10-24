"""Original final-save/report/lock edges; native and OS producers are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_process as process_module
from adapters.pico4.lifecycle_world_codec import unpack as process_unpack
from self_tests import test_pico_lifecycle_process as fixture


class LifecycleProcessFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.LifecycleProcessTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        temp=self.fixture.fixture.temporary;temp._finalizer.detach()
        temp.cleanup=lambda:print('Original final-fence files retained in '+temp.name,flush=True)
        self.fixture.shutdown();self.fixture.new_process();self.owner=self.fixture.process
        self.source=self.fixture.new_source

    def late_device(self):
        clock=self.source.clock_ms;self.source.clock_ms=lambda:clock()+2000

    def test_landed_final_save_cannot_return_success_after_native_clock_jump_with_frozen_host(self):
        save=self.owner.save;fired=[]
        def delayed(state):
            result=save(state)
            if state['phase']=='process-retired':fired.append(True);self.late_device()
            return result
        with patch.object(self.owner,'save',side_effect=delayed),self.assertRaises(NativeUIError):self.fixture.observe()
        self.assertEqual([True],fired);disk=self.owner.store.read()
        self.assertEqual('process-retired',process_unpack(disk['payload'],disk['lifecycleProcessOwnerVersion'])[0]['phase'])
        self.assertTrue(self.owner.inputs.store.read() is not None)
        # A landed history is not a fresh result, and observed app inputs are
        # never repeated to hide the failed delivery. No cached-success path.
        with self.assertRaises(NativeUIError):self.fixture.observe()

    def test_actual_final_report_build_precedes_last_native_clock_check(self):
        original=dict;fired=[]
        def build(*args,**kwargs):
            result=original(*args,**kwargs)
            if result.get('processOwnedScopesRetired') is True:fired.append(True);self.late_device()
            return result
        with patch.object(process_module,'dict',build,create=True),self.assertRaises(NativeUIError):self.fixture.observe()
        self.assertEqual([True],fired)

    def test_new_process_source_guard_is_rechecked_after_landed_final_save(self):
        guard=self.source.guard;fired=[]
        def lost():
            if self.owner.state['phase']=='process-retired':
                fired.append(True);raise NativeUIError('Explicit new process loss after landed save')
            return guard()
        with patch.object(self.source,'guard',side_effect=lost),self.assertRaises(NativeUIError):self.fixture.observe()
        self.assertEqual([True],fired)

    def test_actual_outer_source_lock_exit_is_inside_final_delivery_age(self):
        original=self.owner.lock.held;depth=0;fired=[]
        @contextmanager
        def held():
            nonlocal depth
            outer=depth==0;depth+=1
            try:
                with original():yield
            finally:depth-=1
            if outer and self.owner.state['phase']=='process-retired':fired.append(True);self.late_device()
        def no_input():self.fail('Already launched app inputs must not be repeated')
        with patch.object(self.owner.lock,'held',held),self.assertRaises(NativeUIError):
            process_module.run_lifecycle_restart(self.owner,no_input,lambda:self.source,
                no_input,no_input,no_input,lambda:None,self.fixture.observe)
        self.assertEqual([True],fired)


if __name__=='__main__':unittest.main()
