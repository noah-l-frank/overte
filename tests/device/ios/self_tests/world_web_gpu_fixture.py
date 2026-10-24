"""Explicit host forward-renderer/GPU model paints the actual live DOM/scene.

No native GPU, UIKit, WebKit or device is exercised. Pixels come from the current
modeled scene, consumed controlled HTML and the original page's real marker src;
no requested scenario state, expected image or prior PNG is used for rendering.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import math
import re
from PIL import Image,ImageDraw,ImageFont
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from feature_journeys.fixtures import marker_bytes
from ios.adapters.world_web_sample import WorldWebSample
from self_tests.test_native_vulkan_world_frame import World

EXTENT=(1024,728)


def view(sdk):
    current=sdk.domain.world_template['source']['view'];f=1/math.tan(math.radians(current['fieldOfViewDegrees'])/2);aspect=current['aspectRatio'];near=.1;far=100.
    return {key:deepcopy(current[key]) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')}|dict(nearClip=near,farClip=far,
        projection=[f/aspect,0,0,0,0,f,0,0,0,0,-(far+near)/(far-near),-2*far*near/(far-near),0,0,-1,0])


def screen_box(position,dimensions,sdk):
    camera=view(sdk);assert camera['rotation']==[0,0,0,1];distance=camera['position'][2]-position[2];assert distance>0
    fy=EXTENT[1]/(2*math.tan(math.radians(camera['fieldOfViewDegrees'])/2));fx=EXTENT[0]/(2*math.tan(math.radians(camera['fieldOfViewDegrees'])/2)*camera['aspectRatio'])
    cx=EXTENT[0]/2+(position[0]-camera['position'][0])*fx/distance;cy=EXTENT[1]/2-(position[1]-camera['position'][1])*fy/distance
    return [cx-dimensions[0]*fx/distance/2,cy-dimensions[1]*fy/distance/2,cx+dimensions[0]*fx/distance/2,cy+dimensions[1]*fy/distance/2]


def render(sdk):
    image=Image.new('RGBA',EXTENT,(47,65,91,255));draw=ImageDraw.Draw(image);draws=0
    avatar=sdk.domain.world_template['source']['avatar']
    if avatar['boundsReady']:
        bounds=avatar['bounds'];position=[a+b/2 for a,b in zip(bounds['corner'],bounds['dimensions'])]
        if view(sdk)['position'][2]>position[2]:
            box=screen_box(position,bounds['dimensions'],sdk);draw.rectangle(box,fill=(102,132,145,255));draws+=1
    if sdk.domain.running and sdk.page is not None:
        page=sdk.evaluate(dict(op='read'));document=page['document'];body=Image.new('RGBA',(850,661),(255,255,255,255));html=ImageDraw.Draw(body);font=ImageFont.load_default(size=18)
        # The actual fixture emits matching visible heading and title bytes.
        heading=re.search(r'<h1[^>]*>([^<]*)</h1>',sdk.page_source.body.decode());assert heading
        html.text((8,8),heading.group(1),fill='black',font=font)
        fields={row['id']:row for row in document['elements']};nodes={row['id']:row for row in page['nodes']}
        for key,field in fields.items():
            if key=='feature-marker' or not field['visible']:continue
            box=field['rect'];html.rectangle(box,outline=(48,48,48,255),width=1)
            text=nodes[key]['value'] or nodes[key]['textContent']
            html.text((box[0]+4,box[1]+8),text,fill=(16,16,16,255),font=font)
        marker=nodes['feature-marker'];matched=re.fullmatch(r'/feature-fixture/v1/runs/([a-f0-9]{32})/tickets/([a-f0-9]{32})/marker.png',marker['src']);assert matched and matched[1]==sdk.run
        x0,y0,x1,y1=fields['feature-marker']['rect'];card=Image.open(BytesIO(marker_bytes(matched[1],matched[2]))).convert('RGBA')
        body.paste(card.resize((round(x1-x0),round(y1-y0)),Image.Resampling.NEAREST),(round(x0),round(y0)))
        box=screen_box(sdk.domain.marker['position'],sdk.domain.marker['dimensions'],sdk);bounds=[round(value) for value in box]
        image.paste(body.resize((bounds[2]-bounds[0],bounds[3]-bounds[1]),Image.Resampling.NEAREST),tuple(bounds[:2]));draws+=1
    # A clear/sky pass is an actual draw in this explicit host renderer model.
    output=BytesIO();image.save(output,format='PNG');return output.getvalue(),image.tobytes(),draws+1


class Slot(World):
    @property
    def clock(self):return self._local if self.sdk is None else self.sdk.time
    @clock.setter
    def clock(self,value):
        if self.sdk is None:self._local=value
        else:self.sdk.time=value
    def __init__(self,sdk,pool):
        self.sdk=None;super().__init__();self.sdk,self.pool=sdk,pool;self.offset=sdk.base_epoch;self.sequence=pool.sequence;self.frame_index=pool.frame
        self.source_extent=[512,364];self.target_extent=list(EXTENT);self.fault=self.fix
    def fix(self,packet):
        packet['processId']=self.sdk.pid;self.pool.sequence=max(self.pool.sequence,self.sequence)
        if packet.get('source',{}).get('gpuBufferBytes',0):packet['source']['gpuBufferBytes']=EXTENT[0]*EXTENT[1]*4
        if 'image' in packet.get('source',{}):
            packet['source']['image'].update(width=EXTENT[0],height=EXTENT[1]);trace=packet['source']['renderTrace']
            trace.update(recordedView=view(self.sdk),frameId=format(self.frame_index,'032x'))
    def send(self,query):
        self.sequence=self.pool.sequence
        if query['operation']=='read':self.png,self.raw_pixels,self.actual_draws=render(self.sdk)
        super().send(query);self.pool.sequence=self.sequence


class Pool:
    def __init__(self,sdk):self.sdk=sdk;self.slots={};self.last=None;self.sequence=0;self.frame=0
    def send(self,query):
        request=query['requestId']
        if request not in self.slots:self.frame+=1;self.slots[request]=Slot(self.sdk,self)
        self.last=self.slots[request];self.last.send(query)
    def original(self):
        value=self.last.original();self.sequence=max(self.sequence,self.last.sequence);return value
    def reader(self,intent,receipt):
        return NativeVulkanWorldFrame(self.send,self.original,self.sdk.tick,lambda:True,self.sdk.pid,intent,receipt=receipt,monotonic=lambda:self.sdk.time,sleep=self.sdk.sleep)


def sample(whole,request):
    if not hasattr(whole,'gpu'):whole.gpu=Pool(whole.sdk)
    scope,sdk,source=whole.scope,whole.sdk,whole.source
    def reader(intent,receipt):
        return NativeVulkanWorldFrame(whole.gpu.send,whole.gpu.original,lambda:source.native.read(source.native.sequence)['capturedEpochMs'],
            lambda:True,sdk.pid,intent,receipt=receipt,monotonic=lambda:sdk.time,sleep=sdk.sleep)
    owner=VulkanWorldFrameOwner(PrivateFeatureState(scope.root/('graphics-world-frame-primary-0-'+request[4:]+'.json')),
        scope.root,sdk.binding,sdk.run,'primary',0,request,reader,lambda:True,source_lock=scope.lock,monotonic=lambda:sdk.time,sleep=sdk.sleep)
    return WorldWebSample(PrivateFeatureState(scope.root/('ios-world-web-primary-'+request[4:]+'-sample.json')),source,owner,lambda:True)
