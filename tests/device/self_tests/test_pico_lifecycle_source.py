"""Explicit native/Qt/entity-keyboard boundaries; no headset qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import lifecycle_source
from adapters.pico4.lifecycle_source import PicoLifecycleSource,current_editor,summary,validate,accept
from adapters.normal_ui import NativeUIError
from self_tests.test_pico_chat_keyboard import keyboard

RUN='a'*32

def editor(index=1,kind='create'):
    return dict(id=f'{index:032x}',kind=kind,fieldId=f'{index+100:032x}',pageId=f'{index+200:032x}',
        contextId=f'{index+300:032x}',windowId='1'*32,loaderId='2'*32,firstObservedEpochMs=19000,
        fieldAlive=True,pageAlive=True,contextAlive=True,windowAlive=True,loaderAlive=True,
        alive=True,attached=True,visible=True,focused=True,current=True,text='')


class Boundary:
    def __init__(self):
        self.clock,self.sequence,self.value=0.,0,None
        self.rows=[editor()];self.home,self.shown,self.raised=False,True,True
        self.commands,self.mutate,self.alive,self.ignore=[],None,True,False
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1;k=keyboard(self.raised);k['sequence']=self.sequence
        selected=[row['id'] for row in self.rows if row['current']]
        self.value=dict(lifecycleUiVersion=1,commandId=request['commandId'],runId=request['runId'],
            instance='c'*32,sequence=self.sequence,processId=123,capturedEpochMs=20000,
            source=dict(complete=True,tabletShown=self.shown,onHomeScreen=self.home,
                current=selected[0] if selected else '',editors=deepcopy(self.rows),keyboard=k))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value) if self.value else ''
    def sleep(self,value):self.clock+=value
    def source(self):return PicoLifecycleSource(self.send,self.read,lambda:20000,lambda:self.alive,123,
        monotonic=lambda:self.clock,sleep=self.sleep)
    def retire(self):
        self.rows[0].update(fieldAlive=False,pageAlive=False,contextAlive=False,alive=False,attached=False,visible=False,focused=False,current=False,text='')
        self.home,self.raised=True,False


class LifecycleSourceTests(unittest.TestCase):
    def test_original_context_tokens_and_raw_source_bytes_are_preserved(self):
        native=Boundary();source=native.source();packet=source.capture(RUN)
        self.assertEqual(editor(),current_editor(packet))
        self.assertEqual(source.last_raw,native.read())
        self.assertEqual(hashlib.sha256(native.read().encode()).hexdigest(),source.last_sha256)
        packet['source']['editors'][0]['contextId']='f'*32
        self.assertEqual(editor()['contextId'],current_editor(source.capture(RUN))['contextId'])
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(native.commands[0]))

    def test_actual_retirement_and_new_field_have_distinct_original_identity(self):
        native=Boundary();source=native.source();old=source.capture(RUN)
        native.retire();retired=source.capture(RUN)
        self.assertIsNone(current_editor(retired));self.assertFalse(retired['source']['editors'][0]['alive'])
        native.rows.append(editor(2,'scripts'));native.home=False
        fresh=source.capture(RUN);self.assertNotEqual(current_editor(old)['id'],current_editor(fresh)['id'])
        self.assertEqual(2,len(fresh['source']['editors']))

    def test_durable_summary_pins_native_and_keyboard_cursors_across_host_reconstruction(self):
        native=Boundary();first=native.source().capture(RUN);restored=native.source();restored.restore(summary(first))
        self.assertGreater(restored.capture(RUN)['sequence'],first['sequence'])
        native.mutate=lambda value:value['source']['editors'][0].update(contextId='f'*32)
        with self.assertRaises(NativeUIError):restored.capture(RUN)

    def test_missing_old_contexts_rewritten_creation_ids_and_resurrection_fail(self):
        for fault in ('drop','kind','time','field','resurrect'):
            with self.subTest(fault=fault):
                native=Boundary();source=native.source();source.capture(RUN)
                if fault=='resurrect':native.retire();source.capture(RUN);native.rows=[editor()];native.home=False
                else:
                    def mutate(value):
                        row=value['source']['editors'][0]
                        if fault=='drop':value['source'].update(editors=[],current='')
                        elif fault=='kind':row['kind']='scripts'
                        elif fault=='time':row['firstObservedEpochMs']+=1
                        else:row['fieldId']='f'*32
                    native.mutate=mutate
                with self.assertRaises(NativeUIError):source.capture(RUN)

    def test_partial_objects_and_hidden_detached_pages_remain_retained(self):
        for flag in ('fieldAlive','contextAlive','hidden','detached'):
            with self.subTest(flag=flag):
                native=Boundary();source=native.source();source.capture(RUN)
                row=native.rows[0];row.update(current=False,text='')
                if flag=='fieldAlive':row.update(fieldAlive=False,attached=False,visible=False,focused=False)
                elif flag=='contextAlive':row['contextAlive']=False
                elif flag=='hidden':row.update(visible=False,focused=False)
                else:row.update(attached=False,visible=False,focused=False)
                native.home=True;retained=source.capture(RUN)['source']['editors'][0]
                self.assertTrue(retained['alive']);self.assertTrue(retained['pageAlive'])
                self.assertTrue(retained['windowAlive']);self.assertTrue(retained['loaderAlive'])
                self.assertIsNone(current_editor(source.capture(RUN)))
                if flag in ('fieldAlive','contextAlive'):
                    row[flag]=True
                    with self.assertRaises(NativeUIError):source.capture(RUN)

    def test_missing_liveness_and_partial_or_shared_owner_resurrection_fail(self):
        for flag in ('fieldAlive','pageAlive','contextAlive','windowAlive','loaderAlive'):
            native=Boundary();native.mutate=lambda v:v['source']['editors'][0].pop(flag)
            with self.subTest(missing=flag),self.assertRaises(NativeUIError):native.source().capture(RUN)
            native=Boundary();source=native.source();source.capture(RUN)
            native.retire();native.rows[0][flag]=False;source.capture(RUN)
            native.rows[0][flag]=True
            if flag in ('fieldAlive','pageAlive','contextAlive'):native.rows[0]['alive']=True
            with self.subTest(resurrected=flag),self.assertRaises(NativeUIError):source.capture(RUN)

    def test_foreign_or_stale_packet_and_malformed_current_source_never_become_none(self):
        edits=(lambda v:v.update(processId=8),lambda v:v.update(runId='b'*32),
            lambda v:v.update(instance='x'),lambda v:v.update(capturedEpochMs=18000),
            lambda v:v['source'].update(complete=False),lambda v:v['source'].update(current=''),
            lambda v:v['source'].update(onHomeScreen=True),lambda v:v['source'].update(tabletShown=False),
            lambda v:v['source']['editors'][0].update(alive=False),
            lambda v:v['source']['editors'][0].update(text='unowned private draft'),
            lambda v:v['source']['editors'].append(deepcopy(v['source']['editors'][0])))
        for edit in edits:
            native=Boundary();native.mutate=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):native.source().capture(RUN)

    def test_foreign_keyboard_owner_and_replayed_independent_keyboard_cursor_fail(self):
        for fault in ('instance','sequence','touch'):
            native=Boundary();source=native.source();source.capture(RUN)
            def mutate(value):
                k=value['source']['keyboard']
                if fault=='instance':k['instance']='f'*32
                elif fault=='sequence':k['sequence']=1
                else:value['source']['keyboard']=dict(available=True,backend='native-touch-metrics',visible=False)
            native.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.capture(RUN)

    def test_ignored_original_query_is_bounded_and_never_reissued(self):
        native=Boundary();native.ignore=True
        with self.assertRaises(NativeUIError):native.source().capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertLessEqual(native.clock,5.1)

    def test_final_accept_and_guard_age_are_bounded_with_a_frozen_device_clock(self):
        for fault in ('accept','guard'):
            native=Boundary();source=native.source();source.capture(RUN);original=deepcopy(source.previous)
            if fault=='accept':
                accept_original=lifecycle_source.accept
                def slow(*args):
                    value=accept_original(*args);native.clock+=2;return value
                with mock.patch.object(lifecycle_source,'accept',side_effect=slow):
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.capture(RUN)
            else:
                calls=0
                def slow_guard():
                    nonlocal calls
                    calls+=1
                    if calls==4:native.clock+=2
                    return True
                source.guard=slow_guard
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.capture(RUN)
            self.assertEqual(original,source.previous)

    def test_oversize_or_non_string_original_is_rejected_before_json_decoding_even_for_another_nonce(self):
        for raw in (' '*262145,None,{'commandId':'f'*32}):
            native=Boundary();source=native.source();source.original=lambda:raw
            with mock.patch.object(lifecycle_source,'decode') as decoder:
                with self.subTest(raw_type=type(raw)),self.assertRaises(NativeUIError):source.capture(RUN)
                decoder.assert_not_called()

    def test_transfer_deadline_and_lost_process_do_not_commit_the_new_source_cursor(self):
        native=Boundary();source=native.source();first=source.capture(RUN)
        original=source.original
        def late():native.clock+=6;return original()
        source.original=late
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(summary(first),source.previous)
        native.alive=False
        with self.assertRaises(NativeUIError):native.source().capture(RUN)


if __name__=='__main__':unittest.main()
