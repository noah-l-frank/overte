"""Join newly acquired native originals to host acquisition time without retiming.

The original native packets and their clocks remain unchanged. The public clock
is the measured beginning of this bounded acquisition, never a timestamp minted
around an old cached result. Historical validation cannot produce a fresh read.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time

from adapters.native_feature_observation import NativeFeatureObservation, exact, integer, need, number, validate

VERSION=1


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_join(record, originals):
    exact(record,{'clockJoinVersion','hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic',
        'hostAfterMonotonic','nativeBefore','nativeAfter','sourceTimes','originalsSha256'})
    need(type(record['clockJoinVersion']) is int and record['clockJoinVersion']==VERSION
         and record['originalsSha256']==digest(originals))
    start,end=record['hostBeforeEpochMs'],record['hostAfterEpochMs']
    before,after=record['hostBeforeMonotonic'],record['hostAfterMonotonic']
    need(number(start,1,1e15) and number(end,start,start+1500)
         and number(before,0,1e15) and number(after,before,before+1.5)
         and after-before<1.5 and end-start<1500
         and abs((end-start)-(after-before)*1000)<=250)
    first,last=record['nativeBefore'],record['nativeAfter']
    for packet in (first,last):
        need(type(packet) is dict)
        validate(packet,packet.get('requestId'),packet.get('processId'),packet.get('capturedEpochMs'))
    need(first['processId']==last['processId'] and first['instance']==last['instance']
         and first['sequence']<last['sequence'] and first['requestId']!=last['requestId']
         and first['capturedEpochMs']<=last['capturedEpochMs']
         and abs((last['capturedEpochMs']-first['capturedEpochMs'])-(after-before)*1000)<=250
         and all(last['lifecycle'][key]>=count for key,count in first['lifecycle'].items()))
    times=record['sourceTimes']
    need(type(times) is list and 1<=len(times)<=32)
    seen=set()
    for row in times:
        exact(row,{'source','field','epochMs'})
        name,field=row['source'],row['field']
        need(type(name) is str and type(field) is str and (name,field) not in seen
             and name in originals and type(originals[name]) is dict
             and integer(row['epochMs'],1) and originals[name].get(field)==row['epochMs']
             and first['capturedEpochMs']<=row['epochMs']<=last['capturedEpochMs']
             and last['capturedEpochMs']-row['epochMs']<=1500)
        seen.add((name,field))
    expected={(name,field) for name,packet in originals.items() if type(packet) is dict
              for field in ('capturedEpochMs','sampleEpochMs') if field in packet}
    need(seen==expected)
    return record


class NativeClockAcquisition:
    def __init__(self,native,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(native,NativeFeatureObservation) and native.ios
             and callable(epoch_ms) and callable(monotonic))
        self.native,self.epoch_ms,self.monotonic=native,epoch_ms,monotonic
        self.started=None;self.finished=False

    def begin(self,host_barrier):
        need(self.started is None and number(host_barrier,1,1e15))
        mono=self.monotonic();epoch=self.epoch_ms()
        need(number(mono,0,1e15) and number(epoch,host_barrier,1e15) and self.native.guard() is not False)
        packet=self.native.read(self.native.sequence)
        self.started=dict(clockJoinVersion=VERSION,hostBeforeEpochMs=epoch,hostBeforeMonotonic=mono,
                          nativeBefore=deepcopy(packet))
        return packet['capturedEpochMs']

    def finish(self,originals,fields):
        need(self.started is not None and not self.finished)
        need(type(originals) is dict and type(fields) in (tuple,list))
        packet=self.native.read(self.native.sequence)
        epoch=self.epoch_ms();mono=self.monotonic()
        times=[dict(source=name,field=field,epochMs=originals[name][field]) for name,field in fields]
        record=dict(self.started,hostAfterEpochMs=epoch,hostAfterMonotonic=mono,nativeAfter=deepcopy(packet),
                    sourceTimes=times,originalsSha256=digest(originals))
        validate_join(record,originals);need(self.native.guard() is not False)
        self.finished=True
        return deepcopy(record)
