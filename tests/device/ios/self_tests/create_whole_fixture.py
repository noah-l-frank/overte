"""Composed Create SDK boundary: actual Node Script, PNGs, files and weakrefs.

All Qt/native/product/renderer DTOs are modeled. No installed Overte, native
compiler or device executes. The real Python owners and normal Node Script run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
import uuid
import weakref
from unittest.mock import patch
from PIL import Image,ImageDraw

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.graphics_subject_geometry import projected_box
from feature_journeys.fixtures import challenge
from feature_journeys.witness import Journal
from ios.adapters.create_originals import IOSCreateOriginals
from ios.adapters.create_primary import CreatePrimary
from ios.adapters.create_retirement import CreateRetirement
from ios.adapters.create_sample import CreateSampleOwner
from ios.adapters.create_world_input import CreateWorldInput
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters.normal_input import NativeInput
from ios.adapters import pointer_state
from ios.self_tests import test_ios_create_primary_images as images
from ios.self_tests import test_ios_create_marker_scope as scopes
from ios.self_tests import test_ios_pointer_state as pointers
from ios.self_tests.create_marker_domain_fixture import RunningDomain
from ios.self_tests.test_ios_create_files import BINDING,URL
from ios.self_tests.test_ios_create_state import RUN
from ios.self_tests.test_ios_create_work import packet as default_work
from self_tests.test_native_vulkan_world_frame import World


class Item:pass


class ComposedCreate:
    def __init__(self,case,*,baseline_image=True):
        self.case=case;self.h=images.CreatePrimaryImagesTests();self.h.setUp();case.addCleanup(self.h.doCleanups)
        self.held=self.h.h.held();self.held.__enter__();case.addCleanup(self.held.__exit__,None,None,None)
        self.root,self.lock,self.product=self.h.h.root,self.h.h.lock,self.h.product
        original_read=self.product.read;self.tree_revision=0;self.tree_rows=None
        def product_read(run):
            result=original_read(run);tree=result['source']['tree']
            if tree['entities']!=self.tree_rows:self.tree_revision+=1;self.tree_rows=deepcopy(tree['entities'])
            tree.update(revisionBefore=self.tree_revision,revisionAfter=self.tree_revision)
            self.product.value['source']['tree']=deepcopy(tree);return result
        self.product.read=product_read
        marker=scopes.MarkerScopeTests();marker.root=self.root;marker.lock=self.lock;self.scope=marker.owner(BINDING)
        s=self.scope;s.run=RUN;s.fixture_url=URL;s.ticket='1'*32
        s.originals=IOSCreateOriginals(self.root,BINDING,RUN,'primary',s.guard,s.storage_intent,kind='inputs')
        domain_patch=patch('ios.self_tests.test_ios_emote_marker_owner.RUN',RUN);domain_patch.start();case.addCleanup(domain_patch.stop)
        self.clock=SimpleNamespace(clock=0.,offset=self.h.sh.sdk.offset)
        self.clock.epoch=lambda:self.clock.offset+round(self.clock.clock*1000)
        self.h.h.sdk.shared=self.clock
        clock=self.clock
        class Domain(RunningDomain):
            @property
            def time(_self):return clock.clock
            @time.setter
            def time(_self,value):clock.clock=value
            def epoch(_self):return self.h.sh.sdk.epoch()
        Domain.epoch=lambda _self:clock.epoch()
        self.domain=Domain(s);d=self.domain
        # Model one actual native clock/source birth for the process, shared by
        # all collectors, rather than resetting a counter for each owner.
        native_send=d.native_send
        def send(query):native_send(query);d.boundary.sample['processId']=42
        s.native=NativeFeatureObservation(send,d.boundary.original,clock.epoch,lambda:True,42,ios=True,native_clock_bound=True,
            monotonic=lambda:d.time,sleep=d.sleep)
        s.epoch_ms=lambda:d.epoch();s.monotonic=lambda:d.time
        d.world_template['runId']=RUN;d.world_template['source']['scriptOriginal']['processId']=42
        d.world_template['source']['domain']['domainId']=self.product.value['source']['domainId']
        d.world_template['source']['view'].update({key:deepcopy(self.product.value['source']['view'][key])
            for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')})
        self.product.value['source']['tree']['treeInstance']=d.world_template['source']['tree']['treeInstance']
        d.entity_tree_birth=d.world_template['source']['tree']['treeInstance']
        self.items={};self.lifetimes=[]
        original_create=self.product.create;original_delete=self.product.delete
        def create(*args,**kwargs):
            original_create(*args,**kwargs)
            selected=self.product.page()['page']['selectedIds']
            if not selected:return
            id_=selected[0]
            if id_ in self.items:return
            item=Item();item.model=Item() if self.product.selected()['type']=='Model' else None;self.items[id_]=item
            self.lifetimes.append(dict(id=id_,item=weakref.ref(item),model=None if item.model is None else weakref.ref(item.model),
                born=d.epoch(),destroyed=0,modelDestroyed=0,modelInstance=uuid.uuid4().hex))
        def delete():
            id_=self.product.selected()['id'];original_delete();self.items.pop(id_,None)
        self.product.create=create;self.product.delete=delete;self.h.ah.ui.delete_entity=delete
        domain_create=d.create;domain_world=d.world
        def sync():
            previous=deepcopy(s.create.last);current=domain_create(RUN);s.create.last=previous
            local=current['source']['entities'];domain=[row for row in self.product.value['source']['entities'] if row['hostType']=='domain']
            self.product.value['source']['entities']=deepcopy(local)+domain
            if local:self.product.marker=deepcopy(local[0])
            self.product.read(RUN)
        self.sync=sync
        def world(run):
            sync();value=domain_world(run);value['processId']=42;value['source']['scriptOriginal']['processId']=42
            scripts=value['source']['scriptOriginal']['source'];edit=default_work()['source']['roles'][0]
            scripts['sourceIdentityVersion']=1;scripts['engines'].append(dict(url=edit['manager']['url'],running=True,stopping=False,finished=False,
                code=deepcopy(edit['code']),required=dict(instance=edit['manager']['instance'],sequence=0,modules=[])))
            scripts['membership']['managers'].append(deepcopy(edit['manager']));scripts['membership']['revision']+=1
            value['source']['tree']=deepcopy(self.product.value['source']['tree']);return value
        d.world=world;s.world.read=world
        for name in ('entities','terminal','dialogs','web','widgets','work'):
            original=getattr(d,name)
            def read(*args,_original=original,**kwargs):
                value=_original(*args,**kwargs)
                def process(item):
                    if type(item) is dict:
                        for key,child in item.items():
                            if key=='processId':item[key]=42
                            else:process(child)
                    elif type(item) is list:
                        for child in item:process(child)
                process(value);return value
            setattr(d,name,read)
            reader=getattr(s,'terminals' if name=='terminal' else name,None)
            if reader is not None and hasattr(reader,'read'):reader.read=read
        s.live['native'].capture=d.widgets
        file_request=d.file_request
        def request(*args,**kwargs):
            result=file_request(*args,**kwargs);d.files.last_packet['processId']=42;return result
        d.files.request=request
        source_original=self.h.h.sdk.original
        def original(name):
            sync();value=json.loads(source_original(name))
            if name=='domain':
                value=world(RUN);value['requestId']=self.h.h.sdk.queries[name]['commandId']
            elif name=='work':
                rows=[];now=d.epoch()
                for row in self.lifetimes:
                    if row['item']() is None and not row['destroyed']:row['destroyed']=now
                    if row['model'] is not None and row['model']() is None and not row['modelDestroyed']:row['modelDestroyed']=now
                    rows.append(dict(id=row['id'],bornEpochMs=row['born'],destroyed=bool(row['destroyed']),destructionObservedEpochMs=row['destroyed'],models=[] if row['model'] is None else
                        [dict(instance=row['modelInstance'],bornEpochMs=row['born'],destroyed=bool(row['modelDestroyed']),destructionObservedEpochMs=row['modelDestroyed'])]))
                value['source']['entityLifetimes']['entities']=sorted(rows,key=lambda row:row['id'])
            return json.dumps(value)
        self.h.h.sdk.original=original;self.source=self.h.h.owner();self.source.readers['native']=s.native
        s.create=self.source.readers['create']
        self.history=CreatePrimary(PrivateFeatureState(self.root/'ios-create-primary.json'),self.lock,BINDING,RUN,self.source,lambda:True)
        self.journal=Journal(clock=lambda:d.epoch())
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('create')
        self.journal.activate(RUN,'1'*32);self.source.phase.client.request=lambda path,**kwargs:self.journal.phase(RUN,kwargs['phase_nonce'])
        self.history.capture()
        self.worlds={};self.gpu_sequence=0;self.gpu_frame=0
        self.pointer_native=pointers.NativePointerBoundary()
        def tick():d.time+=.001;self.pointer_native.now=d.epoch();return self.pointer_native.now
        self.pointer_native.tick=tick;self.pointer_native.mono=lambda:d.time
        self.pointer=pointer_state.IOSPointerState(self.pointer_native.send,self.pointer_native.original,lambda:d.epoch(),lambda:True,42,
            monotonic=lambda:d.time,sleep=d.sleep)
        self.geometry_query=None
        def geometry_send(query):self.geometry_query=deepcopy(query)
        def geometry_original():
            d.time+=.001
            return json.dumps(dict(schemaVersion=1,commandId=self.geometry_query['commandId'],observation=dict(schemaVersion=1,
                sampleSequence=1,sampleEpochMs=d.epoch(),nativeUi=dict(valid=True,surfaceWidth=640,surfaceHeight=400,
                    safeInsetLeft=0,safeInsetTop=0,safeInsetRight=0,safeInsetBottom=0,keyboardVisible=False,imeInsetBottom=0),
                window=dict(width=640,height=400))))
        self.geometry=OriginalGeometry(geometry_send,geometry_original,d.epoch,lambda:True,monotonic=lambda:d.time,sleep=d.sleep)
        normal=object.__new__(NativeInput);normal.capture=d.widgets;self.normal=normal
        self.w3c=[]
        def call(method,path,body=None):
            self.w3c.append((method,path,deepcopy(body)))
            if method=='GET':return dict(x=0,y=0,width=640,height=400)
            if method=='POST':
                point=body['actions'][0]['actions'][0];position=[point['x'],point['y']]
                self.pointer_native.touch('touch-begin',position=position)
                self.product.touch(self.product.selected()['id'],self.product.page()['id'],d.epoch())
                self.pointer_native.touch('touch-end',position=position)
        self.ui=NativeUI(SimpleNamespace(call=call),'actual-sdk-session',lambda:True,monotonic=lambda:d.time,sleep=d.sleep)
        self.render('1'*32)
        self.before=self.sample('ios-'+format(10000,'032x'))
        if baseline_image:self.before.capture('1'*32,d.epoch())
        self.retirement=CreateRetirement(PrivateFeatureState(self.root/'ios-create-primary-retirement.json'),self.source,self.history,self.pointer,
            scope=s,before_image=self.before,image_factory=self.sample,sleep=d.sleep)
        if baseline_image:self.retirement.admit()

    def sample(self,request):
        fixture=self;clock=self.clock
        if request not in self.worlds:
            self.render(self.journal.runs[RUN]['ticket'])
            class SharedWorld(World):
                def __init__(sdk):
                    sdk.initializing=True;super().__init__();sdk.initializing=False;sdk.offset=clock.offset
                @property
                def clock(sdk):return clock.clock
                @clock.setter
                def clock(sdk,value):
                    if not getattr(sdk,'initializing',False):clock.clock=value
                def send(sdk,query):
                    sdk.sequence=fixture.gpu_sequence;super().send(query);fixture.gpu_sequence=sdk.sequence
                def original(sdk):
                    sdk.sequence=fixture.gpu_sequence;raw=super().original();fixture.gpu_sequence=sdk.sequence;return raw
            sdk=SharedWorld();self.gpu_frame+=1;sdk.frame_index=self.gpu_frame;sdk.source_extent=[320,200];sdk.target_extent=[640,400]
            sdk.png=self.png;sdk.raw_pixels=self.raw_pixels
            def fault(value):
                if 'image' in value.get('source',{}):
                    value['source']['image'].update(width=640,height=400)
                    trace=value['source']['renderTrace'];trace['frameId']=format(sdk.frame_index,'032x')
                    view=self.product.value['source']['view'];recorded=trace['recordedView']
                    for key in ('position','rotation','fieldOfViewDegrees','aspectRatio'):recorded[key]=deepcopy(view[key])
            sdk.fault=fault;self.worlds[request]=sdk
        sdk=self.worlds[request]
        def factory(intent,receipt):return NativeVulkanWorldFrame(sdk.send,sdk.original,clock.epoch,lambda:True,42,intent,receipt=receipt,
            monotonic=lambda:clock.clock,sleep=sdk.sleep)
        frame=VulkanWorldFrameOwner(PrivateFeatureState(self.root/('graphics-world-frame-primary-0-'+request[4:]+'.json')),self.root,BINDING,RUN,'primary',0,request,
            factory,lambda:True,source_lock=self.lock,monotonic=lambda:clock.clock,sleep=sdk.sleep)
        return CreateSampleOwner(PrivateFeatureState(self.root/('ios-create-sample-'+request[4:]+'.json')),self.lock,BINDING,RUN,'primary',request,lambda:True,
            native=self.scope.native,source=self.source.readers['create'],frame_owner=frame,epoch_ms=clock.epoch,monotonic=lambda:clock.clock)

    def render(self,ticket):
        self.sync();image=Image.new('RGBA',(640,400),(95,95,95,255));draw=ImageDraw.Draw(image)
        colors=images.subject_colors([row for row in self.product.value['source']['entities'] if row['hostType']=='domain'])
        for y in range(0,400,10):
            for x in range(0,640,10):draw.rectangle((x,y,x+9,y+9),fill=colors[(x//10+y//10)%2]+(255,))
        if self.domain.running:
            from self_tests.test_native_completed_frame import view
            native=view();actual=self.product.value['source']['view']
            for key in ('position','rotation','fieldOfViewDegrees','aspectRatio'):native[key]=deepcopy(actual[key])
            box=projected_box(self.product.marker,native,[640,400]);x,y=int(box[0])+3,int(box[1])+3
            width=(int(box[2])-x-3)//32*32;height=(int(box[3])-y-3)//4*4
            self.policy=dict(source='world-render-target',marker=[x,y,x+width,y+height],subject=[0,170,640,400])
            for cell,bit in enumerate(''.join(f'{byte:08b}' for byte in challenge(RUN,ticket))):
                left=x+(cell%32)*width//32;top=y+(cell//32)*height//4
                draw.rectangle((left,top,left+width//32-1,top+height//4-1),fill='white' if bit=='1' else 'black')
        stream=BytesIO();image.save(stream,format='PNG');self.png=stream.getvalue();self.raw_pixels=image.tobytes()

    def prepare(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();self.sync()
        lease=self.scope.prepared();self.h.ah.marker=lease;actions=self.h.ah.owner();actions.prepare();actions.phase=self.source.phase
        self.history.actions=actions;self.history.marker=lease;self.history.sample_resolver=self.sample
        self.retirement.actions=actions;self.actions=actions
        self.h.ah.file_boundary.clock=self.h.h.sdk.tick;actions.files.native.clock_ms=self.h.h.sdk.tick
        actions.world_factory=self.world_input
        return actions

    def world_input(self,ticket):
        d=self.domain
        return CreateWorldInput(PrivateFeatureState(self.root/('ios-create-world-input-'+ticket+'.json')),BINDING,RUN,ticket,self.lock,
            self.scope.native,self.source.readers['create'],self.geometry,self.normal,self.ui,lambda:True,epoch_ms=d.epoch,monotonic=lambda:d.time)
