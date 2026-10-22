"""Independent actual AvatarMixer receive and remote renderer pose joins.

This supplies remote movement provenance, never a remote clip name, requested
Sit variant, local AnimGraph state, or byte equality across interpolation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid
from adapters.native_avatar_receive import validate as receive_packet,motion as received_motion
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from ios.adapters import avatar_renderers as renderers
from ios.adapters.emote_world import original as world_original,actual_domain
from ios.adapters.graphics_history import follow_native

VERSION=1


def session_sha(value):return hashlib.sha256(uuid.UUID(value).bytes).hexdigest()


def acquisition(value,binding):
    exact(value,{'world','receive','renderers','clockJoin'});context(binding);pid=int(binding['processIdentity'])
    originals={k:value[k] for k in ('world','receive','renderers')};join=validate_join(value['clockJoin'],originals)
    need(join['nativeBefore']['processId']==join['nativeAfter']['processId']==pid)
    start,end=join['nativeBefore']['capturedEpochMs'],join['nativeAfter']['capturedEpochMs']
    world=world_original(value['world']);renderer=renderers.original(value['renderers'])
    for packet in (world,renderer):
        need(packet['processId']==pid and start<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=end)
    need(renderer['runId']==world['runId'] and renderer['iosAvatarRenderersVersion']>=3)
    domain=actual_domain(world);receive=value['receive'];query=dict(schemaVersion=1,commandId=receive['commandId'],action='feature-avatar-receive-observe')
    receive_packet(receive,query,pid,end)
    need(receive['source']['selfSha256']==domain['selfSha256'])
    self_rows=[r for r in renderer['source']['avatars'] if r['self']]
    need(len(self_rows)==1 and session_sha(self_rows[0]['sessionId'])==domain['selfSha256'])
    return join


def pose_changed(left,right):
    need(left['instance']==right['instance'] and left['rigId']==right['rigId']
        and right['evaluationSequence']>left['evaluationSequence'] and right['capturedEpochMs']>=left['capturedEpochMs']
        and left['totalJoints']==right['totalJoints'] and len(left['joints'])==len(right['joints']) and left['joints'])
    for a,b in zip(left['joints'],right['joints']):
        rotation=min(sum((x-y)**2 for x,y in zip(a[:4],b[:4])),sum((x+y)**2 for x,y in zip(a[:4],b[:4])))
        translation=sum((x-y)**2 for x,y in zip(a[4:],b[4:]))
        if rotation>1e-6 or translation>1e-6:return True
    return False


def movement(primary_world,primary_binding,before,after,actor_binding):
    """One real sender/session/domain, fresh incoming motion and evaluated pose.

    Native epochs are compared only inside the actor process. The primary
    source supplies actual session/domain identity and no actor clock fence.
    Host acquisition clocks remain independently recorded on both actor reads.
    """
    context(primary_binding);context(actor_binding);world_original(primary_world)
    need(primary_world['processId']==int(primary_binding['processIdentity'])
        and primary_binding['sourceRevision']==actor_binding['sourceRevision']
        and primary_binding['artifactSha256']==actor_binding['artifactSha256']
        and primary_binding['targetFingerprint']!=actor_binding['targetFingerprint']
        and primary_binding['sessionId']!=actor_binding['sessionId'])
    first,last=acquisition(before,actor_binding),acquisition(after,actor_binding)
    follow_native(first['nativeAfter'],last['nativeBefore'])
    need(last['hostBeforeMonotonic']>=first['hostAfterMonotonic'])
    primary=actual_domain(primary_world);old=actual_domain(before['world']);current=actual_domain(after['world'])
    need(old==current and primary['domainId']==current['domainId']
        and primary['avatarMixerSha256']==current['avatarMixerSha256'] and primary['selfSha256']!=current['selfSha256']
        and primary_world['runId']==before['world']['runId']==after['world']['runId'])
    pid=int(actor_binding['processIdentity']);packet=after['receive']
    receive_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-avatar-receive-observe'),pid,
        last['nativeAfter']['capturedEpochMs'],previous=before['receive'])
    rows=received_motion(before['receive']['source'],packet['source'],primary['selfSha256'])
    need(all(row['mixerSha256']==current['avatarMixerSha256']
        and first['nativeAfter']['capturedEpochMs']<=row['capturedEpochMs']<=packet['capturedEpochMs'] for row in rows))
    query=dict(schemaVersion=1,commandId=after['renderers']['requestId'],action=renderers.ACTION,runId=primary_world['runId'])
    renderers.validate(after['renderers'],query,pid,last['nativeAfter']['capturedEpochMs'],before['renderers'])
    candidates=[row for row in after['renderers']['source']['avatars'] if session_sha(row['sessionId'])==primary['selfSha256']]
    need(len(candidates)==1);remote_id=candidates[0]['sessionId']
    a=renderers.avatar(before['renderers'],remote_id,remote=True);b=renderers.avatar(after['renderers'],remote_id,remote=True)
    need(a['requestedUrl']==a['resourceUrl']==b['requestedUrl']==b['resourceUrl']
        and a['jointNames']==b['jointNames'] and a['jointIndices']==b['jointIndices']
        and a['hipsIndex']==b['hipsIndex'] and abs(a['modelScale']-b['modelScale'])<.0001
        and b['externalPose'] is not None and all(i<b['externalPose']['totalJoints'] for i in b['jointIndices'].values()))
    need(all(row['advertisedModelUrl']==b['resourceUrl'] and row['jointCount']==b['externalPose']['totalJoints']
        and abs(row['targetScale']-b['modelScale'])<.0001 for row in rows))
    left=renderers.external(before['renderers'],remote_id,after_epoch=first['nativeBefore']['capturedEpochMs'])
    right=renderers.external(after['renderers'],remote_id,after_epoch=max(first['nativeAfter']['capturedEpochMs'],rows[-1]['capturedEpochMs']))
    need(pose_changed(left,right))
    return dict(iosEmotePeerVersion=VERSION,primarySessionSha256=primary['selfSha256'],actorSessionSha256=current['selfSha256'],
        avatarMixerSha256=current['avatarMixerSha256'],remoteSessionId=remote_id,
        receivedSequences=[r['receiveSequence'] for r in rows],renderedBefore=left,renderedAfter=right)
