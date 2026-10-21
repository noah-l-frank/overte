"""Original world-target acquisition reader; no rendered-feature verdict.

Mono version 1 and opt-in stereo versions 2/3 refuse unimplemented Vulkan readback.
The GPU/backend hook and platform original-file transport must be implemented
before this internal reader can acquire anything on a target.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
import math
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

FILE='world-render-observation.json'
IMAGE_PREFIX='world-render-image-'


def image_name(request):
    nonce=request[4:] if request.startswith('ios-') else request
    need(re.fullmatch('[0-9a-f]{32}',nonce) is not None)
    return IMAGE_PREFIX+nonce+'.png'
LIMIT=32*1024*1024
PIXELS=8388608


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def extent(value, *, stereo=False):
    return (type(value) is list and len(value)==2 and integer(value[0],1,8192 if stereo else 4096)
        and integer(value[1],1,4096) and value[0]*value[1]<=(2*PIXELS if stereo else PIXELS))


def matrix(value, *, affine=False):
    need(type(value) is list and len(value)==16 and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=1e9 for v in value))
    # Gaussian elimination rejects singular/uninitialized original transforms.
    rows=[[float(value[column*4+row]) for column in range(4)] for row in range(4)]
    for column in range(4):
        pivot=max(range(column,4),key=lambda row:abs(rows[row][column]))
        need(abs(rows[pivot][column])>1e-12)
        rows[column],rows[pivot]=rows[pivot],rows[column]
        for row in range(column+1,4):
            factor=rows[row][column]/rows[column][column]
            for index in range(column+1,4):rows[row][index]-=factor*rows[column][index]
    if affine:need(all(abs(value[index])<1e-5 for index in (3,7,11)) and abs(value[15]-1)<1e-5)
    return value


def stereo_source(source,published):
    stereo=source['stereo']
    exact(stereo,{'frameIndex','executionSequence','layout','matrixLayout','cameraView','eyes'})
    need(integer(stereo['frameIndex'],0,2**32-1) and integer(stereo['executionSequence'],1)
         and stereo['layout']=='side-by-side' and stereo['matrixLayout']=='column-major'
         and type(stereo['eyes']) is list and len(stereo['eyes'])==2)
    matrix(stereo['cameraView'],affine=True)
    viewport=source['sourceViewport'];width,height=source['targetExtent']
    need(viewport[0]%2==viewport[2]%2==width%2==0)
    for index,eye in enumerate(stereo['eyes']):
        exact(eye,{'eye','projection','viewOffset','sourceViewport','targetViewport'})
        need(eye['eye']==('left','right')[index]
             and all(type(eye[key]) is list and len(eye[key])==4 and all(integer(v,0,8192) for v in eye[key])
                     for key in ('sourceViewport','targetViewport'))
             and eye['sourceViewport']==[viewport[0]+index*(viewport[2]//2),viewport[1],viewport[2]//2,viewport[3]]
             and eye['targetViewport']==[index*(width//2),0,width//2,height])
        matrix(eye['projection']);matrix(eye['viewOffset'],affine=True)
        # A central mono projection with an identity view offset cannot become
        # two eyes by duplicating the same descriptor or changing the eye label.
        need(abs(eye['projection'][11])>1e-8 and abs(eye['projection'][15])<1e-8)
    need(stereo['eyes'][0]['viewOffset']!=stereo['eyes'][1]['viewOffset'])
    present=source['presentation']
    exact(present,{'backend','frameIndex','submissionSequence','submittedEpochMs','views'})
    need(present['backend']=='openxr' and type(present['frameIndex']) is int
         and present['frameIndex']==stereo['frameIndex'] and integer(present['submissionSequence'],1)
         and integer(present['submittedEpochMs'],source['capturedEpochMs'],published)
         and type(present['views']) is list and len(present['views'])==2)
    for index,view in enumerate(present['views']):
        exact(view,{'eye','imageRect','arrayIndex'})
        rect=view['imageRect']
        need(view['eye']==('left','right')[index] and integer(view['arrayIndex'],0,1)
             and type(rect) is list and len(rect)==4 and all(integer(v,0,8192) for v in rect)
             and 0<rect[2]<=4096 and 0<rect[3]<=4096)


def recorded_view(value):
    """Original primary recording view; projection uses explicit row-major order.

    Stereo effects must use the retained per-eye matrices, not this central
    recording frustum as a replacement for either headset eye.
    """
    exact(value,{'position','rotation','projection','fieldOfViewDegrees','aspectRatio','nearClip','farClip','perspective'})
    for field,size,limit in (('position',3,1e9),('rotation',4,1.01)):
        need(type(value[field]) is list and len(value[field])==size and all(number(v,-limit,limit) for v in value[field]))
    need(abs(sum(v*v for v in value['rotation'])-1)<.02 and value['perspective'] is True
         and number(value['fieldOfViewDegrees'],1,179) and number(value['aspectRatio'],.1,10)
         and number(value['nearClip'],.000001,1e8) and number(value['farClip'],value['nearClip']+.000001,1e9))
    matrix(value['projection'])
    need(abs(value['projection'][14])>1e-8 and abs(value['projection'][15])<1e-8)
    return value


def render_trace(source,requested):
    trace=source['renderTrace'];frame=source['stereo']
    exact(trace,{'traceVersion','frameId','frameIndex','executionSequence','recordedEpochMs','recordedView',
        'begunEpochMs','completedEpochMs','renderer','view','forwardBatches','forwardDrawCommands',
        'hazeBatches','hazeDrawCommands','mirrorBatches','mirrorDrawCommands'})
    need(type(trace['traceVersion']) is int and trace['traceVersion']==3
         and type(trace['frameId']) is str and re.fullmatch('[0-9a-f]{32}',trace['frameId'])
         and integer(trace['frameIndex'],0,2**32-1) and trace['frameIndex']==frame['frameIndex']
         and integer(trace['executionSequence'],1) and trace['executionSequence']==frame['executionSequence']
         and trace['renderer']=='forward' and trace['view']=='main-stereo')
    recorded_view(trace['recordedView'])
    pose=trace['recordedView'];x,y,z,w=pose['rotation']
    norm=math.sqrt(x*x+y*y+z*z+w*w);x,y,z,w=(v/norm for v in (x,y,z,w))
    rotation=[[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],
        [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],
        [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]]
    expected=[rotation[column][row] if column<3 and row<3 else
        -sum(rotation[index][row]*pose['position'][index] for index in range(3)) if column==3 and row<3
        else 1 if row==column else 0 for column in range(4) for row in range(4)]
    need(all(abs(actual-wanted)<=.0002*max(1,abs(wanted))
        for actual,wanted in zip(frame['cameraView'],expected)))
    need(integer(trace['recordedEpochMs'],requested,source['recordedEpochMs'])
         and integer(trace['begunEpochMs'],source['recordedEpochMs'],source['startedEpochMs'])
         and integer(trace['completedEpochMs'],trace['begunEpochMs'],source['startedEpochMs']))
    for prefix in ('forward','haze','mirror'):
        batches,draws=trace[prefix+'Batches'],trace[prefix+'DrawCommands']
        need(integer(batches,0,1000000000) and integer(draws,batches,1000000000)
             and (batches>0)==(draws>0))
    need(trace['forwardDrawCommands']>0 and trace['hazeBatches']<=trace['forwardBatches']
         and trace['hazeDrawCommands']<=trace['forwardDrawCommands'])
    return trace


def validate(value,request,pid,epoch,*,stereo=False,require_trace=False):
    need(type(stereo) is bool and type(require_trace) is bool and (not require_trace or stereo))
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance']) is not None
         and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
         and 0<=value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    fields={'captureVersion','available','acquisitionSequence','recordedEpochMs','startedEpochMs','capturedEpochMs',
        'backend','stage','view','sourceExtent','sourceViewport','targetExtent','pixelFormat','image'}
    if stereo:fields.update(('stereo','presentation'))
    traced=type(source) is dict and source.get('captureVersion')==3
    if traced:fields.add('renderTrace')
    exact(source,fields)
    need(type(source['captureVersion']) is int and source['captureVersion'] in ((2,3) if stereo else (1,))
         and (not require_trace or traced) and source['available'] is True
         and integer(source['acquisitionSequence'],1) and source['backend']=='opengl'
         and source['stage']=='tone-map-before-hud' and source['view']==('main-stereo' if stereo else 'main-mono')
         and source['pixelFormat']=='rgba8-top-left' and extent(source['sourceExtent'],stereo=stereo) and extent(source['targetExtent'],stereo=stereo))
    stamps=[value['requestedEpochMs'],source['recordedEpochMs'],source['startedEpochMs'],source['capturedEpochMs'],value['capturedEpochMs']]
    need(all(integer(v,1) for v in stamps) and stamps==sorted(stamps))
    fresh(source['capturedEpochMs'],epoch)
    viewport=source['sourceViewport']
    need(type(viewport) is list and len(viewport)==4 and all(integer(v,0,8192 if stereo else 4096) for v in viewport)
         and viewport[2]>0 and viewport[3]>0 and viewport[0]+viewport[2]<=source['sourceExtent'][0]
         and viewport[1]+viewport[3]<=source['sourceExtent'][1])
    image=source['image']
    exact(image,{'name','bytes','sha256','pixelSha256','width','height'})
    need(image['name']==image_name(request) and integer(image['bytes'],1,LIMIT) and digest(image['sha256']) and digest(image['pixelSha256'])
         and integer(image['width'],1,8192 if stereo else 4096) and integer(image['height'],1,4096)
         and [image['width'],image['height']]==source['targetExtent'])
    if stereo:stereo_source(source,value['capturedEpochMs'])
    if traced:render_trace(source,value['requestedEpochMs'])
    return value


def original_pixels(value,raw):
    from PIL import Image
    image=value['source']['image']
    need(type(raw) is bytes and 0<len(raw)<=LIMIT and len(raw)==image['bytes']
         and hashlib.sha256(raw).hexdigest()==image['sha256'])
    with Image.open(io.BytesIO(raw)) as decoded:
        need(decoded.format=='PNG' and decoded.mode=='RGBA' and decoded.size==(image['width'],image['height']))
        decoded.load()
        need(hashlib.sha256(decoded.tobytes()).hexdigest()==image['pixelSha256'])
    return raw


def measured_scale(value):
    """Ratios from actual rendered source viewport, never a preference getter."""
    source=value['source'];viewport=source['sourceViewport'];target=source['targetExtent']
    return dict(x=viewport[2]/target[0],y=viewport[3]/target[1])


class NativeWorldRenderCapture:
    def __init__(self,send,read,files,clock_ms,guard,pid,*,intent,ios=False,stereo=False,require_trace=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,intent,monotonic,sleep)) and integer(pid,1) and type(ios) is bool
             and callable(getattr(files,'read',None)) and type(stereo) is bool and not (ios and stereo)
             and type(require_trace) is bool and (not require_trace or stereo))
        self.send,self.original,self.files,self.clock_ms,self.guard,self.pid=send,read,files,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep,self.intent=ios,monotonic,sleep,intent
        self.stereo,self.require_trace=stereo,require_trace;self.trace_frame=None;self.frame=None;self.execution=self.submission=0
        self.instance,self.sequence,self.acquisition,self.captured=None,0,0,0

    def read(self,after_sequence):
        try:
            need(integer(after_sequence) and after_sequence>=self.sequence and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            timeout=1.5 if self.ios else 5.0 # Fresh nonce causality bounds age without assuming equal host/native clocks.
            requested=self.clock_ms();need(integer(requested,1))
            request=('ios-' if self.ios else '')+uuid.uuid4().hex
            command=dict(schemaVersion=1,commandId=request,action='feature-world-render-observe')
            self.intent(dict(command)) # Persist potential native image ownership before acquisition.
            now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout);previous=now
            need(self.guard() is not False)
            self.send(command)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False)
                now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout);previous=now
                if type(value) is dict and value.get('requestId')==request:
                    epoch=value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    validate(value,request,self.pid,epoch,stereo=self.stereo,require_trace=self.require_trace)
                    source=value['source']
                    need(self.instance in (None,value['instance']) and value['sequence']>after_sequence
                         and source['acquisitionSequence']>self.acquisition and source['capturedEpochMs']>=self.captured
                         and (self.ios or value['requestedEpochMs']>=requested))
                    trace=source.get('renderTrace')
                    if trace is not None:need(trace['frameId']!=self.trace_frame)
                    if self.stereo:
                        frame=source['stereo'];present=source['presentation']
                        need(frame['frameIndex']!=self.frame and frame['executionSequence']>self.execution
                             and present['submissionSequence']>self.submission)
                    if callable(getattr(self.files,'bind',None)): self.files.bind(value)
                    png=self.files.read(source['image']['name'])
                    need(self.guard() is not False)
                    now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout)
                    previous=now
                    if not self.ios:fresh(source['capturedEpochMs'],self.clock_ms())
                    original_pixels(value,png)
                    need(self.guard() is not False)
                    now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout)
                    if not self.ios:fresh(source['capturedEpochMs'],self.clock_ms())
                    self.instance,self.sequence,self.acquisition,self.captured=value['instance'],value['sequence'],source['acquisitionSequence'],source['capturedEpochMs']
                    if self.stereo:self.frame,self.execution,self.submission=frame['frameIndex'],frame['executionSequence'],present['submissionSequence']
                    if trace is not None:self.trace_frame=trace['frameId']
                    return value,png
                if attempt<50:self.sleep(0.1)
        except Exception:
            raise NativeUIError('Original world render acquisition is unavailable or invalid') from None
        raise NativeUIError('Original world render acquisition did not produce this request')
