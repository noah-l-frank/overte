"""One-shot private fixture rez inputs with explicit read-only recovery.

Only independent native permissions and real ordinary creation/denial decide
client effects. Actual settings rows remain a separate domain-original source.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import secrets
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from fixture.create_rez_authority import CreateRezControl, NoRedirect, process, rows

from ios.adapters.create_api_clock import check as api_check

VERSION = 1


def configuration(value):
    exact(value, {'controlUrl', 'token', 'domainId'})
    parsed = urlsplit(value['controlUrl'])
    need(parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port is not None
         and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
         and parsed.path == '/v1/create-rez' and type(value['token']) is str and re.fullmatch('[A-Za-z0-9_-]{40,128}', value['token'])
         and type(value['domainId']) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value['domainId'])
         and value['domainId'] != '00000000-0000-0000-0000-000000000000')
    return value


def original(value, domain_id):
    exact(value, {'createRezSettingsVersion', 'binding', 'hostBeforeEpochMs', 'hostAfterEpochMs', 'standardPermissions'})
    need(type(value['createRezSettingsVersion']) is int and value['createRezSettingsVersion'] == 1
         and process(value['binding'])['domainId'] == domain_id
         and number(value['hostBeforeEpochMs'], 1, 1e15)
         and number(value['hostAfterEpochMs'], value['hostBeforeEpochMs'], value['hostBeforeEpochMs']+5000))
    rows(value['standardPermissions']); return value


class CreateRezClient:
    def __init__(self, store, lock, binding, run, config, guard, *, epoch_ms=lambda:time.time()*1000):
        need(isinstance(store, PrivateFeatureState) and isinstance(lock, ScriptSourceLock) and callable(guard) and callable(epoch_ms))
        self.store, self.lock, self.binding, self.run = store, lock, deepcopy(context(binding)), identifier(run)
        self.config, self.guard, self.epoch_ms = deepcopy(configuration(config)), guard, epoch_ms
        lock.assert_held(); self.previous = store.read(); self.state = None if self.previous is None else self.decode(self.previous)

    def envelope(self):
        return dict(iosCreateRezClientVersion=VERSION, binding=self.binding, runId=self.run,
                    controlUrl=self.config['controlUrl'], domainId=self.config['domainId'],
                    tokenSha256=hashlib.sha256(self.config['token'].encode()).hexdigest(), payload=pack([self.state]))

    def decode(self, value):
        exact(value, {'iosCreateRezClientVersion', 'binding', 'runId', 'controlUrl', 'domainId', 'tokenSha256', 'payload'})
        need(type(value['iosCreateRezClientVersion']) is int and value['iosCreateRezClientVersion'] == VERSION
             and same(value['binding'], self.binding) and value['runId'] == self.run and value['controlUrl'] == self.config['controlUrl']
             and value['domainId'] == self.config['domainId'] and value['tokenSha256'] == hashlib.sha256(self.config['token'].encode()).hexdigest())
        entries = unpack(value['payload']); need(len(entries) == 1); state = entries[0]
        exact(state, {'commands'}); need(type(state['commands']) is list and len(state['commands']) <= 128)
        ids, domain_binding = set(), None
        for index, entry in enumerate(state['commands']):
            exact(entry, {'query', 'original'}); query = CreateRezControl.command(entry['query'])
            need(query['operation'] != 'recover' and query['runId'] == self.run and query['commandId'] not in ids); ids.add(query['commandId'])
            if entry['original'] is None: need(index == len(state['commands'])-1)
            else:
                observed = original(entry['original'], self.config['domainId'])
                if domain_binding is None: domain_binding = observed['binding']
                need(same(observed['binding'], domain_binding))
        return state

    def save(self):
        api_check();self.lock.assert_held(); need(self.guard() is not False and same(self.store.read(), self.previous))
        value = self.envelope(); self.decode(value); self.store.write(value, self.previous)
        need(same(self.store.read(), value)); self.previous = deepcopy(value)

    def send(self, query):
        CreateRezControl.command(query); self.lock.assert_held(); need(self.guard() is not False)
        body = json.dumps(query, separators=(',', ':'), allow_nan=False).encode(); need(len(body) <= 256)
        request = Request(self.config['controlUrl'], data=body, method='POST', headers={
            'Content-Type':'application/json', 'X-Overte-E2E-Token':self.config['token']})
        before = self.epoch_ms()
        opener=build_opener(NoRedirect())
        api_check()
        with opener.open(request, timeout=5) as response:
            raw = response.read(16385); need(response.status == 200 and len(raw) <= 16384)
        def pairs(entries):
            value = {}
            for key, item in entries: need(key not in value); value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _value:need(False))
        original(value, self.config['domainId']); need(self.guard() is not False)
        after = self.epoch_ms(); need(number(before, 1, 1e15) and number(after, before, before+5000))
        if query['operation'] != 'recover':
            need(value['hostBeforeEpochMs'] >= before-250 and -250 <= after-value['hostAfterEpochMs'] <= 1500)
        return value

    def request(self, operation, *, allowed=None):
        need(operation in ('observe', 'set', 'restore') and (allowed is None if operation != 'set' else type(allowed) is bool))
        if self.state is None: self.state = dict(commands=[])
        need(not self.state['commands'] or self.state['commands'][-1]['original'] is not None)
        query = dict(schemaVersion=1, commandId=secrets.token_hex(16), runId=self.run, operation=operation)
        if operation == 'set': query['allowed'] = allowed
        self.state['commands'].append(dict(query=query, original=None)); self.save()
        value = self.send(query)  # No retry after unknown HTTP delivery.
        self.state['commands'][-1]['original'] = deepcopy(value); self.save(); return value

    def recover(self):
        need(self.state is not None and self.state['commands'] and self.state['commands'][-1]['original'] is None)
        entry = self.state['commands'][-1]
        query = dict(schemaVersion=1, commandId=secrets.token_hex(16), runId=self.run, operation='recover', queryCommandId=entry['query']['commandId'])
        value = self.send(query)  # Explicit read-only endpoint branch, no set/restore resend.
        entry['original'] = deepcopy(value); self.save(); return value
