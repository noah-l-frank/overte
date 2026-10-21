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
from copy import deepcopy

from adapters.normal_feature_state import context, need
from adapters.normal_ui import NativeUIError
from contracts import validate_operation_arguments
from scripts_observation import OPERATIONS, script_url
from create_observation import owned_url
from urllib.parse import urlsplit

DIAGNOSTIC_FILE = 'normal-feature-observation.json'
MISSING_VERSION = 1


def missing_script_url(url):
    need(type(url) is str and 0 < len(url) <= 4096 and url.isascii()
         and not any(ord(c) <= 32 for c in url) and '%' not in url and '\\' not in url
         and '?' not in url and '#' not in url)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise NativeUIError('Invalid owned missing Script URL') from None
    need(parts.scheme in {'http', 'https'} and bool(parts.hostname)
         and parts.username is None and parts.password is None
         and (port is None or 1 <= port <= 65535)
         and re.fullmatch(r'/feature-fixture/v1/runs/[0-9a-f]{32}/tickets/[0-9a-f]{32}/missing\.js', parts.path))
    return url


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
                 monotonic=time.monotonic, sleep=time.sleep, component_only=False,
                 file_owner=None, file_picker=None):
        self.ui, self.observe, self.store = ui, observe, store
        self.binding = dict(context(binding, component_only=component_only))
        self.monotonic, self.sleep = monotonic, sleep
        need(source_kind in {'scripts', 'create-observer', 'script-file-bundle', 'feature-script-missing'})
        self.source_kind = source_kind
        bundled = source_kind == 'script-file-bundle'
        missing = source_kind == 'feature-script-missing'
        self.file_owner, self.file_picker = file_owner, file_picker
        if bundled:
            from adapters.native_script_files import OwnedScriptFiles
            from adapters.token_script_file_ui import TokenScriptFilePicker
            need(isinstance(file_owner, OwnedScriptFiles) and isinstance(file_picker, TokenScriptFilePicker)
                 and file_owner.binding == self.binding and file_owner.component_only == component_only)
            file_owner.owned()  # Persistent native-file intent must already exist.
        else:
            need(file_owner is None and file_picker is None)
        self.previous = store.read()
        self.retired=False
        initial = dict(schemaVersion=4 if missing else 3 if bundled else 2, sourceKind=source_kind, binding=self.binding,
            tabletOwned=False, managerOwned=False, dialogOwned=False, source=None,
            loadAttempted=False, observerInstance=None, afterSequence=0)
        if bundled: initial.update(fileOwnershipVersion=1, fileOwner=None, pickerOwned=False)
        if missing: initial.update(missingLoadVersion=MISSING_VERSION, missingLoad=None)
        self.state = self.previous or initial
        value = self.state
        need(type(value) is dict and set(value) == {'schemaVersion', 'sourceKind', 'binding', 'tabletOwned',
             'managerOwned', 'dialogOwned', 'source', 'loadAttempted', 'observerInstance', 'afterSequence'}
             | ({'fileOwnershipVersion', 'fileOwner', 'pickerOwned'} if bundled else set())
             | ({'missingLoadVersion', 'missingLoad'} if missing else set())
             and type(value['schemaVersion']) is int and value['schemaVersion'] == (4 if missing else 3 if bundled else 2)
             and value['sourceKind'] == source_kind
             and context(value['binding'], component_only=component_only) == self.binding
             and all(type(value[key]) is bool for key in
                     ('tabletOwned', 'managerOwned', 'dialogOwned', 'loadAttempted'))
             and type(value['afterSequence']) is int and value['afterSequence'] >= 0
             and (value['observerInstance'] is None or type(value['observerInstance']) is str
                  and re.fullmatch('[0-9a-f]{32}', value['observerInstance']))
             and (not value['managerOwned'] or value['tabletOwned'])
             and (not value['dialogOwned'] or value['managerOwned'])
             and (not value['loadAttempted'] or value['source'] is not None))
        if bundled:
            need(type(value['fileOwnershipVersion']) is int and value['fileOwnershipVersion'] == 1
                 and type(value['pickerOwned']) is bool and not value['dialogOwned']
                 and (not value['pickerOwned'] or value['managerOwned'] and value['fileOwner'] is not None)
                 and (value['source'] is None or value['fileOwner'] is not None))
            self.check_file_owner(value['fileOwner'])
        if missing:
            need(type(value['missingLoadVersion']) is int and value['missingLoadVersion'] == MISSING_VERSION)
            self.check_missing_load(value['missingLoad'])
        if value['source'] is not None:
            self.validate_url(value['source'])

    def validate_url(self, url):
        if self.source_kind == 'feature-script-missing': return missing_script_url(url)
        if self.source_kind == 'scripts':
            return script_url(url, missing=url.endswith('/missing.js'))
        if self.source_kind == 'script-file-bundle':
            owner = self.state['fileOwner']; need(owner is not None)
            need(type(url) is str and url in {owner['directory'] + '/' + name for name in ('script.js', 'script-bundle/main.js')})
            return url
        return owned_url(url, {'observer.js'})

    def check_file_owner(self, value):
        from adapters.token_script_file_ui import file_url
        current = self.file_owner.owned()
        if value is None: return current
        need(type(value) is dict and set(value) == {'runId', 'ownerToken', 'hashes', 'directory'}
             and all(value[key] == current[key] for key in ('runId', 'ownerToken', 'hashes'))
             and file_url(value['directory']).endswith('/feature-script-' + current['runId'])
             and value['directory'] == self.file_picker.directory)
        return current

    def file_picker_open(self):
        self.require_current()
        need(self.source_kind == 'script-file-bundle' and self.state['managerOwned']
             and not self.state['pickerOwned'])
        current = self.check_file_owner(self.state['fileOwner'])
        directory = self.file_owner.verify()  # Separate original byte read, not stage ACK.
        need(directory == self.file_picker.directory)
        owner = {key: deepcopy(current[key]) for key in ('runId', 'ownerToken', 'hashes')}
        owner['directory'] = directory
        need(self.state['fileOwner'] in (None, owner))
        self.ui.wait_manager()
        need(self.file_picker.picker(self.file_picker.capture()) is None)
        self.mark(fileOwner=owner, pickerOwned=True)  # Before one ordinary Open.
        self.file_picker.open()

    def file_picker_choose(self, resource):
        self.require_current()
        need(self.source_kind == 'script-file-bundle' and self.state['pickerOwned']
             and not self.state['loadAttempted'] and resource in ('script.js', 'script-bundle/main.js'))
        self.check_file_owner(self.state['fileOwner'])
        need(self.file_owner.verify() == self.state['fileOwner']['directory'])
        source = self.state['fileOwner']['directory'] + '/' + resource
        rows = self.sample()
        need(not any(filename(row['url']).lower() == filename(source).lower() for row in rows))
        # A partial/uncertain selection must never be replayed or adopted as
        # functional success. Record the exact owned source before any choice.
        self.mark(source=source, loadAttempted=True)
        self.file_picker.choose(resource)
        self.mark(pickerOwned=False)

    def file_picker_cancel(self):
        self.require_current()
        need(self.source_kind == 'script-file-bundle' and self.state['pickerOwned'])
        self.check_file_owner(self.state['fileOwner'])
        self.close_dialog()

    def mark(self, **changes):
        value = self.state | changes
        self.store.write(value, self.previous)
        self.state = self.previous = value

    def require_current(self):
        # A retained object cannot send input after an explicit ownership
        # transfer or another invocation changed its original private record.
        need(not self.retired and json.dumps(self.store.read(),sort_keys=True,allow_nan=False)
             == json.dumps(self.previous,sort_keys=True,allow_nan=False))

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
        self.require_current()
        if not self.state['tabletOwned']:
            need(not self.ui.tablet_visible() and not self.ui.manager_visible())
            self.mark(tabletOwned=True)
            self.ui.open_tablet()
        if not self.state['managerOwned']:
            if self.source_kind in {'script-file-bundle','feature-script-missing'}:
                need(self.ui.tablet_visible())
            need(not self.ui.manager_visible())
            self.mark(managerOwned=True)
            self.ui.open_manager()
        elif not self.ui.manager_visible():
            if self.source_kind not in {'script-file-bundle','feature-script-missing'}:
                self.ui.open_manager()
        self.ui.wait_manager()

    def source(self, url):
        self.validate_url(url)
        source = (url.removesuffix('missing.js') + 'client.js'
                  if self.source_kind != 'feature-script-missing' and url.endswith('/missing.js') else url)
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
        self.require_current()
        need(self.source_kind != 'feature-script-missing')
        need(self.state['source'] == url)
        rows = self.sample()
        row = self.row(rows, url)
        if row is None:
            need(action == 'stop')
            return
        need(self.state['loadAttempted'])
        # Observe the actual visible row label, then recheck the independently
        # read service order immediately before one normal native click.
        check_source = getattr(self.ui, 'check_source_row', None)
        if callable(check_source):
            check_source(*row, action, url)
        else:
            self.ui.check_row(*row, action)
        need(self.sample() == rows)
        self.ui.row_action(*row, action)
        if action == 'stop':
            self.wait_rows(lambda current: not any(item['url'] == url for item in current))

    def close(self):
        if self.retired:
            need(self.store.read() is None)
            return
        self.require_current()
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
        self.retired=True

    def close_dialog(self):
        self.require_current()
        if self.source_kind == 'script-file-bundle':
            if self.state['pickerOwned']:
                self.check_file_owner(self.state['fileOwner'])
                if self.file_picker.picker(self.file_picker.capture()) is not None:
                    self.file_picker.cancel()
                else:
                    self.file_picker.wait(lambda value: self.file_picker.picker(value) is not None, absent=True)
                self.mark(pickerOwned=False)
            return
        if self.state['dialogOwned']:
            self.ui.cancel_dialog()
            self.ui.wait_dialog_absent()
            self.mark(dialogOwned=False)

    def close_tablet(self):
        self.require_current()
        need(not self.state['dialogOwned']
             and (self.source_kind != 'script-file-bundle' or not self.state['pickerOwned']))
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
        self.require_current()
        need(self.source_kind not in {'script-file-bundle', 'feature-script-missing'})
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
        need(self.source_kind != 'feature-script-missing')
        self.owned_row_action(url, 'stop')
        self.mark(loadAttempted=False)

    def check_missing_load(self, value):
        from adapters.native_script_loads import validate as loads, result
        if value is None:
            need(not self.state['loadAttempted'])
            return
        need(type(value) is dict and set(value) == {'phase', 'instance', 'pid', 'sequence', 'epoch', 'history', 'completed'}
             and value['phase'] in ('issued', 'settled')
             and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
             and type(value['pid']) is int and value['pid'] > 0
             and type(value['sequence']) is int and value['sequence'] > 0
             and type(value['epoch']) is int and value['epoch'] > 0
             and self.binding['processIdentity'].split(':')[0] == str(value['pid'])
             and self.state['source'] is not None
             and self.state['loadAttempted'] == (value['phase'] == 'issued'))
        loads(value['history'], value['epoch'])
        completed = value['completed']
        if value['phase'] == 'issued': need(completed is None)
        else:
            need(type(completed) is dict and set(completed) == {'epoch', 'history', 'event'}
                 and type(completed['epoch']) is int and completed['epoch'] >= value['epoch'])
            final = loads(completed['history'], completed['epoch']); prefix = value['history']
            need(final['instance'] == prefix['instance'] and final['events'][:prefix['sequence']] == prefix['events'])
            actual = result(dict(source=dict(loadSourceVersion=1, loads=final), capturedEpochMs=completed['epoch']),
                self.state['source'], after_sequence=prefix['sequence'], after_epoch=value['epoch'])
            need(completed['event'] == actual and actual['success'] is False)

    def missing_reader(self, execution):
        from adapters.native_script_observation import NativeScriptObservation
        need(self.source_kind == 'feature-script-missing' and isinstance(execution, NativeScriptObservation)
             and self.binding['processIdentity'].split(':')[0] == str(execution.pid)
             and execution.guard() is not False)
        return execution

    def load_missing(self, url, execution):
        self.require_current()
        execution = self.missing_reader(execution)
        need(self.state['managerOwned'] and self.state['missingLoad'] is None)
        self.ui.wait_manager()
        self.source(url)
        self.close_dialog()
        need(not any(row['url'] == url for row in self.sample()))
        self.mark(dialogOwned=True)
        self.ui.open_url_dialog(); self.ui.fill_url(url)
        packet = execution.read(execution.sequence, require_load_history=True)
        need(not any(engine['url'] == url for engine in packet['source']['engines']))
        origin = dict(phase='issued', instance=packet['instance'], pid=packet['processId'],
            sequence=packet['sequence'], epoch=packet['capturedEpochMs'], history=deepcopy(packet['source']['loads']), completed=None)
        # Persist before the single ordinary submission. A lost receipt is not
        # permission to submit again, stop an unknown engine or discard intent.
        self.mark(missingLoad=origin, loadAttempted=True)
        self.ui.submit_url(); self.ui.wait_dialog_absent()
        self.mark(dialogOwned=False)

    def settle_missing(self, execution):
        from adapters.native_script_loads import result
        execution = self.missing_reader(execution)
        origin = self.state['missingLoad']; need(origin is not None)
        packet = execution.read(max(execution.sequence, origin['sequence']), require_load_history=True)
        loads = packet['source']['loads']; prefix = origin['history']
        need(packet['instance'] == origin['instance'] and packet['processId'] == origin['pid']
             and packet['capturedEpochMs'] >= origin['epoch'] and loads['instance'] == prefix['instance']
             and loads['events'][:prefix['sequence']] == prefix['events'])
        event = result(packet, self.state['source'], after_sequence=prefix['sequence'], after_epoch=origin['epoch'])
        if origin['completed'] is not None:
            final = origin['completed']
            need(packet['capturedEpochMs'] >= final['epoch'] and event == final['event']
                 and loads['events'][:final['history']['sequence']] == final['history']['events'])
        need(event['success'] is False and not any(engine['url'] == self.state['source']
             for engine in packet['source']['engines']))
        need(not any(row['url'] == self.state['source'] for row in self.sample()) and execution.guard() is not False)
        self.mark(missingLoad=origin | dict(phase='settled', completed=dict(epoch=packet['capturedEpochMs'],
            history=deepcopy(loads), event=deepcopy(event))), loadAttempted=False)
        return event  # Original callback/status; visible error and quiet cleanup are separate.
