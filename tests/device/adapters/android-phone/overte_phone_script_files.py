"""Closed Phone native Qt file-picker IO on the existing private probe channel."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import file_control, metadata_fields, validate_metadata

FILE = 'phone-script-file-ui.json'


def nonce(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{32}', value) is not None


def validate(value, command, pid, epoch):
    exact(value, {'schemaVersion', 'commandId', 'action', 'instance', 'generation', 'sourceSequence',
        'lastCommandSequence', 'elapsedMs', 'capturedEpochMs', 'processId', 'fileControlsVersion', 'ready', 'controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['commandId'] == command and value['action'] == 'observe'
         and nonce(value['instance']) and nonce(value['generation'])
         and integer(value['sourceSequence'], 1) and integer(value['lastCommandSequence'])
         and integer(value['elapsedMs']) and integer(value['processId'], 1) and value['processId'] == pid
         and type(value['fileControlsVersion']) is int and value['fileControlsVersion'] == 1
         and value['ready'] is True and type(value['controls']) is list and len(value['controls']) <= 384)
    fresh(value['capturedEpochMs'], epoch)
    ids, tokens = set(), set()
    for row in value['controls']:
        need(type(row) is dict and file_control(row.get('id')))
        exact(row, {'id', 'token', 'enabled', 'focused'} | metadata_fields(row['id']))
        need(nonce(row['token']) and row['token'] not in tokens and row['id'] not in ids
             and type(row['enabled']) is bool and type(row['focused']) is bool)
        validate_metadata(row)
        ids.add(row['id']); tokens.add(row['token'])
    return value


class PhoneScriptFileIO:
    wire_action = "phone-script-file-ui"
    validate_capture = staticmethod(validate)
    def __init__(self, send, read, clock_ms, guard, pid, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(value) for value in (send, read, clock_ms, guard, monotonic, sleep)) and integer(pid, 1))
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        self.monotonic, self.sleep = monotonic, sleep
        self.instance = self.generation = None
        self.sequence = self.elapsed = self.last_command = 0

    def _exchange(self, request):
        started = previous = self.monotonic()
        need(number(started, 0, 1e15) and self.guard() is not False)
        self.send(dict(schemaVersion=1, commandId=request['commandId'], action=self.wire_action, request=request))
        for attempt in range(51):
            need(self.guard() is not False)
            raw = self.original()
            try:
                value = decode(raw) if raw else None
            except json.JSONDecodeError:
                value = None
            need(self.guard() is not False)
            now = self.monotonic()
            need(number(now, 0, 1e15) and now >= previous and now - started < 5)
            previous = now
            if type(value) is dict and value.get('commandId') == request['commandId']: return value
            if attempt < 50: self.sleep(0.1)
        need(False)

    def capture(self):
        try:
            need(self.guard() is not False)
            barrier = self.clock_ms()
            need(integer(barrier, 1))
            request = dict(schemaVersion=1, commandId=uuid.uuid4().hex, action='observe')
            value = self._exchange(request)
            self.validate_capture(value, request['commandId'], self.pid, self.clock_ms())
            need(value['capturedEpochMs'] >= barrier and value['sourceSequence'] > self.sequence
                 and value['elapsedMs'] >= self.elapsed and value['lastCommandSequence'] >= self.last_command
                 and self.instance in (None, value['instance']) and self.generation in (None, value['generation'])
                 and self.guard() is not False)
            self.instance, self.generation, self.sequence = value['instance'], value['generation'], value['sourceSequence']
            self.elapsed, self.last_command = value['elapsedMs'], value['lastCommandSequence']
            return value
        except Exception:
            raise NativeUIError('Phone Script file UI source is unavailable or invalid') from None

    def input(self, identifier, action, *, source=None, text=None, index=None):
        try:
            need(file_control(identifier) and action in ('activate', 'replace', 'submit', 'select-index'))
            if action == 'replace':
                need(identifier == 'script-file.folder' and type(text) is str and len(text) <= 4096
                     and re.fullmatch(r'/(?:[^/\x00-\x1f]+/)*feature-script-[0-9a-f]{32}(?:/script-bundle)?', text)
                     and not any(part in ('.', '..') for part in text.split('/')))
            if action == 'submit': need(identifier == 'script-file.folder')
            if action == 'select-index': need(identifier == 'script-file.primary' and integer(index, 0, 31))
            observed = self.capture()
            rows = [row for row in observed['controls'] if row['id'] == identifier and row['enabled']]
            need(len(rows) == 1 and (source is None or rows[0].get('sourceUrl') == source)
                 and (action not in ('replace', 'submit', 'select-index') or rows[0]['focused']))
            request = dict(schemaVersion=1, commandId=uuid.uuid4().hex, action=action,
                instance=observed['instance'], generation=observed['generation'], sequence=observed['lastCommandSequence'] + 1,
                observedElapsedMs=observed['elapsedMs'], controlId=identifier, controlToken=rows[0]['token'])
            if action == 'replace': request['text'] = text
            if action == 'select-index': request['index'] = index
            self.deliver(request, observed)
        except Exception:
            raise NativeUIError('Phone Script file input delivery failed') from None


    def deliver(self, request, observed):
        value = self._exchange(request)
        exact(value, {'schemaVersion', 'commandId', 'action', 'performed', 'instance', 'generation', 'sequence', 'processId'})
        need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['performed'] is True
             and value['commandId'] == request['commandId'] and value['action'] == request['action']
             and value['instance'] == observed['instance'] and value['generation'] == observed['generation']
             and integer(value['sequence'], 1) and value['sequence'] == request['sequence']
             and integer(value['processId'], 1) and value['processId'] == self.pid and self.guard() is not False)
        self.last_command = request['sequence']

    def activate(self, identifier, *, source=None): self.input(identifier, 'activate', source=source)
    def replace(self, identifier, text): self.input(identifier, 'replace', text=text)
    def submit(self, identifier): self.input(identifier, 'submit')
    def select_index(self, identifier, index):
        self.activate(identifier)
        self.input(identifier, 'select-index', index=index)
