"""Synthetic native Create receipt source; no product or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys

from self_tests.test_normal_create_adapter import NativeCreate
from self_tests.test_token_create_ui import Controls


class CreateNativeBoundary:
    def __init__(self,directory):
        self.native=NativeCreate(directory);self.native.tablet=True;self.native.page='create'
        self.ui=Controls(self.native);self.ui.generation='b'*32;self.ui.pid=31
        self.value=None;self.commands=[];self.input_requests=[];self.mutate=None;self.before_input=None
        self.source_sequence=0

    def raw(self):
        self.source_sequence+=1
        value=self.ui.capture();scope=value['scope']
        return dict(schemaVersion=1,createControlsVersion=1,instance=scope['instance'],generation=scope['generation'],
            sourceSequence=self.source_sequence,lastCommandSequence=scope['sequence'],elapsedMs=scope['elapsedMs'],
            capturedEpochMs=20000,processId=31,ready=value['ready'],controls=value['controls'])

    def send(self,outer):
        assert set(outer)=={'schemaVersion','commandId','action','request'} and outer['action']=='phone-create-ui'
        request=deepcopy(outer['request']);assert request['commandId']==outer['commandId'];self.commands.append(request)
        if request['action']=='observe':self.value=self.raw()|dict(commandId=request['commandId'],action='observe')
        else:
            if self.before_input:self.before_input()
            original=self.ui.capture();scope=original['scope']
            valid=all(request[k]==scope[k] for k in ('instance','generation')) and request['sequence']==scope['sequence']+1
            valid=valid and request['observedElapsedMs']<=scope['elapsedMs']<=request['observedElapsedMs']+5000
            rows=[r for r in original['controls'] if r['id']==request['controlId']]
            valid=valid and len(rows)==1 and rows[0]['token']==request['controlToken']
            self.input_requests.append(request)
            if valid:
                value=request.get('text',request.get('index',request.get('direction')))
                self.ui.input(request['controlId'],request['action'],original,value)
            self.value=dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],performed=bool(valid),
                instance=scope['instance'],generation=scope['generation'],sequence=request['sequence'],processId=31)
        if self.mutate:self.mutate(self.value)
