"""Declared UI/upload/backend models over existing normal Pico factories.

The independent stdin worker provides actual PID/exe/file/locking boundaries;
its AssetServer protocol data and all Native/Qt effects remain explicit models.
No server, oven, Domain, device, compiler or background service is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import shlex
from datetime import datetime,timezone
from unittest.mock import patch
from adb_transport import AdbTransport
from adapters.pico4.assets_transport import HEADER as WIRE_HEADER,FOOTER as WIRE_FOOTER
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import uuid
from urllib.parse import urlsplit

from adapters.assets_input import DIRECTORIES,NAMES
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.assets_backend_originals import PicoAssetsBackendOriginals
from adapters.pico4.assets_file_owner import OwnedAssetsFiles
from adapters.pico4.assets_files import NativeAssetsFiles
from adapters.pico4.assets_prefix import PicoAssetsPrefix
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.pico4.assets_upload_owner import OwnedAssetsUpload
from adapters.script_journey.history import canonical
from self_tests.pico_assets_prefix_fixture import AssetsPrefixModel

WORKER=r'''
import fcntl,json,os,select,sys,time,uuid
from pathlib import Path
root=Path(os.environ['OVERTE_E2E_PICO_ASSETS_ORIGINALS']);state=Path(sys.argv[1]);output=root/'assets-bakes.json'
fd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600);instance=uuid.uuid4().hex;sequence=0
ready=state.with_suffix('.ready');release=state.with_suffix('.go')
start=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
try:
 while not select.select([sys.stdin],[],[],0)[0]:
  source=json.loads(state.read_bytes());now=time.time_ns()//1000000;sequence+=1
  value=dict(assetsBakeOriginalsVersion=2,instance=instance,sequence=sequence,processId=os.getpid(),processStart=start,
   domainId=source['domainId'],assetServerId=source['assetServerId'],capturedEpochMs=now,contextCapturedEpochMs=now,
   valid=True,jobs=[],mappings=source['mappings'],blobs=source['blobs'],pending=0)
  raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
  fcntl.flock(fd,fcntl.LOCK_EX);pending=root/'assets-bakes.pending';pending.write_bytes(b'');pending.chmod(0o600)
  os.ftruncate(fd,0);os.pwrite(fd,raw,0);os.fsync(fd);pending.unlink();fcntl.flock(fd,fcntl.LOCK_UN)
  if sequence==1:
   ready.write_bytes(b'original publication fsynced');ready.chmod(0o600)
   while not release.exists() and not select.select([sys.stdin],[],[],0)[0]:time.sleep(.005)
  time.sleep(.025)
finally:os.close(fd)
'''


class AssetsUploadModel(AssetsPrefixModel):
    def __init__(self,case,path,normal,*,binary_transport=False,canonical_prefix=False):
        super().__init__(case,path,normal,manual_owner=False)
        self.real_time_start=time.monotonic();self.origin=time.time_ns()//1000000
        self.all_browsers=[];self.leases={};self.review=False;self.destination=False;self.review_index=0;self.destination_text=''
        self.bundle_urls=[];self.bundle_paths=[];self.bundles=[];self.upload_calls=[];self.server_rows={};self.server_blobs={};self.filter='';self.selected_mapping=''
        self.ignored_destination=False;self.foreign_download=False
        self.backend_root=self.root/'backend-originals';self.backend_root.mkdir(mode=0o700)
        self.state_file=self.root/'backend-modeled-state.json';self.server_state()
        self.worker_file=self.root/'backend-model-worker.py';self.worker_file.write_text(WORKER);self.worker_file.chmod(0o600)
        env=os.environ.copy();env.update(OVERTE_E2E_PICO_ASSETS_ORIGINALS_ENABLE='1',OVERTE_E2E_PICO_ASSETS_ORIGINALS=str(self.backend_root))
        self.backend=None;self.upload=None
        with (self.root/'backend-worker.stderr').open('wb') as errors:
            self.process=subprocess.Popen([sys.executable,'-u',str(self.worker_file),str(self.state_file),'-t','3'],stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,stderr=errors,env=env)
        case.addCleanup(self.close)
        deadline=time.monotonic()+3
        while not self.state_file.with_suffix('.ready').exists():
            assert self.process.poll() is None and time.monotonic()<deadline;time.sleep(.005)
        self.binary_transport=binary_transport;self.canonical_prefix=canonical_prefix;self.sdk_calls=[]
        if binary_transport:
            self.sdk_original=self.root/'sdk-return-body.bin';self.sdk_original.write_bytes(b'{}');self.sdk_original.chmod(0o600)
            for active in (patch.object(self.native,'execute_bytes',AdbTransport.execute_bytes.__get__(self.native),create=True),
                patch.object(self.native,'command',['declared-sdk-never-executed'],create=True),
                patch('adb_transport.subprocess.run',side_effect=self.binary_sdk)):
                active.start();case.addCleanup(active.stop)
        self.owner=None
        if canonical_prefix:
            assert binary_transport
            self.backend=self.backend_reader()
            self.lock=self.adapter._script_journey()._lock(self.native.target)
            # Only the actual normal factory creates this Parent. No prior
            # Parent/source family is abandoned or reset for the same run.
            with self.lock.held():
                previous_trace=sys.gettrace();exceptions=[]
                def traced(frame,event,arg):
                    if event=='exception' and '/overte-pico-consolidated-' in frame.f_code.co_filename:
                        exceptions.append(dict(file=frame.f_code.co_filename,line=frame.f_lineno,
                            function=frame.f_code.co_name,error=arg[0].__name__,message=str(arg[1])))
                    return traced
                try:
                    if getattr(case,'trace_factory',False):sys.settrace(traced)
                    self.owner=self.adapter._assets_prefix(self.native.target,self.run,self.url,self.phase,
                        source_lock=self.lock,backend=self.backend)
                except BaseException:
                    (self.root/'original-factory-failure.txt').write_text(traceback.format_exc());raise
                finally:
                    sys.settrace(previous_trace)
                    if exceptions:(self.root/'factory-exception-diagnostic.json').write_text(json.dumps(exceptions,indent=2)+'\n')
        else:
            self.owner=PicoAssetsPrefix(self.root/'assets-prefix3.json',self.binding,self.phase,self.lock,
                self.mappings(),self.uploads(),lambda:json.dumps(self.snapshot()),self.controls,self.create_controls,
                self.cancel,self.guard,self.epoch,upload_factory=self.upload_factory)
        case.addCleanup(self.owner.raw_archive.close_host)
        if binary_transport and not canonical_prefix:self.owner.bind_wire(self.adapter,self.native.target)
        # MODEL-only readiness barrier. The same original publisher now runs
        # continuously before first IO; no packet/clock/source scope is renewed.
        release=self.state_file.with_suffix('.go');release.write_bytes(b'publish continuously');release.chmod(0o600)

    def binary_sdk(self,args,**options):
        assert args[:4]==['declared-sdk-never-executed','-s',self.native.target,'exec-out']
        assert 'text' not in options
        self.sdk_calls.append(dict(inputBytes=0 if 'input' not in options else len(options['input'])))
        parts=shlex.split(args[4]);assert parts[:4]==['run-as','org.overte.pico','sh','-c'];nonce=parts[10]
        def stamp(path):
            value=path.stat()
            def date(ns):return datetime.fromtimestamp(ns//10**9,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')+f'.{ns%10**9:09d} +0000'
            return f'{value.st_dev} {value.st_ino} {value.st_mode:x} {value.st_uid} {value.st_nlink} {value.st_size} {date(value.st_mtime_ns)} {date(value.st_ctime_ns)}'
        if 'input' in options:
            raw=options['input'];assert type(raw) is bytes
            command=json.loads(raw);assert command['operation']=='stage'
            self.send(command)
            original=self.root/('sdk-stage-'+command['commandId']+'.bin');original.write_bytes(raw);original.chmod(0o600)
            output=(f'OVT_PICO_ASSETS_STAGE_V1 {nonce} {len(raw)} {hashlib.sha256(raw).hexdigest()}\n'+stamp(original)+'\n').encode()
        else:
            name=parts[-1].rsplit('/',1)[-1]
            if name=='navigation-ui-observation.json':raw=json.dumps(self.snapshot()).encode()
            elif name=='navigation-ui-status.json':raw=json.dumps(self.native.status).encode()
            else:
                assert name in ('feature-pico-assets-files.json','feature-pico-assets-observation.json',
                    'feature-pico-assets-uploads.json','feature-pico-assets-download.json')
                raw=self.raw.encode()
            self.sdk_original.write_bytes(raw);description=stamp(self.sdk_original).encode()
            output=WIRE_HEADER+nonce.encode()+b'\n'+description+b'\n'+raw+WIRE_FOOTER+nonce.encode()+b'\n'+description+b'\n'
        return subprocess.CompletedProcess(args,0,stdout=output,stderr=b'')

    def close(self):
        if self.upload is None and self.owner is not None:self.upload=self.owner.upload_owner
        if self.upload is not None:assert self.upload.file_journal.close_host()
        if self.backend is not None:assert self.backend.close_host()
        if self.process.poll() is None:self.process.stdin.close()
        assert self.process.wait(timeout=5)==0
        if not self.process.stdin.closed:self.process.stdin.close()
        for _ in range(2):
            try:os.kill(self.process.pid,0)
            except ProcessLookupError:pass
            else:raise AssertionError('Original owned worker still exists')

    def server_state(self):
        connection=self.connection()
        value=dict(domainId=connection['domainId'],assetServerId=connection['assetServerId'],
            mappings=[dict(path=path,hash=row['hash']) for path,row in sorted(self.server_rows.items())],
            blobs=[dict(hash=digest,actualSha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)) for digest,raw in sorted(self.server_blobs.items())])
        temporary=self.state_file.with_suffix('.pending');temporary.write_bytes(canonical(value));temporary.chmod(0o600);temporary.replace(self.state_file)

    def backend_reader(self):
        return PicoAssetsBackendOriginals(self.backend_root,self.process.pid,
            hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
            lambda pid:pid==self.process.pid and self.process.poll() is None,self.connection()['domainId'],
            guard=self.guard,retain=lambda _raw:None,capacity=lambda:None)

    def upload_factory(self,parent):
        ticket=parent.state['steps'][-1]['ticket']
        if self.binary_transport:
            files=self.adapter._assets_file_owner(self.native.target,self.run,ticket,self.url,stage=2)
        else:
            native=NativeAssetsFiles(self.send,self.original,self.epoch,self.guard,123,stage=2,monotonic=lambda:self.clock,sleep=self.sleep)
            files=OwnedAssetsFiles(native,PrivateFeatureState(self.root/'assets-files-stage2.json'),self.binding,self.run,ticket,self.url)
        self.backend=self.backend_reader()
        download=PicoAssetsSource(self.send,self.original,self.epoch,self.guard,123,download=True,
            monotonic=lambda:self.clock,sleep=self.sleep)
        self.upload=OwnedAssetsUpload(parent,files,self.backend,download);return self.upload

    def files_source(self,command):
        stage=command['stage'];self.directory=self.root/('feature-assets-'+self.run+'-stage'+str(stage))
        retired=self.leases.get(stage,False);operation=command['operation']
        if operation=='stage':
            self.directory.mkdir(mode=0o700)
            for name,encoded in command['files'].items():
                path=self.directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(encoded))
            self.leases[stage]=False;retired=False
        elif operation=='release':shutil.rmtree(self.directory);self.leases[stage]=True;retired=True
        exists=self.directory.exists()
        return dict(assetsFilesVersion=1,exists=exists,retiring=retired,retired=retired,directory=self.directory.as_uri(),
            rootIdentity=self.identity(self.directory) if exists else None,
            directories=[dict(name=name,identity=self.identity(self.directory/name)) for name in DIRECTORIES] if exists else [],
            files=[dict(name=name,exists=True,identity=self.identity(self.directory/name),bytes=(self.directory/name).stat().st_size,
                sha256=hashlib.sha256((self.directory/name).read_bytes()).hexdigest()) for name in NAMES] if exists else [],primaryRetired=False)

    def snapshot(self):
        packet=super().snapshot()
        if not hasattr(self,'all_browsers'):return packet
        browsers=list(self.all_browsers)
        if self.browser is not None and all(row['id']!=self.browser['id'] for row in browsers):browsers.append(self.browser)
        packet['assetsUiInventory']['browsers']=sorted(deepcopy(browsers),key=lambda row:row['id'])
        def finish():
            for row in packet['controls']:
                row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps({k:v for k,v in row.items() if k!='token'},sort_keys=True)))
            return packet
        def plain(identifier,**fields):
            packet['controls'].append(dict(id=identifier,enabled=True,focused=self.focus==identifier,inputReady=True,**fields))
        if self.page=='assets':
            plain('assets.refresh');plain('assets.filter',text=self.filter)
            for index,(path,row) in enumerate(sorted(self.server_rows.items())):
                plain('assets.row.'+str(index),mapping=dict(path=path,name=path.rsplit('/',1)[-1],folder=False,status='--'))
            page=next(r for r in packet['controls'] if r['id']=='assets.page')
            page.update(selectedPath=self.selected_mapping,selectedUrl='' if not self.selected_mapping else 'atp:'+self.selected_mapping,
                selection=[] if not self.selected_mapping else [dict(path=self.selected_mapping,folder=False,status='--')])
        if self.destination:
            plain('assets.destination.path',text=self.destination_text);plain('assets.destination.accept')
        if self.browser is None or not self.browser['rootAlive']:return finish()
        picker=next(row['picker'] for row in packet['controls'] if 'picker' in row)
        picker.update(review=self.review,bundleRoot='' if not self.review else self.directory.as_uri()+'/gltf-bundle',
            bundleUrls=deepcopy(self.bundle_urls) if self.review else [],relativePaths=deepcopy(self.bundle_paths) if self.review else [])
        for row in packet['controls']:
            if 'picker' in row:row['picker']=deepcopy(picker)
        packet['controls']=[row for row in packet['controls'] if not row['id'].startswith('assets-file.row.')]
        def add(identifier,**values):
            row=dict(id=identifier,enabled=True,focused=self.focus==identifier,inputReady=True,picker=deepcopy(picker),**values)
            row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)));packet['controls'].append(row)
        if self.review:
            add('assets-file.primary',count=len(self.bundle_paths),currentText=self.bundle_paths[self.review_index],currentIndex=self.review_index)
            add('assets-file.confirm');add('assets-file.review-cancel')
        else:
            add('assets-file.accept')
            folder=Path(self.folder) if self.folder else None
            if folder is not None and folder.is_dir():
                for index,path in enumerate(sorted(folder.iterdir())):
                    add('assets-file.row.'+str(index),sourceUrl=path.as_uri(),directory=path.is_dir(),selected=path.as_uri() in self.selected)
        for row in packet['controls']:
            if 'picker' in row:row['picker']=deepcopy(picker)
        return finish()

    def write(self,target,package,path,raw):
        command=json.loads(raw)
        if path.endswith('android-control-command.json'):return super().write(target,package,path,raw)
        row=next(row for row in self.snapshot()['controls'] if row['id']==command['controlId']);identifier=command['controlId']
        extra=(identifier.startswith(('assets-file.row.','assets.row.')) or identifier in ('assets-file.accept','assets-file.primary','assets-file.confirm',
            'assets.destination.path','assets.destination.accept','assets.refresh','assets.filter'))
        if not extra:
            old=self.browser;result=super().write(target,package,path,raw)
            if identifier=='assets.upload' and not self.ignore and old is not None:
                self.all_browsers.append(old)
                number=len(self.all_browsers)*4+1
                for key,offset in (('id',0),('modelId',1),('contextId',2),('windowId',3)):
                    self.browser[key]=format(number+offset,'032x')
                self.selected=[];self.review=False;self.destination=False
            return result
        if self.before_input is not None:self.before_input(command)
        assert row['token']==command['controlToken'] and command['sequence']==self.native.sequence+1
        self.inputs.append(deepcopy(command));self.native.sequence+=1
        if not self.ignore:
            if identifier.startswith('assets-file.row.'):
                assert not row['directory'];url=row['sourceUrl']
                if url not in self.selected:self.selected.append(url)
            elif identifier=='assets-file.accept':
                self.bundle_urls=deepcopy(self.selected);root=self.directory/'gltf-bundle'
                self.bundle_paths=[str(Path(urlsplit(url).path).relative_to(root)) for url in self.selected]
                self.review=True;self.review_index=0
            elif identifier=='assets-file.primary':
                if command['action']=='select-index':self.review_index=command['index']
            elif identifier=='assets-file.confirm':
                self.browser.update(rootAlive=False,modelAlive=False,inCurrentTree=False,visible=False,closing=True)
                self.destination=True;self.review=False
            elif identifier=='assets.destination.path':
                self.focus=identifier
                if command['action']=='replace':self.destination_text=command['text']
            elif identifier=='assets.destination.accept' and not self.ignored_destination:
                self.commit_upload();self.destination=False
            elif identifier=='assets.filter':
                self.focus=identifier
                if command['action']=='replace':self.filter=command['text']
            elif identifier.startswith('assets.row.'):
                self.selected_mapping=row['mapping']['path']
        self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],sequence=command['sequence'],
            performed=True,error='',processId=123,updatedEpochMs=self.epoch())

    def commit_upload(self):
        now=self.epoch();root=self.directory/'gltf-bundle';requests=[];names=[]
        for url,name in zip(self.bundle_urls,self.bundle_paths):
            path=Path(urlsplit(url).path);raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();filename=hashlib.sha256(str(path).encode()).hexdigest()
            names.append(dict(relativePath=name,filenameSha256=filename));self.server_blobs[digest]=raw
            self.server_rows[self.destination_text+name]=dict(path=self.destination_text+name,hash=digest,bakeStatus=0,bakeError='')
            for kind,original in [('upload',dict(filenameSha256=filename,originalSha256=digest,originalBytes=len(raw),errorCode=0,returnedHash=digest)),
                ('mapping',dict(path=self.destination_text+name,hash=digest,errorCode=0))]:
                life=dict(requestAlive=False,finishedConnected=False,destroyedConnected=False,finishedCaptureAlive=False,destroyedCaptureAlive=False,
                    callbacksInstalled=True,resourcesRetired=True)
                requests.append(dict(instance=uuid.uuid4().hex,kind=kind,issuedEpochMs=now,completedEpochMs=now,destroyedEpochMs=now,original=original,lifetime=life))
        context={k:v for k,v in self.connection().items() if k!='canWrite'}
        self.bundles.append(dict(id=str(uuid.uuid4()),runId=self.run,directorySha256=hashlib.sha256(str(root).encode()).hexdigest(),
            destination=self.destination_text,primary=self.bundle_paths[self.review_index],files=names,connection=context,createdEpochMs=now,
            active=False,finishedEpochMs=now,errorSha256=hashlib.sha256(b'').hexdigest(),requests=requests))
        self.upload_calls.append(dict(kind='bundle',epochMs=now,argumentsSha256=hashlib.sha256(canonical(self.bundle_urls)).hexdigest()));self.server_state()

    def send(self,command):
        if command['action'] in ('feature-pico-assets-observe','feature-pico-assets-uploads-observe','feature-pico-assets-download'):
            if self.before_query is not None:self.before_query(command)
            self.calls.append(deepcopy(command));self.query_sequence+=1
            packet=dict(schemaVersion=1,requestId=command['commandId'],runId=self.run,instance='a'*32,sequence=self.query_sequence,
                processId=123,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
            if command['action']=='feature-pico-assets-observe':
                packet.update(activeRequests=0,retainedResults=0,source=dict(picoAssetsObservationVersion=1,complete=True,
                    mappings=[row for _path,row in sorted(self.server_rows.items())],**self.connection(),clientInstance='5'*32,nodeListInstance='6'*32,assetServerInstance='7'*32))
            elif command['action']=='feature-pico-assets-download':
                blob=self.server_blobs[command['hash']];blob=blob+b'foreign' if self.foreign_download else blob
                connection={k:v for k,v in self.connection().items() if k!='canWrite'}
                packet.update(activeRequests=0,retainedResults=0,source=dict(picoAssetsDownloadVersion=1,**connection,clientInstance='5'*32,
                    nodeListInstance='6'*32,assetServerInstance='7'*32,hash=command['hash'],bytes=len(blob),base64=base64.b64encode(blob).decode(),loadedFromCache=False))
            else:
                packet['source']=dict(picoAssetsUploadsVersion=1,instance='8'*32,runId=self.run,valid=True,retired=False,activeBundles=0,
                    liveRequests=0,retainedBundles=len(self.bundles),bundles=sorted(deepcopy(self.bundles),key=lambda r:r['id']),
                    totalCalls=len(self.upload_calls),calls=deepcopy(self.upload_calls),connection=self.connection(),originalActiveBundles=0)
            if self.corrupt is not None:self.corrupt(packet)
            self.raw=json.dumps(packet);return
        return super().send(command)
