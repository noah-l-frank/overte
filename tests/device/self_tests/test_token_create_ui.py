"""Create recipe counterexamples on a synthetic Qt boundary, never device evidence."""
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

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.token_create_ui import TokenCreateUI, metadata, snapshot, same_reference
from adapters.normal_create import NormalCreate
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from create_journey import INITIAL
from self_tests.test_normal_create_adapter import NativeCreate, BINDING, URL, NAME, UUID

ID=UUID.strip('{}')


class Controls:
    """Actual widget buffers and native world seam have separate state.

    Capture never sees the recipe's requested results or journal. Mutations
    apply only after original-reference admission; ACK-only mode consumes
    input without changing widget/world state.
    """
    def __init__(self,native):
        self.native=native;self.intents=[];self.inputs=[];self.tab=0;self.focus=None
        self.selected=[];self.texts={};self.indexes={'create.host':0,'create.import-host':0,'create.shape':0}
        self.sequence=0;self.generation=0;self.instance='a'*32;self.pid=21
        self.ignore=set();self.no_counter=False;self.enabled=True;self.covered=False
        self.scroll_position=0.0;self.hidden=None;self.ignore_scroll=False
        self.foreign_before=False;self.cached=None

    def capture(self):
        rows=[]
        def row(identifier,**extra):
            base=dict(id=identifier,enabled=self.enabled,focused=self.focus==identifier,inputReady=not self.covered)
            base.update(extra)
            source=[base,self.tab,self.selected,self.scroll_position]
            base['token']=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()[:32]
            rows.append(base)
        if self.native.tablet:
            row('tablet.home')
            if self.native.page!='create':row('create.entry')
            else:
                row('create.page',inputReady=False,profile='native-create-v1',tab=self.tab,
                    selectedIds=list(self.selected),statusError=False,statusText='',componentSourceSha256='d'*64)
                for n in range(5):row('create.tab.'+str(n))
                row('create.scrollbar',position=self.scroll_position,size=.2)
                ids={0:['create.host','create.shape','create.resource','create.new-shape','create.new-model','create.new-voxel'],
                     1:['create.refresh','create.filter'],
                     2:['create.name','create.apply','create.delete'] if self.selected else [],
                     3:[],4:['create.import-host','create.import-url','create.import-submit','create.import-browse']}[self.tab]
                if self.tab==1:
                    for entity in self.native.entities:
                        row('create.entity.'+entity['id'].strip('{}').lower(),entityId=entity['id'].strip('{}').lower())
                if self.tab==2 and self.selected:
                    ids += ['create.field.'+g+'.'+c for g,cs in [('position','xyz'),('rotation','xyz'),('dimensions','xyz'),('color',('red','green','blue'))] for c in cs]
                ids+=['create.undo','create.redo']
                for identifier in ids:
                    if identifier==self.hidden and self.scroll_position<.4:continue
                    if identifier in self.indexes:row(identifier,currentIndex=self.indexes[identifier],count=6 if identifier=='create.shape' else 2)
                    elif identifier in {'create.name','create.resource','create.import-url','create.filter'} or identifier.startswith('create.field.'):
                        row(identifier,text=self.texts.get(identifier,''))
                    else:row(identifier)
        value=dict(createControlsVersion=1,open=self.native.tablet,ready=self.native.tablet,
            scope=dict(instance=self.instance,generation=self.generation,sequence=self.sequence,
                       elapsedMs=int(self.native.clock*1000),processId=self.pid),controls=rows)
        self.cached=value
        return value

    def input(self,identifier,action,reference,value=None):
        if self.foreign_before:self.selected=['22222222-2222-2222-2222-222222222222']
        original=same_reference(reference,self.capture(),identifier)
        if not self.intents:raise AssertionError('input preceded intent')
        intent=self.intents[-1]
        if intent['scope']!=reference['scope'] or intent['controlToken']!=original['token']:raise AssertionError('intent retargeted')
        self.inputs.append((identifier,action))
        if not self.no_counter:self.sequence+=1
        if identifier in self.ignore:return
        if action=='replace':self.texts[identifier]=value;return
        if action=='select-index':self.indexes[identifier]=value;return
        if action=='scroll':
            if not self.ignore_scroll:self.scroll_position=round(max(0,min(.8,self.scroll_position+(.2 if value=='down' else -.2))),2)
            return
        self.focus=identifier
        if identifier=='tablet.home':self.native.page='home'
        elif identifier=='create.entry':self.native.open_create()
        elif identifier.startswith('create.tab.'):
            self.tab=int(identifier.rsplit('.',1)[1]);self.scroll_position=0
        elif identifier=='create.new-shape':
            if self.indexes['create.host']!=1:raise AssertionError('domain creation attempted')
            self.native.create_cube();self.tab=2
            if self.native.entities:self.selected=[self.native.entities[-1]['id'].strip('{}').lower()]
        elif identifier.startswith('create.entity.'):
            actual=next(entity['id'] for entity in self.native.entities if entity['id'].strip('{}').lower()==identifier[len('create.entity.'):])
            self.native.select_entity(actual);self.selected=[actual.strip('{}').lower()];self.tab=2
            self.texts['create.name']=self.native.selected['name']
        elif identifier=='create.apply':
            self.native.name_entity(self.texts.get('create.name',''));self.native.edit_properties({})
        elif identifier=='create.delete':
            self.native.delete_entity()
            if not self.native.ignored_delete:self.selected=[]
        elif identifier in {'create.undo','create.redo'}:self.native.history(identifier.rsplit('.',1)[1])
        elif identifier=='create.import-submit':
            if self.indexes['create.import-host']!=1:raise AssertionError('domain import attempted')
            self.native.import_entities(self.texts['create.import-url'])

    def activate(self,identifier,*,reference):self.input(identifier,'activate',reference)
    def replace(self,identifier,value,*,reference):self.input(identifier,'replace',reference,value)
    def select_index(self,identifier,value,*,reference):self.input(identifier,'select-index',reference,value)
    def scroll(self,identifier,value,*,reference):self.input(identifier,'scroll',reference,value)


class TokenCreateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();os.chmod(self.temp.name,0o700)
        self.native=NativeCreate(self.temp.name);self.io=Controls(self.native)
        self.ui=TokenCreateUI(self.io,self.io.intents.append,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.store=PrivateFeatureState(Path(self.temp.name)/'create.json')
        self.scripts=NormalScriptManager(self.native,self.native.observe,self.native.store,BINDING,
            source_kind='create-observer',monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.flow=NormalCreate(self.ui,self.scripts,self.store,BINDING)
    def tearDown(self):self.temp.cleanup()
    def open(self):self.flow.invoke('create.reference.open',{'scriptUrl':URL})
    def cube(self):self.flow.invoke('create.cube',{'name':NAME,'properties':INITIAL})
    def close(self):self.flow.invoke('create.reference.close',{'scriptUrl':URL})

    def test_real_recipe_composes_existing_create_owner_and_independent_observer(self):
        self.open();self.cube()
        self.assertEqual(NAME,self.native.entities[0]['name'])
        self.assertTrue(any(action=='select-index' for _,action in self.io.inputs))
        self.assertTrue(any(action=='replace' for _,action in self.io.inputs))
        self.close();self.assertEqual([],self.native.entities)
        self.assertIsNone(self.store.read());self.assertIsNone(self.native.store.read())
        self.assertTrue(self.io.intents)
        self.assertTrue(all(set(i)=={'createInputVersion','action','controlId','controlToken','scope'} for i in self.io.intents))
        self.assertNotIn(NAME,json.dumps(self.io.intents))

    def test_ignored_create_consumes_input_but_fails_and_is_not_replayed(self):
        self.open();self.native.ignored_create=True
        with self.assertRaises(NativeUIError):self.cube()
        self.assertIsNotNone(self.store.read()['pendingBeforeIds'])
        before=self.native.clock;self.close()
        self.assertGreaterEqual(self.native.clock-before,3)
        self.assertEqual(1,self.native.calls.count('create-cube'))

    def test_uncertain_shape_is_recovered_by_measured_uuid_without_replay(self):
        self.open();self.native.partial_create=True
        with self.assertRaises(NativeUIError):self.cube()
        self.assertEqual('',self.native.entities[0]['name']);self.close()
        self.assertEqual([],self.native.entities);self.assertEqual(1,self.native.calls.count('create-cube'))

    def test_widget_name_readback_cannot_replace_independent_entity_measurement(self):
        self.open();self.native.ignore_name=True
        with self.assertRaises(NativeUIError):self.cube()
        self.assertEqual(NAME,self.io.texts['create.name'])
        self.assertEqual('',self.native.entities[0]['name']);self.close()
        self.assertEqual([],self.native.entities)

    def test_ignored_delete_retains_owner_and_running_observer(self):
        self.open();self.cube();self.native.ignored_delete=True
        with self.assertRaises(NativeUIError):self.close()
        self.assertIsNotNone(self.store.read());self.assertNotIn('stop',self.native.calls)

    def test_foreign_selected_context_is_refused_before_input(self):
        self.open();before=len(self.io.inputs);self.io.foreign_before=True
        with self.assertRaises(NativeUIError):self.ui.tab(0)
        self.assertEqual(before,len(self.io.inputs))

    def test_ignored_text_choice_and_tab_fail_on_actual_widget_readback(self):
        for identifier,operation in [('create.host',lambda:self.ui.choose('create.host',1)),
                                     ('create.resource',lambda:self.ui.replace('create.resource','resource')),
                                     ('create.tab.4',lambda:self.ui.tab(4))]:
            with self.subTest(identifier=identifier):
                self.native.tablet=True;self.native.page='create';self.io.tab=0
                self.io.ignore={identifier}
                with self.assertRaises(NativeUIError):operation()
                self.assertFalse(self.native.entities)

    def test_ack_without_consumed_native_input_fails(self):
        self.open();self.io.no_counter=True
        with self.assertRaises(NativeUIError):self.ui.tab(0)

    def test_disabled_covered_missing_and_failed_intent_refuse_mutation(self):
        self.open()
        for setting in ('enabled','covered'):
            setattr(self.io,setting,setting=='covered');before=len(self.io.inputs)
            with self.assertRaises(NativeUIError):self.ui.tab(0)
            self.assertEqual(before,len(self.io.inputs));setattr(self.io,setting,setting=='enabled')
        def failed(_):raise NativeUIError('journal unavailable')
        self.ui.intent=failed;before=len(self.io.inputs)
        with self.assertRaises(NativeUIError):self.ui.tab(0)
        self.assertEqual(before,len(self.io.inputs))

    def test_reveal_uses_normal_scroll_and_requires_directional_position_change(self):
        self.open();self.io.hidden='create.resource';self.ui.replace('create.resource','resource')
        self.assertEqual('resource',self.io.texts['create.resource'])
        self.assertEqual(2,sum(action=='scroll' for _,action in self.io.inputs))
        self.io.scroll_position=0;self.io.ignore_scroll=True
        with self.assertRaises(NativeUIError):self.ui.replace('create.resource','other')
        self.assertEqual('resource',self.io.texts['create.resource'])

    def test_original_reference_expiry_replacement_and_mutable_template(self):
        self.open();before=self.ui.capture();self.io.cached['controls'].clear()
        self.assertTrue(before['controls'])
        current=self.io.capture();same_reference(before,current,'create.tab.0')
        for key,value in [('instance','f'*32),('generation',1),('sequence',999),('processId',999),('elapsedMs',5001)]:
            altered=deepcopy(current);altered['scope'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):same_reference(before,altered,'create.tab.0')
        changed=deepcopy(current);next(r for r in changed['controls'] if r['id']=='create.tab.0')['token']='f'*32
        with self.assertRaises(NativeUIError):same_reference(before,changed,'create.tab.0')

    def test_native_process_counter_and_clock_regressions_are_refused(self):
        self.open();self.ui.tab(0);self.ui.capture()
        for key,value in [('instance','f'*32),('pid',999),('sequence',0),('generation',-1)]:
            old=getattr(self.io,key);setattr(self.io,key,value)
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.ui.capture()
            setattr(self.io,key,old)
        self.native.clock=2;self.ui.capture();self.native.clock=1
        with self.assertRaises(NativeUIError):self.ui.capture()

    def test_strict_metadata_rejects_missing_unknown_nil_and_false_types(self):
        self.open();value=self.ui.capture();page=next(r for r in value['controls'] if r['id']=='create.page')
        for changes in [{'profile':'invented'},{'selectedIds':['00000000-0000-0000-0000-000000000000']},
                        {'tab':True},{'statusText':'secret\ntext'},{'componentSourceSha256':None},{'inputReady':True},{'future':1}]:
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):metadata(page|changes)
        missing=deepcopy(page);del missing['statusError']
        with self.assertRaises(NativeUIError):metadata(missing)
        for changes in [{'createControlsVersion':True},{'scope':value['scope']|{'instance':'0'*32}},
                        {'controls':value['controls']+[page]}]:
            with self.assertRaises(NativeUIError):snapshot(value|changes)

    def test_unresolved_import_never_becomes_empty_successful_cleanup(self):
        self.open();self.native.ignore_import=True
        with self.assertRaises(NativeUIError):self.flow.invoke('create.import',{'url':URL.replace('observer.js','entities.json')})
        with self.assertRaises(NativeUIError):self.close()
        self.assertIsNotNone(self.store.read()['pendingImportBeforeIds']);self.assertNotIn('stop',self.native.calls)

    def test_ios_fixture_admits_only_closed_original_token_activation(self):
        from fixture.serve import FixtureState
        fixture=FixtureState()
        request=dict(schemaVersion=1,commandId='11111111-1111-4111-8111-111111111111',
            instance='22222222-2222-4222-8222-222222222222',sequence=1,observedElapsedMs=0,
            fieldToken='33333333-3333-4333-8333-333333333333',operation='activate')
        outer=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='normal-ui-input',operation='edit',input=request)
        self.assertEqual(outer,fixture.set_client_command(outer))
        for changes in ({'sequence':True},{'operation':'create-direct'},{'text':'unexpected'},
                        {'expected':{}},{'fieldToken':'00000000-0000-0000-0000-000000000000'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):fixture.set_client_command(outer|{'input':request|changes})

    def test_owned_json_import_is_measured_and_removed_by_existing_owner(self):
        self.open();self.flow.invoke('create.import',{'url':URL.replace('observer.js','entities.json')})
        self.assertEqual(2,len(self.native.entities));self.close();self.assertEqual([],self.native.entities)


if __name__=='__main__':unittest.main()
