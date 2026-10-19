"""Normal Running Scripts flow on current native control tokens and row labels.

Phone uses its established W3C binding. Pico/iOS supply their real source-owned
Qt token transports here; no service call or inferred script verdict is input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import re
import time

from adapters.normal_feature_state import need
from adapters.normal_ui import NativeUIError

FIXED = frozenset({'scripts.entry', 'scripts.menu', 'scripts.menu-edit', 'scripts.menu-running',
    'scripts.from-url', 'scripts.list', 'scripts.url.field', 'scripts.url.submit', 'scripts.url.cancel'})


def script_control(identifier):
    if type(identifier) is not str:
        return False
    match = re.fullmatch(r'scripts\.(?:restart|stop)\.(0|[1-9][0-9]{0,2})', identifier)
    return identifier in FIXED or bool(match and int(match[1]) <= 127)


def metadata_fields(identifier):
    need(script_control(identifier))
    if identifier.startswith(('scripts.restart.', 'scripts.stop.')):
        return {'rowLabel', 'sourceUrl'}
    return {'text'} if identifier == 'scripts.url.field' else set()


def validate_metadata(row):
    need(type(row) is dict and 'id' in row)
    fields = metadata_fields(row['id'])
    need(fields <= set(row) and all(type(row[key]) is str and len(row[key]) <= 4096
             and not any(ord(c) < 32 for c in row[key]) for key in fields))


class TokenScriptUI:
    def __init__(self, io, *, monotonic=time.monotonic, sleep=time.sleep):
        self.io, self.monotonic, self.sleep = io, monotonic, sleep
        self.last_clock = None
        self.source = None

    def now(self):
        value = self.monotonic()
        need(type(value) in (int, float) and math.isfinite(value)
             and (self.last_clock is None or value >= self.last_clock))
        self.last_clock = value
        return value

    def capture(self):
        value = self.io.capture()
        # Owning transports additionally validate every original native field,
        # PID/clock/instance/generation/token and installed candidate association.
        need(type(value) is dict and value.get('featureControlsVersion') == 1
             and type(value['featureControlsVersion']) is int and type(value.get('open')) is bool
             and type(value.get('ready')) is bool and type(value.get('controls')) is list
             and len(value['controls']) <= 384)
        for row in value['controls']:
            need(type(row) is dict and type(row.get('id')) is str and type(row.get('enabled')) is bool)
            if script_control(row['id']):
                validate_metadata(row)
        return value

    @staticmethod
    def control(value, identifier, *, enabled=True):
        found = [row for row in value['controls'] if row['id'] == identifier]
        need(len(found) <= 1)
        return found[0] if found and (not enabled or found[0]['enabled']) else None

    def available(self, identifier, *, enabled=True):
        return self.control(self.capture(), identifier, enabled=enabled) is not None

    def wait(self, predicate, *, absent=False):
        deadline = self.now() + 10
        absent_since = None
        for _attempt in range(101):
            value = self.capture()
            matches = predicate(value)
            now = self.now()
            if not absent and matches:
                return value
            if absent:
                absent_since = now if not matches and absent_since is None else absent_since if not matches else None
                if absent_since is not None and now - absent_since >= 0.3:
                    return value
            if now >= deadline:
                break
            self.sleep(0.1)
        raise NativeUIError('Normal token UI did not reach its observed control state')

    def activate(self, identifier):
        value = self.capture()
        need(value['ready'] and self.control(value, identifier) is not None)
        self.io.activate(identifier)

    def tablet_visible(self):
        return self.capture()['open']

    def manager_visible(self):
        return self.available('scripts.from-url', enabled=False)

    def open_tablet(self):
        need(not self.capture()['open'])
        self.io.tablet(True)
        self.wait(lambda v: v['open'] and v['ready'])

    def open_manager(self):
        current = self.capture()
        need(current['open'] and current['ready'])
        if self.control(current, 'tablet.home'):
            self.activate('tablet.home')
            current = self.capture()
        pages = sorted((row['id'] for row in current['controls']
                        if re.fullmatch(r'tablet\.page\.(?:[1-9]|[12][0-9]|3[0-2])', row['id'])),
                       key=lambda name: int(name.rsplit('.', 1)[1]))
        for page in [None, *pages]:
            if page is not None:
                self.activate(page)
            # Page/app construction is asynchronous. Retry reads, never a click.
            until = self.now() + 0.6
            for _attempt in range(7):
                current = self.capture()
                if self.control(current, 'scripts.entry'):
                    self.activate('scripts.entry')
                    self.wait_manager()
                    return
                if self.control(current, 'scripts.menu'):
                    self.activate('scripts.menu')
                    self.wait(lambda v: self.control(v, 'scripts.menu-edit'))
                    self.activate('scripts.menu-edit')
                    self.wait(lambda v: self.control(v, 'scripts.menu-running'))
                    self.activate('scripts.menu-running')
                    self.wait_manager()
                    return
                if self.now() >= until:
                    break
                self.sleep(0.1)
        raise NativeUIError('Normal native Running Scripts entry is unavailable')

    def wait_manager(self):
        self.wait(lambda value: self.control(value, 'scripts.from-url'))

    def open_url_dialog(self):
        need(not self.available('scripts.url.field', enabled=False))
        self.activate('scripts.from-url')
        self.wait(lambda value: self.control(value, 'scripts.url.field'))

    def fill_url(self, url):
        self.activate('scripts.url.field')
        self.io.replace('scripts.url.field', url)
        current = self.capture()
        field = self.control(current, 'scripts.url.field')
        need(field is not None and field['text'] == url)

    def submit_url(self):
        self.activate('scripts.url.submit')

    def cancel_dialog(self):
        if self.available('scripts.url.field', enabled=False):
            self.activate('scripts.url.cancel')

    def wait_dialog_absent(self):
        self.wait(lambda value: self.control(value, 'scripts.url.field', enabled=False), absent=True)

    def check_row(self, index, name, action):
        need(type(index) is int and 0 <= index <= 127 and action in {'restart', 'stop'}
             and not self.available('scripts.url.field', enabled=False))
        row = self.control(self.capture(), 'scripts.' + action + '.' + str(index))
        need(row is not None and row['rowLabel'] == name and self.source is not None
             and row['sourceUrl'] == self.source)

    def check_source_row(self, index, name, action, source):
        self.source = source
        self.check_row(index, name, action)

    def row_action(self, index, name, action):
        self.check_row(index, name, action)
        # Carry the original source identity into the native token transport.
        # Reused delegates must retire tokens when their actual URL changes.
        self.io.activate('scripts.' + action + '.' + str(index), source=self.source)

    def close_tablet(self):
        need(not self.available('scripts.url.field', enabled=False))
        if self.tablet_visible():
            self.io.tablet(False)

    def wait_tablet_absent(self):
        self.wait(lambda value: value['open'], absent=True)

    def release(self):
        self.io.release()
