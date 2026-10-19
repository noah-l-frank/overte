"""Synthetic Qt seam for Phone transport checks; no native app is executed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from self_tests.test_token_login_ui import Boundary


class LoginNativeBoundary:
    def __init__(self):
        self.ui=Boundary();self.sequence=self.source_sequence=0
        self.value=None;self.commands=[];self.inputs=[];self.mutate=None;self.before_input=None

    def snapshot(self):
        self.source_sequence+=1
        return dict(self.ui.capture(),schemaVersion=1,privateCommandReaderVersion=1,sourceSequence=self.source_sequence,
            lastCommandSequence=self.sequence,elapsedMs=round(self.ui.clock*1000),capturedEpochMs=20000,processId=31)

    def send(self,outer):
        assert set(outer)=={'schemaVersion','commandId','action','request'} and outer['action']=='phone-login-ui'
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
