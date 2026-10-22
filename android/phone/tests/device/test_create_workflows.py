"""Normal Create recipe counterexamples on independent synthetic widgets.

These fixtures own actual widget buffers only. They return no entity, file,
image, permission, lifecycle or cleanup verdicts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import TokenCreateUI,CHOICES,field,same_reference,metadata

RUN='b'*32
ID='12345678-1234-4234-8234-123456789abc'
PATH='/private/feature-create-'+RUN+'/'


class Widgets:
    def __init__(self):
        self.clock=0.;self.tab=0;self.selected=[];self.sequence=0;self.focus=None;self.dialog=None
        self.texts={};self.choices={key:0 for key in CHOICES};self.checked=False
        self.inputs=[];self.intents=[];self.ignore=set();self.no_counter=False;self.before=None
    def capture(self):
        rows=[]
        def row(identifier,**extra):
            value=dict(id=identifier,enabled=True,focused=self.focus==identifier,inputReady=True)|extra
            value['token']=hashlib.sha256(json.dumps([value,self.tab,self.selected],sort_keys=True).encode()).hexdigest()[:32]
            rows.append(value)
        row('create.page',inputReady=False,profile='native-create-v1',tab=self.tab,selectedIds=list(self.selected),
            statusError=False,statusText='',componentSourceSha256='a'*64)
        for n in range(5):row('create.tab.'+str(n))
        ids={0:['create.host','create.shape','create.resource','create.new-shape','create.new-model','create.new-voxel'],
             1:['create.refresh'],2:['create.name','create.apply','create.apply-typed','create.textures','create.property-filter'],
             3:['create.export','create.edit-mode','create.voxel-shape','create.voxel-dynamics','create.voxel-pointer',
                'create.voxel-remove','create.voxel-diameter','create.voxel-reach','create.voxel-apply'],
             4:['create.import-host','create.import-browse']}[self.tab]
        if self.tab==2:ids+=['create.field.'+group+'.'+axis for group in ('position','dimensions') for axis in 'xyz']
        for identifier in ids:
            if identifier in CHOICES:row(identifier,currentIndex=self.choices[identifier],count=CHOICES[identifier])
            elif identifier=='create.voxel-remove':row(identifier,checked=self.checked)
            elif field(identifier):row(identifier,text=self.texts.get(identifier,''))
            else:row(identifier)
        if self.dialog is not None:
            for identifier in ('create-file.name','create-file.accept','create-file.cancel'):
                if identifier=='create-file.name':row(identifier,text=self.texts.get(identifier,''),picker=deepcopy(self.dialog))
                else:row(identifier,picker=deepcopy(self.dialog))
        return dict(createControlsVersion=1,open=True,ready=True,
            scope=dict(instance='a'*32,generation=1,sequence=self.sequence,elapsedMs=int(self.clock*1000),processId=31),controls=rows)
    def input(self,identifier,action,reference,value=None):
        if self.before:self.before()
        same_reference(reference,self.capture(),identifier)
        assert self.intents and self.intents[-1]['scope']==reference['scope']
        self.inputs.append((identifier,action,value))
        if not self.no_counter:self.sequence+=1
        if identifier in self.ignore:return
        if action=='replace':self.texts[identifier]=value;return
        if action=='select-index':self.choices[identifier]=value;return
        self.focus=identifier
        if identifier.startswith('create.tab.'):self.tab=int(identifier.rsplit('.',1)[1])
        elif identifier in ('create.new-model','create.new-voxel','create.new-shape'):self.selected=[ID];self.tab=2
        elif identifier in ('create.import-browse','create.export'):
            save=identifier=='create.export'
            self.dialog=dict(caption='Select Where to Save' if save else 'Select .json to Import',save=save,
                             directory='file:///private',error='',closing=False,pendingDocuments=False)
        elif identifier in ('create-file.cancel','create-file.accept'):self.dialog=None
        elif identifier=='create.voxel-remove':self.checked=not self.checked
    def activate(self,identifier,*,reference):self.input(identifier,'activate',reference)
    def replace(self,identifier,value,*,reference):self.input(identifier,'replace',reference,value)
    def select_index(self,identifier,value,*,reference):self.input(identifier,'select-index',reference,value)
    def sleep(self,delay):self.clock+=delay
    def recipe(self):return TokenCreateUI(self,self.intents.append,monotonic=lambda:self.clock,sleep=self.sleep)


class CreateWorkflowTests(unittest.TestCase):
    def test_model_creation_uses_resource_and_normal_host_choices_and_returns_only_ui_id(self):
        widgets=Widgets();ui=widgets.recipe();url='http://controlled.invalid/gltf-bundle/main.gltf'
        self.assertEqual([ID],ui.new_entity('model',resource=url))
        self.assertEqual(url,widgets.texts['create.resource']);self.assertEqual(0,widgets.choices['create.host'])
        self.assertEqual(1,len([row for row in widgets.inputs if row[0]=='create.new-model']))
        self.assertTrue(all(set(intent)=={'createInputVersion','action','controlId','controlToken','scope'} for intent in widgets.intents))
    def test_ignored_model_creation_is_not_a_success(self):
        widgets=Widgets();widgets.ignore.add('create.new-model')
        with self.assertRaises(NativeUIError):widgets.recipe().new_entity('model',resource='http://controlled.invalid/model.gltf')
        self.assertEqual([],widgets.selected)
    def test_ignored_model_url_and_host_do_not_reach_creation(self):
        for identifier,host in (('create.resource','domain'),('create.host','avatar')):
            widgets=Widgets();widgets.ignore.add(identifier)
            with self.assertRaises(NativeUIError):widgets.recipe().new_entity('model',host=host,resource='http://controlled.invalid/model.gltf')
            self.assertFalse(any(row[0]=='create.new-model' for row in widgets.inputs))
    def test_import_cancel_uses_actual_dialog_and_never_accepts(self):
        widgets=Widgets();ui=widgets.recipe();ui.open_import_picker();self.assertIsNotNone(widgets.dialog)
        ui.cancel_import_picker();self.assertIsNone(widgets.dialog)
        self.assertFalse(any(row[0]=='create-file.accept' for row in widgets.inputs))
    def test_import_accept_types_only_exact_owned_file_then_ordinary_select(self):
        widgets=Widgets();ui=widgets.recipe();ui.open_import_picker();ui.accept_import_picker(PATH+'entity-import.json')
        self.assertEqual(PATH+'entity-import.json',widgets.texts['create-file.name']);self.assertIsNone(widgets.dialog)
        self.assertEqual(1,len([row for row in widgets.inputs if row[0]=='create-file.accept']))
    def test_unowned_file_paths_cannot_reach_picker_input(self):
        for path in ('/private/entity-import.json',PATH+'../entity-import.json',PATH+'foreign.json',PATH+'selection.json'):
            widgets=Widgets();ui=widgets.recipe();ui.open_import_picker();before=len(widgets.inputs)
            with self.assertRaises(NativeUIError):ui.accept_import_picker(path)
            self.assertEqual(before,len(widgets.inputs))
    def test_ignored_cancel_and_select_do_not_prove_dialog_retirement(self):
        for identifier in ('create-file.cancel','create-file.accept'):
            widgets=Widgets();ui=widgets.recipe();ui.open_import_picker();widgets.ignore.add(identifier)
            with self.assertRaises(NativeUIError):
                if identifier.endswith('cancel'):ui.cancel_import_picker()
                else:ui.accept_import_picker(PATH+'entity-import.json')
            self.assertIsNotNone(widgets.dialog)
    def test_export_requires_actual_selection_and_uses_save_dialog(self):
        widgets=Widgets();ui=widgets.recipe()
        with self.assertRaises(NativeUIError):ui.export_selection(PATH+'selection.json')
        widgets.selected=[ID];ui.export_selection(PATH+'selection.json')
        self.assertEqual(PATH+'selection.json',widgets.texts['create-file.name'])
        self.assertEqual(1,len([row for row in widgets.inputs if row[0]=='create.export']))
        self.assertIsNone(widgets.dialog)
    def test_export_refuses_import_filename_without_opening_save(self):
        widgets=Widgets();widgets.selected=[ID]
        with self.assertRaises(NativeUIError):widgets.recipe().export_selection(PATH+'entity-import.json')
        self.assertEqual([],widgets.inputs)
    def test_voxel_tool_uses_original_choices_checkbox_and_size(self):
        widgets=Widgets();ui=widgets.recipe();ui.configure_voxel_remove()
        self.assertEqual(1,widgets.choices['create.edit-mode']);self.assertEqual(2,widgets.choices['create.voxel-shape'])
        self.assertTrue(widgets.checked);self.assertEqual('0.5',widgets.texts['create.voxel-diameter'])
        self.assertEqual('create.voxel-apply',widgets.inputs[-1][0])
    def test_voxel_ignored_checkbox_cannot_qualify_configuration(self):
        widgets=Widgets();widgets.ignore.add('create.voxel-remove')
        with self.assertRaises(NativeUIError):widgets.recipe().configure_voxel_remove()
        self.assertFalse(any(row[0]=='create.voxel-apply' for row in widgets.inputs))
    def test_texture_filter_and_original_typed_value_are_normal_inputs(self):
        widgets=Widgets();widgets.tab=2;widgets.selected=[ID];url='http://controlled.invalid/checker.png'
        widgets.recipe().texture(url)
        self.assertEqual('textures',widgets.texts['create.property-filter'])
        self.assertEqual({'checker.png':url},json.loads(widgets.texts['create.textures']))
        self.assertEqual('create.apply-typed',widgets.inputs[-1][0])
    def test_transform_uses_existing_property_fields_and_apply(self):
        widgets=Widgets();widgets.tab=2;widgets.selected=[ID]
        widgets.recipe().edit_transform(position=dict(x=1,y=2,z=-3),dimensions=dict(x=1,y=1,z=1))
        self.assertEqual('-3',widgets.texts['create.field.position.z']);self.assertEqual('create.apply',widgets.inputs[-1][0])
    def test_no_consumed_counter_refuses_even_an_acknowledged_actual_buffer(self):
        widgets=Widgets();widgets.no_counter=True
        with self.assertRaises(NativeUIError):widgets.recipe().open_import_picker()
    def test_foreign_reference_is_not_silently_retargeted(self):
        widgets=Widgets();ui=widgets.recipe();widgets.before=lambda:setattr(widgets,'selected',[ID])
        with self.assertRaises(NativeUIError):ui.open_import_picker()
        self.assertEqual([],widgets.inputs)
    def test_picker_metadata_refuses_false_types_and_mismatched_caption(self):
        widgets=Widgets();ui=widgets.recipe();ui.open_import_picker()
        for change in ({'save':True},{'closing':1},{'pendingDocuments':1},{'caption':'Open Script and Companion Files'}):
            value=deepcopy(widgets.capture());row=next(row for row in value['controls'] if row['id']=='create-file.name')
            row['picker'].update(change)
            with self.assertRaises(NativeUIError):metadata(row)


if __name__=='__main__':unittest.main()
