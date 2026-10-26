"""Fresh original UI events drive a declared recursive AssetServer model.

Real backend files/bytes and weak holders execute. Mapping deletion mirrors
AssetServer::deleteMappings/removeBakedPathsForDeletedAsset; no real server,
oven, native Qt, renderer or device is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import need
from ios.self_tests import assets_fresh_model_fixture as fresh,assets_model_removal_fixture as removal

RUN=fresh.RUN


class Boundary(removal.Boundary,fresh.Boundary):pass


class Fixture(fresh.Fixture):
    boundary_type=Boundary

    def delete_paths(self,paths):
        source=self.backend;hashes=set()
        for prefix in paths:
            for path in list(source.mappings):
                if path==prefix or prefix.endswith('/') and path.startswith(prefix):hashes.add(source.mappings.pop(path))
        source.persist()
        for digest in hashes-set(source.mappings.values()):
            file=source.b.files/digest
            if file.exists():
                file.unlink();self.delete_paths(['/.baked/'+digest+'/'])

    def events(self,events):
        pending=deepcopy(events[self.events_seen:]);super().events(events);source=self.backend
        for event in pending:
            if event['kind']!='mapping-completed' or event['error']:continue
            removed=[]
            for change in event['changes']:
                path=change['from'];need(path in source.mappings)
                if change['to'] is None:removed.append(path)
                else:source.mappings[change['to']]=source.mappings.pop(path)
            if removed:self.delete_paths(removed)
            source.persist();self.status_dirty=True
        # Binary AssetClient model reads the independent actual server mapping
        # and file store. Neither the adapter's expected paths nor a UI flag
        # manufactures a hidden output/meta mapping or its bytes.
        self.boundary.reads.data={path:(source.b.files/digest).read_bytes() for path,digest in source.mappings.items()}
        self.boundary.reads.status={path:self.get_status(path,digest) for path,digest in source.mappings.items()}

    def shared_original(self,raw):
        digest=hashlib.sha256(raw).hexdigest();self.backend.blob(raw);self.backend.mappings['/foreign/shared.fbx']=digest
        self.backend.persist();self.boundary.reads.data['/foreign/shared.fbx']=raw;self.status_dirty=True;self.publish_status()
