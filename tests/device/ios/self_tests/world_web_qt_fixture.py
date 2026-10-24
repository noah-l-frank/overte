"""Actual host entered/returned/finally frames; Qt event delivery is modeled.

W3C release ACKs are absent here. Contacts and held keys end only through the
modeled actual Qt event dispatch. The handlers execute the original product JS.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary


class QtPointer(NativePointerBoundary):
    def __init__(self,sdk):
        super().__init__();self.sdk=sdk;self.now=sdk.epoch();self.source_instance=uuid.uuid4().hex
        self.born=sdk.base_epoch-100;self.start=sdk.base_epoch-90
    def tick(self):self.now=self.sdk.tick();return self.now
    def edge(self,row,kind):
        stamp=self.tick();event=dict(sequence=len(self.events)+1,dispatch=row['id'],kind=kind,epochMs=stamp,monotonicMs=stamp-self.sdk.base_epoch)
        self.events.append(event);row.update({kind+'Sequence':event['sequence'],kind+'EpochMs':event['epochMs'],kind+'MonotonicMs':event['monotonicMs']})
    def enter(self,event):
        event.setdefault('timestamp',round(self.sdk.time*1000));return super().enter(event)
    def packet_source(self):
        def weak_rows(table):return [dict(row,alive=weak() is not None) for weak,row in table]
        return dict(iosPointerSourceVersion=1,instance=self.source_instance,bornEpochMs=self.born,complete=self.complete,
            startup=dict(observed=True,epochMs=self.start,monotonicMs=0,windowCount=0,mouseButtons=0),eventSequence=len(self.events),events=deepcopy(self.events),
            dispatches=deepcopy(self.rows),pendingDispatches=len(self.pending),contacts=[deepcopy(self.contacts[key]) for key in sorted(self.contacts)],ends=deepcopy(self.ends),
            devices=weak_rows(self.devices),targets=weak_rows(self.targets),qtMouseButtons=self.qt_buttons,worldTapActive=self.world_tap)


class QtKeys:
    def __init__(self,sdk):
        self.sdk=sdk;self.instance=uuid.uuid4().hex;self.rows=[];self.events=[];self.down={};self.ended=[];self.pending=set();self.complete=True
        self.device=uuid.uuid4().hex;self.target=uuid.uuid4().hex;self.device_birth=None;self.target_birth=None;self.modifiers=0;self.physical={}
    def edge(self,row,kind):
        stamp=self.sdk.tick();sequence=len(self.events)+1;mono=stamp-self.sdk.base_epoch
        self.events.append(dict(sequence=sequence,dispatch=row['id'],kind=kind,epochMs=stamp,monotonicMs=mono))
        row.update({kind+'Sequence':sequence,kind+'EpochMs':stamp,kind+'MonotonicMs':mono})
    def notify(self,down,key,text,modifiers,handler=lambda:True):
        if self.device_birth is None:self.device_birth=self.sdk.tick()
        if self.target_birth is None:self.target_birth=self.sdk.tick()
        token=uuid.uuid4().hex;kind='key-press' if down else 'key-release'
        if down:
            assert key not in self.physical;key_id=uuid.uuid4().hex;self.physical[key]=key_id
        else:key_id=self.physical.pop(key)
        row=dict(id=token,batch=uuid.uuid4().hex,kind=kind,target=self.target,device=self.device,detail=dict(keyId=key_id,modifiers=modifiers,autoRepeat=False,qtTimestamp=self.sdk.epoch()-self.sdk.base_epoch),
            enteredSequence=0,enteredEpochMs=0,enteredMonotonicMs=0,returnedSequence=0,returnedEpochMs=0,returnedMonotonicMs=0,
            deliveryResult=None,finallySequence=0,finallyEpochMs=0,finallyMonotonicMs=0)
        self.rows.append(row);self.pending.add(token);self.edge(row,'entered');self.modifiers=modifiers;index=key_id
        if down:
            assert index not in self.down;self.down[index]=dict(device=self.device,keyId=key_id,target=self.target,pressDispatch=token,releaseDispatch='')
        else:
            assert index in self.down;ended=self.down.pop(index);ended['releaseDispatch']=token;self.ended.append(ended)
        try:
            result=handler();assert type(result) is bool;row['deliveryResult']=result;self.edge(row,'returned');return result
        finally:
            if row['deliveryResult'] is None:self.complete=False
            self.edge(row,'finally');self.pending.remove(token)
    def packet_source(self):
        return dict(iosWorldWebKeySourceVersion=2,instance=self.instance,bornEpochMs=self.sdk.base_epoch-100,complete=self.complete,
            startup=dict(observed=True,epochMs=self.sdk.base_epoch-90,monotonicMs=0,windowCount=0,modifiers=0),eventSequence=len(self.events),
            events=deepcopy(self.events),dispatches=deepcopy(self.rows),pendingDispatches=len(self.pending),down=[deepcopy(self.down[key]) for key in sorted(self.down)],ended=deepcopy(self.ended),preedit=[],
            devices=[] if self.device_birth is None else [dict(id=self.device,bornEpochMs=self.device_birth,className='HostModeledQtKeyboard',alive=True)],
            targets=[] if self.target_birth is None else [dict(id=self.target,bornEpochMs=self.target_birth,className='HostModeledQtWindow',alive=True)],qtModifiers=self.modifiers)
