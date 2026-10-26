"""Declared native admission lifetime over an actual host descriptor and files.

UIKit/NSBundle/native clocks remain explicit producers. Descriptor close,
weak lease expiry, published file revisions and host acquisition are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from types import SimpleNamespace
import weakref
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.adapters.snapshot_share_seal_owner import SnapshotShareAdmissionSealOwner
from ios.self_tests.snapshot_photos_domain import revision
from ios.self_tests import snapshot_share_domain
from ios.self_tests.snapshot_share_domain import ShareArchiveDomain,SnapshotShareDomain,WDAView,REAL_TIME,REAL_MONOTONIC
from ios.self_tests.snapshot_share_query_domain import ShareQueryDomain,RUN


def parent_identity(path):
    value=path.stat();return hashlib.sha256((':'.join(str(item) for item in (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid))).encode()).hexdigest()


class SealProducer:
    def setup_seal_source(self,case,advance):
        self.sealed=False;self.seal_calls=0;self.close_calls=0;self.source_fd=None;self.seal_advance=advance
        self.ignore_seal=False;self.lost_output=False;self.unknown_close_return=False;self.collector_ref=None;self.collectors=[]
        self.parent=parent_identity(self.documents)
        self.source_fd=os.open(self.installed,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);self.first_fd=self.source_fd
        self.initial_forest=self.forest();self.bundle_root=revision(self.installed);case.addCleanup(self.close_source)
        self.original=None;self.original_text=''
    def forest(self):
        return {str(path.relative_to(self.installed)):revision(path) for path in [self.installed,*self.installed.rglob('*')]}
    def pin(self,action):
        path=self.documents/('snapshot-share-companion-'+action+'.json');raw=path.read_bytes()
        return dict(name=path.name,revision=revision(path),sha256=hashlib.sha256(raw).hexdigest(),byteCount=len(raw),parentIdentity=parent_identity(self.documents))
    def published_after(self,method,path):
        if method=='POST' and path.endswith('/click'):
            action=path.split('/')[-2].rsplit('.',1)[-1]
            if action in ('identity','clock') and not self.ignore and not self.stale:self.published[action]=self.pin(action)
    def seal_ready(self):return not self.sealed and (self.collector_ref is None or self.collector_ref() is None)
    def close_source(self):
        if self.source_fd is not None:os.close(self.source_fd);self.source_fd=None
    def hold_collector(self):
        class Lease:pass
        lease=Lease();self.collector_ref=weakref.ref(lease);self.collectors.append(lease)
    def seal_native(self,view):
        self.seal_calls+=1
        if self.ignore_seal or self.sealed or self.source_fd is None or self.collector_ref is not None and self.collector_ref() is not None:return
        nonce=view.fields['snapshot.share.archive.query'];need(nonce not in self.nonces);self.nonces.add(nonce)
        if self.forest()!=self.initial_forest or revision(self.installed)!=self.bundle_root or parent_identity(self.documents)!=self.parent:return
        if any(self.pin(action)!=self.published[action] for action in ('identity','clock')):return
        before=self.clock();self.seal_advance();closing=self.clock();self.sealed=True;self.close_calls+=1
        os.close(self.source_fd);self.source_fd=None;self.seal_advance();ended=self.clock();self.sequence+=1
        identity=json.loads((self.documents/'snapshot-share-companion-identity.json').read_bytes())
        self.original=dict(snapshotShareAdmissionSealVersion=1,requestId=nonce,instance=identity['instance'],processId=self.pid,
            bundleId=self.target['appId'],sequence=self.sequence,sourceBirthClock=deepcopy(identity['sourceBirthClock']),preparedClock=deepcopy(identity['preparedClock']),
            bundle=deepcopy(identity['bundle']),bundleRootIdentity=self.bundle_root,clockBefore=before,clockAfter=ended,
            outputs=[deepcopy(self.published[action]) for action in ('identity','clock')],descriptorClose=dict(clockBefore=closing,clockAfter=ended,succeeded=not self.unknown_close_return),
            sealed=True,outputReadersClosed=True,collectorAlive=self.collector_ref is not None and self.collector_ref() is not None,readerClosed=not self.unknown_close_return)
        self.original_text=json.dumps(self.original,separators=(',',':'));view.output=self.original_text


class ShareSealDomain(SealProducer,ShareQueryDomain):
    def __init__(self,case):
        self.published={};self.view=None;self.sealed=False
        super().__init__(case,archive_pid=85,prepare_metadata=False)
        self.foreground=True;self.setup_seal_source(case,self.advance)
        self.flow=SimpleNamespace(advance=self.advance,visible=lambda _role,name:self.foreground and name in {
            'snapshot.share.archive.query','snapshot.share.archive.admission-seal','snapshot.share.archive.admission-seal-original'},
            clicked=lambda _role,_name,view:self.seal_native(view),lost_buttons=set())
        self.view=WDAView(self.flow,'seal',self.binding['sessionId'])
    def advance(self):self.tick+=1
    def call(self,method,path,body=None):
        name=None if body is None else body.get('value')
        if self.view is not None and ((type(name) is str and name.startswith('snapshot.share.archive.')) or '/element/seal-' in path):
            if path.endswith('/enabled') and self.view.names[path.split('/')[4]]=='snapshot.share.archive.admission-seal':return self.seal_ready()
            value=self.view.call(method,path,body)
            if path.endswith('/attribute/value'):value=self.original_text
            if self.lost_output and path.endswith('/attribute/value'):self.lost_output=False;raise NativeUIError('Declared lost original readonly value return')
            return value
        if self.sealed and method=='POST' and path.endswith('/click'):raise NativeUIError('The modeled native admission source is fenced')
        value=super().call(method,path,body);self.published_after(method,path);return value
    @contextmanager
    def seal_owner(self):
        with self.source_lock.held():
            ctx=SnapshotShareArchiveContext(self,self.session,self.target,self.binding,self.ipa,self.admission_store,self.source_lock,RUN,self.fixture_url,
                epoch_ms=self.epoch,monotonic=self.mono,sleep=lambda _:None)
            yield SnapshotShareAdmissionSealOwner(ctx,self.source_lock,epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC)


class ShareSealArchive(SealProducer,ShareArchiveDomain):
    def __init__(self,case,flow):
        self.published={};self.sealed=False
        super().__init__(case,flow);self.setup_seal_source(case,flow.advance)
    def call(self,method,path,body=None):
        if self.ui is not None and path.endswith('/enabled') and '/element/archive-' in path and self.ui.names[path.split('/')[4]]=='snapshot.share.archive.admission-seal':
            return self.seal_ready()
        if self.sealed and method=='POST' and path.endswith('/click') and 'snapshot.share.companion.' in path:
            raise NativeUIError('The modeled native admission source is fenced')
        value=super().call(method,path,body);self.published_after(method,path)
        if path.endswith('/attribute/value') and '/element/archive-' in path:value=self.original_text
        return value


class ShareSealFlow(SnapshotShareDomain):
    def __init__(self,case):
        with patch.object(snapshot_share_domain,'ShareArchiveDomain',ShareSealArchive):super().__init__(case)
    def clicked(self,role,name,view):
        if role=='archive' and name=='snapshot.share.archive.admission-seal':return self.archive.seal_native(view)
        return super().clicked(role,name,view)
