"""Source-bound iOS login UI; private credential transport remains mandatory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from adapters.native_feature_observation import need
from adapters.normal_ui import Locator,NativeUIError
from adapters.token_login_ui import IDS,VERSION


class IOSLoginIO:
    def __init__(self,original,private_input=None):
        self.original=original;self.private_input=private_input;self.elapsed_floor=0

    def capture(self):
        value=self.original.capture()
        need(type(value.get('loginControlsVersion')) is int and value['loginControlsVersion']==VERSION
             and value['elapsedMs']>=self.elapsed_floor)
        self.elapsed_floor=value['elapsedMs'];result=deepcopy(value)
        result['controls']=[r for r in result['controls'] if r['id'] in IDS]
        for row in result['controls']:row.pop('frame') # Original geometry was validated by the native transport.
        return result

    def input(self,identifier,action,*,token,text=None):
        value=self.capture();rows=[r for r in value['controls'] if r['id']==identifier]
        need(identifier in IDS-{'login.page'} and len(rows)==1 and rows[0]['enabled']
             and rows[0]['inputReady'] and rows[0]['token']==token)
        if action=='replace':
            if identifier in ('login.username','login.password'):
                # No credential value enters the public fixture request API.
                need(self.private_input is not None and rows[0]['focused'])
                original=self.original.capture()
                current=[r for r in original['controls'] if r['id']==identifier]
                need(original.get('loginControlsVersion')==VERSION and len(current)==1
                     and current[0]['token']==token and current[0]['enabled'] and current[0]['inputReady'] and current[0]['focused'])
                request=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=original['instance'],
                    sequence=original['lastSequence']+1,observedElapsedMs=original['elapsedMs'],
                    fieldToken=token,operation='replace',text=text)
                self.private_input.replace(request)
                return
            need(identifier=='login.server' and rows[0]['focused'])
            self.original.native.edit('replace',text,field=identifier)
        elif action=='activate':
            need(text is None)
            self.original.ui.click_with_token(Locator('accessibility id','OverteNavigation.'+identifier),token)
        elif action=='submit':
            need(identifier=='login.password' and text is None and rows[0]['focused'])
            submit=[r for r in value['controls'] if r['id']=='login.submit']
            need(len(submit)==1 and submit[0]['enabled'] and submit[0]['inputReady'])
            self.original.ui.click_with_token(Locator('accessibility id','OverteNavigation.login.submit'),submit[0]['token'])
        else:raise NativeUIError('Native iOS login input is invalid')

    def close_view(self):
        value=self.original.capture();rows=[r for r in value['controls'] if r['id']=='tablet.home']
        need(len(rows)==1 and rows[0]['enabled'])
        self.original.ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet.home'),rows[0]['token'])
