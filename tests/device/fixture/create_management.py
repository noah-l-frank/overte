#!/usr/bin/env python3
"""Owned read-only Create observer and normal JSON-import fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from create_observation import PREFIX, entity_rows
from script_management import Handler as SharedHandler, ScriptServer

OBSERVER = Path(__file__).with_suffix('') / 'observer.js'
ROUTE = re.compile(r'/create/([0-9a-f]{32})/(observer\.js|entities\.json|missing\.json|events|observation)')


class CreateJournal:
    def __init__(self, monotonic=time.monotonic):
        self._lock = threading.Lock()
        self._sessions = {}
        self.monotonic = monotonic
        self.source = OBSERVER.read_bytes()
        self.source_sha256 = hashlib.sha256(self.source).hexdigest()

    def create(self):
        with self._lock:
            if len(self._sessions) >= 16:
                raise ValueError('Owned Create session limit reached')
            nonce = secrets.token_hex(16)
            self._sessions[nonce] = {'nonce': nonce, 'token': secrets.token_hex(32),
                'sampleSequence': 0, 'sourceGets': 0, 'importGets': 0, 'missingGets': 0,
                'frame': None, 'lastPayload': None}
            return nonce

    @staticmethod
    def imported_entities(nonce):
        parent_id = str(uuid.uuid5(uuid.NAMESPACE_URL, nonce + '-parent'))
        child_id = str(uuid.uuid5(uuid.NAMESPACE_URL, nonce + '-child'))
        prefix = PREFIX + nonce + '_'
        return {'DataVersion': 3, 'Entities': [
            {'id': '{' + parent_id + '}', 'type': 'Shape', 'shape': 'Cube',
             'name': prefix + 'import-parent', 'position': {'x': 0, 'y': 1, 'z': 0},
             'dimensions': {'x': 0.5, 'y': 0.5, 'z': 0.5},
             'color': {'red': 210, 'green': 40, 'blue': 70}},
            {'id': '{' + child_id + '}', 'parentID': '{' + parent_id + '}',
             'type': 'Shape', 'shape': 'Cube', 'name': prefix + 'import-child',
             'localPosition': {'x': 0.75, 'y': 0, 'z': 0},
             'dimensions': {'x': 0.25, 'y': 0.25, 'z': 0.25},
             'color': {'red': 30, 'green': 180, 'blue': 230}}]}

    def resource(self, nonce, name, origin):
        with self._lock:
            state = self._sessions[nonce]
            if name == 'observer.js':
                config = {'prefix': PREFIX + nonce + '_', 'receiptToken': state['token'],
                          'eventsUrl': origin + f'/create/{nonce}/events'}
                return ('var OVERTE_CREATE_SESSION = ' + json.dumps(config) + ';\n').encode() + self.source
            if name == 'entities.json':
                return json.dumps(self.imported_entities(nonce)).encode()
            return None

    def delivered(self, nonce, name):
        field = {'observer.js': 'sourceGets', 'entities.json': 'importGets', 'missing.json': 'missingGets'}[name]
        with self._lock:
            self._sessions[nonce][field] += 1

    def receive(self, nonce, value):
        fields = {'token', 'instance', 'sequence', 'complete', 'error', 'queriedEntityCount', 'entities'}
        if (not isinstance(value, dict) or set(value) != fields
                or not isinstance(value['token'], str)
                or not isinstance(value['instance'], str) or re.fullmatch('[0-9a-f]{32}', value['instance']) is None
                or type(value['sequence']) is not int or not 0 <= value['sequence'] <= 4095
                or type(value['complete']) is not bool
                or not isinstance(value['error'], str)
                or type(value['queriedEntityCount']) is not int or not 0 <= value['queriedEntityCount'] <= 4096):
            raise ValueError('Create native observation envelope is invalid')
        if ((value['complete'] and value['error'] != '')
                or not value['complete'] and (value['error'] not in {
                    'query-budget', 'matching-entity-budget', 'entity-read-error'} or value['entities'] != [])):
            raise ValueError('Create observation completeness is inconsistent')
        entity_rows(value['entities'], nonce)
        with self._lock:
            state = self._sessions[nonce]
            if not secrets.compare_digest(value['token'], state['token']):
                raise ValueError('Create observer receipt does not match the owned session')
            frame = state['frame']
            if frame is None:
                if value['sequence'] != 0:
                    raise ValueError('Create observer lacks its initial native frame')
            else:
                if value['instance'] != frame['instance']:
                    raise ValueError('Create observer engine unexpectedly restarted')
                if value['sequence'] == frame['sequence'] and value == state['lastPayload']:
                    return
                if value['sequence'] != frame['sequence'] + 1:
                    raise ValueError('Create observer native frames were replayed, changed or skipped')
            state['lastPayload'] = copy.deepcopy(value)
            state['frame'] = {key: copy.deepcopy(item) for key, item in value.items() if key != 'token'}
            state['frame']['receivedMonotonicSeconds'] = self.monotonic()

    def observe(self, nonce):
        with self._lock:
            state = self._sessions[nonce]
            state['sampleSequence'] += 1
            return {'schemaVersion': 1, 'nonce': nonce, 'sourceSha256': self.source_sha256,
                'sampleSequence': state['sampleSequence'], 'sampleMonotonicSeconds': self.monotonic(),
                **{field: state[field] for field in ('sourceGets', 'importGets', 'missingGets')},
                'frame': copy.deepcopy(state['frame'])}

    def remove(self, nonce):
        with self._lock:
            self._sessions.pop(nonce, None)


class CreateServer(ScriptServer):
    def __init__(self, address, public_host=None):
        super().__init__(address, public_host, journal=CreateJournal(), handler=CreateHandler)


class CreateHandler(SharedHandler):
    def route(self):
        return ROUTE.fullmatch(self.path)

    def body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if self.headers.get('Transfer-Encoding') or not 0 < length <= 32768:
            raise ValueError('Bounded Create JSON body required')
        return json.loads(self.rfile.read(length))

    def do_POST(self):
        if self.path == '/create/sessions':
            if not self.authorize():
                return
            try:
                if self.body() != {}:
                    raise ValueError('Registration identity is server-owned')
                nonce = self.server.journal.create()
            except (ValueError, OSError):
                self.send(400)
                return
            base = self.server.origin + f'/create/{nonce}/'
            self.send(200, json.dumps({'schemaVersion': 1, 'nonce': nonce,
                'sourceSha256': self.server.journal.source_sha256,
                'observerUrl': base + 'observer.js', 'importUrl': base + 'entities.json',
                'missingUrl': base + 'missing.json', 'prefix': PREFIX + nonce + '_'}).encode())
            return
        route = self.route()
        if route is None or route[2] != 'events':
            self.send(404)
            return
        try:
            self.server.journal.receive(route[1], self.body())
        except KeyError:
            self.send(404)
            return
        except (ValueError, OSError):
            self.send(400)
            return
        self.send(200, b'{}')

    def do_GET(self):
        if self.path == '/healthz':
            self.send(200, b'{"ready":true}')
            return
        route = self.route()
        if route is None:
            self.send(404)
            return
        nonce, name = route.groups()
        if name == 'observation':
            if not self.authorize():
                return
            try:
                value = self.server.journal.observe(nonce)
            except KeyError:
                self.send(404)
                return
            self.send(200, json.dumps(value).encode())
            return
        if name not in {'observer.js', 'entities.json', 'missing.json'}:
            self.send(404)
            return
        try:
            payload = self.server.journal.resource(nonce, name, self.server.origin)
        except KeyError:
            self.send(404)
            return
        self.send(404 if payload is None else 200, payload or b'',
                  'application/javascript' if name == 'observer.js' else 'application/json')
        self.server.journal.delivered(nonce, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--public-host')
    parser.add_argument('--ready-file', required=True, type=Path)
    args = parser.parse_args()
    if args.ready_file.exists():
        parser.error('Ready file already exists; preserve the existing fixture ownership')
    server = CreateServer((args.bind, args.port), args.public_host)
    ready = {'schemaVersion': 1, 'environment': {
        'OVERTE_E2E_CREATE_FIXTURE_URL': server.origin,
        'OVERTE_E2E_CREATE_CONTROL_TOKEN': server.control_token}}
    args.ready_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.ready_file.with_suffix('.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        temporary.chmod(0o600)
        stream.write(json.dumps(ready) + '\n')
    temporary.replace(args.ready_file)
    print('Owned Create fixture ready; private environment file written.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
