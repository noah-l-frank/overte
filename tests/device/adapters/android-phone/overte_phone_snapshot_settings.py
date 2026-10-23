"""Native-owned fixed Snapshot settings lease; commands carry no desired values.

The original typed Qt serialization is retained and hashed by its native owner.
JSON projections are private diagnostics, never replacement typed settings.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import typed_equal
from overte_phone_snapshot_source import nonce

FILE='phone-snapshot-settings.json'
VERSION=2
KEYS=sorted(('alsoTakeAnimatedSnapshot','snapshotFormat','previousSnapshotHref','previousSnapshotDomainID',
    'previousStillSnapPath','previousStillSnapStoryID','previousStillSnapBlastingDisabled','previousStillSnapHifiSharingDisabled','previousStillSnapUrl',
    'previousAnimatedSnapPath','previousAnimatedSnapStoryID','previousAnimatedSnapUrl','previousAnimatedSnapBlastingDisabled','previousAnimatedSnapHifiSharingDisabled'))


def sha(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def command(value):
    need(type(value) is dict)
    restoring=value.get('operation')=='restore'
    exact(value,{'schemaVersion','commandId','action','runId','operation'}|({'restoreId','expectedSha256'} if restoring else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-snapshot-settings'
        and nonce(value['commandId']) and nonce(value['runId']) and value['operation'] in ('capture','observe','restore','retire'))
    if restoring:need(nonce(value['restoreId']) and sha(value['expectedSha256']))
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'snapshotSettingsLeaseVersion','instance','runId','commandId','sequence','processId','capturedEpochMs','operation','source'})
    need(type(value['snapshotSettingsLeaseVersion']) is int and value['snapshotSettingsLeaseVersion']==VERSION
        and nonce(value['instance']) and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid
        and all(value[k]==request[k] for k in ('runId','commandId','operation')))
    fresh(value['capturedEpochMs'],epoch);source=value['source']
    exact(source,{'scopePresent','closed','restoring','restored','retired','openedEpochMs','handbackEpochMs','originalSha256','currentSha256',
        'restoreId','expectedSha256','current','currentSerializedBase64'})
    need(all(type(source[k]) is bool for k in ('scopePresent','closed','restoring','restored','retired'))
        and source['scopePresent'] is (not source['retired']) and integer(source['openedEpochMs'],1,value['capturedEpochMs'])
        and all(sha(source[k]) for k in ('originalSha256','currentSha256')))
    current=source['current'];exact(current,{'entries','format'});exact(current['entries'],set(KEYS));exact(current['format'],{'set','value'})
    need(type(current['format']['set']) is bool and type(current['format']['value']) is str and len(current['format']['value'])<=16)
    for entry in current['entries'].values():
        exact(entry,{'present','value'});need(type(entry['present']) is bool)
    encoded=source['currentSerializedBase64'];need(type(encoded) is str and 0<len(encoded)<=43692)
    try:raw=base64.b64decode(encoded,validate=True)
    except Exception:need(False)
    need(0<len(raw)<=32768 and base64.b64encode(raw).decode()==encoded and hashlib.sha256(raw).hexdigest()==source['currentSha256'])
    if source['restoring']:need(nonce(source['restoreId']) and sha(source['expectedSha256']))
    else:need(source['restoreId']==source['expectedSha256']=='' and not source['restored'] and not source['retired'])
    if source['restored']:
        need(source['restoring'] and source['currentSha256']==source['originalSha256']
            and integer(source['handbackEpochMs'],source['openedEpochMs'],value['capturedEpochMs']))
    else:need(integer(source['handbackEpochMs'],0,0) and not source['retired'])
    if request['operation']=='capture':need(source['scopePresent'] and source['closed'] and not source['restoring'])
    if request['operation']=='restore':
        need(source['restored'] and source['closed'] and source['scopePresent']
            and source['restoreId']==request['restoreId'] and source['expectedSha256']==request['expectedSha256'])
    if request['operation']=='retire':need(source['retired'] and source['restored'] and source['closed'])
    return value


class PhoneSnapshotSettings:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep,read_only=False):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(read_only) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.read_only=monotonic,sleep,read_only;self.last=None;self.original_source=None

    def restore_source(self,value):
        request=dict(schemaVersion=1,action='phone-snapshot-settings',**{k:value[k] for k in ('commandId','runId','operation')})
        if value['operation']=='restore':request.update({k:value['source'][k] for k in ('restoreId','expectedSha256')})
        validate(value,request,self.pid,value['capturedEpochMs']);need(self.last is None);self.last=deepcopy(value)
        if value['operation']=='capture' or value['source']['restored']:self.original_source=deepcopy(value['source'])

    def request(self,run,operation,*,restore_id=None,expected_sha256=None):
        try:
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-settings',runId=run,operation=operation)
            if operation=='restore':request.update(restoreId=restore_id,expectedSha256=expected_sha256)
            else:need(restore_id is None and expected_sha256 is None)
            command(request);need(not self.read_only or operation=='observe')
            if operation in ('restore','retire'):need(self.last is not None and self.last['runId']==run)
            need(self.guard() is not False);start=prior=self.monotonic();need(number(start,0,1e15))
            barrier=self.clock_ms();need(integer(barrier,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=131072)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,prior,1e15) and now-start<5);prior=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms());need(value['capturedEpochMs']>=barrier)
                    if self.last is not None:
                        old=self.last;before=old['source'];actual=value['source']
                        need(value['runId']==old['runId'] and value['instance']==old['instance'] and value['sequence']>old['sequence']
                            and value['capturedEpochMs']>=old['capturedEpochMs']
                            and all(actual[k]==before[k] for k in ('originalSha256','openedEpochMs')))
                        if before['restoring']:need(actual['restoring'] and all(actual[k]==before[k] for k in ('restoreId','expectedSha256')))
                        if before['restored']:need(actual['restored'] and actual['handbackEpochMs']==before['handbackEpochMs'])
                        if before['retired']:need(actual['retired'])
                    if value['source']['restored'] and self.original_source is not None:
                        need(typed_equal(value['source']['current'],self.original_source['current'])
                            and value['source']['currentSerializedBase64']==self.original_source['currentSerializedBase64'])
                    need(self.guard() is not False);end=self.monotonic();need(number(end,prior,1e15) and end-start<5)
                    if operation=='capture' and self.original_source is None:self.original_source=deepcopy(value['source'])
                    self.last=deepcopy(value);return value
                if attempt==50:break
                self.sleep(min(.1,5-(now-start)))
        except Exception:raise NativeUIError('Original Snapshot settings ownership or restoration failed') from None
        raise NativeUIError('Original Snapshot settings source is unavailable')
