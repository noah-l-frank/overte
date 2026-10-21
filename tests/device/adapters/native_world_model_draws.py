"""Executed model draw table bound to one original main-mono GPU PNG."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce,loaded_source,validate as avatar_packet
from adapters.native_graphics_subject import vector
from adapters.world_render_evidence import validate as capture_packet,digest

VERSION=1
FILE='feature-world-model-draws.json'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','captureRequestId'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-world-model-draws-observe' and nonce(value['commandId'],ios=ios)
         and nonce(value['captureRequestId'],ios=ios))
    return value


def validate(value,request,pid,epoch,*,capture):
    command(request,ios=request['commandId'].startswith('ios-'));envelope(value,request,pid,epoch)
    capture_packet(capture,request['captureRequestId'],pid,epoch)
    original=capture['source'];source=value['source']
    need(original['captureVersion']==2 and original['renderTrace']['traceVersion']==2)
    exact(source,{'modelCaptureVersion','captureRequestId','captureSequence','acquisitionSequence',
        'captureCapturedEpochMs','imageSha256','pixelSha256','modelTrace'})
    need(type(source['modelCaptureVersion']) is int and source['modelCaptureVersion']==VERSION
         and value['instance']==capture['instance'] and request['captureRequestId']==source['captureRequestId']==capture['requestId']
         and integer(source['captureSequence'],1) and source['captureSequence']==capture['sequence']
         and integer(source['acquisitionSequence'],1) and source['acquisitionSequence']==original['acquisitionSequence']
         and integer(source['captureCapturedEpochMs'],1) and source['captureCapturedEpochMs']==original['capturedEpochMs']
         and capture['capturedEpochMs']<=value['requestedEpochMs']
         and digest(source['imageSha256']) and source['imageSha256']==original['image']['sha256']
         and digest(source['pixelSha256']) and source['pixelSha256']==original['image']['pixelSha256'])
    trace=source['modelTrace'];frame=original['renderTrace']
    exact(trace,{'modelTraceVersion','frameId','recordedEpochMs','begunEpochMs','completedEpochMs','renderer','view','drawCommands','models'})
    need(type(trace['modelTraceVersion']) is int and trace['modelTraceVersion']==VERSION
         and nonce(trace['frameId']) and trace['frameId']==frame['frameId']
         and trace['renderer']=='forward' and trace['view']=='main-mono'
         and trace['recordedEpochMs']==frame['recordedEpochMs'] and integer(trace['recordedEpochMs'],1)
         and trace['begunEpochMs']==frame['begunEpochMs'] and integer(trace['begunEpochMs'],1)
         and integer(trace['completedEpochMs'],1) and trace['begunEpochMs']<=trace['completedEpochMs']<=frame['completedEpochMs']
         and integer(trace['drawCommands'],0,1000000) and trace['drawCommands']<=frame['forwardDrawCommands']
         and type(trace['models']) is list and len(trace['models'])<=128)
    fresh(trace['recordedEpochMs'],epoch)
    seen=set();total=0
    for row in trace['models']:
        exact(row,{'modelInstance','geometryInstance','loadedSourcePresent','loadedSourceSha256','drawCommands',
            'skinnedDrawCommands','blendshapedDrawCommands','originalGeometryDrawCommands','indices','minimum','maximum'})
        need(nonce(row['modelInstance']) and nonce(row['geometryInstance']))
        identity=(row['modelInstance'],row['geometryInstance']);need(identity not in seen);seen.add(identity)
        loaded_source(row['loadedSourcePresent'],row['loadedSourceSha256'])
        need(integer(row['drawCommands'],1,1000000) and integer(row['indices'],row['drawCommands'],9007199254740991))
        for key in ('skinnedDrawCommands','blendshapedDrawCommands','originalGeometryDrawCommands'):
            need(integer(row[key],0,row['drawCommands']))
        vector(row['minimum'],3,-1e6,1e6);vector(row['maximum'],3,-1e6,1e6)
        need(all(a<=b for a,b in zip(row['minimum'],row['maximum'])))
        total+=row['drawCommands']
    need(total==trace['drawCommands'])
    return value


class NativeWorldModelDraws(_OriginalQuery):
    def read(self,capture):
        request=command(self._request('feature-world-model-draws-observe',captureRequestId=capture.get('requestId')),ios=self.ios)
        return self._read(request,lambda value,query,pid,epoch:validate(value,query,pid,epoch,capture=capture))


def _near(a,b,tolerance=1e-4):
    return len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b))


def avatar_draws(before,after,capture,draws,pid,epoch):
    """Join original loaded geometry to executed draws, NOT visible fragments.

    The caller must separately prove controlled avatar/fixture identity, current
    challenge pixels, meaningful body ROI changes and owned resource cleanup.
    """
    for packet in (before,after):
        avatar_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action='feature-avatar-render-observe'),pid,epoch)
    request=dict(schemaVersion=1,commandId=draws.get('requestId'),action='feature-world-model-draws-observe',captureRequestId=capture.get('requestId'))
    validate(draws,request,pid,epoch,capture=capture)
    left,right=before['source'],after['source'];frame=capture['source']['renderTrace']
    need(before['instance']==after['instance'] and before['sequence']<after['sequence']
         and before['capturedEpochMs']<=frame['recordedEpochMs'] and capture['source']['capturedEpochMs']<=after['requestedEpochMs'])
    for key in ('modelInstance','rigId','geometry','cameraMode'):
        need(left[key]==right[key])
    for source in (left,right):
        need(all(source[k] is True for k in ('loaded','visible','addedToScene','localRenderingEnabled','avatarShouldRender'))
             and source['geometry'] is not None and source['geometry']['sourcePresent'])
    need(_near(left['pose']['feetPosition'],right['pose']['feetPosition'],.005)
         and (_near(left['pose']['orientation'],right['pose']['orientation'],.001)
              or _near(left['pose']['orientation'],[-v for v in right['pose']['orientation']],.001))
         and abs(left['pose']['modelScale']-right['pose']['modelScale'])<=1e-4)
    recorded=frame['recordedView']
    for live in (left['view'],right['view']):
        need(_near(live['position'],recorded['position'],.005)
             and (_near(live['rotation'],recorded['rotation'],.001) or _near(live['rotation'],[-v for v in recorded['rotation']],.001))
             and _near(live['projection'],recorded['projection']))
        for key in ('fieldOfViewDegrees','aspectRatio','nearClip','farClip'):
            need(abs(live[key]-recorded[key])<=1e-4*max(1,abs(recorded[key])))
    rows=[row for row in draws['source']['modelTrace']['models'] if row['modelInstance']==left['modelInstance']]
    need(len(rows)==1)
    row=rows[0];geometry=left['geometry']
    need(row['geometryInstance']==geometry['instance'] and row['loadedSourcePresent']
         and row['loadedSourceSha256']==geometry['sourceSha256'] and row['skinnedDrawCommands']>0
         and row['originalGeometryDrawCommands']==row['drawCommands']
         and all(a<b for a,b in zip(row['minimum'],row['maximum'])))
    return deepcopy(row)
