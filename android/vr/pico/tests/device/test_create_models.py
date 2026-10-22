"""Durable NEW Model composition at declared substituted source/UI boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[5];sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.native_script_work import NativeScriptWork
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_models import OwnedCreateModels,OriginalReader,WorkJournal,source_pin
from adapters.token_create_ui import TokenCreateUI,same_reference
from self_tests.test_native_script_files import BINDING
from test_create_picker_owner import OriginalBackend,RUN,TICKET,SECOND,URL,SID,MODEL


def activity(script,registrations=0,calls=0,signals=0):
    return dict(scriptId=script,signalCallbacks=0,timerCallbacks=0,signalInvocations=signals,
        timerInvocations=calls,timerRegistrations=registrations)


class ModelBackend(OriginalBackend):
    def __init__(self,path):
        super().__init__(path);self.tab=0;self.resource='';self.name='';self.dimensions=dict(x='',y='',z='')
        self.sequence['work']=0;self.registrations=0;self.invocations=0;self.submitted=None;self.loaded=False
        self.block_work=False;self.bad_load=False;self.work_raw='';self.unknown=False;self.extra_workers=[];self.revision=1;self.freeze_ui=False
        self.foreign_timer=dict(handle=99,active=True,singleShot=False,intervalMs=1000,remainingMs=950,functionScriptId=99)
        compiled=self.callback['source']['managers'][0]['compiled']['compilations']
        compiled.append(dict(scriptId=99,resourceName='file:///original/scripts/foreign.js',encoding='utf-16le-code-units',
            codeUnits=1,sha256=hashlib.sha256(b'x\0').hexdigest(),compiledEpochMs=12000))
    def settle(self):
        if self.submitted is not None:
            age=self.now()-self.submitted
            if age>=.6 and not self.loaded:
                self.loaded=True;self.invocations+=1;self.registrations+=1
                if self.rows and not self.bad_load:
                    self.rows[0].update(visible=True,visuallyReady=True,dimensions=[1,.5,.1],naturalDimensions=[2,1,.2],
                        renderInfo=dict(vertices=3,textures=1,textureBytes=768,drawCalls=1))
                    self.rows[0]['lastEditedEpochUs']=self.epoch()*1000
            if age>=1.2 and self.invocations<self.registrations and not self.block_work:self.invocations=self.registrations
    def reader(self,kind):
        native=super().reader(kind);send=native.send
        def original(command):self.settle();send(command)
        native.send=original;return native
    def work_reader(self):
        def send(request):
            self.settle();self.sequence['work']+=1;epoch=self.epoch();manager=self.callback['source']['managers'][0]
            member=deepcopy(manager['membership']);compiled=deepcopy(manager['compiled'])
            rows=[activity(17,self.registrations,self.invocations,signals=self.sequence['work']),activity(99,1)]
            timers=[deepcopy(self.foreign_timer)]
            if self.registrations>self.invocations:
                timers.insert(0,dict(handle=1,active=not self.block_work,singleShot=True,intervalMs=200,
                    remainingMs=-1 if self.block_work else 100,functionScriptId=17))
            if self.unknown:
                rows.insert(0,activity(0,1));timers.insert(0,dict(handle=2,active=True,singleShot=True,
                    intervalMs=100,remainingMs=50,functionScriptId=0))
                timers.sort(key=lambda r:r['handle'])
            source=dict(complete=True,revision=self.revision,manager=member,
                code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=1,sha256=hashlib.sha256(b'x\0').hexdigest(),submittedEpochMs=11000),
                compiled=compiled,workers=[dict(membership=member,running=True,stopping=False,finished=False,done=False)]+deepcopy(self.extra_workers),
                work=dict(scriptWorkVersion=2,requestId=request['commandId'],sequence=self.sequence['work'],
                    requestedEpochMs=epoch,capturedEpochMs=epoch,signalCallbacks=0,timerCallbacks=0,evaluating=False,
                    timers=timers,activity=rows,timerEntries=len(timers),activityEntries=len(rows)))
            packet=dict(schemaVersion=1,requestId=request['commandId'],instance='9'*32,sequence=self.sequence['work'],processId=123,
                requestedEpochMs=epoch,capturedEpochMs=epoch,source=source)
            self.work_raw=json.dumps(packet,indent=2)+'\n'
        return NativeScriptWork(send,lambda:self.work_raw,self.epoch,lambda:True,123,monotonic=self.now,sleep=self.ui.sleep)
    def make(self):
        self.binding=deepcopy(BINDING);self.binding.update(processIdentity='123:original-process',sessionId=SID,generation=1)
        entities=OriginalReader(self.reader('entities'),self.store('entities'),self.binding)
        callbacks=OriginalReader(self.reader('callbacks'),self.store('callbacks'),self.binding)
        work=WorkJournal(self.work_reader(),self.store('work'),self.binding)
        self.owner=OwnedCreateModels(self.store('owner'),self.binding,lambda intent:TokenCreateUI(ModelIO(self),intent,
            monotonic=self.now,sleep=self.ui.sleep),entities,callbacks,work,monotonic=self.now,sleep=self.ui.sleep)
        return self.owner


class ModelIO:
    def __init__(self,b):self.b=b
    def capture(self):
        b=self.b;b.settle();rows=[]
        def add(identifier,**kwargs):
            row=dict(id=identifier,enabled=True,focused=b.focus==identifier,inputReady=identifier!='create.page',**kwargs)
            row['token']=uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)).hex;rows.append(row)
        add('create.page',profile='native-create-v1',tab=b.tab,selectedIds=list(b.selected),statusError=False,statusText=b.status,componentSourceSha256='a'*64)
        for index in range(5):add('create.tab.'+str(index))
        add('create.host',currentIndex=b.index,count=2);add('create.resource',text=b.resource);add('create.new-model')
        for row in b.rows:add('create.entity.'+row['id'],entityId=row['id'])
        add('create.name',text=b.name);add('create.refresh');add('create.apply');add('create.delete')
        for axis in 'xyz':add('create.field.dimensions.'+axis,text=b.dimensions[axis])
        actual_scope=b.scope()
        if b.freeze_ui:actual_scope['elapsedMs']=0
        return dict(createControlsVersion=1,open=True,ready=True,scope=actual_scope,controls=rows)
    def command(self,identifier,action,reference,value=None):
        b=self.b;same_reference(reference,self.capture(),identifier);b.before_input();b.ui.command_sequence+=1
        b.inputs.append(dict(controlId=identifier,action=action,value=value))
        if identifier.startswith('create.tab.'):b.tab=int(identifier[-1])
        elif identifier=='create.host' and action=='select-index':b.index=value
        elif identifier=='create.resource' and action=='replace':b.resource=value
        elif identifier=='create.new-model':
            entity=uuid.uuid5(uuid.NAMESPACE_URL,b.resource).hex;entity=str(uuid.UUID(entity))
            b.rows=[dict(id=entity,name='',type='Model',hostType='domain',modelUrl=b.resource,textures='',position=[0,1,-2],rotation=[0,0,0,1],
                dimensions=[.1,.1,.1],parentId=None,visible=False,locked=False,lastEditedEpochUs=b.epoch()*1000,visuallyReady=False,
                naturalDimensions=[0,0,0],textureNames={'checker.png':b.resource.rsplit('/',1)[0]+'/textures/checker.png'},
                renderInfo=dict(vertices=0,textures=0,textureBytes=0,drawCalls=0))]
            b.selected=[entity];b.tab=2;b.submitted=b.now();b.loaded=False;b.registrations+=1
        elif identifier=='create.name' and action=='replace':b.name=value
        elif identifier.startswith('create.field.dimensions.') and action=='replace':b.dimensions[identifier[-1]]=value
        elif identifier=='create.apply':
            b.rows[0]['name']=b.name
            if all(b.dimensions.values()):b.rows[0]['dimensions']=[float(b.dimensions[a]) for a in 'xyz']
            b.rows[0]['lastEditedEpochUs']=b.epoch()*1000
        elif identifier.startswith('create.entity.'):b.selected=[identifier[len('create.entity.'):]]
        elif identifier=='create.delete':
            b.absent=sorted(set(b.absent)|{r['id'] for r in b.rows});b.rows=[];b.selected=[]
        else:b.focus=identifier
        if b.lose==identifier:raise NativeUIError('synthetic lost normal input result')
    def activate(self,identifier,*,reference):self.command(identifier,'activate',reference)
    def select_index(self,identifier,index,*,reference):self.command(identifier,'select-index',reference,index)
    def replace(self,identifier,text,*,reference):self.command(identifier,'replace',reference,text)
    def scroll(self,*args,**kwargs):raise AssertionError('fixture has no scroll')


class CreateModelOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.b=ModelBackend(self.path);self.flow=self.b.make()
    def create(self,ticket=TICKET,resource='gltf-bundle/main.gltf'):return self.flow.create(RUN,ticket,URL,resource)
    def test_gltf_then_obj_actual_sources_timer_retirement_normal_properties_and_weak_death(self):
        self.create();value=self.flow.state();first=value['steps'][0]['entityId']
        self.assertTrue(value['steps'][0]['configureAttempted']);self.assertEqual('created',value['steps'][0]['outcome'])
        self.assertEqual([1,1,1],self.b.rows[0]['dimensions']);self.assertEqual('e2e-'+RUN+'-model',self.b.rows[0]['name'])
        self.assertEqual(self.b.registrations,self.b.invocations);self.assertEqual(99,self.b.foreign_timer['handle'])
        self.flow=self.b.make();self.flow.delete();self.create(SECOND,'obj-bundle/main.obj')
        self.assertNotEqual(first,self.flow.state()['steps'][-1]['entityId']);self.flow.delete();self.flow.release()
        self.assertFalse(list(self.path.glob('*.json')))
        self.assertEqual(2,sum(r['controlId']=='create.new-model' for r in self.b.inputs))
        self.assertEqual(2,sum(r['controlId']=='create.delete' for r in self.b.inputs))
    def test_lost_create_is_never_replayed_and_distinct_normal_delete_retires_original_work(self):
        self.b.lose='create.new-model'
        with self.assertRaises(NativeUIError):self.create()
        count=len(self.b.inputs);self.b.lose=None;self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.assertTrue(self.flow.state()['steps'][-1]['submitted'])
        self.flow.delete();self.flow.release();self.assertEqual(1,sum(r['controlId']=='create.new-model' for r in self.b.inputs))
    def test_lost_final_apply_reconciles_read_only_but_partial_edit_is_retained(self):
        original=ModelIO.command;seen=0
        def lose_last(io,identifier,action,reference,value=None):
            nonlocal seen
            if identifier=='create.apply':
                seen+=1
                if seen==2:io.b.lose=identifier
            return original(io,identifier,action,reference,value)
        from unittest.mock import patch
        with patch.object(ModelIO,'command',lose_last),self.assertRaises(NativeUIError):self.create()
        self.b.lose=None;count=len(self.b.inputs);self.flow=self.b.make();self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.flow.delete();self.flow.release()
    def test_lost_name_input_retains_incomplete_effect_and_does_not_resend(self):
        self.b.lose='create.name'
        with self.assertRaises(NativeUIError):self.create()
        self.b.lose=None;count=len(self.b.inputs);self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.flow.delete();self.flow.release()
    def test_lost_delete_or_retained_renderer_reconciles_without_resending(self):
        self.create();self.b.retain_entity=True;self.b.lose='create.delete'
        with self.assertRaises(NativeUIError):self.flow.delete()
        self.b.lose=None;count=len(self.b.inputs);self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.store.read())
        self.b.retain_entity=False;self.flow=self.b.make();self.flow.reconcile();self.assertEqual(count,len(self.b.inputs));self.flow.release()
    def test_bad_load_allows_separate_delete_but_inactive_timer_keeps_ownership(self):
        self.b.bad_load=True;self.b.block_work=True
        with self.assertRaises(NativeUIError):self.create()
        self.assertIsNotNone(self.flow.store.read());self.assertTrue(self.flow.state()['steps'][-1]['submitted'])
        with self.assertRaises(NativeUIError):self.flow.delete()
        count=len(self.b.inputs);self.b.block_work=False;self.flow=self.b.make();self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.flow.release()
    def test_unknown_timer_prevents_input_and_orphan_observation_retirement(self):
        self.b.unknown=True
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual([],self.b.inputs);self.assertIsNone(self.flow.store.read());self.assertIsNotNone(self.flow.work.store.read())
        with self.assertRaises(NativeUIError):self.flow.release_observations()
        self.assertIsNotNone(self.flow.work.store.read())
    def test_dirty_scene_domain_generation_replacement_and_tampered_raw_refuse(self):
        self.create();self.b.domain_birth='4'*32;self.b.domain_revision+=2;count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.flow.delete()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.store.read())
        journal=self.flow.work.store.read();journal['frames']['payload']='foreign'
        self.flow.work.store.write(journal,self.flow.work.previous)
        with self.assertRaises(NativeUIError):self.b.make()
    def test_original_ui_and_native_clocks_must_both_advance_during_final_quiet(self):
        self.create();self.b.freeze_ui=True;count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.flow.quiet('create',created=True)
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.store.read())
        self.b.freeze_ui=False;self.b.freeze_epoch=True
        with self.assertRaises(NativeUIError):self.flow.quiet('create',created=True)
        self.b.freeze_epoch=False;self.flow.delete();self.flow.release()
    def test_acquisition_only_originals_can_retire_after_preexisting_original_timer_dies(self):
        self.b.submitted=0.;self.b.registrations=1;self.b.block_work=True
        with self.assertRaises(NativeUIError):self.create()
        self.assertIsNone(self.flow.store.read());self.assertEqual([],self.b.inputs)
        self.b.block_work=False;self.flow=self.b.make();self.flow.release_observations()
        self.assertFalse(list(self.path.glob('*.json')));self.assertEqual([],self.b.inputs)
    def test_work_original_membership_transitions_survive_private_history_reconstruction(self):
        self.create();member=dict(instance='6'*32,assigned=True,url='file:///original/foreign.js',loadGeneration=1,assignedEpochMs=self.b.epoch())
        self.b.extra_workers=[dict(membership=member,running=True,stopping=False,finished=False,done=False)];self.b.revision+=1
        self.flow.capture();self.b.extra_workers=[];self.b.revision+=1;self.flow.capture()
        self.flow=self.b.make();self.assertIn(member['instance'],self.flow.work.native.retired)
        self.b.extra_workers=[dict(membership=member,running=True,stopping=False,finished=False,done=False)];self.b.revision+=1
        with self.assertRaises(NativeUIError):self.flow.capture()
        self.assertIsNotNone(self.flow.store.read())
    def test_partial_host_retirement_keeps_orphan_sources_and_recovers_without_input(self):
        self.create();self.flow.delete();original=self.flow.callbacks.retire
        def fail():raise OSError('synthetic durable host retirement interruption')
        self.flow.callbacks.retire=fail
        with self.assertRaises(OSError):self.flow.release()
        self.assertIsNone(self.flow.store.read());self.assertIsNotNone(self.flow.work.store.read());count=len(self.b.inputs)
        self.flow=self.b.make();self.flow.release_observations()
        self.assertFalse(list(self.path.glob('*.json')));self.assertEqual(count,len(self.b.inputs))
    def test_bound_factory_inventory_retains_orphans_and_refuses_other_model_run(self):
        import test_normal_scripts as sources
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        instance,native=fixture.instance,fixture.native
        with patch.dict(os.environ,{'OVERTE_PICO_NORMAL_CREATE':'1'}):
            flow=instance._create_models(native.target,RUN);self.assertFalse(flow.owned())
            self.assertFalse(instance._create_models_owned(native.target))
            flow.store('work').write({'original':'retained'},None)
            self.assertTrue(flow.owned());self.assertTrue(instance._create_models_owned(native.target))
            other=instance._create_models(native.target,SECOND)
            with other.lock.held(),self.assertRaises(NativeUIError):other.flow()
            with self.assertRaises(NativeUIError):flow.flow() # An unheld source lock cannot acquire originals.
            self.assertIsNotNone(flow.store('work').read());self.assertEqual([],native.inputs)
            self.assertFalse(any(c.startswith('feature.create.') for c in instance.capabilities(native.target)))
    def test_candidate_binding_and_failed_intent_write_leave_no_unrecorded_input(self):
        self.create();before=self.flow.store.read();changed=deepcopy(before);changed['binding']['artifactSha256']='f'*64
        self.flow.store.write(changed,before)
        with self.assertRaises(NativeUIError):self.b.make()
        self.flow.store.write(before,changed);changed=deepcopy(before);changed['lastInput']['action']='invoke-handler'
        self.flow.store.write(changed,before)
        with self.assertRaises(NativeUIError):self.b.make()
        self.flow.store.write(before,changed);self.flow=self.b.make();count=len(self.b.inputs)
        def unavailable(*args):raise OSError('synthetic private intent storage failure')
        with patch.object(self.flow.store,'write',side_effect=unavailable),self.assertRaises(OSError):self.flow.delete()
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(before,self.flow.store.read())
    def test_normal_model_requests_are_closed_before_any_input(self):
        for resource in ('../foreign.gltf','gltf-bundle/main.gltf?expected=true','other.obj'):
            with self.subTest(resource=resource),self.assertRaises((NativeUIError,ValueError)):self.create(resource=resource)
        self.assertEqual([],self.b.inputs)
    def test_source_selector_requires_actual_compilation_identity_and_original_code_units(self):
        from adapters.pico4.create_models import selected
        packet=self.b.reader('callbacks').read();pin=source_pin();self.assertEqual(17,selected(packet,pin)[1]['scriptId'])
        pin['codeUnits']+=1
        with self.assertRaises(NativeUIError):selected(packet,pin)
        packet['source']['managers'][0]['compiled']['compilations'][0]['resourceName']='https://foreign.test/system/create/edit.js'
        with self.assertRaises(NativeUIError):selected(packet,source_pin())


from test_create_model_script import CreateModelScriptTests

if __name__=='__main__':unittest.main()
