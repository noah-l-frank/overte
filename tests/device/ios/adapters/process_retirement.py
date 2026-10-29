"""Durable role-owned OS quiet windows after the original iOS process stops.

Native resource counters are not rewritten. Process death is a separate source.
This component cannot stop an app, publish product facts or remove ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.retired_process import (IOSRetiredProcess, validate, absent,
    ACQUISITION_VERSION, command)
from ios.adapters.installed_code import source as process_source

VERSION = 1
RECORD_VERSION = 1
PROFILES = {'graphics':'graphics','emote':'emote','worldweb':'world-web','navigation':'navigation','avatar':'avatar','tabletweb':'tablet-web',
            'snapshotsharearchive':'snapshot-share-archive','snapshotphotos':'snapshot-photos'}


def filename(profile,role,stage):
    need(type(profile) is str and profile in PROFILES and role in ('primary','actor')
         and type(stage) is int and stage in (0,1))
    need(profile not in ('snapshotsharearchive','snapshotphotos') or role=='primary' and stage==0)
    return 'ios-'+PROFILES[profile]+'-'+role+'-'+str(stage)+'-process-retirement.json'


def acquisition(value, original):
    exact(value, {'iosRetiredProcessAcquisitionVersion', 'hostBeforeEpochMs', 'hostAfterEpochMs',
                 'hostBeforeMonotonic', 'hostAfterMonotonic', 'originalSha256'})
    need(type(value['iosRetiredProcessAcquisitionVersion']) is int and
         value['iosRetiredProcessAcquisitionVersion'] == ACQUISITION_VERSION and value['originalSha256'] == digest(original))
    first, last = value['hostBeforeEpochMs'], value['hostAfterEpochMs']
    start, end = value['hostBeforeMonotonic'], value['hostAfterMonotonic']
    need(number(first, 1, 10**15) and number(last, first, first+1500) and last-first < 1500
         and number(start, 0, 10**15) and number(end, start, start+1.5) and end-start < 1.5
         and abs(last-first-(end-start)*1000) <= 250)
    return value


class IOSProcessRetirement:
    def __init__(self, store, reader, binding, run, role, stage, lock, *, profile='graphics'):
        need(isinstance(store, PrivateFeatureState) and isinstance(reader, IOSRetiredProcess)
             and isinstance(lock, ScriptSourceLock) and role in ('primary', 'actor')
             and type(stage) is int and stage in (0, 1))
        expected_name=filename(profile,role,stage)
        self.profile=profile
        self.store, self.reader, self.lock = store, reader, lock
        self.binding = deepcopy(context(binding)); self.run = identifier(run)
        self.role, self.stage = role, stage
        self.pid = int(binding['processIdentity']); need(str(self.pid) == binding['processIdentity'] and self.pid == reader.pid)
        self.source, self.bundle = deepcopy(process_source(reader.source)), reader.bundle
        need(store.path.name == expected_name
             and lock.path == store.path.with_name('script-feature-sources.lock'))
        self.historical = False; self.previous = store.read(); self.bound()
        self.state = dict(records=[], windows=[], pending=None) if self.previous is None else self.decode(self.previous)
        if self.previous is None:self.save()
        self.restore_cursor()

    def envelope(self, state):
        return dict(iosProcessRetirementVersion=VERSION, binding=self.binding, source=self.source,
                    bundleId=self.bundle, runId=self.run, role=self.role, stage=self.stage, payload=pack([state]))

    def record_store(self, ordinal):
        need(integer(ordinal, 1, 256))
        return PrivateFeatureState(self.store.path.with_name(self.store.path.stem+'-'+str(ordinal)+'.json'))

    def bound(self):
        need(not self.historical and self.store.path.name==filename(self.profile,self.role,self.stage)); self.lock.assert_held()
        need(self.reader.guard() is not False and same(self.store.read(), self.previous))

    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value)

    def load(self, reference):
        exact(reference, {'ordinal', 'sha256'}); ordinal = reference['ordinal']
        store = self.record_store(ordinal)
        value = store.read() if getattr(self, '_archives', None) is None else self._archives.get(ordinal)
        need(value is not None and digest(value) == reference['sha256'])
        exact(value, {'iosProcessRetirementRecordVersion', 'binding', 'source', 'bundleId', 'runId', 'role', 'stage', 'payload'})
        need(type(value['iosProcessRetirementRecordVersion']) is int and value['iosProcessRetirementRecordVersion'] == RECORD_VERSION
             and same(value['binding'], self.binding) and same(value['source'], self.source)
             and value['bundleId'] == self.bundle and value['runId'] == self.run and value['role'] == self.role
             and type(value['stage']) is int and value['stage'] == self.stage)
        rows = unpack(value['payload']); need(len(rows) == 1 and type(rows[0]['ordinal']) is int and rows[0]['ordinal'] == ordinal)
        row = rows[0]; mode = row.get('mode')
        exact(row, {'ordinal', 'window', 'mode'} | ({'original', 'acquisition'} if mode == 'observed' else set()))
        need(mode in ('observed', 'abandoned') and integer(row['window'], 0, 7))
        if mode == 'observed':
            raw = row['original']; validate(raw, dict(bundleId=self.bundle, commandId=raw['commandId']), self.pid, self.source)
            acquisition(row['acquisition'], raw)
        return row

    @staticmethod
    def elapsed(rows):
        if len(rows) < 3:return None
        first, last = rows[0], rows[-1]
        spans = [last['original']['clockBefore'][key]-first['original']['clockAfter'][key]
                 for key in ('epochMs', 'monotonicMs')]
        spans += [last['acquisition']['hostBeforeEpochMs']-first['acquisition']['hostAfterEpochMs'],
                  (last['acquisition']['hostBeforeMonotonic']-first['acquisition']['hostAfterMonotonic'])*1000]
        return math.floor(min(spans))

    def decode(self, value):
        exact(value, {'iosProcessRetirementVersion', 'binding', 'source', 'bundleId', 'runId', 'role', 'stage', 'payload'})
        rows = unpack(value['payload']); need(len(rows) == 1 and same(value, self.envelope(rows[0])))
        need(type(value['iosProcessRetirementVersion']) is int and type(value['stage']) is int)
        state = rows[0]; exact(state, {'records', 'windows', 'pending'})
        need(type(state['records']) is list and len(state['records']) <= 256
             and type(state['windows']) is list and len(state['windows']) <= 8)
        records = {}; previous = None
        for ordinal, ref in enumerate(state['records'], 1):
            need(type(ref.get('ordinal')) is int and ref['ordinal'] == ordinal)
            row = self.load(ref); records[ordinal] = row
            need(row['window'] < len(state['windows']))
            if row['mode'] == 'observed':
                raw = row['original']
                if previous is not None:
                    validate(raw, dict(bundleId=self.bundle, commandId=raw['commandId']), self.pid, self.source, previous['original'])
                    need(row['acquisition']['hostBeforeEpochMs'] >= previous['acquisition']['hostAfterEpochMs']
                         and row['acquisition']['hostBeforeMonotonic'] >= previous['acquisition']['hostAfterMonotonic'])
                previous = row
        for index, window in enumerate(state['windows']):
            exact(window, {'samples', 'start', 'elapsedMs', 'complete'})
            need(type(window['samples']) is list and len(window['samples']) <= 81
                 and window['samples'] == [n for n, row in records.items() if row['window'] == index]
                 and integer(window['elapsedMs'], 0, 20000) and type(window['complete']) is bool)
            expected_start = None
            for at, ordinal in enumerate(window['samples']):
                row = records[ordinal]
                if row['mode'] != 'observed' or not absent(row['original']):expected_start = None
                elif expected_start is None:expected_start = at
            need((window['start'] is None if expected_start is None else
                  type(window['start']) is int and window['start'] == expected_start))
            quiet = [] if expected_start is None else [records[n] for n in window['samples'][expected_start:]]
            elapsed = self.elapsed(quiet)
            need(window['elapsedMs'] == (max(0, elapsed) if elapsed is not None else 0)
                 and window['complete'] == (elapsed is not None and elapsed >= 3000))
            observed = [records[n] for n in window['samples'] if records[n]['mode'] == 'observed']
            if observed:
                need(observed[-1]['acquisition']['hostAfterMonotonic']-observed[0]['acquisition']['hostBeforeMonotonic'] < 20
                     and observed[-1]['acquisition']['hostAfterEpochMs']-observed[0]['acquisition']['hostBeforeEpochMs'] < 20000)
        pending = state['pending']
        if pending is not None:
            exact(pending, {'ordinal', 'window'})
            need(type(pending['ordinal']) is int and pending['ordinal'] == len(state['records'])+1
                 and integer(pending['window'], 0, len(state['windows'])-1) and pending['window'] == len(state['windows'])-1)
        return state

    def restore_cursor(self):
        self.reader.last = self.reader.acquisition = None
        for ref in reversed(self.state['records']):
            row = self.load(ref)
            if row['mode'] == 'observed':
                self.reader.last, self.reader.acquisition = deepcopy(row['original']), deepcopy(row['acquisition']); break

    def store_record(self, row):
        value = dict(iosProcessRetirementRecordVersion=RECORD_VERSION, binding=self.binding, source=self.source,
                     bundleId=self.bundle, runId=self.run, role=self.role, stage=self.stage, payload=pack([row]))
        store = self.record_store(row['ordinal']); previous = store.read()
        if previous is None:store.write(value, None)
        else:need(same(previous, value))
        need(same(store.read(), value)); return dict(ordinal=row['ordinal'], sha256=digest(value))

    def adopt(self, ref):
        pending = self.state['pending']; need(pending is not None)
        row = self.load(ref); need(row['ordinal'] == pending['ordinal'] and row['window'] == pending['window'])
        self.state['records'].append(deepcopy(ref)); window = self.state['windows'][pending['window']]
        window['samples'].append(row['ordinal'])
        if row['mode'] != 'observed' or not absent(row['original']):window['start'] = None
        elif window['start'] is None:window['start'] = len(window['samples'])-1
        quiet = [] if window['start'] is None else [self.load(self.state['records'][n-1]) for n in window['samples'][window['start']:]]
        elapsed = self.elapsed(quiet); window.update(elapsedMs=max(0, elapsed) if elapsed is not None else 0,
                                                   complete=elapsed is not None and elapsed >= 3000)
        self.state['pending'] = None; self.save(); self.restore_cursor()

    def recover(self):
        pending = self.state['pending']
        if pending is None:return
        value = self.record_store(pending['ordinal']).read()
        ref = self.store_record(dict(**pending, mode='abandoned')) if value is None else dict(ordinal=pending['ordinal'], sha256=digest(value))
        self.adopt(ref)  # Original metadata only; the caller still needs a fresh read.

    def advance(self):
        """One new original read; returns whether this role's quiet window is complete."""
        self.bound(); self.recover(); self.restore_cursor()
        need(len(self.state['records']) < 256)
        windows = self.state['windows']; now = self.reader.monotonic(); epoch = self.reader.epoch_ms()
        need(number(now, 0, 10**15) and number(epoch, 1, 10**15))
        new = not windows
        if windows:
            old = [self.load(self.state['records'][n-1]) for n in windows[-1]['samples']]
            measured = [row for row in old if row['mode'] == 'observed']
            new = (len(old) >= 81 or bool(measured) and
                   (now-measured[0]['acquisition']['hostBeforeMonotonic'] >= 18 or
                    epoch-measured[0]['acquisition']['hostBeforeEpochMs'] >= 18000))
        if new:
            need(len(windows) < 8); windows.append(dict(samples=[], start=None, elapsedMs=0, complete=False))
        pending = dict(ordinal=len(self.state['records'])+1, window=len(windows)-1)
        self.state['pending'] = pending; self.save()
        original = self.reader.read(); receipt = deepcopy(self.reader.acquisition); self.bound()
        row = dict(**pending, mode='observed', original=original, acquisition=receipt)
        ref = self.store_record(row); self.adopt(ref); self.current()
        return self.state['windows'][-1]['complete']

    def current(self):
        """Check original acquisition age; no historical packet is retimed here."""
        self.bound(); need(self.state['pending'] is None and self.state['records'])
        row = self.load(self.state['records'][-1]); need(row['mode'] == 'observed')
        acq = row['acquisition']; now, epoch = self.reader.monotonic(), self.reader.epoch_ms()
        need(number(now, acq['hostAfterMonotonic'], acq['hostBeforeMonotonic']+1.5)
             and now-acq['hostBeforeMonotonic'] < 1.5
             and number(epoch, acq['hostAfterEpochMs'], acq['hostBeforeEpochMs']+1500)
             and epoch-acq['hostBeforeEpochMs'] < 1500
             and abs(epoch-acq['hostBeforeEpochMs']-(now-acq['hostBeforeMonotonic'])*1000) <= 250)
        return deepcopy(row)

    @classmethod
    def archive(cls, value, *, path, binding, source, bundle, run, role, stage, records=None, profile='graphics'):
        """Pure validation of immutable originals; it grants no current OS fact."""
        expected_name=filename(profile,role,stage)
        scope = object.__new__(cls); scope.profile=profile;scope.store = PrivateFeatureState(path)
        scope.binding, scope.source = deepcopy(context(binding)), deepcopy(process_source(source))
        scope.bundle, scope.run, scope.role, scope.stage = bundle, identifier(run), role, stage
        need(role in ('primary', 'actor') and type(stage) is int and stage in (0, 1)
             and scope.store.path.name == expected_name)
        scope.pid = int(binding['processIdentity']); need(str(scope.pid) == binding['processIdentity'] and integer(scope.pid,1,2147483647))
        command(dict(bundleId=bundle,commandId='ios-'+'a'*32))
        scope.historical = True
        if records is not None:
            rows = unpack(value['payload']); need(len(rows) == 1 and type(records) is dict
                and all(type(n) is int for n in records) and set(records) == {r['ordinal'] for r in rows[0]['records']})
        scope._archives = deepcopy(records)
        return deepcopy(scope.decode(value))
