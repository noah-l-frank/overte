"""Pass-through original NativeInput observations, with owned query/raw taps.

The existing source performs the single actual HTTP request and AFC read. This
facade changes no input, native arguments, bytes, source clock or dispatch. It
exposes only its own callbacks so the whole Tablet query owner can journal
before POST and retain safe actual receipt bytes before interpretation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from ios.adapters.normal_input import NativeInput


class TabletWidgetsReader:
    def __init__(self,client,session,target,process,clock,*,monotonic,sleep):
        self.pid=None;self.raw=None;self.client=client;self.session=session;self.target=deepcopy(target)
        self.clock_ms,self.monotonic,self.sleep=clock,monotonic,sleep
        self.remote='@'+target['appId']+':documents/'+target['testBuild']['resultsDirectory']+'/ios-normal-ui-request-result.json'
        self.send=lambda _query:None
        self.original=lambda:self.raw if self.raw is not None else self.read_issued_original()
        outer=self
        class PassThrough:
            def execute(self,actual_session,method,body):
                result=client.execute(actual_session,method,body)
                if method=='mobile: pullFile' and body==dict(remotePath=outer.remote):
                    need(actual_session==session and type(result) is str and len(result)<=131072)
                    outer.raw=base64.b64decode(result,validate=True).decode('utf-8')
                    # The actual bytes reach the owner before the unchanged
                    # NativeInput parser interprets this same SDK result.
                    outer.original()
                return result
        def current():
            value=process();need(type(value) is dict and type(value.get('pid')) is int)
            need(self.pid in (None,value['pid']));self.pid=value['pid'];return value
        self.native=NativeInput(PassThrough(),session,target,current,monotonic=monotonic,sleep=sleep,native_epoch_ms=clock)
        self.native.observe_intent=lambda query:self.send(query)
        self.guard=lambda:current() is not None

    def read(self):
        value=self.native.capture()
        receipt=self.native.last_receipt;need(type(receipt) is dict and receipt.get('observation')==value)
        return value

    def read_issued_original(self):
        """Read an already-issued receipt without sending another query."""
        need(self.guard() is not False)
        result=self.client.execute(self.session,'mobile: pullFile',dict(remotePath=self.remote))
        need(type(result) is str and len(result)<=131072)
        self.raw=base64.b64decode(result,validate=True).decode('utf-8')
        need(self.guard() is not False);return self.raw


class TabletDiagnosticReader:
    """The original normal manager diagnostic, with explicit query/raw taps."""
    def __init__(self,transport,pid,clock,monotonic,sleep):
        self.pid,self.clock_ms,self.monotonic,self.sleep=pid,clock,monotonic,sleep
        self.send,self.original=transport.send,transport.original
        self.guard=lambda:transport.guard() is not False

    def read(self,after):
        from adapters.normal_script_manager import read_native_diagnostic
        import uuid
        need(self.guard() is not False)
        request='ios-'+uuid.uuid4().hex
        self.send(dict(schemaVersion=1,commandId=request,action='normal-feature-observe',includeAvatarEntities=False))
        value,_epoch=read_native_diagnostic(self.original,self.clock_ms,self.guard,after,
            expected_request=request,monotonic=self.monotonic,sleep=self.sleep)
        return value
