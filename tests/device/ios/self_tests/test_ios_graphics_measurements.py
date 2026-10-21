"""Independent original frame interval/pixel joins at synthetic native seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.native_completed_frame import validate as validate_frame
from feature_journeys.fixtures import challenge
from feature_journeys.graphics_fixture import scene,subject_ids
from feature_journeys.graphics_resources import GraphicsResources
from ios.adapters.graphics_images import capture_record
from ios.adapters.graphics_measurements import compose,originals
from ios.adapters.graphics_source import LINKS
from ios.self_tests.test_ios_graphics_source import Boundary as QtSource
from self_tests.test_native_completed_frame import view
from self_tests.test_native_feature_observation import Boundary as NativeSource
from self_tests.test_script_ui_inventory import inventory
from self_tests.test_completed_frame_lease import BINDING,RUN

NATIVE=1700000000000+86400000
HOST=NATIVE-86400000
TICKET='e'*32
URL='http://controlled.test:49121/feature-fixture/v1/runs/'+RUN+'/'


def native(sequence,offset):
    b=NativeSource();b.sequence=sequence-1;b.send(dict(commandId='ios-'+format(sequence,'032x')))
    def clocks(value):
        if type(value) is dict:
            return {key:(NATIVE+offset if key.endswith('EpochMs') else clocks(item)) for key,item in value.items()}
        if type(value) is list:return [clocks(item) for item in value]
        return value
    result=clocks(b.sample);result['processId']=42
    result['graphics'].update(requestedResolutionScale=.5,applicationResolutionScale=.5)
    return result


def subject(sequence,offset):
    document=scene(RUN,TICKET,URL);rows=[]
    for item in document['Entities']:
        haze=item.get('haze',{})
        rows.append(dict(id=item['id'].strip('{}'),name=item['name'],type=item['type'],hostType='local',
            position=[item['position'][axis] for axis in 'xyz'],rotation=[item['rotation'][axis] for axis in 'xyzw'],
            dimensions=[item['dimensions'][axis] for axis in 'xyz'],color=[item.get('color',dict(red=0,green=0,blue=0))[a] for a in ('red','green','blue')],
            visible=True,mirrorMode=item.get('mirrorMode','none'),hazeMode=2 if item['type']=='Zone' else 0,
            sourceUrl=item.get('sourceUrl',''),lastEditedEpochUs=20000000,
            haze=dict(range=haze.get('hazeRange',1000),color=[haze.get('hazeColor',dict(red=128,green=154,blue=179))[a] for a in ('red','green','blue')],
                      altitudeEffect=haze.get('hazeAltitudeEffect',False),glare=haze.get('hazeEnableGlare',False),backgroundBlend=haze.get('hazeBackgroundBlend',0))))
    return dict(schemaVersion=1,requestId='ios-'+format(sequence+100,'032x'),runId=RUN,instance='a'*32,sequence=sequence,
        processId=42,requestedEpochMs=NATIVE+offset,capturedEpochMs=NATIVE+offset,
        source=dict(subjectVersion=2,sceneUrl=URL+'tickets/'+TICKET+'/graphics-scene.v1.json',
            avatarPose=dict(feetPosition=[0,0,0],orientation=[0,0,0,1],modelScale=1),
            view=dict(position=[0,1.6,0],rotation=[0,0,0,1],mode='first person',fieldOfViewDegrees=60,aspectRatio=1.6,perspective=True),
            entities=rows,absentIds=[],scan=dict(center=[0,0,0],radiusMeters=128,propertyScope='graphics-spatial-v1',scannedEntities=7,unowned=[])))


def frame(sequence,offset):
    trace=dict(completedDrawTraceVersion=1,frameId=format(sequence+200,'032x'),recordedEpochMs=NATIVE+offset+1,
        begunEpochMs=NATIVE+offset+2,completedEpochMs=NATIVE+offset+4,drawSource='vulkan-api-issued',renderer='forward',view='main-mono',
        recordedView=view(),forwardBatches=1,forwardDrawCalls=5,hazeBatches=0,hazeDrawCalls=0,mirrorBatches=0,mirrorDrawCalls=0)
    return dict(completedFrameVersion=1,commandId='ios-'+format(sequence+300,'032x'),requestId='ios-'+format(sequence+400,'032x'),
        instance='b'*32,sequence=sequence,processId=42,requestedEpochMs=NATIVE+offset,capturedEpochMs=NATIVE+offset+50,
        source=dict(backend='vulkan',stage='tone-map-before-hud',view='main-mono',sourceExtent=[320,200],targetExtent=[640,400],
                    renderTrace=trace,frameIndex=sequence,submittedEpochMs=NATIVE+offset+5,fenceObservedEpochMs=NATIVE+offset+50))


def geometry(number,offset):
    return dict(schemaVersion=1,commandId='ios-'+format(number+500,'032x'),observation=dict(schemaVersion=1,sampleEpochMs=NATIVE+offset,
        sampleSequence=number,nativeUi=dict(valid=True,surfaceWidth=640,surfaceHeight=400,safeInsetLeft=0,safeInsetTop=0,safeInsetRight=0,
            safeInsetBottom=0,imeInsetBottom=0,keyboardVisible=False,density=1),window=dict(width=640,height=400)))


def provider_source():
    provider=GraphicsResources(URL.rsplit('/runs/',1)[0],clock_ms=lambda:HOST-100);provider.provision(RUN);provider.activate(RUN,TICKET)
    with provider.response(RUN,TICKET,request_authority='controlled.test:49121',request_scheme='http') as response:
        status,body,response_id,written=response
        written(dict(status=status,bytes=len(body),responseId=response_id,sha256=hashlib.sha256(body).hexdigest()))
    return provider


def original_bundle(*,ticket=TICKET,start=0,haze=False,mirror=False,provider=None):
    cursor=(start//1000)*10
    b=QtSource();b.source_sequence=cursor;raw=b.observed();raw.update(controls=[],sampleEpochMs=NATIVE+start+40,elapsedMs=start+100)
    raw['scriptInventory']=inventory(tabletShown=False)
    graphics=dict(schemaVersion=1,commandId='ios-'+'1'*32,action='observe',**{k:deepcopy(raw[v]) for k,v in LINKS.items()},
                  controls=[],originalKind='ios-normal-graphics-ui-v1',originalReceipt=dict(schemaVersion=1,commandId='ios-'+'1'*32,observation=deepcopy(raw)))
    raw['sampleEpochMs']=NATIVE+start+50
    tablet=dict(schemaVersion=1,commandId='ios-'+'2'*32,action='observe',instance=raw['instance'],generation=raw['instance'],
        sourceSequence=raw['scriptSourceSequence'],lastCommandSequence=raw['lastSequence'],elapsedMs=raw['elapsedMs'],
        capturedEpochMs=raw['sampleEpochMs'],processId=42,fileControlsVersion=1,ready=True,controls=[],scriptInventory=raw['scriptInventory'],
        originalKind='ios-normal-ui-v1',originalReceipt=dict(schemaVersion=1,commandId='ios-'+'2'*32,observation=deepcopy(raw)))
    one,two=frame(cursor+1,start+80),frame(cursor+3,start+300)
    for capture in (one,two):
        trace=capture['source']['renderTrace']
        trace.update(hazeBatches=1 if haze else 0,hazeDrawCalls=5 if haze else 0,
                     mirrorBatches=1 if mirror else 0,mirrorDrawCalls=2 if mirror else 0)
    def drained(capture,offset):
        return dict(frameStorageVersion=1,commandId='ios-'+format(offset+600,'032x'),requestId=capture['requestId'],operation='inspect',
                    instance=capture['instance'],sequence=capture['sequence']+1,processId=42,requestedEpochMs=NATIVE+offset,capturedEpochMs=NATIVE+offset,
                    source=dict(retired=True,present=False,callbacks=0,gpuPending=False,metadataBytes=0))
    policy=dict(source='native-screen',marker=[187,70,443,134],subject=[0,170,640,400])
    image=Image.new('RGB',(640,400),(95,95,95));draw=ImageDraw.Draw(image)
    for y in range(170,400,10):
        for x in range(0,640,10):draw.rectangle((x,y,x+9,y+9),fill=(20,40,80) if (x//10+y//10)%2 else (180,200,220))
    bits=''.join(f'{byte:08b}' for byte in challenge(RUN,ticket))
    for index,bit in enumerate(bits):
        x=187+(index%32)*8;y=70+(index//32)*16
        draw.rectangle((x,y,x+7,y+15),fill='white' if bit=='1' else 'black')
    stream=BytesIO();image.save(stream,format='PNG');raw_png=stream.getvalue()
    screen=dict(screenCaptureVersion=1,requestId='ios-'+format(3000+cursor,'032x'),source='native-screen',transport='webdriveragent-original-png',
        sessionId=BINDING['sessionId'],processId=42,nativeBeforeMs=NATIVE+start+200,nativeAfterMs=NATIVE+start+250,
        hostBeginEpochMs=HOST+start+200,hostEndEpochMs=HOST+start+250,hostBeginMonotonic=start/1000+.2,hostEndMonotonic=start/1000+.25,
        bytes=len(raw_png),sha256=hashlib.sha256(raw_png).hexdigest(),extent=[640,400])
    provider=provider_source() if provider is None else provider
    if ticket!=TICKET:
        provider.clock_ms=lambda:HOST+start-100;provider.activate(RUN,ticket)
    provider.clock_ms=lambda:HOST+start+550
    value=dict(nativeBefore=native(cursor+2,start+10),subjectBefore=subject(cursor+1,start+20),graphics=graphics,tablet=tablet,
        geometryBefore=geometry(cursor+1,start+60),frameBefore=one,retirementBefore=drained(one,start+150),screen=screen,
        frameAfter=two,retirementAfter=drained(two,start+370),geometryAfter=geometry(cursor+2,start+400),
        subjectAfter=subject(cursor+2,start+450),nativeAfter=native(cursor+3,start+500),provider=provider.snapshot(RUN,format(cursor+4000,'032x')))
    for key in ('nativeBefore','nativeAfter'):value[key]['graphics'].update(hazeSetting=haze,mirrorsSetting=mirror)
    value['clockJoin']=dict(clockJoinVersion=1,hostBeforeEpochMs=HOST+start,hostAfterEpochMs=HOST+start+600,
        hostBeforeMonotonic=start/1000,hostAfterMonotonic=start/1000+.6,
        nativeBefore=native(cursor+1,start),nativeAfter=native(cursor+4,start+600),sourceTimes=[],originalsSha256='')
    rebind(value);return value,raw_png,policy,provider.instance


def rebind(value):
    sources=originals(value)
    value['clockJoin']['sourceTimes']=[dict(source=name,field=key,epochMs=packet[key]) for name,packet in sources.items()
        for key in ('capturedEpochMs','sampleEpochMs') if key in packet]
    value['clockJoin']['originalsSha256']=digest(sources)


class MeasurementTests(unittest.TestCase):
    def measure(self,value,raw,policy,instance):
        return compose(RUN,TICKET,URL,BINDING,value,raw,policy,provider_instance=instance,after_epoch=HOST)

    def test_native_frame_interval_original_screen_and_host_native_clocks_are_distinct(self):
        value,raw,policy,instance=original_bundle();original=deepcopy(value)
        actual=self.measure(value,raw,policy,instance)
        self.assertEqual(.5,actual['state']['renderScale']);self.assertEqual(.5,actual['state']['resolution'])
        self.assertEqual(HOST,actual['capturedEpochMs']);self.assertEqual(NATIVE+10,actual['nativeEpochMs'])
        self.assertEqual([0,0,640,400],actual['screenViewport']);self.assertEqual(original,value)
        self.assertEqual(2,len(set(actual['frameInterval'])));self.assertFalse(actual['state']['mirrorPass'])

    def test_ack_settings_cpu_commands_or_one_completed_frame_cannot_replace_originals(self):
        faults=[lambda v:v.pop('frameAfter'),lambda v:v.update(frameAfter=deepcopy(v['frameBefore'])),
            lambda v:v['frameAfter']['source']['renderTrace'].update(drawSource='cpu-opcodes'),
            lambda v:v['retirementBefore']['source'].update(callbacks=1),lambda v:v['retirementAfter']['source'].update(gpuPending=True),
            lambda v:v['frameAfter']['source'].update(sourceExtent=[1,1]),lambda v:v['frameAfter'].update(processId=99),
            lambda v:v['screen'].update(capturedEpochMs=NATIVE+250),lambda v:v['screen'].update(nativeBeforeMs=NATIVE-1000),
            lambda v:v['nativeAfter']['graphics'].update(hazeSetting=True)]
        for fault in faults:
            value,raw,policy,instance=original_bundle();fault(value)
            if 'frameAfter' in value:rebind(value)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.measure(value,raw,policy,instance)

    def test_stale_foreign_or_blank_actual_pixels_fail_even_with_valid_native_frames(self):
        for fault in ('stale','blank','outside'):
            value,raw,policy,instance=original_bundle()
            if fault=='stale':
                _foreign,raw,_policy,_instance=original_bundle(ticket='0'*32)
                value['screen'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());rebind(value)
            elif fault=='blank':
                image=Image.open(BytesIO(raw));draw=ImageDraw.Draw(image);draw.rectangle(policy['subject'],fill='gray')
                stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
                value['screen'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());rebind(value)
            elif fault=='outside':policy['marker']=[0,0,256,64]
            with self.subTest(fault=fault),self.assertRaises((AssertionError,NativeUIError,ValueError)):self.measure(value,raw,policy,instance)

    def test_rotation_density_camera_source_or_unowned_geometry_change_is_rejected(self):
        faults=[lambda v:v['geometryAfter']['observation']['nativeUi'].update(density=2),
            lambda v:v['frameAfter']['source']['renderTrace']['recordedView'].update(position=[1,1.6,0]),
            lambda v:v['subjectAfter']['source']['view'].update(position=[1,1.6,0]),
            lambda v:v['subjectAfter']['source']['entities'][0].update(visible=False),
            lambda v:v['geometryAfter']['observation']['nativeUi'].update(keyboardVisible=True),
            lambda v:v['subjectAfter'].update(instance='e'*32)]
        for fault in faults:
            value,raw,policy,instance=original_bundle();fault(value);rebind(value)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.measure(value,raw,policy,instance)


if __name__=='__main__':unittest.main()
