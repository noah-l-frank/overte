"""Original Pico named-lookup modal/listener observations and callback join.

No input, replacement dialog, HTTP request, world arrival or feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.native_navigation_replies import validate_event
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce, scope

VERSION = 1
FILE = 'feature-navigation-modals.json'
HEX = r'[0-9a-f]{32}'
DIGEST = r'[0-9a-f]{64}'
MESSAGE = 'There is no address information for that user or place'
MESSAGE_SHA256 = hashlib.sha256(MESSAGE.encode()).hexdigest()
OK = 1024
IMMUTABLE = {'modalId', 'sequence', 'event', 'createdEpochMs', 'profile', 'createdMessageSha256'}


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-navigation-modals'
         and type(value['commandId']) is str and re.fullmatch(HEX, value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX, value['runId']))
    return value


def digest(value):
    return type(value) is str and re.fullmatch(DIGEST, value) is not None


def validate(value, request, pid, epoch):
    command(request)
    exact(value, {'navigationModalVersion', 'commandId', 'runId', 'instance', 'sequence', 'processId', 'capturedEpochMs',
                  'uiEpochMs', 'uiElapsedMs', 'uiInputSequence', 'uiBridgeId', 'uiGeneration', 'tabletOpen', 'rootComplete', 'records'})
    need(type(value['navigationModalVersion']) is int and value['navigationModalVersion'] == VERSION
         and value['commandId'] == request['commandId'] and value['runId'] == request['runId']
         and type(value['instance']) is str and re.fullmatch(HEX, value['instance'])
         and integer(value['sequence'], 1, 4096) and integer(pid, 1) and integer(value['processId'], 1) and value['processId'] == pid
         and integer(value['uiEpochMs'], 1) and integer(value['uiElapsedMs']) and integer(value['uiInputSequence'])
         and nonce(value['uiBridgeId']) and nonce(value['uiGeneration'])
         and type(value['tabletOpen']) is bool and value['rootComplete'] is True
         and type(value['records']) is list and len(value['records']) <= 128)
    fresh(value['capturedEpochMs'], epoch)
    need(0 <= value['capturedEpochMs'] - value['uiEpochMs'] <= 1500)
    previous_sequence = 0;previous_created = 0;ids = set()
    for row in value['records']:
        exact(row, IMMUTABLE | {'messageSha256', 'rootAlive', 'listenerAlive', 'inCurrentTree', 'visible',
                               'callbackFinished', 'callbackEpochMs', 'selectedButton'})
        need(type(row['modalId']) is str and re.fullmatch(HEX, row['modalId']) and row['modalId'] not in ids
             and integer(row['sequence'], previous_sequence + 1, 128)
             and integer(row['createdEpochMs'], max(1, previous_created), value['capturedEpochMs'])
             and row['profile'] in ('unavailable', 'pico-tablet-critical-v1')
             and (row['createdMessageSha256'] is None or digest(row['createdMessageSha256']))
             and (row['profile'] != 'pico-tablet-critical-v1' or digest(row['createdMessageSha256']))
             and all(type(row[k]) is bool for k in ('rootAlive', 'listenerAlive', 'inCurrentTree', 'visible', 'callbackFinished'))
             and (digest(row['messageSha256']) if row['rootAlive'] else row['messageSha256'] is None)
             and (row['rootAlive'] or not row['inCurrentTree'] and not row['visible']))
        need(type(row['event']) is dict and integer(row['event'].get('lookupGeneration'), 1))
        validate_event(row['event'], request['runId'], generation=row['event']['lookupGeneration'], epoch=row['createdEpochMs'],require_capture=True)
        need(row['event']['contentNotFound'] and row['event']['networkError'] == 203)
        if row['callbackFinished']:
            need(integer(row['callbackEpochMs'], row['createdEpochMs'], value['capturedEpochMs'])
                 and integer(row['selectedButton'], 0, 0x08000000))
        else:
            need(type(row['callbackEpochMs']) is int and row['callbackEpochMs'] == 0 and row['selectedButton'] is None)
        ids.add(row['modalId']);previous_sequence = row['sequence'];previous_created = row['createdEpochMs']
    return value


def validate_continuation(previous, current):
    need(current['instance'] == previous['instance'] and current['processId'] == previous['processId']
         and current['sequence'] > previous['sequence'] and current['capturedEpochMs'] >= previous['capturedEpochMs']
         and current['uiBridgeId'] == previous['uiBridgeId']
         and all(current[k] >= previous[k] for k in ('uiEpochMs', 'uiElapsedMs', 'uiInputSequence')))
    if previous['runId'] != current['runId']:
        return
    old = previous['records']
    need(len(current['records']) >= len(old))
    for before, after in zip(old, current['records']):
        need(all(before[k] == after[k] for k in IMMUTABLE)
             and (before['rootAlive'] or not after['rootAlive'])
             and (before['listenerAlive'] or not after['listenerAlive'])
             and (not before['callbackFinished'] or after['callbackFinished']
                  and all(before[k] == after[k] for k in ('callbackEpochMs', 'selectedButton'))))


def matching(value, event):
    need(type(event) is dict and integer(event.get('lookupGeneration'), 1))
    validate_event(event, value['runId'], generation=event['lookupGeneration'], epoch=value['capturedEpochMs'],require_capture=True)
    rows = [row for row in value['records'] if row['event'] == event]
    need(len(rows) == 1)
    return rows[0]


def presented(value, event):
    row = matching(value, event)
    need(value['tabletOpen'] and row['rootAlive'] and row['listenerAlive'] and row['inCurrentTree'] and row['visible']
         and not row['callbackFinished'] and row['profile'] == 'pico-tablet-critical-v1'
         and row['createdMessageSha256'] == row['messageSha256'] == MESSAGE_SHA256
         and len([r for r in value['records'] if r['rootAlive'] or r['listenerAlive']]) == 1)
    return row


def retired(value, event):
    row = matching(value, event)
    need(row['profile'] == 'pico-tablet-critical-v1' and row['createdMessageSha256'] == MESSAGE_SHA256
         and row['callbackFinished'] and row['selectedButton'] == OK and not row['rootAlive'] and not row['listenerAlive']
         and not any(r['rootAlive'] or r['listenerAlive'] for r in value['records']))
    return row


class NativeNavigationModals:
    def __init__(self, send, original, clock_ms, guard, pid, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(f) for f in (send, original, clock_ms, guard, monotonic, sleep)) and integer(pid, 1))
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, original, clock_ms, guard, pid
        self.monotonic, self.sleep = monotonic, sleep
        self.last = None;self.histories = {};self.requests = set()

    def read(self, run):
        request = dict(schemaVersion=1, commandId=uuid.uuid4().hex, action='feature-navigation-modals', runId=run)
        try:
            command(request)
            need(len(self.requests) < 4096 and request['commandId'] not in self.requests)
            self.requests.add(request['commandId'])
            need(self.guard() is not False)
            started = previous = self.monotonic();need(number(started, 0, 1e15))
            self.send(deepcopy(request))
            for attempt in range(51):
                now = self.monotonic()
                need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                previous = now;raw = self.original()
                try:
                    value = decode(raw) if raw else None
                except (ValueError, NativeUIError):
                    value = None
                if type(value) is dict and value.get('commandId') == request['commandId']:
                    validate(value, request, self.pid, self.clock_ms())
                    if self.last is not None:
                        validate_continuation(self.last, value)
                    if run in self.histories:
                        # Per-run originals survive interleaved independent reads.
                        old = self.histories[run]
                        need(value['sequence'] > old['sequence'])
                        validate_continuation(old, value)
                    need(run in self.histories or len(self.histories) < 32)
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                    self.last = deepcopy(value);self.histories[run] = deepcopy(value)
                    return value
                now = self.monotonic();need(number(now, 0, 1e15) and previous <= now);previous = now
                if now - started >= 5 or attempt == 50:
                    break
                self.sleep(min(.1, 5 - (now - started)))
        except Exception:
            raise NativeUIError('Original native navigation modal source failed') from None
        raise NativeUIError('Original native navigation modal source failed')
