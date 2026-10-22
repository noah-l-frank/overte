"""Synthetic lifecycle source boundaries; native remains uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
from adapters import native_script_terminal as terminal
from adapters.normal_ui import NativeUIError

MANAGER=dict(instance='a'*32,assigned=True,url='file:///owned/script-bundle/main.js',loadGeneration=1,assignedEpochMs=10000)
CODE=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=10,sha256='b'*64,submittedEpochMs=11000)


def event(index,kind):
    return dict(eventSequence=index,capturedEpochMs=12000+index,monotonicMs=index,kind=kind,threadInstance='c'*32,
        manager=deepcopy(MANAGER),code=None if index==1 else deepcopy(CODE),
        work=dict(signalCallbacks=0,timerCallbacks=0,evaluating=False,timers=0) if index==2 else None)


def packet(count=3):
    return dict(scriptTerminalObservationVersion=1,commandId='ios-'+'d'*32,instance='e'*32,sequence=1,processId=31,
        requestedEpochMs=20000,capturedEpochMs=20000,source=dict(scriptTerminalVersion=1,instance='f'*32,
        processId=31,complete=True,eventSequence=count,
        events=[event(i,k) for i,k in enumerate(('thread-bound','shutdown-drained','thread-finished'),1)][:count]))


def valid(value,previous=None):
    return terminal.validate(value,dict(schemaVersion=1,commandId=value['commandId'],action=terminal.ACTION),31,20000,previous=previous)


class TerminalTests(unittest.TestCase):
    def test_shutdown_and_independent_actual_thread_exit_are_both_required(self):
        for count in (1,2):
            value=packet(count);valid(value)
            with self.assertRaises(NativeUIError):terminal.terminal(value,MANAGER,CODE,after_sequence=1,after_epoch=12001)
        value=packet();rows=terminal.terminal(value,MANAGER,CODE,after_sequence=1,after_epoch=12001)
        self.assertEqual(['thread-bound','shutdown-drained','thread-finished'],[r['kind'] for r in rows])

    def test_stop_ack_or_finished_signal_cannot_be_relabeled_thread_exit(self):
        for kind in ('finished','doneRunning','stopping','stop-ack'):
            value=packet();value['source']['events'][-1]['kind']=kind
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):valid(value)

    def test_callback_timer_evaluation_pending_or_boolean_counters_fail_closed(self):
        for key,replacement in (('signalCallbacks',1),('timerCallbacks',1),('timers',1),('evaluating',True),('timers',False)):
            value=packet();value['source']['events'][1]['work'][key]=replacement
            with self.subTest(key=key,value=replacement),self.assertRaises(NativeUIError):valid(value)

    def test_prefix_is_immutable_and_cannot_reset_source_birth_or_drop_events(self):
        before=packet(1);after=packet();after.update(commandId='ios-'+'1'*32,sequence=2);valid(after,before)
        for fault in ('retime','manager','root','ledger','drop','partial'):
            value=deepcopy(after)
            if fault=='retime':value['source']['events'][0]['capturedEpochMs']+=1
            elif fault=='manager':
                for row in value['source']['events']:row['manager']['url']='file:///foreign.js'
            elif fault=='root':value['instance']='1'*32
            elif fault=='ledger':value['source']['instance']='2'*32
            elif fault=='drop':value['source']['events'].pop(0);value['source']['eventSequence']-=1
            else:value['source']['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):valid(value,before)

    def test_foreign_source_code_or_pre_stop_shutdown_cannot_retire_owned_marker(self):
        for fault in ('manager','code','floor','epoch','thread'):
            value=packet();manager=deepcopy(MANAGER);code=deepcopy(CODE);floor=1;epoch=12001
            if fault=='manager':manager['url']='file:///foreign.js'
            elif fault=='code':code['sha256']='0'*64
            elif fault=='floor':floor=2
            elif fault=='epoch':epoch=12003
            else:value['source']['events'][2]['threadInstance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                terminal.terminal(value,manager,code,after_sequence=floor,after_epoch=epoch)

    def test_reader_lost_result_is_not_resent_and_restore_keeps_original_prefix(self):
        sends=[];now=[0.];current=[packet()]
        def send(query):sends.append(query);current[0]['commandId']=query['commandId']
        reader=terminal.NativeScriptTerminal(send,lambda:json.dumps(current[0]),lambda:20000,lambda:True,31,
            ios=True,monotonic=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n))
        first=reader.read(0);self.assertEqual(1,len(sends));reader2=terminal.NativeScriptTerminal(send,lambda:'',lambda:20000,
            lambda:True,31,ios=True,monotonic=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n))
        reader2.restore(first);self.assertEqual(first,reader2.last)
        with self.assertRaises(NativeUIError):reader2.read(1)
        self.assertEqual(2,len(sends));self.assertEqual(first,reader2.last)

    def test_native_ledger_is_gated_bounded_and_has_no_product_owner_retention(self):
        path=Path(__file__).resolve().parents[3]/'libraries/script-engine/src/ScriptTerminalObservation.h'
        source=path.read_text();self.assertIn('OVERTE_E2E_FEATURE_TESTS',source);self.assertIn('--testScript',source)
        self.assertIn('_events.size()>=512',source);self.assertNotIn('shared_ptr',source);self.assertNotIn('QPointer',source)
        self.assertIn('QThread::finished',source);self.assertIn('epoch<_lastEpoch',source)


if __name__=='__main__':unittest.main()
