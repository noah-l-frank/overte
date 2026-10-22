"""Original executed Pico model draws joined to both submitted eye cameras."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_avatar_render import _OriginalQuery,envelope,nonce,loaded_source,validate as avatar_packet
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_graphics_subject import vector
from adapters.world_render_evidence import validate as capture_packet,digest

VERSION=1
FILE='feature-pico-world-model-draws.json'
ACTION='feature-pico-world-model-draws-observe'


def command(value):
    exact(value,{'schemaVersion','commandId','action','captureRequestId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and nonce(value['commandId']) and nonce(value['captureRequestId']))
    return value


def camera_key(sequence,row):
    return (sequence,row['slot'],row['eye'],tuple(row['drawViewport']))


def validate(value,request,pid,epoch,*,capture):
    command(request);envelope(value,request,pid,epoch)
    capture_packet(capture,request['captureRequestId'],pid,epoch,stereo=True,require_trace=True,require_cameras=True)
    original=capture['source'];source=value['source'];frame=original['renderTrace']
    exact(source,{'picoModelCaptureVersion','captureRequestId','captureSequence','acquisitionSequence',
        'captureCapturedEpochMs','imageSha256','pixelSha256','modelTrace'})
    need(type(source['picoModelCaptureVersion']) is int and source['picoModelCaptureVersion']==VERSION
        and value['instance']==capture['instance'] and source['captureRequestId']==capture['requestId']
        and integer(source['captureSequence'],1) and source['captureSequence']==capture['sequence']
        and integer(source['acquisitionSequence'],1) and source['acquisitionSequence']==original['acquisitionSequence']
        and integer(source['captureCapturedEpochMs'],1) and source['captureCapturedEpochMs']==original['capturedEpochMs']
        and capture['capturedEpochMs']<=value['requestedEpochMs']
        and digest(source['imageSha256']) and source['imageSha256']==original['image']['sha256']
        and digest(source['pixelSha256']) and source['pixelSha256']==original['image']['pixelSha256'])
    trace=source['modelTrace']
    exact(trace,{'picoModelTraceVersion','frameId','frameIndex','executionSequence','recordedEpochMs',
        'begunEpochMs','completedEpochMs','renderer','view','drawCommands','models'})
    need(type(trace['picoModelTraceVersion']) is int and trace['picoModelTraceVersion']==VERSION
        and nonce(trace['frameId']) and trace['frameId']==frame['frameId']
        and integer(trace['frameIndex'],0,2**32-1) and trace['frameIndex']==frame['frameIndex']
        and integer(trace['executionSequence'],1) and trace['executionSequence']==frame['executionSequence']
        and trace['renderer']=='forward' and trace['view']=='main-stereo'
        and integer(trace['recordedEpochMs'],1) and trace['recordedEpochMs']==frame['recordedEpochMs']
        and integer(trace['begunEpochMs'],1) and trace['begunEpochMs']==frame['begunEpochMs']
        and integer(trace['completedEpochMs'],1) and trace['begunEpochMs']<=trace['completedEpochMs']<=frame['completedEpochMs']
        and integer(trace['drawCommands'],0,min(4096,frame['forwardDrawCommands']))
        and type(trace['models']) is list and len(trace['models'])<=128)
    fresh(trace['recordedEpochMs'],epoch)
    cameras={camera_key(batch['sequence'],camera):camera for batch in frame['cameraBatches'] if batch['role']=='forward'
        for camera in batch['cameras']}
    claimed={};seen=set();total=references=0
    for row in trace['models']:
        exact(row,{'modelInstance','geometryInstance','loadedSourcePresent','loadedSourceSha256','drawCommands',
            'skinnedDrawCommands','blendshapedDrawCommands','originalGeometryDrawCommands','indices','minimum','maximum','cameraUses'})
        need(nonce(row['modelInstance']) and nonce(row['geometryInstance']))
        identity=(row['modelInstance'],row['geometryInstance']);need(identity not in seen);seen.add(identity)
        loaded_source(row['loadedSourcePresent'],row['loadedSourceSha256'])
        need(integer(row['drawCommands'],1,4096) and integer(row['indices'],row['drawCommands'],row['drawCommands']*100000000))
        for field in ('skinnedDrawCommands','blendshapedDrawCommands','originalGeometryDrawCommands'):
            need(integer(row[field],0,row['drawCommands']))
        vector(row['minimum'],3,-1e6,1e6);vector(row['maximum'],3,-1e6,1e6)
        need(all(a<=b for a,b in zip(row['minimum'],row['maximum'])))
        need(type(row['cameraUses']) is list and 2<=len(row['cameraUses'])<=512)
        used=set();eyes={'left':0,'right':0}
        for use in row['cameraUses']:
            exact(use,{'batchSequence','slot','eye','drawViewport','drawCommands'})
            need(integer(use['batchSequence'],1) and integer(use['slot'],0,4096) and use['eye'] in ('left','right'))
            need(type(use['drawViewport']) is list and len(use['drawViewport'])==4
                and all(integer(v,0,32768) for v in use['drawViewport']) and all(v>0 for v in use['drawViewport'][2:]))
            key=camera_key(use['batchSequence'],use)
            need(key in cameras and key not in used and integer(use['drawCommands'],1,row['drawCommands']))
            used.add(key);eyes[use['eye']]+=use['drawCommands'];references+=1
            claimed[key]=claimed.get(key,0)+use['drawCommands'];need(claimed[key]<=cameras[key]['drawCommands'])
        need(eyes['left']==eyes['right']==row['drawCommands'])
        total+=row['drawCommands']
    need(total==trace['drawCommands'] and references<=512)
    return value


class PicoWorldModelDraws(_OriginalQuery):
    def read(self,capture):
        need(type(capture) is dict and nonce(capture.get('requestId')))
        original=deepcopy(capture)
        request=command(self._request(ACTION,captureRequestId=original.get('requestId')))
        return self._read(request,lambda value,query,pid,epoch:validate(value,query,pid,epoch,capture=original))


def avatar_draws(before,after,capture,draws,pid,epoch):
    """Join original loaded Rig/geometry/pose to actual stereo draw provenance.

    Current challenge pixels and independent actor proof remain separate. The
    central recording frustum is compared only with the central recorded view;
    eye projection must use the specific actual cameraUses returned here.
    """
    for packet in (before,after):
        avatar_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action='feature-avatar-render-observe'),pid,epoch)
    validate(draws,dict(schemaVersion=1,commandId=draws.get('requestId'),action=ACTION,captureRequestId=capture.get('requestId')),pid,epoch,capture=capture)
    left,right=before['source'],after['source'];frame=capture['source']['renderTrace']
    need(before['instance']==after['instance'] and before['sequence']<after['sequence']
        and before['capturedEpochMs']<=frame['recordedEpochMs'] and capture['source']['capturedEpochMs']<=after['requestedEpochMs'])
    for field in ('modelInstance','rigId','geometry','cameraMode'):
        need(left[field]==right[field])
    def near(a,b,tolerance):return len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b))
    def rotation(a,b):return near(a,b,.001) or near(a,[-v for v in b],.001)
    need(near(left['pose']['feetPosition'],right['pose']['feetPosition'],.005)
        and rotation(left['pose']['orientation'],right['pose']['orientation'])
        and abs(left['pose']['modelScale']-right['pose']['modelScale'])<=1e-4)
    for source in (left,right):
        need(all(source[k] is True for k in ('loaded','visible','addedToScene','localRenderingEnabled','avatarShouldRender'))
            and source['geometry'] is not None and source['geometry']['sourcePresent'])
        live=source['view'];recorded=frame['recordedView']
        need(near(live['position'],recorded['position'],.005) and rotation(live['rotation'],recorded['rotation'])
            and near(live['projection'],recorded['projection'],1e-4))
        for field in ('fieldOfViewDegrees','aspectRatio','nearClip','farClip'):
            need(abs(live[field]-recorded[field])<=1e-4*max(1,abs(recorded[field])))
    rows=[row for row in draws['source']['modelTrace']['models'] if row['modelInstance']==left['modelInstance']]
    need(len(rows)==1);row=rows[0];geometry=left['geometry']
    need(row['geometryInstance']==geometry['instance'] and row['loadedSourcePresent']
        and row['loadedSourceSha256']==geometry['sourceSha256'] and row['skinnedDrawCommands']>0
        and row['originalGeometryDrawCommands']==row['drawCommands']
        and all(a<b for a,b in zip(row['minimum'],row['maximum'])))
    return deepcopy(row)
