"""Derive common Create fields only from actual bound native originals.

Image/file/peer evidence remains separate. A consumed texture original and
settled voxel source are necessary observations, never a visual success ACK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json

from adapters.native_feature_observation import exact, need
from adapters.native_graphics_subject import entity_id
from feature_journeys.contract import json_document
from feature_journeys.fixtures import payload
from ios.adapters import create_state

PERMISSION_ERROR = 'Invalid entity type, properties or creation permission.'


def selected(source):
    pages = [row for row in source['roots'] if not row['destroyed'] and row['kind'] == 'editor' and row['active']]
    need(len(pages) <= 1)
    return [] if not pages else deepcopy(pages[0]['page']['selectedIds'])


def model_texture(row):
    """Actual slot remap + renderer-consumed exact original PNG bytes."""
    need(row['type'] == 'Model' and row['model']['loaded'] and row['model']['addedToScene'] and not row['model']['failed'])
    assignment = json_document(row['textures']) if row['textures'] else {}
    need(type(assignment) is dict)
    if not assignment: return False
    need(set(assignment) == {'checker.png'} and type(assignment['checker.png']) is str)
    matches = [entry for entry in row['model']['textures'] if entry['slot'] == 'checker.png']
    need(matches and all(entry['url'] == assignment['checker.png'] and entry['loaded']
         and entry['original']['complete'] and entry['original']['consumptions'] for entry in matches))
    original = payload('checker.png', '0'*32, '0'*32)[1]
    # These bytes are an assertion reference, compared to independently acquired
    # native consumed originals; they are never returned as product file data.
    need(all(base64.b64decode(entry['original']['consumptions'][-1]['base64'], validate=True) == original for entry in matches))
    return True


def project(value, run, owned_ids, *, voxel_baseline=None):
    source = create_state.live(value)
    need(value['runId'] == run and type(owned_ids) is list and len(set(owned_ids)) == len(owned_ids)
         and all(entity_id(id_) for id_ in owned_ids))
    rows = [row for row in source['entities'] if row['id'] in owned_ids]
    owned_names = {'model': 'e2e-'+run+'-model', 'cube': 'e2e-'+run+'-cube', 'voxel': 'e2e-'+run+'-voxel'}
    roles = {}
    for row in rows:
        role = 'model' if row['type'] == 'Model' else 'voxel' if row['type'] == 'PolyVox' else (
            'cube' if row['type'] in ('Shape', 'Box') and row['shape'] == 'Cube' else None)
        need(role is not None and role not in roles and row['name'] == owned_names[role]
             and row['hostType'] == 'domain' and not row['locked'] and row['visible'])
        if role == 'model':
            need(row['model']['loaded'] and row['model']['addedToScene'] and not row['model']['failed'])
        if role == 'voxel': need(row['voxels']['ready'])
        roles[role] = row
    selection = selected(source)
    need(set(selection) <= {row['id'] for row in rows})
    pages = [row for row in source['roots'] if not row['destroyed'] and row['kind'] == 'editor' and row['active']]
    error = 'none'
    if pages and pages[0]['page']['statusError']:
        need(pages[0]['page']['statusText'] == PERMISSION_ERROR); error = 'permission-denied'
    picker = any(not row['destroyed'] and row.get('active') and row['kind'] in ('import', 'export') for row in source['roots'])
    voxel = 0
    if 'voxel' in roles and voxel_baseline is not None:
        exact(voxel_baseline, {'id', 'source'})
        row = roles['voxel']; original = voxel_baseline['source']
        need(voxel_baseline['id'] == row['id'] and type(original) is dict and original.get('ready') is True)
        if row['voxels']['sha256'] != original['sha256']:
            need(row['voxels']['volume'] == original['volume'] and row['voxels']['onCount'] < original['onCount'])
            voxel = 1
    return dict(objects=sorted(roles), editor=bool(pages), picker=picker, error=error,
        canRez=source['canRez'] or source['canRezTmp'],
        selection=sorted(role for role, row in roles.items() if row['id'] in selection),
        textured=model_texture(roles['model']) if 'model' in roles else False, voxelValue=voxel)


def adopt_created(before, after, existing_owned, run, *, actor=None):
    """Record an actual newly selected UUID, never adopt a matching old name.

    This is ownership admission after one persisted normal creation input. It
    does not establish create success for the common journey: image and the
    independent actor still have to observe the same actual entity identity.
    """
    first, last = create_state.live(before), create_state.live(after)
    need(before['iosCreateStateVersion'] >= 2 and after['iosCreateStateVersion'] >= 2
         and before['runId'] == after['runId'] == run and before['processId'] == after['processId']
         and before['instance'] == after['instance'] and before['sequence'] < after['sequence']
         and first['domainId'] == last['domainId'] and first['tree']['treeInstance'] == last['tree']['treeInstance'])
    previous_ids = {row['id'] for row in first['entities']}
    added = [row for row in last['entities'] if row['id'] not in previous_ids]
    need(len(added) == 1 and selected(last) == [added[0]['id']] and added[0]['hostType'] == 'domain'
         and added[0]['id'] not in existing_owned and not added[0]['locked']
         and first['localSessionId'] == last['localSessionId'] == added[0]['lastEditedBy'])
    if actor is not None:
        peer = create_state.live(actor)
        matching = [row for row in peer['entities'] if row['id'] == added[0]['id']]
        need(actor['runId'] == run and peer['domainId'] == last['domainId'] and len(matching) == 1
             and matching[0]['hostType'] == 'domain' and matching[0]['type'] == added[0]['type'])
    return deepcopy(added[0])
