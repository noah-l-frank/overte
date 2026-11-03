"""Typed passive source4 samples; no synthesized legacy observation envelope."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import stat

from adapters.native_feature_observation import exact,integer,need,fresh,number
from adapters.native_avatar_render import nonce,loaded_source
from adapters.native_graphics_subject import vector,rotation
from adapters.world_render_evidence import recorded_view
from adapters.pico4.avatar_remote import client,rig
from adapters.pico4 import remote_joint_pose
from adapters.script_journey.history import same

VERSION=4
FRAME_LIMIT=196608
CONTROL_LIMIT=16384
SAMPLE_FILE='feature-pico-remote-avatar-stream.json'
CONTROL_FILE='feature-pico-remote-avatar-stream-control.json'
PENDING_FILE='feature-pico-remote-avatar-stream-pending.json'
ACTION='feature-pico-remote-avatar-stream-control'


def control_command(value):
    common={'schemaVersion','commandId','action','operation','runId'}
    need(type(value) is dict and value.get('operation') in ('arm','stop','drain'))
    operation=value['operation']
    exact(value,common|({'subjectSessionId','ownerPolicy'} if operation=='arm' else {'streamId','armCommandId','policySha256'}))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and nonce(value['commandId']) and nonce(value['runId']))
    if operation=='arm':
        from adapters.native_graphics_subject import entity_id
        need(entity_id(value['subjectSessionId']) and value['subjectSessionId']!='00000000-0000-0000-0000-000000000000'
            and type(value['ownerPolicy']) is str and len(value['ownerPolicy'].encode())<=8192)
    else:
        import re
        need(nonce(value['streamId']) and nonce(value['armCommandId']) and type(value['policySha256']) is str
            and re.fullmatch('[0-9a-f]{64}',value['policySha256']))
    return value


def control_reply(value,request,pid,epoch,policy_sha):
    control_command(request)
    exact(value,{'schemaVersion','picoRemoteAvatarStreamControlVersion','requestId','available','processId',
        'requestedEpochMs','capturedEpochMs','runId','streamId','armCommandId','ownerPolicySha256','nativeFrameLimit',
        'sampleIntervalMs','issuedFrames','publishedFrames','timerActive','deadlineTimerActive','controlCount',
        'pendingTimerObjects','nativeQueueQuiet','inFlightTick','stopped','drained','pendingWrite','armOriginal'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and type(value['picoRemoteAvatarStreamControlVersion']) is int and value['picoRemoteAvatarStreamControlVersion']==VERSION
        and value['requestId']==request['commandId'] and value['runId']==request['runId']
        and value['available'] is True and value['processId']==pid and integer(value['processId'],1)
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<1500
        and nonce(value['streamId']) and nonce(value['armCommandId']) and value['ownerPolicySha256']==policy_sha
        and integer(value['nativeFrameLimit'],256,256) and integer(value['sampleIntervalMs'],500,500)
        and integer(value['issuedFrames'],0,256) and integer(value['publishedFrames'],0,value['issuedFrames'])
        and integer(value['controlCount'],1,32) and integer(value['pendingTimerObjects'],0,2))
    for key in ('timerActive','deadlineTimerActive','nativeQueueQuiet','inFlightTick','stopped','drained','pendingWrite'):
        need(type(value[key]) is bool)
    fresh(value['capturedEpochMs'],epoch)
    original=value['armOriginal'];exact(original,{'rootNode','sampleNode','sampleStamp','sha256','bytes','sampleSequence'})
    for key,size in (('rootNode',5),('sampleNode',5),('sampleStamp',8)):
        need(type(original[key]) is list and len(original[key])==size
            and all(type(field) is str and re.fullmatch('0|[1-9][0-9]{0,19}',field) for field in original[key]))
    parent,node=original['rootNode'],original['sampleNode']
    need(stat.S_ISDIR(int(parent[2])) and stat.S_IMODE(int(parent[2]))==0o700 and int(parent[1])>0
        and stat.S_ISREG(int(node[2])) and stat.S_IMODE(int(node[2]))==0o600 and node[3]==parent[3] and node[4]=='1'
        and int(node[1])>0 and original['sampleStamp'][:5]==node
        and integer(original['bytes'],1,FRAME_LIMIT) and str(original['bytes'])==original['sampleStamp'][5]
        and integer(original['sampleSequence'],1,value['publishedFrames'])
        and type(original['sha256']) is str and re.fullmatch('[0-9a-f]{64}',original['sha256']))
    if request['operation']=='arm':
        need(value['armCommandId']==request['commandId'] and value['timerActive'] and value['deadlineTimerActive']
            and not value['stopped'] and not value['drained'] and not value['pendingWrite'])
    else:
        need(value['streamId']==request['streamId'] and value['armCommandId']==request['armCommandId']
            and value['stopped'] and not value['timerActive'] and not value['deadlineTimerActive'])
        if request['operation']=='drain':need(value['drained'] and value['nativeQueueQuiet'] and not value['inFlightTick']
            and not value['pendingWrite'] and value['pendingTimerObjects']==0)
    return value


def frame(value,*,run,subject,pid,epoch,stream,policy_sha):
    exact(value,{'schemaVersion','picoRemoteAvatarStreamFrameVersion','streamId','sampleSequence','processId',
        'requestedEpochMs','capturedEpochMs','ownerPolicySha256','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and type(value['picoRemoteAvatarStreamFrameVersion']) is int and value['picoRemoteAvatarStreamFrameVersion']==VERSION
        and nonce(value['streamId']) and value['streamId']==stream and value['ownerPolicySha256']==policy_sha
        and integer(value['sampleSequence'],1,256) and integer(value['processId'],1) and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'picoRemoteAvatarVersion','runId','clientBefore','clientAfter','selfSessionId',
        'subjectSessionId','subject','worldRenderInstance','cameraMode','view'})
    need(type(source['picoRemoteAvatarVersion']) is int and source['picoRemoteAvatarVersion']==VERSION
        and source['runId']==run and source['subjectSessionId']==subject)
    before=client(source['clientBefore'],run,value['capturedEpochMs']);after=client(source['clientAfter'],run,value['capturedEpochMs'])
    need(same(before,after) and source['selfSessionId']==before['sessionId'] and source['selfSessionId']!=subject
        and value['requestedEpochMs']<=source['clientBefore']['requestedEpochMs']
        and source['clientBefore']['capturedEpochMs']<=source['clientAfter']['requestedEpochMs'])
    avatar=source['subject'];exact(avatar,{'sessionId','avatarInstance','modelInstance','rigId','rig','remoteJointPose',
        'loaded','visible','addedToScene','avatarShouldRender','geometry','pose'})
    need(avatar['sessionId']==subject and nonce(avatar['avatarInstance']) and nonce(avatar['modelInstance'])
        and integer(avatar['rigId']) and all(type(avatar[key]) is bool for key in ('loaded','visible','addedToScene','avatarShouldRender')))
    need(type(avatar['rig']) is dict)
    if avatar['rig']:
        need(integer(avatar['rig'].get('capturedEpochMs'),1,value['capturedEpochMs']))
        rig(avatar['rig'],avatar['rigId'],avatar['rig']['capturedEpochMs'])
    # Same actual committed interpolation3 leaf as Source3; no local Rig
    # evaluation, Emote name, receipt or requested pose is manufactured here.
    remote_joint_pose.validate(avatar['remoteJointPose'],avatar,value['capturedEpochMs'],version=2)
    geometry=avatar['geometry']
    if geometry is not None:
        exact(geometry,{'instance','sourcePresent','sourceSha256'});need(nonce(geometry['instance']))
        loaded_source(geometry['sourcePresent'],geometry['sourceSha256'])
    need(avatar['loaded']==(geometry is not None))
    pose=avatar['pose'];exact(pose,{'feetPosition','orientation','modelScale'})
    vector(pose['feetPosition'],3,-1e6,1e6);rotation(pose['orientation']);need(number(pose['modelScale'],.0001,1000))
    need(type(source['cameraMode']) is str and len(source['cameraMode'])<=64 and '\0' not in source['cameraMode']
        and (source['worldRenderInstance'] is None or nonce(source['worldRenderInstance'])))
    recorded_view(source['view']);return value


def continuity(before,after):
    if before is None:return
    a,b=before['source'],after['source']
    need(after['streamId']==before['streamId'] and after['processId']==before['processId']
        and after['ownerPolicySha256']==before['ownerPolicySha256'] and after['sampleSequence']>before['sampleSequence']
        and after['requestedEpochMs']>=before['capturedEpochMs']
        and all(a[key]==b[key] for key in ('runId','selfSessionId','subjectSessionId'))
        and same(a['clientAfter']['identity'],b['clientBefore']['identity'])
        and all(a['subject'][key]==b['subject'][key] for key in ('sessionId','avatarInstance','modelInstance','rigId')))
    remote_joint_pose.continuity(a['subject']['remoteJointPose'],b['subject']['remoteJointPose'])


def independent(primary,actor):
    a,b=primary['source'],actor['source']
    need(primary['streamId']!=actor['streamId'] and a['runId']==b['runId']
        and a['selfSessionId']!=b['selfSessionId'] and b['subjectSessionId']==a['selfSessionId'] and a['subjectSessionId']==b['selfSessionId']
        and a['clientAfter']['identity']['domainId']==b['clientBefore']['identity']['domainId']
        and a['clientAfter']['identity']['domainSession']['domainSha256']==b['clientBefore']['identity']['domainSession']['domainSha256'])
