"""Original Phone login widgets on the bound private Qt command channel."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_ui import NativeUIError
from adapters.token_login_ui import IDS,VERSION,validate_metadata
from overte_phone_script_files import PhoneScriptFileIO,nonce

FILE='phone-login-ui.json'


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','loginControlsVersion','privateCommandReaderVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command
         and value['action']=='observe' and nonce(value['instance']) and nonce(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
         and integer(value['processId'],1) and value['processId']==pid
         and type(value['loginControlsVersion']) is int and value['loginControlsVersion']==VERSION
         and type(value['privateCommandReaderVersion']) is int and value['privateCommandReaderVersion']==1
         and value['ready'] is True and type(value['controls']) is list and len(value['controls'])<=6)
    fresh(value['capturedEpochMs'],epoch)
    ids=set();tokens=set()
    for row in value['controls']:
        need(type(row) is dict);validate_metadata(row)
        need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    return value


class PhoneLoginIO(PhoneScriptFileIO):
    wire_action='phone-login-ui'
    validate_capture=staticmethod(validate)

    def capture(self):
        try:
            value=super().capture()
            need(value['capturedEpochMs']>=getattr(self,'epoch_floor',0))
            self.epoch_floor=value['capturedEpochMs']
            return value
        except Exception:raise NativeUIError('Phone original login UI is unavailable or invalid') from None

    def input(self,identifier,action,*,token,text=None):
        try:
            need(type(identifier) is str and identifier in IDS-{'login.page'} and nonce(token)
                 and type(action) is str and action in ('activate','replace','submit'))
            if action=='replace':
                need(identifier in ('login.username','login.password') and type(text) is str
                     and re.fullmatch('[\x20-\x7e]{1,4096}',text))
            else:need(text is None)
            if action=='submit':need(identifier=='login.password')
            observed=self.capture();rows=[r for r in observed['controls'] if r['id']==identifier]
            need(len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady'] and rows[0]['token']==token
                 and (action=='activate' or rows[0]['focused']))
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=observed['instance'],
                generation=observed['generation'],sequence=observed['lastCommandSequence']+1,
                observedElapsedMs=observed['elapsedMs'],controlId=identifier,controlToken=token)
            if action=='replace':request['text']=text
            if action=='replace':
                try:self.deliver(request,observed)
                finally:
                    # Overwrite the owned private command with a fresh read-only
                    # request even after uncertain delivery. The concrete writer
                    # independently reads back its exact replacement bytes.
                    # A lost binding refuses the write and keeps owner intent.
                    self.capture()
            else:self.deliver(request,observed)
        except Exception:raise NativeUIError('Phone controlled login input delivery failed') from None
