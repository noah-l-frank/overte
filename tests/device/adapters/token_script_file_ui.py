"""Ordinary Script file-bundle picker on actual source-owned native controls.

This is an input primitive for existing journey adapters, not another runner or
an execution verdict. The owning adapter must persist intent before opening,
bind staged original bytes independently, and verify engine/effects afterwards.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import posixpath
import re
import time
from urllib.parse import unquote, urlsplit

from adapters.normal_feature_state import need
from adapters.normal_ui import NativeUIError

FIXED = frozenset({'scripts.from-file', 'script-file.folder', 'script-file.primary',
    'script-file.select', 'script-file.cancel', 'script-file.change-selection',
    'script-file.confirm', 'script-file.review-cancel'})
PICKER_FIELDS = {'caption', 'directory', 'review', 'error', 'relativePaths', 'selectedUrls', 'bundleRoot', 'bundleUrls'}


def file_control(identifier):
    return type(identifier) is str and (identifier in FIXED or
        re.fullmatch(r'script-file\.row\.(0|[1-9][0-9]{0,3})', identifier) is not None)


def bounded_text(value, maximum=4096):
    return type(value) is str and len(value) <= maximum and not any(ord(c) < 32 for c in value)


def file_url(value):
    need(bounded_text(value) and bool(value))
    parsed = urlsplit(value)
    path = unquote(parsed.path, errors='strict')
    need(parsed.scheme == 'file' and not parsed.netloc and not parsed.query and not parsed.fragment
         and path.startswith('/') and '\\' not in path and not any(part in ('.', '..') for part in path.split('/'))
         and not any(ord(c) < 32 for c in path) and '//' not in path)
    return path.rstrip('/')


def metadata_fields(identifier):
    need(file_control(identifier))
    if identifier.startswith('script-file.row.'):
        return {'sourceUrl', 'rowLabel', 'selected', 'directory'}
    if identifier == 'script-file.folder': return {'text', 'picker'}
    if identifier == 'script-file.primary': return {'currentText', 'currentIndex'}
    if identifier in ('script-file.cancel', 'script-file.review-cancel', 'script-file.confirm'): return {'picker'}
    return set()


def validate_metadata(row):
    fields = metadata_fields(row['id'])
    need(fields <= set(row))
    if row['id'].startswith('script-file.row.'):
        file_url(row['sourceUrl'])
        need(bounded_text(row['rowLabel']) and type(row['selected']) is bool and type(row['directory']) is bool)
    elif row['id'] == 'script-file.folder': need(bounded_text(row['text']))
    elif row['id'] == 'script-file.primary':
        need(bounded_text(row['currentText']) and type(row['currentIndex']) is int and -1 <= row['currentIndex'] < 32)
    if 'picker' in fields:
        value = row['picker']
        need(type(value) is dict and set(value) == PICKER_FIELDS and value['caption'] == 'Open Script and Companion Files'
             and type(value['review']) is bool and bounded_text(value['error']))
        file_url(value['directory'])
        for key in ('relativePaths', 'selectedUrls', 'bundleUrls'):
            need(type(value[key]) is list and len(value[key]) <= 32
                 and all(bounded_text(item) and bool(item) for item in value[key])
                 and len(value[key]) == len(set(value[key])))
        for url in value['selectedUrls'] + value['bundleUrls']: file_url(url)
        for relative in value['relativePaths']:
            need(not relative.startswith('/') and '\\' not in relative
                 and not any(part in ('', '.', '..') for part in relative.split('/')))
        need(type(value['bundleRoot']) is str)
        if value['review']:
            file_url(value['bundleRoot'])
            need(len(value['relativePaths']) == len(value['bundleUrls']) > 0)
        else:
            need(value['bundleRoot'] == '' and value['relativePaths'] == [] and value['bundleUrls'] == [])


class TokenScriptFilePicker:
    def __init__(self, io, directory, *, monotonic=time.monotonic, sleep=time.sleep):
        self.io, self.directory = io, directory.rstrip('/') if type(directory) is str else directory
        self.path = file_url(directory)
        need(re.search(r'/feature-script-[0-9a-f]{32}$', self.path) is not None)
        self.monotonic, self.sleep, self.last_clock = monotonic, sleep, None
        self.instance = None

    def now(self):
        value = self.monotonic()
        need(type(value) in (int, float) and math.isfinite(value)
             and (self.last_clock is None or value >= self.last_clock))
        self.last_clock = value
        return value

    def capture(self):
        value = self.io.capture()
        need(type(value) is dict and value.get('fileControlsVersion') == 1
             and type(value['fileControlsVersion']) is int and value.get('ready') is True
             and type(value.get('controls')) is list and len(value['controls']) <= 384)
        identity = value.get('instance', value.get('bridgeId'))
        need(type(identity) is str and bool(identity) and self.instance in (None, identity))
        self.instance = identity
        ids = set()
        for row in value['controls']:
            need(type(row) is dict and type(row.get('id')) is str and row['id'] not in ids)
            ids.add(row['id'])
            if file_control(row['id']):
                need(type(row.get('enabled')) is bool and type(row.get('token')) is str and bool(row['token']))
                validate_metadata(row)
        return value

    @staticmethod
    def control(value, identifier):
        rows = [row for row in value['controls'] if row['id'] == identifier and row['enabled']]
        need(len(rows) <= 1)
        return rows[0] if rows else None

    @staticmethod
    def picker(value):
        rows = [row['picker'] for row in value['controls'] if file_control(row['id']) and 'picker' in row]
        need(not rows or all(row == rows[0] for row in rows))
        return rows[0] if rows else None

    def wait(self, predicate, *, absent=False):
        started = self.now(); stable = None
        for attempt in range(101):
            value = self.capture(); current = self.now()
            if bool(predicate(value)) != absent:
                stable = current if stable is None else stable
                if not absent or current - stable >= 0.3: return value
            else: stable = None
            if current - started >= 10: break
            self.sleep(0.1)
        raise NativeUIError('Normal Script file picker did not reach its observed state')

    def activate(self, identifier, *, source=None):
        value = self.capture(); row = self.control(value, identifier)
        need(row is not None and (source is None or row.get('sourceUrl') == source))
        self.io.activate(identifier, source=source)

    def open(self):
        need(self.picker(self.capture()) is None)
        self.activate('scripts.from-file')
        self.wait(lambda value: self.picker(value) is not None)

    def cancel(self):
        value = self.capture(); observed = self.picker(value)
        need(observed is not None)
        self.activate('script-file.review-cancel' if observed['review'] else 'script-file.cancel')
        self.wait(lambda current: self.picker(current) is not None, absent=True)

    def choose(self, resource):
        need(resource in ('script.js', 'script-bundle/main.js'))
        folder = posixpath.dirname(resource)
        path = self.path + ('/' + folder if folder else '')
        target = self.directory + ('/' + folder if folder else '')
        value = self.capture(); observed = self.picker(value)
        need(observed is not None and not observed['review'] and observed['selectedUrls'] == [])
        if file_url(observed['directory']) != path:
            self.activate('script-file.folder')
            self.io.replace('script-file.folder', path)
            field = self.control(self.capture(), 'script-file.folder')
            need(field is not None and field['text'] == path)
            self.io.submit('script-file.folder')
            self.wait(lambda current: self.picker(current) is not None
                and file_url(self.picker(current)['directory']) == path)
        chosen = []
        for name in (posixpath.basename(resource), 'companion.js'):
            expected = target + '/' + name
            value = self.capture(); observed = self.picker(value)
            need(observed is not None and observed['error'] == '' and observed['selectedUrls'] == chosen)
            rows = [row for row in value['controls'] if row['id'].startswith('script-file.row.')
                    and row['enabled'] and row['sourceUrl'] == expected and not row['directory'] and not row['selected']]
            need(len(rows) == 1)
            self.activate(rows[0]['id'], source=expected)
            chosen.append(expected)
            self.wait(lambda current: self.picker(current) is not None and self.picker(current)['selectedUrls'] == chosen)
        self.activate('script-file.select')
        current = self.wait(lambda value: self.picker(value) is not None and self.picker(value)['review'])
        review = self.picker(current)
        names = [posixpath.basename(resource), 'companion.js']
        need(review['error'] == '' and file_url(review['bundleRoot']) == path
             and review['relativePaths'] == names and review['bundleUrls'] == chosen)
        primary = self.control(current, 'script-file.primary')
        need(primary is not None)
        if primary['currentIndex'] != 0 or primary['currentText'] != names[0]:
            self.io.select_index('script-file.primary', 0)
            primary = self.control(self.capture(), 'script-file.primary')
        need(primary is not None and primary['currentIndex'] == 0 and primary['currentText'] == names[0])
        # Re-read the actual bundle immediately before the one normal Use Files
        # click. A source/row token change is also checked by the owning IO.
        need(self.picker(self.capture()) == review)
        self.activate('script-file.confirm')
        self.wait(lambda value: self.picker(value) is not None, absent=True)
