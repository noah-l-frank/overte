"""Common v17 Emote composition over synthetic target IO and real owner code.

The toy native timer and renderer supply actual model state, not scenario
assertions. This checks adapter/test composition only, never Android behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import io
import os
import unittest
from unittest.mock import patch

from PIL import Image,ImageChops
import test_emote_feature
import test_emote_registration
import test_emote_role
import test_feature_adapters as bound
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import Journal
from overte_phone_emote_actor import PhoneEmoteActor
from overte_phone_emote_retirement import PhoneEmoteRetirement
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class JourneyModel(test_emote_role.Model):
    def __init__(self,root):
        super().__init__(root);self.sit_index=0;paint=self.pixel.paint
        def render(*args,**kwargs):
            raw=paint(*args,**kwargs)
            if self.actual_name!='Crying':return raw
            with Image.open(io.BytesIO(raw)) as image:
                image.load();body=tuple(POLICY['subject'])
                image.paste(ImageChops.invert(image.crop(body).convert('RGB')),body)
                output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()
        self.pixel.paint=render

    def start(self,name):
        if name=='Sit2':
            name=('Sit1','Sit2','Sit3')[self.sit_index%3];self.sit_index+=1
        super().start(name)

    def native_send(self,request):
        # Autonomous native-clock timer derived from the actual selected call.
        # Sit deliberately holds its final pose, matching the ordinary profile.
        if self.actual_name and not self.actual_name.startswith('Sit'):
            call=self.events[-1]['request']
            due=self.started_at+1000*(call['lastFrame']-call['firstFrame'])/call['framesPerSecond']
            if self.epoch+100>=due:self.restore()
        super().native_send(request)


class EmoteFeatureJourneyTests(unittest.TestCase):
    owner=test_emote_feature.EmoteFeatureTests.owner
    feature=test_emote_feature.EmoteFeatureTests.feature
    observation=test_emote_feature.EmoteFeatureTests.observation
    publication_server=test_emote_feature.EmoteFeatureTests.publication_server
    actor_run=test_emote_feature.EmoteFeatureTests.actor_run
    resource_boundary=test_emote_feature.EmoteFeatureTests.resource_boundary
    configuration=test_emote_registration.EmoteRegistrationTests.configuration
    adapter=test_emote_registration.EmoteRegistrationTests.adapter

    def setUp(self):
        with patch.object(test_emote_role,'Model',JourneyModel):test_emote_feature.EmoteFeatureTests.setUp(self)
        self.model.journal=Journal(lambda:self.model.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.model.journal.register('emotes')

    def test_complete_common_journey_uses_normal_inputs_original_files_and_independent_actor(self):
        m=self.model;server,reader,client=self.publication_server();actor=PhoneEmoteActor(self.actor_run(client),POLICY)
        registered=self.adapter();reports=[]
        def invoke(operation,call):
            value=registered.adapter.invoke(bound.SELECTOR,operation,call)
            if operation.endswith(('.observe','.cleanup')):self.assertFalse(actor.step())
            return value
        journey=Journey('emotes',RUN,m.client.url+'/runs/'+RUN+'/',invoke=invoke,
            witness=lambda:reader.request('/runs/'+RUN),activate=lambda ticket,verb='baseline',inputs=None:m.journal.activate(RUN,ticket,verb,inputs),
            read_artifact=lambda name:(m.root/name).read_bytes(),image_policy=dict(screen=POLICY),continuity=lambda *_args:None,
            monotonic=lambda:m.clock,epoch_ms=lambda:m.epoch,sleep=m.sleep,report=reports.append)
        with patch.dict(os.environ,self.configuration()),patch.object(registered.adapter,'_emote_feature',side_effect=lambda *_args,**_kwargs:self.feature()):
            journey.execute()
        self.assertTrue(reports[0]['sequenceCompleted']);self.assertFalse(reports[0]['deviceAcceptance'])
        self.assertEqual({'Sit1','Sit2','Sit3'},journey.sit_variants)
        self.assertGreaterEqual(len(journey.phases),len(SCENARIOS['emotes']['steps'])+2)
        reader.request('/runs/'+RUN,method='DELETE');self.assertTrue(actor.step())
        def resources(owner):return self.resource_boundary(owner)
        with patch.object(PhoneEmoteRetirement,'retire_resources',resources):
            self.assertEqual({'performed':True},self.feature().finalize())
        self.assertEqual([],list(m.root.glob('phone-emote-*.json')));self.assertEqual(0,server.internal_errors)

    def test_target_produced_sit_variants_and_idle_stops_use_actual_source_provenance(self):
        m=self.model;m.journal.activate(RUN,'a'*32,'baseline',{});feature=self.feature()
        value=feature.observe(self.observation());seen=set()
        feature.act(m.call('cancel'));value=feature.observe(self.observation(value['sequence']))
        self.assertFalse(value['state']['restoredBeforeNominalEnd']);self.assertEqual([],value['artifacts'])
        for _ in range(3):
            feature=self.feature();feature.act(m.call('sit'))
            value=feature.observe(self.observation(value['sequence']));seen.add(value['state']['sit'])
            self.assertEqual('Sit',value['state']['animation']);self.assertTrue(value['state']['override'])
            self.assertEqual(['image','file'],[row['kind'] for row in value['artifacts']])
            feature.act(m.call('cancel'));value=feature.observe(self.observation(value['sequence']))
            self.assertEqual('idle',value['state']['animation']);self.assertFalse(value['state']['override'])
        self.assertEqual({'Sit1','Sit2','Sit3'},seen)


if __name__=='__main__':unittest.main()
