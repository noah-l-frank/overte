"""Actual durable camera owner; explicit synthetic HMD/input/source boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_view import PicoEmoteView
from adapters.pico4.tablet_home import PicoTabletHome
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests import test_pico_emote_sources as source_fixture
from self_tests import test_pico_tablet_home as home_fixture
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from openxr_input.adapter_session import PicoOpenXrAdapterSession,AdapterSessionError
RUN,BINDING=source_fixture.RUN,source_fixture.BINDING


class ViewBoundary:
    def __init__(self,case):
        self.sources=source_fixture.SourcesTests();self.sources.setUp();case.addCleanup(self.sources.doCleanups)
        self.lock=self.sources.lock;self.store=PrivateFeatureState(self.sources.root/'view.json')
        self.avatar=AvatarBoundary();self.avatar.epoch=self.sources.epoch;self.avatar.avatar['cameraMode']='first person look at'
        self.avatar.avatar.update(cameraStateVersion=1,cameraState=dict(hmd=True,boomLength=.5,zoomMin=.5,zoomDefault=1.5))
        self.open=False;self.page='home';self.sequence=0;self.inputs=[];self.ignored=None;self.lost=None;self.mutate=None
        self.generation=str(uuid.uuid4());self.menu=str(uuid.uuid4());self.loaded=True
        self.io=SimpleNamespace(capture=self.capture,tablet=self.tablet,navigation=SimpleNamespace(input=self.input))
        self.home_sequence=0;self.home_value=home_fixture.original()
        source=SimpleNamespace(capture=self.capture_home,pid=31,clock_ms=lambda:self.sources.epoch,
            monotonic=lambda:self.sources.clock,sleep=self.sleep,guard=self.sources.guard)
        self.home=PicoTabletHome(source,self.home_stage)
        self.life=False;self.life_sequence=0;self.life_rows=[]
        self.neutral_fault=None;outer=self
        class Transport(FakeTransport):
            def stage(self,envelope,profile):
                from adapters.script_journey.history import unpack
                state=unpack(outer.store.read()['payload'])[0];row=state['steps'][-1]
                unittest.TestCase().assertEqual(envelope,row['stream']['envelope'])
                value=super().stage(envelope,profile)
                operation=envelope['commands'][0]['operation']
                lost=outer.lost;outer.lost=None
                try:
                    if operation=='input.primary':outer.home_effect()
                    else:outer.tablet(operation=='tablet.open')
                finally:outer.lost=lost
                return value
            def read_status(self,**options):
                value=super().read_status(**options);value['updatedEpochMs']=outer.sources.epoch
                if options.get('expected_sequence') is not None:
                    operation=self.envelopes[-1]['commands'][0]['operation']
                    control='tablet.home-ray' if operation=='input.primary' else operation
                    if outer.lost==control:raise NativeUIError('Explicit lost original controller ACK after committed host sequence')
                if options.get('expected_sequence') is None:
                    if outer.neutral_fault=='missing':raise AdapterSessionError('Explicit lost neutral read')
                    if outer.neutral_fault=='foreign':value['acceptedSequence']+=1
                    if outer.neutral_fault=='active':value.update(state='active',activeCommandId='foreign')
                return value
        self.transport=Transport();directory=self.sources.root/'controller';directory.mkdir(mode=0o700)
        self.session=PicoOpenXrAdapterSession(self.transport,'explicit-view-controller-boundary',directory)
        self.session.begin(BINDING['processIdentity'])
        self.session._ack_timeout=lambda:.001
    def capture_home(self):
        self.home_sequence+=1
        value=deepcopy(self.home_value);value.update(commandId=uuid.uuid4().hex,sourceSequence=self.home_sequence,
            processId=31,capturedEpochMs=self.sources.epoch,elapsedMs=int(self.sources.clock*1000),
            tabletShown=self.open,onHomeScreen=self.page=='home',visible=self.open)
        return value
    def home_stage(self,pose,*,intent=None):
        return self.session.stage(BINDING['processIdentity'],'input.primary',pose,intent=intent)
    def home_effect(self):
        self.before_input('tablet.home-ray')
        if self.ignored!='tablet.home-ray':self.page='home'
        if self.lost=='tablet.home-ray':raise NativeUIError('Synthetic lost actual Home ray result')
    def capture(self):
        rows=[]
        if self.open:
            ids=['scripts.menu'] if self.page=='home' else ['view-menu.view'] if self.page=='menu' else ['view-menu.first','view-menu.third']
            for key in ids:
                row=dict(id=key,token=str(uuid.uuid5(uuid.NAMESPACE_URL,key+self.menu+str(self.sequence))),enabled=True,focused=False)
                if key.startswith('view-menu.'):
                    row.update(menuInstance=self.menu,inputReady=True,checked=self.avatar.avatar['cameraMode']==
                        ('first person look at' if key=='view-menu.first' else 'look at' if key=='view-menu.third' else ''))
                rows.append(row)
        packet=dict(schemaVersion=1,bridgeId=BINDING['sessionId'],generation=self.generation,processId=31,
            elapsedMs=int(self.sources.clock*1000),updatedEpochMs=self.sources.epoch,lastCommandSequence=self.sequence,
            open=self.open,ready=self.open,viewMenuControlsVersion=1,featureControlsVersion=1,controls=rows)
        if self.life:
            self.life_sequence+=1
            packet.update(picoViewMenuLifetimeVersion=1,picoViewMenuLifetimes=dict(instance='a'*32,sequence=self.life_sequence,
                capturedEpochMs=self.sources.epoch,originals=deepcopy(self.life_rows)))
        if self.mutate:self.mutate(packet)
        return packet
    def before_input(self,control):
        need=unittest.TestCase()
        header=self.store.read();need.assertIsNotNone(header)
        from adapters.script_journey.history import unpack
        row=unpack(header['payload'])[0]['steps'][-1]
        need.assertEqual(control,row['control']);need.assertEqual(1,len(row['intent']));need.assertIsNone(row['after'])
        self.inputs.append(control)
    def tablet(self,opened):
        control='tablet.open' if opened else 'tablet.close';self.before_input(control)
        self.sequence+=1
        if control!=self.ignored:self.open=opened;self.generation=str(uuid.uuid4())
        if control==self.lost:raise NativeUIError('Synthetic lost controller reply')
    def input(self,control,**options):
        row=next(row for row in self.capture()['controls'] if row['id']==control)
        unittest.TestCase().assertEqual(dict(token=row['token']),options)
        self.before_input(control);self.sequence+=1
        if control!=self.ignored:
            if control=='scripts.menu':
                self.page='menu'
                if self.life:
                    self.life_rows.append(dict(instance=uuid.uuid4().hex,firstObservedEpochMs=self.sources.epoch,
                        pageAlive=True,stackAlive=True,timerAlive=True,contextAlive=True,timerContextAlive=True,
                        alive=True,timerRunning=False,pendingMenuItem=False))
            elif control=='view-menu.view':self.page='view'
            else:
                mode='first person look at' if control=='view-menu.first' else 'look at';source=self.avatar.avatar
                if source['cameraMode']!=mode:
                    state=source['cameraState']
                    if mode=='first person look at':state['boomLength']=state['zoomMin']
                    elif state['boomLength']==state['zoomMin']:state['boomLength']=state['zoomDefault']
                source['cameraMode']=mode
        if control==self.lost:raise NativeUIError('Synthetic lost normal pointer reply')
        return {'performed':True}
    def sleep(self,seconds):self.sources.sleep(seconds)
    def owner(self,**options):
        return PicoEmoteView(self.store,BINDING,self.sources.phase,self.lock,lambda:self.io,self.avatar.reader,
            self.sources.guard,nullcontext,lambda:self.home,lambda:self.session,monotonic=lambda:self.sources.clock,sleep=self.sleep,**options)
    def cleanup_phase(self):self.sources.journal.activate(RUN,'a'*32,verb='cleanup')


class PicoEmoteViewTests(unittest.TestCase):
    def test_normal_open_view_third_and_original_first_restoration_survive_cold_reconstruction(self):
        b=ViewBoundary(self)
        with b.lock.held():
            owner=b.owner();self.assertEqual({'performed':True},owner.prepare())
            self.assertEqual('ready',owner.state['phase']);self.assertFalse(b.open)
            self.assertEqual(['tablet.open','scripts.menu','view-menu.view','view-menu.third','tablet.home-ray','tablet.close'],b.inputs)
            before=deepcopy(b.inputs);self.assertEqual({'performed':True},b.owner().prepare());self.assertEqual(before,b.inputs)
            b.cleanup_phase();self.assertEqual({'performed':True},b.owner().restore())
            self.assertEqual('first person look at',b.avatar.avatar['cameraMode']);self.assertFalse(b.open)
            self.assertEqual('restored',b.owner().state['phase']);self.assertIsNotNone(b.store.read())
            before=deepcopy(b.inputs);b.owner().restore();self.assertEqual(before,b.inputs)
            # No file discard or menu/QML context retirement is synthesized.
            self.assertIsNotNone(b.store.read())

    def test_original_third_person_is_restored_without_importing_phone_selfie_or_zoom(self):
        b=ViewBoundary(self);b.avatar.avatar['cameraMode']='look at';b.avatar.avatar['cameraState']['boomLength']=4.25
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();b.owner().restore()
            self.assertEqual('look at',b.avatar.avatar['cameraMode']);self.assertNotIn('view-menu.first',b.inputs)
            self.assertEqual(4.25,b.avatar.avatar['cameraState']['boomLength'])
            self.assertEqual(12,len(b.inputs))

    def test_ignored_pointer_ack_cannot_become_camera_success_or_be_replayed(self):
        b=ViewBoundary(self);b.ignored='view-menu.third'
        with b.lock.held():
            with self.assertRaises(NativeUIError):b.owner().prepare()
            before=deepcopy(b.inputs)
            with self.assertRaises(NativeUIError):b.owner().prepare()
            self.assertEqual(before,b.inputs);self.assertEqual(1,b.inputs.count('view-menu.third'))
            b.cleanup_phase()
            with self.assertRaises(NativeUIError):b.owner().restore()
            self.assertIsNotNone(b.store.read())

    def test_lost_pointer_result_reconciles_actual_effect_without_another_pointer(self):
        for lost in ('tablet.open','scripts.menu','view-menu.view','view-menu.third','tablet.home-ray','tablet.close'):
            with self.subTest(lost=lost):
                b=ViewBoundary(self);b.lost=lost
                with b.lock.held():
                    with self.assertRaises(NativeUIError):b.owner().prepare()
                    b.lost=None;self.assertEqual({'performed':True},b.owner().prepare())
                    self.assertEqual(1,b.inputs.count(lost));self.assertEqual(6,len(b.inputs))

    def test_failed_durable_intent_before_input_stays_owned_without_replay(self):
        b=ViewBoundary(self)
        with b.lock.held():
            owner=b.owner();write=b.store.write
            def fail(value,previous):
                from adapters.script_journey.history import unpack
                if unpack(value['payload'])[0]['steps']:raise OSError('Synthetic lost journal write')
                return write(value,previous)
            b.store.write=fail
            with self.assertRaises(OSError):owner.prepare()
            self.assertEqual([],b.inputs);self.assertIsNotNone(b.store.read())

    def test_lost_restore_results_reconcile_only_original_effect_and_never_repeat_input(self):
        for lost in ('tablet.open','scripts.menu','view-menu.view','view-menu.first','tablet.home-ray','tablet.close'):
            with self.subTest(lost=lost):
                b=ViewBoundary(self)
                with b.lock.held():
                    b.owner().prepare();b.cleanup_phase();b.lost=lost
                    with self.assertRaises(NativeUIError):b.owner().restore()
                    before=b.inputs.count(lost);b.lost=None;b.owner().restore()
                    self.assertEqual(before,b.inputs.count(lost));self.assertEqual(12,len(b.inputs))
                    self.assertEqual('first person look at',b.avatar.avatar['cameraMode'])

    def test_later_baseline_ticket_cannot_adopt_a_lost_input_from_original_ticket(self):
        b=ViewBoundary(self);b.lost='view-menu.third'
        with b.lock.held():
            with self.assertRaises(NativeUIError):b.owner().prepare()
            before=deepcopy(b.inputs);b.sources.journal.activate(RUN,'e'*32)
            with self.assertRaises(NativeUIError):b.owner().prepare()
            self.assertEqual(before,b.inputs);self.assertIsNotNone(b.store.read())

    def test_unsupported_mode_unloaded_avatar_and_existing_open_tablet_fail_before_input(self):
        for fault in ('selfie','legacy-third','unloaded','open','hidden-menu','custom-first-boom','legacy-source','desktop'):
            b=ViewBoundary(self)
            if fault=='selfie':b.avatar.avatar['cameraMode']='selfie'
            elif fault=='legacy-third':b.avatar.avatar['cameraMode']='third person'
            elif fault=='unloaded':b.avatar.avatar.update(loaded=False,geometry=None)
            elif fault=='custom-first-boom':b.avatar.avatar['cameraState']['boomLength']=5
            elif fault=='legacy-source':b.avatar.avatar.pop('cameraState');b.avatar.avatar.pop('cameraStateVersion')
            elif fault=='desktop':b.avatar.avatar['cameraState']['hmd']=False
            elif fault=='hidden-menu':b.page='view'
            else:b.open=True
            with b.lock.held(),self.subTest(fault=fault),self.assertRaises(NativeUIError):b.owner().prepare()
            self.assertEqual([],b.inputs)

    def test_foreign_candidate_or_changed_original_avatar_cannot_restore_or_adopt_history(self):
        for fault in ('candidate','geometry','pose','model','camera','boom','home'):
            b=ViewBoundary(self)
            with b.lock.held():
                b.owner().prepare();before=deepcopy(b.inputs);b.cleanup_phase()
                if fault=='candidate':b.sources.okay=False
                elif fault=='geometry':b.avatar.avatar['geometry']['instance']='1'*32
                elif fault=='pose':b.avatar.avatar['pose']['feetPosition'][0]+=1
                elif fault=='model':b.avatar.avatar['modelInstance']='1'*32
                elif fault=='camera':b.avatar.avatar['cameraMode']='selfie'
                elif fault=='boom':b.avatar.avatar['cameraState']['boomLength']+=1
                else:b.home_value['homeId']='3'*32
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.owner().restore()
                self.assertEqual(before,b.inputs);self.assertIsNotNone(b.store.read())

    def test_final_original_clock_and_phase_change_cannot_retime_or_dispatch(self):
        for fault in ('native','phase'):
            b=ViewBoundary(self);read=b.io.capture
            def changed():
                value=read()
                if fault=='native':b.avatar.epoch+=2000
                else:b.cleanup_phase()
                return value
            b.io.capture=changed
            with b.lock.held(),self.subTest(fault=fault),self.assertRaises((RuntimeError,ValueError)):b.owner().prepare()
            self.assertEqual([],b.inputs)

    def test_navigation_waits_for_actual_newer_timestamp_without_relabeling_old_source(self):
        b=ViewBoundary(self);capture=b.capture;reads=[0]
        def lagging():
            value=capture();reads[0]+=1
            if reads[0]<=2:value['updatedEpochMs']=b.avatar.epoch-1
            return value
        b.io.capture=lagging
        with b.lock.held():
            owner=b.owner();owner.prepare();self.assertGreaterEqual(b.sources.clock,.1)
            self.assertEqual(b.avatar.epoch,owner.state['original']['widgets']['updatedEpochMs'])
            self.assertEqual(6,len(b.inputs))

    def test_legacy_v1_v2_v3_owner_remains_retained_without_inventing_original_controller_retirement(self):
        for version in (1,2,3):
            b=ViewBoundary(self)
            with b.lock.held():
                b.owner().prepare();value=b.store.read();value['picoEmoteViewVersion']=version;b.store.write(value,b.store.read())
                before=deepcopy(b.inputs)
                with self.subTest(version=version),self.assertRaises(NativeUIError):b.owner()
                self.assertEqual(before,b.inputs);self.assertEqual(value,b.store.read())

    def test_ignored_actual_home_ray_cannot_claim_closed_home_or_repeat_the_gesture(self):
        b=ViewBoundary(self);b.ignored='tablet.home-ray'
        with b.lock.held():
            with self.assertRaises(NativeUIError):b.owner().prepare()
            before=deepcopy(b.inputs)
            with self.assertRaises(NativeUIError):b.owner().prepare()
            self.assertEqual(before,b.inputs);self.assertEqual(1,b.inputs.count('tablet.home-ray'))
            self.assertTrue(b.open);self.assertEqual('view',b.page);self.assertIsNotNone(b.store.read())

    def test_menu_retirement_keeps_original_alive_contexts_and_requires_all_known_object_deaths(self):
        b=ViewBoundary(self);b.life=True
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();owner=b.owner();owner.restore()
            self.assertEqual(2,len(b.life_rows));before=deepcopy(b.inputs)
            self.assertFalse(owner.menu_retirement()['retired'])
            for row in b.life_rows:row.update(pageAlive=False,stackAlive=False,timerAlive=False)
            self.assertFalse(b.owner().menu_retirement()['retired'])
            for row in b.life_rows:row.update(alive=False,contextAlive=False,timerContextAlive=False)
            self.assertTrue(b.owner().menu_retirement()['retired']);self.assertEqual(before,b.inputs)
            self.assertIsNotNone(b.store.read())

    def test_missing_or_removed_original_menu_inventory_never_authorizes_retirement(self):
        b=ViewBoundary(self)
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();owner=b.owner();owner.restore()
            with self.assertRaises(NativeUIError):owner.menu_retirement()
            self.assertIsNotNone(b.store.read())

    def test_each_original_controller_envelope_precedes_transport_and_neutral_survives_cold_restore(self):
        b=ViewBoundary(self)
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();b.owner().restore();before=deepcopy(b.inputs)
            owner=b.owner();proof=owner.controller_retirement()
            self.assertTrue(proof['retired']);self.assertTrue(proof['journalsRetained'])
            self.assertEqual(6,len(proof['streams']));self.assertEqual(6,len(b.transport.envelopes))
            self.assertEqual([1,2,3,4,5,6],[row['envelope']['sequence'] for row in proof['streams']])
            self.assertEqual(['tablet.open','input.primary','tablet.close']*2,
                [row['envelope']['commands'][0]['operation'] for row in proof['streams']])
            self.assertEqual(before,b.inputs);self.assertIsNotNone(b.store.read())

    def test_missing_foreign_active_or_future_neutral_never_becomes_completed_step_or_replayed_input(self):
        for fault in ('missing','foreign','active','future'):
            b=ViewBoundary(self);b.neutral_fault=fault
            if fault=='future':
                read=b.transport.read_status
                def future(**options):
                    value=read(**options)
                    if options.get('expected_sequence') is None:value['updatedEpochMs']+=2000
                    return value
                b.transport.read_status=future
            with b.lock.held(),self.subTest(fault=fault):
                with self.assertRaises(RuntimeError):b.owner().prepare()
                before=deepcopy(b.inputs)
                with self.assertRaises(RuntimeError):b.owner().prepare()
                self.assertEqual(before,b.inputs);self.assertEqual(['tablet.open'],b.inputs)
                self.assertIsNotNone(b.store.read())

    def test_lost_neutral_read_reconciles_original_consumed_stream_without_new_gesture(self):
        b=ViewBoundary(self);b.neutral_fault='missing'
        with b.lock.held():
            with self.assertRaises(RuntimeError):b.owner().prepare()
            self.assertEqual(['tablet.open'],b.inputs)
            b.neutral_fault=None;b.owner().prepare()
            self.assertEqual(1,b.inputs.count('tablet.open'));self.assertEqual(3,len(b.transport.envelopes))

    def test_foreign_stream_after_restoration_cannot_be_adopted_as_owned_controller_cleanup(self):
        b=ViewBoundary(self)
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();b.owner().restore();before=deepcopy(b.inputs)
            with b.session._lock():
                state=b.session._load();state['nextSequence']+=1;b.session._save(state)
            with self.assertRaises(RuntimeError):b.owner().controller_retirement()
            self.assertEqual(before,b.inputs);self.assertIsNotNone(b.store.read())

    def test_failure_after_original_stream_write_cannot_dispatch_or_erase_the_envelope(self):
        from adapters.script_journey.history import unpack
        b=ViewBoundary(self);write=b.store.write
        def lost(value,previous):
            write(value,previous)
            steps=unpack(value['payload'])[0]['steps']
            if steps and steps[-1]['stream'] and steps[-1]['stream']['envelope'] is not None:
                raise OSError('Explicit lost original stream CAS acknowledgement')
        with b.lock.held():
            b.store.write=lost
            with self.assertRaises(OSError):b.owner().prepare()
            b.store.write=write;original=b.store.read()
            self.assertEqual([],b.inputs);self.assertIsNotNone(unpack(original['payload'])[0]['steps'][0]['stream']['envelope'])
            with self.assertRaises(RuntimeError):b.owner().prepare()
            self.assertEqual(original,b.store.read());self.assertEqual([],b.inputs)

    def test_slow_original_stream_intent_cannot_dispatch_after_freshness_budget(self):
        from adapters.script_journey.history import unpack
        b=ViewBoundary(self);write=b.store.write
        def slow(value,previous):
            write(value,previous)
            steps=unpack(value['payload'])[0]['steps']
            if steps and steps[-1]['stream'] and steps[-1]['stream']['envelope'] is not None:b.sleep(2)
        with b.lock.held():
            b.store.write=slow
            with self.assertRaises(RuntimeError):b.owner().prepare()
            self.assertEqual([],b.inputs);self.assertEqual([],b.transport.envelopes)
            self.assertIsNotNone(unpack(b.store.read()['payload'])[0]['steps'][0]['stream']['envelope'])
        b=ViewBoundary(self);b.life=True
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();owner=b.owner();owner.restore();b.life=False
            with self.assertRaises(NativeUIError):owner.menu_retirement()
            self.assertIsNotNone(b.store.read())


if __name__=='__main__':unittest.main()
