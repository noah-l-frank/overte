"""Original closed-tablet source journals/files; all native GPU/VR seams fake."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from adapters.navigation_frames import NavigationFrames
from adapters.navigation_stereo import NavigationStereo
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import result
from feature_journeys.scenarios import VERSION,SCENARIOS
from feature_journeys.fixtures import marker_bytes
from feature_journeys.stereo_navigation_evidence import observation,original_name
from self_tests import test_navigation_tablet_close as close_tests
from self_tests.test_navigation_transit import SELECT,RUN,SCENE
from self_tests.test_stereo_navigation_evidence import POLICY


def clock_boundary(value,epoch):
    """Set synthetic producer clocks before original Python readers see them.

    The old host GPU/native seams have fixed 20000ms source clocks. These tests
    need their native boundary clock to progress after normal UI quiet; this
    never rewrites any acquired original journal, PNG or adapter observation.
    """
    if type(value) is dict:
        for key,child in value.items():
            if key.endswith('EpochMs') and type(child) is int and child>=20000:value[key]=child+epoch-20000
            else:clock_boundary(child,epoch)
    elif type(value) is list:
        for child in value:clock_boundary(child,epoch)


class NavigationFramesTests(unittest.TestCase):
    def setUp(self):
        self.fixture=close_tests.NavigationTabletCloseTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.world=self.fixture.world;self.closed=self.fixture.owner();self.closed.close(SELECT);self.world.active=SELECT
        self.path=self.world.root/'navigation-frames.json'
        native=self.world._native_feature_observer
        def reader(*args,**kwargs):
            source=native(*args,**kwargs);source.clock_ms=self.world.epoch;return source
        self.world._native_feature_observer=reader
        for boundary in (self.world.features,self.world.gpu):
            old=boundary.mutate
            def source(value,old=old):
                if old:old(value)
                clock_boundary(value,self.world.epoch())
            boundary.mutate=source
        for boundary in (self.world.storage,self.world.inventory):
            old=boundary.mutate
            def source(value,old=old):
                if old:old(value)
                value['capturedEpochMs']=self.world.epoch()
            boundary.mutate=source
        original=self.world._world_render_capture
        def capture(*args,**kwargs):
            owner=original(*args,**kwargs)
            for source in (owner.capture,owner.storage,owner.receipts.cleanup):source.clock_ms=self.world.epoch
            return owner
        self.world._world_render_capture=capture
        native_pixels=self.world.gpu.send
        def gpu(command):
            # Reuse the existing synthetic stereo scene, with this fixture's
            # actual owned run challenge before the native source is produced.
            with Image.open(io.BytesIO(self.world.gpu.raw)) as original:image=original.copy()
            with Image.open(io.BytesIO(marker_bytes(RUN,self.world.active))) as original:
                marker=original.resize((320,80),Image.Resampling.NEAREST).convert('RGBA')
            image.paste(marker,(288,248));image.paste(marker,(992,248));out=io.BytesIO();image.save(out,format='PNG')
            self.world.gpu.raw=out.getvalue();self.world.gpu.pixels=hashlib.sha256(image.tobytes()).hexdigest()
            self.world.storage.raw=self.world.gpu.raw;return native_pixels(command)
        self.world.gpu.send=gpu
    def stereo(self,journal,role='primary'):
        return NavigationStereo(self.closed.transit.arrival,
            lambda:self.world._world_render_capture('owned',read_only=True,role=role,require_frame_view=True,source_lock=self.world.lock),
            self.world.artifacts/original_name(RUN,role,journal),self.world.artifacts,RUN,self.world.binding,self.world.lock,self.world.guard,
            role=role,journal_id=journal,ui_factory=lambda:self.world.ui.source(),
            native_factory=lambda:self.world._native_feature_observer('owned',read_only=True),monotonic=lambda:self.world.clock)
    def owner(self):
        return NavigationFrames(self.closed,self.stereo,self.path,self.world.artifacts,'primary',self.world.epoch,self.world.guard,
            monotonic=lambda:self.world.clock)
    def sample(self,frame):
        # Only the image verifier is exercised here. Other Navigation fields
        # remain explicit synthetic test inputs, not new feature implementation.
        return dict(schemaVersion=1,contractVersion=VERSION,runId=RUN,sequence=frame['sequence'],capturedEpochMs=frame['capturedEpochMs'],
            state=dict(SCENARIOS['world-navigation']['baseline'],location=frame['location']),resources=[],
            lifecycle=frame['lifecycle'],artifacts=frame['artifacts'])
    def test_normal_closed_source_publishes_new_original_images_and_common_two_eye_verifier_accepts(self):
        initial=len(self.world.gpu.commands);names=set()
        with self.world.lock.held():
            for index in range(3):
                frame=self.owner().read(SELECT,index);sample=self.sample(frame)
                result('feature.world-navigation.observe',sample)
                image,metadata=[self.world.artifacts/row['name'] for row in frame['artifacts']]
                measured,_=observation(image.read_bytes(),metadata.read_bytes(),RUN,SELECT,
                    self.world.client.url+'/runs/'+RUN+'/',POLICY,sample)
                self.assertEqual('A',measured['location']);self.assertEqual(index+1,frame['sequence']);names.add(metadata.name)
                self.world.sleep(.1)
        self.assertEqual(3,len(names));self.assertEqual(initial+3,len(self.world.gpu.commands))
        self.assertEqual(['tablet.close'],self.fixture.controllers);self.assertIsNone(self.world.owner_store('primary').read())
        self.assertEqual([],list(self.world.native_root.iterdir()))
    def test_lost_publication_returns_same_still_fresh_original_without_reacquiring_or_retiming(self):
        with self.world.lock.held():
            first=self.owner().read(SELECT,0);count=len(self.world.gpu.commands);self.world.sleep(.1)
            resumed=self.owner().read(SELECT,0)
            for field in ('sequence','capturedEpochMs','journalId','artifacts'):self.assertEqual(first[field],resumed[field])
            self.assertEqual(count,len(self.world.gpu.commands))
            fresh=self.owner().read(SELECT,1);self.assertEqual(2,fresh['sequence']);self.assertNotEqual(first['journalId'],fresh['journalId'])
    def test_lost_native_acquisition_keeps_original_pending_identity_and_never_captures_again(self):
        self.world.capture_error=True
        with self.world.lock.held():
            with self.assertRaises(NativeUIError):self.owner().read(SELECT,0)
            pending=deepcopy(self.owner().state['pending']);count=len(self.world.gpu.commands);self.world.capture_error=False
            with self.assertRaises(NativeUIError):self.owner().read(SELECT,0)
            self.assertEqual(pending,self.owner().state['pending']);self.assertEqual(count,len(self.world.gpu.commands))
            self.assertIsNotNone(self.world.owner_store('primary').read())
    def test_reopened_tablet_is_refused_passively_without_controller_repair_or_capture(self):
        self.fixture.shown=True;self.fixture.fixture.widgets.generation='33333333-3333-4333-8333-333333333333'
        self.fixture.fixture.ray.panel_boundary.open=True;count=len(self.world.gpu.commands)
        with self.world.lock.held(),self.assertRaises(NativeUIError):self.owner().read(SELECT,0)
        self.assertEqual(['tablet.close'],self.fixture.controllers);self.assertEqual(count,len(self.world.gpu.commands))
    def test_stale_known_publication_cannot_become_current_by_relabeling_its_epoch_or_sequence(self):
        with self.world.lock.held():
            first=self.owner().read(SELECT,0);count=len(self.world.gpu.commands);self.world.sleep(2)
            with self.assertRaises(NativeUIError):self.owner().read(SELECT,0)
            self.assertEqual(count,len(self.world.gpu.commands));self.assertEqual(1,self.owner().state['sequence'])
            owner=self.stereo(first['journalId']);self.assertEqual(first['capturedEpochMs'],owner.state['frame']['before']['probe']['sampleEpochMs'])
    def test_changed_original_metadata_or_pixels_refuses_before_any_new_acquisition(self):
        for kind in ('metadata','image'):
            self.setUp()
            with self.world.lock.held():
                frame=self.owner().read(SELECT,0);count=len(self.world.gpu.commands)
                path=self.world.artifacts/next(r['name'] for r in frame['artifacts'] if r['kind']==('file' if kind=='metadata' else 'image'))
                path.write_bytes(path.read_bytes()+(b' ' if kind=='metadata' else b'x'))
                with self.subTest(kind=kind),self.assertRaises(NativeUIError):self.owner()
                self.assertEqual(count,len(self.world.gpu.commands))
    def test_competing_stale_publisher_refuses_before_another_acquisition(self):
        with self.world.lock.held():
            old=self.owner();self.owner().read(SELECT,0);count=len(self.world.gpu.commands)
            with self.assertRaises(NativeUIError):old.read(SELECT,0)
            self.assertEqual(count,len(self.world.gpu.commands))
    def test_reused_native_render_id_under_a_new_journal_keeps_completed_source_owned_in_pending(self):
        with self.world.lock.held():
            first=self.owner().read(SELECT,0);identity=self.stereo(first['journalId']).state['frame']['capture']['source']['renderTrace']['frameId']
            old=self.world.gpu.mutate
            def reused(value):old(value);value['source']['renderTrace']['frameId']=identity
            self.world.gpu.mutate=reused
            with self.assertRaises(NativeUIError):self.owner().read(SELECT,1)
            count=len(self.world.gpu.commands);pending=deepcopy(self.owner().state['pending'])
            self.assertEqual('complete',self.stereo(pending['journalId']).state['phase'])
            with self.assertRaises(NativeUIError):self.owner().read(SELECT,1)
            self.assertEqual(count,len(self.world.gpu.commands));self.assertIsNotNone(self.owner().state['pending'])
    def test_actual_private_factory_pins_original_manager_lock_role_and_arrival_source(self):
        from pathlib import Path
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as n
        fixture=n.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups);adapter=fixture.instance()
        adapter._scripts=lambda target:SimpleNamespace(binding=self.world.binding)
        adapter._native_feature_observer=lambda target:SimpleNamespace(guard=self.world.guard,clock_ms=self.world.epoch,monotonic=lambda:self.world.clock)
        def lock(_self,target,provided):self.assertEqual('owned',target);self.assertIs(self.world.lock,provided);return provided
        def stereo(target,path,root,run,scene,**kw):
            self.assertEqual(('owned',self.world.artifacts,RUN,SCENE),(target,root,run,scene))
            self.assertIs(self.world.lock,kw['source_lock']);self.assertIs(self.closed.transit.arrival,kw['arrival'])
            self.assertEqual('actor',kw['role']);self.assertEqual(path,self.world.artifacts/original_name(RUN,'actor',kw['journal_id']))
            return self.stereo(kw['journal_id'],'actor')
        adapter._navigation_stereo=stereo
        with patch('adapters.pico4.graphics_binding.PicoGraphicsBinding._lock',lock):
            with self.assertRaises(ValueError):adapter._navigation_frames('owned',self.path,self.world.artifacts,self.closed,source_lock=self.world.lock,role='actor')
            with self.world.lock.held():
                primary=self.owner().read(SELECT,0)
                actor=adapter._navigation_frames('owned',self.world.root/'actor-frames.json',self.world.artifacts,self.closed,
                    source_lock=self.world.lock,role='actor');frame=actor.read(SELECT,0)
                self.assertNotEqual(primary['journalId'],frame['journalId'])
                image,metadata=[self.world.artifacts/row['name'] for row in frame['artifacts']]
                measured,_=observation(image.read_bytes(),metadata.read_bytes(),RUN,SELECT,self.world.client.url+'/runs/'+RUN+'/',
                    POLICY,self.sample(frame),role='actor');self.assertEqual('A',measured['location'])
        self.assertIsNone(self.world.owner_store('primary').read());self.assertIsNone(self.world.owner_store('actor').read())


if __name__=='__main__':unittest.main()
