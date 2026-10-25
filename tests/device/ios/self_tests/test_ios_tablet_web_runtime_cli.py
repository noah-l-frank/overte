"""Actual runtime continuity across CLI host lives, explicit host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_tablet_web_runtime as runtime_tests


class TabletRuntimeCLIAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=runtime_tests.TabletWebRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def test_next_cli_keeps_original_bootstrap_but_uses_new_actual_host_and_verified_observation(self):
        with self.fixture.opened() as observer:
            original=deepcopy(observer.bootstrap.state);host=observer.admission['hostProcessId']
        fixture=self.fixture.fixture.admission.fixture;fixture.make().verify();count=len(self.fixture.fixture.native.commands)
        with patch('os.getpid',return_value=host+100000),self.fixture.opened() as observer:
            self.assertEqual(original,observer.bootstrap.state);self.assertEqual(host+100000,observer.admission['hostProcessId'])
            self.assertEqual(observer.admission,observer.observer.source.admission)
        self.assertEqual(count,len(self.fixture.fixture.native.commands))
    def test_actual_inflight_guard_accepts_forward_verify_then_rejects_original_record_rollback(self):
        fixture=self.fixture.fixture.admission.fixture
        with self.fixture.opened() as observer:
            before=fixture.store.read();fixture.make().verify();self.assertTrue(observer.check())
            current=fixture.store.read();fixture.store.write(before,current)
            with self.assertRaises(NativeUIError):observer.check()
            fixture.store.write(current,before)

    def test_historical_role_reconstruction_never_creates_native_or_sdk_authority(self):
        import traceback
        failure=None
        with self.fixture.opened() as observer:
            try:
                source=observer.observer.source;before={path.name:path.read_bytes() for path in source.root.iterdir() if path.is_file()}
                with patch.object(self.fixture.runtime,'_existing',side_effect=AssertionError('Historical decoder queried SDK')):
                    history=self.fixture.runtime.historical_observer('private-existing-selector',source.run,source.role,source.binding,
                        observer.bootstrap.setup,observer.observer.origins,source.lock,fixture_url=source.fixture,monotonic=lambda:0.)
                    self.assertTrue(history.observer.source.historical)
                    with self.assertRaises(NativeUIError):history.tail_source()
                    with self.assertRaises(NativeUIError):history.read_auxiliary('native')
                self.assertEqual(before,{path.name:path.read_bytes() for path in source.root.iterdir() if path.is_file()})
            except Exception:failure=traceback.format_exc()
        if failure:self.fail(failure)


if __name__=='__main__':unittest.main()
