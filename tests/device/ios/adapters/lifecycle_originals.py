"""Canonical original UI/holder/UIKit acquisition for Lifecycle integration.

This returns source evidence and editor facts only. World input, generations,
Actor evidence and full journey capability still require their concrete owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters import lifecycle_fields as fields,keyboard_source as keyboard


def validate(value,binding,run):
    exact(value,{'iosLifecycleOriginalsVersion','binding','runId','originals','pendingRequest','clockJoin'})
    need(type(value['iosLifecycleOriginalsVersion']) is int and value['iosLifecycleOriginalsVersion']==1
         and same(context(value['binding']),context(binding)) and value['runId']==identifier(run))
    raw=value['originals'];exact(raw,{'beforeUI','pending','ui','keyboard'})
    joined=validate_join(value['clockJoin'],raw);first,last=joined['nativeBefore'],joined['nativeAfter']
    need(str(first['processId'])==binding['processIdentity'] and same(first['lifecycle'],last['lifecycle']))
    pid=first['processId'];floor,ceiling=first['capturedEpochMs'],last['capturedEpochMs']
    for name in ('beforeUI','ui'):
        ui_packet(raw[name],pid,ceiling)
        need(type(raw[name].get('lifecycleFieldsVersion')) is int and raw[name]['lifecycleFieldsVersion']==1)
        source=raw[name]['lifecycleFieldInventory'];fields.validate(source,pid=pid)
        need(source['complete'] and floor<=source['clockBefore']['epochMs']<=source['clockAfter']['epochMs']<=ceiling)
    need(raw['beforeUI']['instance']==raw['ui']['instance']
         and raw['beforeUI']['lastSequence']==raw['ui']['lastSequence'])
    fields.validate(raw['ui']['lifecycleFieldInventory'],pid=pid,previous=raw['beforeUI']['lifecycleFieldInventory'])
    original=raw['keyboard'];query=dict(schemaVersion=1,commandId=original['requestId'],action=keyboard.ACTION,runId=run)
    keyboard.validate(original,query,pid,ceiling)
    need(floor<=original['clockBefore']['epochMs']<=original['clockAfter']['epochMs']<=ceiling)
    holder=fields.join_pending(raw['ui']['lifecycleFieldInventory'],raw['pending'],value['pendingRequest'])
    need(value['pendingRequest']['operation']=='observe' and value['pendingRequest']['runId']==run)
    return dict(field=fields.active(raw['ui']['lifecycleFieldInventory']),keyboard=keyboard.measured(original),holder=holder)


class IOSLifecycleSources:
    def __init__(self,sources,run,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        self.source=sources;self.run=identifier(run);self.binding=deepcopy(context(sources['binding']))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.keyboard=sources['observer'].keyboard(clock_source=sources['clock_source'])
        self.pending=sources['observer'].pending_owner(clock_source=sources['clock_source'])

    def sample(self,host_barrier,*,event_id=''):
        self.source['check']();clock=NativeClockAcquisition(self.source['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        clock.begin(host_barrier)
        # The original normal survey also installs the native pending provider.
        # Retain that read; it is not silently replaced by the later source cut.
        before=self.source['native'].capture();pending=self.pending.read(self.run,event_id)
        request=dict(schemaVersion=1,commandId=pending['commandId'],action='feature-pending-commit-owner',
                     operation='observe',runId=self.run,eventId=event_id)
        ui=self.source['native'].capture();original=self.keyboard.read(self.run)
        raw=dict(beforeUI=before,pending=pending,ui=ui,keyboard=original)
        joined=clock.finish(raw,[('beforeUI','sampleEpochMs'),('pending','capturedEpochMs'),('ui','sampleEpochMs')])
        result=dict(iosLifecycleOriginalsVersion=1,binding=self.binding,runId=self.run,originals=raw,pendingRequest=request,clockJoin=joined)
        self.source['check']();validate(result,self.binding,self.run);return deepcopy(result)
