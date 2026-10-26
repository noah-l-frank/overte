"""Explicit oven/parser/world models driven by original normal API events.

QML, private bytes/inodes, raw/logical journals and independent backend export
execute. No native parser, oven, renderer, service or device executes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import uuid
import weakref
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import assets_model_origin as origin
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_baking_owner import OwnedAssetsBaking
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.assets_parsed_sources import AssetsParsedSources
from adapters.asset_backend_client import AssetsBackendClient
from ios.self_tests import assets_model_fixture as model,assets_usage_backend_fixture as backend

RUN=model.RUN


class CacheResource:
    def __init__(self):self.hfm=Lease()


class Lease:pass


class Boundary(model.Boundary,backend.Boundary):
    def __init__(self,directory):
        self.origin_rows={};self.origin_sequence=0;self.origin_instance=uuid.uuid4().hex;self.origin_history_instance=uuid.uuid4().hex;self.origin_fault=None
        self.model_resource_cache={};self.origin_weaks={}
        super().__init__(directory)

    def exchange(self,value):
        result=super().exchange(value)
        # The original normal API event has already created these actual
        # boundary entities. Model their original loader consumption now,
        # independently of every later source getter and server checkpoint.
        for id_,entity in sorted(self.entities.items()):
            if id_ not in self.origin_rows:self.consume(id_,entity)
        return result

    def consume(self,id_,entity):
        raw=self.resolve_model(entity.properties['modelURL'])
        resource=CacheResource();lease=Lease();actual=self.models[id_];actual.origin_lease=lease;actual.origin_hfm=resource.hfm
        self.model_resource_cache[id_]=resource
        self.origin_weaks[id_]=dict(lease=weakref.ref(lease),object=weakref.ref(resource),hfm=weakref.ref(resource.hfm))
        def stamp():
            epoch=self.tick();return dict(epochMs=epoch,monotonicMs=epoch-model.usage.picker.EPOCH)
        stamps={key:stamp() for key in ('received','readerCreated','runEntered','queued','invokeReturned','deliveryEntered','deliveryReturned','runReturned')}
        self.origin_rows[id_]=dict(id=uuid.uuid4().hex,kind='model',requestedUrl=entity.properties['modelURL'],effectiveUrl='atp:'+hashlib.sha256(raw).hexdigest(),
            bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode(),**stamps,
            invokeAccepted=True,resourceAlive=True,readerKnown=True,readerAlive=False,modelKnown=True,parsedModelAlive=True)

    def origin(self,query):
        self.origin_sequence+=1;before=self.tick();state=self.state();models=[]
        for id_,entity in sorted(self.entities.items()):
            actual=self.models[id_]
            row=self.origin_rows.get(id_)
            models.append(dict(entityId=id_,present=True,loaded=actual.loaded,addedToScene=actual.added,failed=actual.failed,
                origin=dict(modelUrl=entity.properties['modelURL'],watcherUrl=entity.properties['modelURL'],geometry=dict(readerId=row['id'] if row is not None else '',mappingIds=[]))))
        downloads=[]
        for id_,original in self.origin_rows.items():
            row=deepcopy(original);weak=self.origin_weaks[id_]
            row.update(resourceAlive=weak['lease']() is not None,resourceObjectAlive=weak['object']() is not None,parsedModelAlive=weak['hfm']() is not None);downloads.append(row)
        clock=dict(epochMs=self.tick(),monotonicMs=self.clock()-model.usage.picker.EPOCH);after=self.tick()
        value=dict(iosAssetsModelOriginVersion=1,requestId=query['commandId'],runId=query['runId'],instance=self.origin_instance,
            sequence=self.origin_sequence,processId=42,clockDomain='native-main-assets-model-origin',clockBefore=dict(epochMs=before,monotonicMs=before-model.usage.picker.EPOCH),
            clockAfter=dict(epochMs=after,monotonicMs=after-model.usage.picker.EPOCH),source=dict(complete=True,domainId=state['source']['domainId'],localSessionId=state['source']['localSessionId'],
                tree=state['source']['tree'],models=models,history=dict(assetModelOriginHistoryVersion=2,instance=self.origin_history_instance,complete=True,clock=clock,downloads=downloads),resourceRetirementAvailable=False))
        if self.origin_fault:self.origin_fault(value)
        return value


class Fixture(backend.Fixture,model.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        super().__init__(directory);self.boundary.resolve_model=self.resolve_model
        for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies')):
            getattr(self,attribute).path=self.path(kind)

    def path(self,kind):return self.boundary.directory/('ios-assets-'+RUN+'-primary-'+kind+'.json')
    def sources(self,owner,*,store=None):return super().sources(owner,store=store or PrivateFeatureState(self.path('model-sources')))

    def resolve_model(self,url):
        path=url[4:];digest=self.backend.mappings[path];prefix='/.baked/'+digest+'/'
        return (self.backend.b.files/self.backend.mappings[prefix+'asset.fbx']).read_bytes()

    def prepared(self):
        usage=self.owned_existing_source();old=usage.store.path;usage.store.path=self.path('usage');old.rename(usage.store.path);usage.select()
        backend_owner=OwnedAssetsBackend(usage.source,AssetsBackendClient(self.backend.config,usage.guard),PrivateFeatureState(self.path('backend')),lock=self.lock)
        baking=OwnedAssetsBaking(usage,backend_owner,PrivateFeatureState(self.path('baking')),lock=self.lock);baking.reserve();baking.start();baking.qualify()
        model_owner=OwnedAssetsModel(usage,self.sources(usage),PrivateFeatureState(self.path('model')),lock=self.lock)
        model_owner.reserve();model_owner.start();model_owner.observe()
        actual=self.boundary.models[model_owner.state['creation']['proof']['entityId']];actual.loaded=True;actual.added=True
        return model_owner,baking

    def parsed(self,model_owner,baking):
        b=self.boundary;raw=['']
        def send(query):origin.command(query);raw[0]=json.dumps(b.origin(query))
        def epoch():return model_owner.sources.native.read(model_owner.sources.native.sequence)['capturedEpochMs']
        reader=origin.IOSAssetsModelOrigin(send,lambda:raw[0],epoch,lambda:b.live,42,monotonic=b.monotonic,sleep=b.sleep)
        sources=AssetsParsedSources(model_owner,reader,PrivateFeatureState(self.path('parsed-sources')),lock=self.lock)
        return OwnedAssetsParsedInput(sources,baking,PrivateFeatureState(self.path('parsed')),lock=self.lock)
