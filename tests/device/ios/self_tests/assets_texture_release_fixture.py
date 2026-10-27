"""Fresh History5 producer with actual weak map/source Python holders.

Native Geometry parsing/material/texture existence is an explicit model. No
image parser, native renderer, decoder or GPU is executed or inferred here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
import weakref
from ios.self_tests import assets_strong_release_fixture as strong
from ios.self_tests.test_ios_assets_geometry_consumers import Holder
from ios.self_tests.assets_reply_fixture import EPOCH


class Boundary(strong.Boundary):
    def __init__(self,directory):
        # Select the new producer before any original acquisition. Saved
        # History4 packets and clocks are never upgraded or relabeled.
        self.texture_nodes=[];self.texture_links=[];self.texture_revision=0
        super().__init__(directory)

    def texture_stamp(self):return dict(epochMs=self.tick(),monotonicMs=self.clock()-EPOCH)

    def consume(self,id_,entity):
        super().consume(id_,entity)
        resource=self.model_resource_cache[id_];actual=self.models[id_]
        map_holder=Holder();map_holder.source=Holder()
        # Declared accepted-parser source: both real model materials share the
        # same actual model map/source groups, independently of all later reads.
        resource.geometry.material.map=map_holder;actual.geometry.material.map=map_holder
        map_id,source_id=uuid.uuid4().hex,uuid.uuid4().hex
        for holder,id_,kind in ((map_holder,map_id,'map'),(map_holder.source,source_id,'source')):
            self.texture_nodes.append((weakref.ref(holder),dict(id=id_,kind=kind,born=self.texture_stamp(),ownershipExpiryObserved=None)))
        for _,parent in self.geometry_rows[-2:]:
            for channel in (-1,0):
                self.texture_revision+=1;stamp=self.texture_stamp()
                self.texture_links.append(dict(id=uuid.uuid4().hex,geometryId=parent['id'],materialSlot=0,channel=channel,
                    mapId=map_id if channel==0 else '',sourceId=source_id if channel==0 else '',
                    born=deepcopy(stamp),lastObserved=deepcopy(stamp),revision=self.texture_revision))

    def origin(self,query):
        nodes=[]
        for weak,original in self.texture_nodes:
            alive=weak() is not None
            if not alive and original['ownershipExpiryObserved'] is None:original['ownershipExpiryObserved']=self.texture_stamp()
            nodes.append(dict(deepcopy(original),strongOwnersAlive=alive))
        value=super().origin(query)
        value['source']['history'].update(assetModelOriginHistoryVersion=5,textureOwnership=dict(
            assetModelTextureOwnershipVersion=1,revision=self.texture_revision,nodes=nodes,links=deepcopy(self.texture_links)))
        return value

    def external_source_consumer(self,id_):
        # Test caller owns this real independent reference. No adapter, getter
        # or normal input creates/releases it or performs external eviction.
        return self.models[id_].geometry.material.map.source


class Fixture(strong.Fixture):boundary_type=Boundary
