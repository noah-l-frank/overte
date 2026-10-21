"""Original generic iOS Graphics survey with its untouched native receipt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.token_graphics_ui import IDS,metadata_fields,validate_metadata
from adapters.script_feature.ui_source import identity
from ios.adapters.normal_graphics import IOSGraphicsIO
from ios.adapters.login_source import nonce

VERSION=1
LINKS={'instance':'instance','generation':'generation','sourceSequence':'scriptSourceSequence',
       'lastCommandSequence':'lastSequence','elapsedMs':'elapsedMs','capturedEpochMs':'sampleEpochMs',
       'processId':'processId','graphicsControlsVersion':'graphicsControlsVersion','ready':'ready'}


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action',*LINKS,'originalKind','originalReceipt','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']=='observe'
         and value['commandId']==command and nonce(command) and identity(value['instance']) and identity(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
         and integer(value['processId'],1) and value['processId']==pid
         and type(value['graphicsControlsVersion']) is int and value['graphicsControlsVersion']==1
         and value['ready'] is True and type(value['controls']) is list and len(value['controls'])<=len(IDS)
         and value['originalKind']=='ios-normal-graphics-ui-v1')
    fresh(value['capturedEpochMs'],epoch)
    receipt=value['originalReceipt'];exact(receipt,{'schemaVersion','commandId','observation'})
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and receipt['commandId']==command)
    raw=receipt['observation'];need(type(raw) is dict and type(raw.get('scriptObservationVersion')) is int
        and raw['scriptObservationVersion']==1 and all(type(raw.get(source)) is type(value[target])
        and raw[source]==value[target] for target,source in LINKS.items()))
    from ios.adapters.normal_input import observation
    observation(raw,pid,epoch)
    rows=[{key:deepcopy(item) for key,item in row.items() if key!='frame'} for row in raw['controls'] if row['id'] in IDS]
    need(value['controls']==rows)
    seen=set();tokens=set()
    for row in rows:
        exact(row,{'id','token','enabled','focused'}|metadata_fields(row['id']))
        validate_metadata(row)
        if row['id']=='graphics.page':need(row['profile']=='generic-immediate-v1')
        need(identity(row['token']) and row['id'] not in seen and row['token'] not in tokens
             and type(row['enabled']) is bool and type(row['focused']) is bool)
        seen.add(row['id']);tokens.add(row['token'])
    return value


class IOSGraphicsSource(IOSGraphicsIO):
    def __init__(self,original,clock_ms,guard,pid,*,read_only=False,monotonic=time.monotonic):
        super().__init__(original)
        need(all(callable(fn) for fn in (clock_ms,guard,monotonic)) and integer(pid,1) and type(read_only) is bool)
        self.clock_ms,self.guard,self.pid,self.read_only,self.monotonic=clock_ms,guard,pid,read_only,monotonic
        self.instance=self.generation=None;self.sequence=self.elapsed=self.last_command=self.epoch_floor=0

    def capture(self):
        need(self.guard() is not False)
        started=self.monotonic();need(number(started,0,1e15))
        before=self.clock_ms();need(integer(before,1))
        raw=self.original.native.capture(native_epoch_ms=self.clock_ms)
        receipt=deepcopy(self.original.native.last_receipt)
        need(type(receipt) is dict and receipt.get('observation')==raw)
        value=dict(schemaVersion=VERSION,commandId=receipt['commandId'],action='observe',
            **{target:deepcopy(raw.get(source)) for target,source in LINKS.items()},
            controls=[{key:deepcopy(item) for key,item in row.items() if key!='frame'}
                for row in raw['controls'] if row['id'] in IDS],
            originalKind='ios-normal-graphics-ui-v1',originalReceipt=receipt)
        validate(value,value['commandId'],self.pid,self.clock_ms())
        need(self.instance in (None,value['instance']) and value['sourceSequence']>self.sequence
             and value['elapsedMs']>=self.elapsed and value['lastCommandSequence']>=self.last_command
             and value['capturedEpochMs']>=max(before,self.epoch_floor))
        ended=self.monotonic();need(number(ended,started,started+1.5) and ended-started<1.5 and self.guard() is not False)
        # Retain actual window changes. TokenGraphicsUI pins one input context
        # separately, after the ordinary tablet has been opened.
        self.instance,self.generation=value['instance'],value['generation']
        self.sequence,self.elapsed=value['sourceSequence'],value['elapsedMs']
        self.last_command,self.epoch_floor=value['lastCommandSequence'],value['capturedEpochMs']
        return deepcopy(value)

    def activate(self,identifier,*,token):
        need(not self.read_only);return super().activate(identifier,token=token)
    def scroll(self,identifier,direction,*,token):
        need(not self.read_only);return super().scroll(identifier,direction,token=token)
    def set_value(self,identifier,value,*,token):
        need(not self.read_only);return super().set_value(identifier,value,token=token)
