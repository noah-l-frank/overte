"""Actual JavaScript output through strict Tablet DOM body boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_dom as dom
from ios.self_tests.test_ios_tablet_web_source import query,RUN,ROOT

ROOT_PATH=Path(__file__).resolve().parents[4]


def request(index):return dict(query(index),action=dom.ACTION)


class TabletWebDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        program='''
const fixture=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js');
(async()=>{const result=[];for(const inline of [false,true]){const p=fixture.page({inline});
const before=p.read('ios-'+(1).toString(16).padStart(32,'0'));
p.nodes.get('text').value='Überte 🙂';p.doc.activeElement=p.nodes.get('text');p.event('text','input');
p.click('bridge');const sent=JSON.parse(p.outbound[0]),reply=JSON.stringify({...sent,surface:'tablet'});
for(const callback of p.callbacks)callback(reply);await Promise.resolve();await Promise.resolve();
const after=p.read('ios-'+(2).toString(16).padStart(32,'0'));result.push({before,after});}process.stdout.write(JSON.stringify(result));})().catch(e=>{console.error(e);process.exitCode=1;});'''
        out=subprocess.run(['node','-e',program],cwd=ROOT_PATH,capture_output=True,text=True,timeout=5)
        if out.returncode:raise AssertionError(out.stderr)
        cls.originals=json.loads(out.stdout)

    def test_actual_observer_reference_echo_input_and_optional_inline_metadata_are_original(self):
        for inline,rows in enumerate(self.originals):
            a,b=rows['before'],rows['after'];dom.body(a,request(1),a['capturedEpochMs']);dom.body(b,request(2),b['capturedEpochMs'],a)
            self.assertEqual('Überte 🙂',b['editor']['text']);self.assertTrue(b['editor']['focused']);self.assertEqual(1,len(b['echoes']))
            self.assertEqual('tablet',b['echoes'][0]['surface']);self.assertEqual(bool(inline),b['document']['responseId'] is None)
            self.assertEqual({'input','pointerdown','pointerup','click'},{row['kind'] for row in b['events']})
            self.assertTrue(all(row['trusted'] for row in b['events']));self.assertNotIn('key',b['events'][0])
        self.assertEqual(dom.SOURCE_SHA256,hashlib.sha256((ROOT_PATH/'tests/device/native/ios_tablet_web_dom.js').read_bytes()).hexdigest())

    def test_wrong_surface_echo_keytext_password_value_viewport_and_composition_forgery_are_rejected(self):
        original=self.originals[0]['after']
        for fault in ('echo','key','password','passwordType','viewport','boolPointer','composition','compositionBool','expected'):
            value=deepcopy(original)
            if fault=='echo':value['echoes'][0]['surface']='world'
            elif fault=='key':value['events'][0]['key']='private key text'
            elif fault=='password':next(row for row in value['elements'] if row['id']=='bridge')['value']='secret'
            elif fault=='passwordType':next(row for row in value['elements'] if row['id']=='text')['type']='password'
            elif fault=='viewport':value['document']['visualViewport']['offsetTop']=300
            elif fault=='boolPointer':value['events'][1]['pointerId']=True
            elif fault=='composition':value['compositions']=[dict(target=1,active=True)]
            elif fault=='compositionBool':value['compositions']=[dict(target=1,active=1)]
            else:value['expectedBridgeMessages']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):dom.body(value,request(2),value['capturedEpochMs'])

    def test_original_prefix_and_retained_document_cannot_reset_or_change_owner_response(self):
        before=deepcopy(self.originals[0]['after']);before['requestId']=request(2)['commandId']
        for fault in ('prefix','instance','sequence','response','run','clock'):
            value=deepcopy(before);value['requestId']=request(3)['commandId'];value['sequence']+=1
            if fault=='prefix':value['events'].pop(0)
            elif fault=='instance':value['instance']='9'*32
            elif fault=='sequence':value['sequence']=before['sequence']
            elif fault=='response':value['document']['responseId']='9'*32
            elif fault=='run':value['document']['runId']='9'*32
            else:value['capturedEpochMs']-=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):dom.body(value,request(3),before['capturedEpochMs'],before)


if __name__=='__main__':unittest.main()
