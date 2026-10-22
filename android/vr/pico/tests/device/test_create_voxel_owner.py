"""Real parent/session/token journals with explicitly substituted native actors.

The QML/original JS route has its separate actual Qt harness. This suite joins
production readers, CAS, source/phase fences and input ownership; storage,
controller consumption, native clocks and UI controls here are declared actors.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
import test_create_primitives_owner as primitive
import test_create_journey as parent
from adapters.pico4.create_voxel_ui import TokenCreateVoxelUI,snapshot,same_reference,COUNTS,FIELDS,ENUMS,IDS
from adapters.pico4.create_primitives import CANONICAL
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.normal_ui import NativeUIError
from openxr_input.adapter_session import PicoOpenXrAdapterSession

ORIGINAL=dict(createAppMode='object',voxelEditMode='single',voxelSphereSize=.3,voxelEditDynamics='click',
    voxelRemove=False,voxelPointerMode='laser',voxelBrushLength=.5)
KEYS=dict(mode='createAppMode',shape='voxelEditMode',dynamics='voxelEditDynamics',pointer='voxelPointerMode',
    diameter='voxelSphereSize',reach='voxelBrushLength')


def initialize(b):
    if hasattr(b,'tools'):return
    b.tools=deepcopy(ORIGINAL);b.tools_draft=deepcopy(ORIGINAL);b.voxel_values=CANONICAL;b.stroke_count=0
    b.poly_births={};b.poly_ids=set();b.retain_poly_mesh=False;b.freeze_at=None
    b.epoch=lambda:20000+round((b.now() if b.freeze_at is None else b.freeze_at)*1000)
    b.ignore_stroke=False;b.lose_restore=False;b.delay_publication=0;b.streams=[]


class VoxelIO:
    def __init__(self,b):self.b=b
    def capture(self):
        b=self.b;initialize(b);rows=[]
        for identifier in sorted(IDS if b.editor and b.opened and b.tab==3 else []):
            row=dict(id=identifier,enabled=True,focused=b.focus==identifier,inputReady=True)
            suffix=identifier.split('.')[-1];key=KEYS.get(suffix)
            if identifier in COUNTS:
                row.update(count=COUNTS[identifier],currentIndex=ENUMS[key].index(b.tools_draft[key]))
                if suffix=='mode':row['settings']=deepcopy(b.tools)
            elif identifier in FIELDS:row['text']=str(b.tools_draft[key])
            elif suffix=='remove':row['checked']=b.tools_draft['voxelRemove']
            row['token']=uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)).hex;rows.append(row)
        return snapshot(dict(createVoxelControlsVersion=1,open=b.opened,ready=b.opened,scope=b.scope(),controls=rows))
    def command(self,identifier,action,reference,value=None):
        b=self.b;same_reference(reference,self.capture(),identifier);b.before_input();b.ui.command_sequence+=1
        b.inputs.append(dict(controlId=identifier,action=action,value=value));suffix=identifier.split('.')[-1];key=KEYS.get(suffix)
        if action=='select-index':
            b.tools_draft[key]=ENUMS[key][value]
            if key=='createAppMode':b.tools[key]=b.tools_draft[key]
        elif action=='replace':b.tools_draft[key]=float(value)
        elif suffix=='remove':b.tools_draft['voxelRemove']=not b.tools_draft['voxelRemove']
        elif suffix=='apply':b.tools=deepcopy(b.tools_draft)
        else:b.focus=identifier
        if b.lose_restore and suffix=='mode' and action=='select-index' and value==0:raise NativeUIError('declared lost restore reply')
    def activate(self,identifier,reference):self.command(identifier,'activate',reference)
    def choose(self,identifier,value,reference):self.command(identifier,'select-index',reference,value)
    def replace(self,identifier,value,reference):self.command(identifier,'replace',reference,value)


class ControllerActor:
    """Transport-only seam; actual session owns envelope, sequence and lock."""
    def __init__(self,b):self.b=b;self.sequence=0
    def stage(self,envelope,profile,*,before_publish=None):
        b=self.b;initialize(b);b.ui.sleep(b.delay_publication)
        if before_publish:before_publish(deepcopy(envelope))
        command=envelope['commands'][0];operation=command['operation'];self.sequence=envelope['sequence'];b.streams.append(deepcopy(envelope))
        if operation=='tablet.close':b.opened=False
        elif operation=='tablet.open':b.opened=True
        elif operation=='input.primary':
            b.stroke_count+=1
            if not b.ignore_stroke:
                b.rows[0]['lastEditedEpochUs']=b.epoch()*1000
                b.voxel_values=bytes(v if z<3 else 0 for z in range(8) for y in range(8) for x in range(8) for v in [CANONICAL[z*64+y*8+x]])
        return dict(sequence=envelope['sequence'])
    def read_status(self,**kwargs):
        active=kwargs.get('expected_sequence') is not None
        return dict(state='active' if active else 'neutral',enabled=True,acceptedSequence=self.sequence,
            acceptedNonce='[redacted]',activeCommandId='declared-controller-actor' if active else '',updatedEpochMs=self.b.epoch(),
            booleanAppliedSequence=self.sequence,leftSecondaryApplied=True)


class CreateVoxelJourneyTests(unittest.TestCase):
    make=parent.CreateJourneyTests.make
    act=parent.CreateJourneyTests.act
    def setUp(self):primitive.CreatePrimitiveJourneyTests.setUp(self)
    def _before_prepare(self):
        original_runtime=parent.RuntimeIO.capture;original_reader=primitive.ModelBackend.reader;original_work=primitive.ModelBackend.work_reader
        original_native=parent.AdapterActor._native_feature_observer;original_lifecycle=parent.AdapterActor._lifecycle_ui_source
        def runtime(io):
            value=original_runtime(io);tools=VoxelIO(io.b).capture();value['controls'] += [deepcopy(r)|dict(token=str(uuid.UUID(r['token']))) for r in tools['controls']]
            value['createVoxelControlsVersion']=1;return value
        def reader(b,kind):
            native=original_reader(b,kind);send=native.send
            if kind=='entities':
                def deliver(command):
                    send(command);packet=json.loads(b.frames[kind]);initialize(b)
                    for row in packet['source']['entities']:
                        if row['type']=='PolyVox':row['voxels'].update(valuesBase64=base64.b64encode(b.voxel_values).decode(),
                            nonzero=sum(v!=0 for v in b.voxel_values),dataBase64=base64.b64encode(b'actor-volume-'+hashlib.sha256(b.voxel_values).digest()).decode())
                    source=packet['source'];source['createEntitySourceVersion']=5
                    present=[r['id'] for r in source['entities'] if r['type']=='PolyVox'];b.poly_ids.update(present)
                    ids=['a'*32]+(['b'*32] if b.stroke_count else []);meshes=[]
                    for identifier in ids if b.poly_ids else []:
                        birth=b.poly_births.setdefault(identifier,b.epoch());alive=identifier==ids[-1] and (bool(present) or b.retain_poly_mesh)
                        meshes.append(dict(id=identifier,firstObservedEpochMs=birth,alive=alive))
                    renderer=[dict(id='c'*32,firstObservedEpochMs=b.poly_births.setdefault('c'*32,b.epoch()),alive=bool(present))] if b.poly_ids else []
                    source['polyvoxResources']=dict(createPolyvoxResourcesVersion=1,instance='7'*32,sourceSequence=packet['sequence'],
                        bindings=[dict(entityId=identifier,entityMesh=ids[-1],renderer='c'*32,rendererMesh=ids[-1],textures=[None]*3,
                            renderObservations=1+b.stroke_count) for identifier in sorted(b.poly_ids)],meshes=meshes,renderers=renderer,textures=[])
                    b.frames[kind]=json.dumps(packet,indent=2)+'\n'
                native.send=deliver
            return native
        def work(b):
            native=original_work(b);send=native.send
            def deliver(request):
                send(request);packet=json.loads(b.work_raw);initialize(b)
                if b.stroke_count:packet['source']['work']['activity'].append(dict(scriptId=119,
                    signalCallbacks=0,timerCallbacks=0,signalInvocations=0,timerInvocations=b.stroke_count,timerRegistrations=b.stroke_count))
                packet['source']['work']['activityEntries']=len(packet['source']['work']['activity']);b.work_raw=json.dumps(packet,indent=2)+'\n'
            native.send=deliver;return native
        def native(adapter,target):
            result=original_native(adapter,target);result.clock_ms=adapter.b.epoch;return result
        def lifecycle(adapter,target):
            result=original_lifecycle(adapter,target);send=result.send
            def deliver(request):
                send(request);packet=json.loads(adapter.b.life_raw)
                # Match the original source contract while the tablet is hidden:
                # its live retained editor is not a current visible editor.
                if not adapter.b.opened:packet['source']['current']=''
                adapter.b.life_raw=json.dumps(packet,indent=2)+'\n'
            result.send=deliver;return result
        original_runtime=parent.RuntimeIO.capture;original_reader=primitive.ModelBackend.reader;original_work=primitive.ModelBackend.work_reader
        original_extra=primitive.ExtraIO.capture
        def extra(io):
            editor=io.b.editor
            if not io.b.opened:io.b.editor=False
            try:return original_extra(io)
            finally:io.b.editor=editor
        for boundary in (patch.object(parent.RuntimeIO,'capture',runtime),patch.object(primitive.ModelBackend,'reader',reader),
                patch.object(primitive.ModelBackend,'work_reader',work),patch.object(primitive.ExtraIO,'capture',extra),patch.object(parent.AdapterActor,'_native_feature_observer',native),patch.object(parent.AdapterActor,'_lifecycle_ui_source',lifecycle),
                patch.object(parent.AdapterActor,'_create_voxel_controls',lambda adapter,_target,intent,**_transport:TokenCreateVoxelUI(VoxelIO(adapter.b),intent,monotonic=adapter.b.now,sleep=adapter.b.ui.sleep),create=True)):
            boundary.start();self.addCleanup(boundary.stop)
        initialize(self.b)
        original_input=self.b.before_input
        def before_input():
            state=self.b.root.state()
            if state['cleanupStarted']:
                self.assertEqual('cleanup',state['phase']['activations'][-1]['stimulus']['verb'])
                self.assertEqual(state['lastInput']['original']['scope'],self.b.scope())
            else:original_input()
        self.b.before_input=self.b.ui.before_input=before_input
        # Compilations are an explicit source actor. Use exact current original
        # code-unit hashes, with distinct actual actor script IDs in both readers.
        root=Path(__file__).resolve().parents[5]
        for script,file in ((118,'editModes.js'),(119,'editVoxels.js')):
            relative='system/create/editModes/'+file;code=(root/'scripts'/relative).read_text().encode('utf-16le')
            self.b.callback['source']['managers'][0]['compiled']['compilations'].append(dict(scriptId=script,
                resourceName='file:///original/scripts/'+relative,encoding='utf-16le-code-units',codeUnits=len(code)//2,
                sha256=hashlib.sha256(code).hexdigest(),compiledEpochMs=12000))
        self.controller=ControllerActor(self.b);self.session=PicoOpenXrAdapterSession(self.controller,self.adapter.target,self.path)
        self.session._save(dict(schemaVersion=1,processIdentity=self.b.binding['processIdentity'],sessionNonce='a'*64,nextSequence=1))
        boundary=patch.object(parent.AdapterActor,'pico_input_session',lambda adapter,_target:self.session,create=True);boundary.start();self.addCleanup(boundary.stop)
        home=parent.HomeActor(self.b)
        boundary=patch('adapters.pico4.create_voxel_edit.bind_home',side_effect=lambda *_a:PicoTabletHome(home,home.stage));boundary.start();self.addCleanup(boundary.stop)
    def create(self):self.act('open');self.act('voxel-create')
    def test_normal_edit_original_native_volume_timer_settings_and_cold_delete(self):
        self.create();self.act('voxel-edit',dict(mode='remove',brushMeters=.5));self.assertEqual(ORIGINAL,self.b.tools)
        self.assertEqual(1,self.b.stroke_count);self.assertEqual(16,sum(v!=0 for v in self.b.voxel_values))
        self.assertEqual('edited',self.root.state()['voxelEdit']['outcome']);self.make();self.act('delete-owned');self.assertFalse(self.b.rows)
        self.act('close');self.assertFalse(self.b.editor);self.make()
        self.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{});self.root.invoke('cleanup');self.assertIsNone(self.root.store.read())
        self.assertEqual(1,self.b.stroke_count)
    def test_lost_restore_readonly_reconciles_without_controller_or_ui_replay(self):
        self.create();self.b.lose_restore=True
        with self.assertRaises(NativeUIError):self.act('voxel-edit',dict(mode='remove',brushMeters=.5))
        self.b.lose_restore=False;count=len(self.b.inputs);self.make();self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(1,self.b.stroke_count);self.assertEqual(ORIGINAL,self.b.tools)
    def test_request_and_ack_without_actual_volume_effect_remain_owned(self):
        self.create();self.b.ignore_stroke=True
        with self.assertRaises(NativeUIError):self.act('voxel-edit',dict(mode='remove',brushMeters=.5))
        self.assertEqual(CANONICAL,self.b.voxel_values);count=len(self.b.inputs);self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.state()['pending'])
    def test_deleted_entity_cannot_retire_the_retained_original_renderer_mesh(self):
        self.create();self.act('voxel-edit',dict(mode='remove',brushMeters=.5));self.b.retain_poly_mesh=True
        with self.assertRaises(NativeUIError):self.act('delete-owned')
        self.assertFalse(self.b.rows);count=len(self.b.inputs);self.b.retain_poly_mesh=False;self.make();self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertEqual('deleted',self.root.state()['primitives'][-1]['outcome'])

    def test_slow_final_sdk_admission_with_frozen_native_clock_publishes_no_stream(self):
        self.create();self.b.delay_publication=2;self.b.freeze_at=self.b.now()
        with self.assertRaises(NativeUIError):self.act('voxel-edit',dict(mode='remove',brushMeters=.5))
        self.assertEqual([],self.b.streams);self.assertEqual(1,self.session._load()['nextSequence'])
        self.assertIsNotNone(self.root.state()['voxelEdit']['streams'][0]['envelope']);count=len(self.b.inputs)
        self.make();self.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{})
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(count,len(self.b.inputs));self.assertTrue(self.b.rows);self.assertIsNotNone(self.root.store.read())


PARTITIONS={
    'flow':[
        'test_normal_edit_original_native_volume_timer_settings_and_cold_delete',
        'test_lost_restore_readonly_reconciles_without_controller_or_ui_replay'],
    'guards':[
        'test_request_and_ack_without_actual_volume_effect_remain_owned',
        'test_slow_final_sdk_admission_with_frozen_native_clock_publishes_no_stream',
        'test_deleted_entity_cannot_retire_the_retained_original_renderer_mesh']}


def group(loader,name):
    cases=[case for rows in PARTITIONS.values() for case in rows]
    assert sorted(cases)==sorted(set(cases))==loader.getTestCaseNames(CreateVoxelJourneyTests)
    return unittest.TestSuite(CreateVoxelJourneyTests(case) for case in PARTITIONS[name])


if __name__=='__main__':unittest.main()
