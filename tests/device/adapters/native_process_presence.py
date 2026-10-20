"""Fresh original kernel presence observations; unknown is never process death."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError

VERSION = 1
FILE = 'feature-process-presence.json'
LIMIT = 8192


def command(value, *, ios=False):
    exact(value, {'schemaVersion', 'commandId', 'action', 'queryProcessId'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-process-presence' and type(value['commandId']) is str
         and re.fullmatch(('ios-' if ios else '') + '[0-9a-f]{32}', value['commandId'])
         and integer(value['queryProcessId'], 1, 2147483647))
    return value


def validate(value, request, pid, epoch):
    exact(value, {'processPresenceVersion', 'commandId', 'instance', 'sequence', 'processId',
        'queryProcessId', 'requestedEpochMs', 'capturedEpochMs', 'presence', 'nativeResult', 'nativeError', 'errorSymbol'})
    need(type(value['processPresenceVersion']) is int and value['processPresenceVersion'] == VERSION
         and value['commandId'] == request['commandId'] and integer(value['processId'], 1, 2147483647)
         and value['processId'] == pid and integer(value['queryProcessId'], 1, 2147483647)
         and value['queryProcessId'] == request['queryProcessId']
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and integer(value['sequence'], 1, 1_000_000_000)
         and integer(value['requestedEpochMs'], 1) and integer(value['capturedEpochMs'], 1)
         and 0 <= value['capturedEpochMs'] - value['requestedEpochMs'] < 5000
         and integer(value['nativeResult'], -1, 0) and integer(value['nativeError'], 0, 65535)
         and type(value['errorSymbol']) is str and type(value['presence']) is str)
    fresh(value['capturedEpochMs'], epoch)
    if value['presence'] == 'present':
        need(value['nativeResult'] == 0 and value['nativeError'] == 0 and value['errorSymbol'] == 'NONE')
    elif value['presence'] == 'absent':
        need(value['nativeResult'] == -1 and value['nativeError'] == 3 and value['errorSymbol'] == 'ESRCH'
             and value['queryProcessId'] != pid)
    else:
        need(value['presence'] == 'unknown' and value['nativeResult'] == -1 and value['nativeError'] > 0
             and ((value['errorSymbol'] == 'EPERM' and value['nativeError'] == 1)
                  or (value['errorSymbol'] == 'EACCES' and value['nativeError'] == 13)
                  or (value['errorSymbol'] == 'OTHER' and value['nativeError'] not in {1, 3, 13})))
    return value


class NativeProcessPresence:
    def __init__(self, send, original, clock_ms, guard, pid, *, ios=False,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(fn) for fn in (send, original, clock_ms, guard, monotonic, sleep))
             and integer(pid, 1, 2147483647) and type(ios) is bool)
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, original, clock_ms, guard, pid
        self.ios, self.monotonic, self.sleep = ios, monotonic, sleep
        self.last = None

    def read(self, query_pid):
        request = dict(schemaVersion=1, commandId=('ios-' if self.ios else '') + uuid.uuid4().hex,
            action='feature-process-presence', queryProcessId=query_pid)
        command(request, ios=self.ios)
        try:
            need(self.guard() is not False)
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            requested = self.clock_ms(); need(integer(requested, 1))
            now = self.monotonic()
            need(number(now, 0, 1e15) and now >= previous and now - started < 5 and self.guard() is not False)
            previous = now
            self.send(deepcopy(request))
            for attempt in range(51):
                need(self.guard() is not False)
                raw = self.original(); need(type(raw) is str and len(raw.encode()) <= LIMIT)
                try: value = decode(raw) if raw else None
                except json.JSONDecodeError: value = None
                now = self.monotonic()
                need(number(now, 0, 1e15) and now >= previous and now - started < 5 and self.guard() is not False)
                previous = now
                if type(value) is dict and value.get('commandId') == request['commandId']:
                    epoch = self.clock_ms(); need(integer(epoch, 1) and epoch >= requested)
                    validate(value, request, self.pid, epoch)
                    need(value['requestedEpochMs'] >= requested)
                    if self.last is not None:
                        need(value['instance'] == self.last['instance'] and value['sequence'] > self.last['sequence']
                             and value['capturedEpochMs'] >= self.last['capturedEpochMs'])
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and now >= previous and now - started < 5 and self.guard() is not False)
                    self.last = deepcopy(value); return value
                if attempt < 50: self.sleep(0.1)
        except Exception:
            raise NativeUIError('Original native process presence is unavailable or invalid') from None
        raise NativeUIError('Original native process presence did not produce this request')

    def require_absent(self, query_pid):
        value = self.read(query_pid)
        need(value['presence'] == 'absent')
        return value  # Original ESRCH receipt only; no artifact/restart/adoption verdict.
