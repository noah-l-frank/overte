"""Passive original Chat model/settings source; not a full feature verdict.

The selected channel, visible model and persisted history are separate sources.
Neither a normal input receipt nor a receive-cache event supplies missing rows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from copy import deepcopy
import re
import time
import uuid
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context

VERSION = 3
FILE = 'feature-chat-view-observation.json'
HEX = '[0-9a-f]{32}'


def command(value, *, ios=False):
    need(type(value) is dict)
    selected=value.get('schemaVersion')==2
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'}|({'profile'} if selected else set()))
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion'] in (1,2)
         and (not selected or ios and value['profile']=='loaded-qml-object')
         and value['action'] == 'feature-chat-view-observe'
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '') + HEX, value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX, value['runId']))
    return value


def validate(value, request, pid, epoch):
    need(type(request) is dict and type(request.get('commandId')) is str)
    command(request, ios=request['commandId'].startswith('ios-'))
    if request['schemaVersion']==2:
        exact(value, {'chatViewVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','source','loadedObjectIdentity'})
        need(type(value['chatViewVersion']) is int and value['chatViewVersion']==4)
        legacy=deepcopy(value);cut=legacy.pop('loadedObjectIdentity');legacy['chatViewVersion']=3
        query=dict(request);query.pop('profile');query['schemaVersion']=1
        validate(legacy,query,pid,epoch)
        from adapters.chat_root_loaded_identity import validate as identity_cut
        identity_cut(cut,value['source']['rootOwnership'],pid=pid,captured=value['capturedEpochMs'])
        return value
    exact(value, {'chatViewVersion', 'commandId', 'runId', 'instance', 'sequence', 'processId', 'capturedEpochMs', 'source'})
    need(type(value['chatViewVersion']) is int and value['chatViewVersion'] in (1,2,3)
         and value['commandId'] == request['commandId'] and value['runId'] == request['runId']
         and type(value['instance']) is str and re.fullmatch(HEX, value['instance'])
         and integer(value['sequence'], 1) and integer(pid, 1) and integer(value['processId'], 1) and value['processId'] == pid)
    fresh(value['capturedEpochMs'], epoch)
    source = value['source']
    exact(source, {'tabletShown', 'editorFocused', 'editorHasDraft', 'keyboard', 'ui', 'storage'}|({'rootOwnership'} if value['chatViewVersion']>=3 else set()))
    need(all(type(source[key]) is bool for key in ('tabletShown', 'editorFocused', 'editorHasDraft')))
    keyboard = source['keyboard']
    need(type(keyboard) is dict and type(keyboard.get('available')) is bool)
    exact(keyboard, {'available', 'backend', 'visible'} if keyboard['available'] else {'available'})
    if keyboard['available']:
        need(keyboard['backend'] == 'native-touch-metrics' and type(keyboard['visible']) is bool)
    texts = {context(request['runId'])[key] for key in ('unicode', 'reply', 'hidden', 'retry')}
    ui = source['ui']
    need(type(ui) is dict and type(ui.get('present')) is bool)
    exact(ui, {'present', 'generation', 'channel', 'draft', 'keyboardRequested', 'localMessages', 'domainMessages',
               'localRowCount', 'domainRowCount', 'visibleMessages', 'visibleRowCount'}|({'rootIdentity'} if value['chatViewVersion']>=3 else set()) if ui['present'] else {'present'})
    if ui['present']:
        need(source['tabletShown'] and type(ui['generation']) is str and re.fullmatch(HEX, ui['generation'])
             and ui['channel'] in ('local', 'domain', 'settings') and type(ui['draft']) is str
             and ui['draft'] in texts | {''} and type(ui['keyboardRequested']) is bool
             and (not ui['draft'] or source['editorHasDraft']))
        for prefix in ('local', 'domain', 'visible'):
            rows, count = ui[prefix + 'Messages'], ui[prefix + 'RowCount']
            need(type(rows) is list and integer(count, 0, 1000) and len(rows) <= count
                 and all(type(text) is str and text in texts for text in rows))
    storage = source['storage']
    exact(storage, {'kind', 'count', 'unowned', 'events', 'configSha256'}|({'valueSha256'} if value['chatViewVersion']>=2 else set()))
    if value['chatViewVersion']>=2:
        need(type(storage['valueSha256']) is str and re.fullmatch('[0-9a-f]{64}',storage['valueSha256']))
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
    if value['chatViewVersion']>=3:
        from adapters import chat_root_ownership as roots
        owned=roots.validate(source['rootOwnership'],pid=pid,epoch=value['capturedEpochMs'])
        if owned['available']:need(owned['capturedEpochMs']<=value['capturedEpochMs'])
        if roots.complete(owned):need(bool([page for page in owned['pages'] if page['visible']])==ui['present'])
        if ui['present']:
            need(ui['rootIdentity'] is None or type(ui['rootIdentity']) is str and re.fullmatch(HEX,ui['rootIdentity']))
            if roots.complete(owned):roots.selected(owned,ui['rootIdentity'])
    return value


def measured_view(value):
    """Only the actual UI fields. No delivery, saved-history or peer claim.

    Absent UI remains absent. A real nonempty hidden editor/focused editor or
    unavailable keyboard cannot be laundered into the journey's closed state.
    """
    request = dict(schemaVersion=1, action='feature-chat-view-observe',
                   **{key: value[key] for key in ('commandId', 'runId')})
    if value['chatViewVersion']==4:request.update(schemaVersion=2,profile='loaded-qml-object')
    validate(value, request, value['processId'], value['capturedEpochMs'])
    source = value['source']; ui = source['ui']; keyboard = source['keyboard']
    need(keyboard['available'])
    if not ui['present']:
        need(not source['editorFocused'] and not source['editorHasDraft'] and not keyboard['visible'])
        return dict(open=False, channel='none', draft='', focused=False, keyboard=False, messages=[])
    need(ui['channel'] in ('local', 'domain'))
    return dict(open=True, channel=ui['channel'], draft=ui['draft'], focused=source['editorFocused'],
                keyboard=keyboard['visible'], messages=list(ui['visibleMessages']))


class NativeChatView:
    def __init__(self, send, read, clock_ms, guard, pid, *, ios=False, monotonic=time.monotonic, sleep=time.sleep, loaded_object_identity=False):
        need(all(callable(v) for v in (send, read, clock_ms, guard, monotonic, sleep)) and integer(pid, 1) and type(ios) is bool)
        need(type(loaded_object_identity) is bool and (not loaded_object_identity or ios))
        self.loaded_object_identity=loaded_object_identity;self.identity_cut=None
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        self.ios, self.monotonic, self.sleep = ios, monotonic, sleep
        self.instance, self.sequence, self.captured, self.run = None, 0, 0, None
        self.version = None;self.ownership=None

    def read(self, run):
        try:
            request = dict(schemaVersion=1, commandId=('ios-' if self.ios else '') + uuid.uuid4().hex,
                           action='feature-chat-view-observe', runId=run)
            if self.loaded_object_identity:request.update(schemaVersion=2,profile='loaded-qml-object')
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
                    if value['chatViewVersion']>=3:
                        from adapters.chat_root_ownership import validate as roots
                        roots(value['source']['rootOwnership'],pid=self.pid,epoch=epoch,previous=self.ownership)
                    if self.loaded_object_identity:
                        from adapters.chat_root_loaded_identity import validate as identity_cut
                        identity_cut(value['loadedObjectIdentity'],value['source']['rootOwnership'],pid=self.pid,
                            captured=value['capturedEpochMs'],previous=self.identity_cut)
                    need(self.version in (None,value['chatViewVersion']) and self.instance in (None, value['instance']) and value['sequence'] > self.sequence
                         and value['capturedEpochMs'] >= self.captured
                         and (self.ios or value['capturedEpochMs'] >= requested))
                    now = self.monotonic()
                    need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                    self.run, self.instance, self.sequence, self.captured = run, value['instance'], value['sequence'], value['capturedEpochMs']
                    if self.loaded_object_identity:self.identity_cut=deepcopy(value['loadedObjectIdentity'])
                    self.version=value['chatViewVersion']
                    if self.version>=3:self.ownership=deepcopy(value['source']['rootOwnership'])
                    return value
                now = self.monotonic(); need(number(now, 0, 1e15) and now >= previous); previous = now
                if now - started >= 5 or attempt == 50: break
                self.sleep(min(.1, 5 - (now - started)))
        except Exception:
            raise NativeUIError('Native Chat view observation failed') from None
        raise NativeUIError('Native Chat view observation is unavailable')
