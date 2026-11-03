"""Actual unbaked glTF/OBJ parser input joined to independent server bytes.

This is a specialization of the existing parsed-input owner. It never calls
the FBX oven, relabels a bundle as baked, or treats a dialog ACK as parsing.
Images, independently parsed peer publication and end remain separate owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from adapters import asset_backend_evidence as evidence,asset_backend_source as backend_source,asset_backend_work as work
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,pack,unpack
from feature_journeys.asset_fixture import BUNDLES
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_budget import operation
from ios.adapters.assets_files import original_bytes
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.assets_parsed_sources import AssetsParsedSources
from ios.adapters import assets_model_facts as facts,assets_model_origin as origin
from ios.adapters.assets_usage_controls import project as usage_page

VERSION=1
SLOT='parsed-bundle-input-1'
RESOURCES=frozenset(('gltf-bundle/main.gltf','obj-bundle/main.obj'))


class OwnedAssetsUnbakedInput(OwnedAssetsParsedInput):
    OWNER_VERSION=VERSION
    def extra_envelope(self):return {}
    def __init__(self,sources,backend,store,*,lock):
        need(type(sources) is AssetsParsedSources and isinstance(backend,OwnedAssetsBackend)
            and sources.usage.source is backend.upload and isinstance(store,PrivateFeatureState))
        lock.assert_held()
        self.sources,self.model,self.backend,self.store,self.lock=sources,sources.model,backend,store,lock
        self.monotonic=sources.monotonic;self.previous=store.read();self.state=None
        need(sources.usage.source.files.state is None or sources.usage.source.files.state['resource'] in RESOURCES)
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.sources.guard();self.backend.guard()
        need(all(same(owner.store.read(),owner.previous) for owner in (self,self.sources,self.model,self.backend)))
        return True

    def backend_row(self,index):
        need(integer(index,1,len(self.backend.state['samples'])));return self.backend.state['samples'][index-1]

    def proof(self,source_index,backend_index):
        model=self.model;model.decode(model.previous);need(model.state['phase']=='geometry-observed')
        usage=model.usage;upload=usage.source;resource=upload.files.state['resource'];need(resource in RESOURCES)
        frame=self.frame(source_index);originals=frame['originals'];creation=model.state['creation']['proof']
        geometry=facts.geometry(usage,model.native(model.state['baseline']),model.native(model.state['creation']['frame']),originals['createAfter'])
        parsed=origin.parsed_input(originals['origin'],creation['entityId'])
        need(parsed['modelUrl']==parsed['watcherUrl']==usage.url() and parsed['requestedUrl']==usage.url())
        page=usage_page(originals['ui'],upload.state['page'])
        need(page['baking']['enabled'] is False and page['baking']['checked'] is False)
        row=self.backend_row(backend_index);need(row['slot']==SLOT and row['parts'] is not None and row['parts']['complete'])
        packet=self.backend.packet(row)
        need(evidence.ready_source(packet) and all(work.drained(packet['source'][key]) for key in ('workBefore','workAfter'))
            and packet['domainId']==creation['domainId']==originals['origin']['source']['domainId']==page['domainId'])
        input_proof=usage.proof(model.input()['admission']['slot'])
        need(input_proof['binding']['server']==packet['serverId'] and input_proof['binding']['domainId']==packet['domainId'])
        mapping=evidence.mapping(packet);blobs=evidence.blobs(packet);primary,paths=BUNDLES[resource]
        prefix=usage.path()[:-len(primary)];rows=[]
        for name in paths:
            path=prefix+name;digest=mapping.get(path);need(digest in blobs)
            raw=backend_source.file(blobs[digest],name=digest,limit=32768,required=True)
            need(raw is not None and raw==original_bytes(upload.files.state['files'][name])
                and hashlib.sha256(raw).hexdigest()==digest)
            rows.append(dict(path=path,bytes=len(raw),sha256=digest))
        primary_row=next(row for row in rows if row['path']==usage.path())
        download=next(row for row in originals['origin']['source']['history']['downloads'] if row['id']==parsed['readerId'])
        raw=base64.b64decode(download['base64'],validate=True)
        need(parsed['sha256']==primary_row['sha256']==hashlib.sha256(raw).hexdigest()
            and parsed['bytes']==primary_row['bytes']==len(raw)
            and raw==original_bytes(upload.files.state['files'][primary]))
        return dict(assetModelBundleInputProofVersion=VERSION,runId=creation['runId'],processId=creation['processId'],
            domainId=creation['domainId'],entityId=creation['entityId'],creationRequestId=creation['requestId'],
            originRequestId=parsed['requestId'],readerId=parsed['readerId'],nativeGeometryRequestId=geometry['requestId'],
            backendRequestId=packet['requestId'],path=usage.path(),sha256=primary_row['sha256'],bytes=len(raw),
            resource=resource,files=rows)

    def envelope(self):
        usage=self.sources.usage;source=usage.source
        return dict(iosAssetsUnbakedInputOwnerVersion=self.OWNER_VERSION,binding=source.binding,runId=source.files.run,role=source.role,
            fileOwnerToken=source.files.state['token'],page=source.state['page'],path=usage.path(),payload=pack([self.state]),**self.extra_envelope())

    def decode(self,value):
        exact(value,{'iosAssetsUnbakedInputOwnerVersion','binding','runId','role','fileOwnerToken','page','path','payload'}|set(self.extra_envelope()))
        need(type(value['iosAssetsUnbakedInputOwnerVersion']) is int and value['iosAssetsUnbakedInputOwnerVersion']==self.OWNER_VERSION)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        current=self.state;self.state=state
        try:need(same(value,self.envelope()))
        finally:self.state=current
        exact(state,{'phase','sourceIndex','backendIndex','backendStarted','backendReturned','result'})
        need(state['phase'] in ('reserved','source','backend','observed'))
        if state['sourceIndex'] is None:
            need(state['phase']=='reserved' and all(state[key] is None for key in ('backendIndex','backendStarted','backendReturned','result')))
        else:need(state['phase']!='reserved' and integer(state['sourceIndex'],1,41))
        if state['phase'] in ('reserved','source'):
            need(state['backendStarted'] is None and not any(row['slot']==SLOT for row in self.backend.state['samples']))
        if state['phase'] in ('backend','observed'):
            need(number(state['backendStarted'],self.frame(state['sourceIndex'])['clockJoin']['hostAfterMonotonic']))
        if state['backendIndex'] is not None:
            self.backend_row(state['backendIndex'])
            need(state['phase']=='observed' and number(state['backendReturned'],state['backendStarted'])
                and same(state['result'],self.proof(state['sourceIndex'],state['backendIndex'])))
        else:need(state['phase']!='observed' and state['backendReturned'] is None and state['result'] is None)
        return state

    def save(self):
        self.guard();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    @operation
    def reserve(self):
        self.authoritative();need(self.state is None and self.model.state['phase']=='geometry-observed'
            and self.backend.state['uploadProof'] is not None)
        self.state=dict(phase='reserved',sourceIndex=None,backendIndex=None,backendStarted=None,backendReturned=None,result=None);self.save()

    @operation
    def observe(self):
        self.guard();self.authoritative();need(self.state is not None)
        if self.state['phase']=='observed':self.decode(self.previous);return deepcopy(self.state['result'])
        if self.state['phase']=='reserved':
            if self.sources.state is None:self.sources.reserve()
            self.state.update(phase='source',sourceIndex=self.sources.state['nextIndex']);self.save()
        if self.state['phase']=='source':
            index=self.state['sourceIndex'];existing=[ref for ref in self.sources.state['frames'] if self.sources.originals.expand(ref)['index']==index]
            if not existing:
                need(self.sources.state['nextIndex']==index)
                if self.sources.state['pending'] is not None:self.sources.recover_capture()
                else:self.sources.capture(self.sources.epoch_ms())
            self.frame(index);self.state.update(phase='backend',backendStarted=self.sources.monotonic());self.save()
        packet=self.backend.checkpoint(SLOT,self.ticket())
        if packet is None:return None
        index=next(index for index,row in enumerate(self.backend.state['samples'],1) if row['slot']==SLOT)
        result=self.proof(self.state['sourceIndex'],index)
        self.state.update(phase='observed',backendIndex=index,backendReturned=self.sources.monotonic(),result=result)
        self.save();return deepcopy(result)
