"""Original native callback ownership, including callbacks after QObject death.

This source covers only owned HTTP fixture contexts. A drained callback ledger
is not proof that a WK view, QImage, offscreen surface or GPU resource is absent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import re
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError

VERSION = 3
READS = {1, 2, 3}
FILE = 'feature-ios-web-closures.json'
LIMIT = 262144
KINDS = {'javascript', 'snapshot', 'presentation', 'rule-list', 'notification', 'script-reply', 'download'}
RESOURCES = {'policy-grant', 'native-view', 'native-bitmap'}
SOFTWARE_RESOURCES = {'scenegraph-node', 'offscreen-image', 'upload-image'}


def resources_for(version):
    return RESOURCES | (SOFTWARE_RESOURCES if version >= 3 else set())
HEX = '[0-9a-f]{32}'


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId', 'fixtureUrl'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-ios-web-closures' and type(value['commandId']) is str
         and re.fullmatch('ios-' + HEX, value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX, value['runId'])
         and type(value['fixtureUrl']) is str and 0 < len(value['fixtureUrl']) <= 512
         and not any(ord(c) <= 32 or ord(c) == 127 for c in value['fixtureUrl']))
    url = urlsplit(value['fixtureUrl']); url.port
    need(url.scheme in ('http', 'https') and url.hostname and url.username is None and url.password is None
         and not url.query and not url.fragment and '?' not in value['fixtureUrl'] and '#' not in value['fixtureUrl']
         and url.path == '/feature-fixture/v1/runs/' + value['runId'] + '/'
         and urlunsplit(url) == value['fixtureUrl'])
    return value


def validate(value, request, pid, epoch):
    command(request)
    exact(value, {'iosWebClosureVersion', 'commandId', 'runId', 'fixtureUrl', 'instance', 'sequence',
                  'processId', 'capturedEpochMs', 'complete', 'contexts'})
    need(type(value['iosWebClosureVersion']) is int and value['iosWebClosureVersion'] in READS
         and all(value[k] == request[k] for k in ('commandId', 'runId', 'fixtureUrl'))
         and type(value['instance']) is str and re.fullmatch(HEX, value['instance'])
         and integer(value['sequence'], 1) and integer(value['processId'], 1) and value['processId'] == pid
         and type(value['complete']) is bool and type(value['contexts']) is list and len(value['contexts']) <= 1024)
    fresh(value['capturedEpochMs'], epoch)
    prefix = request['fixtureUrl'] + 'tickets/'
    previous = 0; descriptors = set()
    for row in value['contexts']:
        exact(row, {'id', 'descriptor', 'createdEpochMs', 'updatedEpochMs', 'callbacks'}
              | ({'resources'} if value['iosWebClosureVersion'] >= 2 else set()))
        need(integer(row['id'], previous + 1) and integer(row['createdEpochMs'], 1, value['capturedEpochMs'])
             and integer(row['updatedEpochMs'], row['createdEpochMs'], value['capturedEpochMs']))
        previous = row['id']; descriptor = row['descriptor']
        exact(descriptor, {'handle', 'creation', 'grant', 'page', 'surface', 'identitySha256', 'sourceUrl'})
        need(integer(descriptor['handle'], 1) and integer(descriptor['creation']) and integer(descriptor['grant'], 1)
             and integer(descriptor['page']) and descriptor['surface'] in ('tablet', 'world-entity')
             and type(descriptor['identitySha256']) is str and re.fullmatch('[0-9a-f]{64}', descriptor['identitySha256'])
             and type(descriptor['sourceUrl']) is str and descriptor['sourceUrl'].startswith(prefix)
             and re.fullmatch(HEX + r'/(?:graphics-marker\.v1|index|reference)\.html', descriptor['sourceUrl'][len(prefix):]))
        identity = json.dumps(descriptor, sort_keys=True)
        need(identity not in descriptors); descriptors.add(identity)
        exact(row['callbacks'], KINDS)
        if value['iosWebClosureVersion'] >= 2:exact(row['resources'], resources_for(value['iosWebClosureVersion']))
        for counters in list(row['callbacks'].values()) + list(row.get('resources', {}).values()):
            exact(counters, {'created', 'retired', 'pending'})
            need(integer(counters['created']) and integer(counters['retired'], 0, counters['created'])
                 and integer(counters['pending']) and counters['pending'] == counters['created'] - counters['retired'])
    return value


def continuity(previous, value, pid):
    if previous is None:
        return
    validate(previous, dict(schemaVersion=1, commandId=previous['commandId'], action='feature-ios-web-closures',
                            runId=previous['runId'], fixtureUrl=previous['fixtureUrl']), pid, previous['capturedEpochMs'])
    need(value['iosWebClosureVersion'] == previous['iosWebClosureVersion'] and value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
         and value['capturedEpochMs'] >= previous['capturedEpochMs']
         and all(value[k] == previous[k] for k in ('runId', 'fixtureUrl', 'processId'))
         and len(value['contexts']) >= len(previous['contexts']) and (previous['complete'] or not value['complete']))
    for old, new in zip(previous['contexts'], value['contexts']):
        need(all(new[k] == old[k] for k in ('id', 'descriptor', 'createdEpochMs'))
             and new['updatedEpochMs'] >= old['updatedEpochMs'])
        for collection in ('callbacks', 'resources') if value['iosWebClosureVersion'] >= 2 else ('callbacks',):
            for kind in old[collection]:
                a, b = old[collection][kind], new[collection][kind]
                need(b['created'] >= a['created'] and b['retired'] >= a['retired'])
        if new['callbacks'] != old['callbacks']:
            need(new['updatedEpochMs'] >= old['updatedEpochMs'])


def drained(value, admitted):
    """Require retained originally admitted contexts and no traced callback.

    The caller still owns fresh acquisition, quiet-window and other lifetime
    obligations. Empty or caller-invented admission cannot prove closure.
    """
    need(type(admitted) is dict and type(value) is dict)
    for packet in (admitted, value):
        validate(packet, dict(schemaVersion=1, commandId=packet.get('commandId'), action='feature-ios-web-closures',
                             runId=packet.get('runId'), fixtureUrl=packet.get('fixtureUrl')),
                 packet.get('processId'), packet.get('capturedEpochMs'))
        need(packet['complete'] is True)
    continuity(admitted, value, admitted['processId'])
    need(bool(admitted['contexts']) and any(c['created'] > 0 for row in admitted['contexts'] for c in row['callbacks'].values())
         and all(c['pending'] == 0 for row in value['contexts'] for c in row['callbacks'].values()))
    return deepcopy(value['contexts'])


def drained_native_resources(value, admitted):
    """Callbacks plus original native view/grant/bitmap implicit-copy absence.

    This remains insufficient for painted software buffers or GPU retirement.
    """
    rows = drained(value, admitted)
    need(admitted['iosWebClosureVersion'] >= 2 and value['iosWebClosureVersion'] >= 2
         and all(any(row['resources'][kind]['created'] > 0 for row in admitted['contexts']) for kind in RESOURCES)
         and all(c['pending'] == 0 for row in value['contexts'] for c in row['resources'].values()))
    return rows


def drained_software_resources(value, admitted):
    """Native resources plus actual Qt node and software/upload image leases.

    This does not include CPU texture, Vulkan objects or submission/recycler
    lifetime. Conservative painted-source unions are not reset by dirty paints.
    """
    rows = drained_native_resources(value, admitted)
    need(admitted['iosWebClosureVersion'] >= 3 and value['iosWebClosureVersion'] >= 3
         and all(any(row['resources'][kind]['created'] > 0 for row in admitted['contexts']) for kind in SOFTWARE_RESOURCES))
    return rows


class IOSWebClosures:
    def __init__(self, send, original, clock_ms, guard, pid, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(v) for v in (send, original, clock_ms, guard, monotonic, sleep)) and integer(pid, 1))
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, original, clock_ms, guard, pid
        self.monotonic, self.sleep, self.last = monotonic, sleep, None

    def read(self, run, fixture_url):
        try:
            request = command(dict(schemaVersion=1, commandId='ios-' + uuid.uuid4().hex,
                                   action='feature-ios-web-closures', runId=run, fixtureUrl=fixture_url))
            started = previous = self.monotonic(); need(number(started, 0, 1e15) and self.guard() is not False)
            requested = self.clock_ms(); need(integer(requested, 1)); self.send(request)
            for attempt in range(16):
                need(self.guard() is not False)
                raw = self.original(); need(type(raw) is str and len(raw.encode()) <= LIMIT)
                try:
                    value = decode(raw) if raw else None
                except json.JSONDecodeError:
                    value = None
                current = self.monotonic(); need(number(current, previous, 1e15) and current - started < 1.5); previous = current
                if type(value) is dict and value.get('commandId') == request['commandId']:
                    epoch = self.clock_ms(); need(integer(epoch, requested))
                    validate(value, request, self.pid, epoch)
                    need(requested <= value['capturedEpochMs'] <= epoch and value['complete'] is True)
                    continuity(self.last, value, self.pid)
                    need(self.guard() is not False)
                    tail = self.monotonic(); need(number(tail, previous, 1e15)); previous = tail
                    final_epoch = self.clock_ms(); need(integer(final_epoch, epoch)); fresh(value['capturedEpochMs'], final_epoch)
                    need(self.guard() is not False)
                    finished = self.monotonic()
                    need(number(finished, previous, 1e15) and finished - started < 1.5
                         and final_epoch - value['capturedEpochMs'] + math.ceil((finished - tail) * 1000) <= 1500)
                    self.last = deepcopy(value)
                    return value
                if attempt < 15:
                    self.sleep(.1)
        except Exception:
            raise NativeUIError('Original iOS Web callback ownership is unavailable or invalid') from None
        raise NativeUIError('Original iOS Web callback ownership did not produce this request')
