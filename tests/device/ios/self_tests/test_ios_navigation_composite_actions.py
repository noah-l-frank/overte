"""Real private/phase/W3C paths; selection and native Qt world are modeled.

Original-token selection itself has separate NavigationPlacesActions tests.
These checks exercise the coordinator's ordering, source joins and lost returns.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.native_feature_observation import NativeFeatureObservation, need
from adapters.native_scene_loads import resource_hash
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from ios.adapters import navigation_state, places_controls
from ios.adapters.navigation_composite_actions import NavigationCompositeActions, NavigationArrivalPending
from ios.adapters.navigation_places_actions import NavigationPlacesActions
from ios.self_tests import test_ios_navigation_surface_actions as surfaces
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from navigation_observation import viewpoint_urls


class Selection(NavigationPlacesActions):
    """Explicit Qt selection seam, preserving real durable child handoff."""
    def __init__(self, harness, surface):
        self.h, self.surface = harness, surface
        self.binding, self.run, self.lock = surface.binding, surface.run, surface.lock
        self.fixture = surface.admission.fixture
        self.store = PrivateFeatureState(surface.store.path.with_name('ios-navigation-places-actions.json'))
        self.previous = self.store.read(); self.state = None if self.previous is None else self.decode(self.previous)
    def bound(self):
        self.surface.bound(); need(same(self.store.read(), self.previous))
    def decode(self, value):
        need(value['binding'] == self.binding and value['runId'] == self.run)
        return unpack(value['payload'])[0]
    def act(self, call):
        self.bound(); self.validate_call(call); self.h.selections += 1
        label = 'B' if call['verb'] == 'directory-select' else 'A'
        self.h.world_label = label
        observed = places_controls.project(self.surface.capture())
        rows=[] if self.state is None else self.state['actions']
        self.state = dict(actions=rows+[dict(call=deepcopy(call), phase='acknowledged', observed=observed)])
        value = dict(binding=self.binding, runId=self.run, payload=pack([self.state]))
        self.store.write(value, self.previous); self.previous = value
        if self.h.lose_selection: raise OSError('Synthetic selected return loss')
        return {'performed':True}


class Clock(NativeFeatureObservation):
    def __init__(self, harness):
        self.h=harness;self.ios=True;self.pid=42;self.sequence=2;self.guard=lambda:True
    def read(self, after):
        self.h.tick();self.sequence+=1;value=global_packet(self.h.epoch(),1)
        value.update(sequence=self.sequence,requestId='ios-'+uuid.uuid4().hex);return value


class World(navigation_state.IOSNavigationState):
    def __init__(self, harness):
        self.h=harness;self.pid=42;self.count=0
        self.original=deepcopy(harness.s.admission.archive()['originals']['navigation'])
    def read(self, run):
        h=self.h;self.count+=1;h.tick();before=h.epoch();h.tick();middle=h.epoch();h.tick();after=h.epoch()
        value=deepcopy(self.original);value.update(requestId='ios-'+uuid.uuid4().hex,sequence=self.original['sequence']+self.count)
        value['clockBefore']=dict(epochMs=before,monotonicMs=before-1700086400000)
        value['clockAfter']=dict(epochMs=after,monotonicMs=after-1700086400000)
        source=value['source'];label=h.world_label;url=viewpoint_urls(h.s.fixture.inputs['sceneUrl'])[label]
        source['sceneUrl']=url;source['avatar']['feetPosition']=[2 if label=='B' and not h.ignored else 0,0,4]
        loads=source['sceneLoads'];loads.update(commandId=value['requestId'],sequence=loads['sequence']+self.count,
            capturedEpochMs=middle,currentGeneration=loads['currentGeneration']+1)
        loads['requests'].append(dict(id='f'*32,kind='request',generation=loads['currentGeneration'],resourceSha256=resource_hash(url),
            startedEpochMs=self.original['clockAfter']['epochMs']+1,updatedEpochMs=self.original['clockAfter']['epochMs']+2,
            releasedEpochMs=self.original['clockAfter']['epochMs']+2,phase='committed',pending=False,result=0,bytes=1234))
        if h.fault=='source':value['instance']='e'*32
        if h.fault=='stale':value['clockBefore']=deepcopy(self.original['clockBefore']);value['clockAfter']=deepcopy(self.original['clockAfter'])
        if h.fault=='pid':value['processId']=99
        if h.fault=='lost':raise OSError('Synthetic world read loss')
        return value


class NavigationCompositeActionsTests(unittest.TestCase):
    def setUp(self):
        self.s=surfaces.NavigationSurfaceActionsTests();self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.b=self.s.b;self.ignored=False;self.fault=None;self.world_label='A';self.selections=0;self.lose_selection=False
        self.world=None
        self.s.admission.native=Clock(self)
    def tick(self):self.b.clock+=.001
    def epoch(self):return self.s.h.native_epoch()
    def owner(self):
        surface=self.s.owner();places=Selection(self,surface)
        if self.world is None:self.world=World(self)
        return NavigationCompositeActions(PrivateFeatureState(self.s.h.h.root/'ios-navigation-composite-actions.json'),
            surface,places,self.world,epoch_ms=lambda:self.s.h.h.epoch()+self.b.clock*1000,monotonic=lambda:self.b.clock)
    def start(self):
        self.s.owner().act(self.s.call('open'));return self.s.call('directory-select')

    def test_actual_arrival_precedes_real_owned_close_and_duplicate_has_no_reads_or_input(self):
        with self.s.h.h.lock.held():
            call=self.start();owner=self.owner();self.assertEqual({'performed':True},owner.act(call))
            row=owner.state['actions'][-1];self.assertTrue(row['frames'][-1]['ready']);self.assertEqual('delivered',row['phase'])
            self.assertIsNone(self.b.screen);before=(self.world.count,list(self.b.inputs),self.selections)
            self.owner().act(call);self.assertEqual(before,(self.world.count,self.b.inputs,self.selections))
            self.assertIsNotNone(owner.store.read());self.assertNotIn('passed',row)

    def test_ignored_motion_retains_open_surface_then_fresh_arrival_closes_without_reselecting(self):
        with self.s.h.h.lock.held():
            call=self.start();self.ignored=True;owner=self.owner()
            with self.assertRaises(NavigationArrivalPending):owner.act(call)
            first=deepcopy(owner.state['actions'][-1]['frames'][0]);self.assertEqual('places',self.b.screen)
            before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):self.owner().act(call)
            self.assertEqual(before,self.b.inputs);self.ignored=False;again=self.owner();again.settle()
            self.assertEqual(1,self.selections);self.assertEqual(first,again.state['actions'][-1]['frames'][0])
            self.assertEqual(2,len(again.state['actions'][-1]['frames']));self.assertIsNone(self.b.screen)

    def test_lost_selected_return_is_durable_and_never_replayed_or_closed(self):
        with self.s.h.h.lock.held():
            call=self.start();owner=self.owner();self.lose_selection=True
            with self.assertRaises(OSError):owner.act(call)
            before=list(self.b.inputs);again=self.owner()
            with self.assertRaises(NativeUIError):again.act(call)
            with self.assertRaises(NativeUIError):again.settle()
            self.assertEqual(1,self.selections);self.assertEqual(before,self.b.inputs);self.assertEqual(0,self.world.count)

    def test_lost_or_foreign_original_never_closes_and_partial_capture_cannot_restart(self):
        for fault in ('lost','source','stale','pid'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                with self.s.h.h.lock.held():
                    call=self.start();owner=self.owner();self.fault=fault;before=list(self.b.inputs)
                    with self.assertRaises((OSError,NativeUIError)):owner.act(call)
                    self.assertEqual(before,self.b.inputs);self.assertEqual('places',self.b.screen)
                    count=self.world.count;self.fault=None
                    with self.assertRaises(NativeUIError):self.owner().settle()
                    self.assertEqual(count,self.world.count)

    def test_lost_parent_close_return_recovers_existing_child_ack_without_new_input_or_read(self):
        with self.s.h.h.lock.held():
            call=self.start();owner=self.owner();write=owner.store.write
            def lost(value, previous):
                if unpack(value['payload'])[0]['actions'][-1]['phase']=='delivered':raise OSError('Synthetic final parent write loss')
                write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.act(call)
            before=(self.world.count,list(self.b.inputs),self.selections);again=self.owner();again.recover_close()
            self.assertEqual(before,(self.world.count,self.b.inputs,self.selections));self.assertEqual('delivered',again.state['actions'][-1]['phase'])

    def test_original_deadline_survives_reconstruction_and_cannot_refresh_pending_arrival(self):
        with self.s.h.h.lock.held():
            call=self.start();self.ignored=True;owner=self.owner()
            with self.assertRaises(NavigationArrivalPending):owner.act(call)
            self.b.clock+=31;before=(self.world.count,list(self.b.inputs))
            with self.assertRaises(NativeUIError):self.owner().settle()
            self.assertEqual(before,(self.world.count,self.b.inputs));self.assertEqual('places',self.b.screen)

    def test_bookmark_visit_reopens_selects_measures_and_closes_under_its_original_call(self):
        with self.s.h.h.lock.held():
            first=self.start();self.owner().act(first);call=self.s.call('bookmark-visit');owner=self.owner();owner.act(call)
            self.assertEqual(2,self.selections);self.assertEqual('A',self.world_label)
            self.assertEqual(['directory-select','bookmark-visit'],[row['call']['verb'] for row in owner.state['actions']])
            rows=owner.surfaces.state['actions']
            self.assertEqual(['open','close'],[row['surface'] for row in rows[-2:]])
            self.assertTrue(all(row['call']==call for row in rows[-2:]));self.assertIsNone(self.b.screen)

    def test_retained_lost_arrival_is_read_only_recovery_and_close_requires_another_fresh_frame(self):
        with self.s.h.h.lock.held():
            call=self.start();owner=self.owner();write=owner.store.write
            def lost(value, previous):
                frame=unpack(value['payload'])[0]['actions'][-1]['frames']
                if frame and frame[-1]['ready'] is True:raise OSError('Synthetic arrival result write loss')
                write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.act(call)
            before=(self.world.count,list(self.b.inputs));again=self.owner();retained=deepcopy(again.state['actions'][-1]['frames'][0])
            self.assertTrue(again.recover_arrival());self.assertEqual(before,(self.world.count,self.b.inputs))
            recovered=again.state['actions'][-1]['frames'][0]
            self.assertIsNone(retained.pop('ready'));self.assertEqual(retained,{k:v for k,v in recovered.items() if k!='ready'})
            again.settle();self.assertEqual(before[0]+1,self.world.count);self.assertIsNone(self.b.screen)

    def test_foreign_fixture_phase_or_replaced_owned_page_never_authorizes_close(self):
        for fault in ('phase','page'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                with self.s.h.h.lock.held():
                    call=self.start();self.ignored=True;owner=self.owner()
                    with self.assertRaises(NavigationArrivalPending):owner.act(call)
                    before=list(self.b.inputs);self.ignored=False
                    if fault=='phase':self.s.call('close')
                    else:self.s.root_id=str(uuid.UUID(int=999))
                    with self.assertRaises(NativeUIError):self.owner().settle()
                    self.assertEqual(before,self.b.inputs);self.assertEqual('places',self.b.screen)
