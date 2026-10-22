"""Durable Pico Create composition on substituted original UI/source boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_picker_owner import OwnedCreatePicker,OriginalReader
from adapters.pico4.create_callbacks import NativeCreateCallbacks
from adapters.pico4.create_dialogs import NativeCreateDialogs,ui_bindings
from adapters.pico4.create_entities import NativeCreateEntities,validate,continuity
from adapters.pico4.create_files import NativeCreateFiles,OwnedCreateFiles
from adapters.pico4.create_file_ui import CreateFileUI,same_reference
from adapters.token_create_ui import TokenCreateUI,same_reference as same_create
from self_tests.test_native_script_files import BINDING
from test_create_file_ui import FileEffects
from test_create_files import NativeBoundary
from test_create_browse_setting import raw as raw_setting
from test_create_callbacks import frame as callback_frame
from test_create_dialogs import frame as dialog_frame,bound

RUN='a'*32;TICKET='b'*32;SECOND='c'*32;THIRD='d'*32
URL='http://controlled.test/feature-fixture/v1/runs/'+RUN+'/'
SID='12345678-1111-1111-1111-111111111111'
MODEL='33333333-3333-3333-3333-333333333333'


class OriginalBackend:
    def __init__(self,path):
        self.path=path;self.ui=FileEffects(SimpleNamespace(bridge_id=SID,generation=1))
        self.callback=callback_frame();self.dialog=dialog_frame();self.callback['instance']=self.dialog['instance']='9'*32;self.callback['source']['managers'][0]['callbacks'].update(proxies=[],callbacks=[])
        self.dialog['source']['createDialogSourceVersion']=3
        self.dialog['source']['dialogs']=[];self.rows=[];self.absent=[];self.unowned=[]
        code=(ROOT/'scripts/system/create/edit.js').read_text().encode('utf-16le')
        self.source={'import':dict(sha256=hashlib.sha256(code).hexdigest(),codeUnits=len(code)//2)}
        code=(ROOT/'scripts/system/create/entityList/entityList.js').read_text().encode('utf-16le')
        self.source['export']=dict(sha256=hashlib.sha256(code).hexdigest(),codeUnits=len(code)//2)
        compiled=self.callback['source']['managers'][0]['compiled']['compilations'][0]
        compiled.update(resourceName='file:///original/scripts/system/create/edit.js',**self.source['import'])
        exported=deepcopy(compiled);exported.update(scriptId=18,resourceName='file:///original/scripts/system/create/entityList/entityList.js',**self.source['export'])
        self.callback['source']['managers'][0]['compiled']['compilations'].append(exported)
        self.frames={};self.sequence={'callbacks':0,'dialogs':0,'entities':0};self.file_sources={};self.file_owners={}
        self.ticket=None;self.current=None;self.status='';self.selected=[];self.index=0;self.tab=4;self.focus=None
        self.inputs=[];self.owner=None;self.ignore_import=False;self.lose=None;self.invalid_model=False;self.freeze_epoch=False;self.freeze_dialog=False;self.export_fault=None;self.domain_birth='8'*32;self.domain_revision=2
        self.ui.intents=IntentList(self);self.ui.before_input=self.before_input
    def now(self):return self.ui.clock
    def epoch(self):return 20000+(0 if self.freeze_epoch else round(self.now()*1000))
    def scope(self):return dict(instance=SID,generation=1,sequence=self.ui.command_sequence,elapsedMs=round(self.now()*1000),processId=123)
    def before_input(self):
        if not self.owner.state()['pending']:raise AssertionError('no durable operation')
        if self.owner.state()['lastInput']['scope']!=self.scope():raise AssertionError('intent not original')
    def reader(self,kind):
        def send(command):
            self.sequence[kind]+=1;epoch=self.epoch()
            if kind=='entities':
                source=dict(createEntitySourceVersion=2,domainSession=dict(domainSessionVersion=1,instance='7'*32,revision=self.domain_revision,connected=True,
                    domainSha256=hashlib.sha256((RUN+':').encode()+uuid.UUID('11111111-1111-1111-1111-111111111111').bytes).hexdigest(),
                    connectionBirth=self.domain_birth,connectedEpochMs=19000),runId=RUN,domainConnected=True,domainId='11111111-1111-1111-1111-111111111111',
                    sessionId='22222222-2222-2222-2222-222222222222',canRez=True,canRezTmp=False,
                    entities=deepcopy(self.rows),absentIds=sorted(self.absent),scan=dict(center=[0,1,0],radiusMeters=128,
                    propertyScope='create-domain-v1',scannedEntities=len(self.rows)+len(self.unowned),unowned=deepcopy(self.unowned)))
                value=dict(schemaVersion=1,requestId=command['commandId'],instance='9'*32,sequence=self.sequence[kind],processId=123,
                    requestedEpochMs=epoch,capturedEpochMs=epoch,source=source)
            else:
                value=deepcopy(self.callback if kind=='callbacks' else self.dialog)
                value.update(requestId=command['commandId'],sequence=self.sequence[kind],requestedEpochMs=epoch,capturedEpochMs=epoch)
                if kind=='dialogs':value['source'].update(sequence=self.sequence[kind],elapsedMs=0 if self.freeze_dialog else round(self.now()*1000))
            self.frames[kind]=json.dumps(value,indent=2)+'\n'
        cls=dict(callbacks=NativeCreateCallbacks,dialogs=NativeCreateDialogs,entities=NativeCreateEntities)[kind]
        kwargs=dict(run=RUN) if kind=='entities' else {}
        return cls(send,lambda:self.frames[kind],self.epoch,lambda:True,123,monotonic=self.now,sleep=self.ui.sleep,**kwargs)
    def store(self,name):return PrivateFeatureState(self.path/(name+'.json'))
    def files(self,ticket):
        if ticket not in self.file_sources:
            source=NativeBoundary(self.path);source.root=self.path/('feature-create-'+RUN+'-'+ticket)
            self.file_sources[ticket]=source
        source=self.file_sources[ticket]
        def send(command):
            with patch('test_create_files.TICKET',ticket):source.send(command)
            source.sample.update(instance='9'*32,processId=123)
        native=NativeCreateFiles(send,lambda:json.dumps(source.sample),lambda:20000,lambda:True,123,
            ticket=ticket,monotonic=lambda:source.clock,sleep=source.sleep)
        return OwnedCreateFiles(native,self.store('files-'+ticket),self.binding)
    def make(self):
        self.binding=deepcopy(BINDING);self.binding.update(processIdentity='123:original-process',sessionId=SID,generation=1)
        readers={k:OriginalReader(self.reader(k),self.store(k),self.binding) for k in self.sequence}
        owner=OwnedCreatePicker(self.store('owner'),self.binding,lambda intent:TokenCreateUI(NormalIO(self),intent,
            monotonic=self.now,sleep=self.ui.sleep),lambda intent,step:CreateFileUI(FileIO(self),intent,step['directory'],RUN,
            step['ticket'],step['role'],step['beforeUi'],monotonic=self.now,sleep=self.ui.sleep),FileIO(self),self.files,
            readers['callbacks'],readers['dialogs'],readers['entities'],FakeSetting(self),self.source,monotonic=self.now,sleep=self.ui.sleep)
        self.owner=owner;return owner
    def born(self):
        step=self.owner.state()['steps'][-1];self.ticket=step['ticket'];self.ui.role=step['role'];number=len(self.dialog['source']['dialogs'])+1
        ids=[uuid.uuid5(uuid.NAMESPACE_URL,str(number)+':'+str(k)).hex for k in range(7)]
        self.ui.root=ids[0];source=self.callback['source']['managers'][0]['callbacks'];source['sequence']+=1
        proxy=dict(id=ids[1],targetClass='WindowScriptingInterface',signal='browseChanged(QString)' if step['role']=='import' else 'saveFileChanged(QString)',createdEpochMs=self.epoch(),retiredEpochMs=0,dispatches=0)
        callback=dict(id=ids[2],proxyId=ids[1],scriptId=17 if step['role']=='import' else 18,connectedEpochMs=self.epoch(),disconnectedEpochMs=0)
        source['proxies'].append(proxy);source['proxies'].sort(key=lambda r:r['id']);source['callbacks'].append(callback);source['callbacks'].sort(key=lambda r:r['id'])
        row=dict(id=ids[3],rootId=ids[4],listenerId=ids[5],contextId=ids[6],windowId='1'*32,role=step['role'],
            componentSource='file:///original/dialogs/TabletFileDialog.qml',registeredEpochMs=self.epoch(),enteredEpochMs=0,
            returnedEpochMs=0,pending=True,dispatches=0,listenerAlive=True,rootAlive=True,contextAlive=True,windowAlive=True,responseSha256=None,
            browseSettingRead=dict(before=dict(capturedEpochMs=self.epoch(),raw=deepcopy(self.setting['current'])),
                after=dict(capturedEpochMs=self.epoch(),raw=deepcopy(self.setting['current']))))
        self.dialog['source']['dialogs'].append(row);self.dialog['source']['dialogs'].sort(key=lambda r:r['id'])
        self.current=(row,callback,proxy);self.status=''
    def returned(self,accept):
        row,callback,proxy=self.current;row.update(enteredEpochMs=self.epoch(),returnedEpochMs=self.epoch(),responseSha256=hashlib.sha256((('/owned/'+self.ticket) if accept else '').encode()).hexdigest(),pending=False,
            listenerAlive=False,rootAlive=False)
        callback['disconnectedEpochMs']=self.epoch();self.callback['source']['managers'][0]['callbacks']['sequence']+=1
        if not accept:
            if row['role']=='import':self.status='Import cancelled.'
            return
        if row['role']=='export':
            if self.export_fault=='missing':return
            model=self.rows[0]
            document=dict(DataVersion=0,Entities=[dict(id='{'+model['id']+'}',type=model['type'],name=model['name'],
                modelURL=model['modelUrl'],dimensions=dict(zip('xyz',model['dimensions'])),textures=model['textures'],position=dict(x=0,y=0,z=0))])
            if self.export_fault=='foreign':document['Entities'][0]['modelURL']='http://foreign.test/model.gltf'
            if self.export_fault=='version':document['DataVersion']=3
            output=self.file_sources[self.ticket].root/'export.json';output.write_text(json.dumps(document));output.chmod(0o600)
            if self.export_fault=='old-time':os.utime(output,ns=(1,1))
            return
        self.status='Imported 1 entities.'
        if not self.ignore_import:
            raw=(self.file_sources[self.ticket].root/'entity-import.json').read_bytes();original=json.loads(raw)['Entities'][0]
            self.rows=[dict(id=MODEL,name=original['name'],type='Model',hostType='domain',modelUrl=original['modelURL'] if not self.invalid_model else 'http://foreign.test/a.gltf',
                textures='',position=[0,1,-2],rotation=[0,0,0,1],dimensions=[1,1,1],parentId=None,visible=True,locked=False,
                lastEditedEpochUs=self.epoch()*1000)]
            self.selected=[MODEL]


class FakeSetting:
    def __init__(self,b):
        self.b=b;self.previous=None
        if not hasattr(b,'setting'):
            b.setting=dict(createBrowseSettingVersion=3,originalPhysical={'format':'ini','pathSha256':'5'*64,'row':{}},original=raw_setting(),current=raw_setting(),owned=raw_setting(),writer={'raw':raw_setting(),'physical':{'format':'ini','pathSha256':'5'*64,'row':{}}},claims=[],reads=[],restored=False)
    def reserve(self,run):return self.observe()
    def observe(self):return deepcopy(self.b.setting)
    def claim_read(self,files,binding):
        if not any(r['dialogId']==binding['dialogId'] for r in self.b.setting['reads']):
            self.b.setting['reads'].append(dict(dialogId=binding['dialogId']))
        return self.observe()
    def claim(self,files,binding):
        if not any(r['dialogId']==binding['dialogId'] for r in self.b.setting['claims']):
            setting=raw_setting('/owned/'+files['ticket'])
            self.b.setting['claims'].append(dict(dialogId=binding['dialogId'],setting=setting))
            self.b.setting['current']=setting;self.b.setting['owned']=setting;self.b.setting['writer']['raw']=deepcopy(setting)
        return self.observe()
    def restore(self):
        self.b.setting['current']=deepcopy(self.b.setting['original']);self.b.setting['writer']['raw']=deepcopy(self.b.setting['original']);self.b.setting['restored']=True
        return self.observe()
    def release(self):self.restore()
    def retire(self):pass


class IntentList:
    def __init__(self,backend):self.backend=backend
    def __getitem__(self,index):
        if index!=-1:raise AssertionError(index)
        return self.backend.owner.state()['lastInput']


class FileIO:
    def __init__(self,b):self.b=b
    def capture(self):return self.b.ui.capture()
    def dialog_bindings(self):
        value=self.capture();bindings=[]
        if self.b.ui.root:
            packet=deepcopy(self.b.dialog);packet.update(requestedEpochMs=self.b.epoch(),capturedEpochMs=self.b.epoch())
            row=self.b.current[0];packet['source']['dialogs']=[row]
            bindings=[dict(uiRootId=self.b.ui.root,native=bound(packet))]
        return ui_bindings(dict(bindingVersion=1,inventoryInstance=value['inventory']['instance'],inventorySequence=value['inventory']['sequence'],complete=True,bindings=bindings),value['inventory'])
    def command(self,identifier,action,reference,text=None):
        same_reference(reference,self.capture(),identifier);scope=reference['scope']
        command=dict(controlId=identifier,action=action,controlToken=next(r for r in reference['controls'] if r['id']==identifier)['token'],
            bridgeId=scope['instance'],generation=scope['generation'],sequence=scope['sequence']+1)
        if text is not None:command['text']=text
        accepted=self.b.ui.apply(command);need=unittest.TestCase().assertTrue;need(accepted)
        self.b.inputs.append(deepcopy(command))
        if identifier in ('create-file.cancel','create-file.accept'):
            self.b.returned(identifier.endswith('accept'))
        if self.b.lose==identifier:raise NativeUIError('synthetic lost input result')
    def activate(self,identifier,*,reference):self.command(identifier,'activate',reference)
    def replace(self,identifier,text,*,reference):self.command(identifier,'replace',reference,text)
    def submit(self,identifier,*,reference):self.command(identifier,'submit',reference)


class NormalIO:
    def __init__(self,b):self.b=b
    def capture(self):
        b=self.b;rows=[]
        def add(identifier,**kwargs):
            row=dict(id=identifier,enabled=True,focused=b.focus==identifier,inputReady=identifier!='create.page',**kwargs)
            row['token']=uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)).hex;rows.append(row)
        add('create.page',profile='native-create-v1',tab=b.tab,selectedIds=list(b.selected),statusError=False,statusText=b.status,componentSourceSha256='a'*64)
        for k in range(5):add('create.tab.'+str(k))
        add('create.import-host',currentIndex=b.index,count=2);add('create.import-browse');add('create.export');add('create.refresh');add('create.delete')
        for entity in b.rows:add('create.entity.'+entity['id'],entityId=entity['id'])
        add('create.name',text='')
        return dict(createControlsVersion=1,open=True,ready=True,scope=b.scope(),controls=rows)
    def command(self,identifier,action,reference,value=None):
        b=self.b;same_create(reference,self.capture(),identifier);b.before_input();b.ui.command_sequence+=1
        b.inputs.append(dict(controlId=identifier,action=action))
        if identifier.startswith('create.tab.'):b.tab=int(identifier[-1])
        elif identifier=='create.import-host' and action=='select-index':b.index=value
        elif identifier in ('create.import-browse','create.export'):b.born()
        elif identifier.startswith('create.entity.'):b.selected=[identifier[len('create.entity.'):]]
        elif identifier=='create.delete':b.rows=[];b.absent=[MODEL];b.selected=[]
        else:b.focus=identifier
        if b.lose==identifier:raise NativeUIError('synthetic lost normal input result')
    def activate(self,identifier,*,reference):self.command(identifier,'activate',reference)
    def select_index(self,identifier,index,*,reference):self.command(identifier,'select-index',reference,index)
    def scroll(self,*args,**kwargs):raise AssertionError('fixture has no scroll')


class CreatePickerOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.b=OriginalBackend(self.path);self.flow=self.b.make()
    def open(self,ticket=TICKET):return self.flow.open(RUN,ticket,URL)
    def test_cancel_then_import_delete_preserves_context_owners_across_reconstruction(self):
        self.open();self.flow.cancel();self.assertEqual('cancelled',self.flow.state()['steps'][-1]['outcome'])
        self.assertTrue(self.b.current[0]['contextAlive']);self.assertTrue(self.b.file_sources[TICKET].root.exists())
        self.flow=self.b.make();self.open(SECOND);self.flow.import_file()
        self.assertEqual(MODEL,self.flow.state()['steps'][-1]['entityId']);self.flow.delete_import()
        with self.assertRaises(NativeUIError):self.flow.release()
        self.assertIsNotNone(self.b.store('owner').read());self.assertTrue(self.b.file_sources[TICKET].root.exists())
        for row in self.b.dialog['source']['dialogs']:row['contextAlive']=False
        self.flow=self.b.make();self.flow.release()
        self.assertIsNone(self.b.store('owner').read());self.assertFalse(self.b.file_sources[TICKET].root.exists())
        self.assertFalse(self.b.file_sources[SECOND].root.exists())
    def test_import_save_original_bytes_delete_and_setting_restore_compose_across_restart(self):
        self.open();self.flow.import_file();original=deepcopy(self.b.rows[0])
        self.flow=self.b.make();self.flow.open_export(RUN,SECOND,URL);self.flow.export_file()
        step=self.flow.state()['steps'][-1];self.assertEqual('exported',step['outcome']);self.assertEqual(original,step['exportOriginal'])
        output=self.flow.owned_files(step).exported();self.assertEqual(0,json.loads(base64.b64decode(output['base64']))['DataVersion'])
        self.assertEqual(MODEL,self.b.rows[0]['id']);self.assertEqual('imported',self.flow.state()['steps'][0]['outcome'])
        self.flow=self.b.make();self.flow.delete_import()
        with self.assertRaises(NativeUIError):self.flow.release()
        self.assertTrue(self.b.file_sources[SECOND].root.exists())
        for row in self.b.dialog['source']['dialogs']:row['contextAlive']=False
        self.flow=self.b.make();self.flow.release();self.assertFalse(self.b.file_sources[SECOND].root.exists())
        self.assertEqual(self.b.setting['original'],self.b.setting['current']);self.assertTrue(self.b.setting['restored'])
    def test_uncertain_save_select_reconciles_once_and_invalid_output_never_proves_export(self):
        for fault in ('lost','missing','foreign','version','old-time'):
            with self.subTest(fault=fault):
                path=self.path/fault;path.mkdir(mode=0o700);b=OriginalBackend(path);flow=b.make();flow.open(RUN,TICKET,URL);flow.import_file()
                flow.open_export(RUN,SECOND,URL)
                if fault=='lost':b.lose='create-file.accept'
                else:b.export_fault=fault
                with self.assertRaises(NativeUIError):flow.export_file()
                flow=b.make()
                with self.assertRaises(NativeUIError):flow.export_file()
                if fault=='lost':flow.reconcile();self.assertEqual('exported',flow.state()['steps'][-1]['outcome'])
                else:
                    with self.assertRaises(NativeUIError):flow.reconcile()
                    self.assertEqual('export',flow.state()['pending']['operation'])
                self.assertEqual(2,sum(r['controlId']=='create-file.accept' for r in b.inputs))
                self.assertTrue(b.file_sources[SECOND].root.exists());self.assertEqual(MODEL,b.rows[0]['id'])
    def test_normal_save_cancel_preserves_selected_model_and_never_creates_output(self):
        self.open();self.flow.import_file();self.flow.open_export(RUN,SECOND,URL);self.flow.cancel()
        self.assertEqual([MODEL],self.b.selected);self.assertFalse((self.b.file_sources[SECOND].root/'export.json').exists())
        self.flow.delete_import();self.assertEqual([],self.b.rows)
    def test_preexisting_export_before_select_refuses_input_and_preserves_original_file(self):
        self.open();self.flow.import_file();self.flow.open_export(RUN,SECOND,URL)
        path=self.b.file_sources[SECOND].root/'export.json';path.write_text('{"foreign":"before Select"}');path.chmod(0o600)
        count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.flow.export_file()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.b.store('owner').read());self.assertTrue(path.exists())
    def test_export_original_inode_time_and_bytes_survive_reconstruction_and_replacement_refuses(self):
        self.open();self.flow.import_file();self.flow.open_export(RUN,SECOND,URL);self.flow.export_file()
        step=self.flow.state()['steps'][-1];packet=deepcopy(step['exportEvidence']);self.flow=self.b.make()
        self.assertEqual(packet,self.flow.state()['steps'][-1]['exportEvidence']);self.assertFalse(step['beforeChoice']['source']['files'][1]['exists'])
        path=self.b.file_sources[SECOND].root/'export.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(NativeUIError):self.flow.verify_export(step)
        self.assertEqual(packet,self.flow.state()['steps'][-1]['exportEvidence'])
    def test_same_uuid_disconnect_reconnect_generation_refuses_input_or_cleanup(self):
        self.open();count=len(self.b.inputs);self.b.domain_birth='6'*32;self.b.domain_revision+=2
        with self.assertRaises(NativeUIError):self.flow.import_file()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.b.store('owner').read())
    def test_old_owner_without_original_setting_capture_is_retained_and_refused(self):
        self.open();state=self.b.store('owner').read();self.b.store('owner').write(state|dict(schemaVersion=1),state)
        with self.assertRaises(NativeUIError):self.b.make()
        self.assertTrue(self.b.file_sources[TICKET].root.exists())
    def test_uncertain_cancel_is_never_resent_and_reconciles_original_delivery(self):
        self.open();self.b.lose='create-file.cancel'
        with self.assertRaises(NativeUIError):self.flow.cancel()
        self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.cancel()
        self.flow.reconcile();self.assertEqual(1,sum(r['controlId']=='create-file.cancel' for r in self.b.inputs))
        self.assertEqual('cancelled',self.flow.state()['steps'][-1]['outcome'])
    def test_uncertain_accept_is_not_replayed_or_mistaken_for_missing_domain_effect(self):
        self.open();self.b.lose='create-file.accept'
        with self.assertRaises(NativeUIError):self.flow.import_file()
        self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.import_file()
        self.flow.reconcile();self.assertEqual(MODEL,self.flow.state()['steps'][-1]['entityId'])
        self.assertEqual(1,sum(r['controlId']=='create-file.accept' for r in self.b.inputs))
    def test_ack_selection_or_foreign_model_url_never_proves_the_domain_import(self):
        for fault in ('ignore_import','invalid_model'):
            with self.subTest(fault=fault):
                path=self.path/fault;path.mkdir(mode=0o700);b=OriginalBackend(path);flow=b.make();flow.open(RUN,TICKET,URL)
                setattr(b,fault,True)
                with self.assertRaises(NativeUIError):flow.import_file()
                self.assertEqual('import',flow.state()['pending']['operation']);self.assertIsNotNone(b.store('owner').read())
                with self.assertRaises(NativeUIError):flow.import_file()
                self.assertEqual(1,sum(r['controlId']=='create-file.accept' for r in b.inputs))
    def test_uncertain_open_can_only_cancel_actual_original_picker(self):
        self.b.lose='create.import-browse'
        with self.assertRaises(NativeUIError):self.open()
        self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.open()
        self.flow.cancel();self.assertEqual(1,sum(r['controlId']=='create.import-browse' for r in self.b.inputs))
    def test_frozen_native_clock_unrelated_callbacks_and_changed_scene_retain_owner(self):
        self.open();self.b.freeze_epoch=True
        with self.assertRaises(NativeUIError):self.flow.cancel()
        self.assertIsNotNone(self.b.store('owner').read())
        self.b.freeze_epoch=False;self.b.unowned=[dict(id='44444444-4444-4444-4444-444444444444',sha256='a'*64)]
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertIsNotNone(self.b.store('owner').read())
    def test_lost_filename_focus_uses_only_distinct_cancel_recovery(self):
        self.open();self.b.lose='create-file.name'
        with self.assertRaises(NativeUIError):self.flow.import_file()
        self.flow=self.b.make();self.flow.cancel()
        self.assertEqual('cancelled',self.flow.state()['steps'][-1]['outcome'])
        self.assertEqual(1,sum(r['controlId']=='create-file.name' for r in self.b.inputs))
        self.assertFalse(any(r['controlId']=='create-file.accept' for r in self.b.inputs))
    def test_frozen_dialog_clock_foreign_callback_history_or_changed_cancel_selection_never_retires(self):
        for fault in ('dialog-clock','callback-history','cancel-selection'):
            with self.subTest(fault=fault):
                path=self.path/fault;path.mkdir(mode=0o700);b=OriginalBackend(path);flow=b.make();flow.open(RUN,TICKET,URL)
                returned=b.returned
                def changed(accept):
                    returned(accept)
                    if fault=='callback-history':
                        source=b.callback['source']['managers'][0]['callbacks'];source['sequence']+=1
                        row=deepcopy(source['callbacks'][0]);row['id']='7'*32
                        source['callbacks'].append(row);source['callbacks'].sort(key=lambda r:r['id'])
                    elif fault=='cancel-selection':b.selected=[MODEL]
                b.returned=changed
                if fault=='dialog-clock':b.freeze_dialog=True
                with self.assertRaises(NativeUIError):flow.cancel()
                self.assertIsNotNone(b.store('owner').read());self.assertTrue(b.file_sources[TICKET].root.exists())
    def test_matching_source_name_without_original_compilation_bytes_is_rejected(self):
        self.b.callback['source']['managers'][0]['compiled']['compilations'][0]['sha256']='e'*64
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual('open',self.flow.state()['pending']['operation'])
        self.assertFalse(any(r['controlId']=='create-file.accept' for r in self.b.inputs))
    def test_bound_factory_and_cleanup_inventory_retain_orphan_source_records(self):
        import test_normal_scripts as sources
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        instance,native=fixture.instance,fixture.native
        with patch.dict(os.environ,{'OVERTE_PICO_NORMAL_CREATE':'1'}):
            picker=instance._create_picker(native.target,RUN);self.assertFalse(picker.owned())
            self.assertFalse(instance._create_picker_owned(native.target))
            journal=picker.store('callbacks');journal.write({'original':'unresolved'},None)
            self.assertTrue(picker.owned());self.assertTrue(instance._create_picker_owned(native.target))
            with self.assertRaises(NativeUIError):picker.flow()
            self.assertIsNotNone(journal.read());self.assertEqual([],native.inputs)
    def test_readonly_acquisition_failure_recovers_only_with_joint_original_quiet(self):
        self.flow.actual();self.assertIsNone(self.b.store('owner').read())
        self.assertIsNotNone(self.b.store('callbacks').read());self.flow=self.b.make()
        self.flow.release_observations();self.assertIsNone(self.b.store('callbacks').read())
        self.assertIsNone(self.b.store('dialogs').read());self.assertIsNone(self.b.store('entities').read())
    def test_final_release_requires_fresh_ui_inventory_and_advancing_original_ui_clock(self):
        for fault in ('inventory','clock'):
            with self.subTest(fault=fault):
                path=self.path/fault;path.mkdir(mode=0o700);b=OriginalBackend(path);flow=b.make();flow.open(RUN,TICKET,URL);flow.cancel()
                for row in b.dialog['source']['dialogs']:row['contextAlive']=False
                if fault=='inventory':b.ui.frozen=True
                else:b.ui.native_elapsed=round(b.ui.clock*1000)
                with self.assertRaises(NativeUIError):flow.release()
                self.assertIsNotNone(b.store('owner').read());self.assertTrue(b.file_sources[TICKET].root.exists())
    def test_raw_originals_and_candidate_binding_cannot_be_replaced(self):
        self.open();record=self.b.store('callbacks').read()
        self.assertEqual(hashlib.sha256(record['raw'].encode()).hexdigest(),record['sha256'])
        bad=deepcopy(record);bad['binding']['artifactSha256']='e'*64;self.b.store('callbacks').write(bad,record)
        with self.assertRaises(NativeUIError):self.b.make()
        self.assertIsNotNone(self.b.store('owner').read())


from test_create_entities import CreateEntitySourceTests

if __name__=='__main__':unittest.main()
