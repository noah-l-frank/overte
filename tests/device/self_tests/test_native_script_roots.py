"""Original application root metadata, using synthetic native sources only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_script_roots import NativeScriptRoots,command,root_url,validate
from adapters.normal_ui import NativeUIError


class RootBoundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.instance='a'*32
        self.root='file:///actual/configured/cache/scripts';self.running_url='file:///foreign/scripts/emote.js'
        self.value=None;self.commands=[];self.ignored=False;self.okay=True;self.mutate=None
    def sleep(self,value):self.clock+=value
    def send(self,request):
        command(request,ios=request['commandId'].startswith('ios-'));self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        self.value=dict(scriptRootsVersion=1,commandId=request['commandId'],instance=self.instance,sequence=self.sequence,
            processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=dict(defaultScriptsUrl=self.root))
        if self.mutate:self.mutate(self.value)
    def original(self):return json.dumps(self.value) if self.value is not None else ''
    def reader(self,**kwargs):
        return NativeScriptRoots(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**kwargs)


class ScriptRootTests(unittest.TestCase):
    def test_actual_configured_root_remains_independent_of_running_source_or_requested_name(self):
        source=RootBoundary();reader=source.reader();first=reader.read(0)
        self.assertEqual(source.root,first['source']['defaultScriptsUrl'])
        self.assertEqual('file:///actual/configured/cache/scripts/',root_url(first['source']['defaultScriptsUrl']))
        source.running_url='file:///another/foreign/phoneEmote.js';second=reader.read(first['sequence'])
        self.assertEqual(first['source'],second['source']);self.assertNotEqual(first['commandId'],second['commandId'])
        self.assertTrue(all(set(request)=={'schemaVersion','commandId','action'} for request in source.commands))
        self.assertNotIn('expected',str(source.commands));self.assertNotIn('foreign',str(source.commands))
    def test_file_and_qrc_trailing_separator_normalization_preserves_original_packet(self):
        source=RootBoundary();source.root='qrc:///scripts';value=source.reader().read(0);before=deepcopy(value)
        self.assertEqual('qrc:/scripts/',root_url(value['source']['defaultScriptsUrl']));self.assertEqual(before,value)
        self.assertEqual('file:///actual/scripts/',root_url('file:///actual/scripts/'))
    def test_unknown_remote_encoded_foreign_or_traversed_resource_roots_have_no_fallback(self):
        for root in ('','https://foreign/scripts','file://foreign/scripts','file:///actual/../scripts','file:///actual/%2e%2e/scripts',
            'file:///actual/scripts?expected=known','file:///actual/scripts#fragment','file:///actual//scripts',
            'file:///actual/other','qrc:/scripts\n','file:///actual\\scripts'):
            source=RootBoundary();source.root=root
            with self.subTest(root=root),self.assertRaises(NativeUIError):source.reader().read(0)
    def test_foreign_nonce_birth_process_clock_types_or_extra_expectations_are_refused(self):
        for fault in ('nonce','instance','pid','epoch','request-time','sequence','version','expected','unavailable'):
            source=RootBoundary();reader=source.reader();first=reader.read(0)
            def changed(value):
                if fault=='nonce':value['commandId']=first['commandId']
                elif fault=='instance':value['instance']='b'*32
                elif fault=='pid':value['processId']=32
                elif fault=='epoch':value['capturedEpochMs']=18000
                elif fault=='request-time':value['requestedEpochMs']=19999
                elif fault=='sequence':value['sequence']=True
                elif fault=='version':value['scriptRootsVersion']=True
                elif fault=='expected':value['expectedRoot']=source.root
                else:value.clear();value.update(commandId=source.commands[-1]['commandId'],available=False)
            source.mutate=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(first['sequence'])
            self.assertEqual(first,reader.last)
    def test_changed_actual_root_or_restarted_counter_cannot_be_silently_adopted(self):
        source=RootBoundary();reader=source.reader();first=reader.read(0);source.root='file:///another/scripts'
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        source=RootBoundary();reader=source.reader();first=reader.read(0);source.sequence=0
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
    def test_reconstruction_restores_only_the_exact_original_cursor_and_root(self):
        source=RootBoundary();first=source.reader().read(0);reader=source.reader();reader.restore(first)
        first['source']['defaultScriptsUrl']='file:///mutated-copy/scripts'
        second=reader.read(1);self.assertEqual(source.root,second['source']['defaultScriptsUrl'])
        with self.assertRaises(NativeUIError):reader.restore(second)
        source.root='file:///foreign/scripts';reader=source.reader();reader.restore(second)
        with self.assertRaises(NativeUIError):reader.read(second['sequence'])
    def test_unknown_or_foreign_restored_protocol_and_invalid_cursors_send_no_query(self):
        source=RootBoundary();original=source.reader(ios=True).read(0)
        with self.assertRaises(NativeUIError):source.reader().restore(original)
        for cursor in (True,-1,1_000_000_001):
            source=RootBoundary()
            with self.subTest(cursor=cursor),self.assertRaises(NativeUIError):source.reader().read(cursor)
            self.assertEqual([],source.commands)
    def test_frozen_external_clock_cannot_hide_a_slow_original_acquisition(self):
        source=RootBoundary();source.mutate=lambda value:setattr(source,'clock',source.clock+2)
        with self.assertRaises(NativeUIError):source.reader().read(0)
        source=RootBoundary();source.mutate=lambda value:setattr(source,'clock',-1)
        with self.assertRaises(NativeUIError):source.reader().read(0)
    def test_slow_final_packet_copies_cannot_escape_frozen_native_or_host_clock_guards(self):
        for changed in ('host','native'):
            source=RootBoundary();reader=source.reader();original=reader.read(0)
            def slow(value):
                copied=deepcopy(value)
                if type(value) is dict and 'scriptRootsVersion' in value:
                    if changed=='host':source.clock+=2
                    else:source.epoch+=2000
                return copied
            with self.subTest(clock=changed),patch('adapters.native_script_roots.deepcopy',slow),self.assertRaises(NativeUIError):
                reader.read(original['sequence'])
            self.assertEqual(original,reader.last)

    def test_last_original_guard_clock_jump_after_copy_never_advances_the_reader_cursor(self):
        for changed in ('host','native'):
            source=RootBoundary();reader=source.reader();original=reader.read(0);armed=[False]
            def copy(value):
                result=deepcopy(value)
                if type(value) is dict and 'scriptRootsVersion' in value:armed[0]=True
                return result
            def guard():
                if armed[0]:
                    if changed=='host':source.clock+=2
                    else:source.epoch+=2000
                return True
            reader.guard=guard
            with self.subTest(clock=changed),patch('adapters.native_script_roots.deepcopy',copy),self.assertRaises(NativeUIError):
                reader.read(original['sequence'])
            self.assertEqual(original,reader.last)

    def test_missing_result_foreign_guard_or_oversized_original_never_returns_a_guessed_root(self):
        source=RootBoundary();source.ignored=True
        with self.assertRaises(NativeUIError):source.reader().read(0)
        self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5.1)
        source=RootBoundary();source.okay=False
        with self.assertRaises(NativeUIError):source.reader().read(0)
        self.assertEqual([],source.commands)
        source=RootBoundary();reader=source.reader();reader.original=lambda:'x'*16385
        with self.assertRaises(NativeUIError):reader.read(0)
    def test_actual_request_grammar_rejects_path_selection_and_expected_results(self):
        value=dict(schemaVersion=1,commandId='a'*32,action='feature-script-roots-observe')
        command(value)
        for edit in (dict(schemaVersion=True),dict(commandId='a'*32+'\n'),dict(root='file:///expected/scripts'),
            dict(sourceUrl='file:///another/emote.js'),dict(action='set-script-root')):
            with self.subTest(fields=list(edit)),self.assertRaises(NativeUIError):command(value|edit)


if __name__=='__main__':unittest.main()
