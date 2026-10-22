"""Normal settings-API rez control for one independently owned fixture domain.

The controller changes both actual permission bits through the product's normal
DomainServer administration endpoint. Its HTTP success is never client proof:
the Create journey independently observes canRez/canRezTmp and a real retry.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import ipaddress
import json
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import threading

from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack, unpack, same

VERSION = 1
BITS = ('id_can_rez', 'id_can_rez_tmp')
OTHER_TABLES = ('group_permissions', 'group_forbiddens', 'permissions', 'ip_permissions', 'machine_fingerprint_permissions')
STANDARD_IDS = frozenset(('anonymous', 'friends', 'localhost', 'logged-in'))


def fixture_permissions(description):
    """Opt-in isolated fixture input; preserve the reviewed standard defaults."""
    groups = [group for group in description['settings'] if group.get('name') == 'security']; need(len(groups) == 1)
    settings = [item for item in groups[0]['settings'] if item.get('name') == 'standard_permissions']; need(len(settings) == 1)
    setting = settings[0]
    defaults = {column['name']: column.get('default', False) for column in setting['columns'] if column.get('type') == 'checkbox'}
    need(all(type(value) is bool for value in defaults.values()) and all(bit in defaults for bit in BITS))
    result = [dict(defaults, **row) for row in setting['default']]
    for row in result:
        if row['permissions_id'] == 'anonymous':
            # Physical clients outside loopback need an initially usable owned
            # fixture; assignment roles keep their original normal permissions.
            for bit in BITS: row[bit] = True
    return rows(result)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs): return None


def rows(value):
    need(type(value) is list and len(value) == len(STANDARD_IDS))
    ids = []
    for row in value:
        need(type(row) is dict and row.get('permissions_id') in STANDARD_IDS and len(row) <= 32
             and all(type(row.get(bit)) is bool for bit in BITS))
        ids.append(row['permissions_id'])
    need(set(ids) == STANDARD_IDS and len(set(ids)) == len(ids))
    return deepcopy(value)


def process(value):
    exact(value, {'processId', 'startIdentity', 'domainId'})
    need(integer(value['processId'], 1) and type(value['startIdentity']) is str
         and re.fullmatch('[1-9][0-9]{0,19}', value['startIdentity'])
         and type(value['domainId']) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value['domainId']))
    return value


class CreateRezAuthority:
    def __init__(self, origin, store, owned_domain, *, epoch_ms=lambda: time.time()*1000):
        parsed = urlsplit(origin)
        need(parsed.scheme == 'http' and parsed.hostname is not None and ipaddress.ip_address(parsed.hostname).is_loopback
             and parsed.port is not None and not parsed.username and not parsed.password and not parsed.path
             and not parsed.query and not parsed.fragment and isinstance(store, PrivateFeatureState)
             and callable(owned_domain) and callable(epoch_ms))
        self.origin, self.store, self.owned_domain, self.epoch_ms = origin, store, owned_domain, epoch_ms
        self.binding = deepcopy(process(owned_domain())); self.previous = store.read()
        self.state = None if self.previous is None else self.decode(self.previous)

    def guard(self):
        need(same(process(self.owned_domain()), self.binding) and same(self.store.read(), self.previous))

    def envelope(self):
        return dict(createRezAuthorityVersion=VERSION, origin=self.origin, binding=self.binding, payload=pack([self.state]))

    def decode(self, value):
        exact(value, {'createRezAuthorityVersion', 'origin', 'binding', 'payload'})
        need(type(value['createRezAuthorityVersion']) is int and value['createRezAuthorityVersion'] == VERSION
             and value['origin'] == self.origin and same(value['binding'], self.binding))
        entries = unpack(value['payload']); need(len(entries) == 1); state = entries[0]
        exact(state, {'phase', 'initial', 'current', 'pending', 'observations'})
        need(state['phase'] in ('ready', 'issued', 'restored') and type(state['observations']) is list
             and len(state['observations']) <= 128)
        rows(state['initial']); rows(state['current'])
        if state['pending'] is not None: rows(state['pending'])
        need((state['phase'] == 'issued') == (state['pending'] is not None))
        return state

    def save(self):
        self.guard(); value = self.envelope(); self.decode(value); self.store.write(value, self.previous)
        need(same(self.store.read(), value)); self.previous = deepcopy(value)

    def request(self, method, path, content=None):
        self.guard(); before = self.epoch_ms(); need(number(before, 1, 1e15))
        with build_opener(NoRedirect()).open(self.origin+'/id', timeout=2) as response:
            actual = response.read(129); need(response.status == 200 and len(actual) <= 128)
        need(actual.decode('ascii').strip().strip('{}') == self.binding['domainId']); self.guard()
        body = None if content is None else json.dumps(content, allow_nan=False, separators=(',', ':')).encode()
        request = Request(self.origin+path, data=body, method=method, headers={'Content-Type': 'application/json'})
        with build_opener(NoRedirect()).open(request, timeout=2) as response:
            raw = response.read(1024*1024+1); need(response.status == 200 and len(raw) <= 1024*1024)
        self.guard(); after = self.epoch_ms(); need(number(after, before, before+5000))
        def pairs(entries):
            value = {}
            for key, item in entries: need(key not in value); value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _value: need(False))
        return value, dict(hostBeforeEpochMs=before, hostAfterEpochMs=after)

    def observe(self):
        value, times = self.request('GET', '/settings.json')
        need(type(value) is dict and type(value.get('values')) is dict and type(value['values'].get('security')) is dict)
        security = value['values']['security']
        # An isolated standard-permissions fixture has no user/group/IP/machine
        # override whose union could keep either effective rez bit enabled.
        need(all(security.get(table, []) == [] for table in OTHER_TABLES))
        observed = rows(security.get('standard_permissions'))
        return dict(createRezSettingsVersion=1, binding=deepcopy(self.binding), **times, standardPermissions=observed)

    def prepare(self):
        need(self.state is None); observed = self.observe(); original = observed['standardPermissions']
        self.state = dict(phase='ready', initial=original, current=original, pending=None, observations=[observed]); self.save()
        return deepcopy(observed)

    def transition(self, allowed):
        """One POST, then actual GET. Unknown delivery is observed, never resent."""
        need(type(allowed) is bool and self.state is not None and self.state['phase'] == 'ready')
        observed = self.observe(); need(same(observed['standardPermissions'], self.state['current']))
        target = deepcopy(self.state['initial'])
        if not allowed:
            for row in target:
                for bit in BITS: row[bit] = False
        self.state.update(phase='issued', pending=target); self.state['observations'].append(observed); self.save()
        reply, _times = self.request('POST', '/settings.json', dict(security=dict(standard_permissions=target)))
        need(reply == {'status': 'success'})
        return self.recover()

    def recover(self):
        need(self.state is not None and self.state['phase'] == 'issued')
        observed = self.observe(); need(same(observed['standardPermissions'], self.state['pending']))
        self.state.update(phase='ready', current=self.state['pending'], pending=None)
        self.state['observations'].append(observed); self.save(); return deepcopy(observed)

    def restore(self):
        need(self.state is not None)
        if self.state['phase'] == 'issued': self.recover()
        if self.state['phase'] == 'restored':
            observed = self.observe(); need(same(observed['standardPermissions'], self.state['initial'])); return observed
        if not same(self.state['current'], self.state['initial']): self.transition(True)
        observed = self.observe(); need(same(observed['standardPermissions'], self.state['initial']))
        self.state['phase'] = 'restored'; self.state['observations'].append(observed); self.save()
        # Native clients and the separate actor still need their own original
        # effective permission/callback/quiet proofs before journal retirement.
        return observed


class CreateRezControl:
    """Run-bound private fixture endpoint with durable command nonce ownership."""
    def __init__(self, authority, store):
        need(isinstance(authority, CreateRezAuthority) and isinstance(store, PrivateFeatureState))
        self.authority, self.store, self.lock = authority, store, threading.RLock()
        self.previous = store.read(); self.state = None if self.previous is None else self.decode(self.previous)

    def envelope(self):
        return dict(createRezControlVersion=1, origin=self.authority.origin, binding=self.authority.binding, payload=pack([self.state]))

    def decode(self, value):
        exact(value, {'createRezControlVersion', 'origin', 'binding', 'payload'})
        need(type(value['createRezControlVersion']) is int and value['createRezControlVersion'] == 1
             and value['origin'] == self.authority.origin and same(value['binding'], self.authority.binding))
        entries = unpack(value['payload']); need(len(entries) == 1); state = entries[0]
        exact(state, {'runId', 'commands'})
        need(type(state['runId']) is str and re.fullmatch('[a-f0-9]{32}', state['runId'])
             and type(state['commands']) is list and 1 <= len(state['commands']) <= 128)
        ids = []
        for row in state['commands']:
            exact(row, {'command', 'result'}); self.command(row['command']); ids.append(row['command']['commandId'])
            need(row['command']['runId'] == state['runId'] and (row['result'] is None or type(row['result']) is dict))
        need(len(set(ids)) == len(ids) and all(row['result'] is not None for row in state['commands'][:-1]))
        return state

    def save(self):
        need(same(self.store.read(), self.previous)); value = self.envelope(); self.decode(value)
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value)

    @staticmethod
    def command(value):
        need(type(value) is dict)
        exact(value, {'schemaVersion', 'commandId', 'runId', 'operation'}
              | ({'allowed'} if value.get('operation') == 'set' else set())
              | ({'queryCommandId'} if value.get('operation') == 'recover' else set()))
        need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
             and type(value['commandId']) is str and re.fullmatch('[a-f0-9]{32}', value['commandId'])
             and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}', value['runId'])
             and value['operation'] in ('observe', 'set', 'restore', 'recover')
             and (value['operation'] != 'set' or type(value['allowed']) is bool))
        if value['operation'] == 'recover':
            need(type(value['queryCommandId']) is str and re.fullmatch('[a-f0-9]{32}', value['queryCommandId'])
                 and value['queryCommandId'] != value['commandId'])
        return value

    def handle(self, command):
        self.command(command)
        with self.lock:
            self.authority.guard(); need(same(self.store.read(), self.previous))
            if command['operation'] == 'recover':
                need(self.state is not None and self.state['runId'] == command['runId'])
                matching = [row for row in self.state['commands'] if row['command']['commandId'] == command['queryCommandId']]
                need(len(matching) == 1)
                # This explicit read command cannot reach the new-input branch.
                # Its target's original intent and nonce stay unchanged.
                target = matching[0]
                if target['result'] is None: return self.handle(deepcopy(target['command']))
                return deepcopy(target['result'])
            if self.state is None: self.state = dict(runId=command['runId'], commands=[])
            need(self.state['runId'] == command['runId'])
            matching = [row for row in self.state['commands'] if row['command']['commandId'] == command['commandId']]
            if matching:
                need(same(matching[0]['command'], command))
                if matching[0]['result'] is not None: return deepcopy(matching[0]['result'])
                # A request that already crossed its durable intent may only
                # recover via current GET observations. It never sends POST.
                need(self.authority.state is not None)
                if self.authority.state['phase'] == 'issued': observed = self.authority.recover()
                else: observed = self.authority.observe()
                wanted = deepcopy(self.authority.state['initial'])
                if command['operation'] == 'set' and not command['allowed']:
                    for row in wanted:
                        for bit in BITS: row[bit] = False
                need(command['operation'] == 'observe' or same(observed['standardPermissions'], wanted))
                matching[0]['result'] = observed; self.save(); return deepcopy(observed)
            need(len(self.state['commands']) < 128 and all(row['result'] is not None for row in self.state['commands']))
            self.state['commands'].append(dict(command=deepcopy(command), result=None)); self.save()
            if self.authority.state is None: self.authority.prepare()
            if command['operation'] == 'set': observed = self.authority.transition(command['allowed'])
            elif command['operation'] == 'restore': observed = self.authority.restore()
            else: observed = self.authority.observe()
            self.state['commands'][-1]['result'] = observed; self.save(); return deepcopy(observed)
