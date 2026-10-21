"""Closed original Script UI observations; concrete transports own acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time

from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.script_ui_inventory import validate as validate_inventory
from adapters.token_script_file_ui import file_control, metadata_fields, validate_metadata

VERSION = 1


def identity(value):
    return type(value) is str and re.fullmatch(r'(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})',value) is not None


def validate(value, command, pid, epoch):
    exact(value, {'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','fileControlsVersion','ready','controls',
        'scriptInventory','originalKind','originalReceipt'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION
         and value['commandId']==command and value['action']=='observe'
         and identity(value['instance']) and identity(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence'])
         and integer(value['elapsedMs']) and integer(value['processId'],1) and value['processId']==pid
         and type(value['fileControlsVersion']) is int and value['fileControlsVersion']==1
         and value['ready'] is True and type(value['controls']) is list and len(value['controls'])<=384)
    fresh(value['capturedEpochMs'],epoch);validate_inventory(value['scriptInventory'])
    # Retain the actual native envelope, not a replacement assembled from a
    # requested result. These equality checks make field projection auditable.
    need(value['originalKind']=='ios-normal-ui-v1')
    receipt=value['originalReceipt'];exact(receipt,{'schemaVersion','commandId','observation'})
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and receipt['commandId']==command
         and type(command) is str and re.fullmatch('ios-[0-9a-f]{32}',command))
    original=receipt['observation'];need(type(original) is dict)
    links={'instance':'instance','generation':'instance','sourceSequence':'scriptSourceSequence',
        'lastCommandSequence':'lastSequence','elapsedMs':'elapsedMs','capturedEpochMs':'sampleEpochMs',
        'processId':'processId','fileControlsVersion':'fileControlsVersion','ready':'ready','scriptInventory':'scriptInventory'}
    need(type(original.get('scriptObservationVersion')) is int and original['scriptObservationVersion']==1
         and all(type(original.get(source)) is type(value[target]) and original[source]==value[target]
             for target,source in links.items()))
    projected=[{key:deepcopy(item) for key,item in row.items() if key!='frame'}
               for row in original['controls'] if file_control(row.get('id'))]
    need(value['controls']==projected)
    ids,tokens=set(),set()
    for row in value['controls']:
        need(type(row) is dict and file_control(row.get('id')))
        exact(row,{'id','token','enabled','focused'}|metadata_fields(row['id'],row))
        need(identity(row['token']) and row['token'] not in tokens and row['id'] not in ids
             and type(row['enabled']) is bool and type(row['focused']) is bool)
        validate_metadata(row);ids.add(row['id']);tokens.add(row['token'])
    return value


class ScriptUISource:
    """Acquisition/cursor checks shared by independent primary and actor readers."""
    def __init__(self, acquire, clock_ms, guard, pid, *, ios=True, monotonic=time.monotonic):
        need(all(callable(fn) for fn in (acquire,clock_ms,guard,monotonic)) and integer(pid,1) and ios is True)
        self.acquire,self.clock_ms,self.guard,self.pid=acquire,clock_ms,guard,pid
        self.ios,self.monotonic=ios,monotonic
        self.instance=self.generation=None
        self.sequence=self.elapsed=self.last_command=0
        self.captured_epoch=0

    def capture(self):
        need(self.guard() is not False)
        started=self.monotonic();need(number(started,0,1e15))
        before=self.clock_ms();need(integer(before,1))
        value=self.acquire()
        validate(value,value.get('commandId'),self.pid,self.clock_ms())
        need(value['capturedEpochMs']>=max(before,self.captured_epoch)
             and value['sourceSequence']>self.sequence and value['elapsedMs']>=self.elapsed
             and value['lastCommandSequence']>=self.last_command
             and self.instance in (None,value['instance']) and self.generation in (None,value['generation']))
        ended=self.monotonic();need(number(ended,0,1e15) and started<=ended and ended-started<5
                                    and self.guard() is not False)
        self.instance,self.generation=value['instance'],value['generation']
        self.sequence,self.elapsed,self.last_command=value['sourceSequence'],value['elapsedMs'],value['lastCommandSequence']
        self.captured_epoch=value['capturedEpochMs']
        return deepcopy(value)
