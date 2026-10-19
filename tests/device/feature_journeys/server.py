#!/usr/bin/env python3
"""Local controlled resources and authenticated independent-observer journal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feature_journeys.contract import exact, identifier
from feature_journeys.fixtures import check, companion, payload
from feature_journeys.witness import Journal

PREFIX = '/feature-fixture/v1'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No private URLs, tokens, account aliases or request bodies in logs.

    def send(self, status, value, content_type='application/json'):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        try:
            parsed = urlsplit(self.path)
            if parsed.query or parsed.fragment or not parsed.path.startswith(PREFIX + '/'):
                return self.send(404, {'error': 'not-found'})
            parts = parsed.path[len(PREFIX) + 1:].split('/')
            auth = self.headers.get('Authorization', '')
            reader = hmac.compare_digest(auth, 'Bearer ' + self.server.reader_token)
            actor = hmac.compare_digest(auth, 'Bearer ' + self.server.actor_token)
            if self.command == 'GET' and len(parts) >= 6 and parts[:1] == ['runs'] and parts[2] == 'tickets':
                run, ticket = identifier(parts[1]), identifier(parts[3])
                # Resource access is public only for an unpredictable active run;
                # tickets bind actual resource bytes, never desired observations.
                if not self.server.journal.has_ticket(run, ticket):
                    return self.send(404, {'error': 'not-found'})
                resource = '/'.join(parts[4:])
                data = payload(resource, run, ticket)
                if data is None:
                    try:
                        data = ('application/octet-stream', companion(resource))
                    except ValueError:
                        return self.send(404, {'error': 'not-found'})
                return self.send(200, data[1], data[0])
            if self.command == 'GET' and len(parts) == 3 and parts[0] == 'runs' and parts[2] == 'current':
                return self.send(200, {'ticket': self.server.journal.active(identifier(parts[1]))['ticket']})
            # Flat resource paths have exactly five components.
            if self.command == 'GET' and len(parts) == 5 and parts[0] == 'runs' and parts[2] == 'tickets':
                run, ticket = identifier(parts[1]), identifier(parts[3])
                if not self.server.journal.has_ticket(run, ticket):
                    return self.send(404, {'error': 'not-found'})
                data = payload(parts[4], run, ticket)
                if data is None:
                    return self.send(404, {'error': 'not-found'})
                return self.send(200, data[1], data[0])
            if not reader and not actor:
                return self.send(403, {'error': 'forbidden'})
            body = None
            if self.command == 'POST':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Invalid bounded body')
                body = json.loads(self.rfile.read(size))
            if self.command == 'POST' and parts == ['runs'] and reader:
                exact(body, {'area'}, 'fixture registration')
                return self.send(200, {'runId': self.server.journal.register(body['area'])})
            if len(parts) < 2 or parts[0] != 'runs':
                return self.send(404, {'error': 'not-found'})
            run = identifier(parts[1])
            if self.command == 'POST' and parts[2:] == ['active'] and reader:
                exact(body, {'ticket', 'verb', 'inputs'}, 'fixture challenge')
                self.server.journal.activate(run, body['ticket'], body['verb'], body['inputs'])
                return self.send(200, {})
            if self.command == 'GET' and parts[2:] == ['active']:
                return self.send(200, self.server.journal.active(run))
            if self.command == 'POST' and parts[2:] == ['samples'] and actor:
                self.server.journal.publish(run, body)
                return self.send(200, {})
            if self.command == 'GET' and len(parts) == 2:
                return self.send(200, self.server.journal.snapshot(run))
            if self.command == 'DELETE' and len(parts) == 2 and reader:
                self.server.journal.close(run)
                return self.send(200, {})
            return self.send(403, {'error': 'forbidden'})
        except (ValueError, KeyError, TypeError):
            self.send(400, {'error': 'invalid-owned-fixture-request'})

    do_GET = handle_request
    do_POST = handle_request
    do_DELETE = handle_request


def make_server(reader_token, actor_token, address=('127.0.0.1', 0)):
    if (type(reader_token) is not str or type(actor_token) is not str
            or min(len(reader_token), len(actor_token)) < 32 or reader_token == actor_token):
        raise ValueError('Separate private reader and independent publisher tokens are required')
    server = ThreadingHTTPServer(address, Handler)
    server.reader_token, server.actor_token = reader_token, actor_token
    server.journal = Journal()
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--private-config', type=Path)
    args = parser.parse_args()
    count = check()
    if args.check:
        print(f'PASS: {count} pinned companions and feature fixture generators')
        return
    if args.private_config is None:
        parser.error('--private-config is required to serve')
    config = json.loads(args.private_config.read_text())
    exact(config, {'readerToken', 'actorToken', 'host', 'port'}, 'private fixture configuration')
    with make_server(config['readerToken'], config['actorToken'], (config['host'], config['port'])) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
