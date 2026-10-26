"""Ordinary token transport with explicit Qt/Create controller boundary.

Original Assets QML runs before this route. Create widgets/controller/entity
deletion are declared SDK models; cached object and Model/entity weak ownership
are real separate Python objects. No native parser, renderer or device runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
from types import SimpleNamespace
import uuid
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.normal_input import NativeInput,observation
from ios.self_tests import assets_parsed_fixture as parsed
from ios.self_tests.create_product_controls_fixture import ProductControls

RUN=parsed.RUN


class Product:
    def __init__(self,boundary):self.b=boundary;self.roots=[];self.search_original=None
    @property
    def value(self):
        return dict(source=dict(tabletShown=True,roots=self.roots,entities=[deepcopy(item.properties) for _id,item in sorted(self.b.entities.items())]))
    def page(self):
        rows=[row for row in self.roots if not row['destroyed']];need(len(rows)==1);return rows[0]
    def open(self):
        need(not any(not row['destroyed'] for row in self.roots));id_=str(uuid.uuid4())
        self.roots.append(dict(id=id_,kind='editor',destroyed=False,visible=True,active=True,
            page=dict(profile='native-create-v1',tab=0,selectedIds=[],statusError=False,statusText='',componentSourceSha256=hashlib.sha256(b'explicit Create widget source boundary').hexdigest(),inputReady=False),
            changed={},voxelSettings={},numericFocus=False,propertySearch=dict(rootId=id_,objectName='NativeCreatePropertySearch',text='')))
    def close(self):
        row=self.page();id_=row['id'];row.clear();row.update(id=id_,destroyed=True)
    def select(self,id_):need(id_ in self.b.entities);self.page()['page']['selectedIds']=[id_]
    def selected(self):
        ids=self.page()['page']['selectedIds'];need(len(ids)==1 and ids[0] in self.b.entities);return self.b.entities[ids[0]].properties
    def delete(self):
        id_=self.selected()['id'];self.b.entities.pop(id_);self.b.models.pop(id_);self.b.entity_revision+=1
        self.page()['page']['selectedIds']=[];gc.collect()


class Boundary(parsed.Boundary):
    def __init__(self,directory):
        self.create_product=None;self.create_widgets=None;self.input_ignored='';self.input_lost=''
        super().__init__(directory)

    def attach_create(self):
        self.create_product=Product(self);self.create_widgets=ProductControls(SimpleNamespace(product=self.create_product,domain=SimpleNamespace(time=0)),self.normal_instance)

    def state(self,request_id=None):
        result=super().state(request_id)
        if self.create_product is not None:
            result['source']['tabletShown']=True;result['source']['roots']=deepcopy(self.create_product.roots)
            for row in result['source']['roots']:
                if not row['destroyed']:row['propertySearch']['text']=self.create_widgets.texts.get('create.property-search','')
        return result

    def normal(self):
        result=super().normal()
        if self.create_widgets is None:return result
        self.create_widgets.fixture.domain.time=self.monotonic();create=self.create_widgets.capture();rows=create['controls']
        if self.host_state['pageAlive']:rows=[row for row in rows if row['id'].startswith('tablet.')]
        result.update(tabletShown=True,createControlsVersion=2,createGeneration=self.create_widgets.generation)
        for index,row in enumerate(rows):result['controls'].append(dict(deepcopy(row),frame=dict(x=110,y=index*48,width=100,height=48)))
        return observation(result,42,self.clock())

    def native_input(self):
        original=super().native_input();boundary=self
        class Input(NativeInput):
            def __init__(self):
                self.monotonic=boundary.monotonic;self.sleep=boundary.sleep;self.native_epoch_ms=boundary.clock
                self.process=dict(pid=42);self.instance=boundary.normal_instance;self.last_receipt=None
            def capture(self):
                if boundary.create_widgets is None:
                    previous=getattr(original,'observe_intent',None);original.observe_intent=getattr(self,'observe_intent',None)
                    try:
                        value=original.capture();self.last_receipt=deepcopy(original.last_receipt);return value
                    finally:original.observe_intent=previous
                query=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe')
                intent=getattr(self,'observe_intent',None)
                if intent is not None:intent(deepcopy(query))
                value=boundary.normal();self.last_receipt=dict(schemaVersion=1,commandId=query['commandId'],observation=deepcopy(value));return value
            def deliver(self,command,*,before_send=None):
                if boundary.create_widgets is None:
                    result=original.deliver(command,before_send=before_send);self.last_receipt=deepcopy(original.last_receipt);return result
                if before_send is not None:need(before_send() is not False)
                current=boundary.normal();targets=[row for row in current['controls'] if row['token']==command['fieldToken']];need(len(targets)==1)
                id_=targets[0]['id'];need(command['sequence']==boundary.sequence_input+1 and command['instance']==boundary.normal_instance)
                boundary.sequence_input=command['sequence'];boundary.inputs.append(deepcopy(command))
                if id_!=boundary.input_ignored:
                    if id_=='tablet.home' and boundary.host_state['pageAlive']:boundary.exchange(dict(op='input',id='assets.home',action='activate'))
                    else:
                        reference=boundary.create_widgets.capture();value=command.get('text',command.get('index',command.get('direction')))
                        boundary.create_widgets.input(id_,command['operation'],reference,value)
                boundary.tick()
                if id_==boundary.input_lost:raise NativeUIError('lost original Create token return')
                self.last_receipt=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,status=dict(schemaVersion=1,commandId=command['commandId'],instance=command['instance'],
                    sequence=command['sequence'],performed=True,processId=42,sampleEpochMs=boundary.clock()))
                return dict(performed=True)
        return Input()


class Fixture(parsed.Fixture):
    boundary_type=Boundary
    def prepared_removal(self):
        model,baking=self.prepared();owner=self.parsed(model,baking);owner.reserve();owner.observe()
        self.boundary.attach_create();return owner
