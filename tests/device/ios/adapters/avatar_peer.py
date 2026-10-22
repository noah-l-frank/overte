"""Actual AvatarMixer metadata joined to independent loaded remote geometry.

Model identity, scale and attachments are read from originals. No expected
state or action acknowledgement supplies a received packet or loaded mesh.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_avatar_receive import validate as receive_packet,ACTION as RECEIVE_ACTION
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from ios.adapters import avatar_state,avatar_renderers
from ios.adapters.emote_peer import acquisition,session_sha
from ios.adapters.emote_world import actual_domain
from ios.adapters.graphics_history import follow_native

VERSION=1


def state_original(frame,binding):
    """Validate the actual state used by this join, with its original bracket."""
    context(binding);need(frame.get('avatarSourceGroupVersion')==2)
    originals=frame['originals'];join=validate_join(frame['clockJoin'],originals)
    pid=int(binding['processIdentity']);state=avatar_state.original(originals['state'])
    rendered=avatar_renderers.original(originals['renderers'])
    need(state['iosAvatarStateVersion']==2 and rendered['iosAvatarRenderersVersion']==4
        and join['nativeBefore']['processId']==join['nativeAfter']['processId']==pid)
    for row in (state,rendered):
        need(row['processId']==pid and row['runId']==state['runId']
            and join['nativeBefore']['capturedEpochMs']<=row['clockBefore']['epochMs']
            <=row['clockAfter']['epochMs']<=join['nativeAfter']['capturedEpochMs'])
    own=avatar_renderers.avatar(rendered,state['source']['sessionId'])
    need(own['requestedUrl']==state['source']['requestedUrl']
        and own['resourceUrl']==state['source']['resourceUrl']
        and own['geometryLoaded']==state['source']['geometryLoaded']
        and own['rigReady']==state['source']['rigReady']
        and own['shouldRender']==state['source']['shouldRender']
        and abs(own['targetScale']-state['source']['targetScale'])<.0001
        and abs(own['modelScale']-state['source']['modelScale'])<.0001)
    return state,join


def replication(primary_frame,primary_peer,before,after,actor_frame,primary_binding,actor_binding,*,wearables):
    """Fresh actual sender metadata plus geometry on a distinct actual SDK.

    Primary peer identities are acquired before its state, and actor state
    between its receive reads. Native epochs never cross a process boundary.
    Attachment IDs/resources come from separately retained original creation
    ownership; absence is checked against the complete actual entity tree.
    """
    context(primary_binding);context(actor_binding)
    need(primary_binding['sourceRevision']==actor_binding['sourceRevision']
        and primary_binding['artifactSha256']==actor_binding['artifactSha256']
        and primary_binding['targetFingerprint']!=actor_binding['targetFingerprint']
        and primary_binding['sessionId']!=actor_binding['sessionId'] and type(wearables) is dict)
    primary,pstate=state_original(primary_frame,primary_binding)
    actor,astate=state_original(actor_frame,actor_binding)
    pclock=acquisition(primary_peer,primary_binding)
    first,last=acquisition(before,actor_binding),acquisition(after,actor_binding)
    follow_native(pclock['nativeAfter'],pstate['nativeBefore'])
    follow_native(first['nativeAfter'],astate['nativeBefore']);follow_native(astate['nativeAfter'],last['nativeBefore'])
    need(pstate['hostBeforeMonotonic']>=pclock['hostAfterMonotonic']
        and astate['hostBeforeMonotonic']>=first['hostAfterMonotonic']
        and last['hostBeforeMonotonic']>=astate['hostAfterMonotonic'])
    pd=actual_domain(primary_peer['world']);ad=actual_domain(after['world'])
    need(actual_domain(before['world'])==ad and pd['domainId']==ad['domainId']
        and pd['avatarMixerSha256']==ad['avatarMixerSha256'] and pd['selfSha256']!=ad['selfSha256']
        and session_sha(primary['source']['sessionId'])==pd['selfSha256']
        and session_sha(actor['source']['sessionId'])==ad['selfSha256']
        and primary['runId']==actor['runId']==primary_peer['world']['runId']==after['world']['runId'])
    pid=int(actor_binding['processIdentity']);packet=after['receive']
    receive_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=RECEIVE_ACTION),pid,
        last['nativeAfter']['capturedEpochMs'],previous=before['receive'])
    rendered=after['renderers']
    avatar_renderers.validate(rendered,dict(schemaVersion=1,commandId=rendered['requestId'],
        action=avatar_renderers.ACTION,runId=primary['runId']),pid,last['nativeAfter']['capturedEpochMs'],before['renderers'])
    need(packet['source']['droppedRecords']<=before['receive']['source']['receiveSequence'])
    rows=[row for row in packet['source']['records'] if row['receiveSequence']>before['receive']['source']['receiveSequence']
        and row['avatarSha256']==pd['selfSha256']]
    need(rows and all(row['mixerSha256']==ad['avatarMixerSha256']
        and first['nativeAfter']['capturedEpochMs']<=row['capturedEpochMs']<=packet['capturedEpochMs'] for row in rows))
    source=primary['source'];latest=rows[-1]
    need(latest['advertisedModelUrl']==source['requestedUrl']
        and abs(latest['targetScale']-source['targetScale'])<.0001
        and abs(source['targetScale']-source['modelScale'])<.0001)
    remote=avatar_renderers.avatar(after['renderers'],source['sessionId'],remote=True)
    need(remote['requestedUrl']==source['requestedUrl']
        and abs(remote['targetScale']-source['targetScale'])<.0001
        and abs(remote['modelScale']-source['modelScale'])<.0001)
    own=avatar_renderers.avatar(primary_frame['originals']['renderers'],source['sessionId'])
    loaded=source['geometryLoaded'] and source['rigReady']
    need(loaded==(remote['geometryLoaded'] and remote['rigReady']))
    bounds=None;pose=None
    if loaded:
        resource=actor['source']['defaultResourceUrl'] if source['resourceUrl']==source['defaultResourceUrl'] else source['resourceUrl']
        need(own['geometryLoaded'] and own['rigReady'] and own['addedToScene'] and own['shouldRender']
            and remote['resourceUrl']==resource and remote['addedToScene'] and remote['shouldRender']
            and remote['jointNames']==own['jointNames'] and remote['jointIndices']==own['jointIndices']
            and remote['hipsIndex']==own['hipsIndex'])
        pose=avatar_renderers.external(after['renderers'],source['sessionId'],after_epoch=latest['capturedEpochMs'])
        need(latest['jointCount']==pose['totalJoints']
            and all(index<pose['totalJoints'] for index in remote['jointIndices'].values()))
        bounds=avatar_renderers.bounds(after['renderers'],source['sessionId'],remote=True)
    else:need(not remote['geometryLoaded'] and not remote['rigReady'])
    for entity_id,resource in wearables.items():
        avatar_state.session(entity_id)
        if resource is None:
            need(all(row['id']!=entity_id for row in after['renderers']['source']['tree']['entities'])
                and all(row['id']!=entity_id for row in after['renderers']['source']['avatarEntities']))
        else:
            need(loaded and avatar_renderers.wearable(primary_frame['originals']['renderers'],entity_id,source['sessionId'],resource)
                and avatar_renderers.wearable(after['renderers'],entity_id,source['sessionId'],resource,remote=True))
    return dict(iosAvatarPeerVersion=VERSION,primarySessionSha256=pd['selfSha256'],actorSessionSha256=ad['selfSha256'],
        avatarMixerSha256=ad['avatarMixerSha256'],remoteSessionId=source['sessionId'],
        receivedSequences=[row['receiveSequence'] for row in rows],requestedUrl=remote['requestedUrl'],
        resourceUrl=remote['resourceUrl'],modelLoaded=loaded,scale=remote['modelScale'],
        bounds=deepcopy(bounds),externalPose=deepcopy(pose),wearables=deepcopy(wearables))
