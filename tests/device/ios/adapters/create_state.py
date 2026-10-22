"""Passive whole-tree Create originals, with renderer-consumed texture bytes.

This source has no expected entity IDs, names, requested properties or writes.
An input result or a matching property string cannot become a rendered effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import re

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.native_graphics_subject import entity_id, vector
from adapters.script_feature.history import same
from ios.adapters import create_controls_v2 as controls
from ios.adapters.places_model import IOSPlacesModel, tree as json_tree
from ios.adapters.scene_inventory import tree, uint64

VERSION = 1
ACTION = 'feature-ios-create-state'
FILE = ACTION+'.json'
LIMIT = 262144
SHA = '[a-f0-9]{64}'


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['action'] == ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}', value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}', value['runId']))
    return value


def uuid(value):
    need(type(value) is str and re.fullmatch(controls.base.UUID, value)); return value


def text(value, maximum=4096):
    need(type(value) is str and len(value) <= maximum); value.encode('utf-8'); return value


def texture_original(value, url, epoch):
    exact(value, {'textureOriginalVersion', 'instance', 'url', 'complete', 'consumptions'})
    need(type(value['textureOriginalVersion']) is int and value['textureOriginalVersion'] == 1
         and re.fullmatch('[a-f0-9]{32}', text(value['instance'], 32)) and value['url'] == url
         and type(value['complete']) is bool and type(value['consumptions']) is list and len(value['consumptions']) <= 16)
    previous = 0
    for index, row in enumerate(value['consumptions']):
        exact(row, {'sequence', 'consumedEpochMs', 'bytes', 'sha256', 'base64'})
        need(type(row['sequence']) is int and row['sequence'] == index+1
             and integer(row['consumedEpochMs'], previous, epoch) and integer(row['bytes'], 1, 8192)
             and re.fullmatch(SHA, text(row['sha256'], 64)) and type(row['base64']) is str and len(row['base64']) <= 10924)
        raw = base64.b64decode(row['base64'], validate=True)
        need(base64.b64encode(raw).decode() == row['base64'] and len(raw) == row['bytes']
             and hashlib.sha256(raw).hexdigest() == row['sha256'])
        previous = row['consumedEpochMs']
    return value


def entity(row, original, epoch):
    exact(row, {'id', 'name', 'type', 'hostType', 'dimensions', 'modelURL', 'textures', 'lastEditedBy',
                'createdEpochUs', 'lastEditedEpochUs', 'shape', 'locked', 'visible', 'model', 'voxels'})
    need(entity_id(row['id']) and row['id'] == original['id'] and row['hostType'] == original['hostType']
         and type(row['locked']) is bool and type(row['visible']) is bool)
    for key in ('createdEpochUs', 'lastEditedEpochUs'):
        uint64(row[key]); need(row[key] == original[key])
    for key, bound in (('name', 256), ('type', 64), ('shape', 64), ('modelURL', 4096), ('textures', 8192)): text(row[key], bound)
    uuid(row['lastEditedBy']); vector(row['dimensions'], 3, .000001, 1000000)
    if row['type'] == 'Model':
        model = row['model']; exact(model, {'present', 'loaded', 'addedToScene', 'failed', 'textures'})
        need(all(type(model[key]) is bool for key in ('present', 'loaded', 'addedToScene', 'failed'))
             and (model['present'] or not any(model[key] for key in ('loaded', 'addedToScene', 'failed')))
             and type(model['textures']) is list and len(model['textures']) <= 128)
        seen = set()
        for entry in model['textures']:
            exact(entry, {'material', 'channel', 'slot', 'url', 'loaded', 'original'})
            need(integer(entry['material'], 0, 1024) and integer(entry['channel'], 0, 1024)
                 and (entry['material'], entry['channel']) not in seen and type(entry['loaded']) is bool)
            seen.add((entry['material'], entry['channel']))
            text(entry['slot'], 4096); text(entry['url'], 4096)
            texture_original(entry['original'], entry['url'], epoch)
        need(model['loaded'] or not model['textures'])
    else: need(row['model'] == {})
    if row['type'] == 'PolyVox':
        voxels = row['voxels']; exact(voxels, {'ready', 'bytes', 'sha256', 'volume', 'onCount'})
        need(type(voxels['ready']) is bool and integer(voxels['bytes'], 0, 2**31-1)
             and re.fullmatch(SHA, text(voxels['sha256'], 64)) and integer(voxels['onCount'], 0, 2**31-1))
        vector(voxels['volume'], 3, 1, 128)
    else: need(row['voxels'] == {})


def root(row):
    need(type(row) is dict and type(row.get('destroyed')) is bool); uuid(row['id'])
    if row['destroyed']: exact(row, {'id', 'destroyed'}); return
    need(row.get('kind') in ('editor', 'import', 'export')
         and all(type(row.get(key)) is bool for key in ('active', 'visible')) and (not row['active'] or row['visible']))
    fields = {'id', 'destroyed', 'kind', 'visible', 'active'}
    if row['kind'] == 'editor':
        exact(row, fields | {'page', 'changed', 'voxelSettings', 'numericFocus'})
        page = row['page']; exact(page, {'profile', 'tab', 'selectedIds', 'statusError', 'statusText', 'componentSourceSha256', 'inputReady'})
        need(page['inputReady'] is False)
        controls.base.metadata(dict(page, id='create.page', token=row['id'], enabled=True, focused=False))
        json_tree(row['changed']); json_tree(row['voxelSettings']); need(type(row['numericFocus']) is bool)
    else:
        exact(row, fields | {'picker'}); controls.picker(row['picker'], row['kind'])
        need(row['picker']['rootId'] == row['id'])


def validate(value, query, pid, epoch=None, previous=None):
    command(query)
    exact(value, {'iosCreateStateVersion', 'requestId', 'runId', 'instance', 'sequence', 'processId',
                  'clockDomain', 'clockBefore', 'clockAfter', 'source'})
    need(type(value['iosCreateStateVersion']) is int and value['iosCreateStateVersion'] == VERSION
         and value['requestId'] == query['commandId'] and value['runId'] == query['runId']
         and integer(pid, 1) and type(value['processId']) is int and value['processId'] == pid
         and re.fullmatch('[a-f0-9]{32}', text(value['instance'], 32)) and integer(value['sequence'], 1, 1000000000)
         and value['clockDomain'] == 'native-main-create')
    before, after = value['clockBefore'], value['clockAfter']
    for clock in (before, after):
        exact(clock, {'epochMs', 'monotonicMs'}); need(integer(clock['epochMs'], 1) and integer(clock['monotonicMs']))
    utc = after['epochMs']-before['epochMs']; mono = after['monotonicMs']-before['monotonicMs']
    need(0 <= utc < 1500 and 0 <= mono < 1500 and abs(utc-mono) <= 250)
    if epoch is not None: fresh(after['epochMs'], epoch)
    source = value['source']; exact(source, {'complete', 'tabletShown', 'domainId', 'canRez', 'canRezTmp', 'tree', 'entities', 'roots'})
    need(all(type(source[key]) is bool for key in ('complete', 'tabletShown', 'canRez', 'canRezTmp')))
    uuid(source['domainId']); tree(source['tree'])
    need(source['tree']['complete'] and type(source['entities']) is list
         and len(source['entities']) == len(source['tree']['entities']) and type(source['roots']) is list and len(source['roots']) <= 64)
    for row, original in zip(source['entities'], source['tree']['entities']): entity(row, original, after['epochMs'])
    ids = []
    for row in source['roots']: root(row); ids.append(row['id'])
    need(len(set(ids)) == len(ids) and sum(row.get('active', False) and row.get('kind') == 'editor' for row in source['roots']) <= 1)
    if previous is not None:
        validate(previous, dict(query, commandId=previous['requestId']), pid)
        old = previous['source']; need(value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
            and value['requestId'] != previous['requestId'] and source['domainId'] == old['domainId']
            and before['epochMs'] >= previous['clockAfter']['epochMs']
            and before['monotonicMs'] >= previous['clockAfter']['monotonicMs']
            and source['tree']['treeInstance'] == old['tree']['treeInstance']
            and source['tree']['revisionBefore'] >= old['tree']['revisionAfter']
            and ids[:len(old['roots'])] == [row['id'] for row in old['roots']])
        for first, last in zip(old['roots'], source['roots']):
            need(not first['destroyed'] or same(first, last))
    return value


def original(value):
    need(type(value) is dict)
    return validate(value, dict(schemaVersion=1, action=ACTION, commandId=value.get('requestId'), runId=value.get('runId')), value.get('processId'))


def live(value):
    original(value); need(value['source']['complete']); return deepcopy(value['source'])


class IOSCreateState(IOSPlacesModel):
    _action = ACTION
    _command = staticmethod(command)
    _validate = staticmethod(validate)
    _acquisition_key = 'iosCreateStateAcquisitionVersion'
