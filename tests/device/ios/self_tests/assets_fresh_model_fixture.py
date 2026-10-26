"""Fresh upload events feed independent declared backend and loader models.

No existing test asset is seeded. Original normal QML and real bytes, journals,
private backend files and weak host holders execute; native/server/oven/render
boundaries remain explicit models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from adapters.asset_backend_client import AssetsBackendClient
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import need
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_baking_owner import OwnedAssetsBaking
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.self_tests import assets_parsed_fixture as parsed
from test_asset_backend_source import NativeWorkModel

RUN=parsed.RUN


class Boundary(parsed.Boundary):
    def exchange(self,value):
        result=super().exchange(value);publish=getattr(self,'publish_mapping_status',None)
        # A distinct modeled GetAllMappings response after the original SDK
        # event, never a checkbox/control override or an adapter input.
        if publish is not None:publish()
        # The original transport result (including a lost return) is immutable.
        return result
    def consume(self,id_,entity):
        super().consume(id_,entity)
        # Explicit loader/scene completion at the original consumer event,
        # never at a getter or from the adapter's desired result.
        self.models[id_].loaded=True;self.models[id_].added=True


class Fixture(parsed.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        self.status_dirty=False;self.publishing=False;self.implicit_jobs=[];self.pending_status={}
        super().__init__(directory);self.boundary.publish_mapping_status=self.publish_status
        for path,digest in self.backend.mappings.items():self.boundary.reads.data[path]=(self.backend.b.files/digest).read_bytes()
        self.status_dirty=True;self.publish_status()

    def get_status(self,path,digest):
        # AssetServer::getAssetStatus order, over independent actual model
        # mapping/meta files. This fixture config declares only FBX bakeable.
        if digest in self.pending_status:return self.pending_status[digest],''
        if path.startswith('/.baked/'):return 4,''
        if not path.lower().endswith('.fbx'):return 0,''
        prefix='/.baked/'+digest+'/';meta_hash=self.backend.mappings.get(prefix+'meta.json');meta=None
        if meta_hash is not None:meta=json.loads((self.backend.b.files/meta_hash).read_bytes())
        output=meta.get('redirect_target','') if meta else '';output=output or prefix+'asset.fbx'
        target=self.backend.mappings.get(output)
        if target is not None:return (1 if target==digest else 4),''
        if meta and meta['failed_last_bake']:return 5,meta['last_bake_errors']
        return 2,''

    def publish_status(self):
        if not self.status_dirty or self.publishing:return None
        self.status_dirty=False;self.publishing=True
        try:
            rows=[]
            for path,digest in sorted(self.backend.mappings.items()):
                raw=(self.backend.b.files/digest).read_bytes();status,errors=self.get_status(path,digest)
                rows.append(dict(path=path,base64=base64.b64encode(raw).decode(),status=status,errors=errors))
            return self.boundary.configure(serverRows=rows)
        finally:self.publishing=False

    def implicit_bake(self,path,raw,digest):
        # Model the upload-triggered original worker without inventing a normal
        # checkbox event. Later OFF/ON retains this worker's original history.
        source=self.backend;task=NativeWorkModel();task.inputs.update(path=path,hash=digest)
        task.events[0]['details']['inputs']=deepcopy(task.inputs);source.work.add(task)
        self.pending_status[digest]=2;run=task.enter();self.pending_status[digest]=3;callback=task.enter(True);prefix='/.baked/'+digest+'/'
        source.mappings[prefix+'asset.fbx']=source.blob(b'Explicit modeled oven output\n'+raw)
        meta=dict(bake_version=1,failed_last_bake=False,last_bake_errors='',redirect_target='')
        source.mappings[prefix+'meta.json']=source.blob(json.dumps(meta).encode());source.persist()
        self.pending_status.pop(digest);task.leave(callback,True);task.leave(run);task.expire('lease','owner','object');self.implicit_jobs.append(task.id)

    def events(self,events):
        self.clocks();source=self.backend
        for event in events[self.events_seen:]:
            if event['kind']!='completion-entered':continue
            for row in event['actual']:
                raw=base64.b64decode(row['base64'],validate=True);digest=hashlib.sha256(raw).hexdigest();path=source.b.files/digest
                if path.exists():need(path.read_bytes()==raw)
                else:source.b.record(path,raw)
                source.mappings[row['path']]=digest
                task=NativeWorkModel('upload');source.work.add(task);body=task.enter()
                task.inputs['hash']=digest;task.event('input-observed',dict(field='hash',value=digest))
                task.inputs['messageId']=str(len(source.work.rows)+1);task.event('input-observed',dict(field='messageId',value=task.inputs['messageId']))
                task.leave(body);task.expire('lease')
                if row['path'].lower().endswith('.fbx'):self.implicit_bake(row['path'],raw,digest)
            source.persist()
            self.status_dirty=True
        for event in events[self.events_seen:]:
            if event['kind']=='baking-started' and event['enabled']:
                for path in event['paths']:
                    digest=source.mappings[path];output='/.baked/'+digest+'/asset.fbx'
                    need(source.mappings.get(output)==digest);source.mappings.pop(output);self.pending_status[digest]=3
                source.persist()
                self.status_dirty=True
            if event['kind']=='baking-completed' and not event['enabled'] and not event['error']:
                for path in event['paths']:
                    digest=source.mappings[path];prefix='/.baked/'+digest+'/'
                    removed=[source.mappings.pop(name) for name in list(source.mappings) if name.startswith(prefix)]
                    for old in removed:
                        if old not in source.mappings.values() and old not in source.initial_names:(source.b.files/old).unlink()
                    source.mappings[prefix+'asset.fbx']=digest
                source.persist();self.status_dirty=True
            elif event['kind']=='baking-completed' and event['enabled']:
                for path in event['paths']:self.pending_status.pop(source.mappings[path],None)
                self.status_dirty=True
        super().events(events)

    def parts(self):
        upload=self.owner();usage=OwnedAssetsUsage(upload,PrivateFeatureState(self.path('usage')),lock=self.lock)
        backend=OwnedAssetsBackend(upload,AssetsBackendClient(self.backend.config,upload.guard),PrivateFeatureState(self.path('backend')),lock=self.lock)
        baking=OwnedAssetsBaking(usage,backend,PrivateFeatureState(self.path('baking')),lock=self.lock)
        model=OwnedAssetsModel(usage,self.sources(usage),PrivateFeatureState(self.path('model')),lock=self.lock)
        owner=self.parsed(model,baking)
        return dict(owned_files=self.files,picker=self.picker,owned_replies=self.replies,upload=upload,usage=usage,backend=backend,baking=baking,model=model,
            parsed=owner,parsed_sources=owner.sources,check=upload.guard)
