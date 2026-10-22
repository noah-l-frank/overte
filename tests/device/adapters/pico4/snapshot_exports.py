"""Current actual Pico JNI/export/native-lease originals; no ACK effect facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.pico4.navigation import NativeNavigationIO
from adapters.pico4.snapshot_export_controls import component
from adapters.pico4.snapshot_export_originals import exports,continuity as export_continuity
from adapters.pico4.snapshot_export_readbacks import command,source as readbacks,continuity as readback_continuity,nonce
from adapters.pico4.snapshot_capture_source import path
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
FILE='feature-pico-snapshot-exports.json'
LIMIT=262144


def lease(value):
    need(type(value) is dict and type(value.get('present')) is bool)
    exact(value,{'present'}|({'componentUrl','native'} if value['present'] else set()))
    if not value['present']:return value
    need(component(value['componentUrl']));native=value['native']
    exact(native,{'snapshotExportLeaseVersion','handle','ticket','busy'})
    need(type(native['snapshotExportLeaseVersion']) is int and native['snapshotExportLeaseVersion']==1 and type(native['busy']) is bool)
    for key in ('handle','ticket'):
        text=native[key];need(type(text) is str and (key=='ticket' and text=='' or re.fullmatch('[1-9][0-9]{0,18}',text) is not None and int(text)<=2**63-1))
    need(native['busy']==bool(native['ticket']));return value


def components(value):
    need(all(type(value[key]) is str and 0<len(value[key].encode())<=LIMIT for key in ('exportsRaw','readbacksRaw')))
    return exports(decode(value['exportsRaw']),path),readbacks(decode(value['readbacksRaw']))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'picoSnapshotExportsVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','lease','exportsRaw','readbacksRaw'})
    need(type(value['picoSnapshotExportsVersion']) is int and value['picoSnapshotExportsVersion']==VERSION
        and value['requestId']==request['commandId'] and value['runId']==request['runId'] and nonce(value['instance'])
        and integer(value['sequence'],1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch);lease(value['lease']);events,copies=components(value)
    need(integer(events['capturedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']));fresh(events['capturedEpochMs'],epoch)
    body=copies['source']
    if 'initialized' not in body:
        need(integer(body['capturedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']));fresh(body['capturedEpochMs'],epoch)
    return value


def continuity(before,after):
    need(after['instance']==before['instance'] and after['runId']==before['runId'] and after['processId']==before['processId']
        and after['sequence']>before['sequence'] and after['requestedEpochMs']>=before['requestedEpochMs'] and after['capturedEpochMs']>=before['capturedEpochMs'])
    old,old_copies=components(before);new,new_copies=components(after);export_continuity(old,new);readback_continuity(old_copies['source'],new_copies['source'])


class PicoSnapshotExportIO(NativeNavigationIO):
    DIRECTORY='files/overte-e2e/android-control-'
    def guard(self):super().guard();self.adapter._installation(self.target)
    def raw(self):return self.adapter.adb.read_debug_app_file(self.target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1)
    def _read(self,kind):
        need(kind=='status');raw=self.raw()
        if raw is None or raw=='':return raw
        value=decode(raw);return json.dumps(dict(commandId=value.get('requestId'),packet=value))


class PicoSnapshotExports:
    def __init__(self,io,clock_ms,pid,source_lock,*,read_only=True,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(io,PicoSnapshotExportIO) and isinstance(source_lock,ScriptSourceLock) and integer(pid,1)
            and type(read_only) is bool and (read_only or callable(io._before_send)) and all(callable(fn) for fn in (clock_ms,monotonic,sleep)))
        self.io,self.clock_ms,self.pid,self.lock=io,clock_ms,pid,source_lock
        self.read_only,self.monotonic,self.sleep=read_only,monotonic,sleep
        self.last=self.raw=self.last_request=self.publication=None
    @staticmethod
    def envelope(run,operation='observe',*,export_request='',resource_id=''):
        return command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-snapshot-exports',runId=run,
            operation=operation,exportRequest=export_request,resourceId=resource_id))
    def before_publish(self,request):
        command(request);self.lock.assert_held()
        need(self.publication is not None and self.publication['request']==request and self.publication['published'] is False)
        elapsed=self.monotonic()-self.publication['started'];need(number(elapsed,0,1.5));self.publication['published']=True
    def restore(self,value,request):
        need(self.last is None);validate(value,request,self.pid,value['capturedEpochMs']);self.last=deepcopy(value)
    def request(self,run,operation='observe',*,export_request='',resource_id=''):
        request=self.envelope(run,operation,export_request=export_request,resource_id=resource_id)
        need(not self.read_only or operation=='observe')
        with self.lock.held():
            started=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
            self.publication=dict(request=deepcopy(request),started=started,published=False)
            self.io.bind_input();self.io.send(deepcopy(request));previous=started
            for attempt in range(31):
                self.io.guard();raw=self.io.raw();need(raw is None or type(raw) is str and len(raw.encode())<=LIMIT)
                if raw:
                    value=decode(raw)
                    if value.get('requestId')==request['commandId']:
                        epoch=self.clock_ms();validate(value,request,self.pid,epoch);need(value['requestedEpochMs']>=requested)
                        if self.last is not None:continuity(self.last,value)
                        result=deepcopy(value);saved=deepcopy(value);saved_request=deepcopy(request)
                        events,copies=components(value);captured=min(value['capturedEpochMs'],events['capturedEpochMs'],
                            copies['source'].get('capturedEpochMs',value['capturedEpochMs']))
                        self.io.guard();final=self.clock_ms();completed=self.monotonic()
                        need(number(completed,previous,1e15) and completed-started<5 and number(final,epoch,1e15)
                            and -250<=final-captured and max(final-captured,requested-captured+(completed-started)*1000)<=1500)
                        self.last,self.raw,self.last_request=saved,raw,saved_request;return result
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and attempt<30);previous=now;self.sleep(.1)
            need(False)
    def original(self):
        need(self.raw is not None);return dict(raw=self.raw,sha256=hashlib.sha256(self.raw.encode()).hexdigest(),request=deepcopy(self.last_request))
