"""Physical original Process root ownership at the actual final delivery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from contextlib import contextmanager
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from self_tests import test_lifecycle_process_finalization as original


class LifecycleProcessPhysicalDeliveryTests(unittest.TestCase):
    def fixture(self):
        fixture=original.LifecycleProcessFinalizationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.owner.close_host)
        return fixture

    def test_same_bytes_replaced_final_root_cannot_deliver_warm_process_authority(self):
        fixture=self.fixture()
        owner=fixture.owner;save=owner.save;replaced=[]
        def replace(state):
            save(state)
            if state['phase']=='process-retired':
                path=owner.store.path;raw=path.read_bytes()
                backup=path.with_name('counter-original-final-process.json');backup.write_bytes(raw);backup.chmod(0o600)
                temporary=path.with_name('counter-replaced-final-process.json');temporary.write_bytes(raw);temporary.chmod(0o600)
                os.replace(temporary,path);replaced.append(True)
        with patch.object(owner,'save',side_effect=replace),self.assertRaises(NativeUIError):fixture.fixture.observe()
        self.assertEqual([True],replaced)
        self.assertEqual(owner.disk,owner.store.read())

    def test_actual_outer_lock_exit_root_replacement_cannot_deliver_original_memo(self):
        fixture=self.fixture();owner=fixture.owner;held=owner.lock.held;depth=0;replaced=[]
        @contextmanager
        def replaced_after_exit():
            nonlocal depth
            outer=depth==0;depth+=1
            try:
                with held():yield
            finally:depth-=1
            if outer and owner.state['phase']=='process-retired':
                path=owner.store.path;temporary=path.with_name('counter-exit-replacement.json')
                temporary.write_bytes(path.read_bytes());temporary.chmod(0o600);os.replace(temporary,path);replaced.append(True)
        def no_input():self.fail('Already issued original stop/launch cannot repeat')
        with patch.object(owner.lock,'held',replaced_after_exit),self.assertRaises(NativeUIError):
            original.process_module.run_lifecycle_restart(owner,no_input,lambda:fixture.source,
                no_input,no_input,no_input,lambda:None,fixture.fixture.observe)
        self.assertEqual([True],replaced)

    def test_final_reader_guard_root_replacement_is_checked_before_original_clocks(self):
        fixture=self.fixture();owner=fixture.owner;guard=fixture.source.guard;replaced=[]
        def changing():
            result=guard()
            if owner.state['phase']=='process-retired' and not replaced:
                path=owner.store.path;temporary=path.with_name('counter-guard-replacement.json')
                temporary.write_bytes(path.read_bytes());temporary.chmod(0o600);os.replace(temporary,path);replaced.append(True)
            return result
        with patch.object(fixture.source,'guard',changing),self.assertRaises(NativeUIError):fixture.fixture.observe()
        self.assertEqual([True],replaced)


if __name__=='__main__':unittest.main()
