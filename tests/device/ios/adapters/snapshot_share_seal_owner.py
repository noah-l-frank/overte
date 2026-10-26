"""One ordinary Share admission seal; exact original close result, never resend."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from copy import deepcopy
import re
import time
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_share_actions import SnapshotShareUIAction
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.adapters import snapshot_share_seal as source


class ShareAdmissionSealAction(SnapshotShareUIAction):
    _fields={'snapshot.share.archive.admission-seal':{'snapshot.share.archive.query'}}
    _store_prefix='share-admission-seal-slot'
    _namespace='share-admission-seal-output'
    _schema='shareAdmissionSealOutput'
    _owner_key='snapshotShareAdmissionSealUIActionVersion'
    _frame_key='snapshotShareAdmissionSealUIOutputVersion'
    _output_control='snapshot.share.archive.admission-seal'
    _output_locator='snapshot.share.archive.admission-seal-original'


class SnapshotShareAdmissionSealOwner:
    def __init__(self,ctx,lock,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(ctx,SnapshotShareArchiveContext) and isinstance(lock,ScriptSourceLock) and ctx.admission.lock is lock)
        self.ctx,self.lock,self.historical=ctx,lock,False
        self.binding,self.run,self.fixture_url=deepcopy(context(ctx.binding)),identifier(ctx.admission.run),ctx.admission.fixture_url
        self.admission=ctx.admission;self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.setup()

    @classmethod
    def history(cls,store,lock,binding,run,fixture_url,artifact_path,admission_store):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result=object.__new__(cls);result.ctx=None;result.lock=lock;result.historical=True
        result.binding,result.run,result.fixture_url=deepcopy(context(binding)),identifier(run),fixture_url
        result.epoch_ms=lambda:time.time()*1000;result.monotonic=time.monotonic
        result.admission=IOSSnapshotShareAdmissionOwner.archive(admission_store,lock,binding,run,fixture_url,artifact_path)
        result.setup(store);need(result.previous is not None);return result

    def setup(self,store=None):
        self.lock.assert_held();self.admission.result();self.admission_hash=digest(self.admission.previous)
        self.root=self.admission.store.path.parent;self.store=store or PrivateFeatureState(self.root/'share-admission-seal-owner.json')
        need(self.store.path==self.root/'share-admission-seal-owner.json' and self.lock.path==self.root/'script-feature-sources.lock')
        self.previous=self.store.read();self.state=dict(nonce=None,slotSha256=None,result=None)
        if self.previous is not None:self.state=self.load(self.previous)
        else:self.inventory(set())
    def bound(self):
        self.lock.assert_held();self.admission.bound();need(same(self.store.read(),self.previous) and digest(self.admission.previous)==self.admission_hash);return True
    def check(self):
        self.bound()
        if not self.historical:self.ctx.probe(True)
        return True
    def envelope(self):return dict(snapshotShareAdmissionSealOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,
        admissionSha256=self.admission_hash,payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.check();value=self.envelope();self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)
    def action(self,historical=False):
        need(self.state['nonce'] is not None and (historical or not self.historical))
        plan=dict(label='seal-original-admission',control='snapshot.share.archive.admission-seal',selector=None,
            fields=[['snapshot.share.archive.query',self.state['nonce']]])
        return ShareAdmissionSealAction(self.root,self.lock,self.binding,self.run,1,plan,self.bound if historical else self.check,
            client=None if historical else self.ctx.client,session=None if historical else self.ctx.session,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,historical=historical)
    def inventory(self,allowed):
        for path in self.root.iterdir():
            if path.name.startswith('share-admission-seal-'):need(path==self.store.path or path in allowed)
    def load(self,value):
        exact(value,{'snapshotShareAdmissionSealOwnerVersion','binding','runId','fixtureUrl','admissionSha256','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['snapshotShareAdmissionSealOwnerVersion']) is int and value['snapshotShareAdmissionSealOwnerVersion']==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()));allowed=set()
            if state['nonce'] is not None:
                need(type(state['nonce']) is str and re.fullmatch('ios-[a-f0-9]{32}',state['nonce']));action=self.action(True);allowed.add(action.store.path)
                if action.state['wire'] is not None:allowed.add(action.files.path(action.state['wire']))
                if action.state['proof'] is not None:allowed.add(action.files.path(action.files.expand(action.state['proof'])))
                if state['slotSha256'] is not None:need(action.previous is not None and digest(action.previous)==state['slotSha256']);self.original()
                if state['result'] is not None:need(same(state['result'],self.proof()))
            else:need(state['slotSha256'] is None and state['result'] is None)
            self.inventory(allowed)
        finally:self.state=prior
        return deepcopy(state)
    def original(self):
        need(self.state['slotSha256'] is not None);action=self.action(True);need(digest(action.previous)==self.state['slotSha256'])
        raw=action.original();packet=source.original(decode(raw.decode('utf-8')),self.state['nonce'],self.admission)
        return packet,raw
    def proof(self):
        packet,raw=self.original();source.qualified(packet);action=self.action(True);action.qualified()
        ref=action.files.expand(action.state['proof']);frame=action.files.read(ref)
        need(packet['clockAfter']['monotonicMs']-packet['clockBefore']['monotonicMs']<=frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs']+250)
        return dict(snapshotShareAdmissionSealedVersion=1,runId=self.run,admissionSha256=self.admission_hash,nativeOriginalSha256=hashlib.sha256(raw).hexdigest(),
            processId=packet['processId'],sourceInstance=packet['instance'],bundleRootIdentity=packet['bundleRootIdentity'],outputs=deepcopy(packet['outputs']),
            admissionReaderClosed=True,sourceOutputsRetirementRequired=True,archiveProcessRetirementRequired=True,wholeFeatureRequired=True)
    @operation
    def seal(self):
        need(not self.historical);self.check()
        if self.state['result'] is not None:return self.proof()
        if self.state['nonce'] is None:self.state['nonce']='ios-'+uuid.uuid4().hex;self.save()
        action=self.action();action.execute()
        if self.state['slotSha256'] is None:self.state['slotSha256']=digest(action.previous);self.save()
        result=self.proof();self.state['result']=deepcopy(result);self.save();return result
