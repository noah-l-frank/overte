"""Retained request/cancel child of the existing Pico Avatar parent.

Only original native Avatar identities and surveyed Pal controls supply facts.
Roles acquire their existing source locks separately; every wait is unlocked.
No relationship, rendered-avatar, account or complete-feature verdict is made.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import os
import re
import stat
import time

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.pico4 import avatar_state
from adapters.pico4.avatar_originals import AvatarOriginalFrames
from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI, project, control_id
from adapters.pico4.avatar_urls import packet, PicoAvatarUrls
from adapters.pico4.navigation import validate_snapshot
from adapters.script_journey.history import canonical, pack, same, unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import scope, nonce
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader, validate as phase_packet

VERBS = frozenset(('connection-request', 'connection-cancel'))
ROLES = ('primary', 'peer')
SESSION = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def session(value):
    need(type(value) is str)
    # Preserve the observed string in originals; canonicalization only joins
    # the product's two documented UUID spellings, never arbitrary text.
    actual = value[1:-1] if value.startswith('{') and value.endswith('}') else value
    need(SESSION.fullmatch(actual) is not None and actual != '00000000-0000-0000-0000-000000000000')
    return actual


def consent(widgets):
    rows = [r for r in project(widgets)['controls'] if r['id'] == 'people.page']
    need(len(rows) <= 1)
    if not rows:
        return None
    value = rows[0]['consent']
    need(type(value) is dict and set(value) in (
        {'phase', 'message', 'peerName'}, {'phase', 'message', 'peerName', 'peer', 'requestId'}))
    need(all(type(value[k]) is str for k in value) and len(value['message']) <= 1024
         and len(value['peerName']) <= 128 and value['phase'] in
         ('idle', 'outgoing', 'incoming', 'accepted', 'submitting', 'polling', 'success', 'declined', 'cancelled', 'error'))
    if value['phase'] == 'idle':
        need(value.get('peer', '') == value.get('requestId', '') == '')
    elif value['phase'] != 'error':
        session(value.get('peer')); session(value.get('requestId'))
    # Every visible control is surveyed from this same original Pal object.
    need(all(same(r['consent'], value) for r in project(widgets)['controls']
             if r['id'].startswith('people.') and r['id'] != 'people.entry'))
    return deepcopy(value)


class PicoAvatarPeople:
    def __init__(self, store, binding, phase, lock, roles, *, monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(phase, PhaseFixtureReader) and phase.area == 'avatar-people'
             and isinstance(lock, ScriptSourceLock) and type(roles) is dict and set(roles) == set(ROLES)
             and callable(monotonic) and callable(sleep))
        self.store, self.binding, self.phase, self.lock = store, deepcopy(context(binding)), phase, lock
        self.run, self.roles, self.monotonic, self.sleep = phase.run, roles, monotonic, sleep
        for role in ROLES:
            exact(roles[role], {'binding', 'lock', 'native', 'widgets', 'controls', 'guard'})
            context(roles[role]['binding'])
            need(isinstance(roles[role]['lock'], ScriptSourceLock)
                 and all(callable(roles[role][k]) for k in ('native', 'widgets', 'controls', 'guard')))
        need(roles['primary']['lock'] is lock and same(roles['primary']['binding'], binding)
             and roles['peer']['lock'] is not lock and roles['peer']['lock'].path != lock.path
             and all(roles['primary']['binding'][k] != roles['peer']['binding'][k]
                     for k in ('targetFingerprint', 'processIdentity', 'sessionId')))
        self.archive = AvatarOriginalFrames(store, binding, self.run, phase.fixture_url, 'people')
        self.readers, self.clock, self.anchor, self.active_role = {}, None, None, None
        self.previous = store.read()
        self.state = dict(calls=[], frames=[], inputs=[], pending=None)
        self.bound()
        if self.previous is not None:
            self.state = self.restore(self.previous)

    def bound(self):
        self.lock.assert_held()
        need(self.roles['primary']['guard']() is not False and same(self.previous, self.store.read()))
        now = self.monotonic()
        need(number(now, 0, 1e15) and (self.clock is None or now >= self.clock))
        self.clock = now
        self.budget()

    def budget(self):
        prefix = self.store.path.name.removesuffix('.json')
        match = re.fullmatch(r'avatar-people-owner-([0-9a-f]{32})-([0-9a-f]{32})', prefix)
        need(match is not None and match[2] == self.run)
        key = match[1]; files = total = 0
        for pattern in ('avatar-people-owner-', 'avatar-people-frame-', 'avatar-people-role-primary-owner-', 'avatar-people-role-peer-owner-'):
            for path in self.store.path.parent.glob(pattern + key + '-' + self.run + '*.json'):
                suffix = '-[0-9a-f]{32}' if pattern == 'avatar-people-frame-' else ''
                need(re.fullmatch(re.escape(pattern + key + '-' + self.run) + suffix + r'\.json', path.name) is not None)
                value = PrivateFeatureState(path).read(); need(value is not None)
                files += 1; total += len(canonical(value))
                if 'payload' in value:
                    total += len(canonical(unpack(value['payload'])))
                need(files <= 512 and total <= 16 * 1024 * 1024)

    def parent_file(self):
        store = PrivateFeatureState(self.store.path.with_name(self.store.path.name.replace(
            'avatar-people-owner-', 'avatar-parent-owner-', 1)))
        store._parent(); before = store.path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.geteuid()
             and stat.S_IMODE(before.st_mode) == 0o600 and before.st_size <= 65536)
        descriptor = os.open(store.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        stamp = AvatarOriginalFrames.frame_stamp
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno()); need(stamp(opened) == stamp(before))
            raw = stream.read(65537); after = os.fstat(stream.fileno()); current = store.path.lstat()
        need(stamp(before) == stamp(opened) == stamp(after) == stamp(current) and len(raw) == before.st_size)
        text = raw.decode('utf-8')
        return dict(raw=text, sha256=hashlib.sha256(raw).hexdigest(), identity=list(stamp(current)))

    def parent_original(self, original, request):
        exact(original, {'raw', 'sha256', 'identity'})
        need(type(original['raw']) is str and len(original['raw'].encode()) <= 65536
             and hashlib.sha256(original['raw'].encode()).hexdigest() == original['sha256']
             and type(original['identity']) is list and len(original['identity']) == 8
             and all(type(v) is int and v >= 0 for v in original['identity']))
        value = decode(original['raw'])
        exact(value, {'picoAvatarParentVersion', 'binding', 'runId', 'fixtureUrl', 'payload'})
        need(type(value['picoAvatarParentVersion']) is int and value['picoAvatarParentVersion'] == 2
             and same(value['binding'], self.binding) and value['runId'] == self.run
             and value['fixtureUrl'] == self.phase.fixture_url)
        rows = unpack(value['payload']); need(len(rows) == 1)
        state = rows[0]; exact(state, {'prepared', 'frames', 'calls', 'pending'})
        need(state['prepared'] is True and type(state['calls']) is list and state['calls']
             and state['pending'] == request['ticket'] and same(state['calls'][-1]['request'], request)
             and state['calls'][-1]['after'] is None and state['calls'][-1]['child'] is None)
        return value

    def parent_fence(self):
        need(self.state['calls'])
        call = self.state['calls'][-1]
        self.parent_original(call['parent'], call['request'])
        need(same(call['parent'], self.parent_file()))

    def unlocked(self):
        need(all(self.roles[role]['lock']._owner is None for role in ROLES))

    def role_store(self, role):
        return PrivateFeatureState(self.store.path.with_name(self.store.path.name.replace(
            'avatar-people-owner-', 'avatar-people-role-' + role + '-owner-', 1)))

    def role_record(self, role):
        value = self.role_store(role).read()
        if value is None:
            return dict(picoAvatarPeopleRoleVersion=1, role=role, binding=self.roles[role]['binding'], parentBinding=self.binding,
                        runId=self.run, fixtureUrl=self.phase.fixture_url, frames=[], raws=[], inputs=[])
        exact(value, {'picoAvatarPeopleRoleVersion', 'role', 'binding', 'parentBinding', 'runId', 'fixtureUrl', 'frames', 'raws', 'inputs'})
        need(type(value['picoAvatarPeopleRoleVersion']) is int and value['picoAvatarPeopleRoleVersion'] == 1
             and value['role'] == role and same(value['binding'], self.roles[role]['binding'])
             and same(value['parentBinding'], self.binding) and value['runId'] == self.run
             and value['fixtureUrl'] == self.phase.fixture_url and type(value['frames']) is list and len(value['frames']) <= 128
             and type(value['inputs']) is list and len(value['inputs']) <= 128
             and type(value['raws']) is list and len(value['raws']) <= 128)
        for ref in value['frames']:
            self.role_frame(self.archive.frame_original(ref), role)
        for ref in value['raws']:
            raw = self.archive.frame_original(ref)
            exact(raw, {'kind', 'role', 'binding', 'hostObserved', 'raw', 'sha256'})
            need(raw['kind'] == 'native-raw' and raw['role'] == role and same(raw['binding'], self.roles[role]['binding'])
                 and number(raw['hostObserved'], 0, 1e15) and type(raw['raw']) is str and len(raw['raw'].encode()) <= 262144
                 and hashlib.sha256(raw['raw'].encode()).hexdigest() == raw['sha256'])
        for row in value['inputs']:
            exact(row, {'ticket', 'role', 'intent', 'command'})
            need(row['role'] == role and row['ticket'] in {r['request']['ticket'] for r in self.state['calls']})
            if row['command'] is not None:
                PicoAvatarUrls.command_original(row['command'], row['intent'])
        return value

    def retain_native_raw(self, role, raw):
        self.roles[role]['lock'].assert_held()
        need(type(raw) is str and len(raw.encode()) <= 262144)
        # Tap the actual reader callback before parsing/validation. Bad, empty,
        # late and foreign replies stay original owned bytes too.
        value = dict(kind='native-raw', role=role, binding=self.roles[role]['binding'], hostObserved=self.monotonic(),
                     raw=raw, sha256=hashlib.sha256(raw.encode()).hexdigest())
        store = self.role_store(role); old = store.read(); record = self.role_record(role)
        need(len(record['raws']) < 128)
        record['raws'].append(self.archive.frame_reference(value))
        store.write(record, old); self.budget()

    def role_frame(self, value, role):
        exact(value, {'role', 'binding', 'native', 'widgets', 'nativeEpochMs', 'hostStarted', 'hostFinished'})
        need(value['role'] == role and same(value['binding'], self.roles[role]['binding'])
             and number(value['hostStarted'], 0, 1e15)
             and number(value['hostFinished'], value['hostStarted'], value['hostStarted'] + 1.5))
        pid = int(value['binding']['processIdentity'].split(':')[0])
        native = packet(value['native'], pid)
        need(integer(value['nativeEpochMs'], 1))
        fresh(native['capturedEpochMs'], value['nativeEpochMs'])
        fresh(value['widgets']['updatedEpochMs'], value['nativeEpochMs'])
        validate_snapshot(value['widgets'], pid, value['widgets']['updatedEpochMs'])
        need(value['widgets']['bridgeId'] == value['binding']['sessionId'])
        consent(value['widgets'])
        return native

    def frame(self, value):
        exact(value, {'roles', 'phaseBefore', 'phaseAfter', 'hostStarted', 'hostFinished'})
        exact(value['roles'], set(ROLES))
        need(number(value['hostStarted'], 0, 1e15)
             and number(value['hostFinished'], value['hostStarted'], value['hostStarted'] + 1.5))
        natives = {role: self.role_frame(value['roles'][role], role) for role in ROLES}
        need(natives['primary']['source']['sessionId'] != natives['peer']['source']['sessionId'])
        for key in ('phaseBefore', 'phaseAfter'):
            phase_packet(value[key], run=self.run, area='avatar-people', request=value[key].get('requestId'),
                         epoch=value[key].get('capturedEpochMs'))
        need(same(value['phaseBefore']['activations'], value['phaseAfter']['activations'])
             and value['phaseBefore']['active'] == value['phaseAfter']['active'])
        return natives

    def check(self, state):
        exact(state, {'calls', 'frames', 'inputs', 'pending'})
        need(type(state['frames']) is list and len(state['frames']) <= 128
             and type(state['calls']) is list and len(state['calls']) <= 16
             and type(state['inputs']) is list and len(state['inputs']) <= 128)
        previous = None
        for value in state['frames']:
            natives = self.frame(value)
            if previous is not None:
                need(value['hostStarted'] >= previous['hostFinished'])
                for role in ROLES:
                    avatar_state.continuity(packet(previous['roles'][role]['native'], natives[role]['processId']), natives[role])
                phase_packet(value['phaseBefore'], run=self.run, area='avatar-people', request=value['phaseBefore']['requestId'],
                             epoch=value['phaseBefore']['capturedEpochMs'], previous=previous['phaseAfter'])
            previous = value
        tickets = set()
        for call in state['calls']:
            exact(call, {'request', 'before', 'after', 'requestId', 'quiet', 'parent'})
            request = arguments('feature.avatar-people.act', call['request'])
            need(request['runId'] == self.run and request['fixtureUrl'] == self.phase.fixture_url
                 and request['verb'] in VERBS and request['ticket'] not in tickets)
            tickets.add(request['ticket'])
            self.parent_original(call['parent'], request)
            need(call['before'] is None or integer(call['before'], 1, len(state['frames'])))
            if call['before'] is not None:
                need(state['frames'][call['before'] - 1]['phaseAfter']['activations'][-1]['ticket'] == request['ticket'])
            if call['after'] is not None:
                need(call['before'] is not None and integer(call['after'], call['before'] + 1, len(state['frames'])))
                session(call['requestId'])
                for frame in state['frames'][call['before'] - 1:call['after']]:
                    activation = frame['phaseAfter']['activations'][-1]
                    need(frame['phaseAfter']['active'] and activation['ticket'] == request['ticket']
                         and same(activation['stimulus'], dict(verb=request['verb'], inputs=request['inputs'])))
                    for role in ROLES:
                        pid = int(self.roles[role]['binding']['processIdentity'].split(':')[0])
                        a = packet(state['frames'][call['before'] - 1]['roles'][role]['native'], pid)['source']
                        b = packet(frame['roles'][role]['native'], pid)['source']
                        need(same(PicoAvatarUrls.stable(a), PicoAvatarUrls.stable(b)))
                if request['verb'] == 'connection-request':
                    need(call['quiet'] is None); self.request_pair(state['frames'][call['after'] - 1], call['requestId'])
                    need(all(consent(state['frames'][call['before'] - 1]['roles'][r]['widgets']) is None
                             or consent(state['frames'][call['before'] - 1]['roles'][r]['widgets'])['phase'] == 'idle' for r in ROLES))
                    need(sum(row['role'] == 'primary' and row['intent']['controlId'] == 'people.RequestConnection'
                             for row in state['inputs'] if row['ticket'] == request['ticket']) == 1)
                else:
                    self.quiet_original(state, call)
                    counts = {role: sum(row['role'] == role and row['intent']['controlId'] == 'people.ConnectionCancel'
                                       for row in state['inputs'] if row['ticket'] == request['ticket']) for role in ROLES}
                    need(counts == dict(primary=2, peer=1))
                    cancelled = False
                    for frame in state['frames'][call['before']:call['quiet']['first'] - 1]:
                        try:
                            self.cancelled_pair(frame, call['requestId']); cancelled = True
                        except NativeUIError:
                            pass
                    need(cancelled)
                need(all(row['command'] is not None for row in state['inputs'] if row['ticket'] == request['ticket']))
            else:
                need(call['quiet'] is None)
        need([r['request']['ticket'] for r in state['calls'] if r['after'] is None] ==
             ([] if state['pending'] is None else [state['pending']]))
        for row in state['inputs']:
            exact(row, {'ticket', 'role', 'intent', 'command'})
            need(row['ticket'] in tickets and row['role'] in ROLES)
            intent = row['intent']
            exact(intent, {'avatarPeopleInputVersion', 'action', 'controlId', 'controlToken', 'scope'})
            scope(intent['scope'])
            need(type(intent['avatarPeopleInputVersion']) is int and intent['avatarPeopleInputVersion'] == 1
                 and intent['action'] == 'activate' and control_id(intent['controlId']) and nonce(intent['controlToken'])
                 and intent['scope']['instance'] == self.roles[row['role']]['binding']['sessionId']
                 and intent['scope']['processId'] == int(self.roles[row['role']]['binding']['processIdentity'].split(':')[0]))
            if row['command'] is not None:
                PicoAvatarUrls.command_original(row['command'], intent)

    def restore(self, value):
        exact(value, {'picoAvatarPeopleVersion', 'binding', 'peerBinding', 'runId', 'fixtureUrl', 'payload'})
        need(type(value['picoAvatarPeopleVersion']) is int and value['picoAvatarPeopleVersion'] == 1
             and same(value['binding'], self.binding) and same(value['peerBinding'], self.roles['peer']['binding'])
             and value['runId'] == self.run and value['fixtureUrl'] == self.phase.fixture_url)
        states = unpack(value['payload']); need(len(states) == 1)
        state = states[0]; need(type(state) is dict and type(state.get('frames')) is list and len(state['frames']) <= 128)
        state['frames'] = [self.archive.frame_original(ref) for ref in state['frames']]
        self.check(state)
        return state

    def save(self):
        self.bound(); self.check(self.state)
        payload = deepcopy(self.state)
        payload['frames'] = [self.archive.frame_reference(value) for value in self.state['frames']]
        value = dict(picoAvatarPeopleVersion=1, binding=self.binding, peerBinding=self.roles['peer']['binding'],
                     runId=self.run, fixtureUrl=self.phase.fixture_url, payload=pack([payload]))
        self.store.write(value, self.previous); self.previous = deepcopy(value); self.bound()

    def phase_fence(self, original=None):
        self.parent_fence()
        status = self.phase.status()
        need(status['active'] and status['activations'] and self.state['calls'])
        request = self.state['calls'][-1]['request']; actual = status['activations'][-1]
        need(actual['ticket'] == request['ticket'] and same(actual['stimulus'], dict(verb=request['verb'], inputs=request['inputs'])))
        if original is not None:
            need(same(status['activations'], original['activations']))
        return status

    def reserve(self, request, *, parent_original):
        arguments('feature.avatar-people.act', request); self.bound()
        need(request['verb'] in VERBS and request['runId'] == self.run and request['fixtureUrl'] == self.phase.fixture_url
             and self.state['pending'] is None and len(self.state['calls']) < 16
             and request['ticket'] not in {r['request']['ticket'] for r in self.state['calls']})
        if request['verb'] == 'connection-cancel':
            need(self.state['calls'] and self.state['calls'][-1]['request']['verb'] == 'connection-request'
                 and self.state['calls'][-1]['after'] is not None)
        original = self.parent_file(); need(same(self.parent_original(original, request), parent_original))
        self.state['calls'].append(dict(request=deepcopy(request), before=None, after=None, requestId=None, quiet=None, parent=original))
        self.state['pending'] = request['ticket']; self.phase_fence(); self.save()

    def sample_role(self, role):
        self.unlocked(); source = self.roles[role]
        with source['lock'].held():
            need(source['guard']() is not False)
            started = self.monotonic()
            if role not in self.readers:
                reader = source['native'](); need(isinstance(reader, avatar_state.NativePicoAvatarState))
                if self.state['frames']:
                    reader.restore([packet(f['roles'][role]['native'], reader.pid) for f in self.state['frames']])
                original = reader.original
                def captured(original=original, role=role):
                    raw = original(); self.retain_native_raw(role, raw); return raw
                reader.original = captured
                self.readers[role] = reader
            reader = self.readers[role]; native = reader.read(); widgets = source['widgets']()
            value = dict(role=role, binding=source['binding'], native=dict(raw=reader.last_raw, sha256=reader.last_sha256),
                         widgets=deepcopy(widgets), nativeEpochMs=reader.clock_ms(), hostStarted=started, hostFinished=self.monotonic())
            # Retain this role's full source before joining another role.
            ref = self.archive.frame_reference(value)
            store = self.role_store(role); old = store.read(); record = self.role_record(role)
            need(len(record['frames']) < 128)
            record['frames'].append(ref); store.write(record, old)
            self.role_frame(value, role); fresh(native['capturedEpochMs'], reader.clock_ms())
            fresh(widgets['updatedEpochMs'], reader.clock_ms())
            need(native['capturedEpochMs'] <= widgets['updatedEpochMs'])
            need(source['guard']() is not False and self.monotonic() - started <= 1.5)
        need(self.monotonic() - started <= 1.5)
        self.fresh_role(value)
        return value

    def fresh_role(self, value):
        elapsed = self.monotonic() - value['hostFinished']
        need(number(elapsed, 0, 1.5))
        epoch = value['nativeEpochMs'] + math.ceil(elapsed * 1000)
        native = packet(value['native'], int(value['binding']['processIdentity'].split(':')[0]))
        fresh(native['capturedEpochMs'], epoch); fresh(value['widgets']['updatedEpochMs'], epoch)

    def fresh_current(self):
        need(self.state['frames'])
        for role in ROLES:
            self.fresh_role(self.state['frames'][-1]['roles'][role])

    def sample(self):
        self.unlocked(); started = self.monotonic()
        with self.lock.held():
            self.bound(); before = self.phase_fence()
        roles = {role: self.sample_role(role) for role in ROLES}
        with self.lock.held():
            self.bound(); after = self.phase_fence(before)
            value = dict(roles=roles, phaseBefore=before, phaseAfter=after,
                         hostStarted=started, hostFinished=self.monotonic())
            self.frame(value); need(len(self.state['frames']) < 128)
            self.state['frames'].append(value); self.save()
            self.fresh_current()
            need(self.monotonic() - started <= 1.5)
        self.unlocked()
        need(self.monotonic() - started <= 1.5); self.fresh_current()
        return deepcopy(value)

    def intent(self, role, value):
        need(self.active_role == role and self.state['pending'] is not None and len(self.state['inputs']) < 128)
        # The peer lock is never nested with the Primary lock. Peer-close intent
        # is reserved durably under Primary BEFORE entering the peer source lock.
        need(role == 'primary')
        self.state['inputs'].append(dict(ticket=self.state['pending'], role=role, intent=deepcopy(value), command=None))
        self.save()

    def before_send(self, command, navigation):
        need(self.active_role == 'primary' and self.state['inputs'])
        self.bound(); self.phase_fence(); row = self.state['inputs'][-1]
        need(row['command'] is None and row['ticket'] == self.state['pending'])
        PicoAvatarUrls.command_original(command, row['intent'])
        need(command['action'] == 'activate' and (command['controlId'] in
             ('tablet.home', 'people.entry', 'people.nearby', 'people.RequestConnection', 'people.ConnectionCancel')
             or command['controlId'].startswith(('tablet.page.', 'people.row.'))))
        row['command'] = deepcopy(command); self.save(); self.archive.verify_frames(self.state['frames'])
        self.bound(); self.phase_fence()
        need(self.anchor is not None and self.monotonic() - self.anchor < 1.5)
        latest = self.state['frames'][-1]
        self.fresh_current()

    def click(self, identifier, *, peer_session=None):
        self.sample(); self.unlocked(); self.anchor = self.state['frames'][-1]['hostStarted']
        with self.lock.held():
            self.bound(); self.phase_fence(); self.active_role = 'primary'
            try:
                ui = self.roles['primary']['controls'](lambda v: self.intent('primary', v), self.before_send)
                need(isinstance(ui, TokenAvatarPeopleUI))
                if peer_session is not None:
                    row = ui.row(ui.capture(), identifier)
                    need(row is not None and session(row.get('peerSession')) == peer_session)
                ui.input(identifier)
            finally:
                self.active_role = None
        self.unlocked()

    def close_peer(self):
        """The peer persists and executes its own exact normal Close command."""
        value = self.sample(); self.unlocked(); source = self.roles['peer']
        anchor = value['hostStarted']; request = self.state['calls'][-1]['request']
        current = consent(value['roles']['peer']['widgets'])
        need(current is not None and current['phase'] == 'cancelled')
        with source['lock'].held():
            need(source['guard']() is not False)
            store = self.role_store('peer'); old = store.read(); record = self.role_record('peer')
            need(not any(r['ticket'] == request['ticket'] for r in record['inputs']))
            def persist():
                nonlocal old
                store.write(record, old); old = deepcopy(record)
            def intent(original):
                need(len(record['inputs']) < 128 and original['controlId'] == 'people.ConnectionCancel')
                record['inputs'].append(dict(ticket=request['ticket'], role='peer', intent=deepcopy(original), command=None))
                persist()
            def issued(command, navigation):
                need(record['inputs'] and record['inputs'][-1]['command'] is None)
                PicoAvatarUrls.command_original(command, record['inputs'][-1]['intent'])
                need(command['controlId'] == 'people.ConnectionCancel' and command['action'] == 'activate')
                self.phase_fence(value['phaseAfter']); need(source['guard']() is not False)
                record['inputs'][-1]['command'] = deepcopy(command); persist()
                self.archive.verify_frames(self.state['frames']); self.phase_fence(value['phaseAfter'])
                need(self.monotonic() - anchor < 1.5 and source['guard']() is not False)
                self.fresh_current()
            ui = source['controls'](intent, issued); need(isinstance(ui, TokenAvatarPeopleUI))
            ui.input('people.ConnectionCancel')
            need(record['inputs'] and record['inputs'][-1]['command'] is not None)
            original = deepcopy(record['inputs'][-1])
        with self.lock.held():
            self.bound(); self.state['inputs'].append(original); self.save()
        self.unlocked()

    def wait(self, predicate, *, quiet=False):
        self.unlocked(); started = self.monotonic(); first = None
        for _ in range(82):
            value = self.sample()
            if predicate(value):
                if not quiet:
                    return value
                if first is None:
                    first = len(self.state['frames'])
                if value['hostFinished'] - self.state['frames'][first - 1]['hostFinished'] >= 3:
                    return dict(first=first, last=len(self.state['frames']))
            else:
                first = None
            need(self.monotonic() - started < 20)
            self.unlocked(); self.sleep(.25); self.unlocked()
        raise NativeUIError('Original People source did not settle')

    def request_pair(self, value, request_id=None):
        natives = self.frame(value)
        primary, peer = [consent(value['roles'][r]['widgets']) for r in ROLES]
        need(primary is not None and peer is not None and primary['phase'] == 'outgoing' and peer['phase'] == 'incoming'
             and session(primary['peer']) == natives['peer']['source']['sessionId']
             and session(peer['peer']) == natives['primary']['source']['sessionId']
             and session(primary['requestId']) == session(peer['requestId']))
        actual = session(primary['requestId'])
        if request_id is not None:
            need(actual == request_id)
        return actual

    def cancelled_pair(self, value, request_id):
        natives = self.frame(value)
        rows = [consent(value['roles'][r]['widgets']) for r in ROLES]
        need(all(row is not None and row['phase'] == 'cancelled' and session(row['requestId']) == request_id for row in rows)
             and session(rows[0]['peer']) == natives['peer']['source']['sessionId']
             and session(rows[1]['peer']) == natives['primary']['source']['sessionId'])
        return True

    def quiet_original(self, state, call):
        proof = call['quiet']; exact(proof, {'first', 'last'})
        need(integer(proof['first'], call['before'] + 1, len(state['frames']))
             and integer(proof['last'], proof['first'] + 1, len(state['frames'])) and proof['last'] == call['after'])
        frames = state['frames'][proof['first'] - 1:proof['last']]
        for value in frames:
            need(all(consent(value['roles'][r]['widgets']) is not None
                     and consent(value['roles'][r]['widgets'])['phase'] == 'idle' for r in ROLES))
            need(same(value['phaseAfter']['activations'], frames[0]['phaseAfter']['activations']))
        need(frames[-1]['hostFinished'] - frames[0]['hostFinished'] >= 3)
        for role in ROLES:
            previous = None
            for value in frames:
                row = value['roles'][role]; native = packet(row['native'], int(row['binding']['processIdentity'].split(':')[0]))
                if previous is not None:
                    need(0 <= value['hostFinished'] - previous[0] <= .5
                         and 0 <= native['capturedEpochMs'] - previous[1] <= 500
                         and 0 <= row['widgets']['elapsedMs'] - previous[2] <= 500)
                previous = value['hostFinished'], native['capturedEpochMs'], row['widgets']['elapsedMs']
            a, b = [packet(f['roles'][role]['native'], int(f['roles'][role]['binding']['processIdentity'].split(':')[0])) for f in (frames[0], frames[-1])]
            need(b['capturedEpochMs'] - a['capturedEpochMs'] >= 3000
                 and frames[-1]['roles'][role]['widgets']['elapsedMs'] - frames[0]['roles'][role]['widgets']['elapsedMs'] >= 3000)

    def execute(self, request):
        """Execute outside both locks; a previously attempted call never resends."""
        self.unlocked()
        with self.lock.held():
            self.bound(); need(self.state['pending'] == request['ticket'] and same(self.state['calls'][-1]['request'], request)
                               and not any(r['ticket'] == request['ticket'] for r in self.state['inputs']))
        value = self.sample(); call = self.state['calls'][-1]
        with self.lock.held():
            call['before'] = len(self.state['frames']); self.save()
        if request['verb'] == 'connection-request':
            need(all(consent(value['roles'][r]['widgets']) is None or consent(value['roles'][r]['widgets'])['phase'] == 'idle' for r in ROLES))
            controls = project(value['roles']['primary']['widgets'])
            if not any(r['id'] == 'people.page' for r in controls['controls']):
                if not any(r['id'] == 'people.entry' for r in controls['controls']):
                    self.click('tablet.home')
                for index in range(1, 33):
                    current = project(self.sample()['roles']['primary']['widgets'])
                    if any(r['id'] == 'people.entry' for r in current['controls']):
                        break
                    identifier = 'tablet.page.' + str(index)
                    if any(r['id'] == identifier for r in current['controls']):
                        self.click(identifier)
                else:
                    need(False)
                self.click('people.entry')
            self.click('people.nearby')
            value = self.sample(); target = self.frame(value)['peer']['source']['sessionId']
            rows = [r for r in project(value['roles']['primary']['widgets'])['controls']
                    if r['id'].startswith('people.row.') and r.get('peerSession')
                    and session(r['peerSession']) == target]
            need(len(rows) == 1); self.click(rows[0]['id'], peer_session=target)
            self.click('people.RequestConnection')
            def arrived(frame):
                try:
                    self.request_pair(frame); return True
                except NativeUIError:
                    return False
            value = self.wait(arrived); request_id = self.request_pair(value)
            quiet = None
        else:
            request_id = self.state['calls'][-2]['requestId']; self.request_pair(value, request_id)
            self.click('people.ConnectionCancel')
            # Product Pal keeps the original cancelled prompt visible. It is
            # closed by another normal Close, never by an adapter setter.
            def cancelled(frame):
                try:
                    return self.cancelled_pair(frame, request_id)
                except NativeUIError:
                    return False
            self.wait(cancelled); self.click('people.ConnectionCancel')
            self.close_peer()
            quiet = self.wait(lambda f: all(consent(f['roles'][r]['widgets']) is not None
                and consent(f['roles'][r]['widgets'])['phase'] == 'idle' for r in ROLES), quiet=True)
        with self.lock.held():
            self.bound(); call.update(after=len(self.state['frames']), requestId=request_id, quiet=quiet)
            self.state['pending'] = None; self.save()
            receipt = self.receipt(request)
        self.unlocked(); self.fresh_current()
        return receipt

    def receipt(self, request):
        self.bound(); self.check(self.state)
        calls = [row for row in self.state['calls'] if same(row['request'], request)]
        need(len(calls) == 1 and calls[0]['after'] is not None)
        self.archive.verify_frames(self.state['frames'])
        for role in ROLES:
            original = self.role_record(role)
            expected = [self.archive.frame_reference(frame['roles'][role]) for frame in self.state['frames']]
            need(same(original['frames'], expected))
            role_inputs = [] if role == 'primary' else [row for row in self.state['inputs'] if row['role'] == role]
            need(same(original['inputs'], role_inputs))
        proof = dict(request=deepcopy(request), call=deepcopy(calls[0]),
                     frames=[self.archive.frame_reference(f) for f in self.state['frames'][:calls[0]['after']]])
        return self.archive.frame_reference(proof)
