"""Original generic iOS Login UI over the existing normal HTTP/AFC transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.token_login_ui import IDS,VERSION as LOGIN_VERSION,validate_metadata
from adapters.script_feature.ui_source import identity
from ios.adapters.normal_login import IOSLoginIO
from ios.adapters.account_preferences import validate as validate_preferences,require_owned

VERSION=1
LINKS={'instance':'instance','generation':'generation','sourceSequence':'scriptSourceSequence',
       'lastCommandSequence':'lastSequence','elapsedMs':'elapsedMs','capturedEpochMs':'sampleEpochMs',
       'processId':'processId','loginControlsVersion':'loginControlsVersion','ready':'ready'}


def nonce(value):
    need(type(value) is str and re.fullmatch('ios-[0-9a-f]{32}',value))
    return value


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action',*LINKS,'originalKind','originalReceipt','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']=='observe'
         and value['commandId']==command and nonce(command) and identity(value['instance']) and identity(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
         and integer(value['processId'],1) and value['processId']==pid
         and type(value['loginControlsVersion']) is int and value['loginControlsVersion']==LOGIN_VERSION
         and value['ready'] is True and type(value['controls']) is list and len(value['controls'])<=7
         and value['originalKind']=='ios-normal-login-ui-v1')
    fresh(value['capturedEpochMs'],epoch)
    receipt=value['originalReceipt'];exact(receipt,{'schemaVersion','commandId','observation'})
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and receipt['commandId']==command)
    original=receipt['observation'];need(type(original) is dict and original.get('scriptObservationVersion')==1
        and type(original['scriptObservationVersion']) is int
        and all(type(original.get(source)) is type(value[target]) and original[source]==value[target]
                for target,source in LINKS.items()))
    validate_preferences(original.get('accountPreferences'))
    rows=[{key:deepcopy(item) for key,item in row.items() if key!='frame'}
          for row in original['controls'] if row.get('id') in IDS]
    need(value['controls']==rows)
    seen=set();tokens=set()
    for row in value['controls']:
        validate_metadata(row)
        need(row['id'] not in seen and row['token'] not in tokens and identity(row['token']))
        seen.add(row['id']);tokens.add(row['token'])
    return value


class IOSLoginSource:
    def __init__(self,original,clock_ms,guard,pid,*,private_input=None,read_only=False,origin=None,run=None,monotonic=time.monotonic):
        need(all(callable(fn) for fn in (clock_ms,guard,monotonic)) and integer(pid,1) and type(read_only) is bool)
        self.original,self.clock_ms,self.guard,self.pid=original,clock_ms,guard,pid
        self.input_io=IOSLoginIO(original,private_input);self.read_only=read_only;self.origin=origin;self.run=run
        self.monotonic=monotonic;self.ios=True
        self.instance=self.generation=None
        self.sequence=self.elapsed=self.last_command=self.epoch_floor=0

    def capture(self):
        need(self.guard() is not False)
        started=self.monotonic();need(number(started,0,1e15))
        before=self.clock_ms();need(integer(before,1))
        raw=self.original.native.capture(native_epoch_ms=self.clock_ms)
        need(raw.get('loginControlsVersion')==LOGIN_VERSION and identity(raw.get('generation'))
             and raw.get('scriptObservationVersion')==1)
        if self.origin is not None:require_owned(raw.get('accountPreferences'),self.origin,run=self.run)
        receipt=deepcopy(self.original.native.last_receipt)
        need(type(receipt) is dict and receipt.get('observation')==raw)
        value=dict(schemaVersion=VERSION,commandId=receipt['commandId'],action='observe',
            **{target:deepcopy(raw[source]) for target,source in LINKS.items()},
            controls=[{key:deepcopy(item) for key,item in row.items() if key!='frame'}
                      for row in raw['controls'] if row['id'] in IDS],
            originalKind='ios-normal-login-ui-v1',originalReceipt=receipt)
        validate(value,value['commandId'],self.pid,self.clock_ms())
        need(self.instance in (None,value['instance']) and value['sourceSequence']>self.sequence
             and value['elapsedMs']>=self.elapsed and value['lastCommandSequence']>=self.last_command
             and value['capturedEpochMs']>=max(before,self.epoch_floor))
        ended=self.monotonic();need(number(ended,0,1e15) and started<=ended and ended-started<5 and self.guard() is not False)
        # Native root/window generation is retained verbatim. A normal tablet
        # show/hide can advance it; the transport instance and all source/input
        # cursors still remain bound across role acquisitions. Per-input
        # TokenLoginUI additionally pins its own active generation and tokens.
        self.instance,self.generation=value['instance'],value['generation']
        self.sequence,self.elapsed,self.last_command=value['sourceSequence'],value['elapsedMs'],value['lastCommandSequence']
        self.epoch_floor=value['capturedEpochMs']
        return deepcopy(value)

    def input(self,identifier,action,*,token,text=None):
        need(not self.read_only)
        return self.input_io.input(identifier,action,token=token,text=text)

    def close_view(self):
        need(not self.read_only)
        return self.input_io.close_view()
