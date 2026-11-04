"""Explicit complete capture-settings scope on the original Snapshot baseline.

No setter or setting restoration is supplied. Source2 includes actual duration
raw QVariant and the independent float-handle flags/default/value.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import integer,need,number
from adapters.pico4.snapshot_settings_baseline import PicoSnapshotSettingsBaseline,SnapshotSettingsBaselineOriginals
from adapters.pico4.snapshot_settings_scope2_reader import PicoSnapshotSettingsScope2Reader
from adapters.pico4.snapshot_settings_query_originals import SnapshotSettingsQueryOriginals


class SnapshotSettingsScope2BaselineOriginals(SnapshotSettingsBaselineOriginals):
    settings_scope=2


class PicoSnapshotSettingsScope2Baseline(PicoSnapshotSettingsBaseline):
    settings_scope=2
    originals_type=SnapshotSettingsScope2BaselineOriginals

    def __init__(self,parent,reader,path,*,may_capture):
        need(type(reader) is PicoSnapshotSettingsScope2Reader and type(reader.raw) is SnapshotSettingsQueryOriginals
            and reader.raw.run==parent.run and reader.raw.binding==parent.binding and reader.raw.lock is parent.lock)
        self.raw=self.original_raw=reader.raw
        self.closed_checkpoint=self.original_closed_checkpoint=None
        super().__init__(parent,reader,path,may_capture=may_capture)
        reader.bind_context(self)

    def bound(self):
        need(self.raw is self.original_raw and self.raw.reader is self.reader
            and self.closed_checkpoint is self.original_closed_checkpoint)
        self.raw.resource();return super().bound()

    def bind_closed_checkpoint(self,checkpoint):
        from adapters.pico4.snapshot_settings_close import PicoSnapshotSettingsClose
        need(type(checkpoint) is PicoSnapshotSettingsClose and checkpoint.baseline is self
            and checkpoint.parent is self.parent.close_owner and checkpoint.lock is self.lock
            and checkpoint.run==self.run and checkpoint.binding==self.binding)
        self.bound()
        previous=self.closed_checkpoint
        if previous is not None:
            previous.bound();need(previous.parent is checkpoint.parent and previous.disk==checkpoint.disk)
        self.closed_checkpoint=self.original_closed_checkpoint=checkpoint

    def original_anchor(self,value,anchor,raw_sha):
        need(number(anchor['actualHostMonotonic'],self.raw.created_actual,self.raw.created_actual+120))
        rows=[row for row in self.raw.state['queries'] if row['command']['commandId']==value['commandId']]
        need(len(rows)==1 and rows[0]['command']['runId']==value['runId'] and rows[0]['status']=='returned'
            and rows[0]['anchor']==anchor and rows[0]['acceptedSha256']==raw_sha)

    def source2_query_fence(self,anchor):
        need(self.raw is self.original_raw and self.raw.context is self and self.reader.context is self)
        now=self.parent.native.monotonic();epoch=self.parent.native.clock_ms()
        need(number(now,anchor['hostMonotonic'],anchor['hostMonotonic']+1.5)
            and integer(epoch,anchor['nativeEpochMs'],anchor['nativeEpochMs']+1500))

    def final_actual_fence(self,anchor):
        # This is the SAME original physical Host clock, including persistence
        # and lock waiting after the raw reader returned. No endpoint query.
        with self.lock.held():
            self.bound();need(self.raw.real_clock is self.raw.original_real_clock)
            now=self.raw.real_clock()
            need(number(now,anchor['actualHostMonotonic'],anchor['actualHostMonotonic']+1.5)
                and now<anchor['actualHostMonotonic']+1.5 and now<self.raw.created_actual+120)

    def capture(self):
        result=super().capture();self.final_actual_fence(self.reader.anchor);return result

    def before_input(self):
        super().before_input();self.final_actual_fence(self.reader.anchor)

    def observe(self):
        result=super().observe();self.final_actual_fence(self.reader.anchor);return result
