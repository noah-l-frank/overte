"""Closed admission and actual loop/task/FD ownership; no service execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import lifecycle_touch_transport as transport
from ios.adapters.lifecycle_world_hold_runtime import IOSLifecycleWorldHoldRuntime
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.touch_lease import TouchLeasePending
from ios.self_tests import test_ios_touch_lease as fixture


class TouchTransportAdmissionTests(unittest.TestCase):
    def test_absent_and_explicitly_disabled_transport_stay_unavailable(self):
        for value in (None,{'nativeTouchSupport':False}):
            with self.subTest(disabled=value is not None),self.assertRaises(transport.TouchTransportUnavailable):transport.admit(value)
        self.assertEqual(dict(nativeTouchSupport=False,availability='missing-authenticated-broker'),transport.metadata())
        changed=transport.metadata();changed['nativeTouchSupport']=True;self.assertFalse(transport.metadata()['nativeTouchSupport'])
    def test_selectors_endpoints_pid_and_callbacks_cannot_mint_authenticated_transport(self):
        for value in ({'nativeTouchSupport':True},{'nativeTouchSupport':0},{'endpoint':'private-endpoint'},
                      {'selector':'private-selector'},{'expectedPid':42},{'factory':lambda:None},False):
            with self.subTest(kind=type(value).__name__),self.assertRaises(NativeUIError):transport.admit(value)
    def test_canonical_production_route_refuses_before_candidate_sdk_or_source_acquisition(self):
        runtime=IOSLifecycleWorldHoldRuntime(object())
        with patch.object(IOSScriptRuntime,'_sources',side_effect=AssertionError('Unavailable transport cannot acquire a source')):
            with self.assertRaises(transport.TouchTransportUnavailable):runtime.production_child('private',object(),object())
        self.assertFalse(transport.metadata()['nativeTouchSupport'])


class RetainedTouchWorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f=fixture.TouchLeaseTests();self.f.setUp()
        # Transfer synchronous cleanup callbacks to this actual async runner.
        # The source fixture itself has no separately initialized runner.
        for function,args,kwargs in self.f._cleanups:self.addCleanup(function,*args,**kwargs)
        self.f._cleanups.clear()
    async def asyncTearDown(self):await self.f.asyncTearDown()
    async def test_same_worker_stays_owned_through_unknown_down_and_late_once_release(self):
        f=self.f;f.context.down_gate.clear()
        with self.assertRaises(TouchLeasePending):await f.begin(.3)
        owner=transport.RetainedTouchWorker(f.owner);worker=f.owner.worker
        self.assertTrue(owner.inspect()['hostResponsibility'])
        with self.assertRaises(TouchLeasePending):await owner.release()
        with self.assertRaises(TouchLeasePending):owner.ensure_teardown()
        self.assertIs(worker,f.owner.worker);self.assertFalse(worker.cancelled());self.assertTrue(all(fd.fileno()>=0 for fd in f.context.sockets))
        f.context.down_gate.set();await worker
        self.assertEqual([0xC2,0x02],f.states());self.assertTrue(all(fd.fileno()==-1 for fd in f.context.sockets))
        self.assertFalse(owner.inspect()['hostResponsibility']);self.assertTrue(owner.inspect()['contextExitReturned'])
        self.assertFalse(owner.inspect()['retirementEstablished']);self.assertFalse(owner.inspect()['nativeTouchSupport'])
        with self.assertRaises(transport.TouchTransportUnavailable):owner.ensure_teardown()
    async def test_replaced_worker_foreign_loop_and_changed_binding_cannot_borrow_ownership(self):
        f=self.f;await f.begin();owner=transport.RetainedTouchWorker(f.owner);actual=f.owner.worker
        f.owner.worker=None
        with self.assertRaises(NativeUIError):owner.inspect()
        f.owner.worker=actual
        with patch.object(transport.asyncio,'get_running_loop',return_value=object()),self.assertRaises(NativeUIError):owner.inspect()
        with self.assertRaises(transport.TouchTransportUnavailable):await asyncio.to_thread(owner.inspect)
        binding=deepcopy(f.owner.binding);f.owner.binding['sessionId']='foreign'
        with self.assertRaises(NativeUIError):owner.inspect()
        f.owner.binding=binding;await owner.release();self.assertEqual([0xC2,0x02],f.states())
    async def test_idle_lease_and_foreign_object_cannot_claim_a_retained_worker(self):
        for value in (self.f.owner,object()):
            with self.assertRaises(NativeUIError):transport.RetainedTouchWorker(value)
        self.assertEqual([],self.f.states());self.assertEqual([],self.f.factories)


if __name__=='__main__':unittest.main()
