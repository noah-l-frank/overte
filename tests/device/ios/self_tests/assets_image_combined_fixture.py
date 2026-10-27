"""Fresh shared target for original QML Model and normal Script marker events.

All source packets are produced from the live modeled entity maps on one
PID/run/tree/clock, before their first acquisition. No retained original is
rewritten. Native parser, Web painting and GPU rendering remain explicit
models; original QML, staged marker JS, journals and private bytes execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import math
from types import SimpleNamespace
import uuid
import weakref
from unittest.mock import patch
from PIL import Image,ImageDraw
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import canonical
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_image_sample import AssetsImageSample
from ios.adapters import assets_model_images as image_math,assets_model_renderers,avatar_renderers,create_state
from ios.adapters.create_marker_files import OwnedCreateMarkerFiles
from ios.adapters.create_originals import IOSCreateOriginals
from ios.adapters.create_marker_scope import marker_name
from ios.self_tests import assets_parsed_fixture as parsed
from ios.self_tests.assets_marker_scope_fixture import AssetsMarkerDomain
from ios.self_tests.test_ios_create_marker_scope import MarkerScopeTests
from ios.self_tests import test_ios_emote_marker_owner as marker_packets
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL
from ios.self_tests.assets_picker_fixture import EPOCH
from ios.self_tests import assets_upload_fixture as upload_fixture
from ios.self_tests.test_ios_avatar_renderers import packet as avatar_template
from self_tests.test_native_vulkan_world_frame import World
from feature_journeys.evidence import challenge
from adapters.graphics_subject_geometry import projected_box


class CombinedBoundary(parsed.Boundary):
    def __init__(self,directory):
        self.model_birth_rows={};self.model_birth_events=[]
        super().__init__(directory)
    def exchange(self,value):
        result=super().exchange(value)
        for identity,item in self.entities.items():
            if identity in self.model_birth_rows:continue
            born=item.created//1000;sequence=len(self.model_birth_events)+1;birth=uuid.uuid4().hex
            self.model_birth_events.append(dict(sequence=sequence,kind='inserted',id=identity,birth=birth,epochMs=born,monotonicMs=born-EPOCH))
            self.model_birth_rows[identity]=dict(id=identity,birth=birth,insertedSequence=sequence,bornEpochMs=born,bornMonotonicMs=born-EPOCH,
                removedSequence=0,removedEpochMs=0,removedMonotonicMs=0,destroyed=False,destructionObservedEpochMs=0,destructionObservedMonotonicMs=0)
        return result
    def clock_original(self,value):
        super().clock_original(value)
        # Initial modeled avatar state is selected before any original Model
        # or marker observation. No avatar action is issued by the test.
        value['animation']['overrideActive']=False;value['animation'].pop('clip',None)
    def state(self,request_id=None):
        value=super().state(request_id)
        value['source']['view'].update(aspectRatio=1.6,uiWidth=640,uiHeight=400)
        return value


class ParsedFixture(parsed.Fixture):
    boundary_type=CombinedBoundary
    def __init__(self,directory):
        lock_type=upload_fixture.ScriptSourceLock
        # Select the common canonical lock at initial construction, before
        # any Model/marker originals or ownership metadata exist. Existing
        # standalone Assets fixture defaults remain unchanged.
        def canonical_lock(path):return lock_type(path.with_name('script-feature-sources.lock'))
        with patch.object(upload_fixture,'ScriptSourceLock',side_effect=canonical_lock):super().__init__(directory)


class CombinedMarkerDomain(AssetsMarkerDomain):
    def __init__(self,scope,boundary):
        self.driver=boundary;self.started=False;self.initial_time=0
        super().__init__(scope);self.started=True
        self.boundary=boundary.native_clock
        self.world_template['runId']=scope.run
        source=self.world_template['source'];actual=boundary.state()['source']
        source['domain']['domainId']=actual['domainId']
        source['tree']['treeInstance']=actual['tree']['treeInstance'];self.entity_tree_birth=actual['tree']['treeInstance']
        for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective'):source['view'][key]=deepcopy(actual['view'][key])
        self.tree_born=EPOCH;self.entity_events=deepcopy(boundary.model_birth_events)
        self.entity_rows=[(weakref.ref(item),deepcopy(boundary.model_birth_rows[identity])) for identity,item in boundary.entities.items()]
        self.attach_readers(scope)
    @property
    def time(self):return self.driver.monotonic() if self.started else self.initial_time
    @time.setter
    def time(self,value):
        if self.started:self.driver.elapsed=round(value*1000)
        else:self.initial_time=value
    def epoch(self):return self.driver.clock()
    def sleep(self,seconds):self.driver.sleep(seconds)
    def attach_readers(self,scope):
        scope.monotonic=self.driver.monotonic;scope.sleep=self.sleep;scope.epoch_ms=lambda:1900000000000+self.driver.elapsed
        scope.native=NativeFeatureObservation(self.native_send,self.boundary.original,self.epoch,lambda:self.driver.live,42,
            ios=True,native_clock_bound=True,monotonic=self.driver.monotonic,sleep=self.sleep)
        scope.world=SimpleNamespace(last=None,read=self.world);scope.create=SimpleNamespace(last=None,read=self.create)
        scope.entities=SimpleNamespace(last=None,read=self.entities);scope.terminals=SimpleNamespace(last=None,read=self.terminal)
        scope.dialogs=SimpleNamespace(last=None,read=self.dialogs);scope.web=SimpleNamespace(last=None,read=self.web)
        scope.work=SimpleNamespace(last=None,read=self.work);scope.live=dict(native=SimpleNamespace(capture=self.widgets))
    def native_send(self,query):self.driver.tick(5);self.boundary.send(query)
    def start(self):super().start();self.paint()
    def fresh(self,value):
        # These are fresh producer return objects, never stored originals.
        def visit(node):
            if isinstance(node,dict):
                for key,item in node.items():
                    if key=='processId' and item==31:node[key]=42
                    else:visit(item)
            elif isinstance(node,list):
                for item in node:visit(item)
        visit(value);return value
    def current(self):
        value=self.driver.state();source=value['source'];entities=source['entities'];tree=source['tree']
        if self.running:
            row=deepcopy(self.marker);row.update(createdEpochUs=row['lastEditedEpochUs'],shape='',modelURL='',textures='',locked=False,
                lastEditedBy=source['localSessionId'],model={},voxels={})
            entities.append(row);raw=canonical(row)
            tree['entities'].append(dict(id=row['id'],hostType=row['hostType'],ready=True,createdEpochUs=row['createdEpochUs'],
                lastEditedEpochUs=row['lastEditedEpochUs'],lastEditedAfterEpochUs=row['lastEditedEpochUs'],semanticBytes=len(raw),semanticSha256=hashlib.sha256(raw).hexdigest()))
        entities.sort(key=lambda row:row['id']);tree['entities'].sort(key=lambda row:row['id']);tree['totalEntities']=len(entities)
        revision=self.driver.entity_revision+(0 if self.worker is None else 1 if self.running else 2)
        tree.update(revisionBefore=revision,revisionAfter=revision);source['tabletShown']=self.io.qt.opened
        return value
    def create(self,run):
        value=self.current();value.update(runId=run,requestId='ios-'+uuid.uuid4().hex)
        self.scope.create.last=deepcopy(value);return value
    def world(self,run):
        with patch.object(marker_packets,'RUN',run):value=super().world(run)
        value=self.fresh(value);value.update(runId=run);source=value['source'];actual=self.current()['source']
        source['tree']=deepcopy(actual['tree']);source['domain']['domainId']=actual['domainId']
        source['domain']['selfSha256']=hashlib.sha256(uuid.UUID(actual['localSessionId']).bytes).hexdigest()
        effects=source['scriptOriginal']['source']['effects'];effects['scannedEntities']=len(actual['entities'])
        effects['entities']=[dict(id=row['id'],name=row['name'],type=row['type'],hostType=row['hostType'],userData=row['userData'],
            lastEditedEpochUs=int(row['lastEditedEpochUs']),color=[0,0,0]) for row in actual['entities'] if row['name'].startswith('e2e-'+run+'-')]
        self.scope.world.last=deepcopy(value);return value
    def entities(self,run):
        value=self.fresh(super().entities(run));tree=value['source']['tree'];tree['treeBornEpochMs']=self.tree_born
        tree['treeInstance']=self.driver.entity_tree_instance
        self.scope.entities.last=deepcopy(value);return value
    def terminal(self,after):
        value=self.fresh(super().terminal(after));self.scope.terminals.last=deepcopy(value);return value
    def dialogs(self,run):
        value=self.fresh(super().dialogs(run));self.scope.dialogs.last=deepcopy(value);return value
    def web(self,run,url):
        value=self.fresh(super().web(run,url));self.scope.web.last=deepcopy(value);return value
    def work(self,manager,after):
        value=self.fresh(super().work(manager,after));self.scope.work.last=deepcopy(value);return value
    def widgets(self):return self.fresh(super().widgets())
    def file_request(self,operation,run,owner,files=None):
        result=super().file_request(operation,run,owner,files)
        self.files.last_packet=self.fresh(self.files.last_packet);return result


class Fixture:
    def __init__(self,test,directory):
        self.f=ParsedFixture(directory);test.addCleanup(self.f.close)
        test.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.f))
        self.model,self.baking=self.f.prepared();self.parsed=self.f.parsed(self.model,self.baking);self.parsed.reserve();self.proof=self.parsed.observe()
        self.model.usage.close_clients()
        source=self.model.usage.source;template=MarkerScopeTests();template.root=source.store.path.parent;template.lock=self.f.lock
        scope=template.owner(binding=source.binding)
        scope.run,scope.role,scope.namespace,scope._version=RUN,'primary','assets',3;scope.fixture_url,scope.ticket=URL,TICKET
        scope.store=PrivateFeatureState(template.root/marker_name('primary','assets'));scope.previous=scope.store.read();scope.guard=lambda:self.f.boundary.live
        scope.files=OwnedCreateMarkerFiles(None,scope.marker_store('files'),source.binding)
        scope.originals=IOSCreateOriginals(template.root,source.binding,RUN,'primary',scope.guard,scope.storage_intent,kind='inputs',namespace='assets-marker')
        self.scope=scope;self.domain=CombinedMarkerDomain(scope,self.f.boundary)
        self.marker=OwnedAssetsMarker(scope,PrivateFeatureState(template.root/('ios-assets-marker-'+RUN+'-primary.json')))
        self.marker.reserve();self.image_sources=None

    def sample(self,request):
        if self.image_sources is None:self.image_sources=ImageSources(self)
        source=self.image_sources;boundary=self.f.boundary;native=self.scope.native
        def reader(module,produce):
            raw=['']
            def send(query):module.command(query);raw[0]=json.dumps(produce(query))
            def epoch():return native.read(native.sequence)['capturedEpochMs']
            cls={create_state:create_state.IOSCreateState,assets_model_renderers:assets_model_renderers.IOSAssetsModelRenderers,
                avatar_renderers:avatar_renderers.IOSAvatarRenderers}[module]
            return cls(send,lambda:raw[0],epoch,lambda:boundary.live,42,monotonic=boundary.monotonic,sleep=boundary.sleep)
        def gpu_reader(intent,received):return NativeVulkanWorldFrame(source.gpu.send,source.gpu.original,boundary.clock,lambda:boundary.live,42,
            intent,receipt=received,monotonic=boundary.monotonic,sleep=boundary.sleep)
        frame=VulkanWorldFrameOwner(PrivateFeatureState(self.scope.root/('graphics-world-frame-primary-0-'+request[4:]+'.json')),
            self.scope.root,self.scope.binding,RUN,'primary',0,request,gpu_reader,lambda:boundary.live,source_lock=self.f.lock,
            monotonic=boundary.monotonic,sleep=boundary.sleep)
        owner=AssetsImageSample(PrivateFeatureState(self.scope.root/('ios-assets-image-'+RUN+'-primary-'+request[4:]+'.json')),
            self.f.lock,self.scope.binding,RUN,request,lambda:boundary.live,parsed=self.parsed,marker=self.marker,native=native,
            state=reader(create_state,source.create),models=reader(assets_model_renderers,source.models),avatars=reader(avatar_renderers,source.avatars),frame_owner=frame,
            epoch_ms=lambda:1900000000000+boundary.elapsed,monotonic=boundary.monotonic)
        return owner,source


class ImageSources:
    def __init__(self,fixture):
        self.f=fixture;self.b=fixture.f.boundary;self.sequences=dict(models=0,avatars=0)
        self.instances={kind:uuid.uuid4().hex for kind in self.sequences};self.gpu=ImageGpu(self)
    def create(self,query):
        value=self.f.domain.current();value.update(requestId=query['commandId'],runId=query['runId']);return value
    def bounds(self,identity):
        row=self.b.entities[identity].properties
        return dict(corner=[a-b/2 for a,b in zip(row['position'],row['dimensions'])],dimensions=deepcopy(row['dimensions']))
    def models(self,query):
        self.sequences['models']+=1;self.b.tick();before=self.b.stamp();current=self.f.domain.current()['source'];rows=[]
        for index,(identity,item) in enumerate(sorted(self.b.entities.items())):
            model=self.b.models[identity];origin=self.b.origin_rows[identity];ready=model.loaded and model.added and not model.failed
            rows.append(dict(entityId=identity,present=True,loaded=model.loaded,addedToScene=model.added,renderable=ready,needsFixup=False,
                visible=item.properties['visible'],failed=model.failed,origin=dict(modelUrl=item.properties['modelURL'],watcherUrl=item.properties['modelURL'],
                geometry=dict(readerId=origin['id'],mappingIds=[])),renderItemIds=[index+1] if ready else [],boundsReady=ready,bounds=self.bounds(identity) if ready else None))
        self.b.tick();return dict(iosAssetsModelRenderersVersion=1,requestId=query['commandId'],runId=query['runId'],instance=self.instances['models'],
            sequence=self.sequences['models'],processId=42,clockDomain='native-main-assets-model-renderers',clockBefore=before,clockAfter=self.b.stamp(),
            source=dict(complete=True,domainId=current['domainId'],localSessionId=current['localSessionId'],tree=current['tree'],models=rows,
                renderedPixelsAvailable=False,resourceRetirementAvailable=False))
    def avatars(self,query):
        self.sequences['avatars']+=1;self.b.tick();before=self.b.stamp();current=self.f.domain.current()['source'];value=avatar_template()
        value.update(runId=query['runId'],requestId=query['commandId'],instance=self.instances['avatars'],sequence=self.sequences['avatars'],clockBefore=before)
        own=value['source']['avatars'][0];own['sessionId']=current['localSessionId'];own['bounds']=deepcopy(self.f.domain.world_template['source']['avatar']['bounds'])
        own['rigPose'].update(capturedEpochMs=self.b.clock(),evaluationSequence=self.sequences['avatars'],rigId=self.b.native_clock.sample['animation']['rigId'])
        value['source'].update(avatars=[own],avatarEntities=[],tree=current['tree']);self.b.tick();value['clockAfter']=self.b.stamp();return value
    def view(self):
        actual=deepcopy(self.f.domain.current()['source']['view']);near,far=.1,100.;f=1/math.tan(math.radians(actual['fieldOfViewDegrees'])/2)
        return {key:actual[key] for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')}|dict(nearClip=near,farClip=far,
            projection=[f/actual['aspectRatio'],0,0,0,0,f,0,0,0,0,-(far+near)/(far-near),-2*far*near/(far-near),0,0,-1,0])
    def regions(self):
        view=self.view();extent=[640,400];mark=projected_box(self.f.domain.marker,view,extent)
        marker=[math.ceil(mark[0])+2,math.ceil(mark[1])+2,math.floor(mark[2])-2,math.floor(mark[3])-2]
        bounds=image_math.box(self.bounds(self.f.proof['entityId']),view,extent)
        middle=[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2]
        subject=[round(middle[0]-20),round(middle[1]-20),round(middle[0]+20),round(middle[1]+20)]
        return dict(source='world-render-target',marker=marker,subject=subject)
    def render(self):
        view=self.view();extent=[640,400];image=Image.new('RGBA',tuple(extent),(70,70,70,255));draw=ImageDraw.Draw(image);calls=0
        for identity,model in self.b.models.items():
            if not (model.loaded and model.added) or model.failed:continue
            box=image_math.box(self.bounds(identity),view,extent)
            if box is None:continue
            left,top,right,bottom=[round(item) for item in box]
            # Declared mesh renderer model driven by actual loaded object
            # geometry; it is not the native renderer or a feature verdict.
            for y in range(top,bottom,8):
                for x in range(left,right,8):draw.rectangle((x,y,min(x+7,right),min(y+7,bottom)),fill=(30,60,130,255) if (x//8+y//8)%2 else (170,210,230,255))
            calls+=1
        if self.f.domain.running:
            roi=self.regions()['marker'];bits=''.join(f'{byte:08b}' for byte in challenge(RUN,TICKET))
            for index,bit in enumerate(bits):
                x,y=index%32,index//32
                draw.rectangle((math.floor(roi[0]+x*(roi[2]-roi[0])/32),math.floor(roi[1]+y*(roi[3]-roi[1])/4),
                    math.ceil(roi[0]+(x+1)*(roi[2]-roi[0])/32)-1,math.ceil(roi[1]+(y+1)*(roi[3]-roi[1])/4)-1),fill='white' if bit=='1' else 'black')
            calls+=1
        stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes(),calls


class ImageGpu(World):
    def __init__(self,source):
        self.driver=None;self.initial_clock=0;super().__init__();self.driver=source.b;self.source=source
        self.offset=EPOCH;self.source_extent=[320,200];self.target_extent=[640,400];self.fault=self.decorate
    @property
    def clock(self):return self.driver.monotonic() if self.driver is not None else self.initial_clock
    @clock.setter
    def clock(self,value):
        if self.driver is None:self.initial_clock=value
        else:self.driver.elapsed=round(value*1000)
    def send(self,query):
        if query['operation']=='read':self.png,self.raw_pixels,self.actual_draws=self.source.render()
        super().send(query)
    def decorate(self,value):
        source=value.get('source',{})
        if 'renderTrace' in source:source['renderTrace']['recordedView']=self.source.view()
        if 'image' in source:source['image'].update(width=640,height=400)
