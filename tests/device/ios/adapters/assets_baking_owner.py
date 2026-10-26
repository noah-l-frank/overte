"""Retained original backend rebake joined to one ordinary owned checkbox.

This owner proves neither model parsing/rendering nor whole Assets retirement.
An uncertain click remains owned by the normal UI journal and is never resent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters import asset_backend_evidence as evidence,asset_backend_rebake as rebake,asset_backend_work as work
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,pack,unpack
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_budget import operation
from ios.adapters.assets_files import original_bytes
from ios.adapters.assets_usage_owner import OwnedAssetsUsage

VERSION=1
SLOT='usage-bake-on'


class OwnedAssetsBaking:
    def __init__(self,usage,backend,store,*,lock):
        need(isinstance(usage,OwnedAssetsUsage) and isinstance(backend,OwnedAssetsBackend) and usage.source is backend.upload
            and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.usage,self.backend,self.store,self.lock=usage,backend,store,lock;self.monotonic=usage.monotonic
        self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.usage.guard();self.backend.guard()
        need(all(same(owner.store.read(),owner.previous) for owner in (self,self.usage,self.backend)));return True
    def digest(self):return hashlib.sha256(original_bytes(next(iter(self.usage.source.files.state['files'].values())))).hexdigest()
    def row(self,index):need(integer(index,1,len(self.backend.state['samples'])));return self.backend.state['samples'][index-1]

    def admissible(self,index):
        packet=self.backend.packet(self.row(index));need(evidence.ready_source(packet) and evidence.mapping(packet).get(self.usage.path())==self.digest()
            )
        if not all(work.drained(packet['source'][key]) for key in ('workBefore','workAfter')):return False
        original=evidence.blobs(packet).get(self.digest());need(original is not None)
        from adapters.asset_backend_source import file
        need(file(original,name=self.digest(),limit=32768,required=True)==original_bytes(next(iter(self.usage.source.files.state['files'].values()))))
        return True

    def baseline(self,index,slot):
        need(self.admissible(index));packet=self.backend.packet(self.row(index))
        proof=self.usage.proof(slot);need(proof['binding']['server']==packet['serverId'] and proof['binding']['domainId']==packet['domainId']);return packet

    def input(self):
        matches=[entry for entry in self.usage.state['inputs'] if entry['slot']==SLOT]
        need(len(matches)==1 and matches[0]['id']=='assets.baking' and matches[0]['effect']==dict(kind='baking-ui',checked=True));return matches[0]

    def proof(self,index):
        base,current=self.row(self.state['baseline']),self.row(index)
        return rebake.ready(self.backend.raw(base),base['query'],self.backend.raw(current),current['query'],self.backend.config_for_decode(),self.usage.path(),self.digest())

    def decode(self,value):
        source=self.usage.source
        exact(value,{'iosAssetsBakingOwnerVersion','binding','runId','role','fileOwnerToken','page','path','backendConfiguration','payload'})
        need(type(value['iosAssetsBakingOwnerVersion']) is int and value['iosAssetsBakingOwnerVersion']==VERSION and same(value['binding'],source.binding)
            and value['runId']==source.files.run and value['role']==source.role and value['fileOwnerToken']==source.files.state['token']
            and value['page']==source.state['page'] and value['path']==self.usage.path() and same(value['backendConfiguration'],self.backend.config))
        states=unpack(value['payload']);need(len(states)==1);state=states[0];exact(state,{'phase','admissions','baseline','readSlot','observations','result'})
        need(state['phase'] in ('reserved','baseline','issued','qualified') and type(state['observations']) is list and len(state['observations'])<=16
            and state['observations']==sorted(set(state['observations'])) and type(state['admissions']) is list and len(state['admissions'])<=8 and state['admissions']==sorted(set(state['admissions'])))
        for number,index in enumerate(state['admissions'],1):
            row=self.row(index);need(row['slot']=='usage-bake-baseline-'+str(number) and row['parts'] is not None and row['parts']['complete'])
        if state['baseline'] is not None:
            need(state['baseline'] in state['admissions'] and state['readSlot']=='usage-bake-admission-'+str(state['admissions'].index(state['baseline'])+1));self.baseline(state['baseline'],state['readSlot'])
        else:need(state['phase']=='reserved' and state['readSlot'] is None and not state['observations'] and state['result'] is None)
        if state['phase']!='reserved':need(state['baseline'] is not None)
        for index in state['observations']:need(index>state['baseline']);row=self.row(index);need(row['parts'] is not None and row['parts']['complete'])
        if state['phase'] in ('issued','qualified'):need(self.input()['command'] is not None)
        if state['result'] is not None:
            exact(state['result'],{'sample','proof'});need(state['result']['sample'] in state['observations'] and self.input()['resolvedBy'] is not None)
            base,current=self.row(state['baseline']),self.row(state['result']['sample'])
            proof=rebake.ready(self.backend.raw(base),base['query'],self.backend.raw(current),current['query'],self.backend.config_for_decode(),self.usage.path(),self.digest())
            need(proof is not None and same(proof,state['result']['proof']))
        if state['phase']=='qualified':need(state['result'] is not None)
        return state

    def save(self):
        self.guard();need(same(self.store.read(),self.previous));source=self.usage.source
        value=dict(iosAssetsBakingOwnerVersion=VERSION,binding=source.binding,runId=source.files.run,role=source.role,fileOwnerToken=source.files.state['token'],
            page=source.state['page'],path=self.usage.path(),backendConfiguration=self.backend.config,payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    @operation
    def reserve(self):
        need(self.state is None and self.usage.state is not None and self.usage.state['clientClosedBy'] is None)
        self.state=dict(phase='reserved',admissions=[],baseline=None,readSlot=None,observations=[],result=None);self.save()

    @operation
    def start(self):
        need(self.state['phase'] in ('reserved','baseline') and len(self.state['admissions'])<8 and not any(entry['slot']==SLOT for entry in self.usage.state['inputs']))
        if self.backend.state is None:self.backend.reserve()
        number=len(self.state['admissions'])+1;slot='usage-bake-baseline-'+str(number)
        packet=self.backend.checkpoint(slot,self.usage.source.files.state['ticket'])
        if packet is None:return None
        index=next(index for index,row in enumerate(self.backend.state['samples'],1) if row['slot']==slot);self.state['admissions'].append(index);self.save()
        if not self.admissible(index):return None
        read_slot='usage-bake-admission-'+str(number);self.usage.read(read_slot)
        self.baseline(index,read_slot);self.state.update(phase='baseline',baseline=index,readSlot=read_slot);self.save()
        try:packet=self.usage.baking(True)
        except BaseException as primary:
            matches=[entry for entry in self.usage.state['inputs'] if entry['slot']==SLOT]
            if matches and matches[0]['command'] is not None:
                self.state['phase']='issued'
                # The UI journal remains authoritative if this parent write
                # also fails; never convert the original error into a retry.
                try:self.save()
                except BaseException as secondary:primary.add_note('Retaining the issued rebake parent also failed: '+type(secondary).__name__)
            raise
        self.state['phase']='issued';self.save()
        return packet

    @operation
    def recover(self):
        need(self.state['phase'] in ('baseline','issued') and self.state['baseline'] is not None);entry=self.input();need(entry['command'] is not None)
        if entry['resolvedBy'] is None:self.usage.resolve(SLOT)
        self.state['phase']='issued';self.save()

    @operation
    def qualify(self):
        self.guard();need(self.state['phase'] in ('issued','qualified'))
        if self.state['phase']=='qualified':
            self.usage.source.decode(self.usage.source.previous);self.usage.decode(self.usage.previous);self.backend.decode(self.backend.previous)
            self.decode(self.previous);return deepcopy(self.state['result']['proof'])
        need(self.input()['resolvedBy'] is not None and len(self.state['observations'])<16)
        slot='usage-bake-result-'+str(len(self.state['observations'])+1);packet=self.backend.checkpoint(slot,self.usage.source.files.state['ticket'])
        if packet is None:return None
        index=next(index for index,row in enumerate(self.backend.state['samples'],1) if row['slot']==slot)
        need(index not in self.state['observations']);self.state['observations'].append(index);self.save();proof=self.proof(index)
        if proof is None:return None
        self.state.update(phase='qualified',result=dict(sample=index,proof=proof));self.save();return deepcopy(proof)
