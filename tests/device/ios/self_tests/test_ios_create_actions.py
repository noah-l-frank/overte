"""Whole action-journal tests at explicit product-control/native SDK seams.

The simulated product owns UUIDs, tree bytes, selection and file writes. These
tests exercise orchestration/recovery, not UIKit, rendering or native execution;
their command transport has separate real HTTP/AFC tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI, NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS
from ios.adapters import create_state, create_product_state as product
from ios.adapters.create_action_owner import CreateActionOwner, CreateInputPending
from ios.adapters.create_actions import CreateActions
from ios.adapters.create_inputs import IOSCreateUI
from ios.adapters.create_marker_identity import PreparedCreateMarker
from ios.adapters.create_rez_client import CreateRezClient
from ios.adapters.create_work import IOSCreateWork
from ios.adapters.create_world_input import CreateWorldInput
from ios.adapters.native_geometry import OriginalGeometry
from ios.self_tests.test_ios_create_files import BINDING, URL, Boundary
from ios.adapters.create_files import OwnedCreateFiles
from ios.self_tests.test_ios_create_state import RUN, EPOCH, ID, ROOT, DOMAIN, SESSION, packet, version2, remap
from ios.self_tests.test_ios_create_work import packet as work_packet, ROOT as SCRIPTS_ROOT

SETTINGS = dict(createAppMode='object',voxelEditMode='single',voxelRemove=False,
    voxelEditDynamics='click',voxelPointerMode='laser',voxelSphereSize=.5,voxelBrushLength=.5)


class Product:
    def __init__(self):
        self.value = version2(packet()); self.value['iosCreateStateVersion'] = 3
        self.calls=[]; self.cursor=0; self.clock=0.; self.ignore=False; self.lose=False
        self.marker=self.entity('Web',host='local');self.marker.update(id=ID,name='e2e-'+RUN+'-script',sourceUrl='http://marker',userData='{}')
        self.value['source']['entities']=[self.marker]
    def entity(self,kind,*,host='domain',resource=''):
        return dict(id=str(uuid.uuid4()),hostType=host,createdEpochUs=str(EPOCH*1000),lastEditedEpochUs=str(EPOCH*1000+1),
            name='',type=kind,shape='Cube' if kind=='Shape' else '',dimensions=[8,8,8],modelURL=resource,textures='',
            lastEditedBy=SESSION,locked=False,visible=True,model=dict(present=True,loaded=True,addedToScene=True,failed=False,textures=[]) if kind=='Model' else {},
            voxels=dict(ready=True,bytes=128,sha256='1'*64,volume=[8,8,8],onCount=512) if kind=='PolyVox' else {},
            position=[0,0,-4],rotation=[0,0,0,1],sourceUrl='',userData='',collisionless=True)
    def page(self):
        return next(row for row in self.value['source']['roots'] if not row['destroyed'] and row['kind']=='editor')
    def read(self,run):
        if hasattr(self,'search_original'):
            self.value['iosCreateStateVersion']=4
            for root in self.value['source']['roots']:
                if not root['destroyed'] and root.get('kind')=='editor':
                    root['propertySearch']=dict(rootId=root['id'],objectName='NativeCreatePropertySearch',text=self.search_original(root))
        self.cursor+=1; self.clock+=.001; self.value['sequence']=self.cursor
        self.value['requestId']='ios-'+uuid.uuid4().hex
        self.value['clockBefore']=dict(epochMs=EPOCH+self.cursor*2,monotonicMs=self.cursor*2)
        self.value['clockAfter']=dict(epochMs=EPOCH+self.cursor*2+1,monotonicMs=self.cursor*2+1)
        tree=self.value['source']['tree'];rows=[]
        self.value['source']['entities'].sort(key=lambda row:row['id'])
        for row in self.value['source']['entities']:
            raw=json.dumps(row,sort_keys=True,separators=(',',':')).encode()
            rows.append(dict(id=row['id'],hostType=row['hostType'],ready=True,createdEpochUs=row['createdEpochUs'],
                lastEditedEpochUs=row['lastEditedEpochUs'],lastEditedAfterEpochUs=row['lastEditedEpochUs'],semanticBytes=len(raw),semanticSha256=hashlib.sha256(raw).hexdigest()))
        tree.update(revisionBefore=self.cursor,revisionAfter=self.cursor,totalEntities=len(rows),entities=rows)
        result=deepcopy(self.value);create_state.original(result);return result
    def sleep(self,seconds):self.clock+=seconds
    def tablet(self,locator):
        shown=locator.value=='OverteTabletOpen';self.value['source']['tabletShown']=shown
        for row in self.value['source']['roots']:
            if not row['destroyed']:row['active']=shown and row['visible']
    def open(self):
        roots=self.value['source']['roots'];existing=[row for row in roots if not row['destroyed'] and row['kind']=='editor']
        if not existing:
            roots.append(dict(id=ROOT,destroyed=False,kind='editor',visible=True,active=True,
                page=dict(profile='native-create-v1',tab=2,selectedIds=[],statusError=False,statusText='',componentSourceSha256='e'*64,inputReady=False),
                changed={},voxelSettings=deepcopy(SETTINGS),numericFocus=False))
        else:existing[0].update(visible=True,active=True)
    def close(self):self.page().update(visible=False,active=False)
    def select(self,id_):self.page()['page']['selectedIds']=[id_]
    def selected(self):return next(row for row in self.value['source']['entities'] if row['id']==self.page()['page']['selectedIds'][0])
    def create(self,role,*,resource=''):
        self.calls.append(('create',role,resource))
        if self.ignore:return
        page=self.page()['page']
        if not(self.value['source']['canRez'] or self.value['source']['canRezTmp']):
            page.update(statusError=True,statusText=product.PERMISSION_ERROR);return
        row=self.entity(dict(model='Model',cube='Shape',voxel='PolyVox')[role],resource=resource)
        self.value['source']['entities'].append(row);self.select(row['id']);page.update(statusError=False,statusText='')
        if self.lose:raise NativeUIError('Simulated lost product input return')
    def name_size(self,id_,name):
        self.select(id_);self.selected().update(name=name,dimensions=[1,1,1])
    def position(self,id_,values):self.select(id_);self.selected()['position']=deepcopy(values)
    def delete(self):
        id_=self.selected()['id'];self.calls.append(('delete',id_));self.value['source']['entities']=[row for row in self.value['source']['entities'] if row['id']!=id_]
        self.page()['page']['selectedIds']=[]
    def picker(self,role):
        # Picker wire metadata is tested separately. Here roots use the actual
        # original control fixture, with unique per-dialog native root identity.
        row=dict(role=role,rootId=str(uuid.uuid4()),componentSource='qrc:/qml/dialogs/NativeFileBrowser.qml',
            caption='Select .json to Import' if role=='import' else 'Select Where to Save',filter='*.json',saveDialog=role=='export',
            bundleMode=False,selectDirectory=False,directory='file:///private/create/',closing=False,requestId=str(uuid.uuid4()),error='')
        self.value['source']['roots'].append(dict(id=row['rootId'],destroyed=False,kind=role,visible=True,active=True,picker=row))
    def picker_state(self,role):return deepcopy(next(row['picker'] for row in self.value['source']['roots'] if row.get('kind')==role and not row['destroyed']))
    def dismiss(self,role,id_):
        root=next(row for row in self.value['source']['roots'] if row['id']==id_);root.clear();root.update(id=id_,destroyed=True)
    def texture(self,id_,url):
        self.select(id_);remap(self.selected());self.selected()['textures']=json.dumps({'checker.png':url})
        texture=self.selected()['model']['textures'][0];texture['url']=texture['original']['url']=url
    def voxel_settings(self,**values):
        if values:self.page()['voxelSettings']=dict(createAppMode=['object','voxel'][values['mode']],voxelEditMode=['single','sphere','cube'][values['shape']],
            voxelRemove=values['remove'],voxelEditDynamics=['click','continuous'][values['dynamics']],voxelPointerMode=['laser','brush'][values['pointer']],
            voxelSphereSize=values['diameter'],voxelBrushLength=values['reach'])
    def touch(self,id_,root,epoch):
        self.calls.append(('touch',id_));row=self.selected();assert row['id']==id_
        row['voxels'].update(bytes=120,sha256='2'*64,onCount=448)


class CreateActionsTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.root=Path(directory.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.product=Product();self.file_boundary=Boundary(self.root)
        self.source=object.__new__(create_state.IOSCreateState);self.source.pid=42;self.source.last=None
        def read(run):
            value=self.product.read(run)
            create_state.validate(value,dict(schemaVersion=1,action=create_state.ACTION,commandId=value['requestId'],runId=run),42,previous=self.source.last)
            self.source.last=deepcopy(value);return value
        self.source.read=read
        self.work=object.__new__(IOSCreateWork);self.work.pid=42;self.work.last=None;self.work.read=lambda run:work_packet()
        self.geometry=object.__new__(OriginalGeometry);self.geometry.capture=lambda:dict(observation=dict(nativeUi=dict(keyboardVisible=False,imeInsetBottom=0)))
        self.normal=object.__new__(NativeUI);self.normal.click=self.product.tablet;self.normal.release_actions=lambda:None
        self.ui=object.__new__(IOSCreateUI);self.ui.io=SimpleNamespace(owner=None)
        for name,callback in dict(open_create=self.product.open,create_domain=self.product.create,select_entity=self.product.select,
            name_and_size=self.product.name_size,position=self.product.position,delete_entity=self.product.delete,texture=self.product.texture,
            picker_state=self.product.picker_state,voxel_settings=self.product.voxel_settings,close=self.product.close).items():setattr(self.ui,name,callback)
        self.ui.create_polyvox=lambda:self.product.create('voxel');self.ui.open_import=lambda:self.product.picker('import')
        self.ui.cancel_import=lambda id_:self.product.dismiss('import',id_);self.ui.export=lambda id_:self.product.picker('export')
        self.ui.replace=lambda id_,value:None;self.ui.tab=lambda tab:self.product.page()['page'].update(tab=tab)
        self.ui.capture=lambda:dict(controls=[dict(id='create.page',enabled=True)])
        def accept(role,id_,directory,run):
            if role=='import':
                data=json.loads((self.file_boundary.root/'entity-import.json').read_text());self.product.create('model',resource=data['Entities'][0]['modelURL'])
            else:(self.file_boundary.root/'export.json').write_text(json.dumps(dict(DataVersion=0,Entities=[deepcopy(self.product.selected())])))
            self.product.dismiss(role,id_)
        self.ui.accept_file=accept
        self.rez=object.__new__(CreateRezClient);self.rez.binding=BINDING;self.rez.config=dict(domainId=DOMAIN);self.rez.state=None
        def request(operation,*,allowed=None):
            if operation=='set':self.product.value['source'].update(canRez=allowed,canRezTmp=False)
            if operation=='restore':self.product.value['source'].update(canRez=True,canRezTmp=False)
            self.rez.state=dict(commands=[dict(original={'operation':operation})]);return dict(operation=operation)
        self.rez.request=request
        self.phase=object.__new__(PhaseFixtureReader);self.phase.run=RUN;self.phase.area='create';self.phase.fixture_url=URL;self.phase.read=lambda:deepcopy(self.active)
        # This test begins after the independently tested real original marker
        # admission. Only that coordinator seam is replaced, never product state.
        self.marker=object.__new__(PreparedCreateMarker);self.marker._binding=BINDING;self.marker._run=RUN;self.marker._fixture=URL
        self.marker._admission=dict(marker=deepcopy(self.product.marker))
        self.world=object.__new__(CreateWorldInput);self.world.tap=self.product.touch
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def owner(self):
        def store(name):return PrivateFeatureState(self.root/name)
        inputs=CreateActionOwner(store('ios-create-inputs.json'),self.lock,BINDING,RUN,URL,lambda:True)
        cleanup=CreateActionOwner(store('ios-create-cleanup-inputs.json'),self.lock,BINDING,RUN,URL,lambda:True)
        files=OwnedCreateFiles(self.file_boundary.native(),store('ios-create-files.json'),BINDING,RUN,URL,lock=self.lock)
        return CreateActions(store('ios-create-actions.json'),self.lock,BINDING,RUN,URL,lambda:True,source=self.source,work=self.work,scripts_root=SCRIPTS_ROOT,
            ui=self.ui,normal=self.normal,inputs=inputs,cleanup_inputs=cleanup,files=files,rez=self.rez,phase=self.phase,geometry=self.geometry,
            world_factory=lambda ticket:self.world,marker_scope=self.marker,monotonic=lambda:self.product.clock,sleep=self.product.sleep)
    def query(self,index):
        step=SCENARIOS['create']['steps'][index];ticket=hashlib.sha256(str(index).encode()).hexdigest()[:32]
        self.active=dict(ticket=ticket,afterEpochMs=EPOCH,verb=step['verb'],inputs=step['inputs'])
        return dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=URL,verb=step['verb'],inputs=deepcopy(step['inputs']))
    def test_normal_owned_position_uses_original_camera_and_ignored_edit_stays_owned(self):
        self.product.value['source']['view']['position']=[1,2,3]
        with self.held():
            owner=self.owner();owner.prepare();owner.act(self.query(0));owner.act(self.query(3))
            owned=owner.state['owned'][0]
            self.assertEqual([0,0,-4],next(row['position'] for row in owned['after']['source']['entities'] if row['id']==owned['id']))
            self.assertEqual([1,2,0],self.product.selected()['position'])
            owner.act(self.query(6));self.ui.position=lambda *_args:None
            with self.assertRaises(NativeUIError):owner.act(self.query(7))
            self.assertIsNotNone(owner.active_owned());self.assertEqual('acting',owner.state['calls'][-1]['phase'])

    def test_state4_restores_original_search_before_owned_delete_and_never_writes_hidden_field(self):
        draft=[''];self.product.search_original=lambda root:draft[0]
        writes=[]
        def replace(id_,value):
            self.assertTrue(self.product.page()['page']['selectedIds'],'A hidden search cannot receive ordinary input')
            self.assertEqual('create.property-search',id_);writes.append(value);draft[0]=value
        self.ui.replace=replace
        with self.held():
            owner=self.owner();owner.prepare();owner.act(self.query(0))
            owner.act(self.query(3));draft[0]='textures'
            owner.act(self.query(6))
            self.assertEqual([''],writes);self.assertEqual('',draft[0])
            self.assertEqual([],self.product.page()['page']['selectedIds'])
            owner.restore_editor();self.assertEqual([''],writes)
            draft[0]='actual surviving hidden draft'
            with self.assertRaises(NativeUIError):owner.restore_editor()
            self.assertEqual([''],writes)

    def test_all_21_actions_observe_actual_product_rows_and_original_file_io_then_restore(self):
        with self.held():
            owner=self.owner();owner.prepare();first_ticket=None
            for index,step in enumerate(SCENARIOS['create']['steps']):
                query=self.query(index);owner.act(query)
                actual=owner.read();observed=product.project(actual,RUN,[row['id'] for row in owner.state['owned']],voxel_baseline=owner.state['voxelBaseline'])
                self.assertEqual(step['state'],observed,query['verb'])
                if index==1:first_ticket=owner.files.state['ticket']
                if index==5:self.assertTrue((self.file_boundary.root/'export.json').exists())
                if index==9:self.assertEqual(first_ticket,owner.files.state['ticket'])
            self.assertEqual(5,len(owner.state['owned']));self.assertEqual(5,len(set(row['id'] for row in owner.state['owned'])))
            self.assertEqual(6,len([row for row in self.product.calls if row[0]=='create']))
            restored=owner.cleanup('f'*32);self.assertTrue(owner.cleanup_restored(restored));count=len(self.product.calls)
            owner.cleanup('f'*32);self.assertEqual(count,len(self.product.calls))
            reconstructed=self.owner();self.assertEqual(21,len(reconstructed.state['calls']));self.assertTrue(reconstructed.cleanup_restored(reconstructed.cleanup('f'*32)))
    def test_ignored_input_cannot_become_success_and_ticket_never_replays(self):
        with self.held():
            owner=self.owner();owner.prepare();owner.act(self.query(0));self.product.ignore=True;query=self.query(3)
            with self.assertRaises(NativeUIError):owner.act(query)
            self.assertEqual(1,len(self.product.calls));self.assertEqual([],owner.state['owned'])
            with self.assertRaises(CreateInputPending):self.owner().act(query)
            self.assertEqual(1,len(self.product.calls));owner.cleanup('f'*32)
    def test_lost_creation_return_adopts_actual_selected_uuid_only_for_cleanup_without_create_replay(self):
        with self.held():
            owner=self.owner();owner.prepare();owner.act(self.query(0));self.product.lose=True
            with self.assertRaises(NativeUIError):owner.act(self.query(3))
            self.assertEqual([],owner.state['owned']);owner.cleanup('f'*32)
            self.assertEqual(1,len(owner.state['owned']));self.assertTrue(owner.state['owned'][0]['deleted'])
            self.assertEqual(1,len([row for row in self.product.calls if row[0]=='create']))
    def test_foreign_editor_refuses_before_any_owned_state_or_input(self):
        with self.held():
            self.product.open();self.product.value['source']['tabletShown']=False;self.product.page()['active']=False
            with self.assertRaises(NativeUIError):self.owner().prepare()
            self.assertFalse((self.root/'ios-create-actions.json').exists());self.assertEqual([],self.product.calls)
    def test_unowned_semantic_change_refuses_before_further_input(self):
        with self.held():
            owner=self.owner();owner.prepare()
            # The underlying actual entity changes; no pending recipe may hide
            # that change by excluding all objects sharing a matching basename.
            self.product.value['source']['entities'][0]['position'][0]+=1
            with self.assertRaises(NativeUIError):owner.act(self.query(0))
    def test_cleanup_reservation_gap_and_finished_input_journal_recover_without_redelivery(self):
        with self.held():
            owner=self.owner();owner.prepare();owner.act(self.query(0))
            begin=owner.cleanup_inputs.begin
            def lose(query):raise NativeUIError('Crash before cleanup input reservation')
            owner.cleanup_inputs.begin=lose
            with self.assertRaises(NativeUIError):owner.cleanup('f'*32)
            self.assertEqual([],owner.cleanup_inputs.state['calls']);owner.cleanup_inputs.begin=begin
            reconstructed=self.owner();reconstructed.cleanup('f'*32)
            self.assertEqual('acknowledged',reconstructed.cleanup_inputs.state['calls'][0]['phase'])
            reconstructed.cleanup('f'*32)


if __name__=='__main__':unittest.main()
