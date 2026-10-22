"""Durable ordinary bookmark operations with independent original storage.

This component owns neither world arrival nor whole Navigation retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time

from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_location_bookmarks import validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState, context as binding_context
from adapters.normal_ui import NativeUIError
from adapters.token_places_ui import TokenPlacesUI, sha
from adapters.token_create_ui import nonce, scope
from feature_journeys.fixtures import context

VERSION = 1
VERBS = {'bookmark-add-cancel', 'bookmark-add', 'bookmark-rename-cancel', 'bookmark-rename', 'bookmark-delete'}


def identity(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True))


class NavigationBookmarks:
    def __init__(self, ui_factory, native, path, run, binding, *, monotonic=time.monotonic, sleep=time.sleep):
        need(callable(ui_factory) and callable(monotonic) and callable(sleep)
             and type(run) is str and re.fullmatch('[0-9a-f]{32}', run))
        binding_context(binding)
        self.native, self.store, self.run, self.binding = native, PrivateFeatureState(path), run, deepcopy(binding)
        self.monotonic, self.sleep, self.last_clock = monotonic, sleep, None
        self.deadline = None
        self.state = self.store.read()
        if self.state is not None:
            self._validate_state(self.state)
        self.ui = ui_factory(self._intent)
        need(isinstance(self.ui, TokenPlacesUI) and self.ui.run == run)

    def now(self):
        current = self.monotonic()
        need(number(current, 0, 1e15) and (self.last_clock is None or current >= self.last_clock))
        need(self.deadline is None or current <= self.deadline)
        self.last_clock = current
        return current

    def _save(self, value):
        self._validate_state(value)
        self.store.write(value, self.state)
        self.state = deepcopy(value)

    def _archive(self, value):
        # Pure validation of retained originals at their original timestamp.
        # Currentness is established only by a new guarded native read.
        need(type(value) is dict)
        request = dict(schemaVersion=1, action='feature-location-bookmarks', commandId=value.get('commandId'), runId=self.run)
        native_packet(value, request, int(self.binding['processIdentity'].split(':', 1)[0]), value.get('capturedEpochMs'))
        return value

    def _validate_state(self, value):
        exact(value, {'navigationBookmarksVersion', 'runId', 'binding', 'nativeInstance', 'original', 'lastNative', 'active', 'completed'})
        need(type(value['navigationBookmarksVersion']) is int and value['navigationBookmarksVersion'] == VERSION
             and value['runId'] == self.run and value['binding'] == self.binding
             and type(value['nativeInstance']) is str and re.fullmatch('[0-9a-f]{32}', value['nativeInstance']))
        original = value['original']
        exact(original, {'native', 'storage', 'unownedUiSha256', 'addressSha256', 'rootInstance', 'componentSourceSha256'})
        self._archive(original['native']);self._archive(value['lastNative'])
        need(original['storage'] == original['native']['storage'] and not original['storage']['owned']
             and original['native']['instance'] == value['nativeInstance'] == value['lastNative']['instance']
             and value['lastNative']['sequence'] >= original['native']['sequence']
             and value['lastNative']['capturedEpochMs'] >= original['native']['capturedEpochMs']
             and type(original['rootInstance']) is str and re.fullmatch('[0-9a-f]{32}', original['rootInstance']))
        for key in ('unownedUiSha256', 'addressSha256', 'componentSourceSha256'):
            need(type(original[key]) is str and re.fullmatch('[0-9a-f]{64}', original[key]))
        need(type(value['completed']) is list and len(value['completed']) <= 8)
        tickets = set();sequence = original['native']['sequence'];epoch = original['native']['capturedEpochMs']
        for completed in value['completed']:
            exact(completed, {'ticket', 'verb', 'storage', 'quiet', 'quietUi'})
            need(type(completed['ticket']) is str and re.fullmatch('[0-9a-f]{32}', completed['ticket'])
                 and completed['ticket'] not in tickets and completed['verb'] in VERBS
                 and type(completed['quiet']) is list and 3 <= len(completed['quiet']) <= 8
                 and type(completed['quietUi']) is list and len(completed['quietUi']) == len(completed['quiet']))
            first = completed['quiet'][0];previous = None
            for packet in completed['quiet']:
                self._archive(packet)
                need(packet['instance'] == value['nativeInstance'] and packet['sequence'] > sequence
                     and packet['capturedEpochMs'] >= epoch
                     and packet['storage'] == completed['storage']
                     and (previous is None or 0 <= packet['capturedEpochMs'] - previous <= 1500))
                previous = packet['capturedEpochMs'];epoch = previous;sequence = packet['sequence']
            need(previous - first['capturedEpochMs'] >= 3000)
            previous_ui = None
            for packet, ui in zip(completed['quiet'], completed['quietUi']):
                exact(ui, {'scope', 'observedEpochMs', 'rootInstance', 'pageSha256'})
                scope(ui['scope'])
                need(ui['rootInstance'] == original['rootInstance'] and integer(ui['observedEpochMs'], 1)
                     and 0 <= packet['capturedEpochMs'] - ui['observedEpochMs'] <= 1500
                     and ui['scope']['instance'] == self.binding['sessionId']
                     and ui['scope']['processId'] == packet['processId']
                     and type(ui['pageSha256']) is str and re.fullmatch('[0-9a-f]{64}', ui['pageSha256'])
                     and (previous_ui is None or (0 <= ui['observedEpochMs'] - previous_ui['observedEpochMs'] <= 1500
                         and ui['pageSha256'] == previous_ui['pageSha256']
                         and ui['scope']['elapsedMs'] >= previous_ui['scope']['elapsedMs']
                         and ui['scope']['sequence'] == previous_ui['scope']['sequence']
                         and ui['scope']['generation'] == previous_ui['scope']['generation'])))
                previous_ui = ui
            need(completed['quietUi'][-1]['observedEpochMs'] - completed['quietUi'][0]['observedEpochMs'] >= 3000
                 and completed['quietUi'][-1]['scope']['elapsedMs'] - completed['quietUi'][0]['scope']['elapsedMs'] >= 3000)
            need(completed['storage']['owned'] == self._expected_owned(completed['verb'], original=original)
                 and completed['storage']['unownedCount'] == original['storage']['unownedCount']
                 and completed['storage']['unownedSha256'] == original['storage']['unownedSha256'])
            tickets.add(completed['ticket'])
        need(value['lastNative']['sequence'] >= sequence and value['lastNative']['capturedEpochMs'] >= epoch)
        if value['active'] is not None:
            active = value['active']
            exact(active, {'ticket', 'verb', 'beforeNative', 'stage', 'pending'})
            need(type(active['ticket']) is str and re.fullmatch('[0-9a-f]{32}', active['ticket'])
                 and active['ticket'] not in tickets and active['verb'] in VERBS)
            plan = self._plan(active['verb'])
            self._archive(active['beforeNative'])
            need(active['beforeNative']['instance'] == value['nativeInstance']
                 and active['beforeNative']['sequence'] <= value['lastNative']['sequence']
                 and active['beforeNative']['storage']['unownedSha256'] == original['storage']['unownedSha256']
                 and active['beforeNative']['storage']['unownedCount'] == original['storage']['unownedCount']
                 and active['beforeNative']['storage']['owned'] == self._expected_owned(active['verb'], before=True, original=original))
            need(type(active['stage']) is int and 0 <= active['stage'] <= len(plan))
            if active['pending'] is not None:
                pending = active['pending']
                exact(pending, {'placesInputVersion', 'action', 'controlId', 'controlToken', 'scope'})
                need(active['stage'] < len(plan) and type(pending['placesInputVersion']) is int and pending['placesInputVersion'] == 1
                     and pending['controlId'] == plan[active['stage']][1] and pending['action'] == plan[active['stage']][2]
                     and nonce(pending['controlToken']))
                scope(pending['scope'])
                need(pending['scope']['instance'] == self.binding['sessionId'])

    def _intent(self, value):
        self.now()
        need(self.state is not None and self.state['active'] is not None
             and self.state['active']['pending'] is None)
        current = deepcopy(self.state)
        current['active']['pending'] = deepcopy(value)
        self._save(current)

    def _unowned_ui(self, page):
        owned = {sha(context(self.run)[k]) for k in ('name', 'renamed')}
        return identity([row for row in page['bookmarks']['rows'] if row['bookmarkNameSha256'] not in owned])

    def _sample(self):
        self.now()
        captured = self.ui.capture()
        page = self.ui.page(captured)
        native = self.native.read(self.run)
        self.now()
        need(captured['scope']['processId'] == native['processId'] == int(self.binding['processIdentity'].split(':', 1)[0])
             and 0 <= native['capturedEpochMs'] - captured['observedEpochMs'] <= 1500
             and captured['scope']['instance'] == self.binding['sessionId'])
        if self.state is not None:
            original = self.state['original']
            need(native['instance'] == self.state['nativeInstance']
                 and native['sequence'] > self.state['lastNative']['sequence']
                 and native['capturedEpochMs'] >= self.state['lastNative']['capturedEpochMs']
                 and page['rootInstance'] == original['rootInstance']
                 and page['componentSourceSha256'] == original['componentSourceSha256']
                 and page['currentAddressSha256'] == original['addressSha256']
                 and native['storage']['unownedCount'] == original['storage']['unownedCount']
                 and native['storage']['unownedSha256'] == original['storage']['unownedSha256']
                 and self._unowned_ui(page) == original['unownedUiSha256'])
            current = deepcopy(self.state);current['lastNative'] = native;self._save(current)
        return dict(ui=captured, page=page, native=native)

    def prepare(self):
        if self.state is not None:
            return self._sample()
        sample = self._sample()
        need(not sample['page']['dialog']['visible'] and not sample['native']['storage']['owned']
             and sample['page']['bookmarks']['count'] == sample['native']['storage']['count']
             and not sample['page']['loading'] and sample['page']['queueCount'] == 0
             and not sample['page']['dispatchTimerRunning'])
        self._save(dict(navigationBookmarksVersion=VERSION, runId=self.run, binding=self.binding,
            nativeInstance=sample['native']['instance'], lastNative=sample['native'], original=dict(native=sample['native'], storage=sample['native']['storage'],
                unownedUiSha256=self._unowned_ui(sample['page']), addressSha256=sample['page']['currentAddressSha256'],
                rootInstance=sample['page']['rootInstance'],
                componentSourceSha256=sample['page']['componentSourceSha256']), active=None, completed=[]))
        return sample

    def _plan(self, verb):
        name, renamed = (context(self.run)[key] for key in ('name', 'renamed'))
        if verb == 'bookmark-delete':
            return [('tab', 'places.tab.1', 'activate', None),
                    ('finish', 'places.bookmark.delete.' + sha(renamed), 'activate', None)]
        rename = verb in ('bookmark-rename', 'bookmark-rename-cancel')
        return [('tab', 'places.tab.1', 'activate', None),
            ('dialog', 'places.bookmark.rename.' + sha(name) if rename else 'places.bookmark.add', 'activate', None),
            ('focus', 'places.bookmark.name', 'activate', None),
            ('draft', 'places.bookmark.name', 'replace', renamed if rename else name),
            ('finish', 'places.bookmark.cancel' if verb.endswith('-cancel') else 'places.bookmark.save', 'activate', None)]

    def _expected_owned(self, verb, *, before=False, original=None):
        name, renamed = (context(self.run)[key] for key in ('name', 'renamed'))
        if before:
            names = [] if verb in ('bookmark-add', 'bookmark-add-cancel') else [renamed if verb == 'bookmark-delete' else name]
        else:
            names = [name] if verb in ('bookmark-add', 'bookmark-rename-cancel') else [renamed] if verb == 'bookmark-rename' else []
        original = self.state['original'] if original is None else original
        return [dict(name=value, addressSha256=original['addressSha256']) for value in names]

    def _finish(self, sample, active):
        page, storage = sample['page'], sample['native']['storage']
        if page['dialog']['visible'] or page['queueCount'] or page['dispatchTimerRunning'] or page['loading']:
            return False
        expected = self._expected_owned(active['verb'])
        ui_owned = [dict(bookmarkNameSha256=sha(row['name']), bookmarkAddressSha256=row['addressSha256']) for row in expected]
        allowed = {sha(context(self.run)[k]) for k in ('name', 'renamed')}
        actual_owned = [row for row in page['bookmarks']['rows'] if row['bookmarkNameSha256'] in allowed]
        stable = storage == active['beforeNative']['storage'] if active['verb'].endswith('-cancel') else storage['owned'] == expected
        return stable and actual_owned == ui_owned

    def _effect(self, sample, active, stage):
        page = sample['page']
        if stage == 'finish':
            return self._finish(sample, active)
        need(sample['native']['storage'] == active['beforeNative']['storage'])
        rename = active['verb'] in ('bookmark-rename', 'bookmark-rename-cancel')
        original = context(self.run)['name'] if rename else ''
        if stage == 'tab':
            return page['tab'] == 1 and not page['dialog']['visible']
        dialog = page['dialog']
        if (not dialog['visible'] or dialog['originalNameSha256'] != sha(original)
                or dialog['addressSha256'] != self.state['original']['addressSha256']):
            return False
        editor = self.ui.row(sample['ui'], 'places.bookmark.name', enabled=False)
        if stage == 'dialog':
            return dialog['draftSha256'] == sha(original)
        if stage == 'focus':
            return editor is not None and editor['focused'] and dialog['draftSha256'] == sha(original)
        text = context(self.run)['renamed' if rename else 'name']
        return (editor is not None and editor['focused'] and editor['textSha256'] == sha(text)
            and editor['textLength'] == len(text) and dialog['draftSha256'] == sha(text) and dialog['draftLength'] == len(text))

    def _wait(self, predicate):
        started = self.now()
        for index in range(81):
            sample = self._sample()
            if predicate(sample):
                need(self.now() - started <= 20)
                return sample
            remaining = 20 - (self.now() - started)
            if remaining <= 0 or index == 80:
                break
            self.sleep(min(.25, remaining))
        raise NativeUIError('Original bookmark operation remains unresolved')

    def _quiet(self, active):
        start = self.now();first_epoch = None;previous_epoch = None;count = 0;storage = None;packets = [];ui_rows = []
        for _ in range(8):
            sample = self._sample()
            need(self._finish(sample, active))
            if storage is None:
                storage = sample['native']['storage']
            need(sample['native']['storage'] == storage)
            epoch = sample['native']['capturedEpochMs']
            if first_epoch is None:
                first_epoch = epoch
            need(previous_epoch is None or 0 <= epoch - previous_epoch <= 1500)
            previous_epoch = epoch;count += 1
            packets.append(sample['native'])
            ui = dict(scope=sample['ui']['scope'], observedEpochMs=sample['ui']['observedEpochMs'],
                      rootInstance=sample['page']['rootInstance'], pageSha256=identity(sample['page']))
            if ui_rows:
                need(0 <= ui['observedEpochMs'] - ui_rows[-1]['observedEpochMs'] <= 1500
                     and ui['pageSha256'] == ui_rows[-1]['pageSha256']
                     and ui['scope']['generation'] == ui_rows[-1]['scope']['generation']
                     and ui['scope']['sequence'] == ui_rows[-1]['scope']['sequence'])
            ui_rows.append(ui)
            elapsed = self.now() - start
            need(elapsed <= 20)
            if elapsed >= 3 and epoch - first_epoch >= 3000 and count >= 3:
                need(ui_rows[-1]['observedEpochMs'] - ui_rows[0]['observedEpochMs'] >= 3000
                     and ui_rows[-1]['scope']['elapsedMs'] - ui_rows[0]['scope']['elapsedMs'] >= 3000)
                return sample, packets, ui_rows
            self.sleep(.5)
        raise NativeUIError('Original bookmark storage did not remain quiet')

    def act(self, ticket, verb):
        need(self.deadline is None)
        self.deadline = self.now() + 20
        try:
            return self._act(ticket, verb)
        finally:
            self.deadline = None

    def _act(self, ticket, verb):
        need(type(ticket) is str and re.fullmatch('[0-9a-f]{32}', ticket) and verb in VERBS)
        self.prepare()
        completed = [row for row in self.state['completed'] if row['ticket'] == ticket]
        if completed:
            need(len(completed) == 1 and completed[0]['verb'] == verb and self.state['active'] is None)
            need(self._sample()['native']['storage'] == completed[0]['storage'])
            return dict(performed=True)
        if self.state['active'] is None:
            before = self._sample()
            need(not before['page']['dialog']['visible']
                 and before['native']['storage']['owned'] == self._expected_owned(verb, before=True)
                 and len(self.state['completed']) < 8)
            current = deepcopy(self.state)
            current['active'] = dict(ticket=ticket, verb=verb, beforeNative=before['native'], stage=0, pending=None)
            self._save(current)
        need(self.state['active']['ticket'] == ticket and self.state['active']['verb'] == verb)
        plan = self._plan(verb)
        while self.state['active']['stage'] < len(plan):
            active = self.state['active'];stage, identifier, action, text = plan[active['stage']]
            if active['pending'] is None:
                sample = self._sample()
                if stage == 'tab' and self._effect(sample, active, stage):
                    current = deepcopy(self.state);current['active']['stage'] += 1;self._save(current);continue
                self.ui.input(identifier, action, text)
                active = self.state['active']
            pending = active['pending']
            need(pending is not None and pending['controlId'] == identifier and pending['action'] == action)
            def observed(sample):
                current = sample['ui']['scope'];old = pending['scope']
                need(all(current[k] == old[k] for k in ('instance', 'generation', 'processId'))
                     and old['sequence'] <= current['sequence'] <= old['sequence'] + 1)
                return current['sequence'] == old['sequence'] + 1 and self._effect(sample, active, stage)
            self._wait(observed)
            current = deepcopy(self.state);current['active']['stage'] += 1;current['active']['pending'] = None;self._save(current)
        last, packets, ui_rows = self._quiet(self.state['active'])
        current = deepcopy(self.state)
        current['completed'].append(dict(ticket=ticket, verb=verb, storage=last['native']['storage'], quiet=packets, quietUi=ui_rows))
        current['active'] = None
        self._save(current)
        return dict(performed=True)
