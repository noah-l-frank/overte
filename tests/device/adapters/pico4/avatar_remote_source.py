"""Retained independent remote Avatar originals in the existing source channel."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time

from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.native_fd_owner import require_directory
from adapters.host_process_identity import host_identity
from adapters.normal_feature_state import context
from adapters.pico4.avatar_remote import NativePicoRemoteAvatar, command, validate, continuity, independent, FILE
from adapters.pico4.avatar_remote_state import source_store, namespace_owned
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import same, canonical
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader, validate as phase_packet

VERSION = 2
UNRESOLVED_HOST_FILES = []


class PicoRemoteAvatarSource:
    def __init__(self, store, binding, phase, lock, subject, send, read, clock_ms, guard,
                 *, primary=None, monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(phase, PhaseFixtureReader) and phase.area in ('avatar-people','emotes')
             and isinstance(lock, ScriptSourceLock) and all(callable(fn) for fn in (send, read, clock_ms, guard, monotonic, sleep)))
        command(dict(schemaVersion=1, commandId='a'*32, action='feature-pico-remote-avatar-observe', runId=phase.run, subjectSessionId=subject))
        self.store, self.binding, self.phase, self.lock = store, deepcopy(context(binding)), phase, lock
        self.run, self.subject, self.send, self.read_raw = phase.run, subject, send, read
        self.clock_ms, self.original_guard, self.monotonic, self.sleep = clock_ms, guard, monotonic, sleep
        self.primary = deepcopy(primary); self.pid = int(binding['processIdentity'].split(':')[0])
        self.identity = dict(picoRemoteAvatarSourceVersion=VERSION, binding=self.binding, runId=self.run,
            fixtureUrl=phase.fixture_url, area=phase.area, subjectSessionId=subject,
            producerHostProcessIdentity=host_identity(),
            primarySha256=None if primary is None else hashlib.sha256(canonical(primary)).hexdigest())
        self.previous = None; self.failed = False; self.packets = []; self.rows = []; self.operation = None
        self.clock = self.epoch = self.host = None; self.state = None
        self.file = object.__new__(LifecycleProcessFile)
        try:
            lock.assert_held()
            need(store.read() is not None or not namespace_owned(store, store.path.name))
            LifecycleProcessFile.__init__(self.file, store)
            if self.primary is not None:
                original = self.primary; scope = original['source']
                validate(original, command(dict(schemaVersion=1, commandId=original['requestId'],
                    action='feature-pico-remote-avatar-observe', runId=scope['runId'], subjectSessionId=scope['subjectSessionId'])),
                    original['processId'], original['capturedEpochMs'],current=True)
                need(scope['runId'] == self.run and scope['selfSessionId'] == subject)
            self.previous = store.read(); self.chunks = ChatSourceChunks(store, self.identity)
            if self.previous is None:
                self.chunks.load([])
                self.state = dict(phase='ready', chunks=[], records=[], pending=None,
                    started=monotonic(), epochMs=clock_ms(), hostEpochMs=phase.epoch_ms())
            else:
                exact(self.previous, set(self.identity) | {'phase', 'chunks', 'records', 'pending', 'started', 'epochMs', 'hostEpochMs'})
                need(all(same(self.previous[k], v) for k, v in self.identity.items()))
                self.state = {key:deepcopy(value) for key, value in self.previous.items() if key not in self.identity}
                self.rows = self.chunks.load(self.state['chunks']); self.restore()
            self.guard()
        except BaseException:
            self.failed = True
            if hasattr(self.file, 'parent') and not self.file.close_host(): UNRESOLVED_HOST_FILES.append(self.file)
            raise

    def guard(self):
        self.lock.assert_held(); need(not self.failed and self.original_guard() is not False)
        self.file.guard(); require_directory(self.file.parent, self.store.path.parent)
        need(same(self.store.read(), self.previous)); self.chunks.verify()
        epoch, host, now = self.clock_ms(), self.phase.epoch_ms(), self.monotonic()
        need(integer(epoch, 1 if self.epoch is None else self.epoch)
             and number(host, 1 if self.host is None else self.host, 1e15)
             and number(now, 0 if self.clock is None else self.clock, 1e15))
        if self.state is not None:
            need(self.state['started'] <= now < self.state['started'] + 120
                 and self.state['epochMs'] <= epoch < self.state['epochMs'] + 120000
                 and self.state['hostEpochMs'] <= host < self.state['hostEpochMs'] + 120000)
        if self.operation is not None: need(now - self.operation < 5)
        self.clock, self.epoch, self.host = now, epoch, host
        return True

    def save(self):
        self.guard(); value = dict(self.identity, **deepcopy(self.state))
        self.file.write(value, self.previous); self.previous = deepcopy(value); self.guard()

    def put(self, value):
        self.guard(); need(self.state['phase'] == 'reading')
        index = len(self.rows)
        self.state['chunks'] = self.chunks.append(value, self.state['chunks'])
        self.rows.append(deepcopy(value)); self.save(); return index

    def retain(self, kind, value):
        pending = self.state['pending']; need(pending is not None)
        if kind == 'request':
            need(pending['request'] is None); pending['request'] = self.put(dict(kind='request', value=value)); self.save(); return
        need(kind == 'raw' and type(value) is str and len(value.encode()) <= 196608)
        need(len(pending['raw']) < 51 and pending['partialRaw'] is None)
        pending['partialRaw'] = dict(parts=[], bytes=len(value.encode()), sha256=hashlib.sha256(value.encode()).hexdigest()); self.save()
        for offset in range(0, len(value), 4096):
            index = self.put(dict(kind='raw', value=value[offset:offset+4096]))
            pending['partialRaw']['parts'].append(index); self.save()
        pending['raw'].append(deepcopy(pending['partialRaw'])); pending['partialRaw'] = None; self.save()

    def raw(self, reference):
        exact(reference, {'parts', 'bytes', 'sha256'})
        parts = reference['parts']
        need(type(parts) is list and len(parts) <= 48 and all(integer(index, 0, len(self.rows)-1) for index in parts)
             and integer(reference['bytes'], 0, 196608)
             and (not parts or parts == list(range(parts[0], parts[0]+len(parts)))))
        for index in parts:
            exact(self.rows[index], {'kind', 'value'})
            need(self.rows[index]['kind'] == 'raw' and type(self.rows[index]['value']) is str
                 and len(self.rows[index]['value']) <= 4096)
        raw = ''.join(self.rows[index]['value'] for index in parts)
        need(len(raw.encode()) == reference['bytes'] and hashlib.sha256(raw.encode()).hexdigest() == reference['sha256'])
        return raw

    def restore(self):
        state = self.state
        need(state['phase'] in ('ready', 'reading', 'failed') and type(state['records']) is list and len(state['records']) <= 32
             and number(state['started'], 0, 1e15) and integer(state['epochMs'], 1) and number(state['hostEpochMs'], 1, 1e15))
        need(state['phase'] == 'failed' or (state['pending'] is None) == (state['phase'] == 'ready'))
        if self.primary is not None and state['records']:
            original = ''.join(row['value'] for row in self.rows if row['kind'] == 'primary')
            need(original.encode() == canonical(self.primary))
        previous_phase = None
        for record in state['records']:
            exact(record, {'request', 'raw', 'before', 'after', 'hostStarted', 'hostFinished'})
            need(number(record['hostStarted'], state['started'], 1e15)
                 and number(record['hostFinished'], record['hostStarted'], record['hostStarted'] + 5))
            need(all(integer(record[key], 0, len(self.rows)-1) for key in ('request','before','after'))
                 and self.rows[record['request']]['kind'] == 'request'
                 and all(self.rows[record[key]]['kind'] == 'phase' for key in ('before','after')))
            query = self.rows[record['request']]['value']; command(query)
            need(query['runId'] == self.run and query['subjectSessionId'] == self.subject
                 and (self.clock is None or record['hostStarted'] >= self.clock))
            packet = decode(self.raw(record['raw'])); validate(packet, query, self.pid, packet['capturedEpochMs'],
                current=self.identity['picoRemoteAvatarSourceVersion']==2)
            need(packet['source']['picoRemoteAvatarVersion'] == self.identity['picoRemoteAvatarSourceVersion'])
            before, after = (self.rows[record[k]]['value'] for k in ('before', 'after'))
            self.phase_pair(before, after, previous=previous_phase); previous_phase = after
            if self.primary is not None: independent(self.primary, packet)
            continuity(self.packets[-1] if self.packets else None, packet); self.packets.append(packet)
            self.clock, self.epoch, self.host = record['hostFinished'], packet['capturedEpochMs'], after['capturedEpochMs']

    def phase_pair(self, before, after, *, previous=None):
        for packet, previous in ((before, previous), (after, before)):
            phase_packet(packet, run=self.run, area=self.phase.area, request=packet['requestId'], epoch=packet['capturedEpochMs'], previous=previous)
            need(packet['active'] and packet['activations'])
        need(before['activations'][-1]['ticket'] == after['activations'][-1]['ticket'])

    def read(self):
        self.guard(); need(self.state['phase'] == 'ready' and self.state['pending'] is None and len(self.packets) < 32)
        self.operation = self.monotonic()
        native_anchor, host_anchor = self.clock_ms(), self.phase.epoch_ms()
        self.state.update(phase='reading', pending=dict(request=None, raw=[], partialRaw=None, before=None, after=None, hostStarted=self.operation))
        self.save()
        try:
            if self.primary is not None and not self.rows:
                raw = canonical(self.primary).decode()
                for offset in range(0, len(raw), 4096): self.put(dict(kind='primary', value=raw[offset:offset+4096]))
            floor = None if not self.state['records'] else self.rows[self.state['records'][-1]['after']]['value']
            before = self.phase.read(floor)['status']; self.state['pending']['before'] = self.put(dict(kind='phase', value=before)); self.save()
            reader = NativePicoRemoteAvatar(self.send, self.read_raw, self.clock_ms, self.guard, self.pid,
                retain=self.retain, monotonic=self.monotonic, sleep=self.sleep)
            reader.restore(self.packets); packet = reader.read(self.run, self.subject)
            if self.primary is not None: independent(self.primary, packet)
            after = self.phase.status(before); self.phase_pair(before, after, previous=floor)
            self.state['pending']['after'] = self.put(dict(kind='phase', value=after)); self.save()
            def fresh_delivery():
                self.guard(); native, host = self.clock_ms(), self.phase.epoch_ms(); end = self.monotonic()
                need(number(end, self.operation, self.operation + 1.5) and end - self.operation < 1.5)
                elapsed = math.ceil((end - self.operation) * 1000)
                fresh(packet['requestedEpochMs'], max(native, native_anchor + elapsed))
                fresh(before['capturedEpochMs'], max(host, host_anchor + elapsed))
                return end
            end = fresh_delivery()
            pending = self.state['pending']; need(pending['request'] is not None and pending['raw'] and pending['partialRaw'] is None)
            record = dict(request=pending['request'], raw=deepcopy(pending['raw'][-1]), before=pending['before'], after=pending['after'],
                hostStarted=self.operation, hostFinished=end)
            self.state['records'].append(record); self.packets.append(deepcopy(packet))
            self.state.update(phase='ready', pending=None); self.save()
            returned = deepcopy(packet); fresh_delivery(); return returned
        except BaseException:
            # Persist a terminal source failure even if a final host-only write
            # or guard consumed freshness after an otherwise complete record.
            # This host CAS emits no product query and cannot renew the clocks.
            self.state['phase'] = 'failed'
            try:
                value = dict(self.identity, **deepcopy(self.state))
                self.file.write(value, self.previous); self.previous = deepcopy(value)
            except BaseException:
                if self.file not in UNRESOLVED_HOST_FILES: UNRESOLVED_HOST_FILES.append(self.file)
            self.failed = True; raise
        finally: self.operation = None

    def close_host(self):
        result = self.file.close_host(); self.failed = True
        if not result and self.file not in UNRESOLVED_HOST_FILES: UNRESOLVED_HOST_FILES.append(self.file)
        return result

    @classmethod
    def archive(cls, store, phase, *, guard, monotonic=time.monotonic):
        """Read-only original Source1/2 history; no live owner or input authority.

        In particular, a retained Source1 can never acquire a Source2 observer,
        renew a clock or reinterpret its empty legacy Rig as a remote pose.
        """
        need(isinstance(phase,PhaseFixtureReader) and callable(guard) and callable(monotonic))
        started=monotonic(); file=object.__new__(LifecycleProcessFile)
        try:
            need(guard() is not False); LifecycleProcessFile.__init__(file,store)
            header=store.read(); need(type(header) is dict)
            version=header.get('picoRemoteAvatarSourceVersion'); need(type(version) is int and version in (1,2))
            identity={'picoRemoteAvatarSourceVersion','binding','runId','fixtureUrl','subjectSessionId',
                'producerHostProcessIdentity','primarySha256'} | ({'area'} if version==2 else set())
            exact(header,identity | {'phase','chunks','records','pending','started','epochMs','hostEpochMs'})
            need(header['runId']==phase.run and header['fixtureUrl']==phase.fixture_url
                 and phase.area in ('avatar-people','emotes')
                 and (phase.area=='avatar-people' if version==1 else header['area']==phase.area))
            scope=object.__new__(cls); scope.identity={key:deepcopy(header[key]) for key in identity}
            scope.binding=context(header['binding']); scope.pid=int(scope.binding['processIdentity'].split(':')[0])
            scope.run,scope.subject,scope.phase=phase.run,header['subjectSessionId'],phase
            scope.state={key:deepcopy(value) for key,value in header.items() if key not in identity}
            scope.chunks=ChatSourceChunks(store,scope.identity); scope.rows=scope.chunks.load(header['chunks'])
            original=''.join(row['value'] for row in scope.rows if row['kind']=='primary')
            scope.primary=None if header['primarySha256'] is None else decode(original)
            if scope.primary is not None: need(hashlib.sha256(original.encode()).hexdigest()==header['primarySha256'])
            scope.packets=[];scope.clock=scope.epoch=scope.host=None;scope.restore()
            pending=scope.state['pending']; raws=[]
            if pending is not None:
                raws=[scope.raw(reference) for reference in pending['raw']]
            result=dict(historicalOnly=True,currentOwnership=False,header=deepcopy(header),
                packets=deepcopy(scope.packets),pendingRaw=raws)
            need(guard() is not False);scope.chunks.verify();file.guard();require_directory(file.parent,store.path.parent)
            need(number(monotonic(),started,started+5));closed=file.close_host()
            if not closed: UNRESOLVED_HOST_FILES.append(file);need(False)
            return result
        except BaseException:
            if hasattr(file,'parent') and not file.close_host() and file not in UNRESOLVED_HOST_FILES: UNRESOLVED_HOST_FILES.append(file)
            raise


def create(adapter, target, phase, subject, lock, *, primary=None):
    """Existing candidate-bound transport and exact shared native source lock."""
    lock.assert_held()
    need(lock.path == adapter._script_journey().state_path(target).with_name('script-sources.lock'))
    _ui, _observe, binding = adapter._script_runtime(target); native = adapter._native_feature_observer(target)
    return PicoRemoteAvatarSource(source_store(adapter, target, phase.run,area=phase.area), binding, phase, lock, subject,
        native.send, lambda:adapter.adb.read_debug_app_file(target, 'org.overte.pico', 'files/overte-e2e/' + FILE, attempts=1),
        native.clock_ms, native.guard, primary=primary, monotonic=native.monotonic, sleep=native.sleep)
