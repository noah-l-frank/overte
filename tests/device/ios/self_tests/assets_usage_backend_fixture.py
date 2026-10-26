"""Original normal UI events plus independently exported modeled backend work.

Real bytes/inodes, weak host owners and export WALs are used. Oven output and
native process/Qt APIs remain explicit boundary models, never device evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from adapters.asset_backend_files import AssetsBackendFiles,encode
from adapters.native_feature_observation import need
from asset_backend_evidence_fixture import Fixture as BackendFixture
from test_asset_backend_source import NativeWorkModel
from ios.self_tests import assets_usage_fixture as usage

RUN=usage.RUN


class Boundary(usage.Boundary):
    def exchange(self,value):
        result=super().exchange(value);callback=getattr(self,'backend_observer',None)
        if callback is not None:callback(result['bundleInfo']['serviceEvents'])
        return result


class Fixture(usage.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        super().__init__(directory);self.backend=BackendFixture();self.events_seen=0;self.requests=[];self.tasks={};self.hold_bodies=False;self.last_ui=self.boundary.elapsed
        source=self.backend;source.host.transport.detach();source.host.run=RUN;source.host.query['runId']=RUN
        binding=self.boundary.reads.binding;source.b.server,source.b.domain=binding['server'],binding['domainId'];source.host.admission.update(serverId=source.b.server,domainId=source.b.domain)
        source.b.record(source.b.export/'asset-backend-admission.json',encode(source.host.admission));journal=source.b.root/'usage-journal';journal.mkdir(mode=0o700)
        source.host.transport=AssetsBackendFiles(source.host.process,journal,RUN,epoch_ms=source.host.now,monotonic_ms=source.host.now)
        source.host.addCleanup(source.host.transport.detach);source.config.update(domainId=source.b.domain);self.boundary.backend_observer=self.events

    def close(self):self.backend.close();super().close()

    def seed_fbx_server(self):
        super().seed_fbx_server();source=self.backend
        for path,digest in source.initial.items():self.boundary.reads.data[path]=(source.b.files/digest).read_bytes()
        for path,raw in self.boundary.reads.data.items():
            digest=hashlib.sha256(raw).hexdigest()
            if digest not in source.initial_names:source.blob(raw)
            source.mappings[path]=digest
        source.persist();self.boundary.configure(serverRows=[dict(path=path,base64=base64.b64encode(raw).decode(),status=1) for path,raw in self.boundary.reads.data.items()])

    def clocks(self):
        delta=self.boundary.elapsed-self.last_ui;need(delta>=0);self.last_ui=self.boundary.elapsed;self.backend.work.t+=delta;self.backend.host.clock+=delta

    def events(self,events):
        self.clocks();source=self.backend
        for event in events[self.events_seen:]:
            if event['kind']=='baking-started' and event['enabled']:
                for path in event['paths']:
                    raw=self.boundary.reads.data[path];digest=hashlib.sha256(raw).hexdigest();need(source.mappings[path]==digest)
                    task=NativeWorkModel();task.inputs.update(path=path,hash=digest);task.events[0]['details']['inputs']=deepcopy(task.inputs);source.work.add(task)
                    self.tasks[path]=dict(task=task,run=task.enter(),callback=None,raw=raw,digest=digest)
            elif event['kind']=='baking-completed' and event['enabled']:
                for path in event['paths']:
                    item=self.tasks[path];task=item['task'];item['callback']=task.enter(True);prefix='/.baked/'+item['digest']+'/'
                    # Declared oven-output model, produced from the service's
                    # original input, never adapter-expected hashes or verdicts.
                    output=b'Explicit modeled oven output\n'+item['raw'];source.mappings[prefix+'asset.fbx']=source.blob(output)
                    meta=dict(bake_version=1,failed_last_bake=bool(event['error']),last_bake_errors=event['error'],redirect_target='')
                    source.mappings[prefix+'meta.json']=source.blob(json.dumps(meta).encode());source.persist()
                    if not self.hold_bodies:self.finish(item)
        self.events_seen=len(events)

    def finish(self,item):
        task=item['task'];task.leave(item['callback'],True);task.leave(item['run']);task.expire('lease','owner','object')

    def open(self,request,timeout):
        query=json.loads(request.data);self.requests.append(query);self.clocks();source=self.backend
        native=dict(schemaVersion=1,action='feature-assets-backend-observe',commandId=query['commandId'],runId=query['runId'],ticket=query['ticket'],processId=123,instance=source.host.admission['instance'])
        if query['operation']=='observe':source.host.transport.send(native);source.host.publish();source.host.transport.poll()
        original=source.host.transport.export(query['commandId']);raw=json.dumps(dict(assetsBackendControlVersion=1,requestId=query['commandId'],runId=query['runId'],ticket=query['ticket'],status='original',original=original)).encode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_args):pass
            def read(self,limit):return raw[:limit]
        return Response()
