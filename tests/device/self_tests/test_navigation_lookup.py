"""Original scoped Pico input/protocol; native Qt/VR/QObject seams synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_navigation_panels import NativeNavigationPanels
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import PicoNavigation,NavigationError
from adapters.pico4.navigation_lookup import PicoNavigationLookup,packet
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.token_script_ui import TokenScriptUI
from self_tests.test_pico_graphics_surface import Boundary,IDENTITY

RUN='a'*32;MISSING='hifi://hidden-'+RUN
HOME='7'*32;ADDRESS='9'*32
HOME_SHA=hashlib.sha256(b'qrc:/hifi/tablet/TabletHome.qml').hexdigest()
ADDRESS_SHA=hashlib.sha256(b'qrc:/hifi/tablet/TabletAddressDialog.qml').hexdigest()


class Source(Boundary):
    def __init__(self):
        super().__init__();self.opened=True;self.text='';self.native_sequence=0;self.native=None
        self.root_born=None;self.extra_roots=[];self.panel_edit=None;self.wire_version=2;self.flag=True
    def snapshot(self):
        value=super().snapshot()
        if self.flag:value['navigationLookupControlsVersion']=1
        return value
    def observe(self,request):
        self.native_sequence+=1;roots=deepcopy(self.extra_roots);home=address=None
        if self.page=='address':
            if self.root_born is None:self.root_born=self.epoch
            address=dict(rootId=ADDRESS,sourceSha256=ADDRESS_SHA,textSha256=hashlib.sha256(self.text.encode()).hexdigest(),
                textLength=len(self.text),focused=self.focused,inputReady=self.focused,visible=self.opened)
        if self.root_born is not None:
            roots.append(dict(rootId=ADDRESS,profile='pico-address-v1',sourceSha256=ADDRESS_SHA,firstObservedEpochMs=self.root_born,
                alive=self.page=='address',inCurrentTree=self.page=='address',visible=self.page=='address' and self.opened))
        if self.page=='home':home=dict(rootId=HOME,sourceSha256=HOME_SHA,pageIndex=self.page_number-1,pageCount=2,visible=self.opened)
        self.native=dict(navigationPanelsVersion=self.wire_version,commandId=request['commandId'],runId=request['runId'],instance='f'*32,
            sequence=self.native_sequence,processId=self.pid,capturedEpochMs=self.epoch,complete=True,roots=roots,
            ui=dict(bridgeId=self.bridge,generation=self.generation,sequence=self.sequence,elapsedMs=round(self.clock*1000),
                observedEpochMs=self.epoch,open=self.opened,ready=self.opened))
        if self.wire_version==2:self.native['lookup']=dict(complete=True,home=home,address=address)
        if self.panel_edit:self.panel_edit(self.native)
    def panels(self):
        return NativeNavigationPanels(self.observe,lambda:json.dumps(self.native),lambda:self.epoch,self.guard,self.pid,
            monotonic=lambda:self.clock,sleep=self.sleep)


class NavigationLookupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.native=Source();self.hook=None
        self.navigation=PicoNavigation(self.native,self.root/'normal.json',IDENTITY,'31:synthetic-start','http://controlled.invalid/scene.json',
            monotonic=lambda:self.native.clock,sleep=self.native.sleep,address_authority=lambda value:value==MISSING)
        self.normal=TokenScriptUI(PicoScriptIO(self.navigation),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.store=PrivateFeatureState(self.root/'intent.json');self.controls=PicoNavigationLookup(self.normal,self.native.panels(),self.intent,RUN)
    def intent(self,value):
        self.store.write(value,self.store.read());self.native.intents.append(dict(control=value['controlId']))
        if self.hook:self.hook()
    def input(self,control,action='activate',text=None):
        return self.controls.input(control,action,original=self.controls.capture(),text=text)
    def address(self):self.native.page_number=2;self.input('navigation.goto')
    def test_normal_page_goto_focus_replace_submit_preserve_original_root_and_typed_missing_url(self):
        before=self.controls.capture();self.assertEqual(0,before['native']['lookup']['home']['pageIndex'])
        after=self.controls.input('tablet.page.2',original=before);self.assertEqual(1,after['native']['lookup']['home']['pageIndex'])
        after=self.input('navigation.goto');self.assertEqual(ADDRESS,after['native']['lookup']['address']['rootId'])
        self.input('navigation.address');self.input('navigation.address','replace',MISSING)
        value=self.controls.capture();self.assertEqual(hashlib.sha256(MISSING.encode()).hexdigest(),value['native']['lookup']['address']['textSha256'])
        after=self.controls.input('navigation.address','submit',original=value)
        self.assertEqual([MISSING],self.native.entered);self.assertFalse(after['open'])
        self.assertFalse(after['native']['roots'][0]['alive']);self.assertIsNone(after['native']['lookup']['address'])
        self.assertEqual(['tablet.page.2:activate','navigation.goto:activate','navigation.address:activate','navigation.address:replace','navigation.address:submit'],
            [v for v in self.native.events if not v.startswith('intent:')])
        self.assertEqual(5,len(self.native.inputs));self.assertEqual('submit',self.store.read()['action'])
    def test_legacy_source_or_missing_opt_in_refuses_before_scoped_input(self):
        for fault in ('v1','flag'):
            self.setUp()
            if fault=='v1':self.native.wire_version=1
            else:self.native.flag=False
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,NavigationError)):self.input('tablet.page.2')
            self.assertFalse(self.native.inputs);self.assertIsNone(self.store.read())
    def test_foreign_native_frame_generation_counter_bridge_or_address_hash_never_authorizes_input(self):
        for fault in ('bridge','generation','counter','open','hash','unavailable'):
            self.setUp()
            if fault=='hash':self.address()
            count=len(self.native.inputs)
            def changed(value):
                if fault in ('bridge','generation'):value['ui']['bridgeId' if fault=='bridge' else 'generation']='8'*32
                elif fault=='counter':value['ui']['sequence']+=1
                elif fault=='open':value['ui'].update(open=False,ready=False)
                elif fault=='hash':value['lookup']['address']['textSha256']='8'*64
                else:value['lookup']['complete']=False
            self.native.panel_edit=changed
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,NavigationError)):
                self.input('navigation.address' if fault=='hash' else 'tablet.page.2')
            self.assertEqual(count,len(self.native.inputs))
    def test_changed_page_draft_token_or_candidate_after_intent_refuses_before_delivery(self):
        for fault in ('page','draft','candidate'):
            self.setUp()
            if fault=='draft':self.address();self.input('navigation.address')
            count=len(self.native.inputs)
            def changed():
                if fault=='page':self.native.page_number=2;self.native.revision+=1
                elif fault=='draft':self.native.text='foreign';self.native.revision+=1
                else:self.native.okay=False
            self.hook=changed
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,NavigationError)):
                self.input('navigation.address','replace',MISSING) if fault=='draft' else self.input('tablet.page.2')
            self.assertIsNotNone(self.store.read());self.assertEqual(count,len(self.native.inputs))
    def test_new_retained_root_between_original_and_current_reference_cannot_be_ignored(self):
        before=self.controls.capture();self.native.extra_roots=[dict(rootId='8'*32,profile='pico-places-v1',sourceSha256='6'*64,
            firstObservedEpochMs=self.native.epoch,alive=True,inCurrentTree=False,visible=False)]
        with self.assertRaises(NativeUIError):self.controls.input('tablet.page.2',original=before)
        self.assertFalse(self.native.inputs);self.assertIsNone(self.store.read())
    def test_unowned_url_unfocused_field_and_changed_submit_text_refuse_without_mutation(self):
        self.address();count=len(self.native.inputs)
        with self.assertRaises(NativeUIError):self.input('navigation.address','replace',MISSING)
        self.input('navigation.address');count=len(self.native.inputs)
        with self.assertRaises(NativeUIError):self.input('navigation.address','replace','hifi://foreign')
        self.assertEqual(count,len(self.native.inputs));self.input('navigation.address','replace',MISSING)
        count=len(self.native.inputs);self.native.text='hifi://foreign';self.native.revision+=1
        with self.assertRaises((NativeUIError,NavigationError)):self.input('navigation.address','submit')
        self.assertEqual(count,len(self.native.inputs));self.assertFalse(self.native.entered)
    def test_lost_native_receipt_retains_original_intent_without_a_second_send(self):
        self.native.fault='lost-return'
        with self.assertRaises((NativeUIError,NavigationError)):self.input('tablet.page.2')
        self.assertEqual(1,len(self.native.inputs));self.assertEqual('tablet.page.2',self.store.read()['controlId'])
    def test_scoped_backend_rejects_stale_elapsed_counter_pid_and_missing_capability(self):
        before=self.controls.capture();row=next(r for r in before['controls'] if r['id']=='tablet.page.2')
        for fault in ('elapsed','counter','pid','flag'):
            expected=deepcopy(before['scope']);self.native.flag=True
            if fault=='elapsed':self.native.clock=6
            elif fault=='counter':expected['sequence']+=1
            elif fault=='pid':expected['processId']+=1
            else:self.native.flag=False
            with self.subTest(fault=fault),self.assertRaises(NavigationError):
                self.navigation.input('tablet.page.2',token=row['token'],expected_scope=expected)
            self.native.clock=0
        self.assertFalse(self.native.inputs)
    def test_v2_native_shape_preserves_unready_home_and_rejects_aliases_or_unmatched_address(self):
        before=self.controls.capture();native=deepcopy(before['native'])
        from adapters.native_navigation_panels import validate,command
        request=command(dict(schemaVersion=1,commandId=native['commandId'],action='feature-navigation-panels',runId=RUN))
        native['lookup']['home'].update(pageIndex=-1,pageCount=0);validate(native,request,31,20000)
        for edit in (lambda v:v['lookup']['home'].update(pageIndex=True),lambda v:v['lookup']['home'].update(pageIndex=0),
            lambda v:v['lookup'].update(complete=1),lambda v:v.update(navigationPanelsVersion=1),
            lambda v:v['lookup'].update(address=dict(rootId=ADDRESS,sourceSha256=ADDRESS_SHA,textSha256='0'*64,textLength=0,
                focused=False,inputReady=False,visible=False))):
            bad=deepcopy(native);edit(bad)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(bad,request,31,20000)
    def test_live_native_reader_cannot_switch_producer_version(self):
        source=self.native.panels();source.read(RUN);self.native.wire_version=1
        with self.assertRaises(NativeUIError):source.read(RUN)
    def test_original_android_qml_submit_hides_address_and_skips_standalone_warning(self):
        root=Path(__file__).resolve().parents[3]
        text=(root/'interface/resources/qml/hifi/tablet/TabletAddressDialog.qml').read_text()
        function=text[text.index('    function toggleOrGo('):text.rfind('\n}')]
        program=r'''
let loads=[],hides=0,timers=0,writes=[];const addressLine={text:'hifi://hidden-'+ 'a'.repeat(32)};
const addressBarDialog={loadAddress:(...args)=>loads.push(args)},clearAddressLineTimer={start:()=>timers++};
const DialogsManager={hideAddressBar:()=>hides++},PlatformInfo={isStandalone:()=>false};
const Settings={getValue:()=>true,setValue:(...args)=>writes.push(args)},unoptimizedDomain={visible:false};
SOURCE
toggleOrGo(addressLine.text,false,false);
if(loads.length!==1||hides!==1||timers!==1||unoptimizedDomain.visible||writes.length)throw Error('Original Android path changed');
PlatformInfo.isStandalone=()=>true;toggleOrGo(addressLine.text,false,false);
if(loads.length!==1||!unoptimizedDomain.visible)throw Error('Original standalone warning was bypassed');
'''.replace('SOURCE',function)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)
    def test_actual_private_pico_factory_retains_normal_manager_and_original_native_reader(self):
        root=Path(__file__).resolve().parents[3]
        import sys
        sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as n
        fixture=n.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups);adapter=fixture.instance()
        adapter._scripts=lambda target:SimpleNamespace(ui=self.normal)
        adapter._navigation_panels=lambda target:self.native.panels()
        controls=adapter._navigation_lookup_controls('owned',self.intent,RUN)
        controls.input('tablet.page.2',original=controls.capture());self.assertEqual(1,len(self.native.inputs))


if __name__=='__main__':unittest.main()
