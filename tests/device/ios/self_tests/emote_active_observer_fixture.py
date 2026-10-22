"""Actual Emote JS/HTTP/private PNGs with explicitly modeled native producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import math
from types import SimpleNamespace
import threading
import uuid
from unittest.mock import patch
from urllib.request import urlopen
from PIL import Image,ImageDraw
from adapters.graphics_subject_geometry import projected_box
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from ios.adapters.emote_actions import IOSEmoteActions
from ios.adapters.emote_controls import IOSEmoteIO
from ios.adapters.emote_observer import IOSEmoteObserver
from ios.adapters.emote_samples import IOSEmoteSamples
from ios.adapters.emote_sources import IOSEmoteSources
from ios.self_tests import test_ios_emote_restoration_journey as native_fixture
from ios.self_tests.emote_script_vm_fixture import normal_ui
from ios.self_tests.emote_vm_rig_fixture import ActualVMRig
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class ActiveObserverFixture:
    def __init__(self,test,*,defer_setup=False):
        f=native_fixture.RestorationJourneyTests();f.setUp();test.addCleanup(f.doCleanups)
        self.f=f;self.scope,self.domain,self.root,self.lock=f.scope,f.domain,f.root,f.lock
        d=self.domain;self.vm,self.native,self.ui=normal_ui(test,clock=d);self.native.tablet=False
        self.rig=ActualVMRig(self.vm,d);self.scope.native=self.rig.reader()
        self.rig.augment=self.global_scripts;original_world=d.world
        def world(run):
            value=original_world(run)
            self.rig.epoch=self.rig.roots.epoch=d.epoch()
            value['source']['scriptOriginal']=self.rig.code_reader.read(self.rig.code_reader.sequence,
                require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
            return value
        d.world=world;self.scope.world.read=world
        self.server=make_server('r'*64,'a'*64,adapter_token='d'*64);self.server.journal.clock=self.scope.epoch_ms
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.server.journal.register('emotes')
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start()
        test.addCleanup(self.stop);self.client=Client('http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1','d'*64)
        self.url=self.client.url+'/runs/'+RUN+'/';self.scope.fixture_url=self.url
        self.ticket=None;self.activate('baseline')
        f.sources=self.runtime_sources;f.runtime._sources=self.runtime_sources
        f.pixels=self.pixels;f.renderers=self.renderers
        d.world_template['source']['avatar']['bounds']=dict(corner=[-.6,0,3.7],dimensions=[1.2,1.8,.6])
        f.template['source']['avatars'][1]['externalPose']=None
        if not defer_setup:self.scope.prepare();d.paint();self.scope.admit_rendered()
        self.phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic);self.phase.status()
        readers=dict(roots=self.rig.root_reader,scripts=self.rig.code_reader,native=self.rig.reader(),ui=IOSEmoteIO(self.native),
            world=SimpleNamespace(last=None,read=d.world))
        self.sources=IOSEmoteSources(PrivateFeatureState(self.root/'ios-emote-primary-sources.json'),self.root,BINDING,RUN,'primary',self.lock,
            lambda:True,self.phase,readers=readers,epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)
        # Original fixture PNG has its 32x4 cells at x=4..131,y=4..35;
        # preserve its asymmetric outer border in the complete world quad.
        self.policy=dict(source='world-render-target',marker=[705,480,865,520],subject=[760,560,840,800])
        self.samples=IOSEmoteSamples(f.runtime,'owned',self.scope,self.root,self.policy,self.phase,self.lock,
            epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic,sleep=self.scope.sleep)
        self.observer=IOSEmoteObserver(PrivateFeatureState(self.root/'ios-emote-primary-observer.json'),self.sources,BINDING,'primary',self.root,
            self.policy,self.phase,self.lock,lambda:True,samples=self.samples,epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)
        current=self
        class SDK(NativeUI):
            def __init__(self):self.calls=[];self.sleep=current.native.sleep
            def click(self,locator):self.calls.append(locator.value);current.native.tablet=locator.value=='OverteTabletOpen'
        self.sdk=SDK();self.actions=IOSEmoteActions(PrivateFeatureState(self.root/'ios-emote-inputs.json'),self.sources,self.sdk)

    def global_scripts(self,value):
        d=self.domain;source=value['source'];marker=d.marker
        if d.worker is not None:
            source['loads'].update(sequence=1,events=[dict(sequence=1,eventId='8'*32,managerInstance=d.worker['instance'],url=d.worker['url'],
                loadGeneration=d.worker['loadGeneration'],isURL=True,success=True,status='Success',callbackEpochMs=d.worker['assignedEpochMs'])])
            source['membership']['revision']=2 if d.running else 3
        if d.running:
            source['engines'].append(deepcopy(d.engine));source['membership']['managers'].append(deepcopy(d.worker))
            source['membership']['managers'].sort(key=lambda row:row['instance'])
            source['effects'].update(scannedEntities=1,entities=[dict(id=marker['id'],name=marker['name'],type=marker['type'],hostType=marker['hostType'],
                userData=marker['userData'],lastEditedEpochUs=int(marker['lastEditedEpochUs']),color=[0,0,0])])
        elif marker is not None:source['effects']['absentIds']=[marker['id']]

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def activate(self,verb,**inputs):
        self.ticket=uuid.uuid4().hex;self.server.journal.activate(RUN,self.ticket,verb,inputs)
        return dict(contractVersion=16,runId=RUN,ticket=self.ticket,fixtureUrl=self.url if hasattr(self,'url') else self.client.url+'/runs/'+RUN+'/',verb=verb,inputs=inputs)

    def runtime_sources(self,_selector):
        return dict(binding=deepcopy(BINDING),check=lambda:True,clock_source=None,observer=SimpleNamespace(
            bound_native_observer=lambda _:self.rig.reader(),emote_world=lambda _:SimpleNamespace(last=None,read=self.domain.world),
            avatar_renderers=lambda _:SimpleNamespace(last=None,read=self.renderers),vulkan_world_frame=self.vulkan))

    def renderers(self,run):
        value=native_fixture.RestorationJourneyTests.renderers(self.f,run)
        for row in value['source']['avatars']:
            if row['self']:
                row['bounds']=deepcopy(self.domain.world_template['source']['avatar']['bounds'])
                animation=self.rig.value['animation'];row['rigPose']=dict(rigId=animation['rigId'],capturedEpochMs=animation['capturedEpochMs'],
                    evaluationSequence=animation['evaluationSequence'],animationsEnabled=True,graphLoaded=True,
                    overrideActive=animation['overrideActive'],joints=deepcopy(animation['joints']))
            else:row['externalPose']=None;row['bounds']['corner'][0]=20
        return value

    def pixels(self):
        image=Image.new('RGBA',(1600,1000),(75,85,100,255));draw=ImageDraw.Draw(image)
        draw.rectangle((740,550,860,820),fill=(70,110,180,255))
        x=self.pixel_pose();offset=round((x-.1)*100)
        draw.rectangle((760+offset,560,779+offset,800),fill=(220,65,30,255))
        if self.domain.running:
            marker=self.domain.marker;box=projected_box(marker,self.f.recorded_view(),[1600,1000])
            with urlopen(self.url+'current',timeout=2) as response:
                import json
                ticket=json.load(response)['ticket']
            with urlopen(self.url+'tickets/'+ticket+'/marker.png',timeout=2) as response:raw=response.read()
            bitmap=Image.open(BytesIO(raw)).convert('RGBA');bounds=(math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3]))
            image.paste(bitmap.resize((bounds[2]-bounds[0],bounds[3]-bounds[1]),Image.Resampling.NEAREST),bounds[:2])
        stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes()

    def pixel_pose(self):return self.rig.value['animation']['joints'][0][4]

    def vulkan(self,intent,receipt):
        reader=native_fixture.RestorationJourneyTests.vulkan(self.f,intent,receipt);send=reader.send
        def sending(query):
            send(query);gpu=self.f.gpus[query['requestId']];gpu.source_extent=[800,500];gpu.target_extent=[1600,1000]
            old=gpu.fault
            def observed(packet):
                old(packet)
                if 'image' in packet.get('source',{}):packet['source']['image'].update(width=1600,height=1000)
            gpu.fault=observed
        reader.send=sending;return reader
