"""New modeled process producers born only after ordinary launch.

Each source constructs its own first response and captures current physical
state. No old admitted DTO, retained history or clock is reissued as new.
Native/OS behavior remains modeled; loopback HTTP and bookmark bytes are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import uuid

from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import normal_input
from ios.adapters.navigation_process_owner import NavigationProcessOwner
from ios.adapters.navigation_restart_proof import OWNERS
from ios.self_tests.test_ios_navigation_sample import SDK
from ios.self_tests.test_ios_scene_commit_origin import Boundary as InventoryBoundary
from ios.self_tests.test_ios_navigation_observation_owner import BookSource,ModelSource,HttpSource,DialogSource
from ios.self_tests.test_ios_navigation_ui import observed
from navigation_observation import viewpoint_urls


class NextProcess:
    def __init__(self,world):
        self.h=world;life=world.lifecycle
        if life.pid!=43:raise AssertionError('New sources require the actually launched modeled process')
        self.birth=uuid.uuid4().hex
        old_clock=world.sdk.gpu
        self.sdk=SDK(world.harness,world.run)
        self.sdk.gpu.__class__=type('NewProcessClock',(type(self.sdk.gpu),),{
            'clock':property(lambda _:old_clock.clock,lambda _,v:setattr(old_clock,'clock',max(old_clock.clock,v)))})
        status,raw,_response=world.harness.get('/navigation/scene.json')
        if status!=200:raise AssertionError('New process did not fetch the actual run scene')
        url=viewpoint_urls(world.harness.inputs['sceneUrl'])['A'];sdk=self.sdk
        class Inventory(InventoryBoundary):
            @property
            def clock(self):return sdk.gpu.clock
            @clock.setter
            def clock(self,value):sdk.gpu.clock=value
            def commit(self):
                self.url=url;self.body=raw
                self.raw={r['id'].strip('{}'):json.dumps(r,sort_keys=True).encode() for r in json.loads(raw)['Entities']}
                super().commit()
        self.inventory=Inventory()
        self.sdk.navigation.mutate=lambda value:value['source']['sceneLoads'].update(
            currentGeneration=self.inventory.generation,requests=deepcopy(self.inventory.loads))
        self.books=BookSource(sdk,world.books.path)
        # Actual startup load, independently reading the retained persistence.
        self.books.loaded=json.loads(self.books.path.read_text())
        self.model=ModelSource(sdk);mutate=self.model.mutate
        def preferences(value):mutate(value);value['preferences']['metaverseOrigin']=world.harness.origin
        self.model.mutate=preferences
        self.http,self.dialogs=HttpSource(sdk),DialogSource(sdk)
        self.producers=dict(inventory=self.inventory,navigation=sdk.navigation,bookmarks=self.books,
            model=self.model,http=self.http,dialogs=self.dialogs)
        self.sources={};self.scene_sequence=0
        for name,producer in self.producers.items():
            prior=producer.mutate
            def born(value,prior=prior):
                if prior:prior(value)
                self.identity(value)
                scene=value.get('source',{}).get('sceneLoads')
                if scene is not None:
                    # Both independent reads sample one actual modeled import
                    # ledger; its own read counter is shared across sources.
                    self.scene_sequence+=1;scene['sequence']=self.scene_sequence
            producer.mutate=born
            reader=producer.reader();reader.pid=43;reader.monotonic=world.mono
            self.sources[name]=reader
        self.ui_sequence=self.reply_sequence=0;self.reply_queries=[]
        owner=self
        class UI(normal_input.NativeInput):
            def __init__(self):pass
            def capture(self):
                sdk.gpu.clock+=.001;owner.ui_sequence+=1;value=observed()
                value.update(processId=43,instance=str(uuid.UUID(hex=owner.name('ui'))),sampleEpochMs=sdk.gpu.epoch(),
                    elapsedMs=round(sdk.gpu.clock*1000),
                    placesControlsVersion=2,placesSourceSequence=owner.ui_sequence,
                    navigationDialogControlsVersion=1,navigationDialogSourceSequence=owner.ui_sequence)
                return normal_input.observation(value,43,sdk.gpu.epoch())
        self.sources['ui']=UI()
        def replies():
            sdk.gpu.clock+=.001;self.reply_sequence+=1
            return json.dumps(dict(navigationReplyVersion=1,commandId=self.reply_queries[-1]['commandId'],runId=world.run,
                instance=self.name('replies'),sequence=self.reply_sequence,processId=43,capturedEpochMs=sdk.gpu.epoch(),
                currentLookupGeneration=1,currentLookupActive=False,events=[]))
        self.sources['replies']=NativeNavigationReplies(self.reply_queries.append,replies,sdk.gpu.epoch,
            lambda:life.pid==43,43,ios=True,monotonic=world.mono,sleep=sdk.gpu.sleep)
        source=life.sources('owned')
        self.native=source['observer'].bound_native_observer(source['clock_source'])

    def name(self,key):return hashlib.sha256((self.birth+key).encode()).hexdigest()[:32]

    def identity(self,value):
        # This is the new physical model's birth-time emission hook. It changes
        # no timestamps or counters and never receives an archived DTO.
        if type(value) is list:
            for item in value:self.identity(item)
        elif type(value) is dict:
            for key,item in value.items():
                if key=='processId':value[key]=43
                elif key in ('instance','treeInstance'):
                    new=self.name(str(item));value[key]=str(uuid.UUID(hex=new)) if '-' in str(item) else new
                else:self.identity(item)

    def owner(self,selector,client,initial,before,receipt,lock):
        h=self.h
        return NavigationProcessOwner(PrivateFeatureState(h.root/'ios-navigation-process-context.json'),
            initial,before,receipt,[str(h.root/name) for name in OWNERS],lock,lambda:h.lifecycle.pid==43,
            native=self.native,sources=self.sources,fixture=h.fixture,epoch_ms=h.now,monotonic=h.mono)
