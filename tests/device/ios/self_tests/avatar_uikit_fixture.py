"""Explicit native UIKit2 producer; actual ordinary host callbacks supply events.

Retained native-object pools model UIKit reuse. Quiescence never claims those
objects died. No Qt Keys/Pointer packet or prior UIKit1 DTO is relabelled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid


class UIKit2Boundary:
    def __init__(self,epoch_ms,monotonic_ms,*,pid=31):
        self.epoch_ms,self.monotonic_ms,self.pid=epoch_ms,monotonic_ms,pid
        self.instance=uuid.uuid4().hex;self.installation=self.stamp();self.sequence=0
        self.objects=[];self.contacts=[];self.dispatches=[];self.pending=[]
    def stamp(self):return dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic_ms())
    def object(self,kind):
        value=dict(id=uuid.uuid4().hex,kind=kind,born=self.stamp(),expired=None,alive=True);self.objects.append(value);return value['id']
    def touch(self,callback):
        view=self.object('view');touch=self.object('touch');event=self.object('event');contact=uuid.uuid4().hex
        began=self.stamp();self.contacts.append(dict(id=contact,kind='touch',object=touch,target=view,window=None,source=None,began=began,ended=None,phase=0,active=True))
        def dispatch(phase):
            value=dict(sequence=len(self.dispatches)+1,event=event,entered=self.stamp(),returned=None,
                **{'finally':None},phases=[dict(object=touch,contact=contact,kind='touch',phase=phase,target=view,window=None,source=None)])
            self.dispatches.append(value);self.pending.append(value['sequence']);return value
        start=dispatch(0);start['returned']=self.stamp();start['finally']=self.stamp();self.pending.remove(start['sequence'])
        end=dispatch(3);self.contacts[-1].update(ended=self.stamp(),phase=3,active=False)
        try:
            value=callback();end['returned']=self.stamp();return value
        finally:end['finally']=self.stamp();self.pending.remove(end['sequence'])
    def packet(self,query):
        self.sequence+=1;before=self.stamp()
        return dict(iosUIKitInputVersion=2,commandId=query['commandId'],runId=query['runId'],fixtureUrl=query['fixtureUrl'],
            instance=self.instance,sequence=self.sequence,processId=self.pid,clockDomain='native-main-ios-uikit-input',
            clockBefore=before,clockAfter=self.stamp(),complete=True,installed=True,applicationClass='ModeledUIKitApplication',
            installation=deepcopy(self.installation),failure=None,dispatchSequence=len(self.dispatches),pendingDispatches=deepcopy(self.pending),
            objects=deepcopy(self.objects),targets=[],contacts=deepcopy(self.contacts),dispatches=deepcopy(self.dispatches))
