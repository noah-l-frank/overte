"""Explicit native batch model calls the existing actual typed host producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import secrets
import zlib
from ios.adapters import world_web_snapshot as snapshot
from ios.self_tests.world_web_source_boundary import SDK,URL


def encoded(raw):
    compressed=len(raw).to_bytes(4,'big')+zlib.compress(raw)
    return dict(encoding='qt-zlib-base64',plainBytes=len(raw),plainSha256=hashlib.sha256(raw).hexdigest(),
        compressedBytes=len(compressed),compressedSha256=hashlib.sha256(compressed).hexdigest(),data=base64.b64encode(compressed).decode())


def packed(body):return encoded(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())


class SnapshotNative:
    def __init__(self,sdk=None,*,document=False,pending_polls=0,held_callback=False,autodocument=False):
        self.sdk=SDK() if sdk is None else sdk;self.instance=secrets.token_hex(16);self.sequence=0;self.last=None;self.commands=[];self.records={};self.order=[];self.states={}
        self.document=document;self.autodocument=autodocument;self.fixture_url=getattr(self.sdk,'fixture_url',URL);self.pending_polls=pending_polls;self.held_callback=held_callback;self.callback_pending=False;self.dom_issued=0
        if document:
            from ios.self_tests.world_web_source_fixture import OriginalSources
            self.page=OriginalSources(clock_ms=self.sdk.tick,monotonic_ms=lambda:round(self.sdk.time*1000),fixture_url=self.fixture_url,run=self.sdk.run)
    def clock(self):return dict(epochMs=self.sdk.tick(),monotonicMs=round(self.sdk.time*1000))
    def send(self,query):
        snapshot.command(query);self.commands.append(deepcopy(query));self.last=self.read(query)
    def read(self,query):
        key=query['commandId'];sdk=self.sdk
        if key in self.records:return deepcopy(self.records[key])
        state=self.states.get(key)
        if state is None:
            self.sequence+=1
            state=dict(first=self.clock(),sequence=self.sequence,calls=[],commands=dict.fromkeys(snapshot.ACTIONS),selected=dict.fromkeys(snapshot.ACTIONS),polls=0)
            self.states[key]=state
        calls,commands,selected=state['calls'],state['commands'],state['selected']
        def call(name):
            if commands[name] is None:
                command=dict(schemaVersion=1,commandId='ios-'+secrets.token_hex(16),action=snapshot.ACTIONS[name],runId=sdk.run)
                if name in ('ledgerBefore','document','ledgerAfter'):command['fixtureUrl']=self.fixture_url
                commands[name]=command
            command=commands[name];before=self.clock();module='ledger' if name.startswith('ledger') else name
            if module=='ledger' and self.document:original=self.page.ledger(command)
            elif module=='document' and self.document:
                if 'pending' not in state:
                    self.dom_issued+=1;self.callback_pending=True
                    state['entry']=self.page.event('dom-read-enter',dict(requestId=command['commandId']))
                    self.page.dom_sequence+=1
                    state['pending']=dict(iosWorldWebDOMNativeVersion=1,commandId=command['commandId'],runId=sdk.run,surface='world',instance='e'*32,
                        sequence=self.page.dom_sequence,processId=sdk.pid,capturedEpochMs=sdk.tick(),status='pending',source={})
                state['polls']+=1
                if state['polls']<=self.pending_polls:original=deepcopy(state['pending'])
                else:
                    original=self.page.document(command)
                    self.page.event('callback-enter',dict(entry=state['entry']['sequence'],result=dict(error=False)))
                    if not self.held_callback:
                        self.page.event('callback-return',dict(entry=state['entry']['sequence']));self.callback_pending=False
            else:sdk.send(module,command);original=json.loads(sdk.original(module))
            after=self.clock()
            calls.append(dict(ordinal=len(calls)+1,name=name,command=deepcopy(command),clockBefore=before,clockAfter=after,
                resultJSON=json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False)));selected[name]=len(calls)
            return original
        if not calls:call('ledgerBefore')
        pending=False
        actual_document=self.document
        if self.autodocument:
            from ios.adapters.world_web_trace import current_view
            actual_document=current_view(json.loads(calls[0]['resultJSON'])) is not None
        if actual_document:pending=call('document')['status']=='pending'
        if not pending:
            for name in ('world','work','geometry','keys','pointer','entities','ledgerAfter'):call(name)
        identity=dict(iosWorldWebSnapshotVersion=1,commandId=query['commandId'],runId=sdk.run,fixtureUrl=self.fixture_url,instance=self.instance,sequence=state['sequence'],
            processId=sdk.pid,clockDomain='native-main-ios-world-web-snapshot',clockBefore=deepcopy(state['first']),clockAfter=deepcopy(calls[-1]['clockAfter']))
        body=dict(iosWorldWebSnapshotBodyVersion=1,identity=identity,queries=deepcopy(commands),calls=deepcopy(calls),originals=deepcopy(selected))
        result=dict(identity,status='pending' if pending else 'ready',complete=True,payload=packed(body))
        if not pending:
            self.records[key]=deepcopy(result);self.order.append(key)
            while len(self.order)>2:
                old=self.records[self.order.pop(0)];old.update(status='unavailable',payload=None)
        return deepcopy(result)
    def raw(self):
        if self.last['status']=='pending':
            result=deepcopy(self.last);self.last=self.read(self.commands[-1]);return json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        return json.dumps(self.last,sort_keys=True,separators=(',',':'),ensure_ascii=False)
