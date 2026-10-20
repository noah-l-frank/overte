"""Nonce/PID-bound native original main-bundle reads, before identity claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from ios.adapters.bundle_identity import compare

FILE='ios-installed-bundle-observation.json'
VERSION=1


def command(value):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='ios-bundle-observe' and type(value['commandId']) is str
         and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
    return value


def validate(value,request,pid):
    command(request)
    exact(value,{'bundleObservationVersion','commandId','instance','sequence','processId',
                 'capturedEpochMs','status','preparedEpochMs','bundle'})
    need(type(value['bundleObservationVersion']) is int and value['bundleObservationVersion']==VERSION
         and value['commandId']==request['commandId'] and type(value['instance']) is str
         and re.fullmatch('[0-9a-f]{32}',value['instance']) and integer(value['sequence'],1)
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['capturedEpochMs'],1) and value['status'] in ('pending','ready','unavailable'))
    if value['status']=='ready':
        need(integer(value['preparedEpochMs'],1) and value['preparedEpochMs']<=value['capturedEpochMs'])
        compare(value['bundle'],value['bundle'])
    else:need(type(value['preparedEpochMs']) is int and value['preparedEpochMs']==0 and type(value['bundle']) is dict and not value['bundle'])
    return value


class NativeBundleObservation:
    def __init__(self,send,read,guard,pid,native_clock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,guard,native_clock,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.guard,self.pid,self.native_clock=send,read,guard,pid,native_clock
        self.monotonic,self.sleep=monotonic,sleep
        self.instance,self.sequence,self.epoch,self.bundle,self.prepared=None,0,0,None,None

    def read(self):
        try:
            request=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='ios-bundle-observe')
            command(request);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            self.send(request);latest=None
            for attempt in range(1001):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid)
                    need(value['status']!='unavailable' and self.instance in (None,value['instance'])
                         and value['sequence']>self.sequence and value['capturedEpochMs']>=self.epoch)
                    if latest is not None:
                        need(value['sequence']>=latest['sequence'] and value['capturedEpochMs']>=latest['capturedEpochMs']
                             and (value['sequence']!=latest['sequence'] or value==latest))
                    self.instance=value['instance'];latest=deepcopy(value)
                    if value['status']=='ready':
                        # An independent fresh native clock/PID acquisition
                        # follows this completed file transaction. Host UTC is
                        # never substituted for native time, even after a long
                        # initial hash. The original prepared time stays intact.
                        actual=self.native_clock()
                        need(type(actual) is dict and integer(actual.get('processId'),1) and actual['processId']==self.pid)
                        fresh(value['capturedEpochMs'],actual.get('capturedEpochMs'))
                        if self.bundle is not None:compare(value['bundle'],self.bundle);need(value['preparedEpochMs']==self.prepared)
                        now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<100 and self.guard() is not False)
                        self.sequence,self.epoch,self.prepared=value['sequence'],value['capturedEpochMs'],value['preparedEpochMs']
                        self.bundle=deepcopy(value['bundle']);return value
                now=self.monotonic();need(number(now,0,1e15) and now>=previous);previous=now
                if now-started>=100 or attempt==1000:break
                self.sleep(min(.1,100-(now-started)))
        except Exception:raise NativeUIError('Original iOS installed bundle observation failed') from None
        raise NativeUIError('Original iOS installed bundle observation is unavailable')
