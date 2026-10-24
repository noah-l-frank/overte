"""Closed native inputs and independent script-fixture observation validation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit

OPERATIONS = {'scripts.manager.open', 'scripts.manager.close', 'scripts.load-url',
              'scripts.restart', 'scripts.stop'}
SCRIPT_PATH = re.compile(r'/script-management/([0-9a-f]{32})/(client|missing)\.js')


def script_url(value, *, missing=False):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError('Owned script URL must be a bounded string')
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError:
        raise ValueError('Owned script URL port is invalid') from None
    match = SCRIPT_PATH.fullmatch(parsed.path)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or match is None
            or match[2] != ('missing' if missing else 'client')):
        raise ValueError('Owned script URL must identify the exact fixture session source')
    return match[1]


def action_arguments(operation, value):
    fields = set() if operation in {'scripts.manager.open', 'scripts.manager.close'} else {'url'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Script manager action contains unsupported fields')
    if fields:
        missing = operation == 'scripts.load-url' and isinstance(value['url'], str) and value['url'].endswith('/missing.js')
        script_url(value['url'], missing=missing)
    return value


def observation(value, nonce, expected_source):
    fields = {'schemaVersion', 'nonce', 'sampleSequence', 'sourceGets',
              'companionGets', 'missingGets', 'instances', 'sourceSha256', 'sampleMonotonicSeconds'}
    if (not isinstance(value, dict) or set(value) != fields
            or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
            or value['nonce'] != nonce or value['sourceSha256'] != expected_source):
        raise ValueError('Script observation belongs to a different or invalid session')
    for field in ('sampleSequence', 'sourceGets', 'companionGets', 'missingGets'):
        if type(value[field]) is not int or value[field] < (1 if field == 'sampleSequence' else 0):
            raise ValueError('Script observation counters are invalid')
    captured = value['sampleMonotonicSeconds']
    if type(captured) not in (int, float) or not math.isfinite(captured):
        raise ValueError('Script observer capture time is invalid')
    rows = value['instances']
    if not isinstance(rows, list) or len(rows) > 8:
        raise ValueError('Script instance observations exceed the bounded count')
    previous_id = ''
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'events'}
                or not isinstance(row['id'], str) or re.fullmatch('[0-9a-f]{32}', row['id']) is None
                or row['id'] <= previous_id):
            raise ValueError('Script instances must have sorted unique execution identities')
        previous_id = row['id']
        events = row['events']
        if not isinstance(events, list) or not 1 <= len(events) <= 2048:
            raise ValueError('Script events exceed the bounded count')
        previous_time = None
        for sequence, event in enumerate(events):
            if (not isinstance(event, dict) or set(event) != {'sequence', 'kind', 'receivedMonotonicSeconds'}
                    or type(event['sequence']) is not int or event['sequence'] != sequence
                    or event['kind'] != ('start' if sequence == 0 else 'tick')):
                raise ValueError('Script events were reordered, skipped or replayed')
            when = event['receivedMonotonicSeconds']
            if (type(when) not in (int, float) or not math.isfinite(when)
                    or when > captured
                    or previous_time is not None and when <= previous_time):
                raise ValueError('Script event reception times are invalid')
            previous_time = when
    return value


class FreshJournal:
    def __init__(self, nonce):
        self.nonce = nonce
        self.previous = None
        self.expected_source = hashlib.sha256((Path(__file__).resolve().parent
            / 'fixture/script_management/client.js').read_bytes()).hexdigest()

    def accept(self, value):
        value = observation(value, self.nonce, self.expected_source)
        if self.previous is not None:
            before = self.previous
            if value['sampleSequence'] <= before['sampleSequence']:
                raise ValueError('Script observer replayed an earlier snapshot')
            if value['sampleMonotonicSeconds'] < before['sampleMonotonicSeconds']:
                raise ValueError('Script observer capture time moved backwards')
            if any(value[field] < before[field] for field in ('sourceGets', 'companionGets', 'missingGets')):
                raise ValueError('Script delivery history moved backwards')
            current = {row['id']: row['events'] for row in value['instances']}
            if any(row['id'] not in current or current[row['id']][:len(row['events'])] != row['events']
                   for row in before['instances']):
                raise ValueError('Script execution history was removed or rewritten')
        self.previous = value
        return value
