"""Normal NativeUI W3C input over original modeled UIKit widget objects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import dataclass
import uuid
import weakref
from adapters.normal_ui import NativeUI,W3C_ELEMENT,NativeUIError
from adapters.operation_transport_guard import check as final_transport_guard
from ios.adapters import native_ui


@dataclass
class Widget:
    identifier:str
    visible:bool=True
    enabled:bool=True


class NativeTabletClient:
    def __init__(self,target,*,pointer=None):
        self.target,self.pointer=target,pointer;self.calls=[];self.references={};self.observations=[]
        self.item=None;self.shown=None;self.birth=None;self.retire_before_click=False
        self.session=target.sources.binding['sessionId'];self.pid=int(target.sources.binding['processIdentity'])

    def original(self):
        observed=self.target.native.capture();shown=observed['tabletShown']
        if shown!=self.shown:
            self.shown=shown;self.birth=uuid.uuid4().hex
            self.item=Widget('OverteTabletClose' if shown else 'OverteTabletOpen')
        item=self.item
        packet=native_ui.validate(dict(schemaVersion=1,valid=True,sampleEpochMs=observed['sampleEpochMs'],processId=observed['processId'],
            elements=[dict(identifier=item.identifier,visible=item.visible,enabled=item.enabled,frame=dict(x=16,y=16,width=128,height=64))]),
            self.pid,self.target.domain.epoch())
        self.observations.append(deepcopy(packet));return packet

    def check(self):
        self.original();return True

    def call(self,method,path,body=None):
        final_transport_guard()
        self.calls.append((method,path,deepcopy(body)));base='/session/'+self.session
        if not path.startswith(base+'/'):raise NativeUIError('Foreign modeled existing W3C session')
        if method=='DELETE' and path==base+'/actions':return None
        if method=='POST' and path==base+'/elements':
            observed=self.original();rows=[row for row in observed['elements'] if row['identifier']==body['value']]
            if not rows:return []
            if body['using']!='accessibility id':raise NativeUIError('Unexpected modeled locator')
            reference='node-'+uuid.uuid4().hex;self.references[reference]=(weakref.ref(self.item),self.birth)
            return [{W3C_ELEMENT:reference}]
        reference=path.removeprefix(base+'/element/').split('/')[0]
        if reference not in self.references:raise NativeUIError('Unknown modeled original widget')
        item,birth=self.references[reference];item=item();self.original()
        live=item is not None and item is self.item and birth==self.birth
        if method=='GET' and path.endswith('/displayed'):return live and item.visible
        if method=='GET' and path.endswith('/enabled'):return live and item.enabled
        if method=='POST' and path.endswith('/click'):
            if self.retire_before_click:self.target.native.tablet=not self.shown;self.original();live=False
            if not live:raise NativeUIError('Original modeled widget retired before click')
            if self.pointer is not None:self.pointer.touch('touch-begin',position=[80,48])
            self.target.native.tablet=item.identifier=='OverteTabletOpen';self.original()
            if self.pointer is not None:self.pointer.touch('touch-end',position=[80,48])
            return None
        raise NativeUIError('Unsupported modeled W3C operation')


def normal_tablet(target,*,pointer=None):
    client=NativeTabletClient(target,pointer=pointer)
    normal=NativeUI(client,client.session,client.check,monotonic=lambda:target.domain.time,sleep=target.native.sleep)
    target.sdk=normal;target.actions.sdk=normal
    return client,normal
