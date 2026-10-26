"""Real repository Node source, sockets, clocks and files; DVT/OS are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import time
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_archive_runtime import IOSSnapshotShareArchiveRuntime
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.adapters.snapshot_share_query_owner import SnapshotShareQueryOwner
from ios.self_tests import test_ios_snapshot_share_process as process_fixture
from ios.self_tests.snapshot_share_admission_domain import ShareAdmissionDomain,BUNDLE
from ios.self_tests.snapshot_companion_domain import RUN
from ios.self_tests.test_ios_snapshot_share_original import received,imported


BRIDGE=r'''
const lines=require('node:readline').createInterface({input:process.stdin,crlfDelay:Infinity});
const first=live(),driver=first.driver;first.socket.destroy();let mode='live',services=0,queries=0,lookups=0;
function prepare(){
 const states={live:[4,84,true],absent:[0,0,false],held:[0,0,true],replacement:[4,85,true]};
 const current=lease(driver,...states[mode]),actual=driver.remoteXPCFacade.requireService;
 driver.remoteXPCFacade.requireService=async(...args)=>{services++;return actual(...args);};return current;
}
(async()=>{
 for await(const line of lines){
  try{
   const request=JSON.parse(line);let value;
   if(request.op==='mode'){if(!['live','absent','held','replacement'].includes(request.value))throw Error('invalid model mode');mode=request.value;value=true;}
   else if(request.op==='info')value=source.sourceInfo(driver,bundle,sdk);
   else if(request.op==='query'){queries++;prepare();value=await (request.retired?source.observeRetiredSnapshotShareExtension:source.observeSnapshotShareExtension)(driver,bundle,request.nonce);}
   else if(request.op==='original'){lookups++;value=source.snapshotShareExtensionOriginal(driver,bundle,request.nonce);}
   else if(request.op==='stats')value={services,queries,lookups};
   else throw Error('invalid model operation');
   process.stdout.write(JSON.stringify({ok:true,value})+'\n');
  }catch(_){process.stdout.write(JSON.stringify({ok:false,error:'Declared source unavailable'})+'\n');}
 }
})().catch(()=>{process.exitCode=1;});
'''


class NodeQuerySource:
    def __init__(self,case):
        program=process_fixture.BOOT.replace('org.example.overte',BUNDLE)+'\n'+BRIDGE
        self.process=subprocess.Popen(['node','-e',program,str(process_fixture.PLUGIN)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        case.addCleanup(self.close)
    def call(self,op,**values):
        self.process.stdin.write(json.dumps(dict(op=op,**values))+'\n');self.process.stdin.flush()
        row=json.loads(self.process.stdout.readline())
        if not row['ok']:raise NativeUIError('Original repository source is unavailable')
        return row['value']
    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=3)
        self.process.stdout.close();self.process.stderr.close()


class ShareQueryDomain(ShareAdmissionDomain):
    def __init__(self,case,*,archive_pid=42,physical_selector=None,admission_ticket='d'*32,prepare_metadata=True):
        super().__init__(case);self.pid=archive_pid
        if physical_selector is not None:
            self.target['capabilities']={'appium:udid':physical_selector};self.scope['targetFingerprint']=digest(self.target)
            previous=self.session.read();self.session.write(dict(previous,targetFingerprint=self.scope['targetFingerprint']),previous)
        self.node=NodeQuerySource(case);self.source=self.node.call('info')['instance'];self.foreground=True
        self.lose=False;self.ignore=False;self.query_deliveries=0
        with self.owner() as owner:
            owner.admit(admission_ticket);self.admission_store,self.source_lock,self.binding,self.fixture_url=owner.store,owner.lock,owner.binding,owner.fixture_url
        self.metadata=None
        if prepare_metadata:
            _native,_operation,_exports,record,raw=received();record.update(processId=84,receiverBundleId=BUNDLE+'.receiver')
            _transfer,self.metadata,_finished=imported(record,raw)
            output=self.documents/('snapshot-share-'+RUN);output.mkdir(mode=0o700);(output/'original-extension.json').write_bytes(self.metadata)
        self.foreground=False
    def execute(self,session,operation,query):
        if operation=='mobile: overteProcessSourceInfo':
            self.sdk.append((session,operation,deepcopy(query)));value=self.node.call('info');value['instance']=self.source;return value
        if operation in ('mobile: overteSnapshotShareExtensionInfo','mobile: overteRetiredSnapshotShareExtensionInfo'):
            self.sdk.append((session,operation,deepcopy(query)));self.query_deliveries+=1
            if self.ignore:raise NativeUIError('Declared query request not delivered')
            value=self.node.call('query',nonce=query['commandId'],retired=operation=='mobile: overteRetiredSnapshotShareExtensionInfo')
            if self.lose:self.lose=False;raise NativeUIError('Declared lost query return after actual source completion')
            return value
        if operation=='mobile: overteSnapshotShareExtensionOriginal':
            self.sdk.append((session,operation,deepcopy(query)));return self.node.call('original',nonce=query['commandId'])
        if operation=='mobile: pullFile' and query['remotePath'].endswith('/original-extension.json'):
            self.sdk.append((session,operation,deepcopy(query)))
            return base64.b64encode((self.documents/('snapshot-share-'+RUN)/'original-extension.json').read_bytes()).decode()
        value=super().execute(session,operation,query)
        if operation=='mobile: overteProcessInfo':value['foreground']=self.foreground
        return value
    @contextmanager
    def queries(self):
        with self.source_lock.held():
            ctx=SnapshotShareArchiveContext(self,self.session,self.target,self.binding,self.ipa,self.admission_store,self.source_lock,RUN,self.fixture_url,
                epoch_ms=self.epoch,monotonic=self.mono,sleep=lambda _:None)
            yield SnapshotShareQueryOwner(ctx,self.source_lock)
    def archive(self):
        return IOSSnapshotShareArchiveRuntime(self,self.session,self.target,self.scope,self.ipa,lambda:True,
            admission_store=self.admission_store,lock=self.source_lock,run=RUN,fixture_url=self.fixture_url,
            epoch_ms=self.epoch,monotonic=self.mono,sleep=lambda _:None)
    def bind(self,owner):
        self.foreground=True
        try:return owner.bind_receiver(self.archive())
        finally:self.foreground=False
