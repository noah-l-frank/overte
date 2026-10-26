"""Original QML service events feed a declared independent backend FS model.

The backend model reads actual service publication/change events, never owner
expected mappings, verdicts or final state. No native server/oven executes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import json
from adapters.asset_backend_files import AssetsBackendFiles,encode
from adapters.native_feature_observation import need
from asset_backend_evidence_fixture import Fixture as BackendFixture
from test_asset_backend_source import NativeWorkModel
from ios.self_tests.assets_tree_fixture import Fixture as TreeFixture,RUN


class Fixture(TreeFixture):
    def __init__(self,directory):
        super().__init__(directory);self.backend=BackendFixture();self.events_seen=0;self.last_ui=self.boundary.elapsed
        source=self.backend;source.host.transport.detach();source.host.run=RUN;source.host.query['runId']=RUN
        binding=self.boundary.reads.binding;source.b.server,source.b.domain=binding['server'],binding['domainId']
        source.host.admission.update(serverId=source.b.server,domainId=source.b.domain)
        source.b.record(source.b.export/'asset-backend-admission.json',encode(source.host.admission))
        journal=source.b.root/'mapping-journal';journal.mkdir(mode=0o700)
        source.host.transport=AssetsBackendFiles(source.host.process,journal,RUN,epoch_ms=source.host.now,monotonic_ms=source.host.now)
        source.host.addCleanup(source.host.transport.detach);source.config.update(domainId=source.b.domain)
        for path,digest in source.mappings.items():
            self.boundary.reads.data[path]=(source.b.files/digest).read_bytes()
        self.boundary.configure(serverRows=[dict(path=path,base64=base64.b64encode(raw).decode()) for path,raw in self.boundary.reads.data.items()])
        self.requests=[]

    def close(self):
        self.backend.close();super().close()

    def sync(self):
        source=self.backend;elapsed=self.boundary.elapsed-self.last_ui;need(elapsed>=0);self.last_ui=self.boundary.elapsed
        source.work.t+=elapsed;source.host.clock+=elapsed;events=self.boundary.host_state['bundleInfo']['serviceEvents']
        for event in events[self.events_seen:]:
            if event['kind']=='completion-entered':
                for row in event['actual']:
                    raw=base64.b64decode(row['base64'],validate=True);digest=hashlib.sha256(raw).hexdigest();path=source.b.files/digest
                    if path.exists():need(path.read_bytes()==raw)
                    else:source.b.record(path,raw)
                    source.mappings[row['path']]=digest
                    task=NativeWorkModel('upload');source.work.add(task);body=task.enter();task.inputs['hash']=digest;task.event('input-observed',dict(field='hash',value=digest))
                    task.inputs['messageId']=str(len(source.work.rows)+1);task.event('input-observed',dict(field='messageId',value=task.inputs['messageId']));task.leave(body);task.expire('lease')
                source.persist()
            elif event['kind']=='mapping-completed' and not event['error']:
                for row in event['changes']:
                    raw=base64.b64decode(row['base64'],validate=True);digest=hashlib.sha256(raw).hexdigest();need(source.mappings[row['from']]==digest)
                    del source.mappings[row['from']]
                    if row['to'] is not None:source.mappings[row['to']]=digest
                    elif digest not in source.mappings.values():(source.b.files/digest).unlink()
                source.persist()
        self.events_seen=len(events)

    def open(self,request,timeout):
        query=json.loads(request.data);self.requests.append(query);source=self.backend
        native=dict(schemaVersion=1,action='feature-assets-backend-observe',commandId=query['commandId'],runId=query['runId'],ticket=query['ticket'],processId=123,instance=source.host.admission['instance'])
        if query['operation']=='observe':
            self.sync();source.host.transport.send(native);source.host.publish();source.host.transport.poll()
        original=source.host.transport.export(query['commandId'])
        raw=json.dumps(dict(assetsBackendControlVersion=1,requestId=query['commandId'],runId=query['runId'],ticket=query['ticket'],status='original',original=original)).encode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_args):pass
            def read(self,limit):return raw[:limit]
        return Response()
