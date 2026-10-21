"""Real v5 sampler and artifact/retirement owners at synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.graphics_journey.samples import GraphicsSamples,GraphicsMarkerPending
from adapters.normal_ui import NativeUIError
from feature_journeys.stereo_graphics_evidence import SURFACE_PROFILE,observation
from self_tests.test_pico_graphics_samples import Model as Base
from self_tests.test_stereo_graphics_surface_evidence import Source
from self_tests.test_stereo_graphics_surfaces import SurfacePixels
from self_tests.test_stereo_graphics_pixels import RUN,TICKET,ROOT
from self_tests.test_pico_graphics_composition import composition


class Model(Base):
    def __init__(self):
        super().__init__();self.fixture=Source();self.raw,self.body,_=self.fixture.acquire()
        self.surface_haze=True;self.surface_mirror=True
        self.client.graphics_instance=self.fixture.provider.instance
        self.subject.source=deepcopy(self.body['subjectBefore']['source'])
        self.ui.shown=True;self.ui.controls=deepcopy(self.body['graphics']['controls'])
        self.ui.roots=deepcopy(self.body['graphics']['graphicsInventory']['roots'])
        self.ui.edit=lambda packet:packet.update(graphicsObservationVersion=2,composition=composition())
    def _world_render_capture(self,*args,**options):
        owned=super()._world_render_capture(*args,**options);send=owned.capture.send
        def stimulus(*,card_ticket):
            for stem in ('graphics-haze-code.v1','graphics-reflection-code.v1'):self.fixture.deliver(self.active,stem+'.png')
            return SurfacePixels(ticket=card_ticket,haze=self.surface_haze,mirror=self.surface_mirror)
        def capture(command):
            with patch('self_tests.test_pico_graphics_samples.JourneyPixels',side_effect=stimulus):return send(command)
        owned.capture.send=capture;return owned
    def samples(self,role='primary'):
        return GraphicsSamples(self,'owned',self.client,RUN,self.fixture.provider.instance,role,0,self.lock,self.artifacts,SURFACE_PROFILE,
            epoch_ms=lambda:20000,monotonic=lambda:self.clock)


class PicoGraphicsSurfaceSampleTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_original_v2_pair_matches_independent_verifier_and_preserves_after_ui_across_recreation(self):
        m=self.model
        with m.lock.held():
            owner=m.samples();actual=owner.read(TICKET,20000);frame=owner.state['frame']
            self.assertEqual(frame['graphicsAfter'],owner.state['cursors']['graphics'])
            self.assertGreater(frame['graphicsAfter']['sourceSequence'],frame['graphics']['sourceSequence'])
            sample=dict(schemaVersion=1,contractVersion=16,runId=RUN,sequence=actual['sequence'],capturedEpochMs=actual['capturedEpochMs'],
                state=actual['state'],resources=actual['resources'],lifecycle=actual['lifecycle'],artifacts=[
                    dict(kind=kind,name=frame[key]['name'],sequence=actual['sequence'],capturedEpochMs=frame['capture']['capturedEpochMs'],ticket=TICKET,
                        **({'source':'world-render-target'} if kind=='image' else {})) for kind,key in (('image','image'),('file','metadata'))])
            value,_=observation(Path(actual['imagePath']).read_bytes(),Path(actual['metadataPath']).read_bytes(),RUN,TICKET,ROOT,SURFACE_PROFILE,sample)
            self.assertEqual(2,value['stereoGraphicsEvidenceVersion']);self.assertTrue(actual['state']['dialog'])
            self.assertEqual(['panel:graphics','panel:graphics-tablet'],actual['resources'])
            self.assertIsNone(m.owner_store('primary').read());self.assertEqual([],list(m.native_root.iterdir()))
            recreated=m.samples();recreated.read(TICKET,20000)
            self.assertGreater(recreated.state['frame']['graphics']['sourceSequence'],frame['graphicsAfter']['sourceSequence'])
            archived=GraphicsSamples.archive(recreated.previous,client=m.client,run=RUN,provider_instance=m.fixture.provider.instance,
                role='primary',stage=0,binding=m.binding,artifact_root=m.artifacts,image_policy=SURFACE_PROFILE)
            self.assertEqual(2,archived['sequence'])

    def test_transparent_or_changed_after_ui_is_not_published_and_original_capture_is_retired(self):
        m=self.model
        def edit(packet):
            packet.update(graphicsObservationVersion=2,composition=composition())
            if packet['sourceSequence']>=2:packet['composition']['screen']['alpha']=.9
        m.ui.edit=edit
        with m.lock.held():
            owner=m.samples()
            with self.assertRaises(NativeUIError):owner.read(TICKET,20000)
            self.assertEqual('reading',owner.state['phase']);self.assertEqual([],owner.state['images'])
            self.assertIsNone(m.owner_store('primary').read());self.assertEqual([],list(m.native_root.iterdir()))
            with self.assertRaises(NativeUIError):m.samples()

    def test_rejected_world_code_retires_before_an_independent_fresh_actor_or_primary_capture(self):
        m=self.model;m.activate('e'*32);m.stale=True
        with m.lock.held():
            owner=m.samples()
            with self.assertRaises(GraphicsMarkerPending):owner.read(m.active,20000)
            owner.retire_marker_not_ready();m.stale=False
            actual=m.samples().read(m.active,20000);self.assertTrue(actual['state']['dialog'])
            actor=m.samples('actor');actor.read(m.active,20000)
            self.assertTrue(all(row['role']=='actor' for row in actor.state['images']))
            self.assertEqual(3,len(m.gpu.commands));self.assertEqual([],list(m.native_root.iterdir()))


if __name__=='__main__':unittest.main()
