"""Explicit live Source2 reader over the existing Snapshot query original owner.

Historical Source1 is never upgraded by passive READS membership. Every actual
endpoint return is durably retained as bytes before framing or validation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import secrets

from adapters.native_feature_observation import decode,integer,need,number
from adapters.pico4.snapshot_settings_namespace import _managed_class_guard
from adapters.pico4.snapshot_originals import nonce
from adapters.pico4.snapshot_settings_originals import PicoSnapshotSettingsOriginals,validate,accept,ACTION,LIMIT
from adapters.pico4.snapshot_settings_query_originals import SnapshotSettingsQueryOriginals
from adapters.pico4.snapshot_settings_transport import SnapshotSettingsBinaryRead


class PicoSnapshotSettingsScope2Reader(PicoSnapshotSettingsOriginals):
    settings_scope=2
    def __init__(self,send,transport,clock_ms,guard,pid,source_lock,raw_owner,*,monotonic,sleep):
        need(type(raw_owner) is SnapshotSettingsQueryOriginals and type(transport) is SnapshotSettingsBinaryRead
            and transport.raw is raw_owner and source_lock is raw_owner.lock)
        super().__init__(send,transport,clock_ms,guard,pid,source_lock,monotonic=monotonic,sleep=sleep)
        self.raw=self.original_raw=raw_owner;self.transport=self.original_transport=transport
        self.functions=self.original_functions=(send,transport,clock_ms,guard,monotonic,sleep)
        self.context=self.original_context=None;self.active=False;self.failed=False
        self.raw.bind_reader(self)

    def identity(self):
        need(self.failed is False and self.raw is self.original_raw and self.transport is self.original_transport
            and self.functions is self.original_functions
            and all(a is b for a,b in zip(self.functions,(self.send,self.read,self.clock_ms,self.guard,self.monotonic,self.sleep)))
            and self.raw.reader is self.raw.original_reader is self and self.transport.raw is self.raw
            and self.lock is self.raw.lock and self.context is self.original_context)
        self.lock.assert_held();self.raw.resource()

    def bind_context(self,context):
        from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
        self.identity();need(self.context is None and type(context) is PicoSnapshotSettingsScope2Baseline and context.reader is self
            and context.raw is self.raw and context.lock is self.lock and self.active is False
            and self.raw.context is None and self.raw.state['stage']=='ready')
        self.context=self.original_context=context

    def restore(self,value):
        self.identity();need(value.get('snapshotSettingsOriginalsVersion')==2)
        validate(value,value['runId'],value['commandId'],self.pid,value['capturedEpochMs'])
        # Restoring a logical facade can use only this still-warm producer's
        # own completed query, never cold history or a foreign current packet.
        need(any(row['status']=='returned' and row['command']['commandId']==value['commandId']
            and row['command']['runId']==value['runId'] for row in self.raw.state['queries'])
            and (self.previous is None or self.previous==value))
        self.previous=deepcopy(value)

    def capture(self,run):
        _managed_class_guard()
        need(nonce(run) and self.active is False and self.raw is self.original_raw and self.lock is self.raw.lock
            and self.raw.namespace is self.raw.original_namespace and self.raw.namespace.decoding is False);self.active=True
        try:
            with self.lock.held():
                from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
                self.identity();need(type(self.context) is PicoSnapshotSettingsScope2Baseline and self.context.raw is self.raw)
                actual=self.raw.real_clock();started=self.monotonic();requested=self.clock_ms()
                need(number(started,0,1e15) and integer(requested,1) and self.guard() is not False)
                command=dict(schemaVersion=1,commandId=secrets.token_hex(16),runId=run,action=ACTION,settingsScope=2)
                anchor=dict(hostMonotonic=started,nativeEpochMs=requested,actualHostMonotonic=actual)
                self.raw.begin(self.context,command,anchor)
                # One full worst-case return reservation precedes Native send.
                # The transport consumes that same token for the first getter.
                self.raw.reserve_read();self.raw.fresh();self.send(command)
                for attempt in range(31):
                    raw=self.read();self.raw.fresh()
                    need(type(raw) is bytes and len(raw)<=LIMIT)
                    text=raw.decode('utf-8');value=decode(text);need(type(value) is dict)
                    if value.get('commandId')==command['commandId']:
                        need(value.get('snapshotSettingsOriginalsVersion')==2)
                        epoch=self.clock_ms();validate(value,run,command['commandId'],self.pid,epoch)
                        need(value['capturedEpochMs']>=requested)
                        current=accept(self.previous,value);need(self.guard() is not False)
                        self.raw.fresh();epoch=self.clock_ms();finished=self.monotonic()
                        oldest=min(value['capturedEpochMs'],value['source']['entriesEpochMs'])
                        need(number(finished,started,1e15) and -250<=epoch-oldest
                            and max(epoch-oldest,requested-oldest+(finished-started)*1000)<=1500)
                        self.raw.complete(self.transport.reference,hashlib.sha256(raw).hexdigest())
                        self.raw.context=None
                        self.previous=current;self.last_raw=text;self.last_sha256=hashlib.sha256(raw).hexdigest();self.anchor=anchor
                        return deepcopy(value)
                    self.raw.fresh()
                    if attempt<30:self.sleep(.05)
                need(False)
        except BaseException:
            self.failed=True;self.raw.poison();raise
        finally:self.active=False
