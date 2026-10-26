"""Actual private intent/host FDs with an explicitly modeled HID service.

No device, HID/RSD connection, Appium server or runtime service is opened.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.touch_lease import TouchLease,TouchLeaseError,TouchLeasePending


class Context:
    def __init__(self,store):
        self.store=store;self.events=[];self.entered=0;self.exited=0;self.down_error=False;self.up_error=False;self.drain_error=False
        self.enter_gate=asyncio.Event();self.enter_gate.set();self.down_gate=asyncio.Event();self.down_gate.set()
        self.drain_gate=asyncio.Event();self.drain_gate.set();self.drain_started=asyncio.Event();self.down_started=asyncio.Event()
        self.sockets=socket.socketpair();self.hid=self
    async def __aenter__(self):
        self.entered+=1;await self.enter_gate.wait();return self.hid
    async def send_touchscreen(self,state,x,y):
        journal=self.store.read();expected='down-issued' if state==0xC2 else 'up-issued'
        if journal['phase']!=expected:raise AssertionError('The actual durable intent must precede each ordinary report')
        self.events.append((state,x,y))
        if state==0xC2:
            self.down_started.set()
            await self.down_gate.wait()
            if self.down_error:raise OSError('Synthetic lost Down return')
        elif self.up_error:raise OSError('Synthetic lost Up return')
    async def __aexit__(self,*_args):
        self.drain_started.set();await self.drain_gate.wait()
        if self.drain_error:raise OSError('Synthetic missing original context drainage')
        self.close();self.exited+=1
    def close(self):
        for resource in self.sockets:resource.close()


class TouchLeaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700);self.store=PrivateFeatureState(root/'ordinary-touch-lease.json')
        self.context=Context(self.store);self.addCleanup(self.context.close);self.factories=[]
        def factory():self.factories.append(True);return self.context
        self.factory=factory;self.checks=[];self.foreground=True
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,sessionId='owned-session',generation=1,targetFingerprint='c'*64,processIdentity='31')
        self.run_id='d'*32;self.owner=self.make()
    def check(self):
        self.checks.append(True)
        if not self.foreground:raise TouchLeaseError('Synthetic fresh foreground/PID/candidate mismatch')
        return True
    def make(self):return TouchLease(self.store,self.factory,binding=self.binding,run=self.run_id,check=self.check)
    async def asyncTearDown(self):
        self.context.enter_gate.set();self.context.down_gate.set();self.context.drain_gate.set();self.owner.request_release.set()
        if self.owner.worker is not None:
            await asyncio.wait_for(asyncio.shield(self.owner.worker),2)
    async def begin(self,seconds=2):return await self.owner.begin(100,50,25,10,seconds=seconds)
    def states(self):return [row[0] for row in self.context.events]

    async def test_original_intent_precedes_down_and_same_hid_object_lives_until_once_up_and_fd_drain(self):
        status=await self.begin();self.assertTrue(status['hostResponsibility']);self.assertIs(self.context.hid,self.owner.hid)
        self.assertEqual([(0xC2,16384,13107)],self.context.events)
        self.assertTrue(all(resource.fileno()>=0 for resource in self.context.sockets))
        self.assertEqual(4,len(self.checks));self.assertEqual(self.binding,self.store.read()['binding']);self.assertEqual(self.run_id,self.store.read()['runId'])
        status=await self.owner.release();self.assertFalse(status['hostResponsibility']);self.assertTrue(status['contextExitReturned'])
        self.assertNotIn('contextDrained',status)
        self.assertEqual([0xC2,0x02],self.states());self.assertEqual(1,self.context.exited)
        self.assertTrue(all(resource.fileno()==-1 for resource in self.context.sockets))
        await self.owner.release();self.assertEqual([0xC2,0x02],self.states())
        with self.assertRaises(TouchLeaseError):await self.begin()
        self.assertEqual(1,len(self.factories))

    async def test_watchdog_uses_original_host_deadline_and_never_reports_native_release(self):
        await self.begin(.3);await asyncio.wait_for(asyncio.shield(self.owner.worker),2)
        status=self.owner.inspect();self.assertFalse(status['hostResponsibility']);self.assertEqual('deadline',status['failure'])
        self.assertNotIn('nativeHeld',status);self.assertNotIn('nativeReleased',status)
        self.assertEqual([0xC2,0x02],self.states());self.assertEqual('closed',self.store.read()['phase'])

    async def test_lost_down_is_never_resent_and_original_worker_attempts_ordinary_up(self):
        self.context.down_error=True
        with self.assertRaises(TouchLeaseError):await self.begin()
        await self.owner.worker;self.assertEqual([0xC2,0x02],self.states())
        self.assertEqual('down',self.owner.inspect()['failure']);self.assertEqual(1,self.context.exited)
        with self.assertRaises(TouchLeaseError):await self.begin()
        self.assertEqual(1,len(self.factories))

    async def test_failed_up_remains_owned_and_a_second_release_never_reissues_it(self):
        await self.begin();self.context.up_error=True
        for _ in range(2):
            with self.assertRaises(TouchLeasePending):await self.owner.release()
        self.assertEqual([0xC2,0x02],self.states());self.assertTrue(self.owner.inspect()['hostResponsibility'])
        self.assertEqual('failed',self.store.read()['phase']);self.assertEqual('up',self.owner.inspect()['failure'])

    async def test_actual_pending_drain_retains_original_context_and_fds_until_late_completion(self):
        await self.begin(.3);self.context.drain_gate.clear()
        with self.assertRaises(TouchLeasePending):await self.owner.release()
        self.assertTrue(self.owner.inspect()['workerRunning']);self.assertTrue(self.owner.inspect()['hostResponsibility'])
        self.assertTrue(all(resource.fileno()>=0 for resource in self.context.sockets))
        self.context.drain_gate.set();await self.owner.worker
        self.assertFalse(self.owner.inspect()['hostResponsibility']);self.assertEqual([0xC2,0x02],self.states())

    async def test_unknown_down_retains_its_original_task_and_cannot_be_sent_again(self):
        self.context.down_gate.clear()
        with self.assertRaises(TouchLeasePending):await self.begin(.3)
        with self.assertRaises(TouchLeasePending):await self.owner.release()
        with self.assertRaises(TouchLeaseError):await self.begin()
        self.assertEqual([0xC2],self.states());self.assertTrue(self.owner.inspect()['hostResponsibility'])
        self.context.down_gate.set();await self.owner.worker
        self.assertEqual([0xC2,0x02],self.states());self.assertEqual(1,len(self.factories))

    async def test_cancelling_release_caller_does_not_cancel_original_worker_or_lose_up(self):
        await self.begin();self.context.drain_gate.clear();caller=asyncio.create_task(self.owner.release())
        await self.context.drain_started.wait();caller.cancel()
        with self.assertRaises(asyncio.CancelledError):await caller
        self.assertFalse(self.owner.worker.cancelled());self.assertTrue(self.owner.inspect()['hostResponsibility'])
        self.context.drain_gate.set();await self.owner.worker
        self.assertEqual([0xC2,0x02],self.states());self.assertFalse(self.owner.inspect()['hostResponsibility'])

    async def test_archived_open_intent_cannot_reconstruct_live_hid_or_repeat_down(self):
        await self.begin();restored=self.make()
        self.assertTrue(restored.inspect()['hostResponsibility'])
        with self.assertRaises(TouchLeasePending):await restored.release()
        with self.assertRaises(TouchLeaseError):await restored.begin(100,50,25,10,seconds=1)
        self.assertEqual(1,len(self.factories));await self.owner.release()

    async def test_cancelling_begin_caller_keeps_original_unknown_down_worker_until_once_up(self):
        self.context.down_gate.clear();caller=asyncio.create_task(self.begin())
        await self.context.down_started.wait();caller.cancel()
        with self.assertRaises(asyncio.CancelledError):await caller
        self.assertFalse(self.owner.worker.cancelled());self.assertEqual([0xC2],self.states())
        self.context.down_gate.set();await self.owner.worker
        self.assertEqual([0xC2,0x02],self.states());self.assertEqual('cancelled',self.owner.inspect()['failure'])

    async def test_lost_committed_opening_intent_never_dispatches_down_or_recreates_live_state(self):
        write=self.store.write
        def lost(value,previous):write(value,previous);raise OSError('Synthetic lost committed opening intent')
        with patch.object(self.store,'write',side_effect=lost),self.assertRaises(TouchLeaseError):await self.begin()
        self.assertEqual('opening',self.store.read()['phase']);self.assertEqual([],self.factories);self.assertEqual([],self.states())
        restored=self.make()
        with self.assertRaises(TouchLeaseError):await restored.begin(100,50,25,10,seconds=1)
        with self.assertRaises(TouchLeasePending):await restored.release()
        self.assertEqual([],self.factories)

    async def test_untyped_or_changed_archived_clock_and_responsibility_fields_are_not_accepted(self):
        await self.begin();await self.owner.release();original=self.store.read()
        for field,value in (('phase',[]),('failure',[]),('deadlineMonotonic',original['startedMonotonic']+13),
                            ('position',[True,0]),('leaseId','foreign')):
            wrong=dict(original);wrong[field]=value;self.store.write(wrong,self.store.read())
            with self.subTest(field=field),self.assertRaises(TouchLeaseError):self.make()

    async def test_each_required_fresh_source_guard_can_refuse_without_an_ordinary_down(self):
        for denied in range(1,5):
            store=PrivateFeatureState(self.store.path.with_name('guard-step-'+str(denied)+'.json'))
            actual=Context(store);self.addCleanup(actual.close);checks=[]
            def guard():checks.append(True);return len(checks)!=denied
            owner=TouchLease(store,lambda:actual,binding=self.binding,run=self.run_id,check=guard)
            with self.subTest(denied=denied),self.assertRaises(TouchLeaseError):await owner.begin(100,50,25,10,seconds=2)
            await owner.worker;self.assertEqual([],actual.events);self.assertEqual(denied,len(checks))
            self.assertEqual('continuity',owner.inspect()['failure'])
            if actual.entered:self.assertEqual(1,actual.exited)

    async def test_guard_is_mandatory_and_archived_binding_or_run_cannot_change_ownership(self):
        with self.assertRaises(TouchLeaseError):TouchLease(self.store,self.factory,binding=self.binding,run=self.run_id,check=None)
        await self.begin();await self.owner.release()
        for binding,run in ((dict(self.binding,processIdentity='99'),self.run_id),(self.binding,'e'*32),
                            (dict(self.binding,generation=True),self.run_id)):
            with self.subTest(binding=binding,run=run),self.assertRaises(TouchLeaseError):
                TouchLease(self.store,self.factory,binding=binding,run=run,check=self.check)

    async def test_swapped_public_hid_context_and_factory_cannot_redirect_original_up_or_exit(self):
        await self.begin();foreign=Context(self.store);self.addCleanup(foreign.close)
        self.owner.hid=foreign.hid;self.owner.context=foreign;self.owner.session_factory=lambda:foreign
        await self.owner.release()
        self.assertEqual([0xC2,0x02],self.states());self.assertEqual(1,self.context.exited)
        self.assertEqual([],foreign.events);self.assertEqual(0,foreign.entered);self.assertEqual(0,foreign.exited)
        self.assertTrue(all(resource.fileno()>=0 for resource in foreign.sockets))
        self.assertTrue(all(resource.fileno()==-1 for resource in self.context.sockets))
        self.assertEqual(1,len(self.factories))

    async def test_factory_change_during_fresh_guard_cannot_open_a_foreign_context(self):
        checks=[];foreign=Context(self.store);self.addCleanup(foreign.close)
        def guard():checks.append(True);owner.session_factory=lambda:foreign;return True
        owner=TouchLease(self.store,self.factory,binding=self.binding,run=self.run_id,check=guard)
        with self.assertRaises(TouchLeaseError):await owner.begin(100,50,25,10,seconds=2)
        await owner.worker
        self.assertEqual('continuity',owner.inspect()['failure']);self.assertEqual([],self.factories)
        self.assertEqual([],foreign.events);self.assertEqual(0,foreign.entered)

    async def test_late_acquisition_after_deadline_drains_same_context_without_down(self):
        self.context.enter_gate.clear()
        with self.assertRaises(TouchLeasePending):await self.begin(.3)
        self.assertTrue(self.owner.inspect()['hostResponsibility']);self.assertEqual([],self.states())
        self.context.enter_gate.set();await self.owner.worker
        self.assertEqual([],self.states());self.assertEqual(1,self.context.exited)
        self.assertFalse(self.owner.inspect()['hostResponsibility'])

    async def test_failed_context_drain_stays_owned_with_original_object_retained(self):
        await self.begin();self.context.drain_error=True
        with self.assertRaises(TouchLeasePending):await self.owner.release()
        self.assertTrue(self.owner.inspect()['hostResponsibility']);self.assertIs(self.context,self.owner.context)
        self.assertEqual('drain',self.owner.inspect()['failure']);self.assertEqual([0xC2,0x02],self.states())

    async def test_unbounded_or_untyped_duration_never_creates_an_intent_or_opens_hid(self):
        for seconds in (0,-1,13,True,float('nan')):
            with self.subTest(seconds=seconds),self.assertRaises(TouchLeaseError):await self.begin(seconds)
        self.assertIsNone(self.store.read());self.assertEqual([],self.factories)


if __name__=='__main__':unittest.main()
