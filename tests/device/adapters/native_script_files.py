"""Exclusive E2E Script fixtures, original readback and persistent cleanup intent.

Storage is separate from normal file-picker input and execution evidence. A
successful write receipt never establishes either fixture contents or a load.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import secrets
import time
import uuid

from adapters.normal_feature_state import need, context
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import decode, exact, fresh, integer, number
from adapters.token_script_file_ui import file_url
from feature_journeys.fixtures import payload

FILE = 'feature-script-files.json'
LIMIT = 65536
NAMES = ('script.js', 'companion.js', 'script-bundle/main.js', 'script-bundle/companion.js')


def command(value, *, ios=False):
    need(type(value) is dict)
    fields = {'schemaVersion', 'commandId', 'action', 'operation', 'runId', 'ownerToken'}
    if value.get('operation') == 'stage': fields.add('files')
    exact(value, fields)
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-script-files' and value['operation'] in ('stage', 'observe', 'release', 'locate')
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '(?:ios-)?') + '[0-9a-f]{32}', value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}', value['runId'])
         and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}', value['ownerToken']))
    if value['operation'] == 'stage':
        exact(value['files'], NAMES)
        for encoded in value['files'].values():
            need(type(encoded) is str and 0 < len(encoded) <= 16384)
            raw = base64.b64decode(encoded, validate=True)
            need(0 < len(raw) <= 8192 and base64.b64encode(raw).decode() == encoded)
    need(len(json.dumps(value).encode()) <= 49152)
    return value


def originals(run):
    need(type(run) is str and re.fullmatch('[0-9a-f]{32}', run))
    return {name: payload(name, run, '0' * 32)[1] for name in NAMES}


class NativeScriptFiles:
    def __init__(self, send, read, clock_ms, guard, pid, *, ios=False,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(v) for v in (send, read, clock_ms, guard, monotonic, sleep))
             and integer(pid, 1) and type(ios) is bool)
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        self.ios, self.monotonic, self.sleep = ios, monotonic, sleep
        self.instance, self.sequence = None, 0
        self.last_packet = None
        self.captured_epoch = 0

    def request(self, operation, run, owner, files=None):
        self.last_packet = None
        try:
            request = dict(schemaVersion=1, commandId=('ios-' if self.ios else '') + uuid.uuid4().hex,
                action='feature-script-files', operation=operation, runId=run, ownerToken=owner)
            if files is not None: request['files'] = {key: base64.b64encode(raw).decode() for key, raw in files.items()}
            command(request, ios=self.ios)
            need(self.guard() is not False)
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            requested = self.clock_ms(); need(integer(requested, 1))
            need(self.guard() is not False)
            now = self.monotonic()
            need(number(now, 0, 1e15) and now >= previous and now - started < 5)
            previous = now
            self.send(request)  # Mutations are never replayed after an uncertain receipt.
            for attempt in range(51):
                need(self.guard() is not False)
                raw = self.original()
                need(type(raw) in (str, bytes) and len(raw.encode() if type(raw) is str else raw) <= LIMIT)
                try: value = decode(raw) if raw else None
                except json.JSONDecodeError: value = None
                need(self.guard() is not False)
                now = self.monotonic(); need(number(now, 0, 1e15) and now >= previous and now - started < 5)
                previous = now
                if type(value) is dict and value.get('requestId') == request['commandId']:
                    exact(value, {'schemaVersion', 'requestId', 'instance', 'sequence', 'requestedEpochMs',
                        'capturedEpochMs', 'processId', 'runId', 'operation', 'source'})
                    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
                         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
                         and self.instance in (None, value['instance']) and integer(value['sequence'], self.sequence + 1)
                         and integer(value['processId'], 1) and value['processId'] == self.pid
                         and value['runId'] == run and value['operation'] == operation
                         and integer(value['requestedEpochMs'], 1) and integer(value['capturedEpochMs'], 1)
                         and 0 <= value['capturedEpochMs'] - value['requestedEpochMs'] < 5000
                         and value['requestedEpochMs'] >= requested
                         and value['capturedEpochMs'] >= self.captured_epoch)
                    epoch = self.clock_ms()
                    need(integer(epoch, 1) and epoch >= requested)
                    fresh(value['capturedEpochMs'], epoch)
                    self.validate_source(value['source'], operation, run)
                    need(self.guard() is not False)
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and now >= previous and now - started < 5)
                    self.instance, self.sequence = value['instance'], value['sequence']
                    self.last_packet = deepcopy(value)
                    self.captured_epoch = value['capturedEpochMs']
                    return deepcopy(value['source'])
                if attempt < 50: self.sleep(0.1)
        except Exception:
            raise NativeUIError('Native Script fixture storage is unavailable or invalid') from None
        raise NativeUIError('Native Script fixture storage did not produce this request')

    @staticmethod
    def validate_source(value, operation, run):
        if operation == 'locate':
            exact(value, {'locationVersion', 'exists', 'directory'})
            need(type(value['locationVersion']) is int and value['locationVersion'] == 1
                 and type(value['exists']) is bool
                 and file_url(value['directory']).endswith('/feature-script-' + run))
            return
        if operation != 'observe':
            exact(value, {'performed'}); need(value['performed'] is True); return
        need(type(value) is dict and type(value.get('exists')) is bool)
        exact(value, {'exists', 'files', 'directory'} if value['exists'] else {'exists', 'files'})
        need(type(value['files']) is list)
        if not value['exists']: need(value['files'] == []); return
        directory = file_url(value['directory'])
        need(directory.endswith('/feature-script-' + run) and len(value['files']) == len(NAMES))
        seen = set()
        for row in value['files']:
            need(type(row) is dict and row.get('name') in NAMES and row['name'] not in seen
                 and type(row.get('exists')) is bool)
            exact(row, {'name', 'exists', 'bytes', 'sha256', 'base64'} if row['exists'] else {'name', 'exists'})
            if row['exists']:
                need(integer(row['bytes'], 1, 8192) and type(row['base64']) is str and len(row['base64']) <= 16384)
                raw = base64.b64decode(row['base64'], validate=True)
                need(len(raw) == row['bytes'] and base64.b64encode(raw).decode() == row['base64']
                     and hashlib.sha256(raw).hexdigest() == row['sha256'])
            seen.add(row['name'])


class OwnedScriptFiles:
    def __init__(self, native, store, binding, *, component_only=False):
        self.native, self.store = native, store
        self.component_only = component_only
        self.binding = deepcopy(context(binding, component_only=component_only))

    def owned(self):
        value = self.store.read()
        need(type(value) is dict and set(value) == {'contractVersion', 'runId', 'ownerToken', 'binding', 'hashes'}
             and type(value['contractVersion']) is int and value['contractVersion'] == 1
             and context(value['binding'], component_only=self.component_only) == self.binding
             and type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}', value['runId'])
             and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}', value['ownerToken'])
             and value['hashes'] == {name: hashlib.sha256(raw).hexdigest() for name, raw in originals(value['runId']).items()})
        return value

    def reserve(self, run):
        """Record exclusive input/cleanup intent without any native request."""
        need(self.store.read() is None)
        files = originals(run)
        value = dict(contractVersion=1, runId=run, ownerToken=secrets.token_hex(32), binding=self.binding,
                     hashes={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()})
        self.store.write(value, None)
        return deepcopy(self.owned())

    def stage_reserved(self):
        # The full coordinator must persist its stage phase before this one
        # attempt. No uncertain stage is retried; verify/release are separate.
        value = self.owned()
        self.native.request('stage', value['runId'], value['ownerToken'], originals(value['runId']))
        return self.verify()

    def stage(self, run):
        self.reserve(run)
        return self.stage_reserved()

    def locate(self):
        value = self.owned()
        return self.native.request('locate', value['runId'], value['ownerToken'])

    def verify(self):
        value = self.owned()
        source = self.native.request('observe', value['runId'], value['ownerToken'])
        need(source['exists'] and all(row['exists'] for row in source['files']))
        files = originals(value['runId'])
        need({row['name']: base64.b64decode(row['base64'], validate=True) for row in source['files']} == files)
        return source['directory']  # Actual native directory, never a guessed sandbox path.

    def release(self):
        value = self.owned()
        self.native.request('release', value['runId'], value['ownerToken'])
        observed = self.native.request('observe', value['runId'], value['ownerToken'])
        need(observed == {'exists': False, 'files': []})
        self.store.discard(value)
        return {'performed': True}
