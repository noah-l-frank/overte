"""Create-only extension of the original Qt token grammar.

The JSON browser and Save browser keep different source roles. Script picker
admission is unchanged. Fields and choices use the normal focused IME/key path.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import unquote, urlsplit

from adapters import token_create_ui as base
from adapters.native_feature_observation import exact, integer, need

VERSION = 2
CHOICES = {'create.voxel.mode': 2, 'create.voxel.shape': 3,
           'create.voxel.dynamics': 2, 'create.voxel.pointer': 2, 'create.detailed-type': 6,
           'create.polyvox.texturePreset': 6, 'create.polyvox.surfaceStyle': 4, 'create.polyvox.initialShape': 4}
FIELDS = frozenset(('create.voxel.diameter', 'create.voxel.reach',
                    'create.property-search',
                    'create.import.folder', 'create.import.filename',
                    'create.export.folder', 'create.export.filename', 'create.polyvox.volumeSizeX',
                    'create.polyvox.volumeSizeY', 'create.polyvox.volumeSizeZ', 'create.polyvox.xTextureURL',
                    'create.polyvox.yTextureURL', 'create.polyvox.zTextureURL'))
BUTTONS = frozenset(('create.voxel.remove', 'create.voxel.apply',
                     'create.import.cancel', 'create.import.accept',
                     'create.export.cancel', 'create.export.accept', 'create.detailed-open',
                     'create.polyvox.accept', 'create.polyvox.cancel'))


def control_id(identifier):
    return base.control_id(identifier) or type(identifier) is str and identifier in FIELDS | BUTTONS | CHOICES.keys()


def field(identifier):
    return base.field(identifier) or identifier in FIELDS


def choice(identifier):
    return base.choice(identifier) or identifier in CHOICES


def owned_path(value, run):
    """Only an owned Create root or its exact input/output file is writable."""
    need(type(run) is str and re.fullmatch('[0-9a-f]{32}', run))
    base.ascii_text(value)
    need(re.fullmatch(r'/(?:[^/\x00-\x1f]+/)*feature-create-' + run +
                      r'(?:/(?:entity-import|export)\.json)?', value)
         and not any(part in ('.', '..') for part in value.split('/')))
    return value


def local_url(value):
    need(type(value) is str and len(value) <= 4096)
    parsed = urlsplit(value)
    need(parsed.scheme == 'file' and not parsed.netloc and not parsed.query and not parsed.fragment)
    path = unquote(parsed.path)
    need(path.startswith('/') and not any(part in ('.', '..') for part in path.split('/')))
    return path


def picker(value, role):
    exact(value, {'role', 'rootId', 'componentSource', 'caption', 'filter', 'saveDialog',
                  'bundleMode', 'selectDirectory', 'directory', 'closing', 'requestId', 'error'})
    need(role in ('import', 'export') and value['role'] == role and base.nonce(value['rootId'])
         and type(value['componentSource']) is str
         and value['componentSource'].endswith('/dialogs/NativeFileBrowser.qml')
         and urlsplit(value['componentSource']).scheme in ('file', 'qrc')
         and value['caption'] == ('Select .json to Import' if role == 'import' else 'Select Where to Save')
         and value['filter'] == '*.json' and type(value['saveDialog']) is bool
         and value['saveDialog'] == (role == 'export')
         and value['bundleMode'] is False and value['selectDirectory'] is False
         and type(value['closing']) is bool and type(value['requestId']) is str
         and len(value['requestId']) <= 4096 and type(value['error']) is str and len(value['error']) <= 8192)
    local_url(value['directory'])
    return value


def metadata(row):
    identifier = row.get('id') if type(row) is dict else None
    if base.control_id(identifier):
        return base.metadata(row)
    need(control_id(identifier) and base.nonce(row.get('token'))
         and all(type(row.get(key)) is bool for key in ('enabled', 'focused', 'inputReady')))
    fields = {'id', 'token', 'enabled', 'focused', 'inputReady'}
    if identifier in FIELDS:
        fields.add('text'); base.ascii_text(row.get('text'))
    if identifier in CHOICES:
        fields |= {'count', 'currentIndex'}
        need(type(row.get('count')) is int and row['count'] == CHOICES[identifier]
             and integer(row.get('currentIndex'), 0, row['count']-1))
    if identifier == 'create.voxel.remove':
        fields.add('checked'); need(type(row.get('checked')) is bool)
    if identifier.startswith(('create.import.', 'create.export.')):
        fields.add('picker'); picker(row.get('picker'), identifier.split('.')[1])
    if identifier.startswith('create.polyvox.'):
        fields |= {'dialogRootId', 'dialogSource'}
        need(base.nonce(row.get('dialogRootId')) and type(row.get('dialogSource')) is str
             and row['dialogSource'].endswith('/system/create/qml/NewPolyVoxDialog.qml')
             and urlsplit(row['dialogSource']).scheme in ('file', 'qrc'))
    exact(row, fields)
    return row


def snapshot(value):
    exact(value, {'createControlsVersion', 'open', 'ready', 'scope', 'controls'})
    need(type(value['createControlsVersion']) is int and value['createControlsVersion'] in (1, VERSION)
         and all(type(value[key]) is bool for key in ('open', 'ready'))
         and type(value['controls']) is list and len(value['controls']) <= 384)
    base.scope(value['scope']); ids = set(); tokens = set()
    for row in value['controls']:
        metadata(row)
        need(row['id'] not in ids and row['token'] not in tokens
             and (value['createControlsVersion'] == VERSION or base.control_id(row['id'])))
        ids.add(row['id']); tokens.add(row['token'])
    need(value['open'] or not value['controls'])
    return value


def same_reference(original, current, identifier):
    snapshot(original); snapshot(current)
    need(all(original['scope'][key] == current['scope'][key]
             for key in ('instance', 'generation', 'sequence', 'processId'))
         and original['createControlsVersion'] == current['createControlsVersion']
         and 0 <= current['scope']['elapsedMs']-original['scope']['elapsedMs'] <= 5000)
    old = [row for row in original['controls'] if row['id'] == identifier]
    new = [row for row in current['controls'] if row['id'] == identifier]
    need(len(old) == len(new) == 1 and old[0] == new[0])
    return old[0]


def project(original):
    need(type(original.get('createControlsVersion')) is int and original['createControlsVersion'] in (1, VERSION))
    rows = deepcopy([row for row in original['controls'] if control_id(row['id'])])
    for row in rows:
        row.pop('frame')
    return snapshot(dict(createControlsVersion=original['createControlsVersion'], open=original['tabletShown'],
        ready=original['ready'], scope=dict(instance=original['instance'], generation=original['createGeneration'],
        sequence=original['lastSequence'], elapsedMs=original['elapsedMs'], processId=original['processId']), controls=rows))
