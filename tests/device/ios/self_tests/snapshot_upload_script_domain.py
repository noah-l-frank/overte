"""One actual Script dispatch before native upload creation, over private stdio.

Qt XHR/TLS remain declared edges; actual onMessage/isDomainOpen/request.js and
the Account/domain-policy/HTTP serializers execute without a listener/device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import selectors
import subprocess
from urllib.parse import urlsplit
from adapters.native_feature_observation import need
from feature_journeys.snapshot_concurrency import SnapshotConcurrency
from feature_journeys.snapshot_domain_client import SnapshotDomainClient
from ios.self_tests.snapshot_upload_backend_domain import SnapshotUploadBackendFlow,RUN,REAL_TIME,REAL_MONOTONIC
from self_tests.snapshot_domain_fixture import PolicyFixture,DOMAIN


class OriginalUploadScript:
    def __init__(self,case,backend):self.case,self.backend=case,backend;self.events=[]
    def dispatch(self,path,*,domain='{'+DOMAIN+'}',replace_review=False,on_returned=None):
        root=Path(__file__).resolve().parents[4];driver=Path(__file__).with_name('snapshot_upload_preflight.js')
        process=subprocess.Popen(['node',str(driver),str(root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        buffer=b''
        try:
            def send(value):process.stdin.write((json.dumps(value)+'\n').encode());process.stdin.flush()
            def receive():
                nonlocal buffer
                while b'\n' not in buffer:
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout,selectors.EVENT_READ);need(bool(selector.select(5)))
                    raw=os.read(process.stdout.fileno(),4096);need(bool(raw));buffer+=raw;need(len(buffer)<=65536)
                raw,buffer=buffer.split(b'\n',1);value=json.loads(raw);need(value.get('event') in ('http','returned','result'));self.events.append(value);return value
            logged_in=self.backend.provider.resolve(self.backend._authorization)==RUN
            send(dict(operation='start',origin='https://controlled.invalid',loggedIn=logged_in,domain=domain,href='hifi://controlled.invalid/snapshot-fixture',path=str(path)))
            value=receive();http=None
            if value['event']=='http':http=value;value=receive()
            need(value['event']=='returned')
            if on_returned is not None:on_returned(value)
            if http is not None:
                parsed=urlsplit(http['uri']);need(http['method']=='GET' and http['body'] is None and parsed.scheme=='https' and parsed.netloc=='controlled.invalid' and parsed.path=='/api/v1/user_stories')
                status,body=self.backend.call('GET',parsed.path+'?'+parsed.query)
                send(dict(operation='response',status=status,body=body.decode('utf8'),replaceReview=replace_review))
            value=receive()
            need(value['event']=='result');send(dict(operation='stop'));_out,error=process.communicate(timeout=5);need(process.returncode==0 and not _out and not error);return value
        finally:
            if process.poll() is None:process.terminate()
            try:process.communicate(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=5)


class SnapshotUploadScriptFlow(SnapshotUploadBackendFlow):
    def __init__(self,case):
        super().__init__(case);self.policy=PolicyFixture(case)
        epoch_ms=lambda:int(REAL_TIME()*1000)
        self.policy.reader.epoch_ms=epoch_ms;self.policy.reader.monotonic=REAL_MONOTONIC
        domain_client=SnapshotDomainClient(self.policy.config,epoch_ms=epoch_ms,monotonic=REAL_MONOTONIC)
        self.backend.provider.concurrency=SnapshotConcurrency(self.backend.provider,domain_client)
        self.script=OriginalUploadScript(case,self.backend);self.script_results=[];self.native_birth_preflight=[]
    def dispatch_upload(self):
        # The normal UI event has arrived, but no uploader/body FD exists yet.
        self.call_sequence+=1;call=self.call_sequence;self.event('entry','onMessage',call)
        def returned(actual):
            need(actual['pendingUploads']==0 and self.upload is None)
            self.event('returned','onMessage',call);self.event('finally','onMessage',call)
        value=self.script.dispatch(self.f.f.h.path,on_returned=returned);self.script_results.append(value)
        for shared in value['shares']:
            need(shared==dict(path=str(self.f.f.h.path),href='hifi://controlled.invalid/snapshot-fixture'))
            rows=self.backend.provider.concurrency.snapshot(RUN)['requests'];need(rows and rows[-1]['written'] and rows[-1]['left'] is not None)
            self.native_birth_preflight.append(rows[-1]['requestId']);self.script_state['pendingUploads']+=1;self.upload=self.new_upload()
        if self.upload is not None:
            if self.auto_complete:self.upload.complete(close_fd=not self.hold_fd);self.script_completion()
            else:self.upload.request('upload')
