"""Fresh received motion after an independently replayed original episode.

Only the rooted decoder selects this additive original profile. Dropped rows
never establish the initial motion: the actual earlier version-one observation
must still fully qualify from its unchanged source, receive and image files.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_avatar_receive import validate as receive_packet
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,unpack
from ios.adapters import avatar_renderers
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_peer import acquisition,movement
from ios.adapters.emote_world import actual_domain

VERSION=2


def episode(left,right):
    """The same measured override, across play or its measured restoration."""
    return (left['kind'] in ('playback','restoration') and right['kind'] in ('playback','restoration')
        and all(same(left[key],right[key]) for key in ('baseline','before','played')))


def anchor_original(decoder,reference,sequence):
    exact(reference,{'index','sha256'})
    need(integer(sequence,2,512) and integer(reference['index'],1,sequence-1))
    path=decoder.root/('emote-observation-'+decoder.run+'-actor-'+str(reference['index'])+'.json')
    raw=PrivateFeatureState(path).read();need(raw is not None and digest(raw)==reference['sha256'])
    exact(raw,{'iosEmoteObserverRecordVersion','runId','role','binding','primaryBinding','fixtureUrl','phaseInstance','payload'})
    need(type(raw['iosEmoteObserverRecordVersion']) is int and raw['iosEmoteObserverRecordVersion']==1
        and raw['runId']==decoder.run and raw['role']==decoder.role=='actor'
        and same(raw['binding'],decoder.binding) and same(raw['primaryBinding'],decoder.primary_binding)
        and raw['phaseInstance']==decoder.phase_instance and type(raw['fixtureUrl']) is str
        and raw['fixtureUrl'].endswith('/runs/'+decoder.run+'/'))
    rows=unpack(raw['payload']);need(len(rows)==1)
    original=rows[0];need(type(original) is dict)
    need(type(original.get('iosEmoteObservationOriginalVersion')) is int
        and original['iosEmoteObservationOriginalVersion']==1 and original['sequence']==reference['index'])
    # A continuation cannot recursively borrow another continuation or cycle.
    decoder.derive(original)
    return original


def phase_follows(before,after):
    need(before['instance']==after['instance'] and before['runId']==after['runId']
        and before['area']==after['area']=='emotes' and before['createdEpochMs']==after['createdEpochMs']
        and after['capturedEpochMs']>=before['capturedEpochMs']
        and after['sequence']>=before['sequence']
        and len(after['activations'])>=len(before['activations'])
        and same(after['activations'][:len(before['activations'])],before['activations']))
    if before['sequence']==after['sequence']:need(same(before,after))
    else:need(before['requestId']!=after['requestId'])


def peer_follows(before,after,binding):
    """Continuity only; a dropped interval itself supplies no motion fact."""
    left,right=acquisition(before,binding),acquisition(after,binding)
    need(actual_domain(before['world'])==actual_domain(after['world']))
    if same(before,after):return
    follow(left['nativeAfter'],right['nativeBefore'])
    need(right['hostBeforeMonotonic']>=left['hostAfterMonotonic']
        and right['hostBeforeEpochMs']>=left['hostAfterEpochMs'])
    packet=after['receive'];pid=int(binding['processIdentity'])
    receive_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-avatar-receive-observe'),
        pid,right['nativeAfter']['capturedEpochMs'],previous=before['receive'])
    avatar_renderers.validate(after['renderers'],dict(schemaVersion=1,commandId=after['renderers']['requestId'],
        action=avatar_renderers.ACTION,runId=after['world']['runId']),pid,
        right['nativeAfter']['capturedEpochMs'],before['renderers'])


def derive(decoder,value,current,after):
    need(decoder.role=='actor' and value['peerBefore'] is not None)
    original=anchor_original(decoder,value['peerContinuation'],value['sequence'])
    need(episode(original['proof'],value['proof']) and original['peerAfter'] is not None
        and original['source']['index']<value['source']['index']
        and original['peerAfter']['index']<=value['peerBefore']['index']<value['peerAfter']['index'])
    source=decoder.source(original['source'])
    follow(source['clockJoin']['nativeAfter'],current['clockJoin']['nativeBefore'])
    phase_follows(source['phaseAfter'],current['phaseBefore'])
    anchor=decoder.retained(decoder.peers,original['peerAfter'])
    before=decoder.retained(decoder.peers,value['peerBefore'])
    phase_follows(anchor['phaseAfter'],before['phaseBefore'] if not same(anchor,before) else before['phaseAfter'])
    phase_follows(before['phaseAfter'],after['phaseBefore'])
    peer_follows(anchor['peer'],before['peer'],decoder.binding)
    # This is the unchanged strict motion proof inside the new current cut:
    # two real fresh differing joint records and a changed evaluated pose.
    return deepcopy(movement(current['world'],decoder.primary_binding,before['peer'],after['peer'],decoder.binding))
