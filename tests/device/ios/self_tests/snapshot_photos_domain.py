"""Declared Qt/PhotoKit/OS producers with real files, weak refs and SDK codecs.

No device, service, compiler or native framework runs. Neither observations nor
requested expected values generate the library bytes: a delivered Save reads
the actual main-app file into the independent modeled PhotoKit library.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import uuid
import weakref
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError,W3C_ELEMENT
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters import normal_input,snapshot_companion_source
from ios.adapters.installed_code import SDK
from ios.adapters.snapshot_photos_context import PhotosClientContext,PhotosCompanionContext
from ios.adapters.snapshot_photos_owner import IOSSnapshotPhotosOwner
from ios.adapters.snapshot_photos_runtime import IOSSnapshotPhotosRuntime
from ios.self_tests.snapshot_capture_domain import SnapshotCaptureDomain,RUN,BASE
from ios.self_tests.snapshot_companion_domain import SnapshotCompanionDomain,BUNDLE
from ios.self_tests.test_ios_normal_input import Boundary


def revision(path):
    value=path.stat();fields=(value.st_dev,value.st_ino,value.st_mode,value.st_nlink,value.st_uid,value.st_gid,value.st_size,
        value.st_mtime_ns//10**9,value.st_mtime_ns%10**9,value.st_ctime_ns//10**9,value.st_ctime_ns%10**9)
    return hashlib.sha256(':'.join(map(str,fields)).encode()).hexdigest()


class Callback:
    def __init__(self,domain,kind):self.domain,self.kind=domain,kind
    def __del__(self):self.domain.event('weak-expired' if self.kind=='read' else 'delete-weak-expired')


class PhotosCompanionDomain(SnapshotCompanionDomain):
    def __init__(self,case,domain):
        self.domain=domain;super().__init__(case);self.pid=84;self.fields={};self.authorization=3;self.job=None
        self.query_nonces=set();self.packet_chunks={};self.retirement=None;self.retire_issued=False
        self.read_ref=self.delete_ref=None;self.held_reads=[];self.held_deletes=[];self.hold_read=False;self.hold_delete=False
        self.data_changed=False;self.ignore_controls=set();self.lost_controls=set();self.foreground=False;self.replace_on_chunk=False
        self.file_replaced=False;self.read_count=self.delete_count=self.retire_count=0;self.deleted=False
        self.target['capabilities']={'appium:udid':'HOST-PHYSICAL-DEVICE-MODEL','appium:platformVersion':'99.1'}
        self.scope['targetFingerprint']=digest(self.target);old=self.session.read()
        self.session.write(dict(old,targetFingerprint=self.scope['targetFingerprint']),old)
    def epoch(self):return self.domain.main.epoch()
    def mono(self):return self.domain.main.mono()
    def clock(self,offset=0):return dict(epochMs=int(self.epoch())+offset,monotonicMs=900000+int(self.epoch())-BASE+offset)
    def event(self,kind,detail=None):
        self.domain.advance();self.job['events'].append(dict(sequence=len(self.job['events'])+1,kind=kind,clock=self.clock(),detail={} if detail is None else detail));self.persist()
    @property
    def run_root(self):return self.documents/('snapshot-photos-'+RUN)
    def persist(self):
        if self.run_root.exists():
            path=self.run_root/'photos-original.json';path.write_text(json.dumps(self.job,ensure_ascii=True,indent=1));path.chmod(0o600)
    def observe(self,action):
        value=super().observe(action)
        if action=='photos':value.update(readWriteAuthorizationBefore=self.authorization,readWriteAuthorizationAfter=self.authorization)
        return value
    def read_original(self):
        if self.job is not None:return
        self.read_count+=1;run=self.fields['snapshot.destination.run'];asset=self.fields['snapshot.destination.asset'];name=self.fields['snapshot.destination.basename']
        need(run==RUN and self.authorization==3);self.run_root.mkdir(mode=0o700)
        self.job=dict(iosSnapshotDestinationVersion=2,runId=run,kind='photos-resource',basename=name,photosIdentifier=asset,
            instance='6'*32,processId=self.pid,clockDomain='native-companion-photos',createdClock=self.clock(),events=[],queries=[],
            phase='issued',resource=None,byteCount=0,sha256='',artifact='original.bytes',artifactRevision=None,deletion=None)
        self.event('read-issued');actual=self.domain.library.get(asset)
        if actual is None:self.job['phase']='failed';self.event('read-failed');return
        self.job['resource']=dict(originalFilename=actual['name'],type=1);self.event('resource-selected')
        operation=Callback(self,'read');self.read_ref=weakref.ref(operation)
        self.event('callback-enter',dict(name='data'));raw=actual['raw'];path=self.run_root/'original.bytes'
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
        self.job['byteCount']=path.stat().st_size;self.event('callback-left',dict(name='data'))
        self.event('callback-enter',dict(name='completion'));self.job.update(phase='complete',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),artifactRevision=revision(path))
        self.event('read-completed');self.event('callback-left',dict(name='completion'))
        if self.hold_read:self.held_reads.append(operation)
    def inspect(self):
        need(self.job is not None);nonce=self.fields['snapshot.destination.query'];need(nonce not in self.query_nonces);self.query_nonces.add(nonce)
        self.job['queries'].append(dict(requestId=nonce,clock=self.clock(),operationAlive=self.read_ref is not None and self.read_ref() is not None,
            deletionAlive=self.delete_ref is not None and self.delete_ref() is not None,authorization=self.authorization,
            assetPresent=self.job['photosIdentifier'] in self.domain.library if self.authorization==3 else None));self.persist()
    def delete(self):
        need(self.job is not None and self.job['deletion'] is None and self.authorization==3)
        self.delete_count+=1;self.job['deletion']=dict(phase='issued');self.event('delete-issued')
        operation=Callback(self,'delete');self.delete_ref=weakref.ref(operation)
        self.event('delete-changes-enter');self.domain.library.pop(self.job['photosIdentifier']);self.deleted=True;self.event('delete-changes-left')
        self.event('delete-completion-enter');self.job['deletion']=dict(phase='complete');self.event('delete-completed',dict(success=True,hasError=False));self.event('delete-completion-left')
        if self.hold_delete:self.held_deletes.append(operation)
    def chunk(self):
        nonce=self.fields['snapshot.destination.query'];offset=int(self.fields['snapshot.destination.offset']);path=self.run_root/'original.bytes'
        if self.replace_on_chunk and not self.file_replaced:
            replacement=self.run_root/'replacement';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path);self.file_replaced=True
        need(revision(path)==self.job['artifactRevision']);need(nonce not in self.packet_chunks)
        with path.open('rb') as file:
            file.seek(offset);raw=file.read(512*1024)
        packet=dict(snapshotPhotosChunkVersion=1,nonce=nonce,runId=RUN,instance=self.job['instance'],processId=self.pid,basename=self.job['basename'],
            clockBefore=self.clock(),clockAfter=self.clock(),revision=revision(path),byteCount=self.job['byteCount'],sha256=self.job['sha256'],offset=offset,
            eof=offset+len(raw)==self.job['byteCount'],readerClosed=True,data=base64.b64encode(raw).decode())
        self.packet_chunks[nonce]=packet;self.write('snapshot-photos-chunk.json',packet)
    def write(self,name,value):
        path=self.documents/name;path.write_text(json.dumps(value,ensure_ascii=True,indent=1));path.chmod(0o600)
    def retirement_observe(self):
        nonce=self.fields['snapshot.destination.query'];need(self.retirement is not None and nonce not in self.query_nonces);self.query_nonces.add(nonce)
        packet=dict(snapshotPhotosRetirementVersion=1,nonce=nonce,receipt=deepcopy(self.retirement),clockBefore=self.clock(),clockAfter=self.clock(),
            runAbsent=not self.run_root.exists(),originalAbsent=not (self.run_root/'original.bytes').exists(),journalAbsent=not (self.run_root/'photos-original.json').exists())
        self.write('snapshot-photos-retire.json',packet)
    def retire(self):
        need(not self.retire_issued);self.retire_issued=True;self.retire_count+=1
        path=self.run_root/'original.bytes';journal=self.run_root/'photos-original.json';raw=journal.read_bytes();need(json.loads(raw)==self.job)
        need(self.job['queries'][-1]['assetPresent'] is False and self.job['queries'][-1]['authorization']==3
            and self.job['queries'][-1]['deletionAlive'] is False and revision(path)==self.job['artifactRevision'])
        before=self.clock();need({item.name for item in self.run_root.iterdir()}=={'original.bytes','photos-original.json'})
        steps=[];path.unlink();steps.append('original-unlinked');journal.unlink();steps.append('journal-unlinked');self.run_root.rmdir();steps.append('run-removed')
        self.retirement=dict(phase='complete',runId=RUN,instance=self.job['instance'],processId=self.pid,artifactRevision=self.job['artifactRevision'],
            artifactSha256=self.job['sha256'],byteCount=self.job['byteCount'],journalSha256=hashlib.sha256(raw).hexdigest(),clockBefore=before,
            clockAfter=self.clock(),steps=steps,readersClosed=True);self.retirement_observe()
    def call(self,method,path,body=None):
        self.domain.advance();self.requests.append((method,path,deepcopy(body)))
        if method=='GET' and path=='/session/companion-session':return dict(capabilities={'appium:bundleId':self.driver_bundle})
        need(path.startswith('/session/companion-session/'));suffix=path[len('/session/companion-session'):]
        if suffix=='/elements':
            identifier=body['value'];need(identifier.startswith(('snapshot.companion.','snapshot.destination.')));return [{W3C_ELEMENT:identifier}]
        if suffix.endswith(('/displayed','/enabled')):return True
        identifier=suffix.split('/')[2]
        if suffix.endswith('/text'):return self.fields.get(identifier,'')
        if suffix.endswith('/clear'):self.fields[identifier]='';return None
        if suffix.endswith('/value'):self.fields[identifier]=body['text'];return None
        need(method=='POST' and suffix.endswith('/click'));control=identifier;self.clicks.append(control)
        if control not in self.ignore_controls:
            if control.startswith('snapshot.companion.'):
                action=control.rsplit('.',1)[1];self.nonce=self.fields['snapshot.companion.nonce'];self.write('snapshot-companion-'+action+'.json',self.observe(action))
            elif control=='snapshot.destination.read':self.read_original()
            elif control=='snapshot.destination.inspect':self.inspect()
            elif control=='snapshot.destination.delete':self.delete()
            elif control=='snapshot.destination.chunk':self.chunk()
            elif control=='snapshot.destination.retire':self.retire()
            elif control=='snapshot.destination.retire-inspect':self.retirement_observe()
            else:need(False)
        if control in self.lost_controls:
            self.lost_controls.remove(control);raise NativeUIError('Declared lost companion return after actual delivery')
        return None
    def execute(self,session,operation,query):
        self.domain.advance();self.sdk.append((session,operation,deepcopy(query)));need(session=='companion-session')
        if operation=='mobile: activateApp':
            need(query==dict(bundleId=BUNDLE));self.foreground=True;self.domain.main_foreground=False;return True
        if operation=='mobile: overteProcessSourceInfo':return dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance=self.source,available=True,cleanupPending=False,sdk=deepcopy(SDK))
        if operation=='mobile: overteProcessInfo':return dict(bundleId=BUNDLE,pid=self.pid,foreground=self.foreground)
        need(operation=='mobile: pullFile' and query['remotePath'].startswith('@'+BUNDLE+':documents/'))
        filename=query['remotePath'].split(':documents/',1)[1];path=self.documents/filename
        need(path.resolve().is_relative_to(self.documents.resolve()));return base64.b64encode(path.read_bytes()).decode()


class SnapshotPhotosDomain:
    def __init__(self,case):
        self.main=SnapshotCaptureDomain(case);self.main_foreground=True;self.library={};self.save_count=0;self.ignore_save=False;self.lose_save=False;self.hold_save=None
        with self.main.owner() as capture:self.capture_result=capture.capture('f'*32)
        self.helper=PhotosCompanionDomain(case,self);self.helper.foreground=True;self.main_foreground=False
        self.helper.client=self.main.client
        with self.helper.owner() as owner:owner.admit('f'*32);self.admission_store=owner.store;self.helper_binding=deepcopy(owner.binding)
        self.helper.foreground=False;self.main_foreground=True
        self.save_activated=int(self.main.epoch());self.save_token=str(uuid.uuid4())
        self.phase_sequence=0;self.helper_lock=ScriptSourceLock(self.helper.root/'script-feature-sources.lock')
        observed=self.main.f.input_native.observed
        def current():
            value=observed();value['snapshotExportControlsVersion']=1;row=deepcopy(value['controls'][0])
            row={key:row[key] for key in ('token','enabled','focused','frame')};row.update(token=self.save_token,id='snapshot.save.0',snapshotExportControlVersion=1,
                snapshotRootId=value['controls'][0]['snapshotRootId'],snapshotQmlSource='qrc:/scripts/system/snapshot/NativeSnapshotReview.qml',snapshotRow=0,
                snapshotFileName=self.main.f.f.h.path.name,snapshotFileOwned=True,snapshotExportTicket='',snapshotCapturing=False,snapshotProcessing=False,snapshotSystemBlocked=False,inputReady=True)
            value['controls'].append(row);return value
        self.main.f.input_native.observed=current
        def saving(request,timeout):
            query=json.loads(request.data)
            if query['operation']!='edit':return Boundary.post(self.main.f.input_native,request,timeout)
            self.advance();native=self.main.f.input_native;row=current()['controls'][-1];identifier=str(uuid.uuid4())
            native.event(identifier,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId='snapshot.save.0',
                root=dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource'])))
            result=Boundary.post(native,request,timeout)
            native.receipt['status']['sampleEpochMs']=max(int(native.receipt['status']['sampleEpochMs']),native.epoch)
            native.event(identifier,'returned',native.receipt)
            self.save_count+=1
            if not self.ignore_save:
                op=self.main.exports.start();op.file=self.main.f.f.h.path.name;self.main.exports.rows[op.id][1]['fileName']=op.file
                self.main.exports.save(op);asset='actual-native-placeholder/L0/001'
                self.library[asset]=dict(name=op.file,raw=self.main.f.f.h.path.read_bytes())
                if self.hold_save is not None:self.hold_save=op
            if self.lose_save:self.lose_save=False;raise OSError('Declared lost normal Save return')
            return result
        case.enterContext(patch.object(normal_input,'urlopen',saving))
        domain=self
        class Runtime(IOSSnapshotPhotosRuntime):
            def _sources(self,selector):
                need(domain.main_foreground);value=domain.main.runtime._sources(selector)
                value['native'].monotonic=domain.main.mono;value['native'].sleep=domain.main.sleep;return value
        adapter=SimpleNamespace(state_path=lambda _:self.main.ctx.root/'session.json',_candidate_guard=lambda:True,_binding=lambda:None)
        def attest(_client,_session,target):need(target['capabilities']['appium:udid']=='HOST-PHYSICAL-DEVICE-MODEL')
        adapter.attest_physical_target=attest;self.runtime=Runtime(adapter)
        class Primary(PhotosClientContext):
            def __init__(self):
                self.runtime=domain.runtime;self.binding=deepcopy(domain.main.ctx.binding)
                self.target=dict(appId='org.example.client',capabilities={'appium:udid':'HOST-PHYSICAL-DEVICE-MODEL'})
                self.client=None;self.session='main-photos-session';self.os_source=dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance='8'*32,available=True,cleanupPending=False,sdk=deepcopy(SDK))
            def probe(self,foreground=None):
                need(domain.main.good and (foreground is None or domain.main_foreground==foreground))
                return dict(binding=deepcopy(self.binding),process=dict(bundleId='org.example.client',pid=42,foreground=domain.main_foreground),source=deepcopy(self.os_source))
            def foreground_sources(self):self.probe(True);return domain.runtime._sources('primary')
            def activate(self):self.probe(False);domain.main_foreground=True;domain.helper.foreground=False;return True
        self.primary=Primary()
    def advance(self,amount=1):self.main.f.now+=amount
    def client(self):
        domain=self
        class Phase(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**kwargs):
                domain.main.phase_sequence+=1
                return dict(fixturePhaseVersion=1,instance='e'*32,sequence=domain.main.phase_sequence,requestId=phase_nonce,runId=RUN,area='snapshots',capturedEpochMs=domain.main.epoch(),active=True,
                    createdEpochMs=BASE-100,retiredEpochMs=None,activations=[dict(sequence=1,ticket='f'*32,activatedEpochMs=BASE-90,stimulus=dict(verb='capture',inputs=dict(mode='still',format='png'))),
                        dict(sequence=2,ticket='7'*32,activatedEpochMs=domain.save_activated,stimulus=dict(verb='save',inputs={}))])
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.main.mono,sleep=self.main.sleep)
    @contextmanager
    def owner(self):
        with self.main.ctx.lock.held(),self.helper_lock.held():
            phase=PhaseFixtureReader(self.client(),RUN,'snapshots',epoch_ms=self.main.epoch,monotonic=self.main.mono)
            companion=PhotosCompanionContext(self.helper,self.helper.session,self.helper.target,self.helper_binding,self.helper.ipa,self.admission_store,
                self.helper_lock,RUN,phase.fixture_url,epoch_ms=self.main.epoch,monotonic=self.main.mono,sleep=self.main.sleep)
            yield IOSSnapshotPhotosOwner(self.runtime,'primary',RUN,self.primary,companion,self.main.ctx.lock,self.helper_lock,phase,
                epoch_ms=self.main.epoch,monotonic=self.main.mono,sleep=self.main.sleep)
