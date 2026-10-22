"""Durable normal directory selection and original-value restoration.

The parent owns the tablet/input/source lock and opens the ordinary login page
before each selection. This does not establish a whole Navigation feature.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_navigation_environment import endpoint, validate, continuation, logged_out
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.token_login_ui import validate_metadata
from adapters.token_create_ui import scope, nonce

VERSION = 1


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class NavigationOrigin:
    def __init__(self, io, native, path, run, binding, guard, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(f) for f in (guard, monotonic, sleep)) and type(run) is str and re.fullmatch('[0-9a-f]{32}', run))
        context(binding);need(native.pid == int(binding['processIdentity'].split(':', 1)[0]))
        self.io, self.native, self.run, self.binding, self.guard = io, native, run, deepcopy(binding), guard
        self.monotonic, self.sleep = monotonic, sleep;self.clock = self.deadline = None
        self.store = PrivateFeatureState(path);self.disk_state = self.store.read()
        self.state = self.decode_state(self.disk_state) if self.disk_state is not None else None
        if self.state is not None:
            self.validate_state(self.state)

    def now(self):
        need(self.guard() is not False);value = self.monotonic()
        need(number(value, 0, 1e15) and (self.clock is None or value >= self.clock)
             and (self.deadline is None or value <= self.deadline));self.clock = value;return value

    def archive(self, packet):
        need(type(packet) is dict)
        validate(packet, dict(schemaVersion=1, commandId=packet.get('commandId'), action='feature-navigation-environment', runId=self.run),
                 self.native.pid, packet.get('capturedEpochMs'))
        logged_out(packet)
        need(packet['ui']['bridgeId'] == self.binding['sessionId'] and not packet['environmentOverride'])

    def validate_state(self, value):
        exact(value, {'navigationOriginVersion', 'runId', 'binding', 'original', 'last', 'ownedServer', 'operation', 'queries'})
        need(type(value['navigationOriginVersion']) is int and value['navigationOriginVersion'] == VERSION
             and value['runId'] == self.run and value['binding'] == self.binding)
        endpoint(value['ownedServer']);need(not urlsplit(value['ownedServer']).path)
        self.archive(value['original']);self.archive(value['last'])
        if value['original'] != value['last']:
            continuation(value['original'], value['last'])
        need(value['original']['selectedSettingPresent'] and value['original']['selectedServer'] == value['original']['effectiveServer']
             and value['original']['account']['observation']['endpointSha256'] == sha(value['original']['selectedServer'])
             and value['original']['ui']['passwordEmpty'] is True
             and value['original']['ui']['serverDraftSha256'] == sha(value['original']['selectedServer'])
             and value['last']['otherSettingsSha256'] == value['original']['otherSettingsSha256']
             and value['last']['selectedSettingPresent']
             and value['last']['selectedServer'] in (value['original']['selectedServer'], value['ownedServer'])
             and value['last']['effectiveServer'] in (value['original']['selectedServer'], value['ownedServer'])
             and type(value['queries']) is list and 1 <= len(value['queries']) <= 256
             and all(type(v) is str and re.fullmatch('[0-9a-f]{32}', v) for v in value['queries'])
             and len(set(value['queries'])) == len(value['queries'])
             and all(value[k]['commandId'] in value['queries'] for k in ('original', 'last')))
        operation = value['operation']
        exact(operation, {'ticket', 'restoring', 'stage', 'pending', 'quiet'})
        need(type(operation['ticket']) is str and re.fullmatch('[0-9a-f]{32}', operation['ticket'])
             and type(operation['restoring']) is bool and integer(operation['stage'], 0, 4)
             and type(operation['quiet']) is list and len(operation['quiet']) <= 8)
        if operation['pending'] is not None:
            exact(operation['pending'], {'stage', 'control', 'action', 'token', 'scope'})
            pending = operation['pending'];scope(pending['scope'])
            need(pending['stage'] == operation['stage'] < 4 and pending['control'] == ('login.server' if operation['stage'] < 3 else 'tablet.home')
                 and pending['action'] == ('replace' if operation['stage'] == 1 else 'submit' if operation['stage'] == 2 else 'activate')
                 and nonce(pending['token'])
                 and pending['scope']['instance'] == self.binding['sessionId'] and pending['scope']['processId'] == self.native.pid)
        previous = None
        for packet in operation['quiet']:
            self.archive(packet);self.final(packet, value)
            need(packet['commandId'] in value['queries'])
            continuation(value['original'], packet)
            if previous is not None:
                continuation(previous, packet);self.quiet_continuation(previous, packet)
            previous = packet
        if operation['quiet']:
            need(operation['stage'] == 4 and operation['pending'] is None and len(operation['quiet']) >= 3)
            a, b = operation['quiet'][0], operation['quiet'][-1]
            need(all(b['ui'][k] - a['ui'][k] >= 3000 for k in ('elapsedMs', 'observedEpochMs'))
                 and b['capturedEpochMs'] - a['capturedEpochMs'] >= 3000)

    @staticmethod
    def packet_digest(packet):
        raw = json.dumps(packet, allow_nan=False, sort_keys=True, separators=(',', ':')).encode() + b'\n'
        return hashlib.sha256(raw).hexdigest()

    def packet_store(self, digest):
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest))
        return PrivateFeatureState(self.store.path.parent / ('navigation-' + self.run + '-environment-' + digest + '.json'))

    def archive_packet(self, packet):
        digest = self.packet_digest(packet);archive = self.packet_store(digest);original = archive.read()
        if original is None:
            archive.write(packet, None);original = archive.read()
        need(original == packet and self.packet_digest(original) == digest)
        return dict(navigationEnvironmentArchiveVersion=1, sha256=digest)

    def original_packet(self, reference):
        exact(reference, {'navigationEnvironmentArchiveVersion', 'sha256'})
        need(type(reference['navigationEnvironmentArchiveVersion']) is int and reference['navigationEnvironmentArchiveVersion'] == 1)
        packet = self.packet_store(reference['sha256']).read()
        need(packet is not None and self.packet_digest(packet) == reference['sha256'])
        return packet

    def map_packets(self, value, function):
        result = deepcopy(value)
        for key in ('original', 'last'):
            result[key] = function(result[key])
        result['operation']['quiet'] = [function(packet) for packet in result['operation']['quiet']]
        return result

    def decode_state(self, value):
        exact(value, {'navigationOriginVersion', 'runId', 'binding', 'original', 'last', 'ownedServer', 'operation', 'queries'})
        exact(value['operation'], {'ticket', 'restoring', 'stage', 'pending', 'quiet'})
        need(type(value['operation']['quiet']) is list and len(value['operation']['quiet']) <= 8)
        return self.map_packets(value, self.original_packet)

    def save(self, value):
        self.validate_state(value);encoded = self.map_packets(value, self.archive_packet)
        self.store.write(encoded, self.disk_state);self.disk_state = deepcopy(encoded);self.state = deepcopy(value)

    def sample(self):
        self.now();ui = self.io.capture();packet = self.native.read(self.run);self.now();self.archive(packet)
        need(ui.get('navigationOriginControlsVersion') == 1 and type(ui['navigationOriginControlsVersion']) is int
             and ui['bridgeId'] == packet['ui']['bridgeId'] and ui['generation'] == packet['ui']['generation']
             and ui['lastCommandSequence'] == packet['ui']['sequence'] and ui['processId'] == packet['processId'])
        if self.state is not None:
            continuation(self.state['last'], packet)
            need(packet['commandId'] not in self.state['queries'] and len(self.state['queries']) < 256
                 and packet['otherSettingsSha256'] == self.state['original']['otherSettingsSha256'])
            current = deepcopy(self.state);current['last'] = packet;current['queries'].append(packet['commandId']);self.save(current)
        return ui, packet

    def desired(self, value=None):
        value = self.state if value is None else value
        return value['original']['selectedServer'] if value['operation']['restoring'] else value['ownedServer']

    def final(self, packet, value=None):
        value = self.state if value is None else value
        need(packet['selectedServer'] == packet['effectiveServer'] == self.desired(value)
             and packet['account']['observation']['endpointSha256'] == sha(self.desired(value))
             and packet['selectedSettingPresent'] and not packet['ui']['loginPageAlive']
             and packet['ui']['serverDraftSha256'] is None and packet['otherSettingsSha256'] == value['original']['otherSettingsSha256'])

    def effect(self, packet, pending):
        ui = packet['ui'];before = pending['scope']
        need(ui['sequence'] == before['sequence'] + 1)
        if pending['stage'] < 3:
            need(ui['generation'] == before['generation'] and ui['loginPageAlive'])
        target = sha(self.desired())
        if pending['stage'] == 0:
            need(ui['serverFocused'] is True)
        elif pending['stage'] == 1:
            need(ui['serverFocused'] is True and ui['serverDraftSha256'] == target)
        elif pending['stage'] == 2:
            need(packet['selectedServer'] == packet['effectiveServer'] == self.desired()
                 and packet['account']['observation']['endpointSha256'] == target)
        else:
            self.final(packet)

    @staticmethod
    def quiet_continuation(previous, current):
        need(current['ui']['sequence'] == previous['ui']['sequence']
             and current['ui']['generation'] == previous['ui']['generation']
             and current['capturedEpochMs'] - previous['capturedEpochMs'] <= 1500
             and all(current['account']['observation'][k] == previous['account']['observation'][k]
                     for k in ('credentialGeneration', 'eventSequence')))

    def select(self, ticket, owned_server, *, restoring=False):
        endpoint(owned_server)
        need(not urlsplit(owned_server).path and type(restoring) is bool and type(ticket) is str and re.fullmatch('[0-9a-f]{32}', ticket))
        need(self.deadline is None);self.deadline = self.now() + 20
        try:
            return self.execute(ticket, owned_server, restoring)
        except NativeUIError:
            raise
        except Exception:
            raise NativeUIError('Original directory selection remains unresolved') from None
        finally:
            self.deadline = None

    def execute(self, ticket, owned_server, restoring):
        if self.state is None:
            need(not restoring);_, first = self.sample()
            # An ordinary field cannot restore absence of the setting. Refuse
            # before input, rather than silently materializing a default.
            need(first['selectedSettingPresent'] and first['selectedServer'] == first['effectiveServer']
                 and first['account']['observation']['endpointSha256'] == sha(first['selectedServer'])
                 and first['ui']['passwordEmpty'] is True and first['ui']['serverDraftSha256'] == sha(first['selectedServer']))
            self.save(dict(navigationOriginVersion=VERSION, runId=self.run, binding=self.binding, original=first, last=first,
                ownedServer=owned_server, queries=[first['commandId']],
                operation=dict(ticket=ticket, restoring=False, stage=0, pending=None, quiet=[])))
        need(self.state['ownedServer'] == owned_server)
        operation = self.state['operation']
        if operation['ticket'] != ticket:
            need(restoring and not operation['restoring'] and operation['stage'] == 4 and operation['quiet'])
            current = deepcopy(self.state);current['operation'] = dict(ticket=ticket, restoring=True, stage=0, pending=None, quiet=[]);self.save(current)
        need(self.state['operation']['restoring'] == restoring)
        while self.state['operation']['stage'] < 4:
            ui, packet = self.sample();operation = self.state['operation'];stage = operation['stage']
            if operation['pending'] is None:
                if stage == 0:
                    expected = self.state['ownedServer'] if restoring else self.state['original']['selectedServer']
                    need(packet['selectedServer'] == packet['effectiveServer'] == expected
                         and packet['ui']['passwordEmpty'] is True and packet['ui']['serverDraftSha256'] == sha(expected))
                identifier = 'tablet.home' if stage == 3 else 'login.server'
                rows = [r for r in ui['controls'] if r['id'] == identifier];need(len(rows) == 1)
                row = rows[0]
                if stage < 3:
                    validate_metadata(row)
                need(row['enabled'] and (stage == 3 or row['inputReady'])
                     and (stage not in (1, 2) or row['focused']))
                action = 'replace' if stage == 1 else 'submit' if stage == 2 else 'activate'
                pending = dict(stage=stage, control=identifier, action=action, token=row['token'],
                    scope=dict(instance=ui['bridgeId'], generation=ui['generation'], sequence=ui['lastCommandSequence'],
                               elapsedMs=ui['elapsedMs'], processId=ui['processId']))
                current = deepcopy(self.state);current['operation']['pending'] = pending;self.save(current)
                self.io.deliver(pending, self.desired() if stage == 1 else None)
            pending = self.state['operation']['pending']
            for attempt in range(81):
                _, packet = self.sample()
                need(pending['scope']['sequence'] <= packet['ui']['sequence'] <= pending['scope']['sequence'] + 1)
                try:
                    self.effect(packet, pending)
                    break
                except NativeUIError:
                    need(attempt < 80);self.sleep(.1)
            current = deepcopy(self.state);current['operation']['pending'] = None;current['operation']['stage'] += 1;self.save(current)
        _, packet = self.sample();self.final(packet)
        if self.state['operation']['quiet']:
            return dict(performed=True)
        groups = [];start = self.now()
        for _ in range(8):
            _, packet = self.sample();self.final(packet)
            if groups:
                self.quiet_continuation(groups[-1], packet)
            groups.append(packet)
            if self.now() - start >= 3:
                current = deepcopy(self.state);current['operation']['quiet'] = groups;self.save(current)
                return dict(performed=True)
            self.sleep(.5)
        raise NativeUIError('Directory selection quiet state remains unresolved')
