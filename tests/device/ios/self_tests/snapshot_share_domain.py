"""Connected normal Qt/WDA Share over real files and real Node PID sources.

Qt, UIKit, Photo/provider/OS and native device clocks are declared producers.
Every effect below follows the actual delivered modeled input; no result or
expected digest is sent by an adapter to a producer.
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
from types import SimpleNamespace
import time
import uuid
import weakref
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import W3C_ELEMENT,NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters import normal_input,snapshot_share_original
from ios.adapters.snapshot_share_retirement import FILES
from ios.adapters.installed_code import SDK
from ios.adapters.snapshot_photos_context import PhotosClientContext
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_runtime import IOSSnapshotShareRuntime
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.adapters.snapshot_share_query_owner import SnapshotShareQueryOwner
from ios.self_tests.snapshot_capture_domain import SnapshotCaptureDomain,RUN,BASE
from ios.self_tests.snapshot_share_query_domain import ShareQueryDomain
from ios.self_tests.snapshot_share_admission_domain import BUNDLE
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.snapshot_photos_domain import revision
from ios.self_tests.test_ios_snapshot_share_chunks import root_identity


REAL_TIME=time.time
REAL_MONOTONIC=time.monotonic
REAL_SLEEP=time.sleep
DEVICE='HOST-PHYSICAL-SHARE-DEVICE-MODEL'
SYSTEM_UI=dict(select=dict(using='accessibility id',value='Snapshot Original Receiver'),cancel=dict(using='accessibility id',value='System Share Cancel'))


class ShareRead:
    def __init__(self,archive):self.archive=archive
    def __del__(self):self.archive.event('weak-expired')


class WDAView:
    def __init__(self,flow,role,session):self.flow,self.role,self.session=flow,role,session;self.fields={};self.names={};self.elements={};self.requests=[];self.clicks=[];self.output=''
    def call(self,method,path,body=None):
        self.flow.advance();self.requests.append((method,path,deepcopy(body)));prefix='/session/'+self.session;need(path.startswith(prefix))
        suffix=path[len(prefix):]
        if suffix=='/elements':
            name=body['value'];visible=self.flow.visible(self.role,name)
            if not visible:return []
            if name not in self.elements:
                token=self.role+'-'+str(len(self.elements)+1);self.elements[name]=token;self.names[token]=name
            return [{W3C_ELEMENT:self.elements[name]}]
        name=self.names[suffix.split('/')[2]]
        if suffix.endswith(('/displayed','/enabled')):return self.flow.visible(self.role,name)
        if suffix.endswith('/text'):return self.fields.get(name,'')
        if suffix.endswith('/attribute/value'):return self.output
        if suffix.endswith('/clear'):self.fields[name]='';return None
        if suffix.endswith('/value'):self.fields[name]=body['text'];return None
        need(suffix.endswith('/click'));self.clicks.append(name);self.flow.clicked(self.role,name,self)
        if name in self.flow.lost_buttons:self.flow.lost_buttons.remove(name);raise NativeUIError('Declared lost ordinary WDA click return')
        return None


class ShareArchiveDomain(ShareQueryDomain):
    def __init__(self,case,flow):
        self.flow=flow;self.ui=None;self.job=None;self.read_ref=None;self.held_reads=[];self.hold_read=False;self.read_count=0;self.import_count=0;self.chunk_count=0
        self.retire_count=0;self.retirement=None;self.retirement_fail_after=None;self.retirement_seen=set();self.retirement_pins=None;self.retirement_start=None
        super().__init__(case,archive_pid=85,physical_selector=DEVICE,admission_ticket='f'*32,prepare_metadata=False)
        self.ui=WDAView(flow,'archive',self.scope['sessionId']);self.group=self.root/'AppGroup';self.group.mkdir(mode=0o700)
        self.node.call('mode',value='absent')
    def epoch(self):return self.flow.main.epoch()
    def mono(self):return self.flow.main.mono()
    def clock(self,offset=0):return dict(epochMs=self.epoch()+offset,monotonicMs=900000+self.epoch()-BASE+offset)
    def client(self):return self.flow.client()
    def execute(self,session,operation,query):
        self.flow.advance()
        if operation=='mobile: activateApp':
            need(query==dict(bundleId=BUNDLE));self.foreground=True;self.flow.main_foreground=False;return True
        if operation=='mobile: pullFile' and query['remotePath'].startswith('@'+BUNDLE+':documents/snapshot-share'):
            self.sdk.append((session,operation,deepcopy(query)));name=query['remotePath'].split(':documents/',1)[1]
            return base64.b64encode((self.documents/name).read_bytes()).decode()
        return super().execute(session,operation,query)
    def call(self,method,path,body=None):
        name=None if body is None else body.get('value')
        if self.ui is not None and ((type(name) is str and name.startswith('snapshot.share.archive.')) or '/element/archive-' in path):return self.ui.call(method,path,body)
        return super().call(method,path,body)
    def receiver_clock(self):return dict(epochMs=self.epoch(),monotonicMs=50000+self.epoch()-BASE)
    @property
    def group_run(self):return self.group/('snapshot-share-'+RUN)
    @property
    def archive_run(self):return self.documents/('snapshot-share-'+RUN)
    def persist(self):
        path=self.group_run/'share-original.json';path.write_text(json.dumps(self.job,indent=1)+'\n');path.chmod(0o600)
    def event(self,kind):
        self.flow.advance();self.job['events'].append(dict(sequence=len(self.job['events'])+1,kind=kind,clock=self.receiver_clock()));self.persist()
    def receive(self,view):
        if self.job is not None:return
        self.read_count+=1;run=view.fields['snapshot.share.run'];name=view.fields['snapshot.share.basename'];need(run==RUN and name==self.flow.main.f.f.h.path.name)
        self.group_run.mkdir(mode=0o700)
        self.job=dict(iosSnapshotShareOriginalVersion=2,runId=run,basename=name,instance=uuid.uuid4().hex,processId=84,receiverBundleId=BUNDLE+'.receiver',
            clockDomain='native-share-extension',createdClock=self.receiver_clock(),phase='issued',artifact='original.bytes',attachmentCount=1,registeredTypes=['public.png'],selectedType='public.png',
            receivedFilename=None,byteCount=0,sha256='',artifactRevision=None,rootIdentity=root_identity(self.group_run),events=[],queries=[])
        self.event('read-issued');operation=ShareRead(self);self.read_ref=weakref.ref(operation);self.event('callback-enter')
        path=self.group_run/'original.bytes';descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with self.flow.main.f.f.h.path.open('rb') as original,os.fdopen(descriptor,'wb') as output:
            while True:
                raw=original.read(65536)
                if not raw:break
                output.write(raw)
            output.flush();os.fsync(output.fileno())
        actual=path.read_bytes();self.job.update(phase='complete',receivedFilename=name,byteCount=path.stat().st_size,sha256=hashlib.sha256(actual).hexdigest(),artifactRevision=revision(path))
        self.event('read-completed');self.event('callback-left')
        if self.hold_read:self.held_reads.append(operation)
    def inspect(self,view):
        need(self.job is not None);nonce=view.fields['snapshot.share.query'];need(not any(row['requestId']==nonce for row in self.job['queries']))
        self.flow.advance();self.job['queries'].append(dict(requestId=nonce,clock=self.receiver_clock(),operationAlive=self.read_ref() is not None));self.persist()
        view.output=(self.group_run/'share-original.json').read_bytes().decode('utf-8')
    def finish(self):
        need(self.job is not None and self.job['phase']=='complete' and self.read_ref() is None and self.job['queries'] and not self.job['queries'][-1]['operationAlive'])
        if self.job['events'][-1]['kind']=='finish-issued':return
        self.event('finish-issued');self.flow.receiver_active=False;self.node.call('mode',value='absent');self.flow.complete_share(True)
    def import_original(self,view):
        self.import_count+=1;need(view.fields['snapshot.share.archive.run']==RUN and self.job['events'][-1]['kind']=='finish-issued')
        metadata=(self.group_run/'share-original.json').read_bytes();snapshot_share_original.original(json.loads(metadata));self.archive_run.mkdir(mode=0o700)
        before=self.clock();identity=uuid.uuid4().hex
        intent=dict(iosSnapshotShareImportVersion=2,runId=RUN,phase='issued',clockBefore=before,instance=identity,processId=self.pid,bundleId=BUNDLE,
            clockDomain='native-share-archive',basename=self.job['basename'],artifactRevision=None,archiveRootIdentity=root_identity(self.archive_run),
            sourceArtifactRevision=self.job['artifactRevision'],groupRootIdentity=self.job['rootIdentity'])
        path=self.archive_run/'import-intent.json';path.write_text(json.dumps(intent));path.chmod(0o600)
        source=self.group_run/'original.bytes';target=self.archive_run/'original.bytes';need(revision(source)==self.job['artifactRevision'])
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with source.open('rb') as original,os.fdopen(descriptor,'wb') as copied:
            while True:
                raw=original.read(65536)
                if not raw:break
                copied.write(raw)
            copied.flush();os.fsync(copied.fileno())
        need(metadata==(self.group_run/'share-original.json').read_bytes());path=self.archive_run/'original-extension.json';path.write_bytes(metadata);path.chmod(0o600)
        raw=target.read_bytes();self.flow.advance();self.imported=dict(intent,phase='complete',clockAfter=self.clock(),originalMetadataSha256=hashlib.sha256(metadata).hexdigest(),
            byteCount=target.stat().st_size,sha256=hashlib.sha256(raw).hexdigest(),artifactRevision=revision(target))
        path=self.archive_run/'import-original.json';path.write_text(json.dumps(self.imported,indent=1)+'\n');path.chmod(0o600)
        self.retirement_pins=[]
        for role,name in FILES:
            path=(self.group_run if role=='group' else self.archive_run)/name;raw=path.read_bytes()
            self.retirement_pins.append(dict(root=role,name=name,revision=revision(path),sha256=hashlib.sha256(raw).hexdigest(),byteCount=len(raw)))
        self.retirement_parent_pins={role:(root.parent.stat().st_dev,root.parent.stat().st_ino) for role,root in (('group',self.group_run),('archive',self.archive_run))}
    def chunk(self,view):
        self.chunk_count+=1;nonce=view.fields['snapshot.share.archive.query'];offset=int(view.fields['snapshot.share.archive.offset']);path=self.archive_run/'original.bytes'
        need(revision(path)==self.imported['artifactRevision']);before=self.clock()
        with path.open('rb') as file:file.seek(offset);raw=file.read(512*1024)
        self.flow.advance();packet=dict(snapshotShareChunkVersion=1,nonce=nonce,runId=RUN,instance=self.imported['instance'],processId=self.pid,basename=self.imported['basename'],
            clockDomain='native-share-archive',clockBefore=before,clockAfter=self.clock(),revision=revision(path),byteCount=self.imported['byteCount'],sha256=self.imported['sha256'],
            offset=offset,eof=offset+len(raw)==self.imported['byteCount'],readerClosed=True,data=base64.b64encode(raw).decode())
        output=self.documents/'snapshot-share-chunk.json';output.write_text(json.dumps(packet));output.chmod(0o600)
    def retirement_clock(self):
        if self.retirement_start is None:self.retirement_start=(self.clock(),REAL_MONOTONIC())
        initial,began=self.retirement_start;elapsed=int((REAL_MONOTONIC()-began)*1000)
        return {key:value+elapsed for key,value in initial.items()}
    def retire(self,view):
        self.retire_count+=1;need(self.retirement is None);nonce=view.fields['snapshot.share.archive.query']
        metadata=(self.archive_run/'original-extension.json').read_bytes();import_raw=(self.archive_run/'import-original.json').read_bytes()
        self.retirement=dict(snapshotShareRetirementVersion=1,runId=RUN,instance=self.imported['instance'],processId=self.pid,bundleId=BUNDLE,
            clockDomain='native-share-archive',originalMetadataSha256=hashlib.sha256(metadata).hexdigest(),importOriginalSha256=hashlib.sha256(import_raw).hexdigest(),
            groupRootIdentity=self.imported['groupRootIdentity'],archiveRootIdentity=self.imported['archiveRootIdentity'],files=deepcopy(self.retirement_pins),
            requestId=nonce,clockBefore=self.retirement_clock(),clockAfter=None,steps=[],complete=False,readersClosed=False)
        path=self.documents/'snapshot-share-retire-intent.json';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as output:json.dump(self.retirement,output);output.flush();os.fsync(output.fileno())
        valid=True
        for role,root in (('group',self.group_run),('archive',self.archive_run)):
            valid=valid and root_identity(root)==self.imported['groupRootIdentity' if role=='group' else 'archiveRootIdentity']
            valid=valid and set(os.listdir(root))=={name for kind,name in FILES if kind==role}
        for pin in self.retirement_pins:
            path=(self.group_run if pin['root']=='group' else self.archive_run)/pin['name']
            valid=valid and revision(path)==pin['revision'] and hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        self.retirement['readersClosed']=valid
        for pin in self.retirement_pins:
            if not valid:break
            root=self.group_run if pin['root']=='group' else self.archive_run;path=root/pin['name'];valid=revision(path)==pin['revision']
            if valid:path.unlink()
            self.retirement['steps'].append(dict(sequence=len(self.retirement['steps'])+1,kind='unlink',root=pin['root'],name=pin['name'],succeeded=valid,clock=self.retirement_clock()))
            if self.retirement_fail_after==len(self.retirement['steps']):valid=False
        for role,root in (('group',self.group_run),('archive',self.archive_run)):
            if not valid:break
            valid=not os.listdir(root) and root_identity(root)==self.imported['groupRootIdentity' if role=='group' else 'archiveRootIdentity']
            if valid:root.rmdir()
            self.retirement['steps'].append(dict(sequence=len(self.retirement['steps'])+1,kind='rmdir',root=role,name=root.name,succeeded=valid,clock=self.retirement_clock()))
        self.retirement.update(clockAfter=self.retirement_clock(),complete=valid)
        path=self.documents/'snapshot-share-retire.json';path.write_text(json.dumps(self.retirement));path.chmod(0o600)
    def inspect_retirement(self,view):
        need(self.retirement is not None);nonce=view.fields['snapshot.share.archive.query'];need(nonce not in self.retirement_seen);self.retirement_seen.add(nonce)
        before=self.retirement_clock();absent={};errors=False
        for role,root in (('group',self.group_run),('archive',self.archive_run)):
            parent=root.parent.stat();valid=(parent.st_dev,parent.st_ino)==self.retirement_parent_pins[role]
            try:root.lstat();absent[role]=False
            except FileNotFoundError:absent[role]=valid
            except OSError:errors=True;absent[role]=False
            errors=errors or not valid
        packet=dict(snapshotShareRetirementObservationVersion=1,requestId=nonce,runId=RUN,processId=self.pid,clockDomain='native-share-archive',
            clockBefore=before,clockAfter=self.retirement_clock(),retirement=deepcopy(self.retirement),groupRunAbsent=absent['group'],archiveRunAbsent=absent['archive'],observationErrors=errors)
        path=self.documents/'snapshot-share-retirement-observation.json';path.write_text(json.dumps(packet));path.chmod(0o600)


class SnapshotShareDomain:
    def __init__(self,case):
        self.main=SnapshotCaptureDomain(case);self.main_foreground=True;self.receiver_active=False;self.pending_operation=None
        self.share_count=0;self.ignore_share=False;self.ignore_select=False;self.ignore_cancel=False;self.lost_share=False;self.lost_buttons=set()
        with self.main.owner() as capture:
            capture.capture('f'*32);self.activations=deepcopy(capture.state['phaseOriginal']['activations']);self.created=capture.state['phaseOriginal']['createdEpochMs']
        self.archive=ShareArchiveDomain(case,self);self.primary_ui=WDAView(self,'primary',self.main.ctx.binding['sessionId']);self.share_token=str(uuid.uuid4())
        observed=self.main.f.input_native.observed
        def view():
            value=observed();value['snapshotExportControlsVersion']=1;old=value['controls'][0];blocked=self.pending_operation is not None
            row={key:deepcopy(old[key]) for key in ('token','enabled','focused','frame')};row.update(id='snapshot.share.0',token=self.share_token,enabled=not blocked,snapshotExportControlVersion=1,
                snapshotRootId=old['snapshotRootId'],snapshotQmlSource=old['snapshotQmlSource'],snapshotRow=0,snapshotFileName=self.main.f.f.h.path.name,snapshotFileOwned=True,
                snapshotExportTicket='' if self.pending_operation is None else self.pending_operation.id,snapshotCapturing=False,snapshotProcessing=False,snapshotSystemBlocked=blocked,inputReady=not blocked)
            value['controls'].append(row);return value
        self.main.f.input_native.observed=view
        def send(request,timeout):
            query=json.loads(request.data);native=self.main.f.input_native
            if query['operation']!='edit':return Boundary.post(native,request,timeout)
            row=view()['controls'][-1];identity=str(uuid.uuid4());native.event(identity,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId='snapshot.share.0',root=dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource'])))
            self.main.f.now=max(self.main.f.now,native.epoch);result=Boundary.post(native,request,timeout);self.share_count+=1
            if not self.ignore_share:
                operation=self.main.exports.start('share');operation.file=self.main.f.f.h.path.name;self.main.exports.rows[operation.id][1]['fileName']=operation.file
                operation.state.update(phase=3,sheetPresent=True,sheetAttached=True);self.main.exports.event(operation,'share-created');self.main.exports.event(operation,'share-presentation-requested');self.pending_operation=operation
            native.receipt['status']['sampleEpochMs']=max(int(native.receipt['status']['sampleEpochMs']),native.epoch);native.event(identity,'returned',native.receipt);self.main.f.now=max(self.main.f.now,native.epoch)+1
            if self.lost_share:self.lost_share=False;raise OSError('Declared lost normal Share return')
            return result
        case.enterContext(patch.object(normal_input,'urlopen',send));domain=self
        class Runtime(IOSSnapshotShareRuntime):
            def _sources(self,selector):
                need(domain.main_foreground);value=domain.main.runtime._sources(selector);value['native'].monotonic=domain.main.mono;value['native'].sleep=domain.main.sleep;return value
            def query_owner(self,owner):return SnapshotShareQueryOwner(owner.archive,owner.archive_lock,epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC,sleep=REAL_SLEEP)
        adapter=SimpleNamespace(state_path=lambda _:self.main.ctx.root/'session.json',_candidate_guard=lambda:True,_binding=lambda:None)
        def attest(_client,_session,target):need(target['capabilities']['appium:udid']==DEVICE)
        adapter.attest_physical_target=attest;self.runtime=Runtime(adapter)
        class Primary(PhotosClientContext):
            def __init__(self):
                self.runtime=domain.runtime;self.binding=deepcopy(domain.main.ctx.binding);self.target=dict(appId='org.example.client',capabilities={'appium:udid':DEVICE})
                self.client=domain.primary_ui;self.session=self.binding['sessionId'];self.os_source=dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance='8'*32,available=True,cleanupPending=False,sdk=deepcopy(SDK))
            def probe(self,foreground=None):
                need(domain.main.good and (foreground is None or domain.main_foreground==foreground));return dict(binding=deepcopy(self.binding),process=dict(bundleId=self.target['appId'],pid=42,foreground=domain.main_foreground),source=deepcopy(self.os_source))
            def foreground_sources(self):self.probe(True);return domain.runtime._sources('primary')
            def activate(self):self.probe(False);domain.main_foreground=True;domain.archive.foreground=False;return True
        self.primary=Primary()
    def advance(self):self.main.f.now+=1
    def activate(self,verb,ticket):
        self.advance();self.activations.append(dict(sequence=len(self.activations)+1,ticket=ticket,activatedEpochMs=self.main.epoch(),stimulus=dict(verb=verb,inputs={})))
    def client(self):
        domain=self
        class Phase(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                domain.main.phase_sequence+=1;return dict(fixturePhaseVersion=1,instance='e'*32,sequence=domain.main.phase_sequence,requestId=phase_nonce,runId=RUN,area='snapshots',
                    capturedEpochMs=domain.main.epoch(),active=True,createdEpochMs=domain.created,retiredEpochMs=None,activations=deepcopy(domain.activations))
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.main.mono,sleep=self.main.sleep)
    def visible(self,role,name):
        if role=='archive':return self.archive.foreground and name.startswith('snapshot.share.archive.')
        if name in (SYSTEM_UI['select']['value'],SYSTEM_UI['cancel']['value']):return self.pending_operation is not None and not self.receiver_active
        return self.receiver_active and name.startswith('snapshot.share.') and not name.startswith('snapshot.share.archive.')
    def clicked(self,role,name,view):
        if role=='archive':
            if name=='snapshot.share.archive.import':self.archive.import_original(view)
            elif name=='snapshot.share.archive.chunk':self.archive.chunk(view)
            elif name=='snapshot.share.archive.retire':self.archive.retire(view)
            elif name=='snapshot.share.archive.retire-inspect':self.archive.inspect_retirement(view)
            else:need(False)
        elif name==SYSTEM_UI['select']['value']:
            if not self.ignore_select:self.receiver_active=True;self.archive.node.call('mode',value='live')
        elif name==SYSTEM_UI['cancel']['value']:
            if not self.ignore_cancel:self.complete_share(False)
        elif name=='snapshot.share.receive':self.archive.receive(view)
        elif name=='snapshot.share.inspect':self.archive.inspect(view)
        elif name=='snapshot.share.finish':self.archive.finish()
        else:need(False)
    def complete_share(self,completed):
        operation=self.pending_operation;need(operation is not None);self.main.exports.callback(operation,'share-completion',lambda:self.main.exports.event(operation,'share-completed',completed=completed,hasError=False))
        self.main.exports.finish(operation,'success' if completed else 'cancelled');self.pending_operation=None
    @contextmanager
    def owner(self):
        with self.main.ctx.lock.held(),self.archive.source_lock.held():
            archive=SnapshotShareArchiveContext(self.archive,self.archive.session,self.archive.target,self.archive.binding,self.archive.ipa,self.archive.admission_store,self.archive.source_lock,RUN,self.archive.fixture_url,
                epoch_ms=self.main.epoch,monotonic=self.main.mono,sleep=self.main.sleep)
            yield IOSSnapshotShareOwner(self.runtime,'primary',RUN,self.primary,archive,self.main.ctx.lock,self.archive.source_lock,
                PhaseFixtureReader(self.client(),RUN,'snapshots',epoch_ms=self.main.epoch,monotonic=self.main.mono),SYSTEM_UI,epoch_ms=self.main.epoch,monotonic=self.main.mono,sleep=self.main.sleep)
