"""Synthetic Qt seam for shared Authentication source checks; no native app is executed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from self_tests.test_token_login_ui import Boundary
from self_tests.test_login_ui_inventory import loads


class LoginNativeBoundary:
    def __init__(self):
        self.ui=Boundary(generic=True);self.sequence=self.source_sequence=0
        self.value=None;self.commands=[];self.inputs=[];self.mutate=None;self.before_input=None
        self.root=None;self.retired=set()

    def snapshot(self):
        self.source_sequence+=1
        if self.ui.dialog and self.root is None:self.root=uuid.uuid4().hex
        if not self.ui.dialog and self.root is not None:self.retired.add(self.root);self.root=None
        return dict(self.ui.capture(),schemaVersion=1,loginObservationVersion=1,startupDialogPresent=False,sourceSequence=self.source_sequence,
            lastCommandSequence=self.sequence,elapsedMs=round(self.ui.clock*1000),capturedEpochMs=20000,processId=31,
            loginInventory=dict(inventoryVersion=1,complete=True,qmlLoads=loads(),keyboard3D=dict(raised=False,enabled=False),retiredRoots=sorted(self.retired),roots=[dict(id=self.root,profile='qml-login-v1',
                visible=True,inCurrentTree=True,callbackRunning=False,callbackItemPresent=False)] if self.ui.dialog else []))

    def send(self,outer):
        assert set(outer)=={'schemaVersion','commandId','action','request'} and outer['action']=='login-ui-observe'
        # Record no actual text: this fixture deliberately mirrors the public
        # history privacy rule, not a desired result or production transport.
        safe=deepcopy(outer);safe['request'].pop('text',None);self.commands.append(safe)
        request=outer['request'];action=request['action']
        if action=='observe':
            assert set(request)=={'schemaVersion','commandId','action'}
            self.value=dict(self.snapshot(),commandId=request['commandId'],action=action)
        else:
            fields={'schemaVersion','commandId','action','instance','generation','sequence','observedElapsedMs','controlId','controlToken'}
            if action=='replace':fields.add('text')
            assert set(request)==fields and request['sequence']==self.sequence+1
            self.sequence=request['sequence']
            if self.before_input:self.before_input()
            current=self.snapshot();rows=[r for r in current['controls'] if r['id']==request['controlId']]
            valid=(request['instance']==current['instance'] and request['generation']==current['generation']
                and len(rows)==1 and rows[0]['token']==request['controlToken'] and rows[0]['inputReady'])
            self.inputs.append((request['controlId'],action))
            if valid:
                self.ui.input(request['controlId'],action,token=request['controlToken'],text=request.get('text'))
            self.value=dict(schemaVersion=1,commandId=request['commandId'],action=action,performed=valid,
                instance=current['instance'],generation=current['generation'],sequence=self.sequence,processId=31)
        if self.mutate:self.mutate(self.value)
