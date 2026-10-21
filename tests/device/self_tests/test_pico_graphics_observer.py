"""Durable independent role observation on real sampler/fixture journal logic.

Native/UI/GPU boundaries are synthetic. No product or device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.graphics_journey.fixture import GraphicsFixtureReader
from adapters.graphics_journey.observer import GraphicsObserver
from adapters.graphics_journey.readiness import GraphicsReadiness
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Journal,projection
from feature_journeys.stereo_graphics_evidence import SURFACE_PROFILE,observation
from self_tests.test_pico_graphics_surface_samples import Model as Base
from self_tests.test_stereo_graphics_pixels import RUN,TICKET,SCENE,ROOT


class Model(Base):
    def __init__(self):
        super().__init__();self.journal=Journal(clock=lambda:20000)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('graphics')
        self.journal.activate(RUN,SCENE);self.journal.activate(RUN,TICKET)
        self.client.observe=lambda:self.journal.snapshot(RUN);self.client.closed=False
        self.client.request=self.request
        self.ui.shown=False;self.ui.controls=[];self.ui.roots=[]
        native_camera=self.gpu.mutate
        def camera(packet):
            native_camera(packet)
            if not self.surface_haze:packet['source']['renderTrace'].update(hazeBatches=0,hazeDrawCommands=0)
            if not self.surface_mirror:
                trace=packet['source']['renderTrace'];trace.update(mirrorBatches=0,mirrorDrawCommands=0)
                trace['cameraBatches']=[b for b in trace['cameraBatches'] if b['role']!='mirror']
        self.gpu.mutate=camera
    def request(self,path,value=None):
        if path=='/runs/'+RUN+'/active':return self.journal.active(RUN)
        if path=='/runs/'+RUN+'/samples':self.journal.publish(RUN,value);return dict(accepted=True)
        raise ValueError('Unexpected synthetic fixture request')
    def activate(self,ticket,verb='baseline',inputs=None):
        super().activate(ticket);self.journal.activate(RUN,ticket,verb,inputs)
    def page(self):
        self.ui.shown=True;self.ui.controls=deepcopy(self.body['graphics']['controls'])
        self.ui.roots=deepcopy(self.body['graphics']['graphicsInventory']['roots'])
    def setting(self,feature,value,*,rendered=True):
        key='hazeSetting' if feature=='haze' else 'mirrorsSetting'
        self.body['nativeBefore']['graphics'][key]=value
        for row in self.ui.controls:
            if row['id']=='graphics.'+('haze' if feature=='haze' else 'mirrors'):row.update(checked=value,nativeChecked=value)
        if rendered:setattr(self,'surface_'+feature,value)
    def observer(self,role='primary'):
        source=GraphicsFixtureReader(self.client,RUN,epoch_ms=lambda:20000)
        return GraphicsObserver(self,'owned',source,role,self.lock,self.artifacts,SURFACE_PROFILE,
            monotonic=lambda:self.clock,sleep=self.sleep)


class PicoGraphicsObserverTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)

    def test_original_baseline_and_open_page_have_both_files_and_fresh_recreated_role_cursors(self):
        m=self.model
        with m.lock.held():
            owner=m.observer();first=owner.read(0,0);self.assertFalse(first['state']['dialog'])
            self.assertEqual(2,len(first['artifacts']));self.assertEqual(projection('graphics',first['state']),owner.baseline())
            m.page();m.activate('e'*32,'open',{})
            owner=m.observer();value=owner.read(first['sequence'],0);self.assertTrue(value['state']['dialog'])
            self.assertGreater(value['sequence'],first['sequence']);self.assertEqual(2,len(m.gpu.commands))
            image,file=value['artifacts']
            evidence,_=observation((m.artifacts/image['name']).read_bytes(),(m.artifacts/file['name']).read_bytes(),RUN,'e'*32,ROOT,SURFACE_PROFILE,value)
            self.assertEqual(2,evidence['stereoGraphicsEvidenceVersion'])
            before=len(m.gpu.commands)
            archived=GraphicsObserver.archive(owner.previous,run=RUN,fixture_url=m.client.url,provider_instance=m.fixture.provider.instance,
                role='primary',artifact_root=m.artifacts,image_policy=SURFACE_PROFILE)
            self.assertEqual(value['sequence'],archived['sequence']);self.assertEqual(before,len(m.gpu.commands))

    def test_actor_takes_a_separate_native_frame_and_publishes_only_its_original_projection(self):
        m=self.model
        with m.lock.held():
            primary=m.observer();value=primary.read(0,0);original=deepcopy(primary.previous)
            actor=m.observer('actor');self.assertEqual(1,actor.publish(0,0))
            self.assertEqual(original,primary.store.read());self.assertEqual(2,len(m.gpu.commands))
            entries=m.journal.snapshot(RUN)['entries'];self.assertEqual(1,len(entries))
            self.assertEqual(projection('graphics',value['state']),entries[0]['facts'])
            a,b=primary.state['last']['frame'],actor.state['last']['frame']
            self.assertNotEqual(a['capture']['requestId'],b['capture']['requestId'])
            self.assertNotEqual(a['metadata']['name'],b['metadata']['name'])

    def test_effect_archive_recomputes_original_both_eye_changes_without_a_fake_live_clock(self):
        m=self.model
        with m.lock.held():
            owner=m.observer();owner.read(0,0);m.page()
            m.activate('e'*32,'set-haze',dict(enabled=False));m.setting('haze',False);owner.read(1,0)
            m.activate('f'*32,'set-haze',dict(enabled=True));m.setting('haze',True);value=m.observer().read(2,0)
            owner=m.observer();self.assertEqual(1,len(owner.state['effects']))
            self.assertEqual({'left','right'},set(owner.state['effects'][0]['observed']['eyes']))
            before=len(m.gpu.commands)
            state=GraphicsObserver.archive(owner.previous,run=RUN,fixture_url=m.client.url,provider_instance=m.fixture.provider.instance,
                role='primary',artifact_root=m.artifacts,image_policy=SURFACE_PROFILE)
            self.assertEqual(1,len(state['effects']));self.assertEqual(before,len(m.gpu.commands))
            # Archive API accepts no current clock/guard. Live evidence itself
            # remains pinned to its original epochs and separate real guards.
            self.assertEqual(20000,value['capturedEpochMs'])
            from adapters.graphics_journey.effects import compare
            effect=owner.state['effects'][0];left,right=effect['before'],effect['after']
            with self.assertRaises(NativeUIError):compare(RUN,'haze',ROOT,m.binding,'primary',left,
                (m.artifacts/left['image']['name']).read_bytes(),right,(m.artifacts/right['image']['name']).read_bytes(),
                SURFACE_PROFILE,lambda:40000,lambda:True)

    def test_missing_original_metadata_blocks_recreation_without_another_native_capture(self):
        m=self.model
        with m.lock.held():
            owner=m.observer();value=owner.read(0,0)
            Path(m.artifacts/value['artifacts'][1]['name']).unlink();before=len(m.gpu.commands)
            with self.assertRaises((NativeUIError,OSError)):m.observer()
            self.assertEqual(before,len(m.gpu.commands))

    def test_ignored_haze_pass_is_reported_as_observed_and_cannot_supply_an_off_effect_baseline(self):
        m=self.model
        with m.lock.held():
            owner=m.observer();owner.read(0,0);m.page()
            m.activate('e'*32,'set-haze',dict(enabled=False));m.setting('haze',False,rendered=False)
            value=owner.read(1,0);self.assertFalse(value['state']['haze']);self.assertTrue(value['state']['hazePass'])
            self.assertIsNone(owner.state['offFrames']['haze'])
            m.activate('f'*32,'set-haze',dict(enabled=True));m.setting('haze',True)
            with self.assertRaises(NativeUIError):owner.read(2,0)
            before=len(m.gpu.commands)
            with self.assertRaises(NativeUIError):m.observer().read(2,0)
            self.assertEqual(before,len(m.gpu.commands))

    def test_readiness_retires_rejected_originals_before_new_capture_and_never_retries_unknown_ui(self):
        m=self.model;m.activate('e'*32);m.stale=True
        sleeps=[]
        def sleep(seconds):sleeps.append(seconds);m.sleep(seconds);m.stale=False
        with m.lock.held():
            samples=m.samples();actual=GraphicsReadiness(samples,monotonic=lambda:m.clock,sleep=sleep).read(m.active,20000)
            self.assertEqual(2,actual['sequence']);self.assertEqual(2,len(m.gpu.commands));self.assertEqual([1],sleeps)
            self.assertEqual(1,len(samples.state['readiness']));self.assertEqual([],list(m.native_root.iterdir()))

    def test_readiness_never_retries_an_unknown_ui_as_if_it_were_a_pending_world_code(self):
        m=self.model;m.page();previous=m.ui.edit
        def edit(packet):previous(packet);packet['composition']['screen']['alpha']=.5
        m.ui.edit=edit;sleeps=[]
        with m.lock.held():
            samples=m.samples()
            with self.assertRaises(NativeUIError):GraphicsReadiness(samples,monotonic=lambda:m.clock,sleep=sleeps.append).read(TICKET,20000)
            self.assertEqual(1,len(m.gpu.commands));self.assertEqual([],sleeps)
            self.assertEqual('reading',samples.state['phase']);self.assertIsNone(m.owner_store('primary').read())


if __name__=='__main__':unittest.main()
