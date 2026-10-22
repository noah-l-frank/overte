"""UIKit2 real-control provenance, with unchanged v1 historical decoding."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from ios.adapters import uikit_input as source
from ios.self_tests.test_ios_uikit_input import packet as legacy,query,RUN,ROOT
from ios.self_tests.test_ios_tablet_web_buttons import Boundary


def packet(index=1,*,dead=False):
    button=Boundary();key=button.add();control=button.bind(key);buttons=button.snapshot()
    value=legacy(index,phase='ended',dead=dead);value['iosUIKitInputVersion']=2
    def shift(item):
        if type(item) is dict:
            if set(item)=={'epochMs','monotonicMs'}:item['epochMs']+=1700000000000-90000
            else:
                for child in item.values():shift(child)
        elif type(item) is list:
            for child in item:shift(child)
    shift(value)
    target=dict(view='1'*32,qtControl=dict(control,sourceToken=str(uuid.uuid4())),bound=deepcopy(value['targets'][0]['bound']))
    value['targets']=[target];association=dict(deepcopy(target),ancestry=['1'*32])
    for row in value['contacts']:row['source']=deepcopy(association)
    for row in value['dispatches']:
        for phase in row['phases']:phase['source']=deepcopy(association)
    return value,buttons


class UIKitInputControlTests(unittest.TestCase):
    def test_actual_qt_control_and_returned_proxy_join_without_fake_WK_identity(self):
        value,buttons=packet(2);source.original(value);source.join_buttons(value,buttons)
        self.assertNotIn('identity',value['targets'][0]);self.assertNotIn('httpStatus',value)
        before=legacy();before['iosUIKitInputVersion']=2
        for key in ('clockBefore','clockAfter','installation'):before[key]['epochMs']+=1700000000000-90000
        source.quiescent(before,value,after_epoch=1700000000001,require_delivery=True)
        with self.assertRaises(NativeUIError):source.retired(before,value)
        dead,_=packet(3,dead=True)
        # Preserve actual native Qt/control originals for the same cached
        # UIButton and contact. A freshly generated app identity cannot replace
        # an earlier original while merely keeping the same native object IDs.
        dead['targets']=deepcopy(value['targets'])
        for row in dead['contacts']:row['source']=deepcopy(value['contacts'][0]['source'])
        for row in dead['dispatches']:
            for phase in row['phases']:phase['source']=deepcopy(value['contacts'][0]['source'])
        source.join_buttons(dead,buttons);self.assertEqual({'1'*32,'3'*32,'4'*32},set(source.retired(value,dead)))

    def test_missing_original_caller_proxy_root_visual_or_actual_binding_cannot_join(self):
        value,buttons=packet()
        for fault in ('caller','uuid','root','visual','instance','late','fixture'):
            changed=deepcopy(buttons)
            if fault=='caller':changed['buttons'][0]['caller']=None
            elif fault=='uuid':changed['buttons'][0]['uuid']=str(uuid.uuid4())
            elif fault=='root':changed['buttons'][0]['root']='0'*32;changed['controls'][0]['root']='0'*32
            elif fault=='visual':changed['controls'][0]['id']='0'*32
            elif fault=='instance':changed['rootInstance']='0'*32
            elif fault=='late':changed['buttons'][0]['returned']['epochMs']=1700000001000
            else:changed['fixtureUrl']=ROOT.replace(':18000',':18001')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.join_buttons(value,changed)

    def test_v1_original_remains_exact_and_cannot_provide_new_control_variant_or_live_source(self):
        old=legacy(phase='ended');self.assertEqual(old,source.original(deepcopy(old)))
        changed,_=packet();changed['iosUIKitInputVersion']=1
        with self.assertRaises(NativeUIError):source.original(changed)
        calls=[];raw={}
        def send(q):calls.append(deepcopy(q));raw['value']=json.dumps(dict(old,commandId=q['commandId']))
        reader=source.IOSUIKitInput(send,lambda:raw['value'],lambda:90621,lambda:True,31,monotonic=lambda:0)
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        self.assertEqual(1,len(calls));self.assertIsNone(reader.last)

    def test_immutable_control_target_and_private_closed_grammar_reject_rebinding_and_WK_alias(self):
        value,buttons=packet()
        for fault in ('sourceToken','private','fakeWK','fixture','bool'):
            changed=deepcopy(value)
            if fault=='sourceToken':changed['targets'][0]['qtControl']['sourceToken']='0'*32
            elif fault=='private':changed['targets'][0]['qtControl']['label']='private UI text'
            elif fault=='fakeWK':changed['targets'][0]['identity']={}
            elif fault=='fixture':changed['targets'][0]['qtControl']['fixtureUrl']=ROOT+'other/'
            else:changed['iosUIKitInputVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(changed)
        newer=deepcopy(value);newer.update(sequence=2,commandId=query(2)['commandId']);newer['clockBefore']['epochMs']+=1;newer['clockAfter']['epochMs']+=1
        newer['clockBefore']['monotonicMs']+=1;newer['clockAfter']['monotonicMs']+=1
        newer['targets'][0]['qtControl']['sourceToken']=str(uuid.uuid4())
        for row in newer['contacts']:row['source']['qtControl']=deepcopy(newer['targets'][0]['qtControl'])
        for row in newer['dispatches']:
            for phase in row['phases']:phase['source']['qtControl']=deepcopy(newer['targets'][0]['qtControl'])
        source.original(newer)
        with self.assertRaises(NativeUIError):source.validate(newer,query(2),31,previous=value)


if __name__=='__main__':unittest.main()
