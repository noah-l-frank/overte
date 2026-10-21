"""Original world-target joins with synthetic native/Qt/GPU boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import unittest
import uuid
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import image_observation
from ios.adapters.graphics_world_measurements import compose,originals
from ios.self_tests.test_ios_graphics_measurements import original_bundle,HOST,NATIVE,RUN,TICKET,URL,BINDING
from self_tests.test_token_graphics_ui import GraphicsBoundary


def rebind(value):
    sources=originals(value);value['clockJoin']['originalsSha256']=digest(sources)
    value['clockJoin']['sourceTimes']=[dict(source=name,field=key,epochMs=packet[key]) for name,packet in sources.items()
        for key in ('capturedEpochMs','sampleEpochMs') if key in packet]


def world_bundle(*,dialog=False,**options):
    # These are fresh synthetic SDK originals. There is no production envelope
    # conversion or reuse of a captured image with a new acquisition timestamp.
    sample,raw,policy,instance=original_bundle(**options)
    image=Image.open(BytesIO(raw)).convert('RGBA');pixels=image.tobytes();stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
    metadata=sample['frameBefore'];source=deepcopy(metadata['source']);captured=metadata['capturedEpochMs']+2
    source.update(pixelFormat='rgba8-top-left',pixelsReadEpochMs=captured,
                  image=dict(bytes=len(raw),width=image.width,height=image.height,
                             sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(pixels).hexdigest()))
    capture=dict(vulkanWorldFrameVersion=1,commandId=metadata['commandId'],requestId=metadata['requestId'],instance=metadata['instance'],
        sequence=metadata['sequence'],processId=metadata['processId'],requestedEpochMs=metadata['requestedEpochMs'],capturedEpochMs=captured,source=source)
    old=sample['retirementBefore']
    retirement=dict(vulkanWorldStorageVersion=1,commandId=old['commandId'],requestId=old['requestId'],operation=old['operation'],
        instance=old['instance'],sequence=old['sequence'],processId=old['processId'],requestedEpochMs=old['requestedEpochMs'],capturedEpochMs=old['capturedEpochMs'],
        source=deepcopy(old['source'])|dict(pngBytes=0,gpuBufferBytes=0))
    if dialog:
        model=GraphicsBoundary(generic=True);model.resolution=.5;model.haze=options.get('haze',False);model.mirrors=options.get('mirror',False)
        rows=[]
        for row in model.capture()['controls']:
            row=deepcopy(row);row['token']=str(uuid.UUID(hex=row['token']));row['focused']=False
            row['frame']=None if row['viewport'] in ('above','below') else dict(x=0,y=0,width=640,height=400)
            rows.append(row)
        for key in ('graphics','tablet'):
            original=sample[key]['originalReceipt']['observation'];original.update(controls=deepcopy(rows),tabletShown=True)
            original['scriptInventory']['tabletShown']=True
        sample['graphics']['controls']=[{k:deepcopy(v) for k,v in row.items() if k!='frame'} for row in rows]
        sample['tablet']['scriptInventory']['tabletShown']=True
    result={key:sample[key] for key in ('nativeBefore','subjectBefore','graphics','tablet','subjectAfter','nativeAfter','provider','clockJoin')}
    result.update(capture=capture,retirement=retirement);policy=policy|dict(source='world-render-target');rebind(result)
    return result,raw,policy,instance


class WorldMeasurements(unittest.TestCase):
    def measure(self,sample):
        frame,raw,policy,instance=sample
        return compose(RUN,frame['provider']['ticket'],URL,BINDING,frame,raw,policy,provider_instance=instance,
                       after_epoch=frame['clockJoin']['hostBeforeEpochMs'])

    def test_pre_hud_original_pixels_remain_valid_with_actual_fullscreen_graphics_dialog(self):
        sample=world_bundle(dialog=True);before=deepcopy(sample[0]);actual=self.measure(sample)
        self.assertTrue(actual['state']['dialog']);self.assertEqual(['panel:graphics'],actual['resources'])
        self.assertEqual(.5,actual['state']['renderScale']);self.assertEqual(HOST,actual['capturedEpochMs'])
        self.assertEqual(NATIVE+10,actual['nativeEpochMs']);self.assertEqual(before,sample[0])
        self.assertTrue(sample[0]['tablet']['scriptInventory']['tabletShown'])
        self.assertEqual(640,next(row for row in sample[0]['graphics']['originalReceipt']['observation']['controls']
                                  if row['id']=='graphics.page')['frame']['width'])

    def test_allocation_ratio_is_observed_independently_of_requested_setting(self):
        sample=world_bundle();sample[0]['capture']['source']['sourceExtent']=[416,260];rebind(sample[0])
        actual=self.measure(sample);self.assertEqual(.5,actual['state']['resolution']);self.assertEqual(.65,actual['state']['renderScale'])

    def test_ack_only_retirement_held_copy_or_wrong_target_cannot_prove_pixels(self):
        faults=[lambda v:v['retirement']['source'].update(gpuBufferBytes=4096),lambda v:v['retirement']['source'].update(callbacks=1),
            lambda v:v['retirement']['source'].update(pngBytes=100),lambda v:v['capture']['source'].update(backend='opengl'),
            lambda v:v['capture']['source']['image'].update(pixelSha256='0'*64),lambda v:v['capture'].update(processId=43),
            lambda v:v['capture']['source']['renderTrace'].update(drawSource='cpu-opcodes'),
            lambda v:v['capture']['source'].update(fenceObservedEpochMs=v['capture']['capturedEpochMs']+1)]
        for fault in faults:
            sample=world_bundle();fault(sample[0]);rebind(sample[0])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure(sample)

    def test_stale_pixels_or_foreign_geometry_fail_even_when_capture_metadata_hash_matches(self):
        for fault in ('pixels','scene','clock','marker-region'):
            sample=world_bundle();frame,raw,policy,instance=sample
            if fault=='pixels':
                image=Image.open(BytesIO(raw));image.paste((128,128,128,255),(0,0,image.width,image.height))
                stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
                frame['capture']['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
            elif fault=='scene':frame['subjectAfter']['source']['sceneUrl']='http://foreign.invalid/world.json'
            elif fault=='clock':frame['capture']['requestedEpochMs']-=10000
            else:policy=policy|dict(marker=[0,0,256,64])
            rebind(frame)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,AssertionError)):self.measure((frame,raw,policy,instance))


if __name__=='__main__':unittest.main()
