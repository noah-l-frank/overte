"""Actual Create parent/CAS/phase/readers with declared UI/domain/renderer actors."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import uuid
import unittest
from unittest.mock import patch
import test_create_journey as parent_fixture
from test_create_journey import RuntimeIO,UnifiedIO,HomeActor,AdapterActor
from test_create_models import ModelBackend
from test_create_model_resource_join import ResourceActor
from adapters.pico4.create_extra_ui import TokenCreateExtraUI,snapshot,same_reference,IDS,COUNTS,FIELDS
from adapters.pico4.create_primitives import CANONICAL
from adapters.pico4.create_entities import voxel_source
from adapters.token_create_ui import TokenCreateUI
from adapters.normal_ui import NativeUIError

SESSION='22222222-2222-2222-2222-222222222222'


def initialize(b):
    if hasattr(b,'extra_rows'):return
    b.extra_rows=[];b.extra_sequence=0;b.polyvox=False;b.extra_choices={k:0 for k in COUNTS};b.extra_choices['create-extra.polyvox.style']=3
    b.extra_fields={k:'20' for k in FIELDS};b.local_creations=[];b.creation_times={};b.position_fields=dict(x='',y='',z='')
    b.extra_context_retained=False;b.voxel_dirty=False;b.voxel_empty=False;b.foreign_creation=False


def inventory(b):
    initialize(b);b.extra_sequence+=1
    return dict(createExtraUiInventoryVersion=1,instance='4'*32,sourceSequence=b.extra_sequence,
        elapsedMs=round(b.now()*1000),complete=True,pages=deepcopy(b.extra_rows))


class ExtraIO:
    def __init__(self,b):self.b=b
    def capture(self):
        b=self.b;initialize(b);rows=[]
        ids=IDS-{'create-extra.detail-kind','create-extra.detail-open'} if b.polyvox else {'create-extra.detail-kind','create-extra.detail-open'} if b.editor else set()
        for identifier in sorted(ids):
            row=dict(id=identifier,enabled=True,focused=b.focus==identifier,inputReady=identifier!='create-extra.polyvox.page')
            if identifier in FIELDS:row['text']=b.extra_fields[identifier]
            elif identifier in COUNTS:row.update(count=COUNTS[identifier],currentIndex=b.extra_choices[identifier])
            elif identifier=='create-extra.polyvox.page':row.update(profile='original-new-polyvox-v1',pageId=b.extra_rows[-1]['id'])
            elif identifier=='create-extra.polyvox.add' and b.extra_choices['create-extra.polyvox.preset']==0:row.update(enabled=False,inputReady=False)
            row['token']=uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)).hex;rows.append(row)
        return snapshot(dict(createExtraControlsVersion=1,open=b.opened,ready=b.opened,scope=b.scope(),controls=rows,createExtraUiInventory=inventory(b)))
    def command(self,identifier,action,reference,value=None):
        b=self.b;same_reference(reference,self.capture(),identifier);b.before_input();b.ui.command_sequence+=1
        b.inputs.append(dict(controlId=identifier,action=action,value=value))
        if action=='select-index':b.extra_choices[identifier]=value
        elif action=='replace':b.extra_fields[identifier]=value
        elif identifier=='create-extra.detail-open':
            assert b.extra_choices['create-extra.detail-kind']==3;b.polyvox=True
            b.extra_rows.append(dict(id=uuid.uuid4().hex,contextId=uuid.uuid4().hex,windowId='3'*32,firstObservedEpochMs=b.epoch(),
                pageAlive=True,contextAlive=True,windowAlive=True))
        elif identifier=='create-extra.polyvox.add':
            entity=str(uuid.uuid4());created=b.epoch()*1000;b.creation_times[entity]=created
            b.local_creations.append(dict(sequence=len(b.local_creations)+1,id=entity,type='PolyVox',hostType='domain',
                sessionId=SESSION,createdEpochUs=created,observedEpochMs=b.epoch()))
            b.rows=[dict(id=entity,name='terrain',type='PolyVox',hostType='domain',modelUrl='',textures='',position=[0,1,-12.8],rotation=[0,0,0,1],
                dimensions=[8,8,8],parentId=None,visible=True,locked=False,lastEditedEpochUs=created,visuallyReady=True,naturalDimensions=[1,1,1],
                textureNames={},renderInfo=dict(vertices=0,textures=0,textureBytes=0,drawCalls=1))]
            b.selected=[entity];b.dimensions=dict(x='8',y='8',z='8');b.polyvox=False
            b.extra_rows[-1].update(pageAlive=False,contextAlive=b.extra_context_retained)
            if b.foreign_creation:
                b.local_creations.append(dict(sequence=2,id=str(uuid.uuid4()),type='Shape',hostType='domain',sessionId=SESSION,
                    createdEpochUs=created,observedEpochMs=b.epoch()))
        elif identifier=='create-extra.polyvox.cancel':
            b.polyvox=False;b.extra_rows[-1].update(pageAlive=False,contextAlive=b.extra_context_retained)
        else:b.focus=identifier
        if b.lose==identifier:raise NativeUIError('declared lost original UI reply')
    def activate(self,identifier,reference):self.command(identifier,'activate',reference)
    def replace(self,identifier,value,reference):self.command(identifier,'replace',reference,value)
    def choose(self,identifier,index,reference):self.command(identifier,'select-index',reference,index)


class PrimitiveIO(UnifiedIO):
    def capture(self):
        value=super().capture();b=self.b
        if b.rows and b.rows[0]['type']=='PolyVox' and b.editor:
            for axis in 'xyz':
                row=dict(id='create.field.position.'+axis,enabled=True,focused=b.focus=='create.field.position.'+axis,
                    inputReady=True,text=b.position_fields[axis]);row['token']=uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)).hex
                value['controls'].append(row)
        return value
    def command(self,identifier,action,reference,value=None):
        if identifier.startswith('create.field.position.'):
            from adapters.token_create_ui import same_reference as normal_reference
            normal_reference(reference,self.capture(),identifier);self.b.before_input();self.b.ui.command_sequence+=1
            self.b.inputs.append(dict(controlId=identifier,action=action,value=value))
            if action=='replace':self.b.position_fields[identifier[-1]]=value
            else:self.b.focus=identifier
        else:
            # UnifiedIO's internal same_reference uses its original projection;
            # retain exactly that normal control after this added position view.
            b=self.b
            from adapters.token_create_ui import same_reference as normal_reference
            normal_reference(reference,self.capture(),identifier)
            original=UnifiedIO.capture(self)
            super().command(identifier,action,original,value)
            if identifier=='create.apply' and b.rows and b.rows[0]['type']=='PolyVox' and all(b.position_fields.values()):
                b.rows[0]['position']=[float(b.position_fields[a]) for a in 'xyz']


class CreatePrimitiveJourneyTests(unittest.TestCase):
    make=parent_fixture.CreateJourneyTests.make
    act=parent_fixture.CreateJourneyTests.act
    def setUp(self):
        original_reader=ModelBackend.reader;original_runtime=RuntimeIO.capture;original_resource=ResourceActor.resource_reader;original_home=HomeActor.stage
        def reader(b,kind):
            initialize(b);native=original_reader(b,kind);send=native.send
            if kind=='entities':
                def deliver(command):
                    send(command);packet=json.loads(b.frames[kind]);source=packet['source'];source.update(createEntitySourceVersion=4,
                        avatarRotation=[0,0,0,1],localCreations=dict(createLocalCreationsVersion=1,armedAfterSequence=0,
                        lastSequence=len(b.local_creations),events=deepcopy(b.local_creations)))
                    for row in source['entities']:
                        row.update(createdEpochUs=b.creation_times.setdefault(row['id'],row['lastEditedEpochUs']),lastEditedBy=SESSION,voxels=None)
                        if row['type']=='PolyVox':
                            values=bytes(512) if b.voxel_empty else CANONICAL
                            row['voxels']=dict(createVoxelsVersion=1,ready=not b.voxel_dirty,surfaceStyle=3,volume=[8,8,8],meshReady=True,vertices=64,indices=96,
                                dataBase64=base64.b64encode(b'actual compressed actor bytes').decode(),
                                valuesBase64=base64.b64encode(values if not b.voxel_dirty else b'').decode(),nonzero=sum(v!=0 for v in values) if not b.voxel_dirty else 0)
                    b.frames[kind]=json.dumps(packet,indent=2)+'\n'
                native.send=deliver
            return native
        def runtime(io):
            value=original_runtime(io);extra=ExtraIO(io.b).capture()
            if io.b.polyvox:value['controls']=[]
            for row in extra['controls']:
                row=deepcopy(row);row['token']=str(uuid.UUID(row['token']));value['controls'].append(row)
            value.update(createExtraControlsVersion=1,createExtraUiInventory=extra['createExtraUiInventory']);return value
        def resource(b):
            native=original_resource(b);send=native.send
            def deliver(command):
                rows=b.rows
                if rows and rows[0]['type']=='PolyVox':
                    b.rows=[]
                    try:send(command)
                    finally:b.rows=rows
                    value=json.loads(b.resource_raw);value['source']['bindings'].append(dict(entityId=rows[0]['id'],model=None))
                    value['source']['bindings'].sort(key=lambda r:r['entityId']);b.resource_raw=json.dumps(value)
                else:send(command)
            native.send=deliver;return native
        def home(actor,pose):
            original_home(actor,pose);actor.b.polyvox=False
            for row in actor.b.extra_rows:row.update(pageAlive=False,contextAlive=actor.b.extra_context_retained)
        for boundary in (patch.object(ModelBackend,'reader',reader),patch.object(RuntimeIO,'capture',runtime),
                patch.object(ResourceActor,'resource_reader',resource),patch.object(HomeActor,'stage',home),
                patch.object(AdapterActor,'_create_controls',lambda adapter,_target,intent,**_transport:TokenCreateUI(PrimitiveIO(adapter.b),intent,monotonic=adapter.b.now,sleep=adapter.b.ui.sleep)),
                patch.object(AdapterActor,'_create_extra_controls',lambda adapter,_target,intent,**_transport:TokenCreateExtraUI(ExtraIO(adapter.b),intent,monotonic=adapter.b.now,sleep=adapter.b.ui.sleep),create=True)):
            boundary.start();self.addCleanup(boundary.stop)
        parent_fixture.CreateJourneyTests.setUp(self)
    def create(self):self.act('open');return self.act('voxel-create')
    def test_normal_parent_dialog_create_properties_delete_and_exact_original_volume(self):
        self.create();state=self.root.state();step=state['primitives'][-1]
        self.assertEqual('created',step['outcome']);self.assertEqual('primitive',state['subject']);self.assertEqual([0,1,-2],step['position'])
        self.assertEqual([1,1,1],self.b.rows[0]['dimensions']);self.assertEqual('e2e-'+self.root.run+'-voxel',self.b.rows[0]['name'])
        with self.root.lock.held():self.assertEqual(CANONICAL,voxel_source(self.root.sample()['entities']['source']['entities'][0]['voxels']))
        self.make();self.act('delete-owned');self.assertEqual('deleted',self.root.state()['primitives'][-1]['outcome']);self.assertFalse(self.b.rows)
        from adapters.script_journey.history import unpack
        proof=self.root.state()['primitives'][-1]['creationProof'];frames=unpack(proof['native']);actual=json.loads(frames[0]['raw'])
        self.assertEqual(CANONICAL,voxel_source(actual['source']['entities'][0]['voxels']))
        self.assertEqual(1,sum(i['controlId']=='create-extra.polyvox.add' for i in self.b.inputs))
        self.assertEqual(1,sum(i['controlId']=='create.delete' for i in self.b.inputs))
    def test_lost_add_retains_original_and_cleanup_distinct_delete_without_replay(self):
        self.b.lose='create-extra.polyvox.add'
        with self.assertRaises(NativeUIError):self.create()
        self.b.lose=None;count=len(self.b.inputs);self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{})
        self.root.invoke('cleanup');self.assertFalse(self.b.rows);self.assertIsNone(self.root.store.read())
        self.assertEqual(1,sum(i['controlId']=='create-extra.polyvox.add' for i in self.b.inputs))
    def test_dirty_native_volume_retains_then_readonly_reconciles(self):
        self.b.voxel_dirty=True
        with self.assertRaises(NativeUIError):self.create()
        count=len(self.b.inputs);self.b.voxel_dirty=False;self.make();self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertEqual('created',self.root.state()['primitives'][-1]['outcome'])
    def test_empty_actual_volume_cannot_complete_canonical_requested_create(self):
        self.b.voxel_empty=True
        with self.assertRaises(NativeUIError):self.create()
        self.assertIsNotNone(self.root.state()['pending']);self.assertEqual('creating',self.root.state()['primitives'][-1]['outcome'])
    def test_ambiguous_foreign_local_creation_cannot_be_adopted_or_retired(self):
        self.b.foreign_creation=True
        with self.assertRaises(NativeUIError):self.create()
        count=len(self.b.inputs);self.make();self.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{})
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.store.read())
    def test_actual_polyvox_context_retention_blocks_whole_owner_retirement(self):
        self.b.extra_context_retained=True;self.create();self.act('delete-owned')
        self.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{})
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        count=len(self.b.inputs);self.assertIsNotNone(self.root.store.read());self.assertFalse(self.b.rows)
        self.b.extra_context_retained=False
        for row in self.b.extra_rows:row['contextAlive']=False
        self.make();self.root.invoke('cleanup');self.assertIsNone(self.root.store.read());self.assertEqual(count,len(self.b.inputs))

    def test_lost_final_apply_reconciles_without_repeating_original_input(self):
        original=PrimitiveIO.command;applies=0
        def command(io,identifier,action,reference,value=None):
            nonlocal applies
            if identifier=='create.apply':
                applies+=1
                if applies==2:io.b.lose=identifier
            return original(io,identifier,action,reference,value)
        with patch.object(PrimitiveIO,'command',command),self.assertRaises(NativeUIError):self.create()
        self.b.lose=None;count=len(self.b.inputs);self.make();self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertEqual('created',self.root.state()['primitives'][-1]['outcome'])
    def test_phase_advance_during_extra_acquisition_refuses_add_before_dispatch(self):
        original=ExtraIO.capture;advanced=False
        def capture(io):
            nonlocal advanced
            value=original(io);state=self.root.state()
            if state['primitives'] and 'create' in state['primitives'][-1]['attempted'] and not advanced:
                advanced=True;self.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{})
            return value
        with patch.object(ExtraIO,'capture',capture),self.assertRaises(NativeUIError):self.create()
        self.assertTrue(advanced);self.assertFalse(self.b.rows)
        self.assertFalse(any(i['controlId']=='create-extra.polyvox.add' for i in self.b.inputs))
        self.assertIsNone(self.root.state()['primitives'][-1]['createOriginal']);self.assertIsNotNone(self.root.state()['pending'])
        self.make();self.root.invoke('cleanup');self.assertIsNone(self.root.store.read())
        self.assertEqual(1,sum(i['controlId']=='create-extra.polyvox.cancel' for i in self.b.inputs))


if __name__=='__main__':unittest.main()
