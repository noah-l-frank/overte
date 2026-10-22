"""Original Rig calls/pose frames; no chooser ACK, desired pose or cause label."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,number,need


def clip(value,*,epoch=None):
    sourced=type(value) is dict and 'animationSourceVersion' in value
    exact(value,{'url','requestedUrl','frame','firstFrame','lastFrame','framesPerSecond','loop',
        'loadedFrames','evaluatedEpochMs','evaluationSequence'}|({'animationSourceVersion','assetSource'} if sourced else set()))
    need(all(type(value[k]) is str and len(value[k])<=4096 and not any(ord(c)<32 for c in value[k]) for k in ('url','requestedUrl'))
         and all(number(value[k]) for k in ('frame','firstFrame','lastFrame','framesPerSecond'))
         and type(value['loop']) is bool and integer(value['loadedFrames'],0,1000000)
         and integer(value['evaluatedEpochMs']) and integer(value['evaluationSequence']))
    if sourced:
        need(type(value['animationSourceVersion']) is int and value['animationSourceVersion']==1)
        source=value['assetSource']
        if source is not None:
            need(type(source) is dict)
            from adapters.native_animation_source import validate as source_packet
            source_packet(source,epoch if epoch is not None else max(value['evaluatedEpochMs'],source.get('consumedEpochMs',0)))
            need(source['model']['frames']==value['loadedFrames'])
            if value['evaluatedEpochMs']>0:need(source['consumedEpochMs']<=value['evaluatedEpochMs'])


def validate(value,animation,epoch):
    exact(value,{'historyVersion','instance','available','callSequence','overrideSequence','frameSequence',
        'droppedEvents','droppedFrames','events','frames'})
    need(type(value['historyVersion']) is int and value['historyVersion']==1 and value['available'] is True
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and all(integer(value[k]) for k in ('callSequence','overrideSequence','frameSequence','droppedEvents','droppedFrames'))
         and type(value['events']) is list and len(value['events'])<=64 and type(value['frames']) is list and len(value['frames'])<=32
         and value['callSequence']==value['droppedEvents']+len(value['events'])
         and value['frameSequence']==value['droppedFrames']+len(value['frames'])
         and value['overrideSequence']<=value['callSequence'])
    previous=0;generation=0
    for index,event in enumerate(value['events']):
        need(type(event) is dict and event.get('kind') in ('override','restore'))
        exact(event,{'eventSequence','kind','overrideSequence','capturedEpochMs'}|({'request'} if event['kind']=='override' else set()))
        need(integer(event['eventSequence'],1) and event['eventSequence']==value['droppedEvents']+index+1
             and integer(event['overrideSequence'],1,value['overrideSequence']) and event['overrideSequence']>=generation
             and integer(event['capturedEpochMs'],1) and previous<=event['capturedEpochMs']<=epoch)
        if event['kind']=='override':
            need(index==0 or event['overrideSequence']>generation)
            request=event['request'];exact(request,{'url','framesPerSecond','loop','firstFrame','lastFrame'})
            need(type(request['url']) is str and 0<len(request['url'])<=4096 and not any(ord(c)<32 for c in request['url'])
                 and all(number(request[k]) for k in ('framesPerSecond','firstFrame','lastFrame')) and type(request['loop']) is bool)
        previous,generation=event['capturedEpochMs'],event['overrideSequence']
    if value['events']:need(generation==value['overrideSequence'])
    else:need(value['callSequence']==0 and value['overrideSequence']==0)
    previous=evaluation=generation=0
    for index,frame in enumerate(value['frames']):
        need(type(frame) is dict)
        exact(frame,{'frameSequence','overrideSequence','evaluationSequence','capturedEpochMs','overrideActive','joints'}
             |({'clip'} if 'clip' in frame else set()))
        need(integer(frame['frameSequence'],1) and frame['frameSequence']==value['droppedFrames']+index+1
             and integer(frame['overrideSequence'],0,value['overrideSequence']) and frame['overrideSequence']>=generation
             and integer(frame['evaluationSequence'],evaluation+1,animation['evaluationSequence'])
             and integer(frame['capturedEpochMs'],1) and previous<=frame['capturedEpochMs']<=animation['capturedEpochMs']
             and type(frame['overrideActive']) is bool and type(frame['joints']) is list and len(frame['joints'])<=32)
        indices=[]
        for joint in frame['joints']:
            exact(joint,{'index','pose'})
            need(integer(joint['index'],0,255) and type(joint['pose']) is list and len(joint['pose'])==7
                 and all(number(v) for v in joint['pose']) and .9<=sum(v*v for v in joint['pose'][:4])<=1.1)
            indices.append(joint['index'])
        need(indices==sorted(set(indices)) and ('clip' not in frame or frame['overrideActive']))
        if 'clip' in frame:
            clip(frame['clip'],epoch=frame['capturedEpochMs']);need(frame['clip']['evaluatedEpochMs']<=frame['capturedEpochMs'])
        previous,evaluation,generation=frame['capturedEpochMs'],frame['evaluationSequence'],frame['overrideSequence']
    return value


def accept(previous,rig,history):
    if previous is not None:
        need(rig==previous['rig'] and history['instance']==previous['history']['instance'])
        old=previous['history']
        need(all(history[k]>=old[k] for k in ('callSequence','overrideSequence','frameSequence','droppedEvents','droppedFrames')))
        for field,key in (('events','eventSequence'),('frames','frameSequence')):
            before={row[key]:row for row in old[field]};current={row[key]:row for row in history[field]}
            need(all(before[n]==current[n] for n in before.keys()&current.keys()))
            dropped=history['droppedEvents' if field=='events' else 'droppedFrames']
            need(all(n<=dropped for n in before.keys()-current.keys()))
    return dict(rig=rig,history=deepcopy(history))


def moving_pose(left,right):
    need([r['index'] for r in left['joints']]==[r['index'] for r in right['joints']] and bool(left['joints']))
    for a,b in zip(left['joints'],right['joints']):
        a,b=a['pose'],b['pose']
        need(.9<=sum(v*v for v in a[:4])<=1.1 and .9<=sum(v*v for v in b[:4])<=1.1)
        rotation=min(sum((a[n]-b[n])**2 for n in range(4)),sum((a[n]+b[n])**2 for n in range(4)))
        if rotation+sum((a[n]-b[n])**2 for n in range(4,7))>1e-8:return True
    return False


def clip_run(value,url,*,after_event,after_epoch):
    """A native call plus original loaded, advancing clip and changed poses.

    Historical frames can precede the acquisition envelope, but must follow
    the caller's original action barrier. No effect verdict/target pose input.
    """
    animation=value['animation'];history=validate(animation['history'],animation,value['capturedEpochMs'])
    need(integer(after_event) and integer(after_epoch,1) and type(url) is str)
    events=[e for e in history['events'] if e['kind']=='override' and e['eventSequence']>after_event
            and e['capturedEpochMs']>=after_epoch and e['request']['url']==url]
    need(len(events)==1);event=events[0];request=event['request']
    need(request['loop'] is False and 0<request['framesPerSecond']<=240 and 0<=request['firstFrame']<request['lastFrame'])
    frames=[f for f in history['frames'] if f['overrideActive'] and f['overrideSequence']==event['overrideSequence']
            and f['capturedEpochMs']>=event['capturedEpochMs'] and 'clip' in f]
    loaded=[]
    for frame in frames:
        sample=frame['clip']
        if (sample['url']==url and sample['requestedUrl']==url and sample['loadedFrames']>0
                and sample['evaluationSequence']>0 and sample['evaluatedEpochMs']>=event['capturedEpochMs']
                and request['firstFrame']<=sample['frame']<=request['lastFrame']<=sample['loadedFrames']
                and all(sample[k]==request[k] for k in ('firstFrame','lastFrame','framesPerSecond','loop'))):loaded.append(frame)
    need(len(loaded)>=2)
    first,last=loaded[0],loaded[-1]
    need(last['clip']['evaluationSequence']>first['clip']['evaluationSequence'] and last['clip']['frame']>first['clip']['frame']
         and all(b['clip']['evaluationSequence']>=a['clip']['evaluationSequence'] and b['clip']['frame']>=a['clip']['frame']
                 for a,b in zip(loaded,loaded[1:]))
         and any(moving_pose(a,b) for a,b in zip(loaded,loaded[1:])))
    return deepcopy(event),deepcopy(loaded)


def restored_after(value,event,*,after_epoch,before_nominal_end=False):
    """Native restore and later inactive evaluation; no inferred input cause."""
    animation=value['animation'];history=validate(animation['history'],animation,value['capturedEpochMs'])
    need(integer(after_epoch,1) and type(before_nominal_end) is bool and event in history['events'] and event['kind']=='override')
    restores=[e for e in history['events'] if e['kind']=='restore' and e['overrideSequence']==event['overrideSequence']
        and e['eventSequence']>event['eventSequence'] and e['capturedEpochMs']>=after_epoch]
    need(len(restores)==1);restored=restores[0]
    frames=[f for f in history['frames'] if not f['overrideActive'] and f['overrideSequence']==event['overrideSequence']
        and f['capturedEpochMs']>=restored['capturedEpochMs']]
    need(bool(frames))
    if before_nominal_end:
        request=event['request'];need(request['loop'] is False and request['framesPerSecond']>0)
        duration=(request['lastFrame']-request['firstFrame'])/request['framesPerSecond']*1000
        need(0<=restored['capturedEpochMs']-event['capturedEpochMs']<duration-250)
    return deepcopy(restored),deepcopy(frames)
