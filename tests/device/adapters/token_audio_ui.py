"""Normal Audio UI actions on original control/cycle tokens.

This input primitive does not prove recording/playback/acoustics. The owning
adapter must persist/validate ownership via intent before every actual input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import time
from adapters.normal_feature_state import need
from adapters.normal_ui import NativeUIError

FIXED = frozenset({'audio.entry', 'settings.entry', 'audio.settings-entry', 'audio.page',
    'audio.record', 'audio.live-echo', 'audio.mute', 'audio.mode.desktop', 'audio.mode.vr',
    'audio.scrollbar', 'audio.back'})
PHASES = {'idle', 'capturing', 'playing', 'draining', 'completed', 'cancelled', 'error'}


def audio_control(identifier): return type(identifier) is str and identifier in FIXED


def metadata_fields(identifier):
    need(audio_control(identifier))
    extra = {'audio.page': {'mode', 'nativeHmd', 'uiHmd', 'cycle'},
        'audio.record': {'cycle', 'nativeActive', 'uiActive', 'requested', 'phase', 'label'},
        'audio.live-echo': {'cycle', 'nativeActive', 'uiActive', 'requested', 'checked', 'nativeEcho'},
        'audio.mute': {'checked', 'nativeMuted', 'mode'},
        'audio.mode.desktop': {'checked', 'nativeHmd'}, 'audio.mode.vr': {'checked', 'nativeHmd'},
        'audio.scrollbar': {'position', 'size'}}
    return {'inputReady'} | extra.get(identifier, set())


def validate_metadata(row):
    identifier = row['id']; fields = metadata_fields(identifier)
    need(fields <= set(row) and type(row['inputReady']) is bool)
    for key in fields & {'nativeHmd', 'uiHmd', 'nativeActive', 'uiActive', 'requested', 'checked', 'nativeEcho', 'nativeMuted'}:
        need(type(row[key]) is bool)
    if 'cycle' in fields: need(type(row['cycle']) is int and 0 <= row['cycle'] <= 2**53 - 1)
    if 'mode' in fields: need(type(row['mode']) is int and -1 <= row['mode'] <= 1)
    if identifier == 'audio.page': need(row['inputReady'] is False)
    if identifier == 'audio.record':
        need(type(row['phase']) is str and (row['phase'] in PHASES or row['phase'] == '' and not row['inputReady'])
             and type(row['label']) is str and len(row['label']) <= 256 and all(ord(c) >= 32 for c in row['label']))
        if row['inputReady']: need(row['nativeActive'] == row['uiActive'] and not row['requested']
            and row['uiActive'] == (row['phase'] in {'capturing','playing','draining'}))
    if identifier == 'audio.live-echo' and row['inputReady']:
        need(not row['nativeActive'] and not row['uiActive'] and not row['requested'] and row['checked'] == row['nativeEcho'])
    if identifier == 'audio.mute' and row['inputReady']: need(row['checked'] == row['nativeMuted'])
    if identifier == 'audio.scrollbar':
        need(all(type(row[key]) in (int,float) and math.isfinite(row[key]) for key in ('position','size'))
             and 0 < row['size'] <= 1 and 0 <= row['position'] <= 1 - row['size'] + 1e-6)


class TokenAudioUI:
    def __init__(self, io, intent, *, monotonic=time.monotonic, sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep))
        self.io, self.intent, self.monotonic, self.sleep = io, intent, monotonic, sleep
        self.identity = self.mode = self.last_clock = self.cycle_floor = None

    def now(self):
        value = self.monotonic()
        need(type(value) in (int,float) and math.isfinite(value) and (self.last_clock is None or value >= self.last_clock))
        self.last_clock = value; return value

    @staticmethod
    def row(value, identifier, *, ready=False):
        found = [row for row in value['controls'] if row['id'] == identifier]
        need(len(found) <= 1)
        return found[0] if found and (not ready or found[0]['enabled'] and found[0]['inputReady']) else None

    def capture(self):
        value = self.io.capture()
        need(type(value) is dict and type(value.get('audioControlsVersion')) is int and value['audioControlsVersion'] == 1
             and value.get('ready') is True and type(value.get('controls')) is list and len(value['controls']) <= 384)
        instance = value.get('instance', value.get('bridgeId'))
        generation = value.get('generation')
        need(type(instance) is str and bool(instance)
             and (generation is None or type(generation) is str and bool(generation)))
        identity = (instance, generation)
        need(self.identity in (None, identity))
        self.identity = identity; seen = set()
        for row in value['controls']:
            need(type(row) is dict and type(row.get('id')) is str and row['id'] not in seen)
            seen.add(row['id'])
            if audio_control(row['id']):
                need(type(row.get('token')) is str and bool(row['token']) and type(row.get('enabled')) is bool)
                validate_metadata(row)
        page = self.row(value, 'audio.page')
        if page:
            need(self.mode in (None, page['nativeHmd'])
                 and (self.cycle_floor is None or page['cycle'] >= self.cycle_floor))
            self.mode, self.cycle_floor = page['nativeHmd'], page['cycle']
            matching = page['mode'] == int(page['nativeHmd']) and page['uiHmd'] == page['nativeHmd']
            for row in value['controls']:
                if row['id'] in ('audio.record','audio.live-echo'):
                    need(row['cycle'] == page['cycle'])
                if row['id'] in ('audio.record','audio.live-echo','audio.mute') and row['inputReady']: need(matching)
                if row['id'] == 'audio.mute': need(row['mode'] == page['mode'])
                if row['id'].startswith('audio.mode.'):
                    need(row['checked'] == (page['mode'] == int(row['id'] == 'audio.mode.vr')))
                if row['id'].startswith('audio.mode.') and row['inputReady']:
                    need(row['nativeHmd'] == page['nativeHmd'] and (row['id'] == 'audio.mode.vr') == page['nativeHmd'])
        else: need(not any(row['id'] in {'audio.record','audio.live-echo','audio.mute'} for row in value['controls']))
        return value

    def wait(self, predicate, *, stable=0):
        start = self.now(); since = None
        for _attempt in range(101):
            value = self.capture(); current = self.now()
            if current - start > 10: break
            if predicate(value):
                since = current if since is None else since
                if current - since >= stable: return value
            else: since = None
            if current - start >= 10: break
            self.sleep(0.1)
        raise NativeUIError('Normal Audio UI did not reach its observed state')

    def activate(self, identifier, verb, *, token=None, cycle=None):
        allowed = {'audio.record': {'record-start','record-cancel'}, 'audio.mute': {'mute'},
            'audio.live-echo': {'live-echo'}, 'audio.mode.desktop': {'select-current-mode'},
            'audio.mode.vr': {'select-current-mode'}, 'audio.entry': {'open-audio'},
            'settings.entry': {'open-settings'}, 'audio.settings-entry': {'open-audio-settings'},
            'audio.back': {'back-audio'}}
        need(verb in allowed.get(identifier,set()))
        value = self.capture(); row = self.row(value, identifier, ready=True)
        need(row is not None and (token is None or row['token'] == token)
             and (cycle is None or row.get('cycle') == cycle))
        if verb == 'record-start': need(not row['nativeActive'] and not row['uiActive'])
        if verb == 'record-cancel': need(row['nativeActive'] and row['uiActive'])
        self.intent(verb, value, identifier)  # Owner validates/persists actual scope before input.
        self.io.activate(identifier, token=row['token'])

    def page(self, value):
        page = self.row(value, 'audio.page'); need(page is not None)
        return page

    def current_mode(self):
        value = self.capture(); page = self.page(value)
        if page['mode'] != int(page['nativeHmd']):
            identifier = 'audio.mode.vr' if page['nativeHmd'] else 'audio.mode.desktop'
            self.activate(identifier, 'select-current-mode')
            self.wait(lambda value: self.page(value)['mode'] == int(page['nativeHmd']))
        self.wait(lambda value: self.page(value)['uiHmd'] == page['nativeHmd'])

    def visible(self, identifier):
        self.current_mode()
        for _attempt in range(7):
            value = self.capture(); row = self.row(value, identifier, ready=True)
            if row: return row
            if self.row(value, identifier) is not None:
                return self.row(self.wait(lambda current: self.row(current,identifier,ready=True) is not None), identifier)
            bar = self.row(value, 'audio.scrollbar', ready=True); need(bar is not None)
            direction = 'up' if identifier == 'audio.mute' else 'down'
            before = bar['position']
            need(before > 0 if direction == 'up' else before < 1 - bar['size'] - 1e-6)
            self.intent('scroll-' + direction, value, 'audio.scrollbar')
            self.io.scroll('audio.scrollbar', direction, token=bar['token'])
            def progress(current):
                if self.row(current,identifier,ready=True): return True
                current_bar = self.row(current,'audio.scrollbar'); need(current_bar is not None)
                return current_bar['position'] < before - 1e-6 if direction == 'up' else current_bar['position'] > before + 1e-6
            self.wait(progress)
        raise NativeUIError('Normal Audio control remains outside its actual viewport')

    def start(self):
        row = self.visible('audio.record'); need(not row['nativeActive'] and not row['uiActive'] and not row['requested'])
        cycle = row['cycle']
        self.activate('audio.record', 'record-start', token=row['token'], cycle=cycle)
        def advanced(current):
            observed = self.row(current,'audio.record',ready=True)
            if observed: need(observed['cycle'] <= cycle + 1)
            return observed is not None and observed['cycle'] == cycle + 1
        value = self.wait(advanced)
        return self.row(value, 'audio.record')  # Actual UI/cycle observation; no recording/acoustic verdict.

    def cancel(self, cycle):
        need(type(cycle) is int and cycle > 0)
        row = self.visible('audio.record'); need(row['cycle'] == cycle and row['nativeActive'] and row['uiActive'])
        self.activate('audio.record', 'record-cancel', token=row['token'], cycle=cycle)
        def cancelled(value):
            row = self.row(value,'audio.record',ready=True)
            return row and row['cycle'] == cycle and not row['nativeActive'] and not row['uiActive'] and row['phase'] == 'cancelled'
        return self.row(self.wait(cancelled,stable=0.3), 'audio.record')

    def mute(self, enabled):
        need(type(enabled) is bool)
        row = self.visible('audio.mute')
        if row['nativeMuted'] != enabled: self.activate('audio.mute', 'mute', token=row['token'])
        value = self.wait(lambda current: (self.row(current,'audio.mute',ready=True) or {}).get('nativeMuted') is enabled)
        return self.row(value,'audio.mute')

    def echo(self, enabled):
        need(type(enabled) is bool)
        row = self.visible('audio.live-echo')
        if row['nativeEcho'] != enabled: self.activate('audio.live-echo','live-echo', token=row['token'])
        value = self.wait(lambda current: (self.row(current,'audio.live-echo',ready=True) or {}).get('nativeEcho') is enabled)
        return self.row(value,'audio.live-echo')
