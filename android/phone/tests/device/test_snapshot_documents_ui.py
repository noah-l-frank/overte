"""Synthetic PackageManager/SDK/OS seams; no device picker is run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import shlex
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUI,NativeUIError
from overte_phone_snapshot_documents_ui import SnapshotDocumentResolution,SnapshotDocumentContext,PhoneSnapshotDocumentsUI,RESOLVE
from overte_phone_snapshot_system_ui import PRIMARY,RECEIVER_COMPONENT,LABEL
from test_snapshot_system_context import BINDING

PACKAGE='com.android.documentsui';COMPONENT=PACKAGE+'/'+PACKAGE+'.picker.PickActivity';NAME='e2e-'+('a'*32)+'-actual_native_capture.png'


class Boundary:
    def __init__(self):
        self.current=COMPONENT;self.epoch=20000;self.clock=0.;self.calls=[];self.inputs=[];self.intents=[]
        self.stage='recent';self.okay=True;self.ignored=False;self.fault=lambda raw:raw;self.changed=False
        self.ui=NativeUI(self,'owned',lambda:self.okay,monotonic=lambda:self.clock,sleep=self.sleep)
        self.flow=PhoneSnapshotDocumentsUI(self.ui,self.intent,lambda:self.epoch,COMPONENT)
    def sleep(self,value):self.clock+=value
    def intent(self,value):
        self.intents.append(deepcopy(value))
        if self.changed:self.current='foreign.app/foreign.app.Window'
        return True
    def node(self,**attrs):
        row=dict(package=self.current.split('/')[0],enabled='true',clickable='true',displayed='true',bounds='[10,10][200,80]')|attrs
        return '<node '+' '.join(key+'="'+value+'"' for key,value in row.items())+'/>'
    def xml(self):
        if self.stage=='recent':inner=self.node(**{'resource-id':'android:id/home'})
        elif self.stage=='drawer':inner=self.node(text=LABEL)
        else:inner=self.node(text=LABEL,**{'resource-id':PACKAGE+':id/toolbar_title'})+self.node(text=NAME,**{'resource-id':'android:id/title','class':'android.widget.EditText'})+self.node(text='Save',**{'resource-id':PACKAGE+':id/action_menu_save'})
        return self.fault('<hierarchy>'+inner+'</hierarchy>')
    def call(self,method,path,body=None):
        self.calls.append((method,path,deepcopy(body)))
        if path.endswith('/current_package'):return self.current.split('/')[0]
        if path.endswith('/current_activity'):return self.current.split('/')[1]
        if path.endswith('/source'):return self.xml()
        if method=='DELETE' and path.endswith('/actions'):return None
        if method=='POST':
            self.inputs.append((path,deepcopy(body)))
            if not self.ignored:
                if path.endswith('/back'):self.current=PRIMARY+'/'+PRIMARY+'.MainActivity'
                elif path.endswith('/actions'):
                    if self.stage=='recent':self.stage='drawer'
                    elif self.stage=='drawer':self.stage='root'
                    else:self.current=PRIMARY+'/'+PRIMARY+'.MainActivity'
                else:raise AssertionError(path)
            return {'accepted':True}
        raise AssertionError((method,path))
    def resolve(self):
        class PM:
            def execute(_self,args,*,target,timeout):
                self.calls.append((args,target,timeout));command=shlex.split(args[1])
                return COMPONENT if tuple(command)==RESOLVE else 'package:'+PACKAGE+' uid:10042'
        return SnapshotDocumentResolution(PM(),'explicit-synthetic',lambda:self.okay,lambda:self.epoch,monotonic=lambda:self.clock).read()
    def scope(self):
        value=dict(binding=deepcopy(BINDING),foreground=False,running=True,appState=3)
        return SnapshotDocumentContext(BINDING,self.resolve(),lambda:deepcopy(value),lambda:self.current,lambda:self.okay,monotonic=lambda:self.clock)


class SnapshotDocumentsUiTests(unittest.TestCase):
    def test_actual_resolution_uses_create_document_openable_png_and_no_launch(self):
        b=Boundary();value=b.resolve();self.assertEqual(COMPONENT,value['component']);self.assertEqual(10042,value['uid'])
        self.assertEqual(RESOLVE,tuple(shlex.split(b.calls[0][0][1])));self.assertEqual(3,len(b.calls));self.assertEqual([],b.inputs)
    def test_normal_drawer_root_filename_save_and_cancel_are_only_sdk_input(self):
        b=Boundary();b.flow.select_root();self.assertEqual('root',b.stage);result=b.flow.save(NAME)
        self.assertTrue(result['component'].startswith(PRIMARY+'/'));self.assertNotIn('saved',result)
        self.assertEqual(['document-show-roots','document-select-owned-root','document-save'],[row['action'] for row in b.intents])
        self.assertEqual(3,len(b.inputs));self.assertEqual(3,len([row for row in b.calls if row[0]=='DELETE']))
        b=Boundary();result=b.flow.cancel();self.assertTrue(result['component'].startswith(PRIMARY+'/'));self.assertEqual(1,len(b.inputs))
    def test_ignored_root_save_cancel_ack_never_qualifies_or_replays_input(self):
        for operation in ('root','save','cancel'):
            b=Boundary();b.ignored=True
            if operation=='root':b.stage='drawer'
            if operation=='save':b.stage='root'
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):
                b.flow.select_root() if operation=='root' else b.flow.save(NAME) if operation=='save' else b.flow.cancel()
            self.assertEqual(1,len(b.inputs));self.assertLessEqual(b.clock,5.01)
    def test_foreign_document_name_or_root_duplicate_disabled_button_cannot_save(self):
        for fault in ('name','root','duplicate','disabled','foreign'):
            b=Boundary();b.stage='root'
            def mutate(raw):
                if fault=='name':return raw.replace(NAME,'foreign.png')
                if fault=='root':return raw.replace(LABEL,'Other provider')
                if fault=='disabled':return raw.replace('enabled="true"','enabled="false"')
                if fault=='foreign':return raw.replace('package="'+PACKAGE+'"','package="foreign.app"')
                return raw.replace('</hierarchy>',b.node(text='Save',**{'resource-id':PACKAGE+':id/action_menu_save'})+'</hierarchy>')
            b.fault=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.flow.save(NAME)
            self.assertEqual([],b.inputs)
    def test_changed_window_after_intent_and_lost_ownership_prevent_input(self):
        for fault in ('window','guard','slow'):
            b=Boundary();b.stage='root'
            if fault=='window':b.changed=True
            elif fault=='guard':b.okay=False
            else:
                original=b.intent
                def slow(value):b.epoch+=1600;return original(value)
                b.flow.intent=slow
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.flow.save(NAME)
            self.assertEqual([],b.inputs)
    def test_document_scope_cannot_adopt_share_receiver_or_other_activity(self):
        b=Boundary();scope=b.scope();self.assertTrue(scope.guard())
        for current in (RECEIVER_COMPONENT,PACKAGE+'/'+PACKAGE+'.OtherActivity','foreign.app/foreign.app.Window'):
            b.current=current
            with self.subTest(current=current),self.assertRaises(NativeUIError):scope.guard()
    def test_foreign_or_ambiguous_root_does_not_authorize_touch(self):
        for fault in ('missing','duplicate','disabled'):
            b=Boundary();b.stage='drawer'
            def mutate(raw):
                if fault=='missing':return raw.replace(LABEL,'Foreign')
                if fault=='disabled':return raw.replace('enabled="true"','enabled="false"')
                return raw.replace('</hierarchy>',b.node(text=LABEL)+'</hierarchy>')
            b.fault=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.flow.select_root()
            self.assertEqual([],b.inputs)


if __name__=='__main__':unittest.main()
