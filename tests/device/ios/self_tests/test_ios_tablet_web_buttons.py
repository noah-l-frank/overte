"""Actual host weak ownership and independently authored native button DTOs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
from pathlib import Path
import unittest
import uuid
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_buttons as source
from ios.self_tests import test_ios_avatar_scripts as scripts
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT


class Object:pass


class Boundary:
    def __init__(self):
        self.now=1700000000120;self.sequence=0;self.rows=[];self.controls=[];self.strong={};self.objects={};self.model=Object();self.tablet=Object()
        worker=scripts.packet()['source']['workers'][0];self.manager=deepcopy(worker['membership']);self.code=deepcopy(worker['code'])
        self.model_stamp=None;self.tablet_stamp=None
    def tick(self):self.now+=1;return dict(epochMs=self.now,monotonicMs=self.now-1700000000000)
    def add(self,verb='open',*,returned=True,qualified=True):
        item=Object();key=uuid.uuid4().hex;self.strong[key]=item;self.objects[key]=weakref.ref(item)
        who=dict(callerVersion=1,method='addButton',sequence=len(self.rows)+1,invokedEpochMs=self.tick()['epochMs'],manager=deepcopy(self.manager),code=deepcopy(self.code))
        if self.model_stamp is None:self.model_stamp=self.tick()
        inserted=self.tick()
        if returned and self.tablet_stamp is None:self.tablet_stamp=self.tick()
        row=dict(id=key,uuid=str(uuid.uuid4()),semanticId='tablet-web-app.'+RUN+'.'+'b'*32+'.'+verb,fixtureUrl=ROOT,caller=who if qualified else None,
            model='1'*32,tablet='2'*32 if returned else None,root='3'*32 if returned else None,inserted=inserted,returned=self.tick() if returned else None,
            removed=None,expired=None,alive=True,clicks=[])
        self.rows.append(row);return key
    def bind(self,key):
        item=Object();control=uuid.uuid4().hex;self.strong[control]=item;self.objects[control]=weakref.ref(item)
        row=dict(id=control,button=key,root='3'*32,born=self.tick(),expired=None,alive=True);self.controls.append(row)
        button=next(row for row in self.rows if row['id']==key);verb=source.SEMANTIC.fullmatch(button['semanticId'])[3]
        return dict(instance='4'*32,button=key,control=control,root='3'*32,rootInstance='5'*32,semanticId=button['semanticId'],uuid=button['uuid'],featureRun=RUN,fixtureUrl=ROOT,nonce='b'*32,verb=verb)
    def click(self,key):next(row for row in self.rows if row['id']==key)['clicks'].append(self.tick())
    def remove(self,key):
        next(row for row in self.rows if row['id']==key)['removed']=self.tick();self.strong.pop(key,None)
        for row in self.controls:
            if row['button']==key:self.strong.pop(row['id'],None)
        gc.collect()
    def snapshot(self):
        self.sequence+=1;before=self.tick()
        for row in self.rows+self.controls:
            if self.objects[row['id']]() is None and row['expired'] is None:row.update(expired=self.tick(),alive=False)
        return dict(iosTabletAppButtonsVersion=1,commandId='ios-'+format(self.sequence,'032x'),runId=RUN,fixtureUrl=ROOT,instance='4'*32,sequence=self.sequence,processId=31,
            clockDomain='native-main-ios-tablet-app-buttons',clockBefore=before,clockAfter=self.tick(),complete=True,rootInstance='5'*32,
            models=[dict(id='1'*32,born=self.model_stamp,expired=None,alive=True)] if self.rows else [],
            tablets=[dict(id='2'*32,born=self.tablet_stamp,expired=None,alive=True)] if any(row['returned'] for row in self.rows) else [],buttons=deepcopy(self.rows),controls=deepcopy(self.controls))
    def profile(self):
        return dict(engineInstance=self.manager['instance'],assignedUrl=self.manager['url'],loadGeneration=self.manager['loadGeneration'],assignedEpochMs=self.manager['assignedEpochMs'],code=self.code)


class TabletWebButtonTests(unittest.TestCase):
    def test_real_return_proxy_and_visual_weak_death_are_separate_from_click_or_model_removal(self):
        native=Boundary();before=native.snapshot();key=native.add();control=native.bind(key);ready=native.snapshot()
        chosen=source.selected(ready,control,native.profile());self.assertEqual(key,chosen['id'])
        native.click(key);clicked=native.snapshot();source.validate(clicked,dict(schemaVersion=1,action=source.ACTION,commandId=clicked['commandId'],runId=RUN,fixtureUrl=ROOT),31,previous=ready)
        self.assertEqual(1,len(clicked['buttons'][0]['clicks']));self.assertNotIn('httpStatus',clicked)
        held=native.strong[key];held_control=native.strong[control['control']];native.remove(key);removed=native.snapshot()
        source.original(removed)
        with self.assertRaises(NativeUIError):source.retired(before,removed)
        del held;gc.collect();proxy_gone=native.snapshot()
        with self.assertRaises(NativeUIError):source.retired(before,proxy_gone)
        del held_control;gc.collect();gone=native.snapshot();source.retired(before,gone)
        self.assertTrue(gone['models'][0]['alive']);self.assertTrue(gone['tablets'][0]['alive'])

    def test_label_without_original_return_caller_or_exact_visual_binding_cannot_qualify(self):
        for fault in ('return','caller','control','manager','code','root','uuid','nonce'):
            native=Boundary();key=native.add(returned=fault!='return',qualified=fault!='caller');control=native.bind(key) if fault!='return' else None;value=native.snapshot()
            source.original(value)
            if control is None:control=dict(instance='4'*32,button=key,control='6'*32,root='3'*32,rootInstance='5'*32,semanticId=native.rows[0]['semanticId'],uuid=native.rows[0]['uuid'],featureRun=RUN,fixtureUrl=ROOT,nonce='b'*32,verb='open')
            if fault=='control':control['control']='0'*32
            elif fault=='manager':value['buttons'][0]['caller']['manager']['instance']='0'*32
            elif fault=='code':value['buttons'][0]['caller']['code']['sha256']='0'*64
            elif fault=='root':control['root']='0'*32
            elif fault=='uuid':control['uuid']=str(uuid.uuid4())
            elif fault=='nonce':control['nonce']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.selected(value,control,native.profile())

    def test_history_retains_removed_buttons_and_rejects_reset_retime_resurrection_and_click_rewrite(self):
        native=Boundary();key=native.add();native.bind(key);native.click(key);before=native.snapshot();native.remove(key);current=native.snapshot()
        source.retired(before,current)
        for fault in ('instance','rootInstance','drop','click','birth','expired','resurrect','counter','boolean','private'):
            changed=deepcopy(current)
            if fault in ('instance','rootInstance'):changed[fault]='0'*32
            elif fault=='drop':changed['buttons']=[];changed['controls']=[]
            elif fault=='click':changed['buttons'][0]['clicks']=[]
            elif fault=='birth':changed['buttons'][0]['inserted']['epochMs']-=1
            elif fault=='expired':changed['buttons'][0]['expired']=deepcopy(before['clockBefore'])
            elif fault=='resurrect':changed['buttons'][0].update(expired=None,alive=True)
            elif fault=='counter':changed['sequence']=before['sequence']
            elif fault=='boolean':changed['iosTabletAppButtonsVersion']=True
            else:changed['buttons'][0]['text']='unrelated private label'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.retired(before,changed)

    def test_new_button_after_original_snapshot_needs_new_actual_native_birth(self):
        native=Boundary();key=native.add();native.bind(key);before=native.snapshot();other=native.add('inline');native.bind(other);current=native.snapshot()
        source.validate(current,dict(schemaVersion=1,action=source.ACTION,commandId=current['commandId'],runId=RUN,fixtureUrl=ROOT),31,previous=before)
        current['buttons'][1]['inserted']=deepcopy(before['buttons'][0]['inserted'])
        with self.assertRaises(NativeUIError):source.validate(current,dict(schemaVersion=1,action=source.ACTION,commandId=current['commandId'],runId=RUN,fixtureUrl=ROOT),31,previous=before)

    def test_native_observer_never_owns_product_object_or_interprets_requested_web_state(self):
        path=Path(__file__).resolve().parents[2]/'native'/'IOSTabletAppButtonsObservation.h';raw=path.read_text()
        self.assertIn('QPointer<QObject> proxy',raw);self.assertIn('QPointer<QQuickItem> item',raw)
        self.assertIn('row->removed=clock(actual)',raw);self.assertIn('!row->proxy && row->expired.isEmpty()',raw)
        self.assertNotIn('httpStatus',raw);self.assertNotIn('gotoWebScreen',raw);self.assertNotIn('SharedPointer<QObject>',raw)


if __name__=='__main__':unittest.main()
