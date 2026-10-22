"""Actual durable camera owner; explicit synthetic HMD/input/source boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import unittest
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_view import PicoEmoteView
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests import test_pico_emote_sources as source_fixture
RUN,BINDING=source_fixture.RUN,source_fixture.BINDING


class ViewBoundary:
    def __init__(self,case):
        self.sources=source_fixture.SourcesTests();self.sources.setUp();case.addCleanup(self.sources.doCleanups)
        self.lock=self.sources.lock;self.store=PrivateFeatureState(self.sources.root/'view.json')
        self.avatar=AvatarBoundary();self.avatar.epoch=self.sources.epoch;self.avatar.avatar['cameraMode']='first person look at'
        self.open=False;self.page='home';self.sequence=0;self.inputs=[];self.ignored=None;self.lost=None;self.mutate=None
        self.generation=str(uuid.uuid4());self.menu=str(uuid.uuid4());self.loaded=True
        self.io=SimpleNamespace(capture=self.capture,tablet=self.tablet,navigation=SimpleNamespace(input=self.input))
    def capture(self):
        rows=[]
        if self.open:
            ids=['scripts.menu'] if self.page=='home' else ['view-menu.view'] if self.page=='menu' else ['view-menu.first','view-menu.third']
            for key in ids:
                row=dict(id=key,token=str(uuid.uuid5(uuid.NAMESPACE_URL,key+self.menu+str(self.sequence))),enabled=True,focused=False)
                if key.startswith('view-menu.'):
                    row.update(menuInstance=self.menu,inputReady=True,checked=self.avatar.avatar['cameraMode']==
                        ('first person look at' if key=='view-menu.first' else 'third person' if key=='view-menu.third' else ''))
                rows.append(row)
        packet=dict(schemaVersion=1,bridgeId=BINDING['sessionId'],generation=self.generation,processId=31,
            elapsedMs=int(self.sources.clock*1000),updatedEpochMs=self.sources.epoch,lastCommandSequence=self.sequence,
            open=self.open,ready=self.open,viewMenuControlsVersion=1,featureControlsVersion=1,controls=rows)
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
        if control!=self.ignored:self.open=opened;self.page='home';self.generation=str(uuid.uuid4())
        if control==self.lost:raise NativeUIError('Synthetic lost controller reply')
    def input(self,control,**options):
        row=next(row for row in self.capture()['controls'] if row['id']==control)
        unittest.TestCase().assertEqual(dict(token=row['token']),options)
        self.before_input(control);self.sequence+=1
        if control!=self.ignored:
            if control=='scripts.menu':self.page='menu'
            elif control=='view-menu.view':self.page='view'
            else:self.avatar.avatar['cameraMode']='first person look at' if control=='view-menu.first' else 'third person'
        if control==self.lost:raise NativeUIError('Synthetic lost normal pointer reply')
        return {'performed':True}
    def sleep(self,seconds):self.sources.sleep(seconds)
    def owner(self,**options):
        return PicoEmoteView(self.store,BINDING,self.sources.phase,self.lock,lambda:self.io,self.avatar.reader,
            self.sources.guard,nullcontext,monotonic=lambda:self.sources.clock,sleep=self.sleep,**options)
    def cleanup_phase(self):self.sources.journal.activate(RUN,'a'*32,verb='cleanup')


class PicoEmoteViewTests(unittest.TestCase):
    def test_normal_open_view_third_and_original_first_restoration_survive_cold_reconstruction(self):
        b=ViewBoundary(self)
        with b.lock.held():
            owner=b.owner();self.assertEqual({'performed':True},owner.prepare())
            self.assertEqual('ready',owner.state['phase']);self.assertFalse(b.open)
            self.assertEqual(['tablet.open','scripts.menu','view-menu.view','view-menu.third','tablet.close'],b.inputs)
            before=deepcopy(b.inputs);self.assertEqual({'performed':True},b.owner().prepare());self.assertEqual(before,b.inputs)
            b.cleanup_phase();self.assertEqual({'performed':True},b.owner().restore())
            self.assertEqual('first person look at',b.avatar.avatar['cameraMode']);self.assertFalse(b.open)
            self.assertEqual('restored',b.owner().state['phase']);self.assertIsNotNone(b.store.read())
            before=deepcopy(b.inputs);b.owner().restore();self.assertEqual(before,b.inputs)
            # No file discard or menu/QML context retirement is synthesized.
            self.assertIsNotNone(b.store.read())

    def test_original_third_person_is_restored_without_importing_phone_selfie_or_zoom(self):
        b=ViewBoundary(self);b.avatar.avatar['cameraMode']='third person'
        with b.lock.held():
            b.owner().prepare();b.cleanup_phase();b.owner().restore()
            self.assertEqual('third person',b.avatar.avatar['cameraMode']);self.assertNotIn('view-menu.first',b.inputs)
            self.assertEqual(10,len(b.inputs))

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
        for lost in ('tablet.open','scripts.menu','view-menu.view','view-menu.third','tablet.close'):
            with self.subTest(lost=lost):
                b=ViewBoundary(self);b.lost=lost
                with b.lock.held():
                    with self.assertRaises(NativeUIError):b.owner().prepare()
                    b.lost=None;self.assertEqual({'performed':True},b.owner().prepare())
                    self.assertEqual(1,b.inputs.count(lost));self.assertEqual(5,len(b.inputs))

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
        for lost in ('tablet.open','scripts.menu','view-menu.view','view-menu.first','tablet.close'):
            with self.subTest(lost=lost):
                b=ViewBoundary(self)
                with b.lock.held():
                    b.owner().prepare();b.cleanup_phase();b.lost=lost
                    with self.assertRaises(NativeUIError):b.owner().restore()
                    before=b.inputs.count(lost);b.lost=None;b.owner().restore()
                    self.assertEqual(before,b.inputs.count(lost));self.assertEqual(10,len(b.inputs))
                    self.assertEqual('first person look at',b.avatar.avatar['cameraMode'])

    def test_later_baseline_ticket_cannot_adopt_a_lost_input_from_original_ticket(self):
        b=ViewBoundary(self);b.lost='view-menu.third'
        with b.lock.held():
            with self.assertRaises(NativeUIError):b.owner().prepare()
            before=deepcopy(b.inputs);b.sources.journal.activate(RUN,'e'*32)
            with self.assertRaises(NativeUIError):b.owner().prepare()
            self.assertEqual(before,b.inputs);self.assertIsNotNone(b.store.read())

    def test_unsupported_mode_unloaded_avatar_and_existing_open_tablet_fail_before_input(self):
        for fault in ('selfie','unloaded','open'):
            b=ViewBoundary(self)
            if fault=='selfie':b.avatar.avatar['cameraMode']='selfie'
            elif fault=='unloaded':b.avatar.avatar.update(loaded=False,geometry=None)
            else:b.open=True
            with b.lock.held(),self.subTest(fault=fault),self.assertRaises(NativeUIError):b.owner().prepare()
            self.assertEqual([],b.inputs)

    def test_foreign_candidate_or_changed_original_avatar_cannot_restore_or_adopt_history(self):
        for fault in ('candidate','geometry','pose','model','camera'):
            b=ViewBoundary(self)
            with b.lock.held():
                b.owner().prepare();before=deepcopy(b.inputs);b.cleanup_phase()
                if fault=='candidate':b.sources.okay=False
                elif fault=='geometry':b.avatar.avatar['geometry']['instance']='1'*32
                elif fault=='pose':b.avatar.avatar['pose']['feetPosition'][0]+=1
                elif fault=='model':b.avatar.avatar['modelInstance']='1'*32
                else:b.avatar.avatar['cameraMode']='selfie'
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
            self.assertEqual(5,len(b.inputs))


if __name__=='__main__':unittest.main()
