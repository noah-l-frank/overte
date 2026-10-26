"""Actual named host unlinks and synced intent under declared native producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_source_retirement import NAMES,INTENT,ALL_NAMES
from ios.self_tests import snapshot_share_domain
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain
from ios.self_tests.snapshot_share_seal_domain import parent_identity
from ios.self_tests.snapshot_share_inventory_domain import SourceInventoryArchive,SourceInventoryFlow,stat_revision


class SourceRetirementArchive(SourceInventoryArchive):
    def __init__(self,case,flow):
        super().__init__(case,flow);self.source_retire_calls=0;self.source_retire_issued=False;self.source_retire_text='';self.source_inspect_text=''
        self.source_sync_unknown_at=None;self.ignore_source_retire=False;self.source_observation_errors=False;self.source_queries=set();self.source_unlinks=[]
    def source_ready(self):
        if self.source_retire_issued or not self.inventory_text:return False
        packet=json.loads(self.inventory_text);return packet['current'] and packet['readersClosed'] and self.global_frozen
    def source_census(self,mask):
        expected={name for at,name in enumerate(ALL_NAMES) if mask&(1<<at)}
        return {path.name for path in self.documents.iterdir() if path.name.startswith(('snapshot-share-','.record-','.companion-'))}==expected
    def source_retire(self,view):
        self.source_retire_calls+=1
        if self.ignore_source_retire or not self.source_ready():return
        self.source_retire_issued=True;nonce=view.fields['snapshot.share.archive.query'];self.source_queries.add(nonce)
        inventory=json.loads(self.inventory_text);files=[{key:value for key,value in pin.items() if key!='data'} for pin in inventory['outputs']]
        record=dict(snapshotShareSourceRetirementVersion=1,requestId=nonce,runId=self.imported['runId'],processId=self.pid,bundleId=self.target['appId'],
            instance=self.catalog_instance,sourceInstance=inventory['sourceInstance'],sourceBirthClock=deepcopy(self.catalog_born),
            inventorySha256=hashlib.sha256(self.inventory_text.encode()).hexdigest(),parentIdentity=self.parent,outputs=files,clockBefore=self.clock(),
            clockAfter=None,intent=None,steps=[],readersClosed=False,parentDescriptorClosed=False,complete=False)
        directory=os.open(self.documents,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            valid=parent_identity(self.documents)==self.parent and self.source_census(63)
            for pin in files:
                try:valid=valid and pin==self.source_pin(pin['name'])[0]
                except (NativeUIError,OSError):valid=False
            if valid:
                initial=json.dumps(record,separators=(',',':')).encode()
                try:
                    descriptor=os.open(INTENT,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
                    with os.fdopen(descriptor,'wb') as output:output.write(initial);output.flush();os.fsync(output.fileno())
                    pin,raw=self.source_pin(INTENT);need(raw==initial);os.fsync(directory);record['intent']=dict(pin,data=base64.b64encode(raw).decode())
                except OSError:valid=False
            valid=valid and record['intent'] is not None and self.source_census(127);record['readersClosed']=valid;mask=127 if record['intent'] is not None else 63
            for at,pin in enumerate([*files,*([record['intent']] if record['intent'] is not None else [])],1):
                if not valid:break
                unlinked=False;synced=False;absent=False
                try:
                    named=os.stat(pin['name'],dir_fd=directory,follow_symlinks=False)
                    need(parent_identity(self.documents)==self.parent and stat_revision(named)==pin['revision'])
                    os.unlink(pin['name'],dir_fd=directory);unlinked=True;self.source_unlinks.append(pin['name']);mask&=~(1<<(at-1))
                    os.fsync(directory);synced=self.source_sync_unknown_at!=at
                    try:os.stat(pin['name'],dir_fd=directory,follow_symlinks=False)
                    except FileNotFoundError:absent=parent_identity(self.documents)==self.parent
                except (OSError,NativeUIError):pass
                record['steps'].append(dict(sequence=at,name=pin['name'],unlinked=unlinked,synchronized=synced,absent=absent,clock=self.clock()))
                valid=unlinked and synced and absent and self.source_census(mask)
            valid=valid and mask==0 and len(record['steps'])==7 and parent_identity(self.documents)==self.parent and self.source_census(0)
        finally:os.close(directory)
        record.update(parentDescriptorClosed=True,complete=valid,clockAfter=self.clock());self.source_retire_text=json.dumps(record,separators=(',',':'));view.output=self.source_retire_text
    def source_inspect(self,view):
        need(self.source_retire_text);nonce=view.fields['snapshot.share.archive.query'];need(nonce not in self.source_queries);self.source_queries.add(nonce)
        record=json.loads(self.source_retire_text);before=self.clock();files=[];errors=self.source_observation_errors
        directory=os.open(self.documents,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            for name in ALL_NAMES:
                absent=False
                try:os.stat(name,dir_fd=directory,follow_symlinks=False)
                except FileNotFoundError:absent=parent_identity(self.documents)==self.parent
                except OSError:errors=True
                files.append(dict(name=name,absent=absent))
            empty=self.source_census(0);errors=errors or parent_identity(self.documents)!=self.parent
        finally:os.close(directory)
        packet=dict(snapshotShareSourceRetirementObservationVersion=1,requestId=nonce,runId=record['runId'],processId=self.pid,bundleId=self.target['appId'],
            instance=self.catalog_instance,sourceInstance=record['sourceInstance'],retirementSha256=hashlib.sha256(self.source_retire_text.encode()).hexdigest(),
            parentIdentity=self.parent,clockBefore=before,clockAfter=self.clock(),files=files,sourceNamespaceEmpty=empty,observationErrors=errors,parentDescriptorClosed=True)
        self.source_inspect_text=json.dumps(packet,separators=(',',':'));view.output=self.source_inspect_text
    def call(self,method,path,body=None):
        if self.ui is not None and '/element/archive-' in path:
            name=self.ui.names[path.split('/')[4]]
            if path.endswith('/enabled') and name=='snapshot.share.archive.source-retire':return self.source_ready()
        value=super().call(method,path,body)
        if path.endswith('/attribute/value') and '/element/archive-' in path:
            name=self.ui.names[path.split('/')[4]]
            if name=='snapshot.share.archive.source-retirement-original':return self.source_retire_text
            if name=='snapshot.share.archive.source-retirement-observation-original':return self.source_inspect_text
        return value


class SourceRetirementFlow(SourceInventoryFlow):
    def __init__(self,case):
        with patch.object(snapshot_share_domain,'ShareArchiveDomain',SourceRetirementArchive):SnapshotShareDomain.__init__(self,case)
    def clicked(self,role,name,view):
        if role=='archive' and name=='snapshot.share.archive.source-retire':return self.archive.source_retire(view)
        if role=='archive' and name=='snapshot.share.archive.source-retire-inspect':return self.archive.source_inspect(view)
        return super().clicked(role,name,view)
    def visible(self,role,name):
        if role!='archive':return super().visible(role,name)
        if not self.archive.foreground:return False
        frozen=self.archive.global_frozen;imported=getattr(self.archive,'imported',None) is not None
        if name in {'snapshot.share.archive.run','snapshot.share.archive.import'}:return not frozen and not imported
        if name in {'snapshot.share.archive.offset','snapshot.share.archive.chunk','snapshot.share.archive.retire','snapshot.share.archive.retire-inspect','snapshot.share.archive.admission-seal'}:return imported and not frozen
        if name=='snapshot.share.archive.query':return imported or frozen
        if name.startswith('snapshot.share.archive.source-') or name=='snapshot.share.archive.admission-seal-original':return frozen
        return False
