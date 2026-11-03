"""Original remote joint-section commits and actual Rig copy/build samples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.native_avatar_render import nonce
from adapters.native_graphics_subject import rotation, vector
from adapters.script_journey.history import same

VERSION = 1


def committed(value, kind, subject, count, before, epoch):
    exact(value, {'kind','sequence','subjectSessionId','jointCount','parsedEpochMs','committedEpochMs',
        'parseTimestampUs','bytes','sha256','base64'})
    need(value['kind'] == kind and integer(value['sequence'],1,9007199254740991)
         and value['subjectSessionId'] == subject and integer(value['jointCount'],1,256) and value['jointCount'] == count
         and integer(value['parsedEpochMs'],1,before) and integer(value['committedEpochMs'],value['parsedEpochMs'],before)
         and integer(value['parseTimestampUs'],1,9007199254740991) and integer(value['bytes'],1,8192)
         and type(value['base64']) is str and len(value['base64']) <= 10924)
    try: raw = base64.b64decode(value['base64'], validate=True)
    except ValueError: need(False)
    need(base64.b64encode(raw).decode() == value['base64'] and len(raw) == value['bytes']
         and hashlib.sha256(raw).hexdigest() == value['sha256'] and raw[0] == count)
    # Parse/commit belongs to the actual incoming joint section. A later local
    # recopy must not hide that section's original age under its own new clock.
    if kind == 'joint-data': fresh(value['parsedEpochMs'], epoch)
    return value


def validate(value, subject, epoch):
    exact(value, {'remoteJointPoseVersion','instance','copySequence','copiedSequence','externalSequence',
        'subjectSessionId','avatarInstance','modelInstance','geometryInstance','rigId','available','inputJointCount','skeletonJointCount',
        'begunEpochMs','copiedEpochMs','capturedEpochMs','relativeJoints','joints','received'})
    need(type(value['remoteJointPoseVersion']) is int and value['remoteJointPoseVersion'] == VERSION
         and nonce(value['instance']) and integer(value['copySequence'],1,9007199254740991)
         and type(value['copiedSequence']) is int and value['copiedSequence'] == value['copySequence']
         and type(value['externalSequence']) is int and value['externalSequence'] == value['copySequence']
         and value['subjectSessionId'] == subject['sessionId']
         and all(value[key] == subject[key] for key in ('avatarInstance','modelInstance','rigId'))
         and type(subject['geometry']) is dict and nonce(value['geometryInstance'])
         and value['geometryInstance'] == subject['geometry']['instance']
         and integer(value['rigId']) and value['available'] is True
         and integer(value['inputJointCount'],1,256) and type(value['skeletonJointCount']) is int
         and value['skeletonJointCount'] == value['inputJointCount']
         and integer(value['begunEpochMs'],1,epoch) and integer(value['copiedEpochMs'],value['begunEpochMs'],epoch)
         and integer(value['capturedEpochMs'],value['copiedEpochMs'],epoch))
    fresh(value['capturedEpochMs'], epoch)
    for field in ('relativeJoints','joints'):
        need(type(value[field]) is list and len(value[field]) == value['inputJointCount'])
        for joint in value[field]:
            vector(joint,7,-1e6,1e6); rotation(joint[:4])
    received = value['received']; exact(received, {'jointData','defaultFlags'})
    committed(received['jointData'],'joint-data',value['subjectSessionId'],value['inputJointCount'],value['begunEpochMs'],epoch)
    if received['defaultFlags'] is not None:
        committed(received['defaultFlags'],'default-flags',value['subjectSessionId'],value['inputJointCount'],value['begunEpochMs'],epoch)
    return value


def continuity(before, after):
    need(all(same(before[key],after[key]) for key in
        ('instance','subjectSessionId','avatarInstance','modelInstance','rigId'))
         and after['copySequence'] >= before['copySequence'] and after['capturedEpochMs'] >= before['capturedEpochMs'])
    if after['copySequence'] == before['copySequence']: need(same(before,after))
    for key in ('jointData','defaultFlags'):
        a,b = before['received'][key],after['received'][key]
        if a is None: continue
        need(b is not None and b['sequence'] >= a['sequence'] and b['parsedEpochMs'] >= a['parsedEpochMs']
             and b['committedEpochMs'] >= a['committedEpochMs'])
        if b['sequence'] == a['sequence']: need(same(a,b))


def changed(before, after):
    """Measured copied pose difference only; no local clip/Emote cause label."""
    continuity(before,after)
    fresh_sections=[]
    for key in ('jointData','defaultFlags'):
        a,b=before['received'][key],after['received'][key]
        if b is not None and (a is None or b['sequence']>a['sequence']) and b['parsedEpochMs']>=before['capturedEpochMs']:
            fresh_sections.append(b['kind'])
    need(after['copySequence'] > before['copySequence'] and bool(fresh_sections)
         and after['geometryInstance'] == before['geometryInstance'] and len(before['joints']) == len(after['joints']))
    def moving(a,b):
        orientation=min(max(abs(x-y) for x,y in zip(a[:4],b[:4])),max(abs(x+y) for x,y in zip(a[:4],b[:4])))
        return orientation > .001 or any(abs(x-y) > .001 for x,y in zip(a[4:],b[4:]))
    changed_joints = [index for index,(a,b) in enumerate(zip(before['joints'],after['joints'])) if moving(a,b)]
    need(bool(changed_joints))
    return dict(remoteJointPoseVersion=VERSION, copiedPoseChanged=True, changedJoints=changed_joints,newCommittedSections=fresh_sections,
        before=deepcopy(before),after=deepcopy(after))
