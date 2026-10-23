"""Original inventory2 producer with actual host weak roots; native is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.self_tests.test_ios_emote_held_marker_journey import CachedMarkerDomain
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus


class RootedMarkerDomain(CachedMarkerDomain):
    def __init__(self,scope):
        super().__init__(scope);outer=self
        class OriginalClockCensus(RootCensus):
            def tick(_self):_self.elapsed+=1;return outer.epoch()
            def source(_self,**kwargs):
                # Model the selected role before producing its raw original.
                value=super().source(**kwargs);value['processId']=scope.pid;return value
        self.roots=OriginalClockCensus();self.actual_roots={};self.root_ids={}

    def widgets(self):
        value=super().widgets();inventory=value['scriptInventory'];members=dict(managers=[],pickers=[])
        self.roots.elapsed=round(self.time*1000)
        for group,kind in (('managers','manager'),('pickers','picker')):
            for _row in inventory[group]:
                if kind not in self.actual_roots:
                    self.actual_roots[kind]=Root(kind)
                    self.root_ids[kind]=self.roots.observe(self.actual_roots[kind])
                members[group].append(self.root_ids[kind])
        # Construct the modeled original before its first raw/native capture.
        value['scriptInventory']=dict(inventory,inventoryVersion=2,
            rootOwnership=self.roots.source(),rootMembership=members)
        return value
