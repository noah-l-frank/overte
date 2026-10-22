"""Phone original Create input component; no entity-state success verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid
from copy import deepcopy
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import snapshot,same_reference,metadata,control_id,field,choice,ascii_text
from overte_phone_script_files import PhoneScriptFileIO,nonce

FILE='phone-create-ui.json'


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','createControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command
         and value['action']=='observe' and nonce(value['instance']) and nonce(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
         and integer(value['processId'],1) and value['processId']==pid
         and type(value['createControlsVersion']) is int and value['createControlsVersion']==1
         and type(value['ready']) is bool and type(value['controls']) is list and len(value['controls'])<=384)
    fresh(value['capturedEpochMs'],epoch)
    ids=set();tokens=set()
    for row in value['controls']:
        metadata(row)
        need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls'])
    return value


class PhoneCreateIO(PhoneScriptFileIO):
    wire_action='phone-create-ui'
    validate_capture=staticmethod(validate)

    def __init__(self,*args,tablet_shown,**kwargs):
        need(callable(tablet_shown));self.tablet_shown=tablet_shown
        super().__init__(*args,**kwargs)

    def capture(self):
        try:
            original=super().capture()
            opened=self.tablet_shown();need(type(opened) is bool and self.guard() is not False)
            fresh(original['capturedEpochMs'],self.clock_ms())
            self.last_original=deepcopy(original)
            return snapshot(dict(createControlsVersion=original['createControlsVersion'],open=opened,ready=original['ready'],
                scope=dict(instance=original['instance'],generation=original['generation'],sequence=original['lastCommandSequence'],
                           elapsedMs=original['elapsedMs'],processId=original['processId']),controls=original['controls']))
        except Exception:raise NativeUIError('Phone original Create UI is unavailable or invalid') from None

    def input(self,identifier,action,*,reference,value=None):
        try:
            need(control_id(identifier) and identifier!='create.page' and action in ('activate','replace','select-index','scroll'))
            if action=='replace':need(field(identifier));ascii_text(value)
            elif action=='select-index':need(choice(identifier) and integer(value,0,31))
            elif action=='scroll':need(identifier=='create.scrollbar' and value in ('up','down'))
            else:need(identifier!='create.scrollbar' and value is None)
            current=self.capture();row=same_reference(reference,current,identifier)
            need(current['open'] and current['ready'] and row['enabled'] and row.get('inputReady',True))
            if action=='replace':need(row['focused'])
            if action=='select-index':need(value<row['count'])
            original=reference['scope']
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=original['instance'],
                generation=original['generation'],sequence=original['sequence']+1,observedElapsedMs=original['elapsedMs'],
                controlId=identifier,controlToken=row['token'])
            if action=='replace':request['text']=value
            elif action=='select-index':request['index']=value
            elif action=='scroll':request['direction']=value
            self.deliver(request,dict(instance=original['instance'],generation=original['generation']))
        except Exception:raise NativeUIError('Phone original Create input delivery failed') from None

    def activate(self,identifier,*,reference):self.input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):self.input(identifier,'replace',reference=reference,value=value)
    def select_index(self,identifier,value,*,reference):self.input(identifier,'select-index',reference=reference,value=value)
    def scroll(self,identifier,value,*,reference):self.input(identifier,'scroll',reference=reference,value=value)
