"""Original owners/common verifier; image, Web, Java and VR boundaries are simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
import unittest
import uuid
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.scenarios import VERSION
from feature_journeys.stereo_browser_evidence import PROFILE,observation
from self_tests.test_pico_browser_stereo import Model,URL,SCENE,RUN,TICKET
from self_tests.test_stereo_navigation_evidence import POLICY as NAVIGATION_POLICY
from self_tests.test_stereo_graphics_evidence import JourneyPixels

POLICY=dict(deepcopy(NAVIGATION_POLICY),profile=PROFILE)
NEXT='9'*32
ERRORS=(AssertionError,ValueError,RuntimeError)


class Source(Model):
    def __init__(self):
        super().__init__();self.fault='';self.sample_sequence=0
        original=self.gpu.send
        def send(command):
            with Image.open(io.BytesIO(self.gpu.raw)) as old:
                image=old.copy()
                if self.fault=='stale-right':
                    with Image.open(io.BytesIO(JourneyPixels(card_ticket=TICKET).raw)) as stale:
                        image.paste(stale.crop((800,0,1600,800)),(800,0))
                elif self.fault=='duplicated-eye':image.paste(image.crop((0,0,800,800)),(800,0))
                elif self.fault=='blank-left':image.paste((100,100,100,255),tuple(POLICY['eyes']['left']['subject']))
                output=io.BytesIO();image.save(output,format='PNG');self.gpu.raw=output.getvalue()
                self.gpu.pixels=hashlib.sha256(image.tobytes()).hexdigest();self.storage.raw=self.gpu.raw
            return original(command)
        self.gpu.send=send
    def acquire(self,ticket=TICKET,*,role='primary'):
        self.active=ticket;self.sample_sequence+=1;owner=self.browser_stereo(role=role,journal=uuid.uuid4().hex)
        state=owner.acquire(ticket);frame=state['frame']
        from adapters.pico4.browser_stereo_source import validate
        facts=validate(frame,owner.image_bytes(),RUN,self.binding,SCENE)
        sample=dict(schemaVersion=1,contractVersion=VERSION,runId=RUN,sequence=self.sample_sequence,
            capturedEpochMs=facts['earliestEpochMs'],state=facts['state'],resources=['panel:tablet-web'],
            lifecycle=frame['nativeBefore']['lifecycle'],artifacts=owner.artifacts(self.sample_sequence))
        return owner.image_bytes(),owner.store.path.read_bytes(),sample


class BrowserStereoEvidenceTests(unittest.TestCase):
    def source(self):
        value=Source();self.addCleanup(value.close);return value
    def verify(self,raw,metadata,sample,ticket=TICKET,**kw):return observation(raw,metadata,RUN,ticket,URL,POLICY,sample,**kw)
    def test_actual_original_document_and_both_eye_challenges_join_complete_retirement(self):
        source=self.source();raw,metadata,sample=source.acquire();evidence,subject=self.verify(raw,metadata,sample)
        self.assertEqual({'left','right'},set(evidence['eyes']));self.assertEqual('',subject['state']['text'])
        self.assertEqual('primary',subject['role']);self.assertEqual(2,subject['cursors']['browserAfter'])
        self.assertEqual([],list(source.native_root.iterdir()))
        raw,metadata,sample=source.acquire(role='actor');self.verify(raw,metadata,sample,role='actor')
        with self.assertRaises(ERRORS):self.verify(raw,metadata,sample)
    def test_wrong_eye_challenge_duplicated_mono_and_uniform_subject_fail_independently(self):
        for fault in ('stale-right','duplicated-eye','blank-left'):
            with self.subTest(fault=fault):
                source=self.source();source.fault=fault;raw,metadata,sample=source.acquire(NEXT)
                with self.assertRaises(ERRORS):self.verify(raw,metadata,sample,NEXT)
    def test_sample_effect_cannot_be_substituted_and_original_retirement_cannot_be_dropped(self):
        source=self.source();raw,metadata,sample=source.acquire()
        wrong=deepcopy(sample);wrong['state']['documentLoads']+=1
        with self.assertRaises(ERRORS):self.verify(raw,metadata,wrong)
        body=json.loads(metadata);state=unpack(body['payload'])[0];state['proof']['memory']['present']=True
        body['payload']=pack([state])
        with self.assertRaises(ERRORS):self.verify(raw,json.dumps(body).encode(),sample)
    def test_actual_eye_bounds_and_browser_profile_are_required(self):
        source=self.source();raw,metadata,sample=source.acquire()
        for key in ('eye','profile'):
            wrong=deepcopy(POLICY)
            if key=='eye':wrong['eyes']['left']['marker']=[1000,256,1256,320]
            else:wrong['profile']=NAVIGATION_POLICY['profile']
            with self.subTest(key=key),self.assertRaises(ERRORS):observation(raw,metadata,RUN,TICKET,URL,wrong,sample)
    def test_existing_journey_selects_browser_stereo_and_refuses_original_frame_reuse(self):
        source=self.source();raw,metadata,sample=source.acquire()
        journey=Journey('tablet-web',RUN,URL,invoke=lambda *_:None,witness=lambda *_:None,activate=lambda *_:None,
            read_artifact=lambda name:read_private_artifact(source.artifacts,name),image_policy=dict(screen=POLICY),
            continuity=lambda *_:None,monotonic=lambda:0.,epoch_ms=lambda:20000,sleep=lambda _:None,report=lambda _:None)
        observed,subject=journey.artifacts(sample,TICKET,['image'])
        self.assertTrue(journey.stereo_browser);self.assertEqual(1,len(observed));self.assertEqual('primary',subject['role'])
        changed=deepcopy(sample);changed['sequence']+=1
        for artifact in changed['artifacts']:artifact['sequence']=changed['sequence']
        with self.assertRaises(ERRORS):journey.artifacts(changed,TICKET,['image'])


if __name__=='__main__':unittest.main()
