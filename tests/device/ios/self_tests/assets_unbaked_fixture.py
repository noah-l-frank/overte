"""Actual normal bundle QML/input/WAL with declared server/parser producers.

No native parser, Qt, SDK, device or real AssetServer runs. Original QML and
normal commands create the model. Independent actual backend files supply the
primary and companions; actual Geometry/HFM and scene item holders drive DTOs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from adapters.asset_backend_client import AssetsBackendClient
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import assets_model_origin as origin
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_parsed_sources import AssetsParsedSources
from ios.adapters.assets_unbaked_input import OwnedAssetsUnbakedInput
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_renamed_usage import RenamedAssetsUsage
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.self_tests import assets_baked_tree_fixture as baked
from ios.self_tests.assets_paired_end_boundary_fixture import Boundary
from ios.self_tests.assets_reply_fixture import RUN


class Fixture(baked.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        self.drop_server_companion=False;super().__init__(directory)
        self.boundary.peer.resolve_model=self.resolve_model
    def resolve_model(self,url):
        # Normal unbaked request consumes the selected mapping body, rather
        # than an invented /.baked result or an adapter-supplied expected hash.
        return (self.backend.b.files/self.backend.mappings[url[4:]]).read_bytes()
    def events(self,events):
        super().events(events)
        if self.drop_server_companion:
            paths=[path for path in self.backend.mappings if path.endswith('/mesh/triangle.bin')]
            for path in paths:self.backend.mappings.pop(path)
            if paths:self.backend.persist()
    def parts(self,*,renamed=False):
        upload=self.owner();tree=OwnedAssetsTree(upload,PrivateFeatureState(self.path('tree')),lock=self.lock)
        cls=RenamedAssetsUsage if renamed else OwnedAssetsUsage
        usage=cls(upload,PrivateFeatureState(self.path('usage')),lock=self.lock,**({'tree':tree} if renamed else {}))
        backend=OwnedAssetsBackend(upload,AssetsBackendClient(self.backend.config,upload.guard),PrivateFeatureState(self.path('backend')),lock=self.lock)
        model=OwnedAssetsModel(usage,self.sources(usage),PrivateFeatureState(self.path('model')),lock=self.lock)
        raw=[''];boundary=self.boundary
        def send(query):origin.command(query);raw[0]=json.dumps(boundary.origin(query))
        def epoch():return model.sources.native.read(model.sources.native.sequence)['capturedEpochMs']
        reader=origin.IOSAssetsModelOrigin(send,lambda:raw[0],epoch,lambda:boundary.live,42,monotonic=boundary.monotonic,sleep=boundary.sleep)
        source=AssetsParsedSources(model,reader,PrivateFeatureState(self.path('parsed-sources')),lock=self.lock)
        parsed=OwnedAssetsUnbakedInput(source,backend,PrivateFeatureState(self.path('parsed')),lock=self.lock)
        return dict(owned_files=self.files,picker=self.picker,owned_replies=self.replies,upload=upload,usage=usage,tree=tree,
            backend=backend,model=model,parsed=parsed,parsed_sources=source,check=upload.guard)
