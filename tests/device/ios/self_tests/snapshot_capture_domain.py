"""Connected normal-input/file domain; native/Script/SDK clocks modeled.

Capture work is created only by delivery of the actual normal capture input.
File reads/unlink and weak host worker lifetimes are real host operations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import nullcontext
from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from PIL import Image
from adapters.native_feature_observation import need
from feature_journeys.witness import Client
from ios.adapters import feature_observation,snapshot_work,snapshot_captures,snapshot_exports,snapshot_file_work,snapshot_owned_files,snapshot_inputs
from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime
from ios.adapters.snapshot_remove_owner import RECEIPT
from ios.self_tests.test_ios_snapshot_completion import SnapshotCompletionTests,BASE,RUN
from ios.self_tests.test_ios_snapshot_captures import Native as Captures
from ios.self_tests.test_ios_snapshot_exports import Native as Exports
from ios.self_tests.test_ios_snapshot_owned_files import Owned


class SnapshotCaptureDomain:
    def __init__(self,case):
        self.f=SnapshotCompletionTests();self.f.setUp();case.addCleanup(self.f.doCleanups)
        self.f.now=BASE+1;self.ctx=self.f.ctx;self.commands=[];self.raws={};self.good=True;self.captured=False
        self.ignored=False;self.lost=False;self.hold=False;self.cap=None;self.held_reads=False;self.held_removes=[];self.keep_remove=False
        self.work_sequence=0;self.root_sequence=0;self.capture_count=0;self.bad_bytes=False;self.phase_sequence=0
        self.native=Captures();self.native.tick=lambda:self.f.now;self.native.clock=self.clock
        self.exports=Exports();self.exports.tick=lambda:self.f.now;self.exports.clock=self.clock
        self.owned=Owned(self.ctx.root);self.owned.tick=lambda:self.f.now;self.owned.clock=self.clock
        self.f.f.jobs.clock=self.clock
        image=Image.new('RGB',(32,24))
        for y in range(24):
            for x in range(32):image.putpixel((x,y),(x*7%256,y*11%256,(x*13+y*17)%256))
        stream=BytesIO();image.save(stream,format='PNG');self.f.bytes=stream.getvalue()
        original_execute=self.ctx.files.execute
        def execute(session,operation,values):
            filename=values['remotePath'].rsplit('/',1)[-1]
            if filename in self.raws:return base64.b64encode(self.raws[filename].encode()).decode()
            return original_execute(session,operation,values)
        self.ctx.files.execute=execute
        original_observed=self.f.input_native.observed
        def observed():
            value=original_observed();value['controls'][0]['snapshotImageCount']=int(self.f.f.h.path.exists())
            return value
        self.f.input_native.observed=observed
        original_post=self.f.input_native.post
        def input_post(request,timeout):
            query=json.loads(request.data);result=original_post(request,timeout)
            if query['operation']=='edit' and query['input']['operation']=='activate':
                self.capture_count+=1
                if not self.ignored:self.capture_effect()
                if self.lost:raise OSError('Explicit modeled ordinary capture return lost after delivery')
            return result
        actual=patch('ios.adapters.normal_input.urlopen',input_post);actual.start();case.addCleanup(actual.stop)
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();case.addCleanup(actual.stop)
        domain=self
        class Runtime(IOSSnapshotCaptureRuntime):
            def _sources(self,selector):
                return dict(binding=domain.ctx.binding,check=lambda:domain.good,observer=domain.ctx.feature,
                    clock_source=domain.f.clock().native,native=domain.f.input_native.input())
            def existing_input_session(self,selector):return nullcontext()
        self.runtime=Runtime(SimpleNamespace(state_path=lambda _selector:self.ctx.root/'session.json',_candidate_guard=lambda:True,_binding=lambda:None))
    def epoch(self):return self.f.now
    def mono(self):return (self.f.now-BASE)/1000
    def sleep(self,delay):self.f.now+=round(delay*1000)
    def clock(self):return dict(epochMs=self.f.now,monotonicMs=self.f.now-BASE+1000)
    def capture_effect(self):
        self.captured=True;self.f.now=BASE+1000
        cap,identifier=self.native.begin(self.f.request);self.capture_instance=identifier
        self.f.now=BASE+1100;self.f.f.h.path.write_bytes(b'corrupt captured bytes' if self.bad_bytes else self.f.bytes);self.f.f.h.path.chmod(0o600)
        self.native.finish(cap,identifier)
        if self.hold:self.cap=cap
        self.f.now=BASE+1122
    def work_packet(self,q):
        before,after=self.f.work();value=after if self.captured else before;self.work_sequence+=1
        value.update(requestId=q['commandId'],sequence=self.work_sequence,clockBefore=self.clock(),clockAfter=self.clock())
        if self.work_sequence>1:
            row=value['source']['workers'][0];last=row['events'][-1]
            sequence=last['sequence']+self.work_sequence
            row['latest']=dict(sequence=sequence,callerSequence=sequence,capturedEpochMs=self.f.now,invokedEpochMs=self.f.now,
                event='snapshot',closure='',call=0,state=deepcopy(row['state']))
            value['source']['eventSequence']=sequence
        return value
    def post(self,request,timeout):
        q=json.loads(request.data);self.commands.append(deepcopy(q));action=q['action']
        if action=='snapshot-files':
            result=self.f.f.post(request,timeout);packet=self.ctx.files.value
            if q['operation']=='list':
                if not self.owned.prefixes:self.owned.prefixes=[dict(prefix=q['prefix'],query=deepcopy(q),sampleEpochMs=packet['sampleEpochMs'],initiallyEmpty=not packet['files'])]
                if packet['files'] and not self.owned.files:
                    row=deepcopy(packet['files'][0]);capture=self.native.captures[self.capture_instance][1]
                    identity=uuid.uuid4().hex
                    self.owned.files[identity]=dict(id=identity,prefix=q['prefix'],file=row,
                        capture=dict(pathObservedEpochMs=BASE+1100,phase='complete',fileName=row['name'],captureInstance=self.capture_instance,
                            requestId=self.f.request,bornEpochMs=capture['bornEpochMs'],terminal='complete',nativeDrained=not self.hold),
                        manifestQuery=deepcopy(q),observedEpochMs=packet['sampleEpochMs'],removeCommandId='')
            if not self.held_reads:self.f.f.callbacks.clear()
            return result
        if action=='feature-script-roots-observe':
            self.root_sequence+=1
            value=dict(scriptRootsVersion=1,commandId=q['commandId'],instance='d'*32,sequence=self.root_sequence,processId=42,
                requestedEpochMs=self.f.now,capturedEpochMs=self.f.now,source=dict(defaultScriptsUrl='qrc:/scripts/'))
            filename='feature-script-roots.json'
        elif action==snapshot_work.ACTION:value=self.work_packet(q);filename=snapshot_work.FILE
        elif action==snapshot_captures.ACTION:
            value=self.native.read();value['requestId']=q['commandId'];filename=snapshot_captures.FILE
        elif action==snapshot_exports.ACTION:
            self.exports.send(q);value=self.exports.packet;filename=snapshot_exports.FILE
        elif action==snapshot_file_work.ACTION:value=self.f.f.jobs.read(q);filename=snapshot_file_work.FILE
        elif action==snapshot_owned_files.ACTION:value=self.owned.read(q);filename=snapshot_owned_files.FILE
        elif action==snapshot_inputs.ACTION:
            self.f.input_native.send(q);value=self.f.input_native.packet;self.f.now=max(self.f.now,value['clockAfter']['epochMs']);filename=snapshot_inputs.FILE
        else:
            need(action==snapshot_owned_files.REMOVE);file=self.owned.files[q['fileId']]
            generated,body=self.owned.queued(file);weak,row=self.owned.jobs.pop(generated['commandId'])
            row['query']=deepcopy(q);file['removeCommandId']=q['commandId'];self.owned.jobs[q['commandId']]=(weak,row)
            body()
            if self.keep_remove:self.held_removes.append(body)
            value=dict(iosSnapshotFileRemoveReceiptVersion=1,requestId=q['commandId'],accepted=True);filename=RECEIPT
        self.raws[filename]=json.dumps(value,indent=1)+'\n';self.ctx.files.echo=json.dumps(q).encode();return self.ctx.files
    def client(self):
        domain=self
        class Phase(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                need(path=='/runs/'+RUN+'/phase');domain.phase_sequence+=1
                return dict(fixturePhaseVersion=1,instance='e'*32,sequence=domain.phase_sequence,requestId=phase_nonce,runId=RUN,area='snapshots',
                    capturedEpochMs=domain.epoch(),active=True,createdEpochMs=BASE-100,retiredEpochMs=None,
                    activations=[dict(sequence=1,ticket='f'*32,activatedEpochMs=BASE-90,stimulus=dict(verb='capture',inputs=dict(mode='still',format='png')))])
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.mono,sleep=self.sleep)
    def owner(self):
        # The production runtime, actual OS lock and all typed child factories
        # execute normally. Only its SDK/native/fixture boundaries are models.
        context=self.runtime.capture_owner('primary',RUN,self.client())
        return ClockedOwner(context,self)


class ClockedOwner:
    def __init__(self,context,domain):self.context,self.domain=context,domain
    def __enter__(self):
        owner=self.context.__enter__();owner.epoch_ms=self.domain.epoch;owner.monotonic=self.domain.mono;owner.sleep=self.domain.sleep
        owner.phase.epoch_ms=self.domain.epoch;owner.phase.monotonic=self.domain.mono
        self.owner=owner;return owner
    def __exit__(self,*args):return self.context.__exit__(*args)
