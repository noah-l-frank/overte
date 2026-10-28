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
from ios.adapters.emote_peer import acquisition,movement,session_sha,pose_changed
from ios.adapters.emote_world import actual_domain

VERSION=2
RESTORED_VERSION=3


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


def source_follows(before,after):
    """The original primary source cannot regress either host clock."""
    left,right=before['clockJoin'],after['clockJoin']
    follow(left['nativeAfter'],right['nativeBefore'])
    need(right['hostBeforeMonotonic']>=left['hostAfterMonotonic']
        and right['hostBeforeEpochMs']>=left['hostAfterEpochMs'])


def derive(decoder,value,current,after):
    need(decoder.role=='actor' and value['peerBefore'] is not None)
    original=anchor_original(decoder,value['peerContinuation'],value['sequence'])
    need(episode(original['proof'],value['proof']) and original['peerAfter'] is not None
        and original['source']['index']<value['source']['index']
        and original['peerAfter']['index']<=value['peerBefore']['index']<value['peerAfter']['index'])
    source=decoder.source(original['source'])
    source_follows(source,current)
    phase_follows(source['phaseAfter'],current['phaseBefore'])
    anchor=decoder.retained(decoder.peers,original['peerAfter'])
    before=decoder.retained(decoder.peers,value['peerBefore'])
    phase_follows(anchor['phaseAfter'],before['phaseBefore'] if not same(anchor,before) else before['phaseAfter'])
    phase_follows(before['phaseAfter'],after['phaseBefore'])
    peer_follows(anchor['peer'],before['peer'],decoder.binding)
    # This is the unchanged strict motion proof inside the new current cut:
    # two real fresh differing joint records and a changed evaluated pose.
    return deepcopy(movement(current['world'],decoder.primary_binding,before['peer'],after['peer'],decoder.binding))


def restored_derive(decoder,value,current,after):
    """Original restored peer pose, never a claim of fresh continuing motion.

    Native restore/caller/Rig history was independently checked by state().
    The original literal playback supplies only the Actor's actual pre-effect
    peer baseline. Every later cut still supplies fresh receiver/renderer data.
    """
    need(decoder.role=='actor' and value['proof']['kind']=='restoration' and value['peerBefore'] is not None)
    original=anchor_original(decoder,value['peerContinuation'],value['sequence'])
    need(original['proof']['kind']=='playback' and episode(original['proof'],value['proof'])
        and original['peerBefore'] is not None and original['peerAfter'] is not None
        and original['source']['index']<value['source']['index']
        and original['peerAfter']['index']<=value['peerBefore']['index']<value['peerAfter']['index'])
    source=decoder.source(original['source']);source_follows(source,current)
    phase_follows(source['phaseAfter'],current['phaseBefore'])
    baseline=decoder.retained(decoder.peers,original['peerBefore'])
    anchor=decoder.retained(decoder.peers,original['peerAfter'])
    before=decoder.retained(decoder.peers,value['peerBefore'])
    phase_follows(baseline['phaseAfter'],anchor['phaseBefore'])
    phase_follows(anchor['phaseAfter'],before['phaseBefore'] if not same(anchor,before) else before['phaseAfter'])
    phase_follows(before['phaseAfter'],after['phaseBefore'])
    peer_follows(baseline['peer'],anchor['peer'],decoder.binding)
    peer_follows(anchor['peer'],before['peer'],decoder.binding)
    peer_follows(before['peer'],after['peer'],decoder.binding)
    need(current['world']['processId']==int(decoder.primary_binding['processIdentity'])
        and current['world']['runId']==after['peer']['world']['runId']==decoder.run
        and decoder.primary_binding['sourceRevision']==decoder.binding['sourceRevision']
        and decoder.primary_binding['artifactSha256']==decoder.binding['artifactSha256']
        and decoder.primary_binding['targetFingerprint']!=decoder.binding['targetFingerprint']
        and decoder.primary_binding['sessionId']!=decoder.binding['sessionId'])
    primary=actual_domain(current['world']);actor=actual_domain(after['peer']['world'])
    need(primary['domainId']==actor['domainId'] and primary['avatarMixerSha256']==actor['avatarMixerSha256']
        and primary['selfSha256']!=actor['selfSha256'])
    rows=[row for row in after['peer']['renderers']['source']['avatars'] if session_sha(row['sessionId'])==primary['selfSha256']]
    need(len(rows)==1);remote=rows[0]['sessionId']
    old=avatar_renderers.avatar(baseline['peer']['renderers'],remote,remote=True)
    new=avatar_renderers.avatar(after['peer']['renderers'],remote,remote=True)
    need(old['requestedUrl']==old['resourceUrl']==new['requestedUrl']==new['resourceUrl']
        and old['jointNames']==new['jointNames'] and old['jointIndices']==new['jointIndices']
        and old['hipsIndex']==new['hipsIndex'] and abs(old['modelScale']-new['modelScale'])<.0001)
    first=acquisition(baseline['peer'],decoder.binding);cut=acquisition(before['peer'],decoder.binding);last=acquisition(after['peer'],decoder.binding)
    neutral=avatar_renderers.external(baseline['peer']['renderers'],remote,after_epoch=first['nativeBefore']['capturedEpochMs'])
    restored=avatar_renderers.external(after['peer']['renderers'],remote,after_epoch=cut['nativeAfter']['capturedEpochMs'])
    need(not pose_changed(neutral,restored))
    left=before['peer']['receive']['source'];right=after['peer']['receive']['source']
    need(right['droppedRecords']<=left['receiveSequence'])
    received=[row for row in right['records'] if row['receiveSequence']>left['receiveSequence'] and row['carriesJoints']]
    need(len(received)>=2)
    neutral_suffix=[]
    for row in received:
        need(row['avatarSha256']==primary['selfSha256'] and row['mixerSha256']==actor['avatarMixerSha256'] and row['advertisedModelUrl']==new['resourceUrl']
            and row['jointCount']==neutral['totalJoints']==restored['totalJoints']
            and abs(row['targetScale']-new['modelScale'])<.0001
            and cut['nativeAfter']['capturedEpochMs']<=row['capturedEpochMs']<=after['peer']['receive']['capturedEpochMs'])
        mapped={joint['index']:joint for joint in row['joints']}
        matches=True
        for index,pose in enumerate(neutral['joints']):
            need(index in mapped and mapped[index]['rotation'] is not None and mapped[index]['translation'] is not None)
            joint=mapped[index];rotation=joint['rotation'];translation=joint['translation']
            matches=matches and min(sum((a-b)**2 for a,b in zip(rotation,pose[:4])),sum((a+b)**2 for a,b in zip(rotation,pose[:4])))<=1e-6
            matches=matches and sum((a-b)**2 for a,b in zip(translation,pose[4:]))<=1e-6
        # A real receive cut may first deliver pre-restore queued frames. Only
        # the contiguous original neutral tail supplies the restoration fact.
        if matches:neutral_suffix.append(row)
        else:neutral_suffix=[]
    need(len(neutral_suffix)>=2)
    return dict(kind='original-restored-peer-continuation',receivedSequences=[row['receiveSequence'] for row in neutral_suffix],
        baseline=deepcopy(neutral),restored=deepcopy(restored),acquisition=deepcopy(last))
