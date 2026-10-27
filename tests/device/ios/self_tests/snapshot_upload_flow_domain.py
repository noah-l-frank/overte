"""Normal captured-file Upload/Cancel with explicit native/Qt/HTTP producers.

The body is the actual same capture inode. No body is copied into a second
producer. File-list revisions model the native ten-field fstat grammar directly.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import uuid
from unittest.mock import patch
from adapters.native_feature_observation import need
from ios.adapters import normal_input,snapshot_chunks,snapshot_uploads
from ios.self_tests.snapshot_journey_files_domain import SnapshotJourneyFilesDomain,RUN,BASE,REAL_TIME,REAL_MONOTONIC
from ios.self_tests.snapshot_upload_domain import UploadDomain,fact
from ios.self_tests.test_ios_normal_input import Boundary


class SnapshotUploadFlowDomain(SnapshotJourneyFilesDomain):
    def __init__(self,case):
        super().__init__(case);self.case=case;self.upload=None;self.upload_sequence=0;self.upload_instance=uuid.uuid4().hex
        self.upload_count=0;self.upload_cancel_count=0;self.auto_complete=True;self.hold_fd=False;self.lost_upload=False;self.ignore_upload=False
        self.upload_tokens={key:str(uuid.uuid4()) for key in ('snapshot.upload.0','snapshot.upload-cancel')}
        self.activations=[dict(sequence=1,ticket='f'*32,activatedEpochMs=BASE-90,stimulus=dict(verb='capture',inputs=dict(mode='still',format='png')))]
        # This new producer emits the exact native revision from its first list.
        # Existing fixture producers and already retained originals stay intact.
        self.f.f.h.post=self.file_post
        observed=self.f.input_native.observed
        def view():
            value=observed();value['snapshotExportControlsVersion']=1
            old=next(row for row in value['controls'] if row['id']=='snapshot.capture')
            uploading=self.upload is not None and self.upload.upload['scopeActive']
            for control in self.upload_tokens:
                if control=='snapshot.upload-cancel' and not uploading:continue
                ready=not self.capturing and self.f.f.h.path.exists() and (control=='snapshot.upload-cancel' or not uploading)
                row={key:deepcopy(old[key]) for key in ('enabled','focused','frame')}
                row.update(id=control,token=self.upload_tokens[control],enabled=ready,snapshotExportControlVersion=1,
                    snapshotRootId=old['snapshotRootId'],snapshotQmlSource=old['snapshotQmlSource'],snapshotRow=-1 if control.endswith('cancel') else 0,
                    snapshotFileName=self.f.f.h.path.name if self.f.f.h.path.exists() else '',snapshotFileOwned=self.f.f.h.path.exists(),snapshotExportTicket='',
                    snapshotCapturing=self.capturing,snapshotProcessing=False,snapshotSystemBlocked=False,inputReady=ready)
                value['controls'].append(row)
            return value
        self.f.input_native.observed=view;prior=normal_input.urlopen
        def send(request,timeout):
            query=json.loads(request.data)
            if query['operation']!='edit' or query['input']['fieldToken'] not in self.upload_tokens.values():return prior(request,timeout)
            native=self.f.input_native;row=next(row for row in view()['controls'] if row['token']==query['input']['fieldToken']);control=row['id'];key=str(uuid.uuid4());self.advance()
            native.event(key,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId=control,root=dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource'])))
            self.f.now=max(self.f.now,native.epoch)
            result=Boundary.post(native,request,timeout)
            if control=='snapshot.upload.0':
                self.upload_count+=1
                if not self.ignore_upload:
                    self.call_sequence+=1;call=self.call_sequence;self.event('entry','onMessage',call)
                    self.script_state['pendingUploads']+=1;self.event('returned','onMessage',call);self.event('finally','onMessage',call)
                    self.upload=self.new_upload()
                    if self.auto_complete:self.upload.complete(close_fd=not self.hold_fd);self.script_completion()
                    else:self.upload.request('upload')
            else:
                self.upload_cancel_count+=1;need(self.upload is not None);self.upload.cancel(close_fd=not self.hold_fd);self.script_completion()
            native.receipt['status']['sampleEpochMs']=max(int(native.receipt['status']['sampleEpochMs']),native.epoch);native.event(key,'returned',native.receipt);self.advance()
            if self.lost_upload:self.lost_upload=False;raise OSError('Declared lost actual ordinary Upload return')
            return result
        case.enterContext(patch.object(normal_input,'urlopen',send))
    def new_upload(self):return UploadDomain(self.case,path=self.f.f.h.path,version=2,now=self.epoch)
    def script_completion(self):
        self.call_sequence+=1;call=self.call_sequence;self.event('entry','onNativeUploadStatus',call)
        self.script_state['pendingUploads']-=1;self.event('returned','onNativeUploadStatus',call);self.event('finally','onNativeUploadStatus',call)
    def file_post(self,request,timeout):
        native=self.ctx.files;query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(query);native.echo=json.dumps(query).encode()
        path=self.f.f.h.path;metadata=path.stat() if path.exists() else None;raw=path.read_bytes() if metadata is not None else b''
        revision=snapshot_uploads.file_revision(fact(metadata,2)) if metadata is not None else None
        row=dict(name=path.name,size=len(raw),revision=revision,sha256=hashlib.sha256(raw).hexdigest())
        native.value=dict(schemaVersion=query['schemaVersion'],commandId=query['commandId'],operation=query['operation'],prefix=query['prefix'],processId=42,sampleEpochMs=self.epoch(),ok=True)
        if query['operation']=='list':native.value['files']=[row] if metadata is not None else []
        else:
            need(revision==query['revision']);offset=query['offset'];part=raw[offset:offset+snapshot_chunks.CHUNK_BYTES]
            native.value['file']=dict(name=row['name'],revision=revision,size=len(raw),offset=offset,eof=offset+len(part)==len(raw),data=base64.b64encode(part).decode())
        return native
    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=snapshot_uploads.ACTION:return super().post(request,timeout)
        self.advance();self.commands.append(deepcopy(query));self.upload_sequence+=1;before=self.clock()
        source=(self.upload.source_snapshot() if self.upload is not None else dict(iosSnapshotUploadsSourceVersion=2,complete=True,uploads=[],resources=[],requests=[],callbacks=[],events=[],activity=dict(slots=0,alive=0),transportFDObservationRequired=True))
        value=dict(iosSnapshotUploadsVersion=1,requestId=query['commandId'],runId=RUN,instance=self.upload_instance,sequence=self.upload_sequence,processId=42,
            clockDomain='native-main-snapshot-uploads',clockBefore=before,clockAfter=self.clock(),source=source)
        self.raws[snapshot_uploads.FILE]=json.dumps(value,indent=1)+'\n';self.ctx.files.echo=json.dumps(query).encode();return self.ctx.files
    def prepare(self):
        with self.capture_owner() as capture:result=capture.capture('f'*32)
        self.advance();self.activations.append(dict(sequence=2,ticket='a'*32,activatedEpochMs=self.epoch(),stimulus=dict(verb='upload',inputs={})));return result
    def upload_owner(self):return self.runtime.upload_owner('primary',RUN,self.client(),epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
