"""Fresh History4 boundary with actual weak mesh/material model holders.

Cache and independent-renderer releases are external declared test stimuli;
no adapter, getter or ordinary input automatically performs either event.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import uuid
import weakref
from ios.self_tests import assets_geometry_release_fixture as geometry,assets_model_removal_fixture as removal
from ios.self_tests.test_ios_assets_geometry_consumers import Geometry as GeometryBase,Holder
from ios.self_tests.assets_reply_fixture import EPOCH


class Geometry(GeometryBase):
    def __init__(self,hfm,mesh):super().__init__(hfm);self.mesh=mesh
    def __del__(self):
        self.mesh=None
        super().__del__()


class Boundary(geometry.Boundary):
    def __init__(self,directory):self.ownership_rows=[];super().__init__(directory)
    def consume(self,id_,entity):
        # Select the complete producer before its first acquisition. No old
        # Geometry3 original is relabeled, replaced or timestamp-adjusted.
        removal.Boundary.consume(self,id_,entity)
        resource=self.model_resource_cache[id_];actual=self.models[id_];mesh=Holder()
        resource.geometry=Geometry(resource.hfm,mesh);actual.geometry=Geometry(resource.hfm,mesh)
        for kind,value in (('resource',resource.geometry),('copy',actual.geometry)):
            clock=dict(epochMs=self.tick(),monotonicMs=self.clock()-EPOCH)
            parent=dict(id=uuid.uuid4().hex,readerId=self.origin_rows[id_]['id'],mappingIds=[],kind=kind,
                born=clock,destructionObserved=None)
            self.geometry_rows.append((weakref.ref(value.token),parent))
            for kind,holder in (('mesh',value.mesh),('material',value.material)):
                row=dict(id=uuid.uuid4().hex,geometryId=parent['id'],kind=kind,slot=0,
                    born=dict(epochMs=self.tick(),monotonicMs=self.clock()-EPOCH),ownershipExpiryObserved=None)
                self.ownership_rows.append((weakref.ref(holder),row))
    def origin(self,query):
        rows=[]
        for weak,original in self.ownership_rows:
            alive=weak() is not None
            if not alive and original['ownershipExpiryObserved'] is None:
                original['ownershipExpiryObserved']=dict(epochMs=self.tick(),monotonicMs=self.clock()-EPOCH)
            rows.append(dict(deepcopy(original),strongOwnersAlive=alive))
        value=super().origin(query);history=value['source']['history']
        history.update(assetModelOriginHistoryVersion=4,
            consumerOwnership=dict(assetModelConsumerOwnershipVersion=1,rows=rows))
        return value
    def external_renderer_consumer(self,id_):
        actual=self.models[id_].geometry
        return SimpleNamespace(mesh=actual.mesh,material=actual.material)


class Fixture(geometry.Fixture):boundary_type=Boundary
