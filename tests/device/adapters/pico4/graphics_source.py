"""Passive original generic VR Graphics roots/controls, never input authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import math
from adapters.authentication_journey.login_source import inventory,accept_inventory
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_journey.files import ScriptFileIO,nonce
from adapters.token_graphics_ui import graphics_control,metadata_fields,validate_metadata

VERSION=1
FILE='graphics-ui.json'
COMMAND='files/overte-e2e/graphics-ui-command.json'
PROFILES=frozenset({'graphics-generic-v1','tablet-menu-v1'})


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','graphicsControlsVersion',
        'graphicsObservationVersion','graphicsInventory','tabletShown','editorFocused','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command
        and value['action']=='observe' and nonce(value['instance']) and nonce(value['generation'])
        and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
        and integer(value['processId'],1) and value['processId']==pid
        and type(value['graphicsControlsVersion']) is int and value['graphicsControlsVersion']==1
        and type(value['graphicsObservationVersion']) is int and value['graphicsObservationVersion']==VERSION
        and value['ready'] is True and all(type(value[key]) is bool for key in ('tabletShown','editorFocused'))
        and type(value['controls']) is list and len(value['controls'])<=384)
    fresh(value['capturedEpochMs'],epoch);inventory(value['graphicsInventory'],profiles=PROFILES)
    ids=set();tokens=set()
    for row in value['controls']:
        need(type(row) is dict and graphics_control(row.get('id')))
        exact(row,{'id','token','enabled','focused'}|metadata_fields(row['id']))
        need(nonce(row['token']) and row['token'] not in tokens and row['id'] not in ids
            and type(row['enabled']) is bool and type(row['focused']) is bool)
        validate_metadata(row);ids.add(row['id']);tokens.add(row['token'])
        if row['id']=='graphics.page':
            need(row['profile']=='generic-immediate-v1'
                and any(root['profile']=='graphics-generic-v1' and root['visible'] and root['inCurrentTree']
                    for root in value['graphicsInventory']['roots']))
    return value


class PicoGraphicsSource(ScriptFileIO):
    wire_action='graphics-ui-observe'
    validate_capture=staticmethod(validate)

    def __init__(self,adapter,target,native):
        def send(envelope):
            exact(envelope,{'schemaVersion','commandId','action','request'})
            request=envelope['request'];exact(request,{'schemaVersion','commandId','action'})
            need(envelope['schemaVersion']==request['schemaVersion']==1 and envelope['action']==self.wire_action
                and request['action']=='observe' and request['commandId']==envelope['commandId'])
            native.guard();adapter.adb.write_debug_app_file(target,'org.overte.pico',COMMAND,
                json.dumps(request,sort_keys=True,separators=(',',':'))+'\n');native.guard()
        super().__init__(send,lambda:adapter.adb.read_debug_app_file(target,'org.overte.pico',
            'files/overte-e2e/'+FILE,attempts=1),native.clock_ms,native.guard,native.pid,
            monotonic=native.monotonic,sleep=native.sleep)

    def capture(self):
        started=self.monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
        value=super().capture();need(value['capturedEpochMs']>=getattr(self,'epoch_floor',0))
        current=accept_inventory(getattr(self,'inventory',None),value['graphicsInventory'],profiles=PROFILES)
        need(self.guard() is not False);queried=self.monotonic();need(type(queried) in (int,float) and math.isfinite(queried) and queried>=started)
        epoch=self.clock_ms();fresh(value['capturedEpochMs'],epoch);need(self.guard() is not False)
        finished=self.monotonic();need(type(finished) in (int,float) and math.isfinite(finished)
            and queried<=finished and finished-started<5
            and epoch-value['capturedEpochMs']+math.ceil((finished-queried)*1000)<=1500)
        self.inventory=current;self.epoch_floor=value['capturedEpochMs'];return value

    def restore_inventory(self,previous):
        # History pins the next original acquisition; it is never a current UI
        # fact and never sends a read, input, repair or hidden page creation.
        need(self.guard() is not False)
        validate(previous,previous['commandId'],self.pid,previous['capturedEpochMs'])
        current=accept_inventory(getattr(self,'inventory',None),previous['graphicsInventory'],profiles=PROFILES)
        need(self.instance in (None,previous['instance']) and self.generation in (None,previous['generation'])
            and self.sequence<=previous['sourceSequence'] and self.elapsed<=previous['elapsedMs']
            and self.last_command<=previous['lastCommandSequence']
            and previous['capturedEpochMs']>=getattr(self,'epoch_floor',0) and self.guard() is not False)
        self.instance,self.generation=previous['instance'],previous['generation']
        self.sequence,self.elapsed,self.last_command=previous['sourceSequence'],previous['elapsedMs'],previous['lastCommandSequence']
        self.inventory=current;self.epoch_floor=previous['capturedEpochMs']

    def input(self,*_args,**_kwargs):need(False)


def resources(value):
    """Current actual resources; a hidden retained root is still present."""
    validate(value,value['commandId'],value['processId'],value['capturedEpochMs'])
    source=value['graphicsInventory'];result=[]
    if value['tabletShown']:result.append('panel:graphics-tablet')
    if any(row['profile']=='graphics-generic-v1' for row in source['roots']):result.append('panel:graphics')
    if any(row['profile']=='tablet-menu-v1' for row in source['roots']):result.append('connection:graphics-menu')
    if source['qmlLoads']['components']:result.append('connection:graphics-qml-load')
    if source['keyboard3D']['raised']:result.append('input:graphics-keyboard')
    if value['editorFocused']:result.append('input:graphics-editor')
    return sorted(result)
