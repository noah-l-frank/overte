"""Explicit backend/product event model with original real-file exports.

No native/server/oven execution occurs. Ownership weak references and every
read/journal/export byte/inode are real host objects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from adapters.asset_backend_files import kernel
from test_asset_backend_files import BackendFilesTests
from test_asset_backend_source import NativeWorkModel,stamp


class WorkModel:
    def __init__(self,legacy):self.active=legacy;self.rows=[];self.sequence=legacy.sequence;self.instance=legacy.instance
    @property
    def t(self):return self.active.t
    @t.setter
    def t(self,value):self.active.t=value
    def capture(self):
        value=self.active.capture();self.sequence+=1;value.update(instance=self.instance,sequence=self.sequence,jobs=deepcopy(self.rows)+value['jobs']);return value
    def add(self,model):
        old=self.capture();self.rows=old['jobs'];delta=self.t+20;model.created=stamp(1+delta);model.t+=delta
        for event in model.events:event['clock']=stamp(event['clock']['monotonicMs']+delta)
        self.active=model


class Fixture:
    def __init__(self):
        self.host=BackendFilesTests();self.host.setUp();self.b=self.host.b;self.work=WorkModel(self.b.work);self.b.work=self.work
        self.mappings=json.loads((self.b.data/'map.json').read_bytes());self.initial=deepcopy(self.mappings);self.initial_names={path.name for path in self.b.files.iterdir()};self.b.dataset=self.snapshot;self.index=0
        self.config=dict(url='http://127.0.0.1:43210/v1/assets-backend',token='T'*48,domainId=self.b.domain,processIdentity=self.host.process.process_identity,
            executableSha256=self.host.process.sha256,ownerSha256=self.host.process.owner_sha256,sourceRootIdentity=self.host.transport.root)
    def close(self):self.host.doCleanups()
    def record(self,path):
        raw=path.read_bytes();return dict(name=path.name,exists=True,identity=kernel(path.stat()),body=dict(retained=True,base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))
    def snapshot(self):
        directory=lambda path:dict(configuredPath=str(path),canonicalPath=str(path),identity=kernel(path.stat(),directory=True))
        blobs=[self.record(path) for path in sorted(self.b.files.iterdir())];meta=[]
        for path,digest in self.mappings.items():
            if path.startswith('/.baked/') and path.endswith('/meta.json'):
                raw=json.loads((self.b.files/digest).read_bytes());meta.append(dict(mappingPath=path,originalHash=path.split('/')[2],blobHash=digest,decoded=dict(bakeVersion=raw['bake_version'],failedLastBake=raw['failed_last_bake'],lastBakeErrors=raw['last_bake_errors'],redirectTarget=raw.get('redirect_target',''))))
        return dict(assetBackendSnapshotVersion=1,available=True,complete=True,serverId=self.b.server,domainId=self.b.domain,resourcesRoot=directory(self.b.data),filesRoot=directory(self.b.files),
            memoryMappings=[dict(path=path,hash=digest) for path,digest in sorted(self.mappings.items())],mapFile=self.record(self.b.data/'map.json'),persistedMappings=deepcopy(self.mappings),blobs=blobs,unknownEntries=[],meta=meta,
            workBefore=self.work.capture(),workAfter=self.work.capture(),nodes=[],hiddenPrefix='/.baked/',modelBakeVersion=1,modelOutputName='asset.fbx',bakeableModelExtensions=['fbx'])
    def sample(self):
        self.index+=1;native=self.host.command(self.index);self.host.transport.send(native);self.host.publish();self.host.transport.poll();query=dict(schemaVersion=1,operation='poll',commandId=native['commandId'],runId=native['runId'],ticket=native['ticket'])
        return self.host.transport.export(native['commandId']),query
    def blob(self,raw):
        digest=hashlib.sha256(raw).hexdigest();self.b.record(self.b.files/digest,raw);return digest
    def persist(self):self.b.record(self.b.data/'map.json',json.dumps(self.mappings,sort_keys=True,indent=2).encode())
    def baked(self,*,returned=True,holders=True,failed=False,version=1,output=True):
        path='/e2e-'+self.host.run+'/model.fbx';digest=self.blob(b'fixture-original-fbx');self.mappings[path]=digest
        task=NativeWorkModel();task.inputs.update(hash=digest,path=path);task.events[0]['details']['inputs']=deepcopy(task.inputs);self.work.add(task)
        run=task.enter();callback=task.enter(True)
        if returned:task.leave(callback,True);task.leave(run)
        if not holders:task.expire('lease','owner','object')
        prefix='/.baked/'+digest+'/';meta=dict(bake_version=version,failed_last_bake=failed,last_bake_errors='actual error' if failed else '',redirect_target='')
        self.mappings[prefix+'meta.json']=self.blob(json.dumps(meta,sort_keys=True).encode())
        if output:self.mappings[prefix+'asset.fbx']=self.blob(b'declared actual baked-output bytes')
        self.persist();return path,digest,task
    def restore(self):
        self.mappings=deepcopy(self.initial);self.persist()
        for path in self.b.files.iterdir():
            if path.name not in self.initial_names:path.unlink()
    def advance(self,host=3100,native=3100):self.host.clock+=host;self.work.t+=native
