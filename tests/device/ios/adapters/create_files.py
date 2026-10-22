"""Closed Create JSON input staging and actual product-export byte acquisition.

Input bytes and exported bytes have separate roles. Staging cannot establish an
import; a Save input cannot establish an exported original or its lifetime.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import re
import secrets
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from feature_journeys.contract import identifier
from feature_journeys.fixtures import import_document
from ios.adapters.create_controls_v2 import local_url, owned_path

from ios.adapters.create_api_clock import check as api_check

VERSION = 1
ACTION = 'feature-ios-create-files'
FILE = ACTION+'.json'
LIMIT = 262144
NAMES = ('entity-import.json', 'export.json')


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId', 'ownerToken', 'operation'}
          | ({'inputBase64'} if value.get('operation') == 'stage' else set())
          | ({'originals'} if value.get('operation') == 'release' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['action'] == ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}', value['commandId'])
         and type(value['ownerToken']) is str and re.fullmatch('[a-f0-9]{64}', value['ownerToken'])
         and value['operation'] in ('stage', 'locate', 'observe', 'release'))
    identifier(value['runId'])
    if value['operation'] == 'stage': original_bytes(value['inputBase64'], 8192)
    if value['operation'] == 'release': file_rows(value['originals'])
    need(len(json.dumps(value).encode()) <= 131072)
    return value


def original_bytes(encoded, maximum):
    need(type(encoded) is str and len(encoded) <= 4*((maximum+2)//3))
    raw = base64.b64decode(encoded, validate=True)
    need(0 < len(raw) <= maximum and base64.b64encode(raw).decode() == encoded)
    return raw


def file_rows(value):
    need(type(value) is list and len(value) == 2 and [row.get('name') for row in value] == list(NAMES))
    for row in value:
        need(type(row['exists']) is bool)
        exact(row, {'name', 'exists'} | ({'bytes', 'sha256', 'base64', 'identity'} if row['exists'] else set()))
        if not row['exists']: continue
        raw = original_bytes(row['base64'], 8192 if row['name'] == NAMES[0] else 65536)
        need(type(row['bytes']) is int and row['bytes'] == len(raw) and row['sha256'] == hashlib.sha256(raw).hexdigest())
        identity = row['identity']; exact(identity, {'device', 'inode', 'bytes', 'modifiedSeconds', 'modifiedNanoseconds',
                                                   'changedSeconds', 'changedNanoseconds'})
        for key, number in identity.items():
            need(type(number) is str and re.fullmatch('0|[1-9][0-9]{0,19}', number) and int(number) < 2**64)
        need(identity['bytes'] == str(len(raw)) and 0 <= int(identity['modifiedNanoseconds']) < 10**9
             and 0 <= int(identity['changedNanoseconds']) < 10**9)
    return value


def validate(value, query, pid, epoch=None, previous=None):
    command(query)
    exact(value, {'iosCreateFilesVersion', 'requestId', 'runId', 'instance', 'sequence', 'processId',
                  'clockDomain', 'clockBefore', 'clockAfter', 'source'})
    need(type(value['iosCreateFilesVersion']) is int and value['iosCreateFilesVersion'] == VERSION
         and value['requestId'] == query['commandId'] and value['runId'] == query['runId']
         and integer(pid, 1) and type(value['processId']) is int and value['processId'] == pid
         and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}', value['instance'])
         and integer(value['sequence'], 1, 1000000000) and value['clockDomain'] == 'native-main-create-files')
    before, after = value['clockBefore'], value['clockAfter']
    for clock in (before, after):
        exact(clock, {'epochMs', 'monotonicMs'}); need(integer(clock['epochMs'], 1) and integer(clock['monotonicMs']))
    utc = after['epochMs']-before['epochMs']; mono = after['monotonicMs']-before['monotonicMs']
    need(0 <= utc < 1500 and 0 <= mono < 1500 and abs(utc-mono) <= 250)
    if epoch is not None: fresh(after['epochMs'], epoch)
    source = value['source']; operation = query['operation']
    if operation in ('stage', 'release'): exact(source, {'performed'}); need(source['performed'] is True)
    else:
        need(type(source) is dict and type(source.get('exists')) is bool)
        if operation == 'locate': exact(source, {'exists', 'directory'})
        else:
            exact(source, {'exists', 'files'} | ({'directory'} if source['exists'] else set()))
            if source['exists']: file_rows(source['files'])
            else: need(source['files'] == [])
        if 'directory' in source:
            path = local_url(source['directory']); owned_path(path, query['runId'])
            need(path.endswith('/feature-create-'+query['runId']))
    if previous is not None:
        # The preceding source may be a different operation. Its immutable
        # envelope is retained by the owner, not revalidated as this operation.
        need(value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
             and value['runId'] == previous['runId'] and value['processId'] == previous['processId']
             and value['requestId'] != previous['requestId'] and before['epochMs'] >= previous['clockAfter']['epochMs']
             and before['monotonicMs'] >= previous['clockAfter']['monotonicMs'])
    return value


class IOSCreateFiles:
    def __init__(self, send, read, clock_ms, guard, pid, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(fn) for fn in (send, read, clock_ms, guard, monotonic, sleep)) and integer(pid, 1))
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        self.monotonic, self.sleep = monotonic, sleep
        self.last = self.last_query = None

    def request(self, operation, run, token, *, content=None, originals=None, retain=None):
        query = dict(schemaVersion=1, commandId='ios-'+uuid.uuid4().hex, action=ACTION,
                     operation=operation, runId=run, ownerToken=token)
        if content is not None: query['inputBase64'] = base64.b64encode(content).decode()
        if originals is not None: query['originals'] = deepcopy(originals)
        command(query); need(retain is None or callable(retain))
        need(self.guard() is not False); started = last = self.monotonic(); requested = self.clock_ms()
        need(number(started, 0, 1e15) and integer(requested, 1))
        api_check();self.send(query)  # No retransmission after any uncertain result.
        for attempt in range(61):
            need(self.guard() is not False); raw = self.original()
            need(type(raw) is str and len(raw.encode()) <= LIMIT)
            try: value = decode(raw) if raw else None
            except json.JSONDecodeError: value = None
            now = self.monotonic(); need(number(now, last, started+1.5) and now-started < 1.5); last = now
            if type(value) is dict and value.get('requestId') == query['commandId']:
                if retain is not None: retain(deepcopy(query), deepcopy(value))
                epoch = self.clock_ms(); need(integer(epoch, requested))
                validate(value, query, self.pid, epoch, self.last)
                need(value['clockBefore']['epochMs'] >= requested and self.guard() is not False)
                now = self.monotonic(); need(number(now, last, started+1.5) and now-started < 1.5)
                self.last, self.last_query = deepcopy(value), deepcopy(query)
                return deepcopy(value)
            if attempt < 60: self.sleep(.025)
        raise NativeUIError('Original Create file source did not produce this request')


class OwnedCreateFiles:
    """One immutable import INPUT and one independently read product OUTPUT."""
    def __init__(self, native, store, binding, run, fixture_url, *, lock):
        need(isinstance(native, IOSCreateFiles) and isinstance(store, PrivateFeatureState))
        self.native, self.store, self.binding = native, store, deepcopy(context(binding))
        self.run, self.fixture_url, self.lock = identifier(run), fixture_url, lock
        need(str(native.pid) == binding['processIdentity'])
        lock.assert_held(); self.previous = store.read(); self.state = None if self.previous is None else self.decode(self.previous)
        if self.state and self.state['originals']:
            last = self.state['originals'][-1]; native.last = deepcopy(last['packet']); native.last_query = deepcopy(last['query'])

    def envelope(self):
        return dict(iosCreateFileOwnerVersion=VERSION, runId=self.run, fixtureUrl=self.fixture_url,
                    binding=self.binding, payload=pack([self.state]))

    def decode(self, value):
        exact(value, {'iosCreateFileOwnerVersion', 'runId', 'fixtureUrl', 'binding', 'payload'})
        need(type(value['iosCreateFileOwnerVersion']) is int and value['iosCreateFileOwnerVersion'] == VERSION
             and value['runId'] == self.run and value['fixtureUrl'] == self.fixture_url and same(value['binding'], self.binding))
        states = unpack(value['payload']); need(len(states) == 1); state = states[0]
        exact(state, {'phase', 'token', 'ticket', 'inputBase64', 'directory', 'originals'})
        need(state['phase'] in ('reserved', 'staging', 'staged', 'releasing', 'retired')
             and type(state['token']) is str and re.fullmatch('[a-f0-9]{64}', state['token'])
             and type(state['originals']) is list and len(state['originals']) <= 128)
        identifier(state['ticket']); original_bytes(state['inputBase64'], 8192)
        expected = json.dumps(import_document(self.run, state['ticket'], self.fixture_url), separators=(',', ':')).encode()
        need(base64.b64encode(expected).decode() == state['inputBase64'])
        previous = None
        for entry in state['originals']:
            exact(entry, {'query', 'packet'}); query = entry['query']
            need(query['runId'] == self.run and query['ownerToken'] == state['token'])
            validate(entry['packet'], query, self.native.pid, previous=previous); previous = entry['packet']
        return state

    def save(self):
        self.lock.assert_held(); need(same(self.store.read(), self.previous) and self.native.guard() is not False)
        value = self.envelope(); self.decode(value); self.store.write(value, self.previous)
        need(same(self.store.read(), value)); self.previous = deepcopy(value)

    def retain(self, query, packet):
        need(self.state is not None and len(self.state['originals']) < 128)
        # Keep the matched original even if the later native clock read fails.
        # A malformed original poisons this owner instead of disappearing.
        self.state['originals'].append(dict(query=deepcopy(query), packet=deepcopy(packet))); self.save()

    def reserve(self, ticket):
        api_check();self.lock.assert_held(); need(self.state is None); identifier(ticket)
        raw = json.dumps(import_document(self.run, ticket, self.fixture_url), separators=(',', ':')).encode()
        self.state = dict(phase='reserved', token=secrets.token_hex(32), ticket=ticket,
                         inputBase64=base64.b64encode(raw).decode(), directory=None, originals=[]); self.save()

    def stage(self):
        need(self.state is not None and self.state['phase'] == 'reserved')
        api_check();self.state['phase'] = 'staging'; self.save()
        self.native.request('stage', self.run, self.state['token'],
            content=original_bytes(self.state['inputBase64'], 8192), retain=self.retain)
        return self.recover_stage()

    def recover_stage(self):
        need(self.state is not None and self.state['phase'] in ('staging', 'staged'))
        value = self.observe(); need(value['source']['exists'])
        rows = value['source']['files']; need(rows[0]['exists'] and rows[0]['base64'] == self.state['inputBase64'])
        self.state['phase'] = 'staged'; self.state['directory'] = value['source']['directory']; self.save()
        return local_url(self.state['directory'])

    def observe(self):
        need(self.state is not None)
        return self.native.request('observe', self.run, self.state['token'], retain=self.retain)

    def release(self, originals):
        """Caller must first prove closed picker/renderer/input callbacks quiet.

        Metadata remains after release until the enclosing two-role cleanup
        proves actual native absence. This method cannot retire whole ownership.
        """
        need(self.state is not None and self.state['phase'] == 'staged'); file_rows(originals)
        value = self.observe(); need(value['source']['exists'] and same(value['source']['files'], originals))
        self.state['phase'] = 'releasing'; self.save()
        self.native.request('release', self.run, self.state['token'], originals=originals, retain=self.retain)
        return self.recover_release()

    def recover_release(self):
        """Only read after an uncertain release; never repeat the unlink input."""
        need(self.state is not None and self.state['phase'] in ('releasing', 'retired'))
        after = self.observe(); need(after['source'] == {'exists': False, 'files': []})
        self.state['phase'] = 'retired'; self.save(); return after
