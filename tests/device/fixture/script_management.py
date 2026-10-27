#!/usr/bin/env python3
"""Owned HTTP observations for the normal Running Scripts lifecycle journey."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

CLIENT = Path(__file__).with_suffix('') / 'client.js'
SESSION_PATH = re.compile(r'/script-management/([0-9a-f]{32})/(client\.js|companion\.js|missing\.js|events|observation)')


class Journal:
    def __init__(self, monotonic=time.monotonic):
        self._lock = threading.Lock()
        self._sessions = {}
        self.monotonic = monotonic
        self.client_source = CLIENT.read_bytes()
        self.source_sha256 = hashlib.sha256(self.client_source).hexdigest()

    def create(self):
        with self._lock:
            if len(self._sessions) >= 16:
                raise ValueError('Owned script session limit reached')
            nonce = secrets.token_hex(16)
            self._sessions[nonce] = {'nonce': nonce, 'token': secrets.token_hex(32),
                'proof': secrets.token_hex(32), 'sampleSequence': 0,
                'sourceGets': 0, 'companionGets': 0, 'missingGets': 0,
                'instances': {}}
            return nonce

    def source(self, nonce, name, origin):
        with self._lock:
            state = self._sessions[nonce]
            if name == 'client.js':
                config = {'eventsUrl': origin + f'/script-management/{nonce}/events',
                          'receiptToken': state['token']}
                return ('var OVERTE_SCRIPT_MANAGEMENT_SESSION = '
                        + json.dumps(config) + ';\n').encode() + self.client_source
            if name == 'companion.js':
                return ('var OVERTE_SCRIPT_MANAGEMENT_COMPANION = '
                        + json.dumps(state['proof']) + ';\n').encode()
            return None

    def delivered(self, nonce, name):
        field = {'client.js': 'sourceGets', 'companion.js': 'companionGets',
                 'missing.js': 'missingGets'}[name]
        with self._lock:
            self._sessions[nonce][field] += 1

    def receive(self, nonce, value):
        if not isinstance(value, dict) or set(value) != {
                'token', 'instance', 'sequence', 'kind', 'companionProof'}:
            raise ValueError('Invalid script execution event')
        instance, sequence = value['instance'], value['sequence']
        if (not isinstance(instance, str) or re.fullmatch('[0-9a-f]{32}', instance) is None
                or type(sequence) is not int or not 0 <= sequence <= 2047
                or value['kind'] != ('start' if sequence == 0 else 'tick')
                or not isinstance(value['token'], str)
                or not isinstance(value['companionProof'], str)):
            raise ValueError('Invalid script execution identity or sequence')
        with self._lock:
            state = self._sessions[nonce]
            if (not secrets.compare_digest(value['token'], state['token'])
                    or not secrets.compare_digest(value['companionProof'], state['proof'])):
                raise ValueError('Script execution event does not match the served companion')
            instances = state['instances']
            if instance not in instances:
                if sequence != 0 or len(instances) >= 8:
                    raise ValueError('New script instance lacks its initial event')
                instances[instance] = []
            events = instances[instance]
            if events and sequence == events[-1]['sequence']:
                return  # Lost HTTP acknowledgments may retry; retries add no activity.
            if sequence != len(events):
                raise ValueError('Script execution sequence was replayed or skipped')
            events.append({'sequence': sequence, 'kind': value['kind'],
                           'receivedMonotonicSeconds': self.monotonic()})

    def observe(self, nonce):
        with self._lock:
            state = self._sessions[nonce]
            state['sampleSequence'] += 1
            return {'schemaVersion': 1, 'nonce': nonce,
                    'sourceSha256': self.source_sha256,
                    'sampleMonotonicSeconds': self.monotonic(),
                    **{field: state[field] for field in
                       ('sampleSequence', 'sourceGets', 'companionGets', 'missingGets')},
                    'instances': [{'id': instance, 'events': [dict(event) for event in events]}
                                  for instance, events in sorted(state['instances'].items())]}

    def remove(self, nonce):
        with self._lock:
            self._sessions.pop(nonce, None)


class ScriptServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, _request, _client_address):
        print('Owned script fixture transport failed; private request details omitted.', flush=True)

    def __init__(self, address, public_host=None, *, journal=None, handler=None):
        self.journal = journal if journal is not None else Journal()
        self.control_token = secrets.token_hex(32)
        super().__init__(address, handler or Handler)
        host = public_host or address[0]
        if not host or host in {'0.0.0.0', '::'} or any(c in host for c in '/?#@\r\n'):
            self.server_close()
            raise ValueError('An explicit device-reachable public host is required')
        if ':' in host and not host.startswith('['):
            host = '[' + host + ']'
        self.origin = f'http://{host}:{self.server_address[1]}'


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, _format, *_arguments):
        pass  # Never print request identities, headers or private receipt bytes.

    def send(self, status, payload=b'', content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()

    def authorize(self):
        expected = 'Bearer ' + self.server.control_token
        if not secrets.compare_digest(self.headers.get('Authorization', ''), expected):
            self.send(403)
            return False
        return True

    def route(self):
        parsed = urlsplit(self.path)
        return SESSION_PATH.fullmatch(parsed.path) if not parsed.query else None

    def body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if self.headers.get('Transfer-Encoding') or not 0 < length <= 4096:
            raise ValueError('Bounded JSON body required')
        return json.loads(self.rfile.read(length))

    def do_POST(self):
        if self.path == '/script-management/sessions':
            if not self.authorize():
                return
            try:
                if self.body() != {}:
                    raise ValueError('Registration has no client-selected identity')
                nonce = self.server.journal.create()
            except (ValueError, OSError):
                self.send(400)
                return
            self.send(200, json.dumps({'schemaVersion': 1, 'nonce': nonce,
                'sourceSha256': self.server.journal.source_sha256,
                'scriptUrl': self.server.origin + f'/script-management/{nonce}/client.js',
                'missingUrl': self.server.origin + f'/script-management/{nonce}/missing.js'}).encode())
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
        if name not in {'client.js', 'companion.js', 'missing.js'}:
            self.send(404)
            return
        try:
            payload = self.server.journal.source(nonce, name, self.server.origin)
        except KeyError:
            self.send(404)
            return
        self.send(404 if payload is None else 200, payload or b'', 'application/javascript')
        self.server.journal.delivered(nonce, name)

    def do_DELETE(self):
        route = self.route()
        if route is None or route[2] != 'observation':
            self.send(404)
            return
        if self.authorize():
            self.server.journal.remove(route[1])
            self.send(200, b'{}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--public-host')
    parser.add_argument('--ready-file', required=True, type=Path)
    args = parser.parse_args()
    if args.ready_file.exists():
        parser.error('Ready file already exists; preserve the existing fixture ownership')
    server = ScriptServer((args.bind, args.port), args.public_host)
    ready = {'schemaVersion': 1, 'environment': {
        'OVERTE_E2E_SCRIPTS_FIXTURE_URL': server.origin,
        'OVERTE_E2E_SCRIPTS_CONTROL_TOKEN': server.control_token}}
    args.ready_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.ready_file.with_suffix('.tmp')
    # The bearer token goes only into a private fixture-environment file.
    with temporary.open('x', encoding='utf-8') as stream:
        temporary.chmod(0o600)
        stream.write(json.dumps(ready) + '\n')
    temporary.replace(args.ready_file)
    print('Owned script fixture ready; private environment file written.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
