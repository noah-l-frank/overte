"""Private source-bound control connection for the owned Create observer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import re

from create_observation import PREFIX, owned_url
from script_fixture_client import ScriptFixtureClient


class CreateFixtureClient(ScriptFixtureClient):
    def register(self):
        if self.nonce is not None:
            raise ValueError('Owned Create fixture session is already registered')
        value = self.request('/create/sessions', 'POST', {})
        source = hashlib.sha256((Path(__file__).resolve().parent
            / 'fixture/create_management/observer.js').read_bytes()).hexdigest()
        if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'nonce', 'sourceSha256',
                'observerUrl', 'importUrl', 'missingUrl', 'prefix'}
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or not isinstance(value['nonce'], str) or re.fullmatch('[0-9a-f]{32}', value['nonce']) is None
                or value['sourceSha256'] != source):
            raise ValueError('Owned Create fixture registration differs from the test source')
        nonce = value['nonce']
        base = self.origin + f'/create/{nonce}/'
        if (value['observerUrl'] != base + 'observer.js' or value['importUrl'] != base + 'entities.json'
                or value['missingUrl'] != base + 'missing.json' or value['prefix'] != PREFIX + nonce + '_'):
            raise ValueError('Owned Create fixture returned a foreign resource or prefix')
        owned_url(value['observerUrl'], {'observer.js'})
        self.nonce = nonce
        return value

    def observe(self):
        if self.nonce is None:
            raise ValueError('Owned Create fixture session is not registered')
        return self.request(f'/create/{self.nonce}/observation')

    def close(self):
        if self.nonce is not None:
            self.request(f'/create/{self.nonce}/observation', 'DELETE')
            self.nonce = None
