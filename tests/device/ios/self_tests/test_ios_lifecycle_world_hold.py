"""Actual WAL/files/canonical gates, with explicit UIKit/physics/HID models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from copy import deepcopy
import socket
import time
from unittest.mock import patch
from adapters.original_frame_store import OriginalFrameStore
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import lifecycle_world as world
from ios.adapters.lifecycle_world_hold_runtime import IOSLifecycleWorldHoldRuntime
from ios.adapters.touch_lease import TouchLeaseError,TouchLeasePending
from ios.self_tests.test_ios_lifecycle_world_attempt import AttemptDomain


class HIDContext:
    def __init__(self,boundary,root):
        self.boundary,self.root=boundary,root;self.calls=[];self.entered=0;self.exited=0
        self.down_gate=asyncio.Event();self.down_gate.set();self.down_error=False;self.ignore_move=False;self.route='world'
        self.sockets=socket.socketpair();self.after_down=None;self.enter_hook=None;self.offset=0
    async def __aenter__(self):
        self.entered+=1
        if self.enter_hook is not None:await self.enter_hook()
        return self
    async def send_touchscreen(self,state,x,y):
        journal=self.root.with_name('ios-lifecycle-world-hold-touch.json')
        from adapters.normal_feature_state import PrivateFeatureState
        actual=PrivateFeatureState(journal).read()
        if actual['phase']!=('down-issued' if state==0xC2 else 'up-issued'):raise AssertionError('Actual durable intent must precede report')
        self.calls.append((state,x,y));b=self.boundary;position=[x*1000/65535+self.offset,y*640/65535-20]
        if state==0xC2 and len(self.calls)==1:
            b.event('begin','pressed',position,self.route)
            if self.after_down:self.after_down()
            await self.down_gate.wait()
            if self.down_error:raise OSError('Modeled unknown original Down return')
        elif state==0xC2:
            if not self.ignore_move:
                b.event('update','updated',position,self.route)
                if self.route=='world':
                    b.pad.update(moveValid=True,moveNativeId=7,movePoint=position);b.raw[world.FORWARD]=.5;b.position=[0.,0.,-.7]
        else:
            if b.active:b.event('end','released',position,self.route)
            b.pad.update(moveValid=False,moveNativeId=-1,movePoint=None);b.raw=[0.]*world.DRIVE_KEYS
    async def __aexit__(self,*_args):self.exited+=1;self.close()
    def close(self):
        for resource in self.sockets:resource.close()


class LifecycleWorldHoldTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.b=AttemptDomain(self);self.first=self.b.owner.act()
        self.context=HIDContext(self.b.boundary,self.b.owner.store.path);self.addCleanup(self.context.close)
        self.factories=[];self.owner=None
        self.runtime=IOSLifecycleWorldHoldRuntime(self.b.d.f.f.f.adapter)
    def factory(self):self.factories.append(True);return self.context
    def make(self,close_editor=True):
        if close_editor:self.b.d.flow.back('create')
        self.owner=self.runtime.child('test-only',self.b.d.flow,self.b.owner,self.factory)
        return self.owner
    async def asyncTearDown(self):
        self.context.down_gate.set()
        if self.owner is not None and self.owner.lease is not None:
            lease=self.owner.lease;lease.request_release.set()
            if lease.worker is not None:await asyncio.wait_for(asyncio.shield(lease.worker),2)
    def flags(self):return [row[0] for row in self.context.calls]
    async def test_canonical_same_session_held_contact_has_independent_grounded_effect_then_actual_release(self):
        owner=self.make();first_files={path:(path.stat().st_ino,path.read_bytes()) for path in self.b.owner.store.path.parent.glob('ios-lifecycle-world-proof-*')}
        sessions=(self.b.d.f.f.f.sessions,self.b.d.f.f.f.launches)
        host=await owner.act();self.assertTrue(host['hostResponsibility']);self.assertEqual([0xC2,0xC2],self.flags())
        self.assertEqual({'window','start','end'},set(owner.previous['state']['path']))
        self.assertEqual({'width':1000,'height':640},owner.previous['state']['path']['window'])
        self.assertEqual([100,520],owner.previous['state']['path']['start']);self.assertEqual([100,505],owner.previous['state']['path']['end'])
        self.assertNotIn('actions',owner.previous['state']['path']);self.assertNotIn('body',owner.previous['state'])
        proof=owner.observe();self.assertEqual(.7,proof['facts']['worldDisplacement']);self.assertEqual(['forward'],proof['facts']['heldInputs'])
        self.assertIsNone(proof['contact']['ended']);self.assertTrue(all(fd.fileno()>=0 for fd in self.context.sockets))
        released=await owner.release();self.assertEqual('released',released['terminal']);self.assertEqual([0xC2,0xC2,0x02],self.flags())
        self.assertTrue(all(fd.fileno()==-1 for fd in self.context.sockets));self.assertEqual(1,self.context.exited)
        self.assertEqual(sessions,(self.b.d.f.f.f.sessions,self.b.d.f.f.f.launches))
        self.assertEqual(first_files,{path:(path.stat().st_ino,path.read_bytes()) for path in first_files})
        await owner.release();self.assertEqual([0xC2,0xC2,0x02],self.flags())
        with self.assertRaises(NativeUIError):owner.proof() # No invented three-second quiet.
    async def test_original_create_editor_must_close_before_second_input(self):
        owner=self.make(False)
        with self.assertRaises(NativeUIError):await owner.act()
        self.assertEqual([],self.factories);self.assertEqual([],self.flags())
    async def test_ack_without_actual_move_retains_contact_but_does_not_supply_effect(self):
        owner=self.make();self.context.ignore_move=True;await owner.act()
        with self.assertRaises(NativeUIError):owner.observe()
        self.assertTrue(owner.lease.inspect()['hostResponsibility']);self.assertIsNone(owner.state['held'])
        await owner.release();self.assertEqual([0xC2,0xC2,0x02],self.flags())
        with self.assertRaises(NativeUIError):owner.proof()
    async def test_lost_down_never_moves_or_repeats_and_cannot_become_held(self):
        owner=self.make();self.context.down_error=True
        with self.assertRaises(TouchLeaseError):await owner.act()
        self.assertEqual([0xC2,0x02],self.flags());self.assertIsNone(owner.state['held'])
        await owner.release()
        with self.assertRaises(NativeUIError):await owner.act()
        self.assertEqual(1,len(self.factories));self.assertEqual([0xC2,0x02],self.flags())
    async def test_unknown_down_keeps_original_worker_and_late_completion_cannot_send_move(self):
        owner=self.make();self.context.down_gate.clear()
        with self.assertRaises(TouchLeasePending):await owner.act(seconds=.3)
        self.assertEqual([0xC2],self.flags());self.assertTrue(owner.lease.inspect()['hostResponsibility'])
        with self.assertRaises(TouchLeasePending):await owner.release()
        self.context.down_gate.set();await owner.lease.worker
        self.assertEqual([0xC2,0x02],self.flags());self.assertEqual(1,len(self.factories))
    async def test_candidate_change_after_actual_down_still_releases_original_object_without_move(self):
        owner=self.make();artifact=self.b.d.f.f.f.artifact
        self.context.after_down=lambda:artifact.write_bytes(b'Changed actual fixture candidate while contact is pending')
        with self.assertRaises(TouchLeaseError):await owner.act()
        self.assertEqual([0xC2,0x02],self.flags());self.assertEqual(1,self.context.exited)
        self.assertIsNone(owner.state['held']);self.assertEqual(1,len(self.factories))
    async def test_lost_saved_held_frame_adopts_original_without_a_new_query_or_input(self):
        owner=self.make();await owner.act();write=OriginalFrameStore.write
        def lost(store,index,value):
            result=write(store,index,value)
            if store.namespace=='ios-lifecycle-world-hold-proof' and index==2:raise OSError('Lost parent append after actual saved held original')
            return result
        with patch.object(OriginalFrameStore,'write',new=lost):
            with self.assertRaises(OSError):owner.observe()
        reference=deepcopy(owner.state['storage']['2']);path=owner.files().path(reference);saved=(path.stat().st_ino,path.read_bytes())
        queries=len(self.b.boundary.queries);proof=owner.observe()
        self.assertEqual(.7,proof['facts']['worldDisplacement']);self.assertEqual(queries,len(self.b.boundary.queries))
        self.assertEqual(saved,(path.stat().st_ino,path.read_bytes()));self.assertEqual([0xC2,0xC2],self.flags())
        await owner.release()
    async def test_reopening_open_journal_cannot_recreate_original_live_hid_worker(self):
        owner=self.make();await owner.act()
        replacement=self.runtime.child('test-only',self.b.d.flow,self.b.owner,self.factory)
        with self.assertRaises(TouchLeasePending):await replacement.release()
        self.assertEqual(1,len(self.factories));self.assertTrue(owner.lease.inspect()['hostResponsibility'])
        await owner.release();self.assertEqual([0xC2,0xC2,0x02],self.flags())
    async def test_public_context_alias_swap_cannot_redirect_original_up_or_exit(self):
        owner=self.make();await owner.act();owner.observe()
        class Foreign:
            async def __aexit__(self,*_arguments):raise AssertionError('Wrong actual context released')
            async def send_touchscreen(self,*_arguments):raise AssertionError('Wrong actual HID released')
        owner.lease.context.actual=Foreign();owner.lease.context.hid=Foreign();owner.lease.hid=Foreign()
        await owner.release();self.assertEqual([0xC2,0xC2,0x02],self.flags());self.assertEqual(1,self.context.exited)
    async def test_actual_released_original_precedes_separate_three_second_native_quiet(self):
        owner=self.make();await owner.act();owner.observe();await owner.release()
        self.assertIsNone(owner.sample_quiet())
        for index in range(3):
            start=time.monotonic();await asyncio.sleep(1.05)
            # Explicit producer model: advance its independent native clock
            # by actual elapsed waiting; no retained original is retimed.
            self.b.native.tick+=round((time.monotonic()-start)*1000)
            proof=owner.sample_quiet()
            if index<2:self.assertIsNone(proof)
        self.assertGreaterEqual(proof['quiet']['nativeMilliseconds'],3000)
        self.assertEqual('quiet',owner.state['phase']);self.assertEqual([0xC2,0xC2,0x02],self.flags())
        self.assertEqual(proof,owner.proof());self.assertFalse(owner.lease.inspect()['hostResponsibility'])

    async def test_in_memory_path_mutation_after_down_cannot_redirect_move_or_archived_intent(self):
        owner=self.make()
        def changed():owner.state['path']['end'][0]+=10
        self.context.after_down=changed
        with self.assertRaises(TouchLeaseError):await owner.act()
        self.assertEqual([0xC2,0x02],self.flags());self.assertEqual([100,505],owner.store.read()['state']['path']['end'])
        self.assertEqual(1,self.context.exited);self.assertEqual(1,len(self.factories))

    async def test_unbracketed_geometry_and_extra_frame_fields_cannot_supply_preparation(self):
        owner=self.make();await owner.act();original=owner.frame(1)
        changed=deepcopy(original);changed['originals']['geometry']['observation']['sampleEpochMs']=original['clockJoin']['nativeBefore']['capturedEpochMs']-1
        with self.assertRaises(NativeUIError):owner.source_frame(changed,before=True)
        changed=deepcopy(original);changed['unrelatedOriginal']=True
        with self.assertRaises(NativeUIError):owner.source_frame(changed,before=True)
        self.assertEqual(original,owner.frame(1));await owner.release()
    async def test_completed_extra_contact_between_quiet_samples_is_not_quiet(self):
        owner=self.make();await owner.act();owner.observe();await owner.release()
        self.b.boundary.event('begin','pressed',[100.,500.]);self.b.boundary.event('end','released',[100.,500.])
        with self.assertRaises(NativeUIError):owner.sample_quiet()
        self.assertEqual([],owner.state['quiet']);self.assertEqual('released',owner.state['phase'])
    async def test_disabled_nonzero_raw_drive_never_becomes_a_quiet_sample(self):
        owner=self.make();await owner.act();owner.observe();await owner.release()
        self.b.boundary.raw[0]=.5;self.b.boundary.disabled[0]=True
        with self.assertRaises(NativeUIError):owner.sample_quiet()
        self.assertEqual([],owner.state['quiet']);self.assertEqual([0xC2,0xC2,0x02],self.flags())

    async def test_late_authenticated_context_cannot_send_down_from_expired_original_geometry(self):
        owner=self.make()
        async def late():
            started=time.monotonic();await asyncio.sleep(1.6)
            self.b.native.tick+=round((time.monotonic()-started)*1000)
        self.context.enter_hook=late
        with self.assertRaises(TouchLeaseError):await owner.act()
        self.assertEqual([],self.flags());self.assertEqual(1,self.context.entered);self.assertEqual(1,self.context.exited)
        self.assertFalse(owner.lease.inspect()['hostResponsibility']);self.assertIsNone(owner.state['held'])

    async def test_nearby_foreign_contact_cannot_borrow_original_pad_effect(self):
        owner=self.make();self.context.offset=10;await owner.act()
        with self.assertRaises(NativeUIError):owner.observe()
        self.assertIsNone(owner.state['held']);self.assertTrue(owner.lease.inspect()['hostResponsibility'])
        await owner.release();self.assertEqual([0xC2,0xC2,0x02],self.flags())

    async def test_context_acquisition_cannot_swap_original_coordinate_or_check_aliases(self):
        owner=self.make()
        async def swap():
            owner.lease.context.start=(0,0);owner.lease.context.end=(1,1);owner.lease.context.check=lambda:False
        self.context.enter_hook=swap
        await owner.act();self.assertEqual(.7,owner.observe()['facts']['worldDisplacement'])
        await owner.release();self.assertEqual([0xC2,0xC2,0x02],self.flags())
        self.assertEqual(1,self.context.entered);self.assertEqual(1,self.context.exited)

    async def test_candidate_change_refuses_canonical_factory_before_hid_acquisition(self):
        self.b.d.flow.back('create');self.b.d.f.f.f.artifact.write_bytes(b'Foreign source before hold factory')
        with self.assertRaises((NativeUIError,ValueError)):self.runtime.child('test-only',self.b.d.flow,self.b.owner,self.factory)
        self.assertEqual([],self.factories);self.assertEqual([],self.flags())


if __name__=='__main__':unittest.main()
