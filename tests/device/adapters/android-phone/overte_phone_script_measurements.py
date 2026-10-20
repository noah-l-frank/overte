"""Join original Script sources; no requested action or expected state is input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
from urllib.parse import urlsplit, unquote

from adapters.native_feature_observation import NativeFeatureObservation, fresh, integer, need, number, validate as validate_lifecycle
from adapters.native_script_observation import (validate as validate_execution, measured_effect,
    NativeScriptObservation, loaded_relative_modules, submitted_source)
from adapters.native_script_files import originals
from adapters.normal_script_manager import diagnostic, missing_script_url
from adapters.normal_ui import NativeUIError
from adapters.script_ui_inventory import ui_state
from adapters.token_script_file_ui import file_url
from feature_journeys.contract import identifier, state as validate_state
from overte_phone_script_files import PhoneScriptFileIO, validate as validate_ui

VERSION = 2


def owned_tree(url, directory):
    # Normalization may detect a disguised owned path, never make it eligible.
    from posixpath import normpath
    parts = urlsplit(url)
    path = normpath(unquote(parts.path, errors='strict'))
    root = file_url(directory)
    return parts.scheme in ('file', '') and not parts.netloc and (path == root or path.startswith(root + '/'))


def fixture_scope(run, fixture_url):
    identifier(run)
    need(type(fixture_url) is str and len(fixture_url) <= 512 and not any(ord(c) <= 32 for c in fixture_url)
         and '?' not in fixture_url and '#' not in fixture_url and '%' not in fixture_url)
    scope = urlsplit(fixture_url)
    need(scope.scheme in ('http', 'https') and bool(scope.hostname) and scope.username is None
         and scope.password is None and scope.path == '/feature-fixture/v1/runs/' + run + '/')
    need(scope.port is None or 1 <= scope.port <= 65535)


def compose(run, ticket, directory, fixture_url, pid, execution, ui, service, lifecycle, epoch, after_epoch):
    """Return six measured fields and original oldest acquisition epoch.

    Owning transports must independently guard nonce/cursors/process/candidate
    around acquisition. Shape/freshness is checked again here. Callers cannot
    substitute a desired verb/state or output an acknowledgment as facts. The
    active fixture ticket only scopes actual error provenance.
    """
    identifier(run); identifier(ticket)
    fixture_scope(run, fixture_url)
    need(integer(pid, 1) and file_url(directory).endswith('/feature-script-' + run))
    need(type(execution) is dict and type(ui) is dict and type(lifecycle) is dict)
    validate_execution(execution, execution.get('requestId'), pid, epoch)
    validate_ui(ui, ui.get('commandId'), pid, epoch)
    diagnostic(service, epoch)
    validate_lifecycle(lifecycle, lifecycle.get('requestId'), pid, epoch)
    need(execution['instance']==lifecycle['instance'])
    clocks = [execution['capturedEpochMs'], ui['capturedEpochMs'], service['sampleEpochMs'], lifecycle['capturedEpochMs']]
    need(integer(after_epoch, 1) and min(clocks) >= after_epoch and max(clocks) - min(clocks) <= 1500)
    fresh(min(clocks), epoch)
    source = execution['source']
    need(source.get('effectSourceVersion') == 1 and source.get('sourceIdentityVersion') == 1
         and source.get('loadSourceVersion') == 1 and source.get('membershipSourceVersion') == 1
         and source['membership']['complete'] is True)
    visual = ui_state(ui)
    need(not visual['systemPending'])  # This recipe never requests a system picker.
    engines = [row for row in source['engines'] if owned_tree(row['url'], directory)]
    rows = [row for row in service['scripts'] if owned_tree(row['url'], directory) or owned_tree(row['path'], directory)]
    allowed = {directory + '/script.js': 'script.js', directory + '/script-bundle/main.js': 'script-bundle/main.js'}
    need(len(engines) <= 1 and len(rows) <= 1
         and all(row['url'] in allowed and row['path'] == file_url(row['url']) for row in rows))
    need({row['url'] for row in rows} == {row['url'] for row in engines})
    owned_managers=[row for row in source['membership']['managers'] if row['assigned'] and owned_tree(row['url'],directory)]
    need(len(owned_managers)==len(engines)
         and {(row['instance'],row['url']) for row in owned_managers}
             == {(row['required']['instance'],row['url']) for row in engines})
    for engine in source['engines']:
        if engine in engines: continue
        need(not any(owned_tree(module['url'], directory) for module in engine['required']['modules']))
    companions, running = [], []
    engine_instance = None
    if engines:
        engine = engines[0]
        need(engine['url'] in allowed and engine['running'] and not engine['stopping'] and not engine['finished'])
        code = submitted_source(execution, engine['url'])
        raw = originals(run)[allowed[engine['url']]].decode('utf-8').encode('utf-16-le')
        need(code['codeUnits'] == len(raw) // 2 and code['sha256'] == hashlib.sha256(raw).hexdigest())
        companions = loaded_relative_modules(engine)
        # Unknown companions cannot be redacted into the one expected alias.
        need(companions in ([], ['companion.js'])
             and all(module['url'] == engine['url'].rsplit('/', 1)[0] + '/companion.js'
                     for module in engine['required']['modules'])
             and all(not module['cached'] for module in engine['required']['modules'] if module['loaded']))
        running = ['owned-script']
        engine_instance = engine['required']['instance']
    effect = measured_effect(execution, run)
    if effect is not None:
        need(bool(engines) and effect['ticks'] is not None)
    error = 'none'
    manager = visual['manager']
    if manager is not None:
        status = manager['statusText']
        need(manager['labelText'] == status)
        if status.startswith('Failed to load '):
            url = status[len('Failed to load '):].split(': ', 1)[0]
            missing_script_url(url)
            need(url == fixture_url + 'tickets/' + ticket + '/missing.js'
                 and manager['labelVisible'] and manager['labelText'] == status)
            events = [event for event in source['loads']['events'] if event['url'] == url]
            need(len(events) == 1 and events[0]['success'] is False and events[0]['status'] == 'NotFound'
                 and events[0]['callbackEpochMs'] >= after_epoch
                 and not any(engine['url'] == url for engine in source['engines'])
                 and not any(row['url'] == url or row['path'] == url for row in service['scripts']))
            error = 'not-found'
        elif status:
            need(re.fullmatch(r'(?:Loading|Stopping|Restarting) (?:script\.js|main\.js|missing\.js)', status) is not None)
    measured = dict(running=running, picker=visual['picker'], error=error,
                    effects=effect['ticks'] if effect is not None else 0, open=visual['open'], companions=companions)
    validate_state('scripts', measured, run)
    return deepcopy(dict(measurementVersion=VERSION, state=measured, capturedEpochMs=min(clocks), lifecycle=lifecycle['lifecycle'],
        engineInstance=engine_instance, effect=effect))


class PhoneScriptMeasurements:
    """Fresh original acquisitions and in-process prefix/instance continuity.

    This object is an internal live reader, not durable per-run ownership or a
    CLI observation producer. Reconstruction must not reset a full run's history.
    """
    def __init__(self, run, directory, fixture_url, execution, ui, service, lifecycle,
                 verify_directory, guard, *, file_instance, monotonic=time.monotonic):
        need(isinstance(execution, NativeScriptObservation) and isinstance(ui, PhoneScriptFileIO)
             and isinstance(lifecycle, NativeFeatureObservation)
             and execution.pid == ui.pid == lifecycle.pid
             and all(callable(value) for value in (service, verify_directory, guard, file_instance, monotonic)))
        identifier(run); file_url(directory)
        self.run, self.directory, self.fixture_url = run, directory, fixture_url
        self.execution, self.ui, self.service, self.lifecycle = execution, ui, service, lifecycle
        self.verify_directory, self.guard, self.monotonic = verify_directory, guard, monotonic
        self.file_instance=file_instance
        self.service_instance, self.service_sequence = None, 0
        self.last_sources = None

    def read(self, ticket, after_epoch):
        self.last_sources = None
        try:
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            def check():
                nonlocal previous
                need(self.guard() is not False)
                now = self.monotonic()
                need(number(now, 0, 1e15) and previous <= now and now - started < 20)
                previous = now
            check()
            need(self.verify_directory() == self.directory); check()
            file_birth=self.file_instance()
            need(type(file_birth) is str and re.fullmatch('[0-9a-f]{32}',file_birth) is not None)
            execution = self.execution.read(self.execution.sequence,
                require_effects=True, require_code_identity=True, require_load_history=True, require_membership=True)
            check(); ui = self.ui.capture(); check()
            service, service_epoch = self.service(self.service_sequence)
            diagnostic(service, service_epoch)
            need(self.service_instance in (None, service['instance']) and service['sampleSequence'] > self.service_sequence)
            self.service_instance, self.service_sequence = service['instance'], service['sampleSequence']
            check(); lifecycle = self.lifecycle.read(self.lifecycle.sequence); check()
            epoch = self.lifecycle.clock_ms(); check()
            result = compose(self.run, ticket, self.directory, self.fixture_url, self.execution.pid,
                             execution, ui, service, lifecycle, epoch, after_epoch)
            need(file_birth==execution['instance']==lifecycle['instance'] and self.file_instance()==file_birth)
            check()
            self.last_sources = deepcopy(dict(epochMs=epoch,execution=execution,ui=ui,service=service,lifecycle=lifecycle))
            return result
        except Exception:
            raise NativeUIError('Phone Script measurement sources are unavailable or inconsistent') from None
