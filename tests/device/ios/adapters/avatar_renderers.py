"""Actual self/remote renderer and full avatar attachment inventory originals.

Receiver packet/joint provenance, normal input ownership and current rendered
pixels are mandatory separate joins; these reads cannot act as a peer verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re

from adapters.native_feature_observation import exact, fresh, integer, need, number
from ios.adapters.avatar_state import identity, session, text
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.scene_inventory import tree, uint64

VERSION = 4
READS = (1, 2, 3, 4)
ACTION = 'feature-ios-avatar-renderers'
FILE = ACTION+'.json'
LIMIT = 262144
SELF = '00000000-0000-0000-0000-000000000001'


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['action'] == ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}', value['commandId'])
         and identity(value['runId']))
    return value


def validate(value, query, pid, epoch=None, previous=None):
    command(query)
    exact(value, {'iosAvatarRenderersVersion', 'requestId', 'runId', 'instance', 'sequence', 'processId',
                  'clockDomain', 'clockBefore', 'clockAfter', 'source'})
    version = value['iosAvatarRenderersVersion']
    need(type(version) is int and version in READS
         and value['requestId'] == query['commandId'] and value['runId'] == query['runId']
         and integer(pid, 1) and type(value['processId']) is int and value['processId'] == pid
         and identity(value['instance']) and integer(value['sequence'], 1, 1000000000)
         and value['clockDomain'] == 'native-main-avatar-renderers')
    before, after = value['clockBefore'], value['clockAfter']
    for clock in (before, after):
        exact(clock, {'epochMs', 'monotonicMs'})
        need(integer(clock['epochMs'], 1) and integer(clock['monotonicMs'], 0))
    utc, mono = after['epochMs']-before['epochMs'], after['monotonicMs']-before['monotonicMs']
    need(0 <= utc < 1500 and 0 <= mono < 1500 and abs(utc-mono) <= 250)
    if epoch is not None: fresh(after['epochMs'], epoch)
    source = value['source']; exact(source, {'complete', 'avatars', 'avatarEntities', 'tree'})
    need(type(source['complete']) is bool and type(source['avatars']) is list and len(source['avatars']) <= 64
         and type(source['avatarEntities']) is list and len(source['avatarEntities']) <= 512)
    original_tree = tree(source['tree']); ids = []; self_count = 0
    for row in source['avatars']:
        exact(row, {'sessionId', 'self', 'replicated', 'requestedUrl', 'resourceUrl', 'geometryLoaded',
                    'rigReady', 'shouldRender', 'addedToScene', 'targetScale', 'modelScale', 'jointNames', 'hipsIndex', 'rigPose'}
              | ({'jointIndices'} if version >= 2 else set()) | ({'externalPose'} if version >= 3 else set())
              | ({'boundsReady', 'bounds'} if version >= 4 else set()))
        session(row['sessionId']); ids.append(row['sessionId'])
        for key in ('self', 'replicated', 'geometryLoaded', 'rigReady', 'shouldRender', 'addedToScene'):
            need(type(row[key]) is bool)
        self_count += row['self']
        for key in ('requestedUrl', 'resourceUrl'): text(row[key])
        for key in ('targetScale', 'modelScale'): need(number(row[key], .0001, 1000))
        names = row['jointNames']; need(type(names) is list and len(names) <= 1024)
        for name in names: text(name, 256)
        need(len(set(names)) == len(names) and integer(row['hipsIndex'], -1, 65535))
        if version >= 2:
            need(type(row['jointIndices']) is dict and set(row['jointIndices']) == set(names))
            for index in row['jointIndices'].values(): need(integer(index, 0, 65535))
            need(len(set(row['jointIndices'].values())) == len(names)
                 and row['hipsIndex'] == row['jointIndices'].get('Hips', -1))
        need(not row['rigReady'] or row['geometryLoaded'] and names)
        if version >= 4:
            need(type(row['boundsReady']) is bool)
            if row['boundsReady']:
                exact(row['bounds'], {'corner', 'dimensions'}); need(row['geometryLoaded'])
                for key in ('corner', 'dimensions'):
                    need(type(row['bounds'][key]) is list and len(row['bounds'][key]) == 3
                         and all(number(item) for item in row['bounds'][key]))
                need(all(item > 0 for item in row['bounds']['dimensions']))
            else: need(row['bounds'] is None)
        pose = row['rigPose']
        if pose is not None:
            exact(pose, {'rigId', 'capturedEpochMs', 'evaluationSequence', 'animationsEnabled', 'graphLoaded',
                         'overrideActive', 'joints'})
            need(integer(pose['rigId'], 0) and integer(pose['capturedEpochMs'], 1, after['epochMs'])
                 and integer(pose['evaluationSequence'], 0) and type(pose['joints']) is list and len(pose['joints']) <= 256)
            for key in ('animationsEnabled', 'graphLoaded', 'overrideActive'): need(type(pose[key]) is bool)
            for joint in pose['joints']:
                need(type(joint) is list and len(joint) == 7 and all(number(item) for item in joint)
                     and .9 <= sum(item*item for item in joint[:4]) <= 1.1)
        external_pose = row.get('externalPose')
        if external_pose is not None:
            exact(external_pose, {'externalPoseVersion', 'instance', 'rigId', 'capturedEpochMs',
                                  'evaluationSequence', 'totalJoints', 'joints'})
            need(type(external_pose['externalPoseVersion']) is int and external_pose['externalPoseVersion'] == 1
                 and identity(external_pose['instance']) and integer(external_pose['rigId'], 1)
                 and integer(external_pose['capturedEpochMs'], 1, after['epochMs'])
                 and integer(external_pose['evaluationSequence'], 1, 1000000000)
                 and integer(external_pose['totalJoints'], 0, 256) and type(external_pose['joints']) is list
                 and len(external_pose['joints']) == external_pose['totalJoints'])
            for joint in external_pose['joints']:
                need(type(joint) is list and len(joint) == 7 and all(number(item) for item in joint)
                     and .9 <= sum(item*item for item in joint[:4]) <= 1.1)
    need(ids == sorted(ids) and len(set(ids)) == len(ids) and self_count <= 1)
    entity_ids = []
    inventory = {row['id']: row for row in original_tree['entities'] if row['hostType'] == 'avatar'}
    for row in source['avatarEntities']:
        exact(row, {'id', 'name', 'type', 'parentId', 'parentJointIndex', 'relayParentJoints', 'visible',
                    'modelUrl', 'resourceUrl', 'modelAvailable', 'geometryLoaded', 'addedToScene',
                    'loadFailed', 'lastEditedEpochUs'})
        session(row['id']); entity_ids.append(row['id'])
        need(type(row['parentId']) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', row['parentId']))
        text(row['name'], 256); text(row['type'], 64)
        for key in ('modelUrl', 'resourceUrl'): text(row[key])
        need(integer(row['parentJointIndex'], -1, 65535)); uint64(row['lastEditedEpochUs'])
        for key in ('relayParentJoints', 'visible', 'modelAvailable', 'geometryLoaded', 'addedToScene', 'loadFailed'):
            need(type(row[key]) is bool)
        need(row['modelAvailable'] or not any(row[key] for key in ('geometryLoaded', 'addedToScene', 'loadFailed'))
             and row['resourceUrl'] == '')
        need(row['id'] in inventory and row['lastEditedEpochUs'] == inventory[row['id']]['lastEditedEpochUs'])
    need(entity_ids == sorted(entity_ids) and len(set(entity_ids)) == len(entity_ids))
    if source['complete']:
        need(original_tree['complete'] and set(entity_ids) == set(inventory) and self_count == 1)
    need(len(json.dumps(value, allow_nan=False).encode()) <= LIMIT)
    if previous is not None:
        validate(previous, dict(query, commandId=previous['requestId']), pid)
        need(version >= previous['iosAvatarRenderersVersion']
             and value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
             and value['requestId'] != previous['requestId'] and value['runId'] == previous['runId']
             and before['epochMs'] >= previous['clockAfter']['epochMs']
             and before['monotonicMs'] >= previous['clockAfter']['monotonicMs'])
        old = previous['source']['tree']
        need(original_tree['treeInstance'] == old['treeInstance']
             and original_tree['revisionBefore'] >= old['revisionAfter'])
        if original_tree['revisionBefore'] == old['revisionAfter']:
            need(original_tree == old)
        old_self = [row['sessionId'] for row in previous['source']['avatars'] if row['self']]
        need(old_self == [row['sessionId'] for row in source['avatars'] if row['self']])
        old_avatars = {row['sessionId']: row for row in previous['source']['avatars']}
        for row in source['avatars']:
            old_row = old_avatars.get(row['sessionId'])
            if old_row is None: continue
            if old_row['requestedUrl'] == row['requestedUrl'] and old_row['resourceUrl'] == row['resourceUrl']:
                old_external, external = old_row.get('externalPose'), row.get('externalPose')
                if old_external is not None:
                    need(external is not None and external['instance'] == old_external['instance']
                         and external['rigId'] == old_external['rigId']
                         and external['evaluationSequence'] >= old_external['evaluationSequence']
                         and external['capturedEpochMs'] >= old_external['capturedEpochMs'])
                    if external['evaluationSequence'] == old_external['evaluationSequence']: need(external == old_external)
            old_pose, pose = old_row['rigPose'], row['rigPose']
            if old_pose is None: continue
            if old_row['requestedUrl'] != row['requestedUrl'] or old_row['resourceUrl'] != row['resourceUrl']: continue
            need(pose is not None and pose['rigId'] == old_pose['rigId']
                 and pose['evaluationSequence'] >= old_pose['evaluationSequence']
                 and pose['capturedEpochMs'] >= old_pose['capturedEpochMs'])
            if pose['evaluationSequence'] == old_pose['evaluationSequence']: need(pose == old_pose)
    return value


def original(value):
    return validate(value, dict(schemaVersion=1, commandId=value['requestId'], action=ACTION, runId=value['runId']),
                    value['processId'])


def avatar(value, avatar_id, *, remote=False):
    original(value); session(avatar_id)
    need(type(remote) is bool and value['source']['complete'] and value['iosAvatarRenderersVersion'] >= 2)
    if remote: need(value['iosAvatarRenderersVersion'] >= 4)
    rows = [row for row in value['source']['avatars'] if row['sessionId'] == avatar_id]
    need(len(rows) == 1 and rows[0]['self'] is (not remote) and not rows[0]['replicated'])
    return deepcopy(rows[0])


def loaded(value, avatar_id, resource, scale, *, remote=False):
    row = avatar(value, avatar_id, remote=remote); text(resource); need(resource and number(scale, .0001, 1000))
    need(row['requestedUrl'] == row['resourceUrl'] == resource and row['geometryLoaded'] and row['rigReady']
         and row['addedToScene'] and row['shouldRender'] and abs(row['targetScale']-scale) < .0001
         and abs(row['modelScale']-scale) < .0001)
    return row


def wearable(value, entity_id, avatar_id, resource, *, remote=False):
    row = avatar(value, avatar_id, remote=remote); session(entity_id); text(resource); need(resource)
    entities = [item for item in value['source']['avatarEntities'] if item['id'] == entity_id]
    need(len(entities) <= 1)
    if not entities: return False
    entity = entities[0]
    need(entity['type'] == 'Model' and entity['parentId'] in ({avatar_id} if remote else {avatar_id, SELF})
         and row['hipsIndex'] >= 0 and entity['parentJointIndex'] == row['hipsIndex']
         and not entity['relayParentJoints'] and entity['visible'] and entity['modelAvailable']
         and entity['geometryLoaded'] and entity['addedToScene'] and not entity['loadFailed']
         and entity['modelUrl'] == entity['resourceUrl'] == resource)
    return True


def evaluated(value, avatar_id, *, after_epoch, remote=False):
    """Fresh local animation evaluation; remote external-pose source is separate."""
    need(remote is False)
    row = avatar(value, avatar_id, remote=remote); pose = row['rigPose']
    need(integer(after_epoch, 1) and pose is not None and row['geometryLoaded'] and row['rigReady']
         and row['addedToScene'] and row['shouldRender'] and pose['graphLoaded'] and pose['animationsEnabled']
         and pose['evaluationSequence'] > 0 and pose['joints']
         and after_epoch <= pose['capturedEpochMs'] <= value['clockAfter']['epochMs']
         and value['clockAfter']['epochMs']-pose['capturedEpochMs'] < 1500)
    return deepcopy(pose)


def external(value, avatar_id, *, after_epoch):
    """Remote renderer-facing received joints after real computeExternalPoses."""
    row = avatar(value, avatar_id, remote=True)
    need(value['iosAvatarRenderersVersion'] >= 4)
    pose = row['externalPose']
    need(integer(after_epoch, 1) and pose is not None and row['geometryLoaded'] and row['rigReady']
         and row['addedToScene'] and row['shouldRender'] and pose['joints']
         and after_epoch <= pose['capturedEpochMs'] <= value['clockAfter']['epochMs']
         and value['clockAfter']['epochMs']-pose['capturedEpochMs'] < 1500)
    return deepcopy(pose)


def bounds(value, avatar_id, *, remote=False):
    """Actual render mesh AABB; never Avatar::getBounds' requested-scale fallback."""
    row = avatar(value, avatar_id, remote=remote)
    need(value['iosAvatarRenderersVersion'] >= 4 and row['boundsReady'] and row['geometryLoaded']
         and row['rigReady'] and row['addedToScene'] and row['shouldRender'])
    return deepcopy(row['bounds'])


def preserve_unowned(before, after, owned_ids):
    """Actual complete ID/hash maps, including hidden/detached avatar entities."""
    for value in (before, after): original(value); need(value['source']['complete'])
    need(type(owned_ids) is set)
    for value in owned_ids: session(value)
    maps = []
    for value in (before, after):
        maps.append({row['id']: row for row in value['source']['tree']['entities']
                     if row['hostType'] == 'avatar' and row['id'] not in owned_ids})
    need(maps[0] == maps[1])
    return deepcopy(maps[1])


class IOSAvatarRenderers(IOSPlacesModel):
    _action = ACTION
    _command = staticmethod(command)
    _validate = staticmethod(validate)
    _acquisition_key = 'iosAvatarRenderersAcquisitionVersion'
