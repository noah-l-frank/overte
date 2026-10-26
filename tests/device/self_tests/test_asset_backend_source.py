"""Device-free backend protocol counterexamples with real files/weak holders.

Native task bodies, Qt, AssetServer, oven and native clocks are declared models;
these tests do not compile or execute the new C++ instrumentation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import gc
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import weakref
from adapters import asset_backend_source as source, asset_backend_work as work
from adapters.normal_ui import NativeUIError


def uid():return str(uuid.uuid4())
def stamp(t=100):return dict(epochMs=10000+t,monotonicMs=t)


class Holder:pass


class NativeWorkModel:
    """Explicit native event model; weak ownership itself is Python-real."""
    def __init__(self,kind='bake'):
        self.kind=kind;self.t=1;self.events=[];self.sequence=0;self.instance=uid();self.id=uid()
        self.inputs=dict(hash='a'*64 if kind=='bake' else '',path='/e2e/model.fbx' if kind=='bake' else '',senderId='' if kind=='bake' else uid(),messageId='')
        self.holders={name:Holder() for name in (('lease','owner','object') if kind=='bake' else ('lease',))}
        self.weak={key:weakref.ref(item) for key,item in self.holders.items()};self.expired={};self.created=stamp(self.t)
        self.event('queued',dict(inputs=deepcopy(self.inputs)))
        if kind=='bake':self.event('owner-bound',{})
    def event(self,kind,details):
        self.t+=1;self.events.append(dict(sequence=len(self.events)+1,eventId=uid(),kind=kind,clock=stamp(self.t),details=details))
    def enter(self,callback=False):
        body=uid();self.event('callback-enter' if callback else 'run-enter',dict(bodyId=body,callback='bake-complete' if callback else 'run'));return body
    def leave(self,body,callback=False):self.event('callback-return' if callback else 'run-return',dict(bodyId=body,callback='bake-complete' if callback else 'run'))
    def expire(self,*keys):
        for key in keys:self.holders.pop(key,None)
        gc.collect()
    def capture(self,**changes):
        for key,ref in self.weak.items():
            if ref() is None and key not in self.expired:
                self.t+=1;self.expired[key]=stamp(self.t);self.event(key+'-expired-observed',{})
        self.t+=1;self.sequence+=1;row=dict(id=self.id,kind=self.kind,inputs=deepcopy(self.inputs),created=self.created,ownerKnown=self.kind=='bake',events=deepcopy(self.events))
        for key in ('lease','owner','object'):
            row[key+'Alive']=self.weak[key]() is not None if key in self.weak else None;row[key+'Expired']=self.expired.get(key)
        for kind,prefix in (('run','run'),('callback','callback')):
            row[prefix+'Entered']=sum(event['kind']==kind+'-enter' for event in self.events);row[prefix+'Returned']=sum(event['kind']==kind+'-return' for event in self.events)
        row['pendingRuns']=row['runEntered']-row['runReturned'];row['pendingBodies']=row['callbackEntered']-row['callbackReturned']
        value=dict(assetBackendWorkVersion=1,instance=self.instance,sequence=self.sequence,processId=123,clock=stamp(self.t),available=True,complete=True,jobs=[row],pendingBakes=[],transferActiveThreads=0,bakeActiveThreads=0,queuedRequests=0,queueingRequests=False)
        value.update(changes);return value


def kernel(value,directory=False):
    result=dict(device=str(value.st_dev),inode=str(value.st_ino),uid=str(value.st_uid),mode=str(value.st_mode&0o7777),links=str(value.st_nlink),
        modifiedSeconds=str(value.st_mtime_ns//10**9),modifiedNanoseconds=str(value.st_mtime_ns%10**9),changedSeconds=str(value.st_ctime_ns//10**9),changedNanoseconds=str(value.st_ctime_ns%10**9))
    if not directory:result['bytes']=str(value.st_size)
    return result


class BackendWorkTests(unittest.TestCase):
    def test_real_weak_expiry_never_substitutes_for_pending_original_bodies(self):
        model=NativeWorkModel();run=model.enter();callback=model.enter(True);model.expire('lease','owner','object');value=model.capture()
        self.assertFalse(work.drained(value));model.leave(callback,True);self.assertFalse(work.drained(model.capture()));model.leave(run)
        final=model.capture();self.assertTrue(work.drained(final));work.accept(value,final)
    def test_run_and_signal_return_do_not_retire_actual_shared_and_qobject_owners(self):
        model=NativeWorkModel();run=model.enter();callback=model.enter(True);model.leave(callback,True);model.leave(run)
        self.assertFalse(work.drained(model.capture()));model.expire('lease','owner');self.assertFalse(work.drained(model.capture()));model.expire('object');self.assertTrue(work.drained(model.capture()))
    def test_actual_pending_map_pool_and_queue_keep_responsibility_after_expiry(self):
        model=NativeWorkModel();body=model.enter();callback=model.enter(True);model.leave(callback,True);model.leave(body);model.expire('lease','owner','object');self.assertTrue(work.drained(model.capture()))
        for changes in (dict(pendingBakes=[dict(id=model.id,hash='a'*64)]),dict(transferActiveThreads=1),dict(bakeActiveThreads=1),dict(queuedRequests=1),dict(queueingRequests=True),dict(available=False),dict(complete=False)):
            with self.subTest(changes=changes):self.assertFalse(work.drained(model.capture(**changes)))
    def test_original_event_prefix_and_expiry_cannot_be_rewritten_or_resurrected(self):
        model=NativeWorkModel();old=model.capture();new=model.capture();new['jobs'][0]['events'][0]['details']['inputs']['hash']='b'*64
        with self.assertRaises(NativeUIError):work.accept(old,new)
        model.expire('lease');old=model.capture();model.holders['lease']=Holder();model.weak['lease']=weakref.ref(model.holders['lease'])
        with self.assertRaises(NativeUIError):work.accept(old,model.capture())
    def test_unobserved_input_hash_and_sticky_product_flag_cannot_supply_completion(self):
        model=NativeWorkModel('upload');model.inputs['hash']='b'*64
        with self.assertRaises(NativeUIError):work.validate(model.capture())
        model=NativeWorkModel();value=model.capture();value['jobs'][0]['isBaking']=False
        with self.assertRaises(NativeUIError):work.validate(value)
    def test_task_run_return_must_close_the_actual_body_and_kind(self):
        model=NativeWorkModel();body=model.enter();model.leave(uid());value=model.capture()
        with self.assertRaises(NativeUIError):work.validate(value)

    def test_expired_unentered_queue_entry_or_unobserved_bake_callback_is_not_drained(self):
        model=NativeWorkModel('upload');model.expire('lease');self.assertFalse(work.drained(model.capture()))
        model=NativeWorkModel();body=model.enter();model.leave(body);model.expire('lease','owner','object');self.assertFalse(work.drained(model.capture()))


class BackendSourceTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name);self.root.chmod(0o700)
        self.data=self.root/'product';self.data.mkdir();self.files=self.data/'files';self.files.mkdir();self.export=self.root/'source';self.export.mkdir(mode=0o700)
        self.server,self.domain=uid(),uid();self.work=NativeWorkModel();body=self.work.enter();callback=self.work.enter(True);self.work.leave(callback,True);self.work.leave(body);self.work.expire('lease','owner','object')
    def record(self,path,raw):
        path.write_bytes(raw);path.chmod(0o600);return dict(name=path.name,exists=True,identity=kernel(path.stat()),body=dict(retained=True,base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))
    def dataset(self):
        raw=b'actual observed blob';blob=self.record(self.files/hashlib.sha256(raw).hexdigest(),raw);mapping={'/foreign/model.fbx':blob['name']};mapfile=self.record(self.data/'map.json',json.dumps(mapping,indent=2).encode())
        directory=lambda path:dict(configuredPath=str(path),canonicalPath=str(path),identity=kernel(path.stat(),True))
        return dict(assetBackendSnapshotVersion=1,available=True,complete=True,serverId=self.server,domainId=self.domain,resourcesRoot=directory(self.data),filesRoot=directory(self.files),memoryMappings=[dict(path=key,hash=value) for key,value in mapping.items()],mapFile=mapfile,persistedMappings=mapping,blobs=[blob],unknownEntries=[],meta=[],workBefore=self.work.capture(),workAfter=self.work.capture(),nodes=[dict(nodeId=uid(),type=73,canWriteAssets=False)],hiddenPrefix='/.baked/',modelBakeVersion=1,modelOutputName='asset.fbx',bakeableModelExtensions=['fbx'])
    def original(self):
        value=dict(assetBackendAdmissionVersion=1,instance=uid(),processId=123,role='asset-server',ownerSha256='b'*64,serverId=self.server,domainId=self.domain,sourceRootIdentity={key:kernel(self.export.stat(),True)[key] for key in ('device','inode')},dataRoot=str(self.data),dataRootIdentity={key:kernel(self.data.stat(),True)[key] for key in ('device','inode')},clockDomain='asset-server-native',clock=stamp(1))
        query=dict(schemaVersion=1,commandId='assets-'+'a'*32,action='feature-assets-backend-observe',runId='c'*32,ticket='d'*32,processId=123,instance=value['instance'])
        packet=dict(assetBackendObservationVersion=1,requestId=query['commandId'],instance=value['instance'],sequence=1,runId=query['runId'],ticket=query['ticket'],processId=123,ownerSha256=value['ownerSha256'],serverId=self.server,domainId=self.domain,admissionSha256='e'*64,clockDomain='asset-server-native',clockBefore=stamp(1),clockAfter=stamp(100),source=self.dataset())
        return value,query,packet
    def test_actual_files_hashes_mapping_bytes_and_independent_clock_domain(self):
        original,query,packet=self.original();source.observation(packet,query,original,'e'*64);self.assertTrue(work.drained(packet['source']['workAfter']))
        raw=json.dumps(packet).encode();path=self.export/('asset-backend-original-'+query['commandId']+'.json');row=self.record(path,raw)
        receipt=dict(assetBackendSavedVersion=1,instance=original['instance'],requestId=query['commandId'],processId=123,admissionSha256='e'*64,original=dict(file=path.name,identity=row['identity'],sha256=hashlib.sha256(raw).hexdigest()));source.saved(receipt,packet,raw)
    def test_desired_state_or_foreign_process_cannot_enter_closed_passive_query(self):
        original,query,_=self.original()
        for change in (dict(expectedMappings=[]),dict(processId=124),dict(schemaVersion=True),dict(action='delete-mappings')):
            wrong=deepcopy(query);wrong.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.query(wrong,original)
    def test_missing_hook_or_cross_process_clock_and_root_identity_are_unavailable(self):
        original,query,packet=self.original()
        for mutate in (lambda p:p.update(source={}),lambda p:p.update(clockDomain='device-native'),lambda p:p['source']['resourcesRoot']['identity'].update(inode='999'),lambda p:p['source']['workAfter'].update(processId=124),lambda p:p.update(clockAfter=stamp(1))):
            wrong=deepcopy(packet);mutate(wrong)
            with self.assertRaises(NativeUIError):source.observation(wrong,query,original,'e'*64)
    def test_retained_body_size_hash_and_persisted_memory_mismatch_are_rejected(self):
        value=self.dataset()
        for mutate in (lambda p:p['blobs'][0]['identity'].update(bytes='1'),lambda p:p['blobs'][0]['body'].update(sha256='f'*64),lambda p:p['persistedMappings'].update({'/new':'f'*64}),lambda p:p['mapFile']['body'].update(base64=base64.b64encode(b'{"same":1,"same":2}').decode())):
            wrong=deepcopy(value);mutate(wrong)
            with self.assertRaises(NativeUIError):source.snapshot(wrong,pid=123)
    def test_large_unknown_body_stays_unknown_and_cannot_be_filled_by_a_meta_verdict(self):
        value=self.dataset();body=value['blobs'][0]['body'];body.update(retained=False,base64=None,sha256=None);source.snapshot(value,pid=123)
        body['sha256']=value['blobs'][0]['name']
        with self.assertRaises(NativeUIError):source.snapshot(value,pid=123)
    def test_saved_receipt_is_bound_to_actual_original_bytes_and_inode(self):
        _,_,packet=self.original();raw=json.dumps(packet).encode();name='asset-backend-original-'+packet['requestId']+'.json';row=self.record(self.export/name,raw)
        saved=dict(assetBackendSavedVersion=1,instance=packet['instance'],requestId=packet['requestId'],processId=123,admissionSha256='e'*64,original=dict(file=name,identity=row['identity'],sha256=hashlib.sha256(raw).hexdigest()))
        with self.assertRaises(NativeUIError):source.saved(saved,packet,raw+b' ')
        saved['original']['identity']['links']='2'
        with self.assertRaises(NativeUIError):source.saved(saved,packet,raw)
