"""Phone original Chat normal input; no message or keyboard verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import snapshot,same_reference,metadata,control_id,text
from overte_phone_script_files import PhoneScriptFileIO,nonce

FILE='phone-chat-ui.json'


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','chatControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command
         and value['action']=='observe' and nonce(value['instance']) and nonce(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
         and integer(value['processId'],1) and value['processId']==pid
         and type(value['chatControlsVersion']) is int and value['chatControlsVersion']==1
         and type(value['ready']) is bool and type(value['controls']) is list and len(value['controls'])<=64)
    fresh(value['capturedEpochMs'],epoch)
    ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls'])
    return value


class PhoneChatIO(PhoneScriptFileIO):
    wire_action='phone-chat-ui'
    validate_capture=staticmethod(validate)

    def __init__(self,*args,tablet_shown,**kwargs):
        need(callable(tablet_shown));self.tablet_shown=tablet_shown
        super().__init__(*args,**kwargs)

    def capture(self):
        try:
            original=super().capture();opened=self.tablet_shown()
            need(type(opened) is bool and self.guard() is not False)
            return snapshot(dict(chatControlsVersion=original['chatControlsVersion'],open=opened,ready=original['ready'],
                scope=dict(instance=original['instance'],generation=original['generation'],sequence=original['lastCommandSequence'],
                           elapsedMs=original['elapsedMs'],processId=original['processId']),controls=original['controls']))
        except Exception:raise NativeUIError('Phone original Chat UI is unavailable or invalid') from None

    def input(self,identifier,action,*,reference,value=None):
        try:
            need(control_id(identifier) and identifier!='chat.page' and action in ('activate','replace','submit'))
            if action=='replace':need(identifier=='chat.input');text(value)
            elif action=='submit':need(identifier=='chat.input' and value is None)
            else:need(value is None)
            current=self.capture();row=same_reference(reference,current,identifier)
            need(current['open'] and current['ready'] and row['enabled'] and row.get('inputReady',True))
            if action in ('replace','submit'):need(row['focused'])
            original=reference['scope']
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=original['instance'],
                generation=original['generation'],sequence=original['sequence']+1,observedElapsedMs=original['elapsedMs'],
                controlId=identifier,controlToken=row['token'])
            if action=='replace':request['text']=value
            self.deliver(request,dict(instance=original['instance'],generation=original['generation']))
        except Exception:raise NativeUIError('Phone original Chat input delivery failed') from None

    def activate(self,identifier,*,reference):self.input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):self.input(identifier,'replace',reference=reference,value=value)
    def submit(self,identifier,*,reference):self.input(identifier,'submit',reference=reference)
