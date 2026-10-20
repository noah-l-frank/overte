"""Durable five-source Script observations; no desired result is an input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier
from overte_phone_script_history import PhoneDurableScriptMeasurements, same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_file_scope import join, file_cursor, VERSION as FILE_VERSION
from overte_phone_script_measurements import fixture_scope
from adapters.token_script_file_ui import file_url

VERSION = 2


class PhoneScriptObservation:
    def __init__(self, store, binding, run, role, fixture_url, reader_factory, source_lock,
                 guard, *, monotonic=time.monotonic):
        try:
            identifier(run); fixture_scope(run,fixture_url)
            need(isinstance(store, PrivateFeatureState) and role in ('primary', 'actor')
                 and isinstance(source_lock, PhoneScriptSourceLock)
                 and source_lock.path == store.path.with_name('phone-script-sources.lock')
                 and all(callable(value) for value in (reader_factory, guard, monotonic)))
            self.store, self.lock, self.guard, self.monotonic = store, source_lock, guard, monotonic
            self.make_reader = reader_factory
            self.binding = deepcopy(context(binding))
            self.run, self.role, self.directory, self.fixture_url = run, role, None, fixture_url
            self.previous = store.read()
            self.state = dict(sourceObservationVersion=VERSION, sourceKind='phone-script-observation',
                binding=self.binding, runId=run, role=role, directory=None, fixtureUrl=fixture_url,
                phase='ready', sequence=0, fileCursor=None, fileObservation=None)
            if self.previous is not None:
                exact(self.previous, set(self.state))
                for key in set(self.state) - {'phase', 'sequence', 'fileCursor','fileObservation','directory'}:
                    need(same(self.previous[key], self.state[key]))
                need(self.previous['phase'] == 'ready' and integer(self.previous['sequence'], 1, 1000000000))
                directory=self.previous['directory']
                need(file_url(directory).endswith('/feature-script-'+run))
                cursor = self.previous['fileCursor']
                exact(cursor, {'fileScopeVersion', 'instance', 'sequence', 'capturedEpochMs', 'directory'})
                identifier(cursor['instance'])
                need(type(cursor['fileScopeVersion']) is int and cursor['fileScopeVersion'] == FILE_VERSION
                     and integer(cursor['sequence'], 1) and integer(cursor['capturedEpochMs'], 1)
                     and cursor['directory'] == directory)
                packet=self.previous['fileObservation']
                original=file_cursor(run,directory,int(self.binding['processIdentity'].split(':')[0]),packet,
                    packet['capturedEpochMs'],packet['capturedEpochMs'])
                need(same(original,cursor))
                self.state = deepcopy(self.previous)
                self.directory=directory
        except Exception:
            raise NativeUIError('Phone Script observation provenance is unavailable, foreign or interrupted') from None

    def current(self):
        need(same(self.store.read(), self.previous))

    def write(self, value):
        self.lock.assert_held()
        self.current()
        self.store.write(value, self.previous)
        need(same(self.store.read(), value))
        self.previous = self.state = deepcopy(value)

    def read(self, ticket, after_epoch, *, after_sequence=None):
        try:
            identifier(ticket)
            need(integer(after_epoch, 1) and (after_sequence is None or integer(after_sequence)))
            started = previous = self.monotonic()
            need(number(started, 0, 1e15))
            def check():
                nonlocal previous
                self.lock.assert_held()
                need(self.guard() is not False)
                now = self.monotonic()
                need(number(now, 0, 1e15) and previous <= now and now - started < 20)
                previous = now
            with self.lock.held():
                check(); self.current()
                need(self.state['phase'] == 'ready' and self.state['sequence'] < 1000000000
                     and (after_sequence is None or after_sequence <= self.state['sequence']))
                pending = deepcopy(self.state); pending['phase'] = 'reading'
                self.write(pending); check()
                # The factory and the entire four-source read share this exact
                # held lock. Original file-query intent is persisted first too.
                live = self.make_reader(self.lock)
                need(isinstance(live, PhoneDurableScriptMeasurements) and live.source_lock is self.lock
                     and same(live.history.binding, self.binding) and live.history.run == self.run
                     and live.history.role == self.role and self.directory in (None,live.history.directory)
                     and live.history.fixture_url == self.fixture_url
                     and live.history.store.path.parent == self.store.path.parent)
                reader = live.reader
                need(callable(getattr(reader, 'file_observation', None))
                     and self.binding['processIdentity'].split(':')[0]==str(reader.execution.pid))
                directory=reader.directory
                admission=file_cursor(self.run,directory,reader.execution.pid,reader.file_observation(),
                    reader.lifecycle.clock_ms(),after_epoch,previous=self.state['fileCursor'])
                check(); original = live.read(ticket, after_epoch); check()
                epoch = reader.lifecycle.clock_ms(); check()
                actual = join(self.run, ticket, directory, self.fixture_url, reader.execution.pid,
                    deepcopy(reader.last_sources), reader.file_observation(), epoch, after_epoch,
                    previous=admission)
                # The recomposition must agree with the accepted original four
                # sources; only the oldest fifth source may lower capture time.
                measured = deepcopy(actual['measurement'])
                measured['capturedEpochMs'] = original['capturedEpochMs']
                need(same(measured, original)); check()
                finished = deepcopy(self.state)
                finished.update(phase='ready', sequence=finished['sequence'] + 1, directory=directory,
                                fileCursor=actual['fileCursor'],fileObservation=reader.file_observation())
                self.write(finished);self.directory=directory; check()
                return deepcopy(dict(sourceObservationVersion=VERSION, sequence=finished['sequence'],
                                     sources=reader.last_sources, **actual))
        except Exception:
            raise NativeUIError('Phone Script observation failed; original provenance and ownership are retained') from None
