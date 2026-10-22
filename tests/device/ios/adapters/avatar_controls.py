"""Original Avatar/People widgets and ordinary token-bound Qt input.

Each delivered pointer/IME event requires caller-owned durable intent first.
This component returns input completion only, never model/backend/peer effects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_state import session, text

VERSION = 1
PROFILE = 'ios-avatar-people-native-v1'
FIXED = frozenset({'tablet.home', 'avatar.entry', 'people.entry', 'avatar.page', 'people.page', 'avatar.url-open',
    'avatar.wearables-open', 'avatar.settings-open', 'avatar.scale', 'avatar.url', 'avatar.favorite-name',
    'avatar.favorite-add', 'avatar.manage', 'avatar.wearable-remove', 'avatar.wearable-add', 'avatar.wearable-choice',
    'people.accept', 'people.decline', 'people.cancel', 'people.nearby', 'people.connections'}
    | {'avatar.'+panel+'.'+choice for panel in ('popup', 'favorite', 'settings', 'wearables') for choice in ('confirm', 'cancel')})
FIELDS = frozenset({'avatar.url', 'avatar.favorite-name'})
PHASES = frozenset({'idle', 'incoming', 'outgoing', 'accepted', 'submitting', 'polling', 'success', 'cancelled', 'declined', 'error'})


def nonce(value):
    try: return type(value) is str and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0
    except ValueError: return False


def control_id(value):
    return type(value) is str and (value in FIXED or re.fullmatch(r'tablet\.page\.(?:[1-9]|[12][0-9]|3[0-2])', value)
        or re.fullmatch(r'avatar\.favorite\.[a-f0-9]{32}', value)
        or re.fullmatch(r'people\.(?:select|request)\.[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value)
        or re.fullmatch(r'people\.(?:remove|connection-select)\.[a-f0-9]{32}', value))


def component(value):
    text(value, 4096); parsed = urlsplit(value)
    need(parsed.scheme in ('file', 'qrc') and not parsed.netloc and not parsed.query and not parsed.fragment
         and parsed.path.endswith(('/hifi/AvatarApp.qml', '/hifi/Pal.qml')))


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token')))
    base = {'id', 'token', 'enabled', 'focused', 'inputReady'}; identifier = row['id']
    for key in ('enabled', 'focused', 'inputReady'): need(type(row.get(key)) is bool)
    if identifier in ('avatar.entry', 'people.entry', 'tablet.home') or identifier.startswith('tablet.page.'):
        exact(row, base); return row
    base |= {'rootId', 'qmlSource'}
    need(nonce(row.get('rootId'))); component(row.get('qmlSource'))
    if identifier == 'avatar.page':
        exact(row, base | {'profile', 'dialog', 'popupTitle', 'manage', 'favoriteName', 'favoritePresent'})
        need(row['profile'] == PROFILE and row['dialog'] in ('none', 'popup', 'favorite', 'settings', 'wearables')
             and type(row['manage']) is bool and type(row['favoritePresent']) is bool and not row['inputReady'])
        text(row['popupTitle'], 4096); text(row['favoriteName'], 4096)
    elif identifier == 'people.page':
        exact(row, base | {'profile', 'dialog', 'connectionState', 'activeTab'})
        need(row['profile'] == PROFILE and row['dialog'] in ('none', 'connection') and not row['inputReady']
             and row['activeTab'] in ('nearbyTab', 'connectionsTab'))
        state = row['connectionState']; need(type(state) is dict and {'phase', 'message', 'peerName'} <= set(state)
             and set(state) <= {'phase', 'message', 'peerName', 'peer', 'requestId'} and state['phase'] in PHASES)
        for field in ('message', 'peerName'): text(state[field], 4096)
        if state['phase'] != 'idle': need(set(state) == {'phase', 'message', 'peerName', 'peer', 'requestId'})
        for field in ('peer', 'requestId'):
            if field in state:
                need(state[field] == '' or nonce(state[field]))
    elif identifier in FIELDS:
        exact(row, base | {'text'}); text(row['text'], 4096)
    elif identifier == 'avatar.scale':
        exact(row, base | {'value', 'minimum', 'maximum'})
        need(number(row['value'], .1, 4) and row['minimum'] == .1 and type(row['minimum']) in (int, float)
             and row['maximum'] == 4 and type(row['maximum']) in (int, float))
    elif re.fullmatch(r'avatar\.favorite\.[a-f0-9]{32}', identifier):
        exact(row, base | {'name'}); text(row['name'], 4096)
        need(row['name'] and hashlib.sha256(row['name'].encode()).hexdigest()[:32] == identifier.rsplit('.', 1)[1])
    elif identifier == 'avatar.wearable-choice':
        exact(row, base | {'choices', 'index'})
        need(type(row['choices']) is list and len(row['choices']) <= 64 and len(set(row['choices'])) == len(row['choices'])
             and integer(row['index'], -1, len(row['choices'])-1))
        for value in row['choices']: session(value)
    elif identifier == 'avatar.wearable-remove':
        exact(row, base | {'selectedId'})
        need(row['selectedId'] == '' and not row['inputReady'] or nonce(row['selectedId']))
    elif identifier == 'avatar.favorite.confirm':
        exact(row, base | {'nameConflict'}); need(type(row['nameConflict']) is bool)
    elif identifier.startswith(('people.select.', 'people.request.', 'people.remove.', 'people.connection-select.')):
        exact(row, base | {'peerSession', 'username', 'selected', 'present', 'replicated'})
        text(row['username'], 256)
        for key in ('selected', 'present', 'replicated'): need(type(row[key]) is bool)
        need(type(row['peerSession']) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', row['peerSession']))
        if identifier.startswith(('people.remove.', 'people.connection-select.')):
            need(row['username'] and hashlib.sha256(row['username'].encode()).hexdigest()[:32] == identifier.rsplit('.', 1)[1])
        else: session(row['peerSession']); need(identifier.endswith('.'+row['peerSession']))
        if row['inputReady']: need((identifier.startswith(('people.select.', 'people.connection-select.')) or row['selected'])
                                   and row['present'] and not row['replicated'])
    else: exact(row, base)
    need(row['qmlSource'].endswith('/Pal.qml') if identifier.startswith('people.') else row['qmlSource'].endswith('/AvatarApp.qml'))
    return row


def snapshot(value):
    exact(value, {'avatarControlsVersion', 'open', 'ready', 'scope', 'controls'})
    need(type(value['avatarControlsVersion']) is int and value['avatarControlsVersion'] == VERSION
         and type(value['open']) is bool and type(value['ready']) is bool and type(value['controls']) is list
         and len(value['controls']) <= 128)
    scope = value['scope']; exact(scope, {'instance', 'generation', 'sequence', 'sourceSequence', 'elapsedMs', 'capturedEpochMs', 'processId'})
    need(nonce(scope['instance']) and nonce(scope['generation']))
    for key in ('sequence', 'elapsedMs'): need(integer(scope[key], 0))
    for key in ('sourceSequence', 'capturedEpochMs', 'processId'): need(integer(scope[key], 1))
    ids = []; tokens = []
    for row in value['controls']: metadata(row); ids.append(row['id']); tokens.append(row['token'])
    need(len(set(ids)) == len(ids) and len(set(tokens)) == len(tokens) and (value['open'] or not value['controls']))
    pages = [row for row in value['controls'] if row['id'] in ('avatar.page', 'people.page')]; need(len(pages) <= 1)
    if pages:
        root = pages[0]
        for row in value['controls']:
            if 'rootId' in row: need((row['rootId'], row['qmlSource']) == (root['rootId'], root['qmlSource']))
    return value


def project(original):
    need(type(original) is dict and type(original.get('avatarControlsVersion')) is int and original['avatarControlsVersion'] == VERSION)
    rows = deepcopy([row for row in original['controls'] if control_id(row['id'])])
    for row in rows:
        frame = row.pop('frame'); need(type(frame) is dict and frame['width'] > 0 and frame['height'] > 0)
        if row['id'] == 'tablet.home' or row['id'].startswith('tablet.page.'): row['inputReady'] = row['enabled']
    return snapshot(dict(avatarControlsVersion=VERSION, open=original['tabletShown'], ready=original['ready'],
        scope=dict(instance=original['instance'], generation=original['avatarGeneration'], sequence=original['lastSequence'],
            sourceSequence=original['avatarSourceSequence'], elapsedMs=original['elapsedMs'],
            capturedEpochMs=original['sampleEpochMs'], processId=original['processId']), controls=rows))


def same_reference(before, after, identifier):
    for value in (before, after): snapshot(value)
    need(all(before['scope'][key] == after['scope'][key] for key in ('instance', 'generation', 'sequence', 'processId'))
         and after['scope']['sourceSequence'] > before['scope']['sourceSequence']
         and 0 <= after['scope']['elapsedMs']-before['scope']['elapsedMs'] <= 5000
         and after['scope']['capturedEpochMs'] >= before['scope']['capturedEpochMs'])
    old = [row for row in before['controls'] if row['id'] == identifier]
    current = [row for row in after['controls'] if row['id'] == identifier]
    need(len(old) == len(current) == 1 and old == current)
    for page in ('avatar.page', 'people.page'):
        need([row for row in before['controls'] if row['id'] == page] == [row for row in after['controls'] if row['id'] == page])
    return deepcopy(old[0])


class IOSAvatarIO:
    def __init__(self, native):
        need(callable(native.capture) and callable(native.deliver)); self.native = native; self.last_input = None
    def capture(self): return project(self.native.capture())
    def command(self, identifier, action, *, reference, value=None):
        need(control_id(identifier) and identifier not in ('avatar.page', 'people.page')
             and action in ('activate', 'replace', 'set-value', 'select-index'))
        snapshot(reference); rows = [row for row in reference['controls'] if row['id'] == identifier]
        need(len(rows) == 1); row = rows[0]
        need(reference['open'] and reference['ready'] and row['enabled'] and row['inputReady'])
        if action == 'replace': need(identifier in FIELDS and row['focused']); text(value, 4096)
        elif action == 'set-value': need(identifier == 'avatar.scale' and number(value, .1, 4) and abs(value*10-round(value*10)) < .0001)
        elif action == 'select-index': need(identifier == 'avatar.wearable-choice' and integer(value, 0, len(row['choices'])-1))
        else: need(value is None)
        scope = reference['scope']; query = dict(schemaVersion=1, commandId=str(uuid.uuid4()), instance=scope['instance'],
            sequence=scope['sequence']+1, observedElapsedMs=scope['elapsedMs'], fieldToken=row['token'], operation=action)
        if action == 'replace': query['text'] = value
        elif action == 'set-value': query['value'] = value
        elif action == 'select-index': query['index'] = value
        return query
    def input(self, identifier, action, *, reference, value=None, command=None):
        query = self.command(identifier, action, reference=reference, value=value)
        if command is not None:
            need(type(command) is dict and nonce(command.get('commandId')))
            query['commandId'] = command['commandId']; need(query == command)
        current = self.capture(); same_reference(reference, current, identifier)
        self.last_input = None
        result = self.native.deliver(query)
        self.last_input = dict(command=deepcopy(query), originalReceipt=deepcopy(self.native.last_receipt))
        return result


class AvatarUI:
    """Actual widget workflow. `intent` must durably own every individual event."""
    def __init__(self, io, intent, *, delivered=None, observed=None, monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(io, IOSAvatarIO) and all(callable(fn) for fn in (intent, monotonic, sleep)))
        need(all(fn is None or callable(fn) for fn in (delivered, observed)))
        self.io, self.intent, self.monotonic, self.sleep = io, intent, monotonic, sleep
        self.delivered, self.observed = delivered, observed
        self.last = self.last_clock = None
    def capture(self):
        value = deepcopy(snapshot(self.io.capture())); scope = value['scope']
        if self.last is not None:
            old = self.last['scope']
            need(all(old[key] == scope[key] for key in ('instance', 'generation', 'processId'))
                 and all(scope[key] >= old[key] for key in ('sequence', 'elapsedMs', 'capturedEpochMs'))
                 and scope['sourceSequence'] > old['sourceSequence'])
        self.last = deepcopy(value); return value
    @staticmethod
    def row(value, identifier):
        rows = [row for row in value['controls'] if row['id'] == identifier]; need(len(rows) <= 1)
        return rows[0] if rows else None
    def now(self):
        clock = self.monotonic(); need(number(clock, 0, 1e15) and (self.last_clock is None or clock >= self.last_clock))
        self.last_clock = clock; return clock
    def wait(self, predicate):
        started = self.now()
        for attempt in range(101):
            value = self.capture()
            if predicate(value): return value
            if self.now()-started >= 10 or attempt == 100: break
            self.sleep(.1)
        raise NativeUIError('Original iOS Avatar control transition did not settle')
    def input(self, identifier, action='activate', value=None):
        before = self.capture(); row = self.row(before, identifier)
        need(row is not None and row['enabled'] and row['inputReady'])
        command = self.io.command(identifier, action, reference=before, value=value)
        intent = dict(controlId=identifier, action=action, reference=deepcopy(before), nativeCommand=deepcopy(command))
        if value is not None: intent['value'] = value
        self.intent(intent)  # Persist before crossing the native event boundary.
        self.io.input(identifier, action, reference=before, value=value, command=command)
        if self.delivered is not None: self.delivered(intent, deepcopy(self.io.last_input))
        after = self.capture(); need(after['scope']['sequence'] == before['scope']['sequence']+1)
        if self.observed is not None: self.observed(intent, deepcopy(after))
        return before, after
    def open(self, page='avatar'):
        need(page in ('avatar', 'people')); value = self.capture(); need(value['open'] and value['ready'])
        if self.row(value, page+'.page') is not None: return
        if self.row(value, page+'.entry') is None:
            self.input('tablet.home'); self.wait(lambda current: self.row(current, page+'.entry') is not None)
        self.input(page+'.entry'); self.wait(lambda current: self.row(current, page+'.page') is not None)
    def replace(self, identifier, value):
        need(identifier in FIELDS); text(value, 4096)
        self.input(identifier); self.wait(lambda current: bool(self.row(current, identifier) and self.row(current, identifier)['focused']))
        self.input(identifier, 'replace', value)
        self.wait(lambda current: bool(self.row(current, identifier) and self.row(current, identifier)['text'] == value))
    def avatar_url(self, url):
        text(url, 2048); self.open(); self.input('avatar.url-open')
        self.wait(lambda current: bool(self.row(current, 'avatar.url')))
        need(self.row(self.capture(), 'avatar.page')['popupTitle'] == 'Specify Avatar URL')
        self.replace('avatar.url', url); self.input('avatar.popup.confirm')
        self.wait(lambda current: self.row(current, 'avatar.url') is None)
    def save_bookmark(self, name):
        text(name, 256); self.open(); self.input('avatar.favorite-add')
        self.wait(lambda current: bool(self.row(current, 'avatar.favorite-name')))
        self.replace('avatar.favorite-name', name)
        need(self.row(self.capture(), 'avatar.favorite.confirm')['nameConflict'] is False)
        self.input('avatar.favorite.confirm')
        self.wait(lambda current: self.row(current, 'avatar.favorite-name') is None)
    def scale(self, value):
        need(number(value, .1, 4)); self.open(); self.input('avatar.settings-open')
        self.wait(lambda current: bool(self.row(current, 'avatar.scale')))
        self.input('avatar.scale', 'set-value', value)
        self.wait(lambda current: bool(self.row(current, 'avatar.scale') and abs(self.row(current, 'avatar.scale')['value']-value) < .0001))
        self.input('avatar.settings.confirm'); self.wait(lambda current: self.row(current, 'avatar.scale') is None)
    def choose_bookmark(self, name, *, delete=False):
        text(name, 256); need(type(delete) is bool and name); self.open()
        page = self.row(self.capture(), 'avatar.page'); need(page is not None)
        if page['manage'] != delete:
            self.input('avatar.manage'); self.wait(lambda current: self.row(current, 'avatar.page')['manage'] is delete)
        identifier = 'avatar.favorite.'+hashlib.sha256(name.encode()).hexdigest()[:32]
        self.input(identifier)
        self.wait(lambda current: self.row(current, 'avatar.page')['dialog'] == 'popup')
        need(self.row(self.capture(), 'avatar.page')['popupTitle'] == ('Delete Favorite: ' if delete else 'Load Favorite: ')+name)
        self.input('avatar.popup.confirm'); self.wait(lambda current: self.row(current, 'avatar.page')['dialog'] == 'none')
        if delete:
            self.input('avatar.manage'); self.wait(lambda current: not self.row(current, 'avatar.page')['manage'])
    def add_wearable(self, url):
        text(url, 2048); self.open(); self.input('avatar.wearables-open')
        self.wait(lambda current: self.row(current, 'avatar.page')['dialog'] == 'wearables')
        self.input('avatar.wearable-add'); self.wait(lambda current: bool(self.row(current, 'avatar.url')))
        need(self.row(self.capture(), 'avatar.page')['popupTitle'] == 'Specify Wearable URL')
        self.replace('avatar.url', url); self.input('avatar.popup.confirm')
        self.wait(lambda current: self.row(current, 'avatar.page')['dialog'] == 'wearables')
        self.input('avatar.wearables.confirm'); self.wait(lambda current: self.row(current, 'avatar.page')['dialog'] == 'none')
    def remove_wearable(self, entity_id):
        session(entity_id); self.open(); self.input('avatar.wearables-open')
        self.wait(lambda current: bool(self.row(current, 'avatar.wearable-choice')))
        choice = self.row(self.capture(), 'avatar.wearable-choice'); need(entity_id in choice['choices'])
        index = choice['choices'].index(entity_id)
        if choice['index'] != index:
            self.input('avatar.wearable-choice'); self.input('avatar.wearable-choice', 'select-index', index)
            self.wait(lambda packet: self.row(packet, 'avatar.wearable-choice')['index'] == index)
        need(self.row(self.capture(), 'avatar.wearable-remove')['selectedId'] == entity_id)
        self.input('avatar.wearable-remove')
        self.wait(lambda packet: entity_id not in self.row(packet, 'avatar.wearable-choice')['choices'])
        self.input('avatar.wearables.confirm'); self.wait(lambda packet: self.row(packet, 'avatar.page')['dialog'] == 'none')
    def request_connection(self, peer):
        session(peer); self.open('people')
        page = self.row(self.capture(), 'people.page'); need(page['dialog'] == 'none')
        if page['activeTab'] != 'nearbyTab':
            self.input('people.nearby'); self.wait(lambda packet: self.row(packet, 'people.page')['activeTab'] == 'nearbyTab')
        self.input('people.select.'+peer)
        self.wait(lambda packet: bool(self.row(packet, 'people.request.'+peer)))
        self.input('people.request.'+peer)
        self.wait(lambda packet: self.row(packet, 'people.page')['dialog'] == 'connection')
    def respond_connection(self, peer, *, accept):
        session(peer); need(type(accept) is bool); self.open('people')
        page = self.row(self.capture(), 'people.page')
        need(page['dialog'] == 'connection' and page['connectionState']['phase'] == 'incoming'
             and page['connectionState']['peer'] == peer)
        self.input('people.accept' if accept else 'people.decline')
    def remove_connection(self, username):
        text(username, 256); need(username); self.open('people')
        page = self.row(self.capture(), 'people.page'); need(page['dialog'] == 'none')
        if page['activeTab'] != 'connectionsTab':
            self.input('people.connections'); self.wait(lambda packet: self.row(packet, 'people.page')['activeTab'] == 'connectionsTab')
        identifier = 'people.remove.'+hashlib.sha256(username.encode()).hexdigest()[:32]
        selection = 'people.connection-select.'+hashlib.sha256(username.encode()).hexdigest()[:32]
        if self.row(self.capture(), identifier) is None:
            self.input(selection)
        self.wait(lambda packet: bool(self.row(packet, identifier)))
        need(self.row(self.capture(), identifier)['username'] == username)
        self.input(identifier)
    def close_connection(self):
        """Cancel pending consent, then separately close its real terminal panel."""
        self.open('people')
        for _ in range(2):
            value = self.capture(); page = self.row(value, 'people.page'); need(page is not None)
            if page['dialog'] == 'none': return
            phase = page['connectionState']['phase']
            need(phase != 'incoming')  # Incoming consent requires explicit accept/decline.
            self.input('people.cancel')
            self.wait(lambda current: self.row(current, 'people.page')['connectionState']['phase'] != phase)
        need(self.row(self.capture(), 'people.page')['dialog'] == 'none')
