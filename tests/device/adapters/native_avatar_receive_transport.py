"""Bounded original avatar receive acquisition; no input or outgoing evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from adapters.native_feature_observation import decode,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.native_avatar_receive import ACTION,LIMIT,command,validate

def read(self,after_sequence):
    try:
        need(integer(after_sequence,0,1_000_000_000) and (self.last is None or after_sequence>=self.last['sequence']) and self.guard() is not False)
        started=previous=self.monotonic();need(number(started,0,1e15))
        barrier=self.clock_ms();need(integer(barrier,1))
        request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action=ACTION)
        command(request,ios=self.ios);self.send(deepcopy(request))
        for attempt in range(51):
            need(self.guard() is not False)
            raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and self.guard() is not False);previous=now
            if type(value) is dict and value.get('commandId')==request['commandId']:
                epoch=self.clock_ms();need(integer(epoch,barrier))
                validate(value,request,self.pid,epoch,previous=self.last)
                need(value['sequence']>after_sequence and value['requestedEpochMs']>=barrier and self.guard() is not False)
                final=self.monotonic();need(number(final,previous,1e15) and final-started<5)
                need(max(epoch-value['capturedEpochMs'],barrier-value['capturedEpochMs']+(final-started)*1000)<=1500)
                self.last=deepcopy(value);return deepcopy(value)
            if attempt<50:self.sleep(.1)
    except Exception:raise NativeUIError('Original received avatar source is unavailable or invalid') from None
    raise NativeUIError('Original received avatar source did not produce this request')
