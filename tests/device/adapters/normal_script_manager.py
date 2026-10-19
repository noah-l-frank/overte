"""Normal Running Scripts actions, with native service reads for row identity.

The supplied UI owns its platform's native bindings. The diagnostic contains
actual service rows, not an input receipt or an execution-success verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import json
import re
import time

from adapters.normal_feature_state import context, need
from adapters.normal_ui import NativeUIError
from contracts import validate_operation_arguments
from scripts_observation import OPERATIONS, script_url
from create_observation import owned_url

DIAGNOSTIC_FILE = 'normal-feature-observation.json'


def read_native_diagnostic(read, clock_ms, guard, after_sequence, *,
                           expected_request=None, monotonic=time.monotonic, sleep=time.sleep):
    """Poll only original private native bytes; never relabel a cached sample."""
    need(type(after_sequence) is int and after_sequence >= 0)
    need(expected_request is None or type(expected_request) is str
         and re.fullmatch('(?:ios-)?[0-9a-f]{32}', expected_request) is not None)
    started = previous = monotonic()
    need(type(started) in (int, float) and math.isfinite(started))
    for _attempt in range(51):
        try:
            need(guard() is not False)
            raw = read()
            need(type(raw) is str and len(raw.encode()) <= 65536)
            def pairs(items):
                value = {}
                for key, item in items:
                    need(key not in value)
                    value[key] = item
                return value
            try:
                value = json.loads(raw, object_pairs_hook=pairs) if raw else None
            except json.JSONDecodeError:
                # Test.saveObject currently truncates/writes its fixed file.
                # A partial read is not an observation; wait only for the
                # requested original complete document within the same bound.
                if expected_request is None:
                    raise
                value = None
            epoch = clock_ms()
            need(guard() is not False)
            if expected_request is None or type(value) is dict and value.get('requestId') == expected_request:
                value = diagnostic(value, epoch)
                if value['sampleSequence'] > after_sequence:
                    return value, epoch
            now = monotonic()
            need(type(now) in (int, float) and math.isfinite(now) and now >= previous)
            previous = now
            if now - started >= 5:
                break
            sleep(0.1)
        except Exception:
            raise NativeUIError('Normal feature native diagnostic is unavailable or invalid') from None
    raise NativeUIError('Normal feature native diagnostic did not advance')


def diagnostic(value, epoch_ms):
    need(type(value) is dict and set(value) - {'requestId'} in ({'schemaVersion', 'instance', 'sampleSequence',
         'sampleEpochMs', 'complete', 'scripts'}, {'schemaVersion', 'instance', 'sampleSequence',
         'sampleEpochMs', 'complete', 'scripts', 'avatarEntities', 'entitiesComplete'})
         and set(value) >= {'schemaVersion', 'instance', 'sampleSequence',
         'sampleEpochMs', 'complete', 'scripts'}
         and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and type(value['complete']) is bool and value['complete']
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and type(value['sampleSequence']) is int and value['sampleSequence'] > 0
         and type(value['sampleEpochMs']) is int and type(epoch_ms) is int
         and -250 <= epoch_ms - value['sampleEpochMs'] <= 1500
         and type(value['scripts']) is list and len(value['scripts']) <= 128)
    need('requestId' not in value or type(value['requestId']) is str
         and re.fullmatch('(?:ios-)?[0-9a-f]{32}', value['requestId']) is not None)
    urls = set()
    for row in value['scripts']:
        need(type(row) is dict and set(row) == {'url', 'path'}
             and all(type(row[key]) is str and 0 < len(row[key]) <= 4096
                     and not any(ord(c) < 32 for c in row[key]) for key in row)
             and row['url'] not in urls)
        urls.add(row['url'])
    return value


def filename(value):
    # Match TabletRunningScripts.filename exactly, including file paths.
    return re.split('[?#]', value, maxsplit=1)[0].replace('\\', '/').rsplit('/', 1)[-1]


class NormalScriptManager:
    def __init__(self, ui, observe, store, binding, *, source_kind='scripts',
                 monotonic=time.monotonic, sleep=time.sleep):
        self.ui, self.observe, self.store = ui, observe, store
        self.binding = dict(context(binding))
        self.monotonic, self.sleep = monotonic, sleep
        need(source_kind in {'scripts', 'create-observer'})
        self.source_kind = source_kind
        self.previous = store.read()
        self.state = self.previous or dict(schemaVersion=2, sourceKind=source_kind, binding=self.binding,
            tabletOwned=False, managerOwned=False, dialogOwned=False, source=None,
            loadAttempted=False, observerInstance=None, afterSequence=0)
        value = self.state
        need(type(value) is dict and set(value) == {'schemaVersion', 'sourceKind', 'binding', 'tabletOwned',
             'managerOwned', 'dialogOwned', 'source', 'loadAttempted', 'observerInstance', 'afterSequence'}
             and type(value['schemaVersion']) is int and value['schemaVersion'] == 2
             and value['sourceKind'] == source_kind
             and context(value['binding']) == self.binding
             and all(type(value[key]) is bool for key in
                     ('tabletOwned', 'managerOwned', 'dialogOwned', 'loadAttempted'))
             and type(value['afterSequence']) is int and value['afterSequence'] >= 0
             and (value['observerInstance'] is None or type(value['observerInstance']) is str
                  and re.fullmatch('[0-9a-f]{32}', value['observerInstance']))
             and (not value['managerOwned'] or value['tabletOwned'])
             and (not value['dialogOwned'] or value['managerOwned'])
             and (not value['loadAttempted'] or value['source'] is not None))
        if value['source'] is not None:
            self.validate_url(value['source'])

    def validate_url(self, url):
        if self.source_kind == 'scripts':
            return script_url(url, missing=url.endswith('/missing.js'))
        return owned_url(url, {'observer.js'})

    def mark(self, **changes):
        value = self.state | changes
        self.store.write(value, self.previous)
        self.state = self.previous = value

    def sample(self):
        return self.sample_full()['scripts']

    def sample_full(self):
        value, epoch = self.observe(self.state['afterSequence'])
        value = diagnostic(value, epoch)
        need(self.state['observerInstance'] in (None, value['instance'])
             and value['sampleSequence'] > self.state['afterSequence'])
        self.mark(observerInstance=value['instance'], afterSequence=value['sampleSequence'])
        return value

    def wait_rows(self, predicate, seconds=10):
        started = self.monotonic()
        need(type(started) in (int, float) and math.isfinite(started))
        previous = started
        for _attempt in range(41):
            rows = self.sample()
            if predicate(rows):
                return rows
            now = self.monotonic()
            need(type(now) in (int, float) and math.isfinite(now) and now >= previous)
            previous = now
            if now - started >= seconds:
                break
            self.sleep(0.25)
        raise NativeUIError('Normal script manager did not observe its owned native row transition')

    def open(self):
        if not self.state['tabletOwned']:
            need(not self.ui.tablet_visible() and not self.ui.manager_visible())
            self.mark(tabletOwned=True)
            self.ui.open_tablet()
        if not self.state['managerOwned']:
            need(not self.ui.manager_visible())
            self.mark(managerOwned=True)
            self.ui.open_manager()
        elif not self.ui.manager_visible():
            self.ui.open_manager()
        self.ui.wait_manager()

    def source(self, url):
        self.validate_url(url)
        source = url.removesuffix('missing.js') + 'client.js' if url.endswith('/missing.js') else url
        need(self.state['source'] in (None, source))
        if self.state['source'] is None:
            rows = self.sample()
            # Never adopt an existing source, including aliases of its basename.
            need(not any(filename(row['url']) in {filename(source), 'missing.js'} for row in rows))
            self.mark(source=source)
        return source

    @staticmethod
    def row(rows, url):
        # The UI sorts by basename only. Ties make an ordinal unsafe even if
        # the desired URL itself is unique, so reject all ambiguous ordering.
        ordered = sorted(rows, key=lambda row: filename(row['url'] or row['path']).lower())
        names = [filename(row['url'] or row['path']).lower() for row in ordered]
        need(len(set(names)) == len(names) and all(name.isascii() for name in names))
        found = [index for index, row in enumerate(ordered) if row['url'] == url]
        need(len(found) <= 1)
        return (found[0], filename(url)) if found else None

    def owned_row_action(self, url, action):
        need(self.state['source'] == url)
        rows = self.sample()
        row = self.row(rows, url)
        if row is None:
            need(action == 'stop')
            return
        need(self.state['loadAttempted'])
        # Observe the actual visible row label, then recheck the independently
        # read service order immediately before one normal native click.
        self.ui.check_row(*row, action)
        need(self.sample() == rows)
        self.ui.row_action(*row, action)
        if action == 'stop':
            self.wait_rows(lambda current: not any(item['url'] == url for item in current))

    def close(self):
        errors = []
        for function in (self.close_dialog, self.close_tablet, self.ui.release):
            try:
                function()
            except Exception as error:
                errors.append(error)
        if errors:
            raise errors[0]
        need(not self.state['loadAttempted'])
        self.store.discard(self.previous)
        self.previous = None

    def close_dialog(self):
        if self.state['dialogOwned']:
            self.ui.cancel_dialog()
            self.ui.wait_dialog_absent()
            self.mark(dialogOwned=False)

    def close_tablet(self):
        if self.state['tabletOwned']:
            self.ui.close_tablet()
            self.ui.wait_tablet_absent()
            self.mark(tabletOwned=False, managerOwned=False)

    def invoke(self, operation, arguments):
        need(self.source_kind == 'scripts')
        need(operation in OPERATIONS)
        arguments = validate_operation_arguments(operation, arguments)
        if operation == 'scripts.manager.open':
            self.open()
        elif operation == 'scripts.manager.close':
            self.close()
        else:
            need(self.state['managerOwned'])
            self.ui.wait_manager()
            source = self.source(arguments['url'])
            if operation == 'scripts.load-url':
                self.load_source(arguments['url'])
            else:
                self.owned_row_action(source, 'restart' if operation == 'scripts.restart' else 'stop')
                if operation == 'scripts.stop':
                    self.mark(loadAttempted=False)
        return {'performed': True}

    def load_source(self, url):
        source = self.source(url)
        self.close_dialog()
        rows = self.sample()
        need(not any(item['url'] == url for item in rows))
        self.mark(dialogOwned=True)
        self.ui.open_url_dialog()
        self.ui.fill_url(url)
        self.mark(loadAttempted=self.state['loadAttempted'] or url == source)
        self.ui.submit_url()
        self.ui.wait_dialog_absent()
        self.mark(dialogOwned=False)

    def stop_source(self, url):
        self.owned_row_action(url, 'stop')
        self.mark(loadAttempted=False)
