"""Original Phone Emote UI over the existing private Qt command transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import snapshot,metadata,control_id,same_reference
from overte_phone_script_files import PhoneScriptFileIO,nonce

FILE='phone-emote-ui.json'


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence','lastCommandSequence',
        'elapsedMs','capturedEpochMs','processId','emoteControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command
        and value['action']=='observe' and nonce(value['instance']) and nonce(value['generation'])
        and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
        and integer(value['processId'],1) and value['processId']==pid
        and type(value['emoteControlsVersion']) is int and value['emoteControlsVersion']==1
        and type(value['ready']) is bool and type(value['controls']) is list and len(value['controls'])<=64)
    fresh(value['capturedEpochMs'],epoch)
    ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls']);return value


class PhoneEmoteIO(PhoneScriptFileIO):
    wire_action='phone-emote-ui'
    validate_capture=staticmethod(validate)

    def __init__(self,*args,tablet_shown,**kwargs):
        need(callable(tablet_shown));self.tablet_shown=tablet_shown;self.original_packet=None
        super().__init__(*args,**kwargs)

    def capture(self):
        try:
            started=self.monotonic();epoch=self.clock_ms();need(number(started,0,1e15) and integer(epoch,1))
            original=super().capture();opened=self.tablet_shown();now=self.monotonic();current_epoch=self.clock_ms()
            need(type(opened) is bool and number(now,started,1e15) and integer(current_epoch,epoch)
                and self.guard() is not False)
            validate(original,original['commandId'],self.pid,current_epoch)
            need(max(current_epoch-original['capturedEpochMs'],epoch-original['capturedEpochMs']+(now-started)*1000)<=1500)
            value=snapshot(dict(emoteControlsVersion=1,open=opened,ready=original['ready'],controls=original['controls'],
                scope=dict(instance=original['instance'],generation=original['generation'],sequence=original['lastCommandSequence'],
                    sourceSequence=original['sourceSequence'],elapsedMs=original['elapsedMs'],
                    capturedEpochMs=original['capturedEpochMs'],processId=original['processId'])))
            self.original_packet=deepcopy(original);return value
        except Exception:raise NativeUIError('Phone original Emote UI is unavailable or invalid') from None

    def input(self,identifier,*,reference,direction=None):
        try:
            need(control_id(identifier) and identifier!='emote.page')
            need(direction in ('up','down') if identifier=='emote.grid' else direction is None)
            current=self.capture();row=same_reference(reference,current,identifier)
            need(current['open'] and current['ready'] and row['enabled'] and row['inputReady'])
            scope=reference['scope'];action='scroll' if direction is not None else 'activate'
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=scope['instance'],
                generation=scope['generation'],sequence=scope['sequence']+1,observedElapsedMs=scope['elapsedMs'],
                controlId=identifier,controlToken=row['token'])
            if direction is not None:request['direction']=direction
            self.deliver(request,dict(instance=scope['instance'],generation=scope['generation']))
        except Exception:raise NativeUIError('Phone original Emote input delivery failed') from None

    def activate(self,identifier,*,reference):self.input(identifier,reference=reference)
    def scroll(self,identifier,direction,*,reference):self.input(identifier,reference=reference,direction=direction)
