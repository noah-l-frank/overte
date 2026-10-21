"""Original owned missing-Script HTTP writes and challenge clock, never state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from .contract import exact, identifier, number

VERSION = 1
BODY = b'{"error":"not-found"}'


def authority(value):
    if (type(value) is not str or not 0 < len(value) <= 512 or not value.isascii()
            or any(ord(char) <= 32 for char in value) or any(char in value for char in '/\\?#@%')):
        raise ValueError('Original Script request authority is invalid')
    parsed = urlsplit('//'+value)
    if not parsed.hostname or parsed.path or parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Original Script request authority is invalid')
    return parsed.hostname.lower(), parsed.port


class ScriptResources:
    def __init__(self, *, clock_ms=lambda: int(time.time() * 1000)):
        if not callable(clock_ms): raise ValueError('Original Script fixture clock is required')
        self.clock_ms, self.instance = clock_ms, secrets.token_hex(16)
        self.lock, self.runs = threading.RLock(), {}
        self.last_epoch, self.failed, self.valid = 0, 0, True

    def epoch(self):
        now = self.clock_ms()
        if type(now) is not int or now <= 0 or now < self.last_epoch:
            self.valid = False
            raise ValueError('Script fixture clock is unavailable')
        self.last_epoch = now
        return now

    def ready(self):
        with self.lock:
            return dict(scriptProviderVersion=VERSION, instance=self.instance, capturedEpochMs=self.epoch(),
                ready=self.valid and not self.failed and len(self.runs) < 32,
                activeRuns=sum(row['active'] for row in self.runs.values()), failedResponses=self.failed)

    def has_run(self, run):
        with self.lock: return run in self.runs

    def provision(self, run):
        identifier(run)
        with self.lock:
            if not self.valid or self.failed or run in self.runs or len(self.runs) >= 32 or any(row['active'] for row in self.runs.values()):
                raise ValueError('Script fixture ownership is unavailable')
            self.epoch()
            self.runs[run] = dict(active=True, ticket=None, activations=[], responses=[])

    def activate(self, run, ticket):
        identifier(ticket)
        with self.lock:
            row = self.runs[identifier(run)]
            if not self.valid or self.failed or not row['active'] or len(row['activations']) >= 256 or any(item['ticket'] == ticket for item in row['activations']):
                raise ValueError('Script fixture challenge is unavailable')
            row['activations'].append(dict(sequence=len(row['activations']) + 1, ticket=ticket, activatedEpochMs=self.epoch()))
            row['ticket'] = ticket

    def snapshot(self, run, request_id=None):
        request_id = secrets.token_hex(16) if request_id is None else identifier(request_id)
        with self.lock:
            row = self.runs[identifier(run)]
            return dict(scriptProviderVersion=VERSION, instance=self.instance, runId=run, requestId=request_id,
                capturedEpochMs=self.epoch(), healthy=self.valid and not self.failed,
                active=row['active'], ticket=row['ticket'], activations=deepcopy(row['activations']),
                responses=deepcopy(row['responses']), failedResponses=self.failed)

    def retire(self, run):
        with self.lock:
            row = self.runs[identifier(run)]
            row.update(active=False, ticket=None)

    @contextmanager
    def response(self, run, ticket, *, request_authority, request_scheme):
        identifier(run); identifier(ticket)
        authority(request_authority)
        if request_scheme not in ('http','https'):raise ValueError('Original Script request transport is invalid')
        # Same lock through the bounded original socket write: challenge change
        # and cleanup cannot overtake an in-flight owned reply.
        with self.lock:
            row = self.runs.get(run)
            if row is None or not self.valid or self.failed or not row['active'] or row['ticket'] != ticket:
                yield None
                return
            if len(row['responses']) >= 256:
                self.valid = False
                yield None
                return
            started, response_id = self.epoch(), secrets.token_hex(16)
            observed = []
            def actual_write(value):
                exact(value, {'responseId', 'status', 'bytes', 'sha256'}, 'original Script socket write')
                if (observed or value['responseId'] != response_id or type(value['status']) is not int
                        or not 100 <= value['status'] <= 599 or type(value['bytes']) is not int or not 0 < value['bytes'] <= 4096
                        or type(value['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', value['sha256']) is None):
                    raise ValueError('Original Script socket write is unavailable')
                observed.append(deepcopy(value))
            try:
                yield 404, BODY, response_id, actual_write
                if len(observed) != 1: raise ValueError('Original Script socket write was not observed')
                completed = self.epoch()
            except BaseException:
                self.failed += 1
                raise
            else:
                row['responses'].append(dict(sequence=len(row['responses']) + 1, responseId=response_id,
                    ticket=ticket, status=observed[0]['status'], bytes=observed[0]['bytes'], sha256=observed[0]['sha256'],
                    requestAuthority=request_authority, requestScheme=request_scheme,
                    startedEpochMs=started, completedEpochMs=completed))


def validate_status(value, *, instance, run, previous=None, request_id=None):
    exact(value, {'scriptProviderVersion', 'instance', 'runId', 'requestId', 'capturedEpochMs', 'healthy', 'active',
                  'ticket', 'activations', 'responses', 'failedResponses'}, 'original Script provider status')
    identifier(instance); identifier(run)
    identifier(value['requestId'])
    if request_id is not None and value['requestId'] != identifier(request_id):
        raise ValueError('Original Script provider snapshot belongs to another request')
    if (type(value['scriptProviderVersion']) is not int or value['scriptProviderVersion'] != VERSION
            or value['instance'] != instance or value['runId'] != run or value['healthy'] is not True
            or type(value['active']) is not bool or type(value['failedResponses']) is not int or value['failedResponses'] != 0
            or type(value['capturedEpochMs']) is not int or value['capturedEpochMs'] <= 0
            or any(type(value[key]) is not list or len(value[key]) > 256 for key in ('activations', 'responses'))):
        raise ValueError('Original Script provider is unavailable or changed')
    tickets, epoch = {}, 0
    for sequence, row in enumerate(value['activations'], 1):
        exact(row, {'sequence', 'ticket', 'activatedEpochMs'}, 'original Script challenge')
        identifier(row['ticket'])
        if (type(row['sequence']) is not int or row['sequence'] != sequence or row['ticket'] in tickets
                or type(row['activatedEpochMs']) is not int or not epoch <= row['activatedEpochMs'] <= value['capturedEpochMs']
                or row['activatedEpochMs'] <= 0): raise ValueError('Invalid original Script challenge history')
        epoch = row['activatedEpochMs']; tickets[row['ticket']] = epoch
    expected = value['activations'][-1]['ticket'] if value['active'] and value['activations'] else None
    if value['ticket'] != expected: raise ValueError('Script provider retained a stale or retired challenge')
    response_ids, epoch = set(), 0
    for sequence, row in enumerate(value['responses'], 1):
        exact(row, {'sequence', 'responseId', 'ticket', 'status', 'bytes', 'sha256', 'requestAuthority', 'requestScheme', 'startedEpochMs', 'completedEpochMs'},
              'original missing Script HTTP receipt')
        identifier(row['responseId']); identifier(row['ticket'])
        authority(row['requestAuthority'])
        if (type(row['sequence']) is not int or row['sequence'] != sequence or row['responseId'] in response_ids
                or row['ticket'] not in tickets or type(row['status']) is not int or row['status'] != 404
                or row['requestScheme'] not in ('http','https')
                or type(row['bytes']) is not int or row['bytes'] != len(BODY)
                or type(row['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None
                or row['sha256'] != hashlib.sha256(BODY).hexdigest()
                or type(row['startedEpochMs']) is not int or type(row['completedEpochMs']) is not int
                or not max(epoch, tickets[row['ticket']]) <= row['startedEpochMs'] <= row['completedEpochMs'] <= value['capturedEpochMs']):
            raise ValueError('Invalid original missing Script HTTP receipt')
        response_ids.add(row['responseId']); epoch = row['completedEpochMs']
    if previous is not None:
        if (value['capturedEpochMs'] < previous['capturedEpochMs'] or not previous['active'] and value['active']
                or any(len(value[key]) < len(previous[key]) or value[key][:len(previous[key])] != previous[key]
                       for key in ('activations', 'responses'))):
            raise ValueError('Original Script history changed or resurrected')
    return value


def missing_receipt(value, *, run, ticket, fixture_url, after_epoch):
    """One original current HTTP failure, independently of native/UI error.

    The owning reader must have verified this snapshot's fresh request nonce,
    pinned provider and wall-clock age. Scope inputs are never returned as facts.
    """
    identifier(ticket);number(after_epoch,1)
    validate_status(value,instance=value['instance'],run=run)
    if type(fixture_url) is not str or '?' in fixture_url or '#' in fixture_url or '%' in fixture_url:
        raise ValueError('Owned Script fixture origin is invalid')
    origin=urlsplit(fixture_url)
    if (origin.scheme not in ('http','https') or not origin.hostname or origin.username is not None or origin.password is not None
            or origin.path!='/feature-fixture/v1/runs/'+run+'/'):
        raise ValueError('Owned Script fixture origin is invalid')
    default=443 if origin.scheme=='https' else 80
    if not value['active'] or value['ticket']!=ticket:raise ValueError('Original Script HTTP challenge is retired or foreign')
    rows=[row for row in value['responses'] if row['ticket']==ticket]
    if len(rows)!=1:raise ValueError('One original current owned Script HTTP failure is required')
    row=rows[0];host,port=authority(row['requestAuthority'])
    if (row['startedEpochMs']<after_epoch or row['requestScheme']!=origin.scheme
            or host!=origin.hostname.lower() or (port or default)!=(origin.port or default)):
        raise ValueError('Original Script HTTP failure belongs to a different origin or barrier')
    return deepcopy(row)
