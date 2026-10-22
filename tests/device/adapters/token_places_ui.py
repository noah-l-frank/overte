"""Original Pico Places controls, models and ordinary one-send VR input.

UI effects are distinct from independently persisted bookmarks and arrivals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time

from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import navigation, nonce, scope
from feature_journeys.fixtures import context

VERSION = 1
DIGEST = r'[0-9a-f]{64}'
RATINGS = {'everyone', 'teen', 'mature', 'adult', 'unrated'}
FIELDS = {'places.search', 'places.bookmark.name', 'places.server.url'}
FIXED = {'places.entry', 'places.page', 'places.refresh', 'places.search', 'places.ratings',
         'places.bookmark.add', 'places.bookmark.name', 'places.bookmark.save', 'places.bookmark.cancel',
         'places.server.url', 'places.server.add', 'places.tab.0', 'places.tab.1', 'places.tab.2',
         'places.scroll.directory', 'places.scroll.bookmarks', 'places.scroll.servers'}


def sha(text):
    need(type(text) is str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def digest(value):
    return type(value) is str and re.fullmatch(DIGEST, value) is not None


def control_id(value):
    return type(value) is str and (value in FIXED or navigation(value)
        or value.startswith('places.rating.') and value[14:] in RATINGS
        or re.fullmatch(r'places\.(?:visit|bookmark\.(?:visit|rename|delete)|server\.(?:fetch|pin))\.' + DIGEST, value) is not None)


def dynamic_bookmark(value):
    return type(value) is str and re.fullmatch(r'places\.bookmark\.(?:visit|rename|delete)\.' + DIGEST, value) is not None


def model(value, fields):
    exact(value, {'count', 'rows'})
    need(integer(value['count'], 0, 256) and type(value['rows']) is list and len(value['rows']) == value['count'])
    for row in value['rows']:
        exact(row, fields)
        for key, item in row.items():
            if key == 'serverIndex':
                need(integer(item, 0, 255))
            elif key in ('fetched', 'pinned', 'failed'):
                need(type(item) is bool)
            else:
                need(digest(item))
    return value


def page_metadata(row):
    need(row['profile'] == 'pico-places-v1' and type(row['rootInstance']) is str
         and re.fullmatch('[0-9a-f]{32}', row['rootInstance']) and digest(row['componentSourceSha256'])
         and integer(row['tab'], 0, 2) and type(row['loading']) is bool
         and digest(row['querySha256']) and integer(row['queryLength'], 0, 8192)
         and digest(row['currentAddressSha256']) and integer(row['queueCount'], 0, 64)
         and type(row['dispatchTimerRunning']) is bool and type(row['maturity']) is list
         and len(row['maturity']) <= 5 and all(type(v) is str and v in RATINGS for v in row['maturity'])
         and len(set(row['maturity'])) == len(row['maturity']))
    model(row['directory'], {'placeNameSha256', 'placeAddressSha256', 'placeIdSha256'})
    model(row['bookmarks'], {'bookmarkNameSha256', 'bookmarkAddressSha256'})
    model(row['servers'], {'serverUrlSha256', 'serverIndex', 'fetched', 'pinned', 'failed'})
    dialog = row['dialog']
    exact(dialog, {'visible', 'originalNameSha256', 'addressSha256', 'draftSha256', 'draftLength'})
    need(type(dialog['visible']) is bool and all(digest(dialog[k]) for k in ('originalNameSha256', 'addressSha256', 'draftSha256'))
         and integer(dialog['draftLength'], 0, 8192) and row['inputReady'] is False)


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token'))
         and type(row.get('enabled')) is bool)
    base = {'id', 'token', 'enabled'}
    if navigation(row['id']):
        exact(row, base | ({'focused'} if 'focused' in row else set()) | ({'inputReady'} if 'inputReady' in row else set()))
        need(all(type(row[k]) is bool for k in set(row) - base))
        return row
    base |= {'focused', 'inputReady'}
    need(type(row.get('focused')) is bool and type(row.get('inputReady')) is bool)
    identifier = row['id']
    if identifier == 'places.page':
        exact(row, base | {'profile', 'rootInstance', 'componentSourceSha256', 'tab', 'loading', 'querySha256', 'queryLength',
            'currentAddressSha256', 'directory', 'bookmarks', 'servers', 'maturity', 'queueCount', 'dispatchTimerRunning', 'dialog'})
        page_metadata(row)
    elif identifier in FIELDS:
        exact(row, base | {'textSha256', 'textLength'})
        need(digest(row['textSha256']) and integer(row['textLength'], 0, 8192))
    elif identifier.startswith('places.scroll.'):
        exact(row, base | {'position', 'size'})
        need(number(row['position'], 0, 1) and number(row['size'], 0, 1) and row['size'] > 0
             and row['position'] + row['size'] <= 1.000001)
    elif identifier.startswith('places.rating.') or identifier.startswith(('places.server.fetch.', 'places.server.pin.')):
        exact(row, base | {'checked'})
        need(type(row['checked']) is bool)
    elif identifier.startswith('places.visit.') or dynamic_bookmark(identifier):
        exact(row, base | {'addressSha256'})
        need(digest(row['addressSha256']))
    else:
        exact(row, base)
    return row


def snapshot(value):
    exact(value, {'placesControlsVersion', 'open', 'ready', 'observedEpochMs', 'scope', 'controls'})
    need(type(value['placesControlsVersion']) is int and value['placesControlsVersion'] == VERSION
         and type(value['open']) is bool and type(value['ready']) is bool
         and integer(value['observedEpochMs'], 1)
         and (not value['ready'] or value['open'])
         and type(value['controls']) is list and len(value['controls']) <= 384)
    scope(value['scope'])
    ids, tokens = set(), set()
    for row in value['controls']:
        metadata(row)
        need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls'])
    return value


def same_reference(original, current, identifier):
    snapshot(original);snapshot(current)
    need(all(original['scope'][key] == current['scope'][key] for key in ('instance', 'generation', 'sequence', 'processId'))
         and 0 <= current['scope']['elapsedMs'] - original['scope']['elapsedMs'] <= 5000)
    need(0 <= current['observedEpochMs'] - original['observedEpochMs'] <= 5000)
    old = [row for row in original['controls'] if row['id'] == identifier]
    new = [row for row in current['controls'] if row['id'] == identifier]
    need(len(old) == len(new) == 1 and old[0] == new[0]
         and [row for row in original['controls'] if row['id'] == 'places.page']
             == [row for row in current['controls'] if row['id'] == 'places.page'])
    return old[0]


class TokenPlacesUI:
    def __init__(self, io, intent, run, *, monotonic=time.monotonic, sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep)
             and type(run) is str and re.fullmatch('[0-9a-f]{32}', run))
        self.io, self.intent, self.run, self.monotonic, self.sleep = io, intent, run, monotonic, sleep
        self.last_clock = None
        self.last = None

    def now(self):
        current = self.monotonic()
        need(number(current, 0, 1e15) and (self.last_clock is None or current >= self.last_clock))
        self.last_clock = current
        return current

    def capture(self):
        value = deepcopy(snapshot(self.io.capture()))
        if self.last is not None:
            need(all(value['scope'][k] == self.last['scope'][k] for k in ('instance', 'processId'))
                 and value['observedEpochMs'] >= self.last['observedEpochMs']
                 and all(value['scope'][k] >= self.last['scope'][k] for k in ('sequence', 'elapsedMs')))
        self.last = deepcopy(value)
        return value

    @staticmethod
    def row(value, identifier, *, enabled=True):
        found = [r for r in value['controls'] if r['id'] == identifier]
        need(len(found) <= 1)
        return found[0] if found and (not enabled or found[0]['enabled'] and found[0].get('inputReady', True)) else None

    def page(self, value):
        row = self.row(value, 'places.page', enabled=False)
        need(row is not None and value['open'] and value['ready'])
        return row

    def wait(self, predicate, seconds=20):
        deadline = self.now() + seconds
        for attempt in range(81):
            value = self.capture()
            if value['ready'] and predicate(value):
                need(self.now() <= deadline)
                return value
            remaining = deadline - self.now()
            if remaining <= 0 or attempt == 80:
                break
            self.sleep(min(.25, remaining))
        raise NativeUIError('Normal Places transition was not observed')

    def idle(self):
        return self.wait(lambda v: (p := self.page(v))['queueCount'] == 0
                         and not p['dispatchTimerRunning'] and not p['loading'])

    def input(self, identifier, action='activate', value=None):
        need(control_id(identifier) and identifier != 'places.page' and action in ('activate', 'replace', 'scroll'))
        if dynamic_bookmark(identifier):
            need(identifier.rsplit('.', 1)[1] in {sha(context(self.run)[k]) for k in ('name', 'renamed')})
        if identifier.startswith('places.visit.'):
            need(identifier == 'places.visit.' + sha(context(self.run)['name']))
        if identifier.startswith(('places.server.fetch.', 'places.server.pin.')):
            # Server mutation needs a separately owned origin recipe, not a
            # generic arbitrary unowned row action.
            raise NativeUIError('Places server ownership recipe is required')
        if action == 'replace':
            need(identifier in FIELDS and type(value) is str and len(value) <= 4096
                 and all(32 <= ord(c) <= 126 for c in value))
            if identifier in ('places.search', 'places.bookmark.name'):
                allowed = ('name', 'hidden') if identifier == 'places.search' else ('name', 'renamed')
                need(value == '' or value in {context(self.run)[k] for k in allowed})
            else:
                raise NativeUIError('Places server ownership recipe is required')
        elif action == 'scroll':
            need(identifier.startswith('places.scroll.') and value in ('up', 'down'))
        else:
            need(value is None and not identifier.startswith('places.scroll.') and identifier != 'places.server.add')
        before = self.capture()
        row = self.row(before, identifier)
        need(row is not None and before['open'] and before['ready'])
        if action == 'replace':
            need(row['focused'])
        self.intent(dict(placesInputVersion=VERSION, action=action, controlId=identifier,
                         controlToken=row['token'], scope=deepcopy(before['scope'])))
        if action == 'activate':
            self.io.activate(identifier, reference=before)
        elif action == 'replace':
            self.io.replace(identifier, value, reference=before)
        else:
            self.io.scroll(identifier, value, reference=before)
        after = self.capture()
        need(after['scope']['sequence'] == before['scope']['sequence'] + 1)
        return after

    def open(self):
        current = self.capture()
        need(current['open'] and current['ready'])
        if self.row(current, 'places.page', enabled=False) is not None:
            self.idle();return
        if self.row(current, 'places.entry') is None and self.row(current, 'tablet.home'):
            self.input('tablet.home')
        current = self.capture()
        pages = sorted((r['id'] for r in current['controls'] if navigation(r['id']) and r['id'] != 'tablet.home'),
                       key=lambda key: int(key.rsplit('.', 1)[1]))
        for page in [None, *pages]:
            if page is not None:
                self.input(page)
            until = self.now() + .6
            for _ in range(7):
                current = self.capture()
                if self.row(current, 'places.entry'):
                    self.input('places.entry')
                    self.wait(lambda v: self.row(v, 'places.page', enabled=False) is not None)
                    self.idle();return
                if self.now() >= until:
                    break
                self.sleep(.1)
        raise NativeUIError('Normal Places entry was not observed')

    def tab(self, index):
        need(integer(index, 0, 2));self.idle()
        if self.page(self.capture())['tab'] != index:
            self.input('places.tab.' + str(index))
            self.wait(lambda v: self.page(v)['tab'] == index)

    def reveal(self, identifier, area):
        need(control_id(identifier) and area in ('directory', 'bookmarks', 'servers'))
        current = self.capture()
        if self.row(current, identifier):
            return current
        deadline = self.now() + 20
        for direction in ('up', 'down'):
            for _ in range(32):
                need(self.now() < deadline)
                current = self.capture()
                if self.row(current, identifier):
                    return current
                bar = self.row(current, 'places.scroll.' + area)
                if bar is None or (direction == 'up' and bar['position'] <= .000001
                        or direction == 'down' and bar['position'] + bar['size'] >= .999999):
                    break
                self.input('places.scroll.' + area, 'scroll', direction)
                self.wait(lambda v: (r := self.row(v, 'places.scroll.' + area)) is not None
                    and (r['position'] < bar['position'] if direction == 'up' else r['position'] > bar['position']),
                    seconds=min(10, max(0, deadline - self.now())))
        raise NativeUIError('Normal Places row could not be revealed')

    def replace(self, identifier, text):
        need(identifier in ('places.search', 'places.bookmark.name'))
        allowed = ('name', 'hidden') if identifier == 'places.search' else ('name', 'renamed')
        need(type(text) is str and (text == '' or text in {context(self.run)[key] for key in allowed}))
        self.input(identifier)
        self.wait(lambda v: (self.row(v, identifier) or {}).get('focused') is True)
        self.input(identifier, 'replace', text)
        self.wait(lambda v: (self.row(v, identifier) or {}).get('textSha256') == sha(text)
                  and (self.row(v, identifier) or {}).get('textLength') == len(text))

    def bookmark_dialog(self, *, original=''):
        need(original == '' or original in {context(self.run)[k] for k in ('name', 'renamed')})
        self.tab(1)
        if original:
            identifier = 'places.bookmark.rename.' + sha(original)
            self.reveal(identifier, 'bookmarks')
        else:
            identifier = 'places.bookmark.add'
        self.input(identifier)
        self.wait(lambda v: (d := self.page(v)['dialog'])['visible'] and d['originalNameSha256'] == sha(original))

    def dismiss_bookmark(self, *, save=False):
        need(type(save) is bool and self.page(self.capture())['dialog']['visible'])
        self.input('places.bookmark.save' if save else 'places.bookmark.cancel')
        self.wait(lambda v: not self.page(v)['dialog']['visible'])
        self.idle()

    def delete_bookmark(self, name):
        need(name in {context(self.run)[k] for k in ('name', 'renamed')})
        self.tab(1)
        identifier = 'places.bookmark.delete.' + sha(name)
        self.reveal(identifier, 'bookmarks');self.input(identifier)
        self.idle()
        self.wait(lambda v: not any(r['bookmarkNameSha256'] == sha(name) for r in self.page(v)['bookmarks']['rows']))
