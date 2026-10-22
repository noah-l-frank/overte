"""Explicit original Create JSON/export role over the existing file transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import secrets
import uuid

from adapters.native_feature_observation import exact, integer, need
from adapters.native_script_files import NativeScriptFiles
from adapters.normal_feature_state import context
from adapters.token_script_file_ui import file_url
from feature_journeys.contract import identifier
from feature_journeys.fixtures import import_document

VERSION = 1
ROLE = 'create-json-v1'
FILE = 'feature-create-files.json'
NAMES = ('entity-import.json', 'export.json')


def input_bytes(run, ticket, fixture_url):
    return json.dumps(import_document(run, ticket, fixture_url), allow_nan=False,
        sort_keys=True, separators=(',', ':')).encode('utf-8')


def validate_command(value):
    need(type(value) is dict)
    operation = value.get('operation')
    exact(value, {'schemaVersion', 'commandId', 'action', 'sourceRole', 'operation', 'runId', 'ticket', 'ownerToken'}
        | ({'files'} if operation == 'stage' else {'exportSha256'} if operation == 'release' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == VERSION
         and value['action'] == 'feature-script-files' and value['sourceRole'] == ROLE
         and operation in ('stage', 'observe', 'locate', 'release')
         and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}', value['ownerToken']))
    for key in ('commandId', 'runId', 'ticket'):
        identifier(value[key])
    if operation == 'release':
        need(type(value['exportSha256']) is str and
            (value['exportSha256'] == '' or re.fullmatch('[0-9a-f]{64}', value['exportSha256'])))
    if operation == 'stage':
        exact(value['files'], {'entity-import.json'})
        raw = base64.b64decode(value['files']['entity-import.json'], validate=True)
        need(0 < len(raw) <= 8192 and base64.b64encode(raw).decode() == value['files']['entity-import.json'])
    need(len(json.dumps(value).encode()) <= 16384)
    return value


class NativeCreateFiles(NativeScriptFiles):
    def __init__(self, *args, ticket, **kwargs):
        identifier(ticket)
        super().__init__(*args, **kwargs)
        need(not self.ios)
        self.ticket, self.export_sha256 = ticket, None

    def prepare(self, operation, run, owner, files):
        value = dict(schemaVersion=VERSION, commandId=uuid.uuid4().hex, action='feature-script-files',
            sourceRole=ROLE, operation=operation, runId=run, ticket=self.ticket, ownerToken=owner)
        if files is not None:
            value['files'] = {key:base64.b64encode(raw).decode() for key,raw in files.items()}
        if operation == 'release':
            value['exportSha256'] = self.export_sha256
        return validate_command(value)

    def packet_fields(self):
        return super().packet_fields() | {'sourceRole', 'ticket'}

    def packet_scope(self, value):
        need(value['sourceRole'] == ROLE and value['ticket'] == self.ticket)

    def validate_source(self, value, operation, run):
        suffix = '/feature-create-' + run + '-' + self.ticket
        if operation == 'locate':
            exact(value, {'locationVersion', 'exists', 'directory'})
            need(type(value['locationVersion']) is int and value['locationVersion'] == VERSION
                 and type(value['exists']) is bool and file_url(value['directory']).endswith(suffix))
        elif operation != 'observe':
            exact(value, {'performed'})
            need(value['performed'] is True)
        else:
            need(type(value) is dict and type(value.get('exists')) is bool)
            exact(value, {'exists', 'files', 'directory'} if value['exists'] else {'exists', 'files'})
            need(type(value['files']) is list)
            if not value['exists']:
                need(value['files'] == [])
                return
            need(file_url(value['directory']).endswith(suffix) and len(value['files']) == 2)
            for name, row in zip(NAMES, value['files']):
                need(type(row) is dict and row.get('name') == name and type(row.get('exists')) is bool)
                exact(row, {'name', 'exists', 'bytes', 'sha256', 'base64', 'device', 'inode', 'mode', 'modified', 'changed'}
                    if row['exists'] else {'name', 'exists'})
                if not row['exists']:
                    continue
                need(integer(row['bytes'], 1, 32768 if name == 'export.json' else 8192)
                     and type(row['base64']) is str and len(row['base64']) <= 43692
                     and type(row['mode']) is int and row['mode'] in ((384,420) if name == 'export.json' else (384,)))
                raw = base64.b64decode(row['base64'], validate=True)
                need(len(raw) == row['bytes'] and base64.b64encode(raw).decode() == row['base64']
                     and hashlib.sha256(raw).hexdigest() == row['sha256'])
                for key in ('device', 'inode'):
                    need(type(row[key]) is str and re.fullmatch('[1-9][0-9]{0,20}', row[key]))
                for key in ('modified', 'changed'):
                    need(type(row[key]) is str and re.fullmatch(r'[0-9]{1,20}\.[0-9]{9}', row[key]))


class OwnedCreateFiles:
    def __init__(self, native, store, binding):
        self.native, self.store, self.binding = native, store, deepcopy(context(binding))

    def owned(self):
        value = self.store.read()
        exact(value, {'schemaVersion', 'binding', 'runId', 'ticket', 'fixtureUrl', 'ownerToken', 'inputBase64',
            'inputSha256', 'stageAttempted', 'exportSha256'})
        need(type(value['schemaVersion']) is int and value['schemaVersion'] == VERSION
             and context(value['binding']) == self.binding and type(value['stageAttempted']) is bool
             and value['ticket'] == self.native.ticket
             and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}', value['ownerToken'])
             and (value['exportSha256'] is None or type(value['exportSha256']) is str
                  and re.fullmatch('[0-9a-f]{64}', value['exportSha256'])))
        identifier(value['runId']); identifier(value['ticket'])
        raw = base64.b64decode(value['inputBase64'], validate=True)
        need(raw == input_bytes(value['runId'], value['ticket'], value['fixtureUrl'])
             and base64.b64encode(raw).decode() == value['inputBase64']
             and hashlib.sha256(raw).hexdigest() == value['inputSha256'])
        return value

    def reserve(self, run, fixture_url):
        need(self.store.read() is None)
        raw = input_bytes(run, self.native.ticket, fixture_url)
        value = dict(schemaVersion=VERSION, binding=self.binding, runId=run, ticket=self.native.ticket,
            fixtureUrl=fixture_url, ownerToken=secrets.token_hex(32), inputBase64=base64.b64encode(raw).decode(),
            inputSha256=hashlib.sha256(raw).hexdigest(), stageAttempted=False, exportSha256=None)
        self.store.write(value, None)
        return deepcopy(self.owned())

    def stage(self):
        previous = self.owned()
        need(not previous['stageAttempted'])
        value = previous | {'stageAttempted':True}
        self.store.write(value, previous)  # Before the sole native mutation.
        self.native.request('stage', value['runId'], value['ownerToken'],
            {'entity-import.json':base64.b64decode(value['inputBase64'], validate=True)})
        return self.verify()

    def observe(self):
        value = self.owned()
        return self.native.request('observe', value['runId'], value['ownerToken'])

    def verify(self):
        value = self.owned(); observed = self.observe()
        need(observed['exists'] and observed['files'][0]['exists']
             and observed['files'][0]['sha256'] == value['inputSha256']
             and observed['files'][0]['base64'] == value['inputBase64'])
        return observed

    def exported(self):
        value = self.owned(); observed = self.verify(); row = observed['files'][1]
        need(row['exists'])
        # This is an original-byte acquisition, not the export semantic verdict.
        # The common Create evidence parser independently judges the real JSON.
        need(value['exportSha256'] in (None, row['sha256']))
        if value['exportSha256'] is None:
            self.store.write(value | {'exportSha256':row['sha256']}, value)
        return deepcopy(row)

    def release(self):
        value = self.owned()
        # Caller must first prove ordinary picker/callback retirement and quiet
        # product state. Unknown export bytes cannot inherit deletion authority.
        observed = self.observe()
        if observed['exists']:
            output = observed['files'][1]
            need(not output['exists'] or output['sha256'] == value['exportSha256'])
        self.native.export_sha256 = value['exportSha256'] or ''
        self.native.request('release', value['runId'], value['ownerToken'])
        need(self.observe() == {'exists':False, 'files':[]})
        self.store.discard(value)
        return {'performed':True}
