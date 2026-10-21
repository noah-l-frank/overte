"""Actual loaded/evaluated Emote playback and restoration, never UI ACKs.

Each proof retains the complete original source group. The caller owns durable
role/input/phase/image/lifetime journals; this pure join supplies no capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from posixpath import dirname,join,normpath
from urllib.parse import urlsplit,urlunsplit
from adapters.native_feature_observation import exact,fresh,integer,need,validate as native_packet
from adapters.native_animation_history import accept,clip_run,restored_after,moving_pose
from adapters.native_animation_caller import selected as selected_caller
from adapters.native_animation_source import controlled as controlled_animation
from adapters.emote_source_profile import select_from_roots
from feature_journeys.contract import typed_equal

VERSION=2
NAMES=('Crying','Surprised','Dancing','Cheering','Waving','Fall','Pointing','Clapping','Sit1','Sit2','Sit3','Love')
GROUP={'rootsBefore','script','native','rootsAfter'}


def asset_urls(selected):
    """Fixed animation directory relative to the original physical source."""
    relative='../assets/animations/' if selected['profile']['sourcePath'].endswith('/phoneEmote.js') else 'assets/animations/'
    assigned=urlsplit(selected.get('sourceUrl',selected['assignedUrl']))
    directory=normpath(join(dirname(assigned.path),relative))+'/'
    base='qrc:'+directory if assigned.scheme=='qrc' else urlunsplit((assigned.scheme,'',directory,'',''))
    return {base+name+'.fbx':name for name in NAMES}


def source(group,pid,epoch):
    exact(group,GROUP)
    selected=select_from_roots(group['script'],group['rootsBefore'],group['rootsAfter'],pid=pid,epoch=epoch)
    current=group['native']
    need(type(current) is dict and type(current.get('requestId')) is str
        and re.fullmatch(r'(?:ios-)?[0-9a-f]{32}',current['requestId']))
    native_packet(current,current.get('requestId'),pid,epoch,require_animation=True,require_animation_history=True)
    need(current['instance']==group['rootsBefore']['instance']
        and group['script']['capturedEpochMs']<=current.get('requestedEpochMs',0)
        <=current['animation']['capturedEpochMs']<=current['capturedEpochMs']<=group['rootsAfter']['requestedEpochMs'])
    history=current['animation']['history'];frames=history['frames'];need(bool(frames) and history['historyVersion']==2)
    last=frames[-1]
    need(last['overrideSequence']==history['overrideSequence']
        and last['overrideActive']==current['animation']['overrideActive']
        and last['evaluationSequence']<=current['animation']['evaluationSequence']
        and 0<=current['animation']['capturedEpochMs']-last['capturedEpochMs']<75)
    if last['evaluationSequence']==current['animation']['evaluationSequence']:
        need(all(row['index']<len(current['animation']['joints'])
            and typed_equal(row['pose'],current['animation']['joints'][row['index']]) for row in last['joints']))
    # Path selection follows actual submitted source and its original assigned
    # physical URL. The observed native clip selects a name from this inventory.
    # urllib.urljoin does not resolve Qt's qrc scheme. Resolve only this fixed
    # reviewed relative directory against the original physical assigned URL.
    return selected,current,asset_urls(selected)


def continuation(before,current,pid):
    need(type(before) is dict and type(before.get('requestId')) is str
        and re.fullmatch(r'(?:ios-)?[0-9a-f]{32}',before['requestId']))
    native_packet(before,before.get('requestId'),pid,before.get('capturedEpochMs'),require_animation_history=True)
    need(before['instance']==current['instance'] and current['sequence']>before['sequence']
        and current['requestedEpochMs']>=before['capturedEpochMs']
        and current['animation']['evaluationSequence']>before['animation']['evaluationSequence']
        and current['animation']['capturedEpochMs']>=before['animation']['capturedEpochMs']
        and all(current['lifecycle'][key]>=before['lifecycle'][key] for key in before['lifecycle']))
    previous=accept(None,before['animation']['rigId'],before['animation']['history'])
    accept(previous,current['animation']['rigId'],current['animation']['history'])
    need(current['animation']['history']['droppedEvents']<=before['animation']['history']['callSequence'])


def actual_state(current,event,urls,baseline):
    animation=current['animation'];history=animation['history'];request=event['request']
    need(event['request']['url'] in urls and history['overrideSequence']==event['overrideSequence'])
    restores=[row for row in history['events'] if row['kind']=='restore' and row['overrideSequence']==event['overrideSequence']
        and row['eventSequence']>event['eventSequence']]
    if animation['overrideActive']:
        need(not restores and 'clip' in animation)
        clip=animation['clip'];need(clip['url']==request['url']==clip['requestedUrl']
            and clip['loadedFrames']>0 and clip['evaluationSequence']>0
            and all(clip[key]==request[key] for key in ('firstFrame','lastFrame','framesPerSecond','loop'))
            and 0<=clip['firstFrame']<=clip['frame']<=clip['lastFrame']<=clip['loadedFrames']
            and clip['lastFrame']>clip['firstFrame'])
        fresh(clip['evaluatedEpochMs'],current['capturedEpochMs'])
        name=urls[clip['url']]
        before,after=baseline['animation']['joints'],animation['joints']
        need(bool(before) and len(before)==len(after))
        changed=sum(moving_pose(dict(joints=[dict(index=index,pose=left)]),
            dict(joints=[dict(index=index,pose=right)])) for index,(left,right) in enumerate(zip(before,after)))
        state=dict(animation='Sit' if name.startswith('Sit') else name,sit=name if name.startswith('Sit') else 'none',
            override=True,poseProgress=changed/len(before),
            restoredBeforeNominalEnd=False)
        return state,None,[]
    restored,frames=restored_after(current,event,after_epoch=event['capturedEpochMs'])
    need(request['loop'] is False and request['framesPerSecond']>0 and request['lastFrame']>request['firstFrame'])
    duration=(request['lastFrame']-request['firstFrame'])/request['framesPerSecond']*1000
    early=0<=restored['capturedEpochMs']-event['capturedEpochMs']<duration-250
    return dict(animation='idle',sit='none',override=False,poseProgress=0.,restoredBeforeNominalEnd=early),restored,frames


def playback(group,native_barrier,*,pid,epoch):
    """A new actual override, loaded advancing frames and changed final poses."""
    selected,current,urls=source(group,pid,epoch);continuation(native_barrier,current,pid)
    history=current['animation']['history'];floor=native_barrier['animation']['history']['callSequence']
    events=[row for row in history['events'] if row['kind']=='override' and row['eventSequence']>floor]
    need(len(events)==1);event=events[0]
    need(event['request']['url'] in urls and event['capturedEpochMs']>=native_barrier['capturedEpochMs']
        and selected['code']['submittedEpochMs']<=event['capturedEpochMs'])
    selected_caller(event,selected,after_epoch=native_barrier['capturedEpochMs'])
    original,frames=clip_run(current,event['request']['url'],after_event=floor,after_epoch=native_barrier['capturedEpochMs'])
    need(original==event)
    if 'compilation' in selected:
        originals=[controlled_animation(frame['clip'],urls[frame['clip']['url']],frame['capturedEpochMs']) for frame in frames]
        # The clip retains the data actually copied into this generation. A
        # cache hit may legitimately predate the input; it must not be retimed
        # or replaced between original playback samples/current evaluation.
        need(all(typed_equal(value,originals[0]) for value in originals))
        if current['animation']['overrideActive']:
            need(typed_equal(controlled_animation(current['animation']['clip'],urls[event['request']['url']],
                current['capturedEpochMs']),originals[0]))
    state,restore,inactive=actual_state(current,event,urls,native_barrier)
    if restore is not None:selected_caller(restore,selected,after_epoch=event['caller']['invokedEpochMs'])
    return dict(emoteRigVersion=VERSION,kind='playback',group=deepcopy(group),barrier=deepcopy(native_barrier),
        state=state,event=event,frameSequences=[frame['frameSequence'] for frame in frames],restore=restore,
        inactiveFrameSequences=[frame['frameSequence'] for frame in inactive])


def restoration(group,played,*,pid,epoch,native_barrier=None):
    """Current inactive evaluation plus an original restore in the same run.

    A supplied ordinary-input barrier additionally proves a new restore after
    that native barrier. No early/natural/button cause is accepted as an input.
    """
    exact(played,{'emoteRigVersion','kind','group','barrier','state','event','frameSequences','restore','inactiveFrameSequences'})
    need(type(played['emoteRigVersion']) is int and played['emoteRigVersion']==VERSION and played['kind']=='playback')
    original=playback(played['group'],played['barrier'],pid=pid,epoch=played['group']['rootsAfter']['capturedEpochMs'])
    need(typed_equal(original,played))
    selected,current,urls=source(group,pid,epoch)
    prior=select_from_roots(played['group']['script'],played['group']['rootsBefore'],played['group']['rootsAfter'],
        pid=pid,epoch=played['group']['rootsAfter']['capturedEpochMs'])
    need(typed_equal(selected,prior));continuation(played['group']['native'],current,pid)
    need(current['animation']['overrideActive'] is False)
    event=played['event'];state,restored,frames=actual_state(current,event,urls,played['barrier'])
    caller=selected_caller(restored,selected,after_epoch=event['caller']['invokedEpochMs'])
    need(caller['sequence']>event['caller']['sequence'])
    if native_barrier is not None:
        continuation(native_barrier,current,pid)
        need(native_barrier['animation']['overrideActive'] is True
            and native_barrier['animation']['history']['overrideSequence']==event['overrideSequence']
            and restored['eventSequence']>native_barrier['animation']['history']['callSequence']
            and restored['capturedEpochMs']>=native_barrier['capturedEpochMs']
            and caller['invokedEpochMs']>=native_barrier['capturedEpochMs'])
    return dict(emoteRigVersion=VERSION,kind='restoration',group=deepcopy(group),played=deepcopy(played),
        barrier=deepcopy(native_barrier),state=state,restore=deepcopy(restored),
        inactiveFrameSequences=[frame['frameSequence'] for frame in frames])
