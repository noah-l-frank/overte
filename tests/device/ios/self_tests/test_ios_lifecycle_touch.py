"""Original Qt event models; no UIKit, native compilation or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import pathlib
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from ios.adapters import lifecycle_world as world,lifecycle_touch as touch
from ios.self_tests.test_ios_lifecycle_world import Boundary,RUN


class TouchBoundary(Boundary):
    def __init__(self):
        super().__init__();self.events=[];self.device=uuid.uuid4().hex;self.touch_instance=uuid.uuid4().hex
        self.birth=self.stamp();self.active=[];self.device_alive=True;self.failure=None
        self.pad=dict(objectId=uuid.uuid4().hex,active=True,enabled=True,hidden=False,viewport=[1000,600],fixed=True,
            center=[100.,500.],radius=60.,moveValid=False,moveNativeId=-1,moveOrigin=[100.,500.],movePoint=None)
        self.mutate=self.decorate
    def stamp(self):
        # An independent native monotonic origin, deliberately unlike World.
        return dict(epochMs=self.scene.epoch(),monotonicMs=500+round(self.scene.clock*1000))
    def event(self,kind,phase,position,route='world',contact=None,native_id=7):
        self.scene.clock+=.01
        if contact is None:contact=self.active[0] if self.active else uuid.uuid4().hex
        row=dict(id=contact,nativeId=native_id,phase=phase,position=deepcopy(position))
        self.events.append(dict(sequence=len(self.events)+1,clock=self.stamp(),device=self.device,
            eventTimestampMs=7000+round(self.scene.clock*1000),kind=kind,route=route,points=[row]))
        if phase=='pressed':self.active.append(contact)
        if phase in ('released','cancelled'):self.active.remove(contact)
        return contact
    def decorate(self,value):
        stamp=self.stamp();value['iosLifecycleWorldVersion']=2
        value['source']['touch']=dict(iosLifecycleTouchVersion=1,instance=self.touch_instance,
            clockDomain='native-main-lifecycle-touch',clockBefore=stamp,clockAfter=deepcopy(stamp),birth=deepcopy(self.birth),
            installed=True,complete=self.failure is None,failure=self.failure,events=deepcopy(self.events),
            devices=[dict(id=self.device,alive=self.device_alive)] if self.events else [],active=deepcopy(self.active))
        value['source']['pad']=deepcopy(self.pad)
    def held(self,route='world'):
        first=self.reader().read(RUN)
        self.event('begin','pressed',[100.,500.],route)
        self.event('update','updated',[100.,475.],route)
        self.position=[0.,0.,-.7]
        if route=='world':
            self.pad.update(moveValid=True,moveNativeId=7,movePoint=[100.,475.]);self.raw[world.FORWARD]=.5
        return first,self.reader().read(RUN)
    def release(self,phase='released'):
        self.event('cancel' if phase=='cancelled' else 'end',phase,[100.,475.])
        self.pad.update(moveValid=False,moveNativeId=-1,movePoint=None);self.raw=[0.]*world.DRIVE_KEYS
        return self.reader().read(RUN)


class LifecycleTouchTests(unittest.TestCase):
    def test_active_contact_plugin_and_actual_forward_keys_are_separate_required_originals(self):
        b=TouchBoundary();first,held=b.held();saved=deepcopy(first)
        proof=world.active_forward(first,held)
        self.assertEqual(['forward'],proof['facts']['heldInputs']);self.assertEqual(.7,proof['facts']['worldDisplacement'])
        self.assertIsNone(proof['contact']['ended']);self.assertEqual(2,len(held['source']['touch']['events']))
        self.assertEqual(saved,first);self.assertEqual(2,len(b.queries))
        self.assertNotEqual(held['clockAfter']['monotonicMs'],held['source']['touch']['clockAfter']['monotonicMs'])

    def test_ui_intercept_is_an_actual_attempt_without_a_world_effect(self):
        b=TouchBoundary();first,held=b.held('ui');b.position=[0.,0.,0.]
        # A separate fresh observation reports actual unchanged physics.
        current=b.reader().read(RUN);row=world.contact_attempt(first,current)
        self.assertEqual('ui',row['route']);self.assertEqual([],world.measure(first,current)['heldInputs'])
        self.assertEqual(0.,world.measure(first,current)['worldDisplacement'])
        with self.assertRaises(NativeUIError):world.active_forward(first,current)

    def test_completed_w3c_style_contact_cannot_be_called_held(self):
        b=TouchBoundary();first,held=b.held();released=b.release()
        self.assertEqual('released',world.contact_attempt(first,released)['terminal'])
        with self.assertRaises(NativeUIError):world.active_forward(first,released)
        original=world.contact_released(held,released);self.assertIsNotNone(original['ended'])
        self.assertEqual([],released['source']['touch']['active'])

    def test_cancel_is_terminal_but_not_a_quiet_or_weak_retirement_proof(self):
        b=TouchBoundary();first,held=b.held();cancel=b.release('cancelled')
        self.assertEqual('cancelled',world.contact_released(held,cancel)['terminal'])
        with self.assertRaises(NativeUIError):world.stationary([cancel])
        self.assertTrue(cancel['source']['touch']['devices'][0]['alive'])

    def test_different_contact_or_pad_cannot_borrow_effective_forward(self):
        mutations=(lambda v:v['source']['pad'].update(moveNativeId=8),
            lambda v:v['source']['pad'].update(movePoint=[100.,474.]),
            lambda v:v['source']['pad'].update(moveOrigin=[101.,500.]),
            lambda v:v['source']['pad'].update(objectId=uuid.uuid4().hex),
            lambda v:v['source']['drive']['raw'].__setitem__(2,0),
            lambda v:v['source']['touch']['events'][1].update(route='captured'))
        for mutate in mutations:
            b=TouchBoundary();first,held=b.held();mutate(held)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):world.active_forward(first,held)

    def test_original_journal_prefix_device_death_and_clock_changes_are_rejected(self):
        for change in ('rewrite','rebirth','revive','clock','missing-end','failure','dead-active'):
            b=TouchBoundary();first,held=b.held();released=b.release();mutated=deepcopy(released)
            j=mutated['source']['touch'];old=deepcopy(held)
            if change=='rewrite':j['events'][0]['points'][0]['position'][0]+=1
            if change=='rebirth':j['birth']['monotonicMs']+=1
            if change=='revive':old['source']['touch']['devices'][0]['alive']=False
            if change=='clock':j['events'][1]['clock']['monotonicMs']=0
            if change=='missing-end':j['events'].pop()
            if change=='failure':j.update(complete=False,failure='event-capacity')
            if change=='dead-active':j['active']=[j['events'][0]['points'][0]['id']];j['devices'][0]['alive']=False
            with self.subTest(change=change),self.assertRaises(NativeUIError):world.contact_released(old,mutated)

    def test_duplicate_native_contact_and_second_pointer_do_not_become_one_attempt(self):
        b=TouchBoundary();first,held=b.held();b.event('update','pressed',[101.,475.],contact=uuid.uuid4().hex,native_id=8)
        current=b.reader().read(RUN)
        with self.assertRaises(NativeUIError):world.contact_attempt(first,current)
        j=deepcopy(held['source']['touch']);j['events'][1]['points'][0]['phase']='pressed'
        with self.assertRaises(NativeUIError):touch.contacts(j)

    def test_snapshot_cannot_late_append_a_contact_that_predates_its_previous_original(self):
        b=TouchBoundary();first,held=b.held();j=held['source']['touch']
        j['events'][0]['clock']=deepcopy(first['source']['touch']['birth'])
        with self.assertRaises(NativeUIError):world.contact_attempt(first,held)

    def test_held_contact_is_bounded_and_requires_grounded_measured_distance(self):
        for age,position in ((12.1,[0,0,-.7]),(0,[0,0,-.29]),(0,[0,0,-3.01]),(0,[0,.051,-.7])):
            b=TouchBoundary();first,held=b.held();b.scene.clock+=age;b.position=position;current=b.reader().read(RUN)
            with self.subTest(age=age,position=position),self.assertRaises(NativeUIError):world.active_forward(first,current)

    def test_release_requires_real_terminal_for_same_contact_and_zero_raw_keys(self):
        for change in ('raw','pad','fresh-contact','still-held'):
            b=TouchBoundary();first,held=b.held();released=b.release()
            if change=='raw':released['source']['drive']['raw'][0]=.1;released['source']['drive']['effective'][0]=.1
            if change=='pad':released['source']['pad'].update(moveValid=True,moveNativeId=7,movePoint=[100.,475.])
            if change=='fresh-contact':
                b.event('begin','pressed',[100.,500.]);b.event('end','released',[100.,500.]);released=b.reader().read(RUN)
            if change=='still-held':released=deepcopy(held);released['requestId']='ios-'+uuid.uuid4().hex;released['sequence']+=1
            with self.subTest(change=change),self.assertRaises(NativeUIError):world.contact_released(held,released)

    def test_literal_world_one_stays_readable_without_contact_or_pad_invention(self):
        b=Boundary();first=b.reader().read(RUN);world.original(first)
        self.assertNotIn('touch',first['source']);self.assertNotIn('pad',first['source'])
        with self.assertRaises(NativeUIError):world.contact_attempt(first,first)

    def test_native_tap_is_gated_passive_and_does_not_double_record_internal_begin_update(self):
        root=pathlib.Path(__file__).resolve().parents[4]
        header=(root/'tests/device/native/IOSLifecycleTouchObservation.h').read_text()
        app=(root/'interface/src/Application_Events.cpp').read_text()
        self.assertIn('defined(OVERTE_IOS_E2E_TEST_BUILD)',header)
        self.assertIn('if (!_installed || !main()',header)
        self.assertIn('event->type()==QEvent::TouchUpdate?event:nullptr',app)
        self.assertIn('unresolved-route',header)
        for forbidden in ('sendEvent(', 'postEvent(', 'event->accept(', 'setDriveKey(', 'captureTouchEvents('):
            self.assertNotIn(forbidden,header)
