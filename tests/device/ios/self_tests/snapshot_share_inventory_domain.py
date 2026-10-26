"""Modeled native global publishers over real first-pinned host file objects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
import stat
import uuid
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_inventory import NAMES
from ios.self_tests import snapshot_share_domain
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain
from ios.self_tests.snapshot_share_seal_domain import ShareSealArchive,ShareSealFlow,parent_identity


def stat_revision(value):
    fields=(value.st_dev,value.st_ino,value.st_mode,value.st_nlink,value.st_uid,value.st_gid,value.st_size,
        value.st_mtime_ns//10**9,value.st_mtime_ns%10**9,value.st_ctime_ns//10**9,value.st_ctime_ns%10**9)
    return hashlib.sha256(':'.join(map(str,fields)).encode()).hexdigest()


class SourceInventoryArchive(ShareSealArchive):
    def __init__(self,case,flow):
        super().__init__(case,flow);self.global_pins={};self.global_raw={};self.global_frozen=False;self.catalog_instance=uuid.uuid4().hex
        self.catalog_born=self.clock();self.inventory_text='';self.inventory_calls=0;self.ignore_inventory=False;self.lost_inventory_value=False
    def clock(self,offset=0):
        if getattr(self,'retirement_start',None) is not None:
            return {key:value+offset for key,value in self.retirement_clock().items()}
        return super().clock(offset)
    def source_pin(self,name):
        path=self.documents/name;descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        with os.fdopen(descriptor,'rb') as file:
            before=os.fstat(file.fileno());need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid()
                and stat.S_IMODE(before.st_mode)==0o600 and 0<before.st_size<=720896)
            raw=file.read(720897);need(len(raw)==before.st_size and stat_revision(before)==stat_revision(os.fstat(file.fileno()))==stat_revision(path.lstat()))
        return dict(name=name,revision=stat_revision(before),sha256=hashlib.sha256(raw).hexdigest(),byteCount=len(raw),parentIdentity=parent_identity(self.documents)),raw
    def before_publish(self,names):
        need(not self.global_frozen and parent_identity(self.documents)==self.parent)
        for name in names:
            if name in self.global_pins:need(self.global_pins[name]==self.source_pin(name)[0])
            else:need(not os.path.lexists(self.documents/name))
    def retain_published_globals(self,names):
        for name in names:self.global_pins[name],self.global_raw[name]=self.source_pin(name)
    def import_original(self,view):need(not self.global_frozen);return super().import_original(view)
    def chunk(self,view):
        self.before_publish(NAMES[2:3]);super().chunk(view);self.retain_published_globals(NAMES[2:3])
    def retire(self,view):
        self.before_publish(NAMES[3:5]);super().retire(view);self.retain_published_globals(NAMES[3:5])
    def inspect_retirement(self,view):
        self.before_publish(NAMES[5:6]);super().inspect_retirement(view);self.retain_published_globals(NAMES[5:6])
    def seal_native(self,view):
        super().seal_native(view)
        if self.sealed:self.global_frozen=True
    def inventory_ready(self):return self.global_frozen and self.original is not None and self.original['readerClosed'] and len(self.global_pins)==4 and not self.inventory_text
    def inventory_native(self,view):
        self.inventory_calls+=1
        if self.ignore_inventory or not self.inventory_ready():return
        before=self.clock();expected=[deepcopy(self.published[action]) for action in ('identity','clock')]
        expected.extend(deepcopy(self.global_pins[name]) for name in NAMES[2:]);current=parent_identity(self.documents)==self.parent
        names={path.name for path in self.documents.iterdir() if path.name.startswith(('snapshot-share-','.record-','.companion-'))}
        current=current and names==set(NAMES)
        for pin in expected:
            try:current=current and pin==self.source_pin(pin['name'])[0]
            except (OSError,ValueError,TypeError,NativeUIError):current=False
            if pin['name'] in NAMES[3:5]:pin['data']=base64.b64encode(self.global_raw[pin['name']]).decode()
        packet=dict(snapshotShareSourceInventoryVersion=1,requestId=view.fields['snapshot.share.archive.query'],processId=self.pid,bundleId=self.target['appId'],
            instance=self.catalog_instance,sourceBirthClock=deepcopy(self.catalog_born),sourceInstance=self.original['instance'],
            admissionSealSha256=hashlib.sha256(self.original_text.encode('utf-8')).hexdigest(),clockBefore=before,clockAfter=self.clock(),
            parentIdentity=self.parent,outputs=expected,frozen=self.global_frozen,current=current,readersClosed=current)
        self.inventory_text=json.dumps(packet,separators=(',',':'));view.output=self.inventory_text
    def call(self,method,path,body=None):
        if self.ui is not None and path.endswith('/enabled') and '/element/archive-' in path and self.ui.names[path.split('/')[4]]=='snapshot.share.archive.source-inventory':
            return self.inventory_ready()
        value=super().call(method,path,body)
        if path.endswith('/attribute/value') and '/element/archive-' in path and self.ui.names[path.split('/')[4]]=='snapshot.share.archive.source-inventory-original':
            if self.lost_inventory_value:self.lost_inventory_value=False;raise OSError('Declared lost frozen source value return')
            return self.inventory_text
        return value


class SourceInventoryFlow(ShareSealFlow):
    def __init__(self,case):
        with patch.object(snapshot_share_domain,'ShareArchiveDomain',SourceInventoryArchive):SnapshotShareDomain.__init__(self,case)
    def clicked(self,role,name,view):
        if role=='archive' and name=='snapshot.share.archive.source-inventory':return self.archive.inventory_native(view)
        return super().clicked(role,name,view)
