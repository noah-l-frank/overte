"""Real parent/factories with explicit native/domain/render/setting actors.

No primary state or requested phase is a source effect. This test uses the real
fixture input journal, private CAS files, Script source lock, token owners,
original packet readers and file bytes; native/UI/domain allocation is an actor.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import patch

from test_create_model_resource_join import ResourceActor
from test_create_models import ModelIO
from test_create_picker_owner import NormalIO,FileIO,FakeSetting,NativeBoundary,RUN,URL,SID
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_journey import PicoCreateJourney
from adapters.pico4.create_models import PicoCreateModels
from adapters.pico4.create_picker_owner import PicoCreatePicker
from adapters.pico4.create_file_ui import CreateFileUI
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_create_ui import TokenCreateUI
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from feature_journeys.scenarios import SCENARIOS,VERSION
from self_tests.test_pico_tablet_home import original as home_original


class PhaseClient(Client):
    def __init__(self,journal):super().__init__(URL.split('/runs/')[0],'private-host-reader-'+'a'*32);self.journal=journal
    def request(self,path,value=None,method=None,**kwargs):
        assert path=='/runs/'+RUN+'/phase' and value is None and method is None and set(kwargs)=={'phase_nonce'}
        return self.journal.phase(RUN,kwargs['phase_nonce'])


class UnifiedIO(ModelIO):
    def capture(self):
        b=self.b
        if not b.opened:return dict(createControlsVersion=1,open=False,ready=False,scope=b.scope(),controls=[])
        if not b.editor:
            return dict(createControlsVersion=1,open=True,ready=True,scope=b.scope(),controls=[dict(id='create.entry',
                token='1'*32,enabled=True,focused=False,inputReady=True)])
        actual=super().capture();other=NormalIO(b).capture()
        rows={r['id']:r for r in other['controls']};rows.update({r['id']:r for r in actual['controls']})
        actual['controls']=list(rows.values());return actual
    def command(self,identifier,action,reference,value=None):
        b=self.b
        from adapters.token_create_ui import same_reference
        same_reference(reference,self.capture(),identifier)
        if identifier=='create.entry':
            b.before_input();b.ui.command_sequence+=1;b.inputs.append(dict(controlId=identifier,action=action));b.editor=True
        elif identifier in ('create.import-browse','create.export','create.import-host'):
            NormalIO(b).command(identifier,action,reference,value)
        else:super().command(identifier,action,reference,value)


class RuntimeIO:
    def __init__(self,b):self.b=b
    def capture(self):
        b=self.b;actual=UnifiedIO(b).capture();rows=deepcopy(actual['controls'])
        for row in rows:row['token']=str(uuid.UUID(row['token']))
        return dict(schemaVersion=1,bridgeId=SID,generation=SID,processId=123,elapsedMs=round(b.now()*1000),
            updatedEpochMs=b.epoch(),lastCommandSequence=b.ui.command_sequence,open=b.opened,ready=b.opened,
            controls=rows,featureControlsVersion=1,createControlsVersion=1)
    def tablet(self,value):
        b=self.b;root=b.root.state();assert root['lastInput']['kind']==('tablet-open' if value else 'tablet-close')
        b.inputs.append(dict(controlId='tablet.open' if value else 'tablet.close'));b.ui.command_sequence+=1;b.opened=value
    def release(self):pass


class HomeActor:
    def __init__(self,b):self.b=b;self.pid=123;self.monotonic=b.now;self.sleep=b.ui.sleep;self.clock_ms=b.epoch;self.guard=lambda:True;self.sequence=0
    def capture(self):
        self.sequence+=1;return home_original()|dict(commandId=uuid.uuid4().hex,processId=123,capturedEpochMs=self.b.epoch(),
            elapsedMs=round(self.b.now()*1000),sourceSequence=self.sequence,tabletShown=self.b.opened,onHomeScreen=not self.b.editor)
    def stage(self,_pose):
        assert self.b.root.state()['lastInput']['kind']=='home';self.b.editor=False;self.b.ui.command_sequence+=1
        self.b.inputs.append(dict(controlId='tablet.home-ray'))


class AdapterActor:
    def __init__(self,b,path):
        self.b=b;self.pico_configuration=('original-existing-candidate',path);self.file_raw='';self.target='host-create-candidate'
        self.adb=SimpleNamespace(read_debug_app_file=lambda *_a,**_k:self.file_raw)
    def _script_runtime(self,_target):return TokenScriptUI(RuntimeIO(self.b),monotonic=self.b.now,sleep=self.b.ui.sleep),None,self.b.binding
    def _create_management(self,_target):return SimpleNamespace(owned=lambda:False)
    def _create_models_owned(self,target):return PicoCreateModels.owned_target(self,target)
    def _create_picker_owned(self,target):return PicoCreatePicker.owned_target(self,target)
    def _script_paths(self,_target):return self.pico_configuration[1]/'unused-regular-script.json',None
    def _create_entity_observer(self,_target,_run):return self.b.reader('entities')
    def _create_callback_observer(self,_target):return self.b.reader('callbacks')
    def _create_dialog_observer(self,_target):return self.b.reader('dialogs')
    def _create_model_resources_observer(self,_target,_run):return self.b.resource_reader()
    def _script_work(self,_target):return self.b.work_reader()
    def _create_browse_setting_native(self,_target):return self.b
    def _create_controls(self,_target,intent):return TokenCreateUI(UnifiedIO(self.b),intent,monotonic=self.b.now,sleep=self.b.ui.sleep)
    def _create_file_controls(self,_target,intent,directory,run,ticket,role,before):
        return CreateFileUI(FileIO(self.b),intent,directory,run,ticket,role,before,monotonic=self.b.now,sleep=self.b.ui.sleep)
    def _lifecycle_ui_source(self,_target):
        from adapters.pico4.lifecycle_source import PicoLifecycleSource
        b=self.b
        def send(request):
            b.life_sequence+=1
            if b.editor and (not b.life_rows or not b.life_rows[-1]['fieldAlive']):
                ids=[uuid.uuid4().hex for _ in range(6)]
                b.life_rows.append(dict(id=ids[0],kind='create',fieldId=ids[1],pageId=ids[2],contextId=ids[3],
                    windowId=ids[4],loaderId=ids[5],firstObservedEpochMs=b.epoch(),fieldAlive=True,pageAlive=True,
                    contextAlive=True,windowAlive=True,loaderAlive=True,alive=True,attached=True,visible=True,focused=False,current=True,text=''))
            if b.life_rows:
                row=b.life_rows[-1];retained=b.editor or b.editorContextAlive
                row.update(fieldAlive=b.editor,pageAlive=b.editor,contextAlive=retained,alive=retained,attached=b.editor,
                    visible=b.editor and b.opened,current=b.editor and b.opened)
            keyboard=dict(available=True,backend='native-vr-entity-keyboard',visible=False,instance='6'*32,
                sequence=b.life_sequence,created=False,enabled=True,raised=False,inputToHud=False,inputTarget=None,
                focusedEntity=None,tabletScreen=None,anchor=None,textDisplay=None,backPlate=None,activeLayer=0,keys=[],entities=[])
            packet=dict(lifecycleUiVersion=1,commandId=request['commandId'],runId=RUN,instance='5'*32,sequence=b.life_sequence,
                processId=123,capturedEpochMs=b.epoch(),source=dict(complete=True,tabletShown=b.opened,onHomeScreen=not b.editor,
                current=b.life_rows[-1]['id'] if b.editor else '',editors=deepcopy(b.life_rows),keyboard=keyboard))
            b.life_raw=json.dumps(packet,indent=2)+'\n'
        return PicoLifecycleSource(send,lambda:b.life_raw,b.epoch,lambda:True,123,monotonic=b.now,sleep=b.ui.sleep)

    def _native_feature_observer(self,_target):
        def send(command):
            ticket=command['ticket'];b=self.b
            if ticket not in b.file_sources:
                source=NativeBoundary(b.path);source.root=b.path/('feature-create-'+RUN+'-'+ticket);b.file_sources[ticket]=source
            with patch('test_create_files.TICKET',ticket):b.file_sources[ticket].send(command)
            b.file_sources[ticket].sample.update(instance='9'*32,processId=123);self.file_raw=json.dumps(b.file_sources[ticket].sample)
        return SimpleNamespace(send=send,clock_ms=lambda:20000,guard=lambda:True,pid=123,monotonic=self.b.now,sleep=self.b.ui.sleep)


class CreateJourneyTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.b=ResourceActor(self.path);self.b.make();self.b.opened=False;self.b.editor=False;self.b.editorContextAlive=False;self.b.life_rows=[];self.b.life_sequence=0;self.b.life_raw=''
        self.b.scope=lambda:dict(instance=SID,generation=SID,sequence=self.b.ui.command_sequence,elapsedMs=round(self.b.now()*1000),processId=123)
        self.b.ui.native.generation=SID;self.adapter=AdapterActor(self.b,self.path)
        self.journal=Journal(self.b.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,self.journal.register('create'))
        self.journal.activate(RUN,uuid.uuid4().hex)
        self.source=lambda:PhaseFixtureReader(PhaseClient(self.journal),RUN,'create',epoch_ms=self.b.epoch,monotonic=self.b.now)
        self.environ=patch.dict(os.environ,{'OVERTE_PICO_NORMAL_CREATE':'1','OVERTE_PICO_NORMAL_SCRIPTS':'1',
            'OVERTE_ANDROID_E2E_DEBUG':'1','OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'http://controlled.test/scene.json'})
        self.environ.start();self.addCleanup(self.environ.stop)
        self.root=self.make()
        def current_owner():
            state=self.b.root.state();kind=state['lastInput']['kind']
            if kind in ('models','picker'):
                constructor=PicoCreateModels if kind=='models' else PicoCreatePicker
                return constructor(self.adapter,self.adapter.target,RUN,coordinator=self.b.root).store('owner').read()
            return state|dict(lastInput=state['lastInput']['original'])
        self.b.owner=SimpleNamespace(state=current_owner)
        def before_input():
            state=current_owner();self.assertIsNotNone(state['pending']);self.assertEqual(state['lastInput']['scope'],self.b.scope())
        self.b.before_input=before_input;self.b.ui.before_input=before_input
        old_capture=self.b.ui.capture
        def file_capture():
            directory=self.b.file_sources[self.b.ticket].root if self.b.ticket in self.b.file_sources else self.path/'unused'
            with patch('test_create_file_ui.DIRECTORY',directory.as_uri()),patch('test_create_file_ui.PATH',str(directory)):return old_capture()
        self.b.ui.capture=file_capture
        home=HomeActor(self.b)
        for boundary in (patch('adapters.pico4.create_file_ui.PicoCreateFileIO',side_effect=lambda _original:FileIO(self.b)),
                patch('adapters.pico4.create_browse_setting.OwnedCreateBrowseSetting',side_effect=lambda *_a:FakeSetting(self.b)),
                patch('adapters.pico4.tablet_home.bind_home',side_effect=lambda *_a:PicoTabletHome(home,home.stage))):
            boundary.start();self.addCleanup(boundary.stop)
        self.root.invoke('prepare')
    def make(self):
        self.root=PicoCreateJourney(self.adapter,self.adapter.target,RUN,self.source());self.b.root=self.root;return self.root
    def act(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;inputs={} if inputs is None else inputs;self.journal.activate(RUN,ticket,verb,inputs)
        call=dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=URL,verb=verb,inputs=inputs)
        return self.root.invoke('act',call)
    def prefix(self):
        for step in SCENARIOS['create']['steps'][:12]:
            self.act(step['verb'],step['inputs']);self.make()
    def test_original_first_twelve_steps_share_durable_owner_and_export_actual_model(self):
        self.prefix();state=self.root.state();self.assertEqual(12,len(state['calls']));self.assertIsNone(state['subject'])
        picker=PicoCreatePicker(self.adapter,self.adapter.target,RUN,coordinator=self.root)
        original=picker.store('owner').read();self.assertEqual(['cancelled','deleted','deleted'],[s['outcome'] for s in original['steps']])
        evidence=original['steps'][1]['exportEvidence']['source']['files'][1]
        self.assertTrue(evidence['exists']);self.assertNotEqual('',original['steps'][1]['exportOriginal']['textures'])
        self.assertEqual([],self.b.rows);self.assertTrue(PicoCreateJourney.owned_target(self.adapter,self.adapter.target))
        self.assertGreater(state['inputCount'],20)
    def test_joint_cleanup_retains_cache_then_qml_context_and_retires_only_original_joint_proof(self):
        self.b.retain_resources=True;self.b.editorContextAlive=True;self.prefix();self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.store.read())
        self.b.retain_resources=False;self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(count,len(self.b.inputs));self.assertTrue(any(self.path.glob('feature-create-*/entity-import.json')))
        for row in self.b.dialog['source']['dialogs']:row['contextAlive']=False
        self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        count=len(self.b.inputs);self.assertFalse(self.b.editor);self.assertTrue(self.b.life_rows[-1]['contextAlive'])
        self.b.editorContextAlive=False;self.make();self.root.invoke('cleanup');self.assertIsNone(self.root.store.read())
        self.assertEqual(count,len(self.b.inputs));self.make();self.root.invoke('cleanup');self.assertEqual(count,len(self.b.inputs))
        self.assertFalse(self.b.opened);self.assertFalse(self.b.editor)
        self.assertFalse(PicoCreateJourney.owned_target(self.adapter,self.adapter.target))
        self.assertFalse(PicoCreateModels.owned_target(self.adapter,self.adapter.target))
        self.assertFalse(PicoCreatePicker.owned_target(self.adapter,self.adapter.target))
        self.assertFalse(list(self.path.glob('feature-create-*')))
    def test_lost_texture_apply_reconciles_actual_resource_without_any_input_replay(self):
        self.act('open');self.act('import-picker-open',{'resource':'entity-import.json'});self.act('import-picker-cancel')
        self.act('model-create',{'resource':'gltf-bundle/main.gltf'});self.b.lose='create.apply-typed'
        with self.assertRaises(NativeUIError):self.act('apply-texture',{'resource':'checker.png'})
        count=len(self.b.inputs);original=deepcopy(self.root.state()['calls']);self.b.lose=None;self.make();self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(original,self.root.state()['calls']);self.assertIsNone(self.root.state()['pending'])
        self.act('export-selection');self.act('delete-owned')
    def test_lost_new_model_reply_never_resumes_configuration_and_cleanup_uses_distinct_delete(self):
        self.act('open');self.b.lose='create.new-model'
        with self.assertRaises(NativeUIError):self.act('model-create',{'resource':'gltf-bundle/main.gltf'})
        count=len(self.b.inputs);self.b.lose=None;self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        self.root.invoke('cleanup');self.assertIsNone(self.root.store.read())
        self.assertEqual(1,sum(row.get('controlId')=='create.new-model' for row in self.b.inputs))
        self.assertEqual(1,sum(row.get('controlId')=='create.delete' for row in self.b.inputs))
    def test_standalone_child_and_foreign_original_binding_refuse_parent_bypass(self):
        self.act('open');self.act('import-picker-open',{'resource':'entity-import.json'});self.act('import-picker-cancel')
        count=len(self.b.inputs);standalone=PicoCreateModels(self.adapter,self.adapter.target,RUN)
        with standalone.lock.held():
            with self.assertRaises(NativeUIError):standalone.flow()
        picker=PicoCreatePicker(self.adapter,self.adapter.target,RUN,coordinator=self.root);store=picker.store('callbacks')
        original=store.read();foreign=deepcopy(original);foreign['binding']['processIdentity']='124:foreign';store.write(foreign,original)
        with self.assertRaises(NativeUIError):self.act('model-create',{'resource':'gltf-bundle/main.gltf'})
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.store.read())
    def test_original_phase_domain_reconnect_or_replaced_launch_cannot_relabel_parent(self):
        self.act('open');self.b.domain_revision+=2;self.b.domain_birth='4'*32;count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.act('model-create',{'resource':'gltf-bundle/main.gltf'})
        self.assertEqual(count,len(self.b.inputs));self.assertIsNone(self.root.state()['pending'])

    def test_bound_pico_factory_uses_adapter_only_phase_reader_and_retains_root_inventory(self):
        import test_normal_scripts as sources
        from adapters.feature_fixture_access import AdapterFixtureClient
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        instance,native=fixture.instance,fixture.native;configuration=Path(instance.pico_configuration[1])/'create-fixture-access.json'
        PrivateFeatureState(configuration).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL.split('/runs/')[0],adapterToken='a'*32),None)
        with patch.dict(os.environ,{'OVERTE_PICO_FEATURE_FIXTURE_CONFIG':str(configuration),'OVERTE_PICO_NORMAL_CREATE':'1'}):
            owner=instance._create_journey(native.target,RUN)
            self.assertIsInstance(owner,PicoCreateJourney);self.assertIsInstance(owner.source.client,AdapterFixtureClient)
            self.assertFalse(instance._create_feature_owned(native.target));self.assertEqual([],native.inputs)
            owner.store.write({'original':'retained'},None);self.assertTrue(instance._create_feature_owned(native.target))
            self.assertFalse(any(x.startswith('feature.create.') for x in instance.capabilities(native.target)))
            manager=instance._create_management(native.target)
            with manager.lock.held():
                with self.assertRaises(NativeUIError):manager.flow()
            self.assertEqual([],native.inputs)

    def test_phase_advance_during_actual_ui_acquisition_refuses_dispatch_and_replay(self):
        capture=RuntimeIO.capture;advanced=[]
        def changed(io):
            if self.root.state()['pending'] is not None and not advanced:
                advanced.append(True);self.journal.activate(RUN,uuid.uuid4().hex,'close',{})
            return capture(io)
        with patch.object(RuntimeIO,'capture',changed):
            with self.assertRaises(NativeUIError):self.act('open')
        self.assertTrue(advanced);self.assertEqual([],self.b.inputs);original=deepcopy(self.root.state()['calls'])
        self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual([],self.b.inputs);self.assertEqual(original,self.root.state()['calls']);self.assertIsNotNone(self.root.state()['pending'])
    def test_phase_retirement_during_native_acquisition_before_child_input_keeps_original_owner(self):
        self.act('open');reader=self.adapter._create_entity_observer;retired=[]
        def original(target,run):
            native=reader(target,run);send=native.send
            def acquire(command):
                send(command)
                if self.root.state()['pending'] is not None and not retired:
                    retired.append(True);self.journal.close(RUN)
            native.send=acquire;return native
        count=len(self.b.inputs)
        with patch.object(self.adapter,'_create_entity_observer',side_effect=original):
            with self.assertRaises(NativeUIError):self.act('model-create',{'resource':'gltf-bundle/main.gltf'})
        self.assertTrue(retired);self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.state()['pending'])
    def test_phase_advance_after_consumed_input_refuses_completion_and_readonly_relabel(self):
        original=self.root.lifecycle_packet;advanced=[]
        def capture(binding):
            packet=original(binding)
            if self.b.editor and not advanced:
                advanced.append(True);self.journal.activate(RUN,uuid.uuid4().hex,'close',{})
            return packet
        with patch.object(self.root,'lifecycle_packet',side_effect=capture):
            with self.assertRaises(NativeUIError):self.act('open')
        count=len(self.b.inputs);self.assertGreater(count,0);self.assertTrue(self.b.editor);self.assertIsNotNone(self.root.state()['pending'])
        self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.state()['pending'])
    def test_cleanup_activation_advance_before_actual_home_input_refuses_dispatch(self):
        self.act('open');self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{});capture=HomeActor.capture;advanced=[]
        def changed(actor):
            packet=capture(actor)
            if not advanced:advanced.append(True);self.journal.activate(RUN,uuid.uuid4().hex,'open',{})
            return packet
        count=len(self.b.inputs)
        with patch.object(HomeActor,'capture',changed):
            with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(count,len(self.b.inputs));self.assertTrue(self.b.editor);self.assertTrue(self.root.state()['cleanupStarted'])

    def test_final_fixture_read_cannot_age_native_sources_into_completed_call(self):
        read=self.root.source.read;delayed=[]
        def original(previous=None):
            actual=read(previous)
            if self.b.editor and not delayed:delayed.append(True);self.b.ui.sleep(2)
            return actual
        with patch.object(self.root.source,'read',side_effect=original):
            with self.assertRaises(NativeUIError):self.act('open')
        self.assertTrue(delayed);self.assertTrue(self.b.editor);self.assertIsNotNone(self.root.state()['pending'])
    def test_final_cleanup_phase_advance_keeps_all_root_originals_after_normal_close(self):
        self.act('open');self.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{});read=self.root.source.read;advanced=[]
        def original(previous=None):
            if self.root.state()['cleanupStarted'] and not self.b.editor and not self.b.opened and not advanced:
                advanced.append(True);self.journal.activate(RUN,uuid.uuid4().hex,'open',{})
            return read(previous)
        with patch.object(self.root.source,'read',side_effect=original):
            with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertTrue(advanced);self.assertIsNotNone(self.root.store.read());self.assertIsNotNone(self.root.source_store('lifecycle').read())
        count=len(self.b.inputs);self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.root.source_store('entities').read())

    def test_foreign_phase_refuses_before_normal_input(self):
        self.journal.activate(RUN,uuid.uuid4().hex,'open',{});before=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.root.invoke('act',dict(contractVersion=VERSION,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=URL,verb='open',inputs={}))
        self.assertEqual(before,len(self.b.inputs));self.assertIsNone(self.root.state()['pending'])
    def test_parent_write_failure_prevents_first_actual_normal_input(self):
        original=self.root.store.write
        def refuse_input(value,previous):
            if value['lastInput'] is not None:raise OSError('synthetic parent original-input persistence failure')
            return original(value,previous)
        with patch.object(self.root.store,'write',side_effect=refuse_input):
            with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual([],self.b.inputs);self.assertIsNotNone(self.root.state()['pending'])


if __name__=='__main__':unittest.main()
