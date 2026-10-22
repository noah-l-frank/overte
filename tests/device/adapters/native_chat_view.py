"""Passive original Chat model/settings source; not a full feature verdict.

The selected channel, visible model and persisted history are separate sources.
Neither a normal input receipt nor a receive-cache event supplies missing rows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context

VERSION = 2
FILE = 'feature-chat-view-observation.json'
HEX = '[0-9a-f]{32}'


def entity_id(value):
    need(type(value) is str)
    try: original = uuid.UUID(value)
    except ValueError: need(False)
    need(original.int != 0 and str(original) == value)
    return value


def vr_keyboard(value):
    """Original owner inventory, never a projection of keyboardRaised.

    Read all layers so a stale visible key outside the active layer cannot be
    hidden by the advertised raised state. No private typed text/key labels.
    """
    exact(value, {'available', 'backend', 'visible', 'instance', 'sequence', 'created', 'enabled', 'raised',
        'inputToHud', 'inputTarget', 'focusedEntity', 'tabletScreen', 'anchor', 'textDisplay', 'backPlate', 'activeLayer', 'keys', 'entities'})
    need(value['available'] is True and value['backend'] == 'native-vr-entity-keyboard'
        and all(type(value[k]) is bool for k in ('visible', 'created', 'enabled', 'raised', 'inputToHud'))
        and type(value['instance']) is str and re.fullmatch(HEX, value['instance']) and integer(value['sequence'], 1)
        and integer(value['activeLayer'], 0, 31) and type(value['keys']) is list and len(value['keys']) <= 1021
        and type(value['entities']) is list and len(value['entities']) <= 1024)
    for key in ('inputTarget', 'focusedEntity', 'tabletScreen', 'anchor', 'textDisplay', 'backPlate'):
        if value[key] is not None: entity_id(value[key])
    roles = [value[key] for key in ('anchor', 'textDisplay', 'backPlate')]
    ids = set(); keys = set(); layers = set()
    for row in value['keys']:
        exact(row, {'id', 'layer', 'pressed'}); entity_id(row['id'])
        need(row['id'] not in keys and row['id'] not in roles and integer(row['layer'], 0, 31)
            and type(row['pressed']) is bool)
        keys.add(row['id']); layers.add(row['layer'])
    for row in value['entities']:
        exact(row, {'id', 'type', 'parentId', 'visible', 'hostType'}); entity_id(row['id'])
        need(row['id'] not in ids and row['hostType'] == 'local' and type(row['visible']) is bool
            and row['type'] in ('Box', 'Text', 'Model'))
        if row['parentId'] is not None: entity_id(row['parentId'])
        ids.add(row['id'])
        if row['id'] in keys or row['id'] in (value['textDisplay'], value['backPlate']):
            need(row['parentId'] == value['anchor'])
        if row['id'] in (value['anchor'], value['backPlate']): need(row['type'] == 'Box')
        if row['id'] == value['textDisplay']: need(row['type'] == 'Text')
    if value['created']:
        need(None not in roles and len(set(roles)) == 3 and keys and value['activeLayer'] in layers
            and ids == keys | set(roles))
    else:
        need(roles == [None, None, None] and not keys and not ids and not value['raised'])
    need(value['visible'] == any(row['visible'] for row in value['entities'] if row['id'] != value['anchor']))
    return value


def measured_keyboard(value):
    need(value['available'])
    if value['backend'] == 'native-vr-entity-keyboard':
        vr_keyboard(value)
        # Preserve inconsistent original states as failures, not a successful
        # hidden keyboard or a successful typed checkpoint.
        need(value['raised'] == value['visible'] and not any(row['pressed'] for row in value['keys']))
        if value['visible']:
            need(value['enabled'] and value['created'] and not value['inputToHud']
                and value['tabletScreen'] is not None and value['inputTarget'] == value['tabletScreen'])
        by_id = {row['id']: row for row in value['entities']}
        for key in value['keys']:
            need(by_id[key['id']]['visible'] == (value['raised'] and key['layer'] == value['activeLayer']))
        for role in ('textDisplay', 'backPlate'):
            if value[role] is not None: need(by_id[value[role]]['visible'] == value['raised'])
    return value['visible']


def command(value, *, ios=False):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-chat-view-observe'
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '') + HEX, value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX, value['runId']))
    return value


def validate(value, request, pid, epoch):
    exact(request, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(request['commandId']) is str)
    command(request, ios=request['commandId'].startswith('ios-'))
    exact(value, {'chatViewVersion', 'commandId', 'runId', 'instance', 'sequence', 'processId', 'capturedEpochMs', 'source'})
    need(type(value['chatViewVersion']) is int and value['chatViewVersion'] in (1, VERSION)
         and value['commandId'] == request['commandId'] and value['runId'] == request['runId']
         and type(value['instance']) is str and re.fullmatch(HEX, value['instance'])
         and integer(value['sequence'], 1) and integer(pid, 1) and integer(value['processId'], 1) and value['processId'] == pid)
    fresh(value['capturedEpochMs'], epoch)
    source = value['source']
    exact(source, {'tabletShown', 'editorFocused', 'editorHasDraft', 'keyboard', 'ui', 'storage'})
    need(all(type(source[key]) is bool for key in ('tabletShown', 'editorFocused', 'editorHasDraft')))
    keyboard = source['keyboard']
    need(type(keyboard) is dict and type(keyboard.get('available')) is bool)
    if value['chatViewVersion'] == 2 and keyboard.get('backend') == 'native-vr-entity-keyboard':
        vr_keyboard(keyboard)
    else:
        exact(keyboard, {'available', 'backend', 'visible'} if keyboard['available'] else {'available'})
    if keyboard['available'] and keyboard['backend'] != 'native-vr-entity-keyboard':
        need(keyboard['backend'] == 'native-touch-metrics' and type(keyboard['visible']) is bool)
    texts = {context(request['runId'])[key] for key in ('unicode', 'reply', 'hidden', 'retry')}
    ui = source['ui']
    need(type(ui) is dict and type(ui.get('present')) is bool)
    digest = {'historySha256'} if value['chatViewVersion'] == 2 and ui['present'] and 'historySha256' in ui else set()
    exact(ui, {'present', 'generation', 'channel', 'draft', 'keyboardRequested', 'localMessages', 'domainMessages',
               'localRowCount', 'domainRowCount', 'visibleMessages', 'visibleRowCount'} | digest if ui['present'] else {'present'})
    if ui['present']:
        need(source['tabletShown'] and type(ui['generation']) is str and re.fullmatch(HEX, ui['generation'])
             and ui['channel'] in ('local', 'domain', 'settings') and type(ui['draft']) is str
             and ui['draft'] in texts | {''} and type(ui['keyboardRequested']) is bool
             and (not ui['draft'] or source['editorHasDraft']))
        if digest: need(type(ui['historySha256']) is str and re.fullmatch('[0-9a-f]{64}', ui['historySha256']))
        for prefix in ('local', 'domain', 'visible'):
            rows, count = ui[prefix + 'Messages'], ui[prefix + 'RowCount']
            need(type(rows) is list and integer(count, 0, 1000) and len(rows) <= count
                 and all(type(text) is str and text in texts for text in rows))
    storage = source['storage']
    exact(storage, {'kind', 'count', 'unowned', 'events', 'configSha256'})
    need(storage['kind'] in ('unset', 'null', 'empty-string', 'array', 'string-list')
         and integer(storage['count'], 0, 1000) and integer(storage['unowned'], 0, 1000)
         and type(storage['events']) is list and storage['count'] == storage['unowned'] + len(storage['events'])
         and type(storage['configSha256']) is str and re.fullmatch('[0-9a-f]{64}', storage['configSha256']))
    if storage['kind'] not in ('array', 'string-list'):
        need(storage['count'] == 0)
    if storage['kind'] == 'string-list':
        need(not storage['events'])  # Actual stored strings are not accepted-message maps.
    for event in storage['events']:
        exact(event, {'channel', 'text', 'timestamp'})
        need(event['channel'] in ('local', 'domain') and type(event['text']) is str and event['text'] in texts
             and integer(event['timestamp'], 1) and event['timestamp'] <= value['capturedEpochMs'])
    return value


def measured_view(value):
    """Only the actual UI fields. No delivery, saved-history or peer claim.

    Absent UI remains absent. A real nonempty hidden editor/focused editor or
    unavailable keyboard cannot be laundered into the journey's closed state.
    """
    request = dict(schemaVersion=1, action='feature-chat-view-observe',
                   **{key: value[key] for key in ('commandId', 'runId')})
    validate(value, request, value['processId'], value['capturedEpochMs'])
    source = value['source']; ui = source['ui']; keyboard = source['keyboard']
    visible = measured_keyboard(keyboard)
    if not ui['present']:
        need(not source['editorFocused'] and not source['editorHasDraft'] and not visible)
        return dict(open=False, channel='none', draft='', focused=False, keyboard=False, messages=[])
    need(ui['channel'] in ('local', 'domain'))
    return dict(open=True, channel=ui['channel'], draft=ui['draft'], focused=source['editorFocused'],
                keyboard=visible, messages=list(ui['visibleMessages']))


class NativeChatView:
    def __init__(self, send, read, clock_ms, guard, pid, *, ios=False, vr=False, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(v) for v in (send, read, clock_ms, guard, monotonic, sleep)) and integer(pid, 1) and type(ios) is bool)
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        need(type(vr) is bool and not (ios and vr))
        self.ios, self.vr, self.monotonic, self.sleep = ios, vr, monotonic, sleep
        self.instance, self.sequence, self.captured, self.run = None, 0, 0, None
        self.version, self.keyboard_instance, self.keyboard_sequence = 1, None, 0

    def read(self, run):
        try:
            request = dict(schemaVersion=1, commandId=('ios-' if self.ios else '') + uuid.uuid4().hex,
                           action='feature-chat-view-observe', runId=run)
            command(request, ios=self.ios)
            need(self.run in (None, run) and self.guard() is not False)
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            requested = self.clock_ms(); need(integer(requested, 1)); self.send(request)
            for attempt in range(51):
                need(self.guard() is not False); raw = self.original()
                try: value = decode(raw) if raw else None
                except json.JSONDecodeError: value = None
                if type(value) is dict and value.get('commandId') == request['commandId']:
                    # AFC/PID acquisition bounds iOS freshness. Host UTC never
                    # replaces a native timestamp from another clock domain.
                    epoch = value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    validate(value, request, self.pid, epoch)
                    need(value['chatViewVersion'] >= self.version)
                    keyboard = value['source']['keyboard']
                    if self.vr:
                        need(value['chatViewVersion'] == 2)
                        vr_keyboard(keyboard)
                        need(self.keyboard_instance in (None, keyboard['instance']) and keyboard['sequence'] > self.keyboard_sequence)
                    need(self.instance in (None, value['instance']) and value['sequence'] > self.sequence
                         and value['capturedEpochMs'] >= self.captured
                         and (self.ios or value['capturedEpochMs'] >= requested))
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                    self.run, self.instance, self.sequence, self.captured = run, value['instance'], value['sequence'], value['capturedEpochMs']
                    self.version = value['chatViewVersion']
                    if self.vr: self.keyboard_instance, self.keyboard_sequence = keyboard['instance'], keyboard['sequence']
                    return value
                now = self.monotonic(); need(number(now, 0, 1e15) and now >= previous); previous = now
                if now - started >= 5 or attempt == 50: break
                self.sleep(min(.1, 5 - (now - started)))
        except Exception:
            raise NativeUIError('Native Chat view observation failed') from None
        raise NativeUIError('Native Chat view observation is unavailable')
