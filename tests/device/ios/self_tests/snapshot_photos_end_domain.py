"""Declared Photos OS/SDK with actual repository Node process-source originals.

The SDK remains modeled; this starts no device service or Appium server. The
existing normal Save remains the only cause of library bytes. End observations
never stop a process or delete an SDK by themselves.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import subprocess
from unittest.mock import patch
from adapters.native_feature_observation import exact,need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.snapshot_combined_journey import SnapshotCombinedJourney
from ios.adapters.snapshot_combined_photos_journey import SnapshotCombinedPhotosJourney
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive
from ios.adapters.snapshot_photos_end_owner import SnapshotPhotosEndOwner
from ios.adapters.snapshot_photos_end_originals import SnapshotPhotosEndOriginals
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.self_tests import snapshot_photos_domain
from ios.self_tests.snapshot_photos_domain import PhotosCompanionDomain
from ios.self_tests.snapshot_companion_domain import BUNDLE,RUN
from ios.self_tests.snapshot_combined_photos_return_domain import CombinedPhotosReturnFlow
from ios.self_tests.snapshot_combined_upload_return_domain import CombinedUploadPageDomain
from ios.self_tests import snapshot_preflight_original_domain
from feature_journeys.snapshot_domain_client import SnapshotDomainClient
from ios.self_tests.snapshot_share_query_domain import NodeQuerySource
from ios.self_tests.snapshot_share_domain import REAL_TIME,REAL_MONOTONIC,REAL_SLEEP,SYSTEM_UI
from ios.self_tests import test_ios_process_plugin as process_fixture
from ios.self_tests import test_ios_snapshot_page_return as return_test


BRIDGE=r'''
const lines=require('node:readline').createInterface({input:process.stdin,crlfDelay:Infinity});
const first=native(4,84),driver=first.driver;first.socket.destroy();let mode='live';
function prepare(){
 const modes={live:[4,84,true],background:[3,84,true],absent:[0,0,false],held:[0,0,true],replacement:[4,86,true]};
 const [appState,pid,running]=modes[mode],next=native(appState,pid);
 next.dvt.deviceInfo={async isRunningPid(){return running;}};
 driver.remoteXPCFacade=next.driver.remoteXPCFacade;driver.mobileQueryAppState=next.driver.mobileQueryAppState;return next;
}
(async()=>{for await(const line of lines){try{const q=JSON.parse(line);let value;
 if(q.op==='info')value=source.sourceInfo(driver,bundle,sdk);
 else if(q.op==='mode'){if(!['live','background','absent','held','replacement'].includes(q.value))throw Error('unknown model mode');mode=q.value;value=true;}
 else if(q.op==='observe'){prepare();value=await source.observe(driver,bundle);}
 else if(q.op==='retired'){prepare();value=await source.observeRetired(driver,bundle,q.nonce);}
 else if(q.op==='stop'){mode='absent';value=true;}
 else if(q.op==='sdk-delete')value=await source.cleanup(async()=>true,driver);
 else throw Error('unknown model operation');
 process.stdout.write(JSON.stringify({ok:true,value})+'\n');
 }catch(_){process.stdout.write(JSON.stringify({ok:false,error:'Declared source unavailable'})+'\n');}}})().catch(()=>{process.exitCode=1;});
'''


class PhotosEndNodeSource(NodeQuerySource):
    def __init__(self,case):
        program=process_fixture.BOOT.replace('org.example.overte',BUNDLE)+'\n'+BRIDGE
        self.process=subprocess.Popen(['node','-e',program,str(process_fixture.SOURCE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        case.addCleanup(self.close)


class PhotosEndCompanionDomain(PhotosCompanionDomain):
    def __init__(self,case,domain):
        super().__init__(case,domain);self.end_node=PhotosEndNodeSource(case)
        self.sdk_alive=True;self.stopped=False;self.stop_calls=self.delete_calls=0
        self.ignore_stop=self.lose_stop=self.ignore_delete=self.lose_delete=False;self.parent_mode=None
    def execute(self,session,operation,query):
        if not self.sdk_alive:raise WebDriverRequestError(404)
        if operation in ('mobile: overteProcessSourceInfo','mobile: overteProcessInfo','mobile: overteRetiredProcessInfo','mobile: terminateApp'):
            self.domain.advance();self.sdk.append((session,operation,deepcopy(query)));need(session==self.scope['sessionId'] and query['bundleId']==BUNDLE)
            if operation=='mobile: overteProcessSourceInfo':return self.end_node.call('info')
            if operation=='mobile: overteProcessInfo':
                if not self.stopped:self.end_node.call('mode',value=self.parent_mode or ('live' if self.foreground else 'background'))
                return self.end_node.call('observe')
            if operation=='mobile: overteRetiredProcessInfo':return self.end_node.call('retired',nonce=query['commandId'])
            self.stop_calls+=1
            if not self.ignore_stop:self.end_node.call('stop');self.stopped=True;self.foreground=False
            if self.lose_stop:self.lose_stop=False;raise NativeUIError('Declared lost Photos Stop return after delivery')
            return True
        return super().execute(session,operation,query)
    def call(self,method,path,body=None):
        if path=='/session/'+self.scope['sessionId']:
            if not self.sdk_alive:self.requests.append((method,path,deepcopy(body)));raise WebDriverRequestError(404)
            if method=='DELETE':
                self.requests.append((method,path,deepcopy(body)));self.delete_calls+=1
                if not self.ignore_delete:self.end_node.call('sdk-delete');self.sdk_alive=False
                if self.lose_delete:self.lose_delete=False;raise WebDriverRequestError(500)
                return None
        return super().call(method,path,body)


def selection_pin(path):
    return list(IOSSnapshotCompanionRuntime.pin_artifact(SimpleNamespace(artifact_path=Path(path))))


def selected_public_policy(ticket):
    """Independent controller selection; never recover it from a result graph."""
    exact(ticket,{'path','stat','sha256','valueSha256'})
    path=Path(ticket['path']);need(selection_pin(path)==ticket['stat'])
    raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==ticket['sha256'])
    value=PrivateFeatureState(path).read();exact(value,{'selectionKind','runId','configuration'})
    need(value['selectionKind']=='snapshot-photos-public-domain-selection' and value['runId']==RUN
        and digest(value)==ticket['valueSha256'] and selection_pin(path)==ticket['stat'])
    return deepcopy(value['configuration'])


class PhotosEndReturnFlow(CombinedPhotosReturnFlow):
    def prepare_main(self,case):
        chosen=[];base=snapshot_preflight_original_domain.PolicyFixture
        class SelectedPolicy(base):
            def __init__(policy,selected_case):
                super().__init__(selected_case)
                folder=tempfile.TemporaryDirectory(prefix='snapshot-photos-selection-');selected_case.addCleanup(folder.cleanup)
                root=Path(folder.name);root.chmod(0o700);path=root/'selected-domain-policy.json'
                value=dict(selectionKind='snapshot-photos-public-domain-selection',runId=RUN,
                    configuration=SnapshotDomainClient(policy.config).public())
                raw=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
                descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                chosen.append(dict(path=str(path),stat=selection_pin(path),sha256=hashlib.sha256(raw).hexdigest(),valueSha256=digest(value)))
        prepare=CombinedUploadPageDomain.prepare_png
        def before_first_page_delivery(page):
            need(len(chosen)==1 and not page.clicks and not page.capture.commands
                and page.capture.capture_count==0 and page.capture.upload_count==0)
            self.public_selection=deepcopy(chosen[0]);selected_public_policy(self.public_selection)
            self.public_selection_before_first_page_delivery=True
            return prepare(page)
        with patch.object(snapshot_preflight_original_domain,'PolicyFixture',SelectedPolicy),patch.object(CombinedUploadPageDomain,'prepare_png',before_first_page_delivery):
            result=super().prepare_main(case)
        need(self.public_selection_before_first_page_delivery and same(result[0].domain_policy,selected_public_policy(self.public_selection)))
        return result
    def prepare_destinations(self,case):
        with patch.object(snapshot_photos_domain,'PhotosCompanionDomain',PhotosEndCompanionDomain):super().prepare_destinations(case)


class PhotosEndFlow:
    def __init__(self,case):
        with patch.object(return_test,'PageReturnFlow',PhotosEndReturnFlow):self.domain,self.host=return_test.SnapshotPageReturnOwnerTests.prepared(case)
        with self.domain.return_owner() as returned:returned.restore()
        self.returned=returned
        self.public_selection=deepcopy(self.domain.public_selection)
    def originals(self):
        d=self.domain
        def helper(value,pid,admission):
            binding=dict(deepcopy(value.scope),processIdentity=str(pid))
            need(binding['artifactSha256']==hashlib.sha256(value.ipa.read_bytes()).hexdigest())
            return dict(root=str(value.root),binding=binding,artifactPath=str(value.ipa),sessionPath=str(value.session.path),
                admissionPath=str(value.root/admission),target=deepcopy(value.target))
        return SnapshotPhotosEndOriginals(dict(root=str(d.main.ctx.root),binding=deepcopy(d.main.ctx.binding)),
            helper(d.photos.helper,84,'ios-snapshot-companion-owner.json'),helper(d.archive,85,'ios-snapshot-share-code-owner.json'),
            run=RUN,fixture_url='https://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/',primary_bundle='org.example.client',system_ui=SYSTEM_UI,
            domain_policy=selected_public_policy(self.public_selection),reuse_originals=True)
    @contextmanager
    def journey(self):
        factory=self.originals();locks=factory.locks
        with locks['main'].held(),locks['archive'].held(),locks['photos'].held():
            with factory.read_journey() as historical:journey=historical
            # The passive area has closed, while the SAME existing lock
            # instances remain held. Live End writes/SDK calls happen later.
            self.last_read_counts=deepcopy(factory.last_read_counts)
            selected_public_policy(self.public_selection)
            yield journey
            selected_public_policy(self.public_selection)
    def helper(self):
        photo=self.domain.photos;helper=photo.helper
        return dict(client=helper,sessionStore=helper.session,target=helper.target,binding=photo.helper_binding,
            artifactPath=helper.ipa,admissionStore=photo.admission_store)
    @contextmanager
    def owner(self):
        with self.journey() as journey:
            yield SnapshotPhotosEndOwner(journey,self.helper(),epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC,sleep=REAL_SLEEP)
