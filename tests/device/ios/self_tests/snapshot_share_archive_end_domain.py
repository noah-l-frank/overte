"""Existing SDK and repository process source over fake OS, real Node sockets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import json
import subprocess
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.snapshot_share_archive_end_context import SnapshotShareArchiveEndContext
from ios.self_tests import snapshot_share_query_domain
from ios.self_tests.snapshot_share_query_domain import ShareQueryDomain,NodeQuerySource,RUN
from ios.self_tests.snapshot_share_admission_domain import BUNDLE
from ios.self_tests.snapshot_share_domain import REAL_TIME,REAL_MONOTONIC
from ios.self_tests import test_ios_process_plugin as process_fixture
from ios.self_tests.test_ios_snapshot_share_process import PLUGIN
from ios.self_tests.snapshot_share_source_retirement_domain import SourceRetirementArchive,SourceRetirementFlow
from ios.self_tests import snapshot_share_domain
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain,SYSTEM_UI,REAL_SLEEP
from ios.adapters import snapshot_share_runtime


BRIDGE=r'''
const lines=require('node:readline').createInterface({input:process.stdin,crlfDelay:Infinity});
const first=native(4,85),driver=first.driver;first.socket.destroy();let parent='live',extension='absent',held=false;
function prepare(role){
 const modes=role==='parent'?{live:[4,85,true],background:[3,85,true],absent:[0,0,false],held:[0,0,true],replacement:[4,86,true]}:
  {live:[4,84,true],absent:[0,0,false],held:[0,0,true],replacement:[4,85,true]};
 const [appState,pid,running]=modes[role==='parent'?parent:extension],next=native(appState,pid);
 next.dvt.deviceInfo={async isRunningPid(){return running;}};
 if(held)next.service.close=async()=>{};
 driver.remoteXPCFacade=next.driver.remoteXPCFacade;driver.mobileQueryAppState=next.driver.mobileQueryAppState;
 return next;
}
(async()=>{for await(const line of lines){try{const q=JSON.parse(line);let value;
 if(q.op==='info')value=source.sourceInfo(driver,bundle,sdk);
 else if(q.op==='mode'){extension=q.value;value=true;}
 else if(q.op==='parent-mode'){parent=q.value;value=true;}
 else if(q.op==='parent-observe'){prepare('parent');value=await source.observe(driver,bundle);}
 else if(q.op==='parent-retired'){prepare('parent');value=await source.observeRetired(driver,bundle,q.nonce);}
 else if(q.op==='query'){prepare('extension');value=await(q.retired?source.observeRetiredSnapshotShareExtension:source.observeSnapshotShareExtension)(driver,bundle,q.nonce);}
 else if(q.op==='original')value=source.snapshotShareExtensionOriginal(driver,bundle,q.nonce);
 else if(q.op==='stop-parent'){parent='absent';value=true;}
 else if(q.op==='hold-close'){held=true;value=true;}
 else if(q.op==='sdk-delete'){value=await source.cleanup(async()=>true,driver);}
 else throw Error('unknown model operation');
 process.stdout.write(JSON.stringify({ok:true,value})+'\n');
 }catch(_){process.stdout.write(JSON.stringify({ok:false,error:'Declared source unavailable'})+'\n');}}})().catch(()=>{process.exitCode=1;});
'''


class ArchiveEndNodeSource(NodeQuerySource):
    def __init__(self,case):
        boot=process_fixture.BOOT.replace("assert.equal(bundle,'org.example.overte')","assert(['org.example.overte','org.example.overte.receiver'].includes(bundle))").replace('org.example.overte',BUNDLE)
        self.process=subprocess.Popen(['node','-e',boot+'\n'+BRIDGE,str(PLUGIN)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        case.addCleanup(self.close)


class ArchiveEndSDK:
    def setup_end_sdk(self):
        self.sdk_alive=True;self.stop_calls=0;self.delete_calls=0;self.ignore_stop=False;self.lose_stop=False;self.ignore_delete=False;self.lose_delete=False
        self.archive_stopped=False;self.parent_override=None
    def execute(self,session,operation,query):
        if not self.sdk_alive:raise WebDriverRequestError(404)
        if operation=='mobile: overteProcessInfo':
            need(query==dict(bundleId=BUNDLE))
            if hasattr(self,'flow') and not self.archive_stopped:self.node.call('parent-mode',value=self.parent_override or ('live' if self.foreground else 'background'))
            return self.node.call('parent-observe')
        if operation=='mobile: overteRetiredProcessInfo':need(query['bundleId']==BUNDLE);return self.node.call('parent-retired',nonce=query['commandId'])
        if operation=='mobile: terminateApp':
            need(query==dict(bundleId=BUNDLE));self.stop_calls+=1
            if not self.ignore_stop:self.node.call('stop-parent');self.archive_stopped=True;self.foreground=False
            if self.lose_stop:self.lose_stop=False;raise NativeUIError('Declared lost Archive stop return')
            return True
        return super().execute(session,operation,query)
    def call(self,method,path,body=None):
        if path=='/session/'+self.scope['sessionId']:
            if not self.sdk_alive:raise WebDriverRequestError(404)
            if method=='DELETE':
                self.delete_calls+=1
                if not self.ignore_delete:self.node.call('sdk-delete');self.sdk_alive=False
                if self.lose_delete:self.lose_delete=False;raise WebDriverRequestError(500)
                return None
        return super().call(method,path,body)


class ArchiveEndDomain(ArchiveEndSDK,ShareQueryDomain):
    def __init__(self,case):
        self.setup_end_sdk()
        with patch.object(snapshot_share_query_domain,'NodeQuerySource',ArchiveEndNodeSource):super().__init__(case,archive_pid=85,prepare_metadata=False)
        self.foreground=True
    @contextmanager
    def end_context(self,snapshot=None):
        with self.source_lock.held():
            yield SnapshotShareArchiveEndContext(self,self.session,self.target,self.binding,self.ipa,self.admission_store,self.source_lock,RUN,self.fixture_url,
                epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC,snapshot=snapshot)


class SourceArchiveEndArchive(ArchiveEndSDK,SourceRetirementArchive):
    def __init__(self,case,flow):
        self.setup_end_sdk()
        with patch.object(snapshot_share_query_domain,'NodeQuerySource',ArchiveEndNodeSource):super().__init__(case,flow)


class SourceArchiveEndFlow(SourceRetirementFlow):
    def __init__(self,case):
        with patch.object(snapshot_share_domain,'ShareArchiveDomain',SourceArchiveEndArchive):SnapshotShareDomain.__init__(self,case)
    def archive_config(self):
        return dict(client=self.archive,sessionStore=self.archive.session,target=self.archive.target,binding=self.archive.binding,
            artifactPath=self.archive.ipa,admissionStore=self.archive.admission_store)
    @contextmanager
    def end_owner(self):
        def primary(runtime,selector,binding):
            need(runtime is self.runtime and selector=='primary' and binding==self.primary.binding);return self.primary
        with patch.object(snapshot_share_runtime,'PhotosClientContext',primary):
            with self.runtime.archive_end_owner('primary',RUN,self.client(),self.archive_config(),SYSTEM_UI,
                    epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC,sleep=REAL_SLEEP,combined=getattr(self,'combined',False)) as owner:yield owner
