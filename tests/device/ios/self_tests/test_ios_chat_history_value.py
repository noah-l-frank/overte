"""Typed original history hash source/relations; Qt serialization is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import subprocess
import unittest
from adapters.native_chat_view import measured_view,validate
from adapters.normal_ui import NativeUIError
from ios.adapters.chat_history_value import unchanged_empty
from self_tests.test_native_chat_view import Boundary,RUN


class TypedBoundary(Boundary):
    """Explicit original modeled QVariant bytes, never actual Qt serialization."""
    def __init__(self):
        super().__init__();self.original_bytes=b'present:QVariant:invalid'
        self.source.update(editorFocused=False,editorHasDraft=False,ui=dict(present=False),
            keyboard=dict(available=True,backend='native-touch-metrics',visible=False))
        self.source['storage'].update(kind='null',count=0,unowned=0,events=[])
    def send(self,request):
        super().send(request)
        if self.value is not None:
            self.value['chatViewVersion']=2
            self.value['source']['storage']['valueSha256']=hashlib.sha256(self.original_bytes).hexdigest()


class ChatHistoryValueTests(unittest.TestCase):
    def pair(self):
        self.n=TypedBoundary();reader=self.n.reader();return reader,reader.read(RUN)
    def test_independent_originals_retain_exact_empty_value_without_current_queries_or_writes(self):
        reader,before=self.pair();after=reader.read(RUN);commands=deepcopy(self.n.commands)
        original=(deepcopy(before),deepcopy(after));self.assertTrue(unchanged_empty(before,after))
        self.assertEqual(original,(before,after));self.assertEqual(commands,self.n.commands)
        self.assertFalse(measured_view(after)['open'])
    def test_same_null_kind_cannot_hide_a_different_actual_variant_type_or_presence(self):
        reader,before=self.pair()
        for raw in (b'present:QString:null',b'absent:QVariant:invalid',b'present:QString:empty'):
            with self.subTest(raw=raw):
                self.n.original_bytes=raw;after=reader.read(RUN)
                self.assertEqual(before['source']['storage']['kind'],after['source']['storage']['kind'])
                with self.assertRaises(NativeUIError):unchanged_empty(before,after)
    def test_changed_configuration_or_nonempty_history_does_not_count_as_original_restoration(self):
        reader,before=self.pair();self.n.source['storage']['configSha256']='f'*64
        with self.assertRaises(NativeUIError):unchanged_empty(before,reader.read(RUN))
        self.n.source['storage']['configSha256']=before['source']['storage']['configSha256']
        self.n.source['storage'].update(kind='array',count=1,events=[dict(channel='domain',text='reply-'+RUN,timestamp=19000)])
        with self.assertRaises(NativeUIError):unchanged_empty(before,reader.read(RUN))
    def test_old_readable_literal_one_never_acquires_a_typed_value_hash_by_inference(self):
        n=Boundary();value=n.reader().read(RUN);self.assertEqual(1,value['chatViewVersion']);measured_view(value)
        with self.assertRaises(NativeUIError):unchanged_empty(value,value)
        bad=deepcopy(value);bad['source']['storage']['valueSha256']='e'*64
        with self.assertRaises(NativeUIError):validate(bad,n.commands[-1],123,20000)
    def test_missing_malformed_or_expected_hash_fields_are_unavailable(self):
        reader,before=self.pair();after=reader.read(RUN);request=self.n.commands[-1]
        for value in (None,True,'','a'*63,'a'*64+'\n'):
            with self.subTest(value=value):
                changed=deepcopy(after);changed['source']['storage']['valueSha256']=value
                with self.assertRaises(NativeUIError):validate(changed,request,123,20000)
        changed=deepcopy(after);changed['source']['storage'].pop('valueSha256')
        with self.assertRaises(NativeUIError):validate(changed,request,123,20000)
        changed=deepcopy(after);changed['source']['storage']['expectedSha256']='e'*64
        with self.assertRaises(NativeUIError):validate(changed,request,123,20000)
    def test_reused_nonce_old_sequence_or_foreign_source_cannot_supply_the_after_original(self):
        reader,before=self.pair();after=reader.read(RUN)
        for edit in ({'commandId':before['commandId']},{'sequence':before['sequence']},{'instance':'d'*32},{'processId':124},{'runId':'b'*32}):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):unchanged_empty(before,dict(after,**edit))

    def test_actual_probe_retains_literal_two_hash_and_does_not_requery_current_nonce(self):
        from self_tests.test_native_feature_observation import probe_source
        n=TypedBoundary();original=n.reader(ios=True).read(RUN)
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=ORIGINAL,files=[];let calls=0;
const Test={featureChatViewObservation:c=>{calls++;return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const command={schemaVersion:1,commandId:original.commandId,action:"feature-chat-view-observe",runId:original.runId};
applyClientCommand(command);applyClientCommand(command);
if(calls!==1||files.length!==1||files[0].name!=="feature-chat-view-observation.json"
 ||JSON.stringify(files[0].v)!==JSON.stringify(original))throw Error("Typed original changed or native query repeated");
'''.replace('ORIGINAL',json.dumps(original)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_live_reader_cannot_change_protocol_within_the_same_native_instance(self):
        for typed in (False,True):
            with self.subTest(typed=typed):
                n=TypedBoundary() if typed else Boundary();reader=n.reader();before=reader.read(RUN);send=reader.send
                def switched(request):
                    send(request)
                    if typed:
                        n.value['chatViewVersion']=1;n.value['source']['storage'].pop('valueSha256')
                    else:
                        n.value['chatViewVersion']=2;n.value['source']['storage']['valueSha256']='a'*64
                    validate(n.value,request,123,20000) # Valid individually, foreign protocol for this birth.
                reader.send=switched
                with self.assertRaises(NativeUIError):reader.read(RUN)
                self.assertEqual(before['chatViewVersion'],reader.version);self.assertEqual(2,len(n.commands))


if __name__=='__main__':unittest.main()
