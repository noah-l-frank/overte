"""Original PCM taps for the normal automatic three-second memory preview.

This source reader never starts/stops a preview or supplies audio. Returned
bytes are native captures, not synthesized WAVs, expectations or verdicts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import re
import shlex
import time
import uuid

from adb_transport import AdbTransport
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError

FILE = 'recorded-preview-observation.json'
INPUT = 'recorded-preview-input.pcm16le'
SINK = 'recorded-preview-sink.pcm16le'
MAX_BYTES = 32 * 1024 * 1024


def validate_absence(value,request,pid,epoch,*,instance=None,after_sequence=0):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','files','memoryEmpty'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and instance in (None,value['instance']) and integer(value['sequence'],after_sequence+1)
        and integer(value['processId'],1) and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
        and 0<=value['capturedEpochMs']-value['requestedEpochMs']<5000 and value['memoryEmpty'] is True
        and type(value['files']) is list and len(value['files'])==2)
    fresh(value['capturedEpochMs'],epoch)
    for row,name in zip(value['files'],(INPUT,SINK)):
        exact(row,{'name','exists'});need(row['name']==name and row['exists'] is False)
    return value


def validate(value, request, pid, epoch):
    exact(value, {'schemaVersion', 'requestId', 'instance', 'sequence', 'requestedEpochMs',
                  'capturedEpochMs', 'processId', 'source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['requestId'] == request and integer(value['processId'], 1) and value['processId'] == pid
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and integer(value['sequence'], 1) and integer(value['requestedEpochMs'], 1)
         and integer(value['capturedEpochMs'], 1)
         and 0 <= value['capturedEpochMs'] - value['requestedEpochMs'] < 5000)
    fresh(value['capturedEpochMs'], epoch)
    source = value['source']
    exact(source, {'cycle', 'startedEpochMs', 'sampleRate', 'channels', 'inputLastEpochMs',
                   'sinkLastEpochMs', 'events', 'input', 'sink'})
    need(integer(source['cycle'], 1) and integer(source['sampleRate'], 8000, 48000)
         and integer(source['channels'], 1, 2) and integer(source['startedEpochMs'], 1)
         and 0 <= value['capturedEpochMs'] - source['startedEpochMs'] < 30000)
    frame = source['channels'] * 2
    limit = source['sampleRate'] * frame * 3
    for kind, name, tap in [('input', INPUT, 'capture-before-normalization'),
                             ('sink', SINK, 'loopback-device-accepted-write')]:
        artifact = source[kind]
        exact(artifact, {'name', 'tap', 'bytes', 'sha256'})
        need(artifact['name'] == name and artifact['tap'] == tap
             and integer(artifact['bytes'], 0, limit if kind == 'input' else MAX_BYTES)
             and artifact['bytes'] % frame == 0
             and type(artifact['sha256']) is str and re.fullmatch('[0-9a-f]{64}', artifact['sha256']))
        captured = source[kind + 'LastEpochMs']
        need(integer(captured) and (captured == 0 if artifact['bytes'] == 0 else
             source['startedEpochMs'] <= captured <= value['capturedEpochMs']))
    need(type(source['events']) is list and 1 <= len(source['events']) <= 64)
    previous, terminal, event_epoch = 0, False, source['startedEpochMs']
    previous_captured = previous_played = 0
    for event in source['events']:
        exact(event, {'schemaVersion', 'eventSequence', 'publishedEpochMs', 'phase', 'error',
                      'capturedBytes', 'playedBytes', 'totalBytes'})
        need(type(event['schemaVersion']) is int and event['schemaVersion'] == 1
             and integer(event['eventSequence'], previous + 1) and integer(event['publishedEpochMs'], 1)
             and event_epoch <= event['publishedEpochMs'] <= value['capturedEpochMs']
             and type(event['phase']) is str and event['phase'] in
                 {'capturing', 'playing', 'draining', 'completed', 'cancelled', 'error'}
             and type(event['error']) is str and len(event['error']) <= 128
             and not any(ord(c) < 32 for c in event['error'])
             and integer(event['capturedBytes'], previous_captured, limit)
             and integer(event['playedBytes'], previous_played, event['capturedBytes'])
             and integer(event['totalBytes']) and event['totalBytes'] in (0, limit)
             and event['capturedBytes'] <= event['totalBytes']
             and event['capturedBytes'] <= source['input']['bytes'] and not terminal)
        previous, previous_captured, previous_played = event['eventSequence'], event['capturedBytes'], event['playedBytes']
        event_epoch = event['publishedEpochMs']
        terminal = event['phase'] in {'completed', 'cancelled', 'error'}
    last = source['events'][-1]
    if terminal:
        need(last['capturedBytes'] == source['input']['bytes'])
    if last['phase'] == 'completed':
        need(last['capturedBytes'] == last['playedBytes'] == limit
             and source['sink']['bytes'] >= limit)
    return value


class RecordedPreviewEvidence:
    def __init__(self, send, read, read_bytes, clock_ms, guard, pid, *, ios=False,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(v) for v in (send, read, read_bytes, clock_ms, guard, monotonic, sleep))
             and integer(pid, 1) and type(ios) is bool)
        self.send, self.original, self.bytes = send, read, read_bytes
        self.clock_ms, self.guard, self.pid, self.ios = clock_ms, guard, pid, ios
        self.monotonic, self.sleep = monotonic, sleep
        self.instance, self.sequence, self.cycle, self.event_sequence = None, 0, 0, 0

    def _request(self, action):
        need(self.guard() is not False)
        request = ('ios-' if self.ios else '') + uuid.uuid4().hex
        self.send(dict(schemaVersion=1, commandId=request, action=action))
        return request

    def _packet(self, request, started):
        previous = started
        for attempt in range(51):
            need(self.guard() is not False)
            raw = self.original()
            try:
                value = decode(raw) if raw else None
            except ValueError:
                # Partial original writes can be retried. A complete malformed
                # matching packet is rejected by the caller's typed validator.
                value = None
            need(self.guard() is not False)
            current = self.monotonic()
            need(number(current, 0, 1e15) and current >= previous and current - started < 5)
            previous = current
            if type(value) is dict and value.get('requestId') == request:
                return value
            if attempt < 50:
                self.sleep(0.1)
        need(False)

    def read(self, after_sequence, *, after_cycle=0):
        try:
            need(integer(after_sequence) and after_sequence >= self.sequence and integer(after_cycle))
            started = self.monotonic()
            need(number(started, 0, 1e15))
            requested = self.clock_ms()
            request = self._request('feature-recorded-audio-observe')
            value = self._packet(request, started)
            epoch = value.get('capturedEpochMs') if self.ios else self.clock_ms()
            validate(value, request, self.pid, epoch)
            source = value['source']
            need(value['sequence'] > after_sequence and self.instance in (None, value['instance'])
                 and source['cycle'] >= self.cycle and source['cycle'] > after_cycle
                 and source['events'][-1]['eventSequence'] >= self.event_sequence
                 and (self.ios or value['requestedEpochMs'] >= requested))
            original = {}
            for kind in ('input', 'sink'):
                item = source[kind]
                need(self.guard() is not False)
                raw = self.bytes(item['name'])
                need(type(raw) is bytes and len(raw) == item['bytes']
                     and hashlib.sha256(raw).hexdigest() == item['sha256']
                     and self.guard() is not False)
                original[kind] = raw
            completed = self.monotonic()
            need(number(completed, 0, 1e15) and started <= completed and completed - started < 5)
            self.instance, self.sequence, self.cycle = value['instance'], value['sequence'], source['cycle']
            self.event_sequence = source['events'][-1]['eventSequence']
            return value, original
        except Exception:
            raise NativeUIError('Original recorded preview evidence is unavailable or invalid') from None

    def release(self):
        try:
            started = self.monotonic()
            need(number(started, 0, 1e15))
            request = self._request('feature-recorded-audio-release')
            value = self._packet(request, started)
            exact(value, {'schemaVersion', 'requestId', 'released'})
            need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['released'] is True)
            # A release acknowledgement cannot establish absence. Issue a
            # separate read-only native filesystem/memory query with a fresh ID.
            self.require_absent(started=started)
        except Exception:
            raise NativeUIError('Original recorded preview evidence cleanup is incomplete') from None

    def require_absent(self,*,started=None):
        """Fresh original absence without releasing or adopting any source."""
        try:
            if started is None:started=self.monotonic()
            need(number(started,0,1e15))
            request = self._request('feature-recorded-audio-files')
            observed = self._packet(request, started)
            validate_absence(observed,request,self.pid,observed['capturedEpochMs'] if self.ios else self.clock_ms(),instance=self.instance,after_sequence=self.sequence)
            for item, name in zip(observed['files'], (INPUT, SINK)):
                exact(item, {'name', 'exists'})
                need(item['name'] == name and item['exists'] is False)
                if not self.ios:
                    need(self.guard() is not False and self.bytes(name) is None and self.guard() is not False)
            completed = self.monotonic()
            need(number(completed, 0, 1e15) and started <= completed and completed - started < 5)
            need(self.guard() is not False)
            self.instance, self.sequence = observed['instance'], observed['sequence']
            return observed
        except Exception:
            raise NativeUIError('Original recorded preview evidence cleanup is incomplete') from None


READ_SCRIPT = r'''
[ -d files ] && [ ! -L files ] && [ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
p="files/overte-e2e/$1"
if [ ! -e "$p" ] && [ ! -L "$p" ]; then printf 'OVT_PREVIEW_MISSING_V1\n'; exit 0; fi
[ -f "$p" ] && [ ! -L "$p" ] && [ "$(stat -c %h "$p")" = 1 ] && [ "$(stat -c %a "$p")" = 600 ] || exit 1
n=$(stat -c %s "$p") || exit 1
[ "$n" -ge 0 ] && [ "$n" -le 33554432 ] || exit 1
printf 'OVT_PREVIEW_BYTES_V1\n'
head -c 33554433 "$p" || exit 1
printf '\nOVT_PREVIEW_BYTES_END_V1\n'
'''.strip()


class AndroidPreviewFiles:
    def __init__(self, adb, target, package, guard):
        AdbTransport._validate_debug_app_file(package, 'files/overte-e2e/' + INPUT)
        need(type(target) is str and bool(target) and callable(guard))
        self.adb, self.target, self.package, self.guard = adb, target, package, guard

    def __call__(self, name):
        try:
            need(name in (INPUT, SINK) and self.guard() is not False)
            remote = ' '.join(shlex.quote(v) for v in
                ('run-as', self.package, 'sh', '-c', READ_SCRIPT, 'overte-preview-evidence', name))
            raw = self.adb.execute_bytes(['exec-out', remote], target=self.target, timeout=5)
            need(type(raw) is bytes and self.guard() is not False)
            if raw == b'OVT_PREVIEW_MISSING_V1\n':
                return None
            start, end = b'OVT_PREVIEW_BYTES_V1\n', b'\nOVT_PREVIEW_BYTES_END_V1\n'
            need(raw.startswith(start) and raw.endswith(end) and len(raw) <= MAX_BYTES + len(start) + len(end))
            return raw[len(start):-len(end)]
        except Exception:
            raise NativeUIError('Original recorded preview file transport failed') from None
