"""Passive original Pico LocationBookmarks map and backing-file observations.

No input, persistence, page state, arrival or whole-feature verdict is supplied.
Unowned names, URLs and the backing path remain inside the native process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError

VERSION = 1
FILE = 'feature-location-bookmarks.json'
HEX = r'[0-9a-f]{32}'
DIGEST = r'[0-9a-f]{64}'


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-location-bookmarks'
         and type(value['commandId']) is str and re.fullmatch(HEX, value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX, value['runId']))
    return value


def digest(value):
    return type(value) is str and re.fullmatch(DIGEST, value) is not None


def validate(value, request, pid, epoch):
    command(request)
    exact(value, {'bookmarkObservationVersion', 'commandId', 'runId', 'instance', 'sequence',
                  'processId', 'requestedEpochMs', 'capturedEpochMs', 'storage'})
    need(type(value['bookmarkObservationVersion']) is int and value['bookmarkObservationVersion'] == VERSION
         and value['commandId'] == request['commandId'] and value['runId'] == request['runId']
         and type(value['instance']) is str and re.fullmatch(HEX, value['instance'])
         and integer(pid, 1) and integer(value['processId'], 1) and value['processId'] == pid
         and integer(value['sequence'], 1, 4096) and integer(value['requestedEpochMs'], 1)
         and integer(value['capturedEpochMs'], value['requestedEpochMs'], value['requestedEpochMs'] + 5000))
    fresh(value['capturedEpochMs'], epoch)
    storage = value['storage']
    exact(storage, {'count', 'mapSha256', 'unownedCount', 'unownedSha256', 'owned', 'storageMatches', 'file'})
    need(integer(storage['count'], 0, 4096) and integer(storage['unownedCount'], 0, storage['count'])
         and digest(storage['mapSha256']) and digest(storage['unownedSha256'])
         and storage['storageMatches'] is True
         and type(storage['owned']) is list and len(storage['owned']) <= 2
         and storage['count'] == storage['unownedCount'] + len(storage['owned']))
    allowed = ['e2e-' + request['runId'], 'renamed-' + request['runId']]
    names = []
    for row in storage['owned']:
        exact(row, {'name', 'addressSha256'})
        need(type(row['name']) is str and row['name'] in allowed and row['name'] not in names
             and digest(row['addressSha256']))
        names.append(row['name'])
    need(names == sorted(names, key=allowed.index))
    if not names:
        need(storage['mapSha256'] == storage['unownedSha256'])
    if storage['file'] is None:
        # An absent file is not proof that an in-memory bookmark was saved.
        import hashlib
        need(storage['count'] == 0 and storage['mapSha256'] == hashlib.sha256(b'{}').hexdigest())
    else:
        exact(storage['file'], {'bytes', 'sha256', 'revisionSha256'})
        need(integer(storage['file']['bytes'], 2, 4 * 1024 * 1024)
             and digest(storage['file']['sha256']) and digest(storage['file']['revisionSha256']))
    return value


class NativeLocationBookmarks:
    def __init__(self, send, original, clock_ms, guard, pid, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(f) for f in (send, original, clock_ms, guard, monotonic, sleep)) and integer(pid, 1))
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, original, clock_ms, guard, pid
        self.monotonic, self.sleep = monotonic, sleep
        self.last = None
        self.requests = set()

    def read(self, run):
        request = dict(schemaVersion=1, commandId=uuid.uuid4().hex, action='feature-location-bookmarks', runId=run)
        try:
            command(request)
            need(len(self.requests) < 4096 and request['commandId'] not in self.requests)
            self.requests.add(request['commandId'])
            need(self.guard() is not False)
            started = self.monotonic()
            need(number(started, 0, 1e15))
            previous = started
            self.send(deepcopy(request))
            for attempt in range(51):
                now = self.monotonic()
                need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                previous = now
                raw = self.original()
                try:
                    value = decode(raw) if raw else None
                except (ValueError, NativeUIError):
                    value = None
                if type(value) is dict and value.get('commandId') == request['commandId']:
                    validate(value, request, self.pid, self.clock_ms())
                    if self.last is not None:
                        need(value['instance'] == self.last['instance'] and value['sequence'] > self.last['sequence']
                             and value['requestedEpochMs'] >= self.last['capturedEpochMs'])
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                    self.last = deepcopy(value)
                    return value
                now = self.monotonic()
                need(number(now, 0, 1e15) and previous <= now)
                previous = now
                if now - started >= 5 or attempt == 50:
                    break
                self.sleep(min(.1, 5 - (now - started)))
        except Exception:
            raise NativeUIError('Original native bookmark storage source failed') from None
        raise NativeUIError('Original native bookmark storage source failed')
