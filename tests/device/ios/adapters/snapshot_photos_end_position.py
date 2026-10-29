"""Typed completed Photos SDK position, distinct from live presence guards."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same


class SnapshotPhotosRetiredSDKPosition:
    def __init__(self,owner):
        from ios.adapters.snapshot_photos_end_owner import SnapshotPhotosEndOwner
        need(type(owner) is SnapshotPhotosEndOwner);self.owner=owner;self.record=deepcopy(owner.position_record())
    def check(self,graph):
        need(self.owner.graph is graph and same(self.record,self.owner.position_record())
            and self.record['graphSha256']==digest(graph.previous))
        return deepcopy(self.record)
