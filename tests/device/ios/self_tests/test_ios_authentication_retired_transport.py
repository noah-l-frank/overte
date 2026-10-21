"""A retired synthetic process cannot consume a late HTTP transport failure."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import Future
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ios.self_tests.authentication_native_boundary import Native
from self_tests.test_native_account_observation import append,event


class RetiredTransportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.opener=Mock();self.opener.open.side_effect=AssertionError('No HTTP request is allowed in this SDK consumer test')
        self.native=Native(Path(temporary.name),'https://sdk.invalid:49121',self.opener)
        self.addCleanup(self.native.close)

    def future(self,*,result=None,error=None,done=True):
        future=Future()
        if done:
            if error is not None:future.set_exception(error)
            else:future.set_result(result)
        self.native.tasks.append((future,self.native.birth,self.native.account['observation']['credentialGeneration']))
        return future

    def test_normal_process_replacement_discards_old_transport_failure_and_unparsed_body(self):
        self.future(error=TimeoutError('Synthetic retired TLS read timeout'))
        self.future(result=(200,b'unparsed retired response'))
        self.native.lifecycle_input('app.stop');self.native.lifecycle_input('app.launch')
        original=deepcopy(self.native.account);self.native.poll()
        self.assertEqual(original,self.native.account);self.assertEqual([],self.native.tasks)
        self.assertEqual(43,self.native.pid);self.assertEqual(['app.stop','app.launch'],self.native.lifecycle_inputs)
        self.opener.open.assert_not_called()

    def test_stopped_process_does_not_consume_its_completed_transport_error(self):
        self.future(error=TimeoutError('Synthetic reply after process stop'));self.native.lifecycle_input('app.stop')
        original=deepcopy(self.native.account);self.native.poll()
        self.assertFalse(self.native.running);self.assertEqual(original,self.native.account);self.assertEqual([],self.native.tasks)

    def test_replaced_credential_generation_cannot_consume_old_error_in_the_same_process(self):
        self.future(error=TimeoutError('Synthetic reply after credential retirement'))
        append(self.native.account,event(kind='logout-complete',epoch=self.native.epoch(),generation=2))
        original=deepcopy(self.native.account);self.native.poll()
        self.assertEqual(original,self.native.account);self.assertEqual([],self.native.tasks)
        self.assertEqual(42,self.native.pid)

    def test_current_process_transport_error_remains_a_failure_without_account_adoption(self):
        self.future(error=TimeoutError('Synthetic current TLS failure'));original=deepcopy(self.native.account)
        with self.assertRaises(TimeoutError):self.native.poll()
        self.assertEqual(original,self.native.account);self.assertIsNone(self.native.token)
        self.assertEqual(1,len(self.native.tasks))

    def test_retired_pending_transport_is_kept_until_settled_then_discarded_without_new_process_effect(self):
        future=self.future(done=False);self.native.lifecycle_input('app.stop');self.native.lifecycle_input('app.launch')
        original=deepcopy(self.native.account);self.native.poll();self.assertEqual(1,len(self.native.tasks))
        future.set_exception(TimeoutError('Synthetic late retired transport failure'));self.native.poll()
        self.assertEqual([],self.native.tasks);self.assertEqual(original,self.native.account)
        self.opener.open.assert_not_called()


if __name__=='__main__':unittest.main()
