"""Retained actual geometry input joined to independent current baked bytes.

No input is issued here. Rendering, peers and all resource retirement remain
separate responsibilities after this observational join.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from adapters import asset_backend_evidence as evidence,asset_backend_source as backend_source,asset_backend_work as work
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import assets_model_facts as facts,assets_model_origin as origin
from ios.adapters.assets_baking_owner import OwnedAssetsBaking
from ios.adapters.assets_budget import operation
from ios.adapters.assets_parsed_sources import AssetsParsedSources
from ios.adapters.assets_usage_controls import project as usage_page

VERSION=1
SLOT='parsed-output-1'


class OwnedAssetsParsedInput:
    def __init__(self,sources,baking,store,*,lock):
        need(isinstance(sources,AssetsParsedSources) and isinstance(baking,OwnedAssetsBaking) and sources.usage is baking.usage
            and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.sources,self.model,self.baking,self.store,self.lock=sources,sources.model,baking,store,lock
        self.monotonic=sources.monotonic
        self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.sources.guard();self.baking.guard()
        need(all(same(owner.store.read(),owner.previous) for owner in (self,self.sources,self.model,self.baking)));return True

    def authoritative(self):
        need((self.previous is None and self.state is None) or self.previous is not None and same(self.decode(self.previous),self.state))

    def frame(self,index):
        matches=[frame for reference,frame in zip(self.sources.state['frames'],self.sources._cached)
            if self.sources.originals.expand(reference)['index']==index];need(len(matches)==1);return matches[0]

    def backend_row(self,index):
        need(integer(index,1,len(self.baking.backend.state['samples'])));return self.baking.backend.state['samples'][index-1]

    def proof(self,source_index,backend_index):
        self.model.decode(self.model.previous);self.baking.decode(self.baking.previous)
        need(self.model.state['creation'] is not None and self.baking.state['phase']=='qualified')
        frame=self.frame(source_index);originals=frame['originals'];creation=self.model.state['creation']['proof'];model=self.model
        geometry=facts.geometry(model.usage,model.native(model.state['baseline']),model.native(model.state['creation']['frame']),originals['createAfter'])
        parsed=origin.parsed_input(originals['origin'],creation['entityId']);need(parsed['modelUrl']==model.usage.url())
        baking=self.baking;backend=baking.backend;row=self.backend_row(backend_index)
        need(row['slot']==SLOT and row['parts'] is not None and row['parts']['complete'])
        packet=backend.packet(row);prior=backend.packet(baking.row(baking.state['result']['sample']));backend_source.accept(prior,packet)
        need(evidence.ready_source(packet) and all(work.drained(packet['source'][key]) for key in ('workBefore','workAfter'))
            and packet['domainId']==creation['domainId']==originals['origin']['source']['domainId'])
        page=usage_page(originals['ui'],model.usage.source.state['page']);binding=model.usage.proof(model.input()['admission']['slot'])['binding']
        need(page['domainId']==packet['domainId'] and binding['domainId']==packet['domainId'] and binding['server']==packet['serverId'])
        baked=baking.state['result']['proof'];mapping=evidence.mapping(packet)
        need(mapping.get(baking.usage.path())==baked['originalHash'] and mapping.get(baked['outputPath'])==baked['outputHash'])
        current_meta=[value for value in packet['source']['meta'] if value['originalHash']==baked['originalHash']]
        old_meta=[value for value in prior['source']['meta'] if value['originalHash']==baked['originalHash']]
        need(len(current_meta)==1 and same(current_meta,old_meta) and current_meta[0]['blobHash']==baked['metaHash'])
        blob=evidence.blobs(packet).get(baked['outputHash']);need(blob is not None)
        raw=backend_source.file(blob,name=baked['outputHash'],limit=32768,required=True)
        reader=next(value for value in originals['origin']['source']['history']['downloads'] if value['id']==parsed['readerId'])
        need(raw is not None and raw==base64.b64decode(reader['base64'],validate=True) and parsed['sha256']==baked['outputHash']
            and parsed['bytes']==baked['outputBytes']==len(raw))
        return dict(assetModelBakedInputProofVersion=VERSION,runId=creation['runId'],processId=creation['processId'],domainId=creation['domainId'],
            entityId=creation['entityId'],creationRequestId=creation['requestId'],originRequestId=parsed['requestId'],readerId=parsed['readerId'],
            nativeGeometryRequestId=geometry['requestId'],backendRequestId=packet['requestId'],bakeRequestId=baked['requestId'],
            path=baking.usage.path(),outputPath=baked['outputPath'],sha256=baked['outputHash'],bytes=len(raw))

    def decode(self,value):
        usage=self.sources.usage;source=usage.source
        exact(value,{'iosAssetsParsedInputOwnerVersion','binding','runId','role','fileOwnerToken','page','path','payload'})
        need(type(value['iosAssetsParsedInputOwnerVersion']) is int and value['iosAssetsParsedInputOwnerVersion']==VERSION and same(value['binding'],source.binding)
            and value['runId']==source.files.run and value['role']==source.role and value['fileOwnerToken']==source.files.state['token']
            and value['page']==source.state['page'] and value['path']==usage.path())
        states=unpack(value['payload']);need(len(states)==1);state=states[0];exact(state,{'phase','sourceIndex','backendIndex','backendStarted','backendReturned','result'})
        need(state['phase'] in ('reserved','source','backend','observed'))
        if state['sourceIndex'] is None:need(state['phase']=='reserved' and all(state[key] is None for key in ('backendIndex','backendStarted','backendReturned','result')))
        else:need(state['phase']!='reserved' and integer(state['sourceIndex'],1,41))
        if state['phase'] in ('reserved','source'):need(state['backendStarted'] is None)
        if state['phase'] in ('reserved','source'):need(not any(row['slot']==SLOT for row in self.baking.backend.state['samples']))
        if state['phase'] in ('backend','observed'):
            frame=self.frame(state['sourceIndex']);need(number(state['backendStarted'],frame['clockJoin']['hostAfterMonotonic']))
        if state['backendIndex'] is not None:
            self.backend_row(state['backendIndex']);need(state['phase']=='observed' and number(state['backendReturned'],state['backendStarted'])
                and state['result'] is not None and same(state['result'],self.proof(state['sourceIndex'],state['backendIndex'])))
        else:need(state['backendReturned'] is None and state['result'] is None and state['phase']!='observed')
        return state

    def save(self):
        self.guard();usage=self.sources.usage;source=usage.source
        value=dict(iosAssetsParsedInputOwnerVersion=VERSION,binding=source.binding,runId=source.files.run,role=source.role,
            fileOwnerToken=source.files.state['token'],page=source.state['page'],path=usage.path(),payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    @operation
    def reserve(self):
        self.authoritative()
        need(self.state is None and self.model.state['creation'] is not None and self.baking.state['phase']=='qualified')
        self.state=dict(phase='reserved',sourceIndex=None,backendIndex=None,backendStarted=None,backendReturned=None,result=None);self.save()

    @operation
    def freeze_failed_source(self):
        self.authoritative();need(self.state['phase']=='source');index=self.state['sourceIndex']
        if self.sources.state['pending'] is not None:
            need(self.sources.state['nextIndex']==index);self.sources.freeze_interrupted()
        else:
            need(self.sources.state['nextIndex']==index+1 and len([row for row in self.sources.state['interrupted'] if row['index']==index])==1)
        self.state['sourceIndex']=self.sources.state['nextIndex'];self.save()

    @operation
    def observe(self):
        self.guard();self.authoritative();need(self.state is not None)
        if self.state['phase']=='observed':self.decode(self.previous);return deepcopy(self.state['result'])
        if self.state['phase']=='reserved':
            if self.sources.state is None:self.sources.reserve()
            self.state.update(phase='source',sourceIndex=self.sources.state['nextIndex']);self.save()
        if self.state['phase']=='source':
            index=self.state['sourceIndex'];existing=[reference for reference in self.sources.state['frames'] if self.sources.originals.expand(reference)['index']==index]
            if not existing:
                need(self.sources.state['nextIndex']==index)
                if self.sources.state['pending'] is not None:self.sources.recover_capture()
                else:self.sources.capture(self.sources.epoch_ms())
            self.frame(index);self.state.update(phase='backend',backendStarted=self.sources.monotonic());self.save()
        backend=self.baking.backend;packet=backend.checkpoint(SLOT,self.sources.usage.source.files.state['ticket'])
        if packet is None:return None
        index=next(i for i,row in enumerate(backend.state['samples'],1) if row['slot']==SLOT)
        proof=self.proof(self.state['sourceIndex'],index)
        self.state.update(phase='observed',backendIndex=index,backendReturned=self.sources.monotonic(),result=proof);self.save();return deepcopy(proof)
