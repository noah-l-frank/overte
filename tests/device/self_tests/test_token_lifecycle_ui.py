"""Real token reader over explicit native field/input boundaries, no client run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.token_lifecycle_ui import ID,OBJECTS,TokenLifecycleUI,same_reference,snapshot
from feature_journeys.fixtures import context

RUN='a'*32


class Boundary:
    def __init__(self):
        self.clock=0.;self.sequence=0;self.focused=False;self.text='';self.field='1'*32;self.before=None;self.ignore=set();self.calls=[]
        self.lost=False;self.component='e'*64;self.generation='2'*32
    def capture(self):
        return dict(lifecycleControlsVersion=1,open=True,ready=True,
            scope=dict(instance='3'*32,generation=self.generation,sequence=self.sequence,elapsedMs=round(self.clock*1000),processId=123),
            controls=[dict(id=ID,token='4'*32,enabled=True,focused=self.focused,inputReady=True,text=self.text,
                fieldId=self.field,pageId='5'*32,contextId='6'*32,windowId='7'*32,componentSourceSha256=self.component)])
    def input(self,identifier,action,value=None,*,reference):
        if self.before:self.before()
        same_reference(reference,self.capture(),identifier);self.calls.append((identifier,action,value));self.sequence+=1
        if action not in self.ignore:
            if action=='activate':self.focused=True
            else:self.text=value
        if self.lost:raise NativeUIError('Explicit lost native input response')
    def activate(self,identifier,*,reference):self.input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):self.input(identifier,'replace',value,reference=reference)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,intent=lambda _value:None):return TokenLifecycleUI(self,intent,RUN,monotonic=lambda:self.clock,sleep=self.sleep)


class LifecycleControlTests(unittest.TestCase):
    def test_unicode_draft_uses_original_field_and_reads_focus_text_after_consumption(self):
        io=Boundary();intents=[];reader=io.reader(intents.append);result=reader.type_owned()
        self.assertEqual(context(RUN)['unicode'],result['controls'][0]['text']);self.assertTrue(result['controls'][0]['focused'])
        self.assertEqual(['activate','replace'],[call[1] for call in io.calls]);self.assertEqual(2,len(intents))
        self.assertEqual({key:result['controls'][0][key] for key in OBJECTS},intents[-1]['objects'])
    def test_ignored_focus_or_ime_with_consumed_cursor_is_not_an_effect_or_retry(self):
        for ignored,expected in (({'activate'},1),({'replace'},2)):
            with self.subTest(ignored=ignored):
                io=Boundary();io.ignore=ignored
                with self.assertRaises(NativeUIError):io.reader().type_owned()
                self.assertEqual(expected,len(io.calls));self.assertEqual('',io.text)
    def test_durable_intent_failure_and_aged_original_prevent_first_possible_input(self):
        io=Boundary()
        def fail(_value):raise RuntimeError('Explicit journal write failure')
        with self.assertRaises(RuntimeError):io.reader(fail).type_owned()
        self.assertEqual([],io.calls)
        with self.assertRaises(NativeUIError):io.reader(lambda _value:io.sleep(2)).type_owned()
        self.assertEqual([],io.calls)
    def test_changed_field_component_or_native_cursor_after_intent_is_not_silently_recaptured(self):
        for change in (lambda io:setattr(io,'field','8'*32),lambda io:setattr(io,'component','f'*64),lambda io:setattr(io,'sequence',1)):
            with self.subTest(change=change):
                io=Boundary();io.before=lambda:change(io)
                with self.assertRaises(NativeUIError):io.reader().type_owned()
                self.assertEqual([],io.calls);self.assertEqual('',io.text)
    def test_uncertain_ime_response_keeps_effect_original_and_cannot_type_over_nonempty_draft(self):
        io=Boundary();reader=io.reader();reader.input('activate');io.lost=True
        with self.assertRaises(NativeUIError):reader.input('replace',context(RUN)['unicode'])
        io.lost=False
        with self.assertRaises(NativeUIError):reader.type_owned()
        self.assertEqual(2,len(io.calls));self.assertEqual(context(RUN)['unicode'],io.text)
    def test_unowned_text_and_replacement_generation_do_not_receive_input(self):
        io=Boundary();io.text='Private unowned draft'
        with self.assertRaises(NativeUIError):io.reader().type_owned()
        self.assertEqual([],io.calls);io.text='';reader=io.reader();reader.capture();io.generation='9'*32
        with self.assertRaises(NativeUIError):reader.type_owned()
        self.assertEqual([],io.calls)
    def test_protocol_boolean_marker_duplicate_field_missing_original_ids_are_unavailable(self):
        io=Boundary()
        for edit in (lambda v:v.update(lifecycleControlsVersion=True),lambda v:v['controls'].append(deepcopy(v['controls'][0])),
                lambda v:v['controls'][0].pop('contextId'),lambda v:v['controls'][0].update(text='Overte ä Ω 東京 '+'b'*32)):
            value=io.capture();edit(value)
            with self.assertRaises((NativeUIError,KeyError)):
                if value['controls'] and value['controls'][0].get('text','').endswith('b'*32):
                    io.capture=lambda:value;io.reader().capture()
                else:snapshot(value)
        self.assertEqual([],io.calls)
    def test_only_closed_create_unicode_is_input_and_no_submit_or_entity_action_exists(self):
        io=Boundary();reader=io.reader()
        for action,value in (('submit',None),('activate','text'),('replace',''),('replace',context(RUN)['reply']),('replace','arbitrary')):
            with self.subTest(action=action,value=value),self.assertRaises(NativeUIError):reader.input(action,value)
        self.assertEqual([],io.calls)


if __name__=='__main__':unittest.main()
