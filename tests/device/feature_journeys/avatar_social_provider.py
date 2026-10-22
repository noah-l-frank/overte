"""Real authenticated mutual-connection protocol for two owned principals.

This provider consumes actual client requests. It never handles peer Messages,
accepts UI verdicts, creates consent for a peer, or establishes rendered effects.
The trusted HTTPS listener and independent real client actor remain mandatory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import re
import secrets
import threading
import time
from urllib.parse import parse_qsl, unquote

from feature_journeys.contract import identifier, json_document

VERSION = 1
REQUEST = '/api/v1/user/connection_request'
USERS = '/api/v1/users'
CONNECTIONS = '/api/v1/users/connections'
DELETE = '/api/v1/user/connections/'


def session(value):
    if (type(value) is not str or re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value) is None
            or value == '00000000-0000-0000-0000-000000000000'):
        raise ValueError('Invalid original avatar session identity')
    return value


def body(raw, *, wrapped):
    if type(raw) is not bytes or not 0 < len(raw) <= 4096:
        raise ValueError('Invalid bounded social request body')
    value = json_document(raw.decode('utf-8'))
    if wrapped:
        if type(value) is not dict or set(value) != {'user_connection_request'}:
            raise ValueError('Invalid original connection envelope')
        value = value['user_connection_request']
    if type(value) is not dict or set(value) != {'node_id', 'proposed_node_id'}:
        raise ValueError('Invalid original connection participants')
    return session(value['node_id']), session(value['proposed_node_id'])


class AvatarSocialProvider:
    """Bounded actual backend rows and immutable request/write history.

    ``authenticate`` resolves a real Bearer grant to its actual username. It must
    return None for expired/revoked/foreign authority. Provisioning records two
    separately provisioned OAuth principals and observed avatar session IDs.
    It creates no relationship. Both directions require an actual POST, as in
    peopleConnection.js; GET polling cannot supply the missing participant.
    """
    def __init__(self, authenticate, *, epoch_ms=lambda: int(time.time()*1000), monotonic=time.monotonic):
        if not all(callable(fn) for fn in (authenticate, epoch_ms, monotonic)):
            raise ValueError('Invalid social provider boundaries')
        self.authenticate, self.epoch_ms, self.monotonic = authenticate, epoch_ms, monotonic
        self.lock = threading.RLock()
        self.instance = secrets.token_hex(16)
        self.runs, self.retired = {}, set()
        self.sequence = self.last_epoch = 0
        self.last_mono = 0.0

    def _now(self):
        epoch, mono = self.epoch_ms(), self.monotonic()
        if (type(epoch) is not int or epoch < max(1, self.last_epoch) or type(mono) not in (int, float)
                or not self.last_mono <= mono < 1e15):
            raise ValueError('Social provider clocks are unavailable')
        self.last_epoch, self.last_mono = epoch, mono
        return epoch, mono

    def provision(self, run, principals, sessions, domain):
        identifier(run); session(domain)
        if (type(principals) is not dict or set(principals) != {'primary', 'actor'}
                or type(sessions) is not dict or set(sessions) != set(principals)
                or len(set(principals.values())) != 2 or len(set(sessions.values())) != 2):
            raise ValueError('Two independent original principals and sessions are required')
        for name in principals.values():
            if type(name) is not str or re.fullmatch(r'e2e-[a-f0-9]{32}', name) is None:
                raise ValueError('Only owned account principals may be provisioned')
        for value in sessions.values(): session(value)
        with self.lock:
            if (run in self.runs or run in self.retired or len(self.runs) >= 32 or len(self.retired) >= 256
                    or any(set(principals.values()) & set(row['principals'].values())
                           or set(sessions.values()) & set(row['sessions'].values()) for row in self.runs.values())):
                raise ValueError('Social scope is reused or provider is full')
            self._now()
            self.runs[run] = dict(principals=deepcopy(principals), sessions=deepcopy(sessions), domain=domain,
                ticket=None, pending={}, connected=False, active=True, inflight=0, history=[], dropped=0)

    def activate(self, run, ticket):
        with self.lock:
            row = self.runs[identifier(run)]
            if not row['active']: raise ValueError('Social scope is retired')
            row['ticket'] = identifier(ticket)

    def _event(self, run, kind, **facts):
        row = self.runs[run]
        self.sequence += 1
        result = dict(eventSequence=self.sequence, capturedEpochMs=self._now()[0],
                      runId=run, ticket=row['ticket'], kind=kind, **facts)
        row['history'].append(result)
        if len(row['history']) > 1024:
            row['history'].pop(0); row['dropped'] += 1
        return result

    def _principal(self, authorization):
        if type(authorization) is not str or len(authorization) > 512:
            return None
        principal = self.authenticate(authorization)
        for run, row in self.runs.items():
            if row['active']:
                for role, username in row['principals'].items():
                    if principal == username: return run, role
        return None

    @contextmanager
    def response(self, method, path, query, raw, authorization):
        """Hold actual request ownership through the listener's socket write.

        Yields (status, original serialized bytes, response UUID, write callback).
        The listener must invoke the callback only after the complete write. A
        broken/missing write remains unresolved and prevents retirement.
        """
        with self.lock:
            principal = self._principal(authorization)
            if principal is None:
                yield 401, b'{"status":"fail","error":"unauthorized"}', None, None
                return
            run, role = principal; row = self.runs[run]
            if row['ticket'] is None or row['inflight'] >= 16 or row['dropped']:
                raise ValueError('Social request has no current bounded owner')
            self._now(); response_id = secrets.token_hex(16)
            row['inflight'] += 1
            event = self._event(run, 'request', responseId=response_id, role=role, method=method,
                path=path, query=query, bodyBytes=len(raw), bodySha256=hashlib.sha256(raw).hexdigest(),
                status=None, responseBytes=None, responseSha256=None, written=False, writeEpochMs=None)
            try:
                status, value = self._handle(row, role, method, path, query, raw)
                serialized = json.dumps(value, separators=(',', ':'), sort_keys=True).encode()
                event.update(status=status, responseBytes=len(serialized), responseSha256=hashlib.sha256(serialized).hexdigest())
                wrote = False
                def written(actual):
                    nonlocal wrote
                    if (wrote or type(actual) is not dict or set(actual) != {'status', 'responseId', 'bytes', 'sha256'}
                            or actual != dict(status=status, responseId=response_id, bytes=len(serialized),
                                              sha256=hashlib.sha256(serialized).hexdigest())):
                        raise ValueError('Original social response write differs from supplied bytes')
                    event.update(written=True, writeEpochMs=self._now()[0]); wrote = True
                yield status, serialized, response_id, written
            finally:
                row['inflight'] -= 1

    def _handle(self, row, role, method, path, query, raw):
        peer = 'actor' if role == 'primary' else 'primary'
        now = self._now()[1]
        row['pending'] = {key: value for key, value in row['pending'].items() if now-value < 12}
        if path == REQUEST and method in ('POST', 'GET'):
            if method == 'POST':
                if query: raise ValueError('POST connection request has unexpected query')
                own, target = body(raw, wrapped=True)
            else:
                if raw: raise ValueError('GET connection polling has unexpected body')
                pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
                values = dict(pairs)
                if len(pairs) != 2 or set(values) != {'node_id', 'proposed_node_id'}:
                    raise ValueError('Invalid original connection poll')
                own, target = session(values['node_id']), session(values['proposed_node_id'])
            if own != row['sessions'][role] or target != row['sessions'][peer]:
                return 403, dict(status='fail', error='foreign-participant')
            if method == 'POST': row['pending'].setdefault(role, now)
            if len(row['pending']) == 2:
                row['connected'] = True; row['pending'].clear()
            if row['connected']:
                return 200, dict(status='success', connection=dict(username=row['principals'][peer]))
            return 200, dict(status='success', connection='pending')
        if path in (USERS, CONNECTIONS) and method == 'GET' and raw == b'':
            values = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=6)
            params = dict(values)
            if (len(params) != len(values) or set(params) - {'filter', 'per_page', 'search', 'status', 'page', 'sort'}
                    or params.get('filter', '') not in ('', 'connections')
                    or not params.get('per_page', '400').isdigit()
                    or not 1 <= int(params.get('per_page', '400')) <= (1000 if path == CONNECTIONS else 400)
                    or not params.get('page', '1').isdigit() or not 1 <= int(params.get('page', '1')) <= 32
                    or ('sort' in params and params['sort'] not in
                        {column+','+order for column in ('username', 'is_friend', 'location') for order in ('ASC', 'DESC')})
                    or ('status' in params and params['status'] not in ('online', row['domain']))):
                raise ValueError('Unsupported original social directory request')
            found = row['connected'] or path != CONNECTIONS and params.get('filter') != 'connections'
            if params.get('search') and params['search'] not in row['principals'][peer]: found = False
            if int(params.get('page', '1')) != 1: found = False
            users = [dict(username=row['principals'][peer], connection='connection' if row['connected'] else '',
                location=dict(node_id=row['sessions'][peer], domain=dict(name='Owned domain')),
                images=dict(thumbnail=''))] if found else []
            value = dict(status='success', data=dict(users=users))
            if path == CONNECTIONS:
                value.update(current_page=int(params.get('page', '1')), total_pages=1, total_entries=int(row['connected']))
            return 200, value
        if path.startswith(DELETE) and not query and method == 'DELETE' and raw == b'':
            target = unquote(path[len(DELETE):], errors='strict')
            if '/' in target or target != row['principals'][peer]:
                return 403, dict(status='fail', error='foreign-participant')
            row['connected'] = False; row['pending'].clear()
            return 200, dict(status='success')
        return 405, dict(status='fail', error='method-not-allowed')

    def snapshot(self, run):
        with self.lock:
            row = self.runs[identifier(run)]
            now, mono = self._now()
            row['pending'] = {key: value for key, value in row['pending'].items() if mono-value < 12}
            return dict(avatarSocialVersion=VERSION, instance=self.instance, runId=run, ticket=row['ticket'],
                capturedEpochMs=now, eventSequence=self.sequence, active=row['active'],
                connected=row['connected'], pendingRoles=sorted(row['pending']), inflightRequests=row['inflight'],
                complete=row['dropped'] == 0, history=deepcopy(row['history']))

    def revoke(self, run):
        """Revoke scope only; never silently remove an uncleaned relationship."""
        with self.lock:
            row = self.runs[identifier(run)]
            if row['connected'] or row['pending'] or row['inflight'] or any(not e['written'] for e in row['history']):
                raise ValueError('Actual social resources or unresolved responses remain')
            row['active'] = False

    def retire(self, run):
        with self.lock:
            row = self.runs[identifier(run)]
            if row['active'] or row['connected'] or row['pending'] or row['inflight'] or row['dropped']:
                raise ValueError('Social scope is not cleanly retired')
            del self.runs[run]; self.retired.add(run)
