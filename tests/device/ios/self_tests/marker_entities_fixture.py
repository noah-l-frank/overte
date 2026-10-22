"""Modeled generic native entity source driven by ordinary marker recipes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.create_entities import IOSCreateEntities
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.self_tests import test_ios_create_entities as entities_fixture


class EntityDomain:
    def __init__(self,test,scope,domain):
        self.scope,self.domain=scope,domain
        for name,value in (('EPOCH',20000),('RUN',scope.run)):
            p=patch.object(entities_fixture,name,value);p.start();test.addCleanup(p.stop)
        self.native=entities_fixture.NativeBoundary();self.native.tree_instance=domain.world_template['source']['tree']['treeInstance']
        def tick():domain.time+=.001;self.native.now=domain.epoch();return self.native.now
        self.native.tick=tick;send=self.native.send
        def real_send(query):send(query);self.native.packet['processId']=scope.pid
        self.reader=IOSCreateEntities(real_send,self.native.original,tick,lambda:True,scope.pid,monotonic=lambda:domain.time,sleep=domain.sleep)
        if hasattr(domain,'start'):
            start,stop=domain.start,domain.stop
            def add():
                start();self.native.manager=deepcopy(domain.worker);self.native.code=deepcopy(domain.engine['code'])
                self.native.add(id_=domain.marker['id'])
            def remove():
                if domain.marker is not None:self.native.delete(domain.marker['id'])
                return stop()
            domain.start,domain.stop=add,remove
    def owner(self):
        s=self.scope;return IOSEmoteMarkerEntities(PrivateFeatureState(s.root/'ios-emote-primary-marker-entities.json'),s.root,s.binding,s.run,s.role,
            s.lock,lambda:True,native=s.native,entities=self.reader,epoch_ms=s.epoch_ms,monotonic=s.monotonic)
