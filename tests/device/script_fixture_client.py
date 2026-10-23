"""Private control connection to the owned script-management HTTP fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import hashlib
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts_observation import script_url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        raise HTTPError(request.full_url, code, 'Owned fixture redirects are forbidden', headers, file)


class ScriptFixtureClient:
    def __init__(self, origin, token):
        parsed = urlsplit(origin) if isinstance(origin, str) else None
        if (parsed is None or parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {'', '/'} or parsed.query or parsed.fragment
                or len(origin) > 2048 or any(ord(c) < 33 for c in origin)):
            raise ValueError('Explicit owned script fixture HTTP origin required')
        try:
            parsed.port
        except ValueError:
            raise ValueError('Owned script fixture port is invalid') from None
        if not isinstance(token, str) or re.fullmatch('[0-9a-f]{64}', token) is None:
            raise ValueError('Private script fixture control token is invalid')
        self.origin, self.token = origin.rstrip('/'), token
        self.opener = build_opener(NoRedirect())
        self.nonce = None

    def request(self, path, method='GET', value=None):
        body = json.dumps(value).encode() if value is not None else None
        request = Request(self.origin + path, data=body, method=method,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=5) as response:
                content = response.read(1024 * 1024 + 1)
                if response.status != 200 or len(content) > 1024 * 1024:
                    raise ValueError('Script fixture response is invalid or too large')
                return json.loads(content)
        except (OSError, ValueError) as error:
            # Do not expose response bodies, request headers or private tokens.
            raise OSError('Owned script fixture request failed') from error

    def register(self):
        if self.nonce is not None:
            raise ValueError('Owned script fixture session is already registered')
        value = self.request('/script-management/sessions', 'POST', {})
        expected_source = hashlib.sha256((Path(__file__).resolve().parent
            / 'fixture/script_management/client.js').read_bytes()).hexdigest()
        if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'nonce', 'scriptUrl', 'missingUrl', 'sourceSha256'}
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['sourceSha256'] != expected_source
                or not isinstance(value['nonce'], str) or re.fullmatch('[0-9a-f]{32}', value['nonce']) is None):
            raise ValueError('Owned script fixture registration is invalid')
        nonce = value['nonce']
        expected = self.origin + f'/script-management/{nonce}/'
        if value['scriptUrl'] != expected + 'client.js' or value['missingUrl'] != expected + 'missing.js':
            raise ValueError('Owned script fixture returned a foreign source origin')
        script_url(value['scriptUrl'])
        self.nonce = nonce
        return value

    def observe(self):
        if self.nonce is None:
            raise ValueError('Owned script fixture session is not registered')
        return self.request(f'/script-management/{self.nonce}/observation')

    def close(self):
        if self.nonce is not None:
            self.request(f'/script-management/{self.nonce}/observation', 'DELETE')
            self.nonce = None
