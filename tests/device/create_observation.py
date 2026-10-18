"""Closed normal Create inputs and actual read-only entity observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit

PREFIX = 'OVERTE_E2E_CREATE_'
NAME = re.compile(PREFIX + r'([0-9a-f]{32})_(cube|import-parent|import-child)')
URL_PATH = re.compile(r'/create/([0-9a-f]{32})/(observer\.js|entities\.json|missing\.json)')
OPERATIONS = {'create.reference.open', 'create.reference.close', 'create.cube',
              'create.update', 'create.undo', 'create.redo', 'create.delete', 'create.import'}


def owned_url(value, kind):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError('Owned Create fixture URL must be a bounded string')
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError:
        raise ValueError('Owned Create fixture port is invalid') from None
    match = URL_PATH.fullmatch(parsed.path)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or match is None or match[2] not in kind):
        raise ValueError('Owned Create fixture requires its exact session resource URL')
    return match[1]


def properties(value):
    if not isinstance(value, dict) or set(value) != {'color', 'dimensions'}:
        raise ValueError('Create properties must contain only color and dimensions')
    color, dimensions = value['color'], value['dimensions']
    if (not isinstance(color, dict) or set(color) != {'red', 'green', 'blue'}
            or any(type(v) is not int or not 0 <= v <= 255 for v in color.values())):
        raise ValueError('Create color requires actual integer RGB channels')
    if (not isinstance(dimensions, dict) or set(dimensions) != {'x', 'y', 'z'}
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0.01 <= v <= 10
                   for v in dimensions.values())):
        raise ValueError('Create dimensions exceed the owned test range')
    return value


def action_arguments(operation, value):
    fields = ({'scriptUrl'} if operation in {'create.reference.open', 'create.reference.close'}
              else {'name', 'properties'} if operation in {'create.cube', 'create.update'}
              else {'names'} if operation == 'create.delete'
              else {'url'} if operation == 'create.import' else set())
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Create action contains unsupported or missing fields')
    if 'scriptUrl' in fields:
        owned_url(value['scriptUrl'], {'observer.js'})
    if 'url' in fields:
        owned_url(value['url'], {'entities.json', 'missing.json'})
    if 'name' in fields:
        if not isinstance(value['name'], str) or NAME.fullmatch(value['name']) is None:
            raise ValueError('Create action requires a unique owned entity name')
        properties(value['properties'])
    if 'names' in fields:
        names = value['names']
        if (not isinstance(names, list) or not 1 <= len(names) <= 3
                or not all(isinstance(name, str) and NAME.fullmatch(name) for name in names)
                or len(set(names)) != len(names)
                or len({NAME.fullmatch(name)[1] for name in names}) != 1):
            raise ValueError('Create delete must target only unique names from one owned session')
    return value


def entity_rows(value, nonce):
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError('Create observation entity count exceeds its bound')
    known_ids, previous = set(), None
    for row in value:
        fields = {'id', 'name', 'type', 'shape', 'dimensions', 'color', 'host',
                  'ownedByCurrentAvatar', 'parentId', 'hasExternalParent'}
        if (not isinstance(row, dict) or set(row) != fields
                or not isinstance(row['id'], str) or re.fullmatch('[0-9a-f]{32}', row['id']) is None
                or row['id'] in known_ids
                or not isinstance(row['name'], str) or NAME.fullmatch(row['name']) is None
                or NAME.fullmatch(row['name'])[1] != nonce):
            raise ValueError('Create observation contains foreign, duplicate or malformed entity identities')
        order = row['name'], row['id']
        if previous is not None and order <= previous:
            raise ValueError('Create entity observations must preserve stable sorted order')
        previous = order
        known_ids.add(row['id'])
        if (not isinstance(row['type'], str) or not isinstance(row['shape'], str)
                or not isinstance(row['host'], str)
                or row['host'] not in {'avatar', 'domain', 'local'}
                or not isinstance(row['ownedByCurrentAvatar'], bool)
                or not isinstance(row['hasExternalParent'], bool)
                or row['parentId'] is not None and (not isinstance(row['parentId'], str)
                    or re.fullmatch('[0-9a-f]{32}', row['parentId']) is None)):
            raise ValueError('Create observation entity type or ownership data is invalid')
        # Observe actual values even when the product ignored a requested edit.
        color, dimensions = row['color'], row['dimensions']
        if (not isinstance(color, dict) or set(color) != {'red', 'green', 'blue'}
                or any(type(v) is not int or not 0 <= v <= 255 for v in color.values())
                or not isinstance(dimensions, dict) or set(dimensions) != {'x', 'y', 'z'}
                or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                       for v in dimensions.values())):
            raise ValueError('Create observation has malformed actual color or dimensions')
    if any(row['parentId'] is not None and row['parentId'] not in known_ids for row in value):
        raise ValueError('Create observation disclosed an unrelated parent identity')
    return value


class FreshCreate:
    def __init__(self, nonce):
        self.nonce = nonce
        self.source_sha256 = hashlib.sha256((Path(__file__).resolve().parent
            / 'fixture/create_management/observer.js').read_bytes()).hexdigest()
        self.previous = None
        self.last_frame = None

    def accept(self, value):
        fields = {'schemaVersion', 'nonce', 'sourceSha256', 'sampleSequence',
                  'sampleMonotonicSeconds', 'sourceGets', 'importGets', 'missingGets', 'frame'}
        if (not isinstance(value, dict) or set(value) != fields
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['nonce'] != self.nonce or value['sourceSha256'] != self.source_sha256):
            raise ValueError('Create observer source or session identity differs')
        for field in ('sampleSequence', 'sourceGets', 'importGets', 'missingGets'):
            if type(value[field]) is not int or value[field] < (1 if field == 'sampleSequence' else 0):
                raise ValueError('Create observation counter is invalid')
        captured = value['sampleMonotonicSeconds']
        if type(captured) not in (int, float) or not math.isfinite(captured):
            raise ValueError('Create observer capture clock is invalid')
        if self.previous is not None:
            previous = self.previous
            if (value['sampleSequence'] <= previous['sampleSequence']
                    or captured < previous['sampleMonotonicSeconds']
                    or any(value[field] < previous[field] for field in ('sourceGets', 'importGets', 'missingGets'))):
                raise ValueError('Create observer replayed or rewrote its history')
        frame = value['frame']
        is_new = False
        if frame is not None:
            expected = {'instance', 'sequence', 'complete', 'error', 'queriedEntityCount',
                        'entities', 'receivedMonotonicSeconds'}
            if (not isinstance(frame, dict) or set(frame) != expected
                    or not isinstance(frame['instance'], str) or re.fullmatch('[0-9a-f]{32}', frame['instance']) is None
                    or type(frame['sequence']) is not int or frame['sequence'] < 0
                    or type(frame['complete']) is not bool
                    or type(frame['queriedEntityCount']) is not int or not 0 <= frame['queriedEntityCount'] <= 4096
                    or type(frame['receivedMonotonicSeconds']) not in (int, float)
                    or not math.isfinite(frame['receivedMonotonicSeconds'])
                    or frame['receivedMonotonicSeconds'] > captured):
                raise ValueError('Create native frame is malformed')
            if frame['complete'] is not True or frame['error'] != '':
                raise ValueError('Create native observation is incomplete; it cannot prove absence')
            entity_rows(frame['entities'], self.nonce)
            previous = self.last_frame
            if previous is not None:
                if (frame['instance'] != previous['instance']
                        or frame['sequence'] < previous['sequence']
                        or frame['sequence'] == previous['sequence'] and frame != previous
                        or frame['sequence'] > previous['sequence']
                            and frame['receivedMonotonicSeconds'] <= previous['receivedMonotonicSeconds']):
                    raise ValueError('Create native observer restarted, replayed or changed an earlier frame')
            is_new = previous is None or frame['sequence'] > previous['sequence']
            self.last_frame = frame
        elif self.last_frame is not None:
            raise ValueError('Create native frame history disappeared')
        self.previous = value
        return value, is_new
