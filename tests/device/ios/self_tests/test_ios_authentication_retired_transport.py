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

    def test_current_network_failure_settles_once_as_original_native_login_failure(self):
        from urllib.error import URLError
        from http.client import RemoteDisconnected
        for error in (TimeoutError('Synthetic current TLS failure'),URLError('Synthetic current network failure'),RemoteDisconnected('Synthetic EOF')):
            with self.subTest(error=type(error).__name__):
                future=self.future(error=error);generation=self.native.account['observation']['credentialGeneration']
                self.native.account['observation']['loginPending']=True;self.native.login.waiting=True
                self.native.poll();obs=self.native.account['observation'];events=deepcopy(obs['events'])
                self.assertFalse(obs['loginPending']);self.assertFalse(self.native.login.waiting)
                self.assertEqual(['login-reply','login-failed'],[e['kind'] for e in events[-2:]])
                self.assertEqual(0,events[-2]['httpStatus']);self.assertNotEqual(0,events[-2]['networkError'])
                self.assertFalse(events[-2]['timedOut']);self.assertEqual(generation,events[-2]['credentialGeneration'])
                self.assertIsNone(self.native.token);self.assertFalse(self.native.account['loggedIn'])
                self.assertNotIn(future,self.native.task_started);self.assertEqual([],self.native.tasks)
                self.native.poll();self.assertEqual(events,self.native.account['observation']['events'])

    def test_original_native_absolute_timer_expires_at_fifteen_virtual_seconds(self):
        future=self.future(done=False);self.native.task_started[future]=self.native.clock
        self.native.account['observation']['loginPending']=True;self.native.login.waiting=True
        self.native.clock+=14.999;self.native.poll();self.assertTrue(self.native.account['observation']['loginPending'])
        self.assertFalse(self.native.account['observation']['events'])
        self.native.clock+=.001;self.native.poll();obs=self.native.account['observation'];events=deepcopy(obs['events'])
        self.assertFalse(obs['loginPending']);self.assertEqual(0,events[-2]['httpStatus'])
        self.assertEqual(5,events[-2]['networkError']);self.assertTrue(events[-2]['timedOut'])
        self.assertEqual(['login-reply','login-failed'],[e['kind'] for e in events])
        self.assertEqual(1,len(self.native.tasks));self.assertIn(future,self.native.finished_tasks)
        self.native.clock+=2;self.native.poll();self.assertEqual(events,self.native.account['observation']['events'])
        future.set_result((200,b'unparsed late timed-out grant'));self.native.poll()
        self.assertEqual([],self.native.tasks);self.assertFalse(self.native.finished_tasks)
        self.assertEqual(events,self.native.account['observation']['events']);self.assertIsNone(self.native.token)
        self.assertFalse(self.native.account['loggedIn']);self.opener.open.assert_not_called()

    def test_real_loopback_socket_guard_does_not_replace_original_native_deadline(self):
        self.native.login.fields.update({'login.username':'test-only','login.password':'test-only'})
        self.native.shown=True;self.native.login.dialog=True
        row=next(r for r in self.native.observed()['controls'] if r['id']=='login.submit')
        key='test-submit';self.native.references[key]=('OverteNavigation.login.submit',row['token'])
        from concurrent.futures import Future
        from unittest.mock import patch
        future=Future()
        with patch.object(self.native.executor,'submit',return_value=future) as submit:
            self.native.call('POST','/session/owned-session/element/'+key+'/click')
        self.assertEqual(90,submit.call_args.kwargs['timeout'])
        self.assertEqual(self.native.clock,self.native.task_started[future])
        self.native.clock+=15;self.native.poll()
        self.assertTrue(self.native.account['observation']['events'][-2]['timedOut'])
        future.set_exception(TimeoutError('Synthetic settled socket guard'));self.native.poll()
        self.assertEqual([],self.native.tasks);self.opener.open.assert_not_called()

    def test_unexpected_sdk_programming_error_is_not_reclassified_as_network_evidence(self):
        self.future(error=AssertionError('Unexpected synthetic SDK programming fault'))
        with self.assertRaises(AssertionError):self.native.poll()
        self.assertFalse(self.native.account['observation']['events']);self.assertIsNone(self.native.token)

    def test_retired_pending_transport_is_kept_until_settled_then_discarded_without_new_process_effect(self):
        future=self.future(done=False);self.native.lifecycle_input('app.stop');self.native.lifecycle_input('app.launch')
        original=deepcopy(self.native.account);self.native.poll();self.assertEqual(1,len(self.native.tasks))
        future.set_exception(TimeoutError('Synthetic late retired transport failure'));self.native.poll()
        self.assertEqual([],self.native.tasks);self.assertEqual(original,self.native.account)
        self.opener.open.assert_not_called()


if __name__=='__main__':unittest.main()
